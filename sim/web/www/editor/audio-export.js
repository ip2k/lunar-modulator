// Offline export never accesses the live AudioContext or changes playback state.
// exportAudio({project, mode:'mix'|'sound-stems'|'track-stems'|'multichannel',
//   tail:3, sampleRate:44118, bits:24, masterVolume:1, signal,
//   onProgress:({fraction,pass,passes,name,frames,sampleRate})=>{},
//   onFile:async ({blob,name,channels,samples,sampleRate,bits,peak,clipped})=>{}})
// resolves {files,warnings}. With onFile, files contains metadata only; the
// caller should download/release each Blob before resolving its callback.
// Otherwise files retains the Blobs. Limits: 20 minutes incl tail (0..60s),
// 256 MiB of PCM per file and aggregate retained output; 44100/44118 Hz,
// PCM16/24. An eight-channel file interleaves sound1 L/R through sound4 L/R,
// with a discrete channel mask (zero), rather than surround speaker positions.
// masterVolume is the panel knob position (0..1; native gain squares it).
// Sound stems are post-insert with master effects bypassed, preserving host
// amp modulation and limiter. Track stems mute other tracks; shared voices
// and note-triggered modulation can change. Neither mode promises an exact
// sum to a nonlinear master mix. The returned warnings disclose these limits.
// Native sound isolation must survive mix-level locks; older Wasm is refused.
export function exportAudio(options) {
  return new Promise((resolve, reject) => {
    const {signal, onProgress, onFile, ...request} = options;
    let worker, settled = false; const files = [];
    const abortError = () => new DOMException('Audio export cancelled.', 'AbortError');
    const cleanup = () => { signal?.removeEventListener('abort', abort); worker?.terminate(); };
    const fail = error => { if (!settled) { settled = true; cleanup(); reject(error); } };
    const abort = () => fail(abortError());
    if (signal?.aborted) { fail(abortError()); return; }
    try { worker = new Worker(new URL('./render.worker.js', import.meta.url), {type: 'module'}); }
    catch (error) { fail(error); return; }
    signal?.addEventListener('abort', abort, {once: true});
    worker.onerror = event => fail(new Error(event.message || 'Offline renderer failed.'));
    worker.onmessage = async ({data}) => {
      if (settled) return;
      try {
        if (data.type === 'progress') onProgress?.(data.progress);
        else if (data.type === 'file') {
          const {buffer, type, ...metadata} = data;
          const file = {...metadata, blob: new Blob([buffer], {type: 'audio/wav'})};
          if (onFile) { await onFile(file); files.push(metadata); }
          else files.push(file);
          if (!settled) worker.postMessage({type: 'ack'});
        } else if (data.type === 'error') fail(Object.assign(new Error(data.message), {name: data.name || 'Error'}));
        else if (data.type === 'done') { settled = true; cleanup(); resolve({files, warnings: data.warnings}); }
      } catch (error) { fail(error); }
    };
    try { worker.postMessage({type: 'render', options: request}); } catch (error) { fail(error); }
  });
}
