// editor.mjs -- the editor's port on the real AudioWorklet, in headless
// Chromium (stage ED1, notes/2026-10-06-web-editor.md §5, §12): a page
// powers on, plays the demo song, hands the worklet an editor port and
// storms it for SECONDS: eight packed records every few milliseconds, every
// telemetry row subscribed and each block handed back, and a snapshot at the
// end. It counts what came back (each op's verdicts, change batches, views,
// telemetry blocks) and the worklet's own stats: its quanta and the late ones
// (a quantum that took longer than it plays: an underrun of the audio
// thread), when its scope has a clock; and Chromium's own playback stats
// (underruns), when the browser has them.
//
//   PLAYWRIGHT_DIR=/pw node editor.mjs WWW OUT [SECONDS]
// MIT licence, like the rest of this repository.

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { startSchedulingCapture } from './scheduling-capture.mjs';
import { launch, which } from './launch.mjs';
import { playbackDelta } from './playback-stats.mjs';


const [www, out, secondsArg] = process.argv.slice(2);
const SECONDS = Number(secondsArg || 30);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8767);
const { browser, name: browserName } = await launch();
const report = { browser: browserName, seconds: SECONDS, logs: [] };
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
page.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error') report.logs.push(`error: ${m.text()}`); });
await page.goto(url);
await page.click('#power-on');
await page.waitForFunction(() => window.fm1 && window.fm1.screens > 0, null, { timeout: 20000 });
await page.waitForTimeout(300);

const capture = process.env.FM1_SCHEDULING_CAPTURE === '1'
  ? await startSchedulingCapture(browser, out, { trace: which === 'chromium' }) : null;
report.scheduling_capture = !!capture;
let r, stormError;
try {
r = await page.evaluate(async (seconds) => {
  const node = window.fm1.node;
  const ctx = window.fm1.ctx;
  const PLAY = 12;
  node.port.postMessage({ type: 'button', button: PLAY, down: true });
  node.port.postMessage({ type: 'button', button: PLAY, down: false });
  const ch = new MessageChannel();
  const port = ch.port1;
  const got = { edited: 0, codes_not_ok: 0, changes: 0, entries: 0, resyncs: 0, views: 0, telemetry: 0, stats: null, snapshot: null };
  port.onmessage = (e) => {
    const m = e.data;
    if (m.type === 'edited') {
      got.edited += 1;
      for (const c of m.codes) if (c !== 0) got.codes_not_ok += 1;
    } else if (m.type === 'changes') {
      got.changes += 1;
      got.entries += m.bytes.length / 32;
    } else if (m.type === 'resync') {
      got.resyncs += 1;
    } else if (m.type === 'view') {
      got.views += 1;
    } else if (m.type === 'telemetry') {
      got.telemetry += 1;
      port.postMessage({ type: 'telemetry-buffer', buffer: m.buffer }, [m.buffer]);
    } else if (m.type === 'stats') {
      got.stats = { quanta: m.quanta, timed: m.timed, late: m.late, maxMs: m.maxMs, editMs: m.editMs };
    } else if (m.type === 'snapshot') {
      got.snapshot = { ok: m.ok, bytes: m.bytes ? m.bytes.length : 0, binary: !!m.bytes && m.bytes[0] === 0x89 && m.bytes[1] === 0x4c };
    }
  };
  node.port.postMessage({ type: 'editor-port', port: ch.port2 }, [ch.port2]);
  port.postMessage({ type: 'subscribe', mask: new Uint32Array([0xffffffff, 0xffffffff, 0xffffffff, 0x7fffff]) });
  const telemetry = (await (await fetch(new URL('meta.json', location.href))).json()).telemetry;
  for (let k = 0; k < 2; ++k) {
    const buffer = new ArrayBuffer(telemetry.floats * 4);
    port.postMessage({ type: 'telemetry-buffer', buffer }, [buffer]);
  }
  // Packed records (fm1_edit.h): PARAM (6) of Sound 1's uids 2 and 3, and
  // LEVEL (7) of each sound.
  const rec = (b, at, type, sound, uid, value) => {
    const dv = new DataView(b.buffer, at, 24);
    b[at] = type;
    b[at + 2] = sound;
    if (type === 6) {
      b[at + 1] = 1;                  // FM1_ROLE_SOUND
      dv.setUint16(4, uid, true);
      b[at + 6] = 0xff;
      dv.setFloat32(8, value, true);
    } else {
      dv.setFloat32(4, value, true);
    }
  };
  const playback = () => ctx.playbackStats ? {
    events: ctx.playbackStats.underrunEvents,
    seconds: ctx.playbackStats.underrunDuration,
  } : null;
  const under0 = playback();
  let sent = 0;
  let ops = 0;
  const t0 = performance.now();
  while (performance.now() - t0 < seconds * 1000) {
    const bytes = new Uint8Array(8 * 24);
    for (let k = 0; k < 8; ++k) {
      if (k % 2) rec(bytes, 24 * k, 7, (sent + k) % 4, 0, 40 + ((sent + k) % 50));
      else rec(bytes, 24 * k, 6, 0, 2 + ((k / 2) % 2), ((sent + k) % 17) / 17);
    }
    port.postMessage({ type: 'edit', tag: ++ops & 0xffff, bytes }, [bytes.buffer]);
    sent += 8;
    await new Promise((res) => setTimeout(res, 3));
  }
  port.postMessage({ type: 'snapshot', id: 1 });
  await new Promise((res) => setTimeout(res, 1500));
  got.ops = ops;
  got.records = sent;
  got.rate = ctx.sampleRate;
  got.playback = { before: under0, after: playback() };
  return got;
}, SECONDS);
} catch (e) {
  report.pass = false;
  report.logs.push(`storm failed: ${e.message}`);
  writeFileSync(join(out, 'editor.json'), JSON.stringify(report, null, 2) + '\n');
  stormError = e;
} finally {
  if (capture) await capture.finish();
}

if (stormError) {
  await browser.close();
  server.close();
  throw stormError;
}

r.playback = playbackDelta(r.playback.before, r.playback.after);
Object.assign(report, r);
const quantaWanted = Math.floor((SECONDS * r.rate) / 128 * 0.9);
report.pass = r.edited === r.ops && r.codes_not_ok === 0 && r.changes > 0 && r.entries > 0 && r.telemetry > 0 &&
  r.stats !== null && r.stats.quanta >= quantaWanted && (!r.stats.timed || r.stats.late === 0) &&
  (!r.playback || r.playback.underrun_events === 0) && !!r.snapshot && r.snapshot.ok && r.snapshot.binary &&
  report.logs.length === 0;
writeFileSync(join(out, 'editor.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
await browser.close();
server.close();
process.exit(report.pass ? 0 : 1);
