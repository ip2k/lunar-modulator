// node sim/web/test/audio-export.mjs [--wasm /absolute/path/fm1.wasm]
// 2026-10-11 receipt: Hera node:22-bookworm-slim, Docker CPU=2/memory=2GiB,
// docker-batch.slice; Wasm SHA256 a8e3893389e16c630eb95a2a257034b905e3c15168881d49a83abc3d33c7126c.
// All actual-Wasm assertions passed, including the native isolation gate.
// Regressions cover automation leakage, MIDI-follow mode and unequal clip lengths.
// Parent owns the shared branch checkpoint/push and browser download integration.
// Isolated receipt: /home/claude/mvave-fm1/audio-export-20261011/test-gate.log.
// Browser download integration and owner listening remain separate acceptance gates.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createWav} from '../www/editor/wav.js';
import {renderOffline} from '../www/editor/render.worker.js';
import {exportAudio} from '../www/editor/audio-export.js';
import {emptySet, emptyClip, writeSet} from '../www/editor/sequence-model.js';

for (const bits of [16, 24]) {
  const wav = createWav({frames: 2, channels: 2, sampleRate: 44118, bits});
  wav.writeBlock(0, [1, -1, 2, -0.5]);
  const result = wav.finish(), v = new DataView(result.buffer), b = bits / 8;
  assert.equal(v.getUint32(4, true), result.buffer.byteLength - 8);
  assert.equal(v.getUint32(40, true), 4 * b); assert.equal(v.getUint16(20, true), 1);
  assert.equal(v.getUint32(24, true), 44118); assert.equal(result.clipped, 1); assert.equal(result.peak, 2);
  if (bits === 16) { assert.equal(v.getInt16(44, true), 32767); assert.equal(v.getInt16(46, true), -32768); assert.equal(v.getInt16(50, true), -16384); }
  else { assert.deepEqual([...new Uint8Array(result.buffer, 44, 6)], [255,255,127,0,0,128]); }
}
const multi = createWav({frames: 2, channels: 8, sampleRate: 44100, bits: 16});
multi.writeBlock(0, [0.25, -0.25, 0.5, -0.5], 2, 6);
const mv = new DataView(multi.finish(1).buffer);
assert.equal(mv.byteLength, 84); assert.equal(mv.getUint16(20, true), 0xfffe);
assert.equal(mv.getUint32(16, true), 40); assert.equal(mv.getUint16(36, true), 22); assert.equal(mv.getUint32(40, true), 0);
assert.deepEqual([...new Uint8Array(mv.buffer, 44, 16)], [1,0,0,0,0,0,16,0,128,0,0,170,0,56,155,113]);
assert.equal(mv.getInt16(68 + 12, true), 8192); assert.equal(mv.getInt16(68, true), 0);
const mono = createWav({frames:1,channels:1,sampleRate:44100,bits:24}).finish();
assert.equal(mono.buffer.byteLength,48); assert.equal(new DataView(mono.buffer).getUint32(40,true),3);
assert.throws(() => createWav({frames: 1e9, channels: 8, sampleRate: 44100}), /limit/);
assert.throws(() => multi.writeBlock(0, [NaN], 1), /non-finite/);
assert.throws(() => multi.writeBlock(2, [0,0], 2), /outside/);

const oldWorker = globalThis.Worker; let terminated = 0;
class FakeWorker {
  constructor() { this.mode = 'test'; }
  terminate() { ++terminated; }
  postMessage(message) {
    if (message.type === 'ack') queueMicrotask(() => this.onmessage({data:{type:'done', warnings:[]}}));
    else if (message.options.mode === 'fake') queueMicrotask(() => this.onmessage({data:{type:'file', name:'test.wav', channels:2, samples:1, peak:0, buffer:new ArrayBuffer(44)}}));
  }
}
globalThis.Worker = FakeWorker;
const controller = new AbortController(), cancelled = exportAudio({signal:controller.signal}); controller.abort();
await assert.rejects(cancelled, {name:'AbortError'}); assert.equal(terminated, 1);
let delivered = false;
const streamed = await exportAudio({mode:'fake', onFile: async file => {assert(file.blob instanceof Blob); delivered = true;}});
assert(delivered); assert.equal(streamed.files[0].blob, undefined); assert.equal(terminated, 2);
await assert.rejects(exportAudio({mode:'fake', onFile:()=>{throw new Error('sink failed');}}), /sink failed/);
assert.equal(terminated, 3); globalThis.Worker = oldWorker;
console.log('WAV encoding, bounds, stream backpressure and cancellation: PASS');

