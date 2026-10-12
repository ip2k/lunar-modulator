// Offline export never accesses the live AudioContext or changes playback state.
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
