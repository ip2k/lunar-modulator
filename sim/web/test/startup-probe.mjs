// Diagnostic only: compare unchanged startup with destination connection gated
// on ready, using the actual page/worklet/Wasm. No acceptance gate or retry.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch, which } from './launch.mjs';
import { startSchedulingCapture } from './scheduling-capture.mjs';
import { installPlaybackTimeline } from './playback-timeline.mjs';

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8767);
const { browser } = await launch();
const results = [];
try {
  for (const gated of [false, true]) {
    const dir = join(out, gated ? 'ready-gated' : 'original');
    mkdirSync(dir, { recursive: true });
    const page = await browser.newPage();
    await page.addInitScript(installPlaybackTimeline);
    await page.addInitScript(({ gated }) => {
      const events = [];
      window.__startupProbe = { events };
      const mark = (type, extra = {}) => events.push({ type, page_ms: performance.now(), ...extra });
      const Original = window.AudioWorkletNode;
      window.AudioWorkletNode = class extends Original {
        constructor(...args) {
          super(...args);
          this.probeContext = args[0]; this.probeReady = false; this.probeConnections = [];
          mark('node-created', { state: args[0].state, audio_seconds: args[0].currentTime });
          this.port.addEventListener('message', ({ data }) => {
            if (data.type === 'startup-probe') mark('init-measured', { instantiate_ms: data.instantiate_ms, setup_ms: data.setup_ms, audio_frame: data.audio_frame, rate: data.rate });
            if (data.type === 'ready') {
              mark('ready', { state: this.probeContext.state, audio_seconds: this.probeContext.currentTime });
              this.probeReady = true;
              for (const args of this.probeConnections) this.connect(...args);
              this.probeConnections = [];
            }
          });
          this.port.start();
        }
        connect(...args) {
          mark('connect-request', { destination: args[0].constructor.name, ready: this.probeReady });
          if (gated && !this.probeReady) { this.probeConnections.push(args); return args[0]; }
          const result = super.connect(...args);
          mark('connected', { destination: args[0].constructor.name, ready: this.probeReady });
          return result;
        }
      };
    }, { gated });
    // Instrument only the diagnostic response. Fail loudly if source drifts.
    await page.context().route('**/worklet.js*', async (route) => {
      const response = await route.fetch();
      let body = await response.text();
      const replace = (from, to) => {
        assert.equal(body.split(from).length, 2, `unique startup anchor: ${from}`);
        body = body.replace(from, to);
      };
      replace('const fm1 = await instantiateFm1(m.wasm);',
        'const probeBegin = Date.now(); const fm1 = await instantiateFm1(m.wasm); const probeInstantiated = Date.now();');
      replace("this.port.postMessage({ type: 'ready', rate: sampleRate, catalog, imports: fm1.imports });",
        "this.port.postMessage({ type: 'startup-probe', instantiate_ms: probeInstantiated - probeBegin, setup_ms: Date.now() - probeInstantiated, audio_frame: currentFrame, rate: sampleRate }); this.port.postMessage({ type: 'ready', rate: sampleRate, catalog, imports: fm1.imports });");
      await route.fulfill({ response, body });
    });
    const capture = await startSchedulingCapture(browser, dir, { trace: which === 'chromium', phases: true });
    try {
      await page.goto(url);
      await page.evaluate(() => window.__lunarPlaybackTimeline.mark('power-on-request'));
      await page.click('#power-on');
      await page.waitForFunction(() => window.fm1?.screens > 0, null, { timeout: 20000 });
      await page.evaluate(() => window.__lunarPlaybackTimeline.mark('first-screen'));
      await page.waitForTimeout(2200);
    } finally { await capture.finish(); }
    const result = await page.evaluate(() => ({ events: window.__startupProbe.events,
      timeline: window.__lunarPlaybackTimeline.stop(), screens: window.fm1?.screens ?? 0,
      context_state: window.fm1?.ctx?.state ?? null }));
    results.push({ gated, ...result });
    writeFileSync(join(out, 'startup-probe.json'), JSON.stringify({ schema: 1, acceptance: false,
      perturbation: 'Two ordered diagnostic starts; route timing instrumentation, page observers, graph-lock getters and CDP tracing perturb scheduling.', results }, null, 2) + '\n');
    assert.ok(result.events.some((e) => e.type === 'init-measured'));
    assert.ok(result.events.some((e) => e.type === 'ready'));
    assert.ok(result.screens > 0);
    await page.close();
  }
} finally { await browser.close(); server.close(); }