const wasmArg = process.argv.indexOf('--wasm');
if (wasmArg >= 0) {
  const wasm = await readFile(process.argv[wasmArg + 1]);
  const project = JSON.parse(await readFile(new URL('../www/examples/first-orbit.lunar', import.meta.url), 'utf8'));
  project.title = 'Offline test'; project.master = [null,null]; project.mod = {seed:1,rack:[],cables:[]};
  project.sounds = Array.from({length:4},()=>({engine:'test-sine',params:{Volume:0.2},level:50,inserts:[null,null],midi_fx:[]}));
  const set = emptySet(); set.bpmX100 = 30000; set.song = [0]; set.songEnd = 0;
  for (let t = 0; t < 2; ++t) { set.tracks[t].route = {kind:1,index:t}; const clip = emptyClip(); clip.notes = [{tick:0,gate:192,pitch:60+t*7,vel:100,step:0}]; set.tracks[t].clips[0]=clip; }
  project.set = writeSet(set);
  const request = {project, tail:0.05, bits:16};
  const a = await renderOffline(request, wasm), b = await renderOffline(request, wasm);
  assert.deepEqual(a.files[0].buffer, b.files[0].buffer); assert(a.files[0].peak > 0.001);
  assert(a.files[0].samples > 0.8*44118 && a.files[0].samples < 0.86*44118);
  const quiet = await renderOffline({...request,masterVolume:0.5},wasm);
  assert(Math.abs(quiet.files[0].peak/a.files[0].peak-0.25)<0.001);
  const stems = await renderOffline({...request,mode:'sound-stems'},wasm);
  assert.equal(stems.files.length,4); assert(stems.files[0].peak > 0); assert(stems.files[1].peak > 0);
  assert.equal(stems.files[2].peak,0); assert.equal(stems.files[3].peak,0);
  const automated = structuredClone(project), automationSet = structuredClone(set);
  automationSet.tracks[1].lanes[0]={base:50,label:'mix:Level'};
  automationSet.tracks[1].clips[0].locks=[{lane:0,step:0,value:0},{lane:0,step:4,value:127}];
  automated.set=writeSet(automationSet);
  const lockedStems=await renderOffline({...request,project:automated,mode:'sound-stems'},wasm);
  assert.deepEqual(lockedStems.files[0].buffer,stems.files[0].buffer,'Unrelated mix automation leaked into the selected sound stem.');
  assert.notDeepEqual(lockedStems.files[1].buffer,stems.files[1].buffer,'mix:Level lock did not affect its selected stem.');
  let streamedCount=0;
  const streamResult=await renderOffline({...request,mode:'sound-stems'},wasm,{onFile:async file=>{assert(file.buffer instanceof ArrayBuffer); ++streamedCount;}});
  assert.equal(streamedCount,4); assert.equal(streamResult.files.length,0);
  const channels = await renderOffline({...request,mode:'multichannel'},wasm);
  const packed = new DataView(channels.files[0].buffer);
  for (let s=0;s<4;++s) {
    const stereo = new DataView(stems.files[s].buffer);
    assert.equal(stems.files[s].samples, channels.files[0].samples);
    for(let f=0;f<stems.files[s].samples;++f) for(let c=0;c<2;++c) assert.equal(packed.getInt16(68+(f*8+s*2+c)*2,true),stereo.getInt16(44+(f*2+c)*2,true));
  }
  const tracks = await renderOffline({...request,mode:'track-stems'},wasm); assert.equal(tracks.files.length,2);
  assert.deepEqual(tracks.files[0].buffer,stems.files[0].buffer); assert.deepEqual(tracks.files[1].buffer,stems.files[1].buffer);
  const linkedProject=structuredClone(project), linkedSet=structuredClone(set); linkedSet.link=1;
  linkedProject.set=writeSet(linkedSet);
  assert.deepEqual((await renderOffline({...request,project:linkedProject},wasm)).files[0].buffer,a.files[0].buffer,'Saved MIDI-follow preference stalled the internal offline clock.');
  const unevenProject=structuredClone(project), unevenSet=structuredClone(set);
  unevenSet.tracks[1].clips[0]=emptyClip(32); unevenSet.tracks[1].clips[0].notes=[{tick:0,gate:192,pitch:67,vel:100,step:0}];
  unevenProject.set=writeSet(unevenSet);
  const unevenMix=await renderOffline({...request,project:unevenProject},wasm);
  const unevenTracks=await renderOffline({...request,project:unevenProject,mode:'track-stems'},wasm);
  assert(unevenMix.files[0].samples>a.files[0].samples);
  assert(unevenTracks.files.every(f=>f.samples===unevenMix.files[0].samples),'Track isolation changed the arrangement duration.');
  const midiOnly = structuredClone(project); const midiSet = structuredClone(set);
  midiSet.tracks.forEach((t,i)=>{t.route={kind:0,index:i+1};}); midiOnly.set=writeSet(midiSet);
  const external = await renderOffline({...request,project:midiOnly},wasm);
  assert.equal(external.files[0].peak,0); assert(external.warnings.some(w=>w.includes('External MIDI')));
  let cancel = false;
  await assert.rejects(renderOffline(request,wasm,{isCancelled:()=>cancel,onProgress:()=>{cancel=true;}}),{name:'AbortError'});
  const long = structuredClone(project); const longSet = emptySet(); longSet.bpmX100=2000; longSet.song=Array(64).fill(0); longSet.tracks[0].clips[0]=emptyClip(256); long.set=writeSet(longSet);
  await assert.rejects(renderOffline({...request,project:long},wasm),/twenty minutes/);
  const complete = JSON.parse(await readFile(new URL('../www/examples/first-orbit.lunar', import.meta.url), 'utf8'));
  const shortSet = emptySet(); shortSet.bpmX100=30000; shortSet.song=[0];
  shortSet.tracks[0].route={kind:1,index:3}; const held=emptyClip(); held.notes=[{tick:0,gate:192,pitch:60,vel:100,step:0}]; shortSet.tracks[0].clips[0]=held; complete.set=writeSet(shortSet);
  const withBus = await renderOffline({project:complete,tail:0.1,bits:16},wasm);
  const withoutBus = await renderOffline({project:complete,tail:0.1,bits:16,mode:'sound-stems'},wasm);
  assert(withBus.files[0].peak>0); assert(withoutBus.files[3].peak>0); assert.notDeepEqual(withBus.files[0].buffer,withoutBus.files[3].buffer);
  assert.deepEqual(complete.master,JSON.parse(await readFile(new URL('../www/examples/first-orbit.lunar', import.meta.url), 'utf8')).master);
  const arpProject = structuredClone(complete); shortSet.tracks[0].route.index=2; arpProject.set=writeSet(shortSet);
  const withArp = await renderOffline({project:arpProject,tail:0,bits:16},wasm);
  arpProject.sounds[2].midi_fx=[];
  const noArp = await renderOffline({project:arpProject,tail:0,bits:16},wasm);
  assert(withArp.files[0].peak>0); assert.notDeepEqual(withArp.files[0].buffer,noArp.files[0].buffer);
  console.log('Actual FM6, inserts, MIDI arp, modulation and separate master effect processing: PASS');
  console.log(`Actual Wasm deterministic finite song, silent unused stems, track isolation, 8-channel interleave, cancellation: PASS (${a.files[0].samples} frames)`);
}
