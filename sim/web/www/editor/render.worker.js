import {instantiateFm1} from '../fm1-wasm.mjs';
import {parseSet, writeSet, arrangementEntries, validateSet} from './sequence-model.js';
import {createWav} from './wav.js';

const MAX_SECONDS = 20 * 60, MAX_BYTES = 256 * 1024 * 1024;
const abortError = () => Object.assign(new Error('Audio export cancelled.'), {name: 'AbortError'});
const pause = () => new Promise(resolve => setTimeout(resolve, 0));
const safeName = name => String(name || 'Lunar').replace(/[\x00-\x1f<>:"/\\|?*]/g, '-').slice(0, 100);

// Public core also allows exact-Wasm tests without a browser or AudioContext.
// Each pass gets fresh C state (including the sequencer RNG and effect buffers).
export async function renderOffline(options, source, hooks = {}) {
  const {mode = 'mix', tail = 3, sampleRate = 44118, bits = 24, masterVolume = 1} = options;
  if (!['mix', 'sound-stems', 'track-stems', 'multichannel'].includes(mode)) throw new RangeError('Unknown audio export mode.');
  if (![44100, 44118].includes(sampleRate) || ![16, 24].includes(bits) || !Number.isFinite(tail) || tail < 0 || tail > 60 || !Number.isFinite(masterVolume) || masterVolume < 0 || masterVolume > 1) throw new RangeError('Invalid audio export settings.');
  const original = typeof options.project === 'string' ? JSON.parse(options.project) : structuredClone(options.project);
  if (original?.kind !== 'project' || !Array.isArray(original.sounds) || original.sounds.length !== 4) throw new Error('Export requires a complete Lunar project.');
  const model = parseSet(original.set), validation = validateSet(model);
  if (!validation.valid) throw new Error(`Invalid sequencer set: ${validation.errors.join(" ")}`);
  if (!model.song.length) throw new Error('Add scenes to the song arrangement before exporting.');
  for (const scene of model.song) if (!model.tracks.some(t => t.clips[scene])) throw new Error('Song contains an empty scene that cannot finish a finite pass.');
  const bars = arrangementEntries(model).reduce((sum, e) => sum + e.bars, 0);
  const seconds = bars * 4 * 60 * 100 / model.bpmX100;
  if (!Number.isFinite(seconds) || seconds + tail > MAX_SECONDS) throw new RangeError('Export is limited to twenty minutes including the tail.');
  // Native advance services tick zero after the first PPQN interval; Stop
  // is checked on the tick after the last bar. Polling happens in 64-frame
  // render blocks, so include that interval and round to the block boundary.
  const stopFrames = Math.ceil((bars * 4 * 96 + 1) * sampleRate * 6000 / (model.bpmX100 * 96));
  const tailFrames = Math.round(tail * sampleRate), songBound = Math.ceil(stopFrames / 64) * 64;
  const capacity = songBound + tailFrames;
  const warnings = [];
  if (model.tracks.some(t => t.route.kind === 0 && t.clips.some(c => c?.notes.length))) warnings.push('External MIDI tracks do not produce audio in an offline export.');
  if (mode !== 'mix') warnings.push('Stems bypass master effects but retain master volume, host amp modulation and the safety limiter. Shared modulation and nonlinear processing mean stems may not sum exactly to the master mix.');
  if (mode === 'track-stems') warnings.push('Track isolation mutes other sequencer tracks. Shared sound voices and note-triggered modulation can differ from the full mix.');
  const passes = mode === 'mix' ? [{name: 'master'}] : mode === 'track-stems'
    ? model.tracks.flatMap((t, i) => t.route.kind === 1 && t.clips.some(Boolean) ? [{name: `track-${i + 1}`, track: i, sound: t.route.index}] : [])
    : Array.from({length: 4}, (_, sound) => ({name: `sound-${sound + 1}`, sound}));
  if (!passes.length) throw new Error('No internal sound tracks to export.');
  // Without an onFile sink all separate WAVs remain resident in the caller.
  const retainedBytes = (44 + capacity * 2 * (bits / 8)) * passes.length;
  if (mode !== 'multichannel' && !hooks.onFile && retainedBytes > MAX_BYTES) throw new RangeError('Export exceeds the memory limit. Download each stem as it finishes.');
  const module = source instanceof WebAssembly.Module ? source : await WebAssembly.compile(source);
  if (hooks.isCancelled?.()) throw abortError();
  const files = [], multi = mode === 'multichannel' ? createWav({frames: capacity, channels: 8, sampleRate, bits, maxBytes: MAX_BYTES}) : null;
  let commonSamples;
  for (let passIndex = 0; passIndex < passes.length; ++passIndex) {
    const pass = passes[passIndex], project = structuredClone(original), set = structuredClone(model);
    set.songEnd = 2; // one pass, independent of the saved loop/park preference
    if (pass.track !== undefined) set.tracks.forEach((t, i) => { if (i !== pass.track) t.muted = 1; });
    project.set = writeSet(set);
    if (mode !== 'mix') project.master = [null, null];
    const fm1 = await instantiateFm1(module), ex = fm1.exports;
    ex.fm1w_init(sampleRate); ex.fm1w_default_chain();
    const put = text => {
      const bytes = new TextEncoder().encode(text);
      if (bytes.length > ex.fm1w_text_cap()) throw new RangeError('Project exceeds the Wasm state buffer.');
      new Uint8Array(ex.memory.buffer, ex.fm1w_text_buf(), bytes.length).set(bytes); return bytes.length;
    };
    if (ex.fm1w_state_load(1, 0, 0, 4, put(JSON.stringify(project))) !== 1) throw new Error(`Project could not be loaded: ${fm1.string(ex.fm1w_state_report())}`);
    if (pass.sound !== undefined) {
      if (typeof ex.fm1w_export_sound_mask !== 'function') throw new Error('This Wasm build needs the offline sound isolation gate for safe stem export.');
      // A contribution gate survives mix:Level automation. Do not mute tracks
      // or change sound levels: their engines and SEQ modulation keep running.
      ex.fm1w_export_sound_mask(1 << pass.sound);
    }
    ex.fm1w_master(masterVolume, 0);
    const commands = 'sgend 2;sgjump 0;play';
    if (ex.fm1w_seq_text(put(commands)) !== commands.length) throw new Error('Could not start offline song transport.');
    const writer = multi || createWav({frames: capacity, channels: 2, sampleRate, bits, maxBytes: MAX_BYTES});
    let frames = 0, stopped = false, tailLeft = tailFrames;
    while (!stopped || tailLeft > 0) {
      if (hooks.isCancelled?.()) throw abortError();
      const count = stopped ? Math.min(64, tailLeft) : 64;
      if (frames + count > capacity || (!stopped && frames > songBound)) throw new Error('Song did not stop within its arrangement duration.');
      const ptr = ex.fm1w_render(count);
      writer.writeBlock(frames, new Float32Array(ex.memory.buffer, ptr, count * 2), 2, multi ? passIndex * 2 : 0);
      frames += count;
      if (stopped) tailLeft -= count;
      else if (!new Uint32Array(ex.memory.buffer, ex.fm1w_seq_info(), 8)[0]) stopped = true;
      if (frames % 4096 === 0) {
        hooks.onProgress?.({pass: passIndex + 1, passes: passes.length, name: pass.name, frames, sampleRate, fraction: Math.min(1, (passIndex + frames / capacity) / passes.length)});
        await pause();
      }
    }
    if (ex.fm1w_seq_dropped() || fm1.calls.length) throw new Error('Offline render dropped sequencer events or invoked an unsupported Wasm import.');
    if (commonSamples !== undefined && commonSamples !== frames) throw new Error('Stem transport lengths differ.');
    commonSamples = frames;
    if (!multi) {
      const file = {...writer.finish(frames), name: `${safeName(original.title || original.name)}-${pass.name}.wav`};
      if (hooks.onFile) await hooks.onFile(file); else files.push(file);
    }
  }
  if (multi) {
    const file = {...multi.finish(commonSamples), name: `${safeName(original.title || original.name)}-sound-stems-8ch.wav`};
    if (hooks.onFile) await hooks.onFile(file); else files.push(file);
  }
  hooks.onProgress?.({fraction: 1, passes: passes.length, pass: passes.length});
  return {files, warnings};
}

// File acknowledgements enforce backpressure: the next stem is not allocated
// until the caller has finished its download callback.
if (typeof WorkerGlobalScope !== 'undefined' && globalThis instanceof WorkerGlobalScope) {
  let acknowledge;
  globalThis.onmessage = async ({data}) => {
    if (data.type === 'ack') { acknowledge?.(); acknowledge = null; return; }
    if (data.type !== 'render') return;
    try {
      const response = await fetch(new URL('../fm1.wasm', import.meta.url));
      if (!response.ok) throw new Error(`Wasm fetch failed (${response.status}).`);
      const result = await renderOffline(data.options, await response.arrayBuffer(), {
        onProgress: progress => postMessage({type: 'progress', progress}),
        onFile: file => new Promise(resolve => { acknowledge = resolve; postMessage({type: 'file', ...file}, [file.buffer]); })
      });
      postMessage({type: 'done', warnings: result.warnings});
    } catch (error) { postMessage({type: 'error', name: error.name, message: error.message}); }
  };
}
