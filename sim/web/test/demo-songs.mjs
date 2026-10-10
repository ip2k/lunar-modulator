// Whole-arrangement acceptance against the browser's actual Wasm module.
// Run on the build host: node demo-songs.mjs --manifest demo-songs.json
//   --wasm ../www/fm1.wasm --out build/demo-songs.json
// MIT licence.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { basename, dirname, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { parseArgs } from 'node:util';
import { instantiateFm1, BLOCK } from '../www/fm1-wasm.mjs';

const { values } = parseArgs({ options: {
  manifest: { type: 'string' }, wasm: { type: 'string' }, out: { type: 'string' },
  native: { type: 'string' }, work: { type: 'string' },
} });
assert(values.manifest && values.wasm && values.out, '--manifest, --wasm and --out required');
assert(!values.native || values.work, '--native requires --work for audio/screen receipts');
if (values.work) mkdirSync(values.work, { recursive: true });
const manifest = resolve(values.manifest);
const songs = JSON.parse(readFileSync(manifest, 'utf8'));
assert.equal(songs.length, 4, 'four complete demo songs');
assert.equal(new Set(songs.map(song => song.title)).size, 4, 'distinct demo songs');
const module = await WebAssembly.compile(readFileSync(values.wasm));
const rate = 44118;
const results = [];
const stripInfo = (doc) => {
  const { made, name, title, about, author, licence, view, ...state } = doc;
  return state;
};

for (const song of songs) {
  assert(song.bpm > 0 && song.bars > 0 && song.scenes >= 4, 'valid song contract');
  const path = resolve(dirname(manifest), song.file);
  const bytes = readFileSync(path);
  const doc = JSON.parse(bytes);
  assert.equal(doc.kind, 'project');
  assert.equal(doc.title, song.title);
  const chain = doc.set.find(line => line.startsWith('sg '));
  assert(chain, 'song has a scene chain');
  assert(new Set(chain.split(/\s+/).slice(1)).size >= song.scenes,
    'chain actually uses the declared number of scenes');
  assert(doc.set.includes('se 2'), 'stop-at-end is persisted in the project');
  const w = await instantiateFm1(module);
  const ex = w.exports;
  ex.fm1w_init(rate);
  const load = (data) => {
    assert(data.length <= ex.fm1w_text_cap(), 'project fits transfer buffer');
    new Uint8Array(w.memory.buffer, ex.fm1w_text_buf(), data.length).set(data);
    assert.equal(ex.fm1w_state_load(0, -1, 0, 0, data.length), 1,
      w.string(ex.fm1w_state_report()));
  };
  const save = () => {
    const n = ex.fm1w_state_save(1, 0, 0);
    assert(n > 0, w.string(ex.fm1w_state_report()));
    return Buffer.from(new Uint8Array(w.memory.buffer, ex.fm1w_text_buf(), n));
  };
  load(bytes);
  const loadReport = JSON.parse(w.string(ex.fm1w_state_report()));
  assert(loadReport.percent <= 100, 'project fits simulated RAM budget');
  const first = save();
  load(first);
  assert.deepEqual(stripInfo(JSON.parse(save())), stripInfo(JSON.parse(first)),
    'save/load/save preserves executable project state');
  ex.fm1w_master(1, 0);
  const start = Buffer.from('play');
  new Uint8Array(w.memory.buffer, ex.fm1w_text_buf(), start.length).set(start);
  assert.equal(ex.fm1w_seq_text(start.length), start.length);
  const duration = song.bars * 240 / song.bpm;
  const limit = Math.ceil((duration + 2) * rate / BLOCK) * BLOCK;
  let peak = 0, squares = 0, stoppedFrame = null, playingSeen = false;
  const energy = [];
  let windowSquares = 0, windowSamples = 0;
  for (let frame = 0; frame < limit; frame += BLOCK) {
    const samples = new Float32Array(w.memory.buffer, ex.fm1w_render(BLOCK), BLOCK * 2);
    for (const sample of samples) {
      assert(Number.isFinite(sample), `${song.title}: non-finite audio at ${frame}`);
      peak = Math.max(peak, Math.abs(sample));
      squares += sample * sample;
      windowSquares += sample * sample;
      windowSamples++;
    }
    if (windowSamples >= rate * 2) {
      energy.push(Math.sqrt(windowSquares / windowSamples));
      windowSquares = windowSamples = 0;
    }
    const info = new Uint32Array(w.memory.buffer, ex.fm1w_seq_info(), 8);
    assert.equal(info[1], Math.round(song.bpm * 100), 'tempo matches production sheet');
    if (info[0]) playingSeen = true;
    else if (playingSeen && stoppedFrame === null) stoppedFrame = frame + BLOCK;
  }
  assert(playingSeen, 'transport actually started');
  assert(stoppedFrame !== null, 'song stops at end of arrangement');
  assert(Math.abs(stoppedFrame / rate - duration) < 0.1,
    `${song.title}: expected ${duration}s, stopped at ${stoppedFrame / rate}s`);
  assert.equal(ex.fm1w_seq_dropped(), 0, 'no lost sequencer events');
  assert.equal(w.imports.length, 0, 'standalone module');
  assert.equal(w.calls.length, 0, 'no stubbed host calls');
  const rms = Math.sqrt(squares / (limit * 2));
  assert(rms > 0.001 && peak > 0.01, 'arrangement produces audible audio');
  let native = null;
  if (values.native) {
    const stem = resolve(values.work, basename(song.file, '.lunar'));
    writeFileSync(`${stem}.verbs`, `#! rate=${rate} block=${BLOCK} tracks=8\n@0 play\n`);
    native = JSON.parse(execFileSync(values.native, [
      '--load', path, '--cmd', `${stem}.verbs`, '--seconds', String(duration + 2),
      '--master', '1', '--out', `${stem}.wav`, '--screen', `${stem}.ppm`,
    ], { encoding: 'utf8', timeout: 600000 }));
    assert.equal(native.load.ok, 1, 'native accepts project');
    assert.equal(native.seq_view.playing, 0, 'native song stops');
    assert.equal(native.seq_dropped, 0, 'native drops no sequencer events');
    assert(native.seq_events > 0 && native.rms > 0.001 && Number.isFinite(native.peak),
      'native actually plays finite audible audio');
    writeFileSync(`${stem}.json`, JSON.stringify(native, null, 2) + '\n');
  }
  results.push({ title: song.title, file: song.file, bpm: song.bpm, bars: song.bars,
    duration, stoppedAt: stoppedFrame / rate, peak, rms, secondRms: energy,
    dropped: 0, ramPercent: loadReport.percent, roundTrip: true, native });
  console.log(`${song.title}: ${duration.toFixed(2)}s, peak ${peak.toFixed(4)}, RMS ${rms.toFixed(4)}`);
}
writeFileSync(values.out, JSON.stringify({ rate, songs: results, pass: true }, null, 2) + '\n');
