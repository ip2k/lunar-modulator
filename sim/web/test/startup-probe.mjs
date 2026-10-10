// Diagnostic only: compare running-context initialization with suspended
// initialization, using an isolated actual page/worklet/Wasm. No gate or retry.
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { serve } from './serve.mjs';
import { launch, which } from './launch.mjs';
import { startSchedulingCapture } from './scheduling-capture.mjs';
import { installPlaybackTimeline } from './playback-timeline.mjs';

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
// AudioWorklet fetches bypass Playwright routing in Chromium. Serve an
// isolated instrumented copy instead of changing the source or trusting routes.
const site = mkdtempSync(join(tmpdir(), 'lunar-startup-'));
cpSync(www, site, { recursive: true });
let body = readFileSync(join(site, 'worklet.js'), 'utf8');
const replace = (from, to) => {
  assert.equal(body.split(from).length, 2, `unique startup anchor: ${from}`);
  body = body.replace(from, to);
};
replace('const fm1 = await instantiateFm1(m.wasm);',
  'const probeBegin = Date.now(); const fm1 = await instantiateFm1(m.wasm); const probeInstantiated = Date.now();');
replace("this.port.postMessage({ type: 'ready', rate: sampleRate, catalog, imports: fm1.imports });",
  "this.port.postMessage({ type: 'startup-probe', instantiate_ms: probeInstantiated - probeBegin, setup_ms: Date.now() - probeInstantiated, audio_frame: currentFrame, rate: sampleRate }); this.port.postMessage({ type: 'ready', rate: sampleRate, catalog, imports: fm1.imports });");
writeFileSync(join(site, 'worklet.js'), body);
const { server, url } = await serve(site, 8767);
const { browser } = await launch();
const appSource = readFileSync(join(site, 'app.js'), 'utf8');
const replaceOnce = (source, from, to) => {
  assert.equal(source.split(from).length, 2, `unique suspension anchor: ${from}`);
  return source.replace(from, to);
};
const results = [];
try {
  for (const suspended of [false, true]) {
    let app = appSource;
    if (!suspended) {
      app = replaceOnce(app, 'wakeWhenReady(ctx, ctx === sim.ctx && sim.audioReady);',
        'wakeWhenReady(ctx, true);');
      assert.equal(app.split('    await ctx.suspend();').length, 3);
      app = app.replaceAll('    await ctx.suspend();', '    ctx.resume().catch(() => {});');
    }
    writeFileSync(join(site, 'app.js'), app);
    const dir = join(out, suspended ? 'suspended-init' : 'running-init');
    mkdirSync(dir, { recursive: true });
    const page = await browser.newPage();
    await page.addInitScript(installPlaybackTimeline);
    await page.addInitScript(() => {
      const events = [];
      window.__startupProbe = { events };
      const mark = (type, extra = {}) => events.push({ type, page_ms: performance.now(), ...extra });
      const Original = window.AudioWorkletNode;
      window.AudioWorkletNode = class extends Original {
        constructor(...args) {
          super(...args);
          this.probeContext = args[0]; this.probeReady = false;
          mark('node-created', { state: args[0].state, audio_seconds: args[0].currentTime });
          this.port.addEventListener('message', ({ data }) => {
            if (data.type === 'startup-probe') mark('init-measured', { instantiate_ms: data.instantiate_ms, setup_ms: data.setup_ms, audio_frame: data.audio_frame, rate: data.rate });
            if (data.type === 'ready') {
              mark('ready', { state: this.probeContext.state, audio_seconds: this.probeContext.currentTime });
              this.probeReady = true;
            }
          });
          this.port.start();
        }
        connect(...args) {
          mark('connect-request', { destination: args[0].constructor.name, ready: this.probeReady });
          const result = super.connect(...args);
          mark('connected', { destination: args[0].constructor.name, ready: this.probeReady });
          return result;
        }
      };
    });
    const capture = await startSchedulingCapture(browser, dir, { trace: which === 'chromium', phases: true });
    let failure = null;
    try {
      await page.goto(url);
      await page.evaluate(() => window.__lunarPlaybackTimeline.mark('power-on-request'));
      await page.click('#power-on');
      await page.waitForFunction(() => window.fm1?.screens > 0, null, { timeout: 20000 });
      await page.evaluate(() => window.__lunarPlaybackTimeline.mark('first-screen'));
      await page.waitForTimeout(2200);
    } catch (err) { failure = String(err); } finally { await capture.finish(); }
    const result = await page.evaluate(() => ({ events: window.__startupProbe.events,
      timeline: window.__lunarPlaybackTimeline.stop(), screens: window.fm1?.screens ?? 0,
      context_state: window.fm1?.ctx?.state ?? null }));
    results.push({ suspended, failure, ...result });
    writeFileSync(join(out, 'startup-probe.json'), JSON.stringify({ schema: 2, acceptance: false,
      perturbation: 'Two ordered running/suspended diagnostic starts; isolated timing-instrumented worklet copy, page observers, graph-lock getters and CDP tracing perturb scheduling.', results }, null, 2) + '\n');
    if (!failure) {
      assert.ok(result.events.some((e) => e.type === 'init-measured'));
      assert.ok(result.events.some((e) => e.type === 'ready'));
      assert.ok(result.screens > 0);
    }
    await page.close();
  }
} finally { await browser.close(); server.close(); rmSync(site, { recursive: true, force: true }); }
if (results.some((r) => r.failure)) process.exitCode = 1;
