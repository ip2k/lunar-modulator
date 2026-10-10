// External PulseAudio monitor capture: sustained simulator tone + edit storm,
// then First orbit A/B playback for listening. Run in an isolated Linux container.
// PULSE_SOURCE must name a monitor; PLAYWRIGHT_DIR and BROWSER use launch.mjs.
// MIT licence.
import { mkdirSync, openSync, closeSync, writeFileSync, readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
import { toneAnalysis, pcmWave } from './audio-analysis.mjs';
const [www, out, secondsArg = '30'] = process.argv.slice(2);
const seconds = Number(secondsArg);
if (!process.env.PULSE_SOURCE?.endsWith('.monitor') || !(seconds >= 5 && seconds <= 300))
  throw new Error('Set PULSE_SOURCE to an isolated sink monitor; seconds must be 5..300');
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8775);
const { browser, name } = await launch({ audible: true });
const report = { browser: name, seconds, source: process.env.PULSE_SOURCE, events: [], logs: [] };
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on('pageerror', e => report.logs.push(e.message));
const wait = ms => page.waitForTimeout(ms);
async function record(label, action) {
  const fd = openSync(join(out, `${label}.f32`), 'w');
  report[`${label}StartedAt`] = Date.now();
  const proc = spawn('parec', ['--raw', '--format=float32le', '--rate=48000', '--channels=2',
    `--device=${process.env.PULSE_SOURCE}`, '--latency-msec=20'], { stdio: ['ignore', fd, 'pipe'] });
  let error = ''; proc.stderr.on('data', b => error += b);
  const done = new Promise((resolve, reject) => { proc.on('error', reject); proc.on('exit', code => resolve(code)); });
  try { await wait(500); await action(); await wait(500); }
  finally { proc.kill('SIGINT'); const code = await done; closeSync(fd); if (code && code !== 130) throw new Error(`parec: ${code} ${error}`); }
}
try {
  await page.goto(url);
  await page.click('#power-on');
  await page.locator('[data-layout="editor"]').first().evaluate(b => b.click());
  await page.waitForFunction(() => window.fm1?.editor?.state?.mirror?.blocks.size > 0);
  const loaded = await page.evaluate(async () => {
    const text = JSON.stringify({ lunar: '1.0', kind: 'project', title: 'Loopback tone',
      session: { current: 0 }, sounds: [{ engine: 'test-sine', params: { Volume: 0.7 } }],
      mix: { levels: [80, 0, 0, 0] } });
    return window.fm1.files.load(new TextEncoder().encode(text),
      { d: { enc: 2, kind: 'project', title: 'Loopback tone' }, before: false, quiet: true });
  });
  if (!loaded.ok) throw new Error(`tone project refused: ${JSON.stringify(loaded)}`);
  await wait(1000);
  await record('tone-storm', async () => {
    report.storm = await page.evaluate(async seconds => {
      const sim = window.fm1;
      sim.node.port.postMessage({ type: 'note-on', note: 69, velocity: 100 });
      await new Promise(r => setTimeout(r, 1000));
      const ch = new MessageChannel(), port = ch.port1;
      let replies = 0, refused = 0, resyncs = 0;
      port.onmessage = e => { const m = e.data; if (m.type === 'edited') { replies++; refused += [...m.codes].filter(x => x !== 0).length; } if (m.type === 'resync') resyncs++; };
      sim.node.port.postMessage({ type: 'editor-port', port: ch.port2 }, [ch.port2]);
      const start = performance.now(); let batches = 0;
      while (performance.now() - start < seconds * 1000) {
        const bytes = new Uint8Array(8 * 24);
        for (let k = 0; k < 8; k++) {
          const at = k * 24, dv = new DataView(bytes.buffer, at, 24);
          bytes[at] = 6; bytes[at + 1] = 1; bytes[at + 2] = 0; bytes[at + 6] = 255;
          dv.setUint16(4, 1, true); dv.setFloat32(8, 0.5 + ((batches + k) % 20) / 100, true);
        }
        port.postMessage({ type: 'edit', tag: ++batches & 65535, bytes }, [bytes.buffer]);
        await new Promise(r => setTimeout(r, 3));
      }
      await new Promise(r => setTimeout(r, 1000));
      sim.node.port.postMessage({ type: 'note-off', note: 69 });
      return { batches, replies, refused, resyncs, rate: sim.ctx.sampleRate };
    }, seconds);
  });
  // Fresh page restores the editor's own port after the storm's dedicated port.
  await page.goto(`${url}?layout=panel`);
  await page.locator('[data-layout="panel"]').first().evaluate(b => b.click());
  await page.click('#power-on');
  await page.locator('[data-layout="editor"]').first().evaluate(b => b.click());
  await page.waitForFunction(() => window.fm1?.editor?.state?.mirror?.blocks.size > 0);
  const musical = await page.evaluate(async () => {
    const bytes = new Uint8Array(await (await fetch('examples/first-orbit.lunar')).arrayBuffer());
    return window.fm1.files.load(bytes, { d: { enc: 2, kind: 'project', title: 'First orbit' }, before: false, quiet: true });
  });
  if (!musical.ok) throw new Error('First orbit refused');
  await wait(1000);
  await page.evaluate(async () => { const ed = window.fm1.editor; ed.select('s2', { view: 'ab' }); await ed.project.keepA(); });
  await wait(700);
  await page.evaluate(() => {
    const sim = window.fm1;
    sim.node.port.postMessage({ type: 'button', button: 12, down: true });
    sim.node.port.postMessage({ type: 'button', button: 12, down: false });
  });
  await page.evaluate(() => {
    const sim = window.fm1; let seq = sim.seq;
    window.__stopped = [];
    Object.defineProperty(sim, 'seq', { configurable: true, get: () => seq,
      set: value => { seq = value; if (!value.playing) window.__stopped.push(Date.now()); } });
  });
  await record('ab-playback', async () => {
    await wait(2500);
    // Give B an audible timbre change through the actual parameter control.
    await page.evaluate(() => { const ed = window.fm1.editor; ed.select('s2', { view: 'sound' }); });
    await wait(400);
    const slider = page.locator('.ed-insp[data-block="s2"] .ed-row[data-uid="3"] [role="slider"]');
    await slider.focus(); await page.keyboard.press('End'); await wait(1500);
    for (const scope of ['project', 's2']) {
      await page.evaluate(() => window.fm1.editor.select('s2', { view: 'ab' }));
      await wait(400);
      await page.evaluate(scope => {
        const b = [...document.querySelectorAll('.ed-ab-scope button')].find(b => b.textContent === (scope === 'project' ? 'Project' : 'Sound 2'));
        if (!b) throw new Error(`missing A/B scope ${scope}`); b.click();
      }, scope);
      await wait(700);
      if (scope === 's2') {
        await page.evaluate(() => window.fm1.editor.project.keepA()); await wait(700);
        await page.evaluate(() => window.fm1.editor.select('s2', { view: 'sound' })); await wait(400);
        await slider.focus(); await page.keyboard.press('Home'); await wait(700);
        await page.evaluate(() => window.fm1.editor.select('s2', { view: 'ab' })); await wait(400);
      }
      for (let k = 0; k < 4; k++) {
        const before = await page.evaluate(() => ({ playing: window.fm1.seq.playing, side: window.fm1.editor.state.ab.playing }));
        const at = Date.now(); await page.evaluate(() => window.fm1.editor.project.switchAB());
        await wait(2500);
        const after = await page.evaluate(() => ({ playing: window.fm1.seq.playing, side: window.fm1.editor.state.ab.playing, busy: window.fm1.editor.state.ab.busy, message: document.querySelector('.ed-sr')?.textContent, scope: window.fm1.editor.state.ab.scope }));
        report.events.push({ scope, at, before, after });
      }
    }
  });
  const samples = label => { const b = readFileSync(join(out, `${label}.f32`)); if (b.length % 8) throw new Error('partial stereo frame'); return new Float32Array(b.buffer, b.byteOffset, b.length / 4); };
  report.audio = toneAnalysis(samples('tone-storm'), seconds);
  const music = samples('ab-playback');
  report.music = { seconds: music.length / 2 / 48000, peak: 0, nonfinite: 0 };
  for (const v of music) { if (!Number.isFinite(v)) report.music.nonfinite++; else report.music.peak = Math.max(report.music.peak, Math.abs(v)); }
  report.transportStopped = await page.evaluate(() => window.__stopped);
  writeFileSync(join(out, 'ab-playback.wav'), pcmWave(music));
  report.pass = report.audio.pass && report.music.seconds > 25 && report.music.peak > 0.005 && !report.music.nonfinite && !report.transportStopped.length && report.storm.refused === 0 && report.storm.resyncs === 0 && report.storm.replies === report.storm.batches &&
    report.events.every(e => e.before.playing && e.after.playing && e.after.side !== e.before.side) && !report.logs.length;
} finally {
  writeFileSync(join(out, 'audio-loopback.json'), JSON.stringify(report, null, 2));
  await browser.close(); server.close();
}
console.log(JSON.stringify(report));
if (!report.pass) process.exitCode = 1;
