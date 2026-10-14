// SPDX-License-Identifier: MIT
// Same-origin client for the private diagnostic-build API. The service returns
// a verified summary only; it does not expose firmware bytes or installation.

const BUILD_PATH = '/api/v1/builds';
const OPAQUE_ID = /^[A-Za-z0-9_-]{32}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const MAX_RESPONSE_BYTES = 65536;
const MAX_ARTIFACT_BYTES = 1048576;

function fail(message) { throw new Error(message); }

function validateRequest(request) {
  const groups = ['engines', 'effects', 'midi', 'modulation'];
  const keys = ['version', ...groups, 'project_ids', 'startup_index'];
  if (!request || typeof request !== 'object'
      || (Object.getPrototypeOf(request) !== Object.prototype && Object.getPrototypeOf(request) !== null)
      || request.version !== 1 || !Array.isArray(request.project_ids)
      || request.project_ids.length < 1 || request.project_ids.length > 8
      || Object.keys(request).length !== keys.length
      || keys.some((key) => !Object.hasOwn(request, key))
      || !Number.isInteger(request.startup_index)
      || request.startup_index < 0 || request.startup_index >= request.project_ids.length) {
    fail('The selected build request is invalid.');
  }
  for (const key of [...groups, 'project_ids']) {
    const maxLength = key === 'project_ids' ? 8 : 128;
    if (!Array.isArray(request[key]) || request[key].length > maxLength
        || (key === 'engines' && request[key].length === 0)
        || request[key].some((value) => typeof value !== 'string' || value.length === 0)
        || new Set(request[key]).size !== request[key].length) {
      fail('The selected build request is invalid.');
    }
  }
  if (new TextEncoder().encode(JSON.stringify(request)).byteLength > MAX_RESPONSE_BYTES) {
    fail('The selected build request is too large.');
  }
}

async function readJson(response, signal) {
  const media = response.headers?.get?.('content-type');
  if (media && media.split(';', 1)[0].trim().toLowerCase() !== 'application/json') {
    fail('The build service returned an unexpected response type.');
  }
  const rawLength = response.headers?.get?.('content-length');
  if (rawLength && (!/^\d+$/.test(rawLength) || Number(rawLength) > MAX_RESPONSE_BYTES)) {
    fail('The build service returned an oversized response.');
  }
  if (response.body?.getReader) {
    const reader = response.body.getReader();
    const chunks = [];
    let byteLength = 0;
    while (true) {
      let removeAbort;
      const aborted = new Promise((_, reject) => {
        const onAbort = () => {
          void reader.cancel().catch(() => {});
          reject(new DOMException('Aborted', 'AbortError'));
        };
        if (signal?.aborted) onAbort();
        else if (signal) {
          signal.addEventListener('abort', onAbort, { once: true });
          removeAbort = () => signal.removeEventListener('abort', onAbort);
        }
      });
      let result;
      try { result = await Promise.race([reader.read(), aborted]); }
      finally { removeAbort?.(); }
      const { done, value } = result;
      if (done) break;
      byteLength += value.byteLength;
      if (byteLength > MAX_RESPONSE_BYTES) {
        await reader.cancel();
        fail('The build service returned an oversized response.');
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(byteLength);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)); }
    catch { fail('The build service returned invalid data.'); }
  }
  fail('The build service returned invalid data.');
}

function responseError(response, body) {
  if (response.status === 429) return new Error('The build queue is full. Try again later.');
  if (response.status === 422) return new Error('The build request was rejected. Review the selected modules and projects.');
  if (response.status >= 500) return new Error('The build service could not complete this request.');
  return new Error(typeof body?.detail === 'string' ? body.detail.slice(0, 180) : 'The build service rejected this request.');
}

function validateStatusURL(value, id, origin) {
  if (typeof value !== 'string') fail('The build service returned an invalid status address.');
  let url;
  try { url = new URL(value, origin); } catch { fail('The build service returned an invalid status address.'); }
  if (url.origin !== origin || url.username || url.password || url.search || url.hash
      || url.pathname !== `${BUILD_PATH}/${id}`) {
    fail('The build service returned an invalid status address.');
  }
  return url.href;
}

function validateSubmission(body, origin) {
  if (!body || typeof body !== 'object' || !OPAQUE_ID.test(body.id)
      || body.status !== 'queued') fail('The build service returned an invalid job.');
  return Object.freeze({
    id: body.id,
    statusURL: validateStatusURL(body.status_url, body.id, origin),
  });
}

function validateSnapshot(body, id) {
  if (!body || body.id !== id || body.kind !== 'private-diagnostic-build'
      || !['queued', 'running', 'succeeded', 'failed'].includes(body.status)) {
    fail('The build service returned an invalid job status.');
  }
  if (body.status === 'failed') fail('The private diagnostic build failed. No firmware was produced.');
  if (body.status !== 'succeeded') return Object.freeze({ status: body.status });
  const result = body.result;
  if (!result || result.status !== 'linked-private-diagnostic'
      || typeof result.artifact_sha256 !== 'string' || !SHA256.test(result.artifact_sha256)
      || !Number.isInteger(result.artifact_bytes) || result.artifact_bytes < 1
      || result.artifact_bytes > MAX_ARTIFACT_BYTES
      || result.installable !== false || result.hardware_tested !== false) {
    fail('The build result did not pass diagnostic receipt checks.');
  }
  return Object.freeze({
    status: 'succeeded',
    artifactSha256: result.artifact_sha256,
    artifactBytes: result.artifact_bytes,
    installable: false,
    hardwareTested: false,
  });
}

function cancellable(signal, timeoutMs) {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  else signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort(new DOMException('Build request timed out.', 'TimeoutError'));
  }, timeoutMs);
  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    dispose() { clearTimeout(timer); signal?.removeEventListener('abort', abort); },
  };
}

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Aborted', 'AbortError')); return; }
    const timer = setTimeout(done, ms);
    function done() { signal.removeEventListener('abort', aborted); resolve(); }
    function aborted() { clearTimeout(timer); signal.removeEventListener('abort', aborted); reject(new DOMException('Aborted', 'AbortError')); }
    signal.addEventListener('abort', aborted, { once: true });
  });
}

/** Create a bounded same-origin diagnostic build client. Cancellation stops
 * this browser's active request and polling; the API has no server cancel route.
 */
export function createInstallerBuildClient({
  fetchImpl = globalThis.fetch,
  origin = globalThis.location?.origin,
  pollIntervalMs = 1000,
  maxWaitMs = 120000,
} = {}) {
  if (typeof fetchImpl !== 'function') throw new TypeError('A fetch implementation is required');
  if (typeof origin !== 'string') throw new TypeError('A page origin is required');
  const parsedOrigin = new URL(origin).origin;
  if (!Number.isFinite(pollIntervalMs) || pollIntervalMs < 100 || pollIntervalMs > 30000
      || !Number.isFinite(maxWaitMs) || maxWaitMs < 1000 || maxWaitMs > 300000) {
    throw new RangeError('Build client timing limits are outside the supported bounds');
  }

  return Object.freeze({
    async build(request, { signal, onProgress = () => {} } = {}) {
      validateRequest(request);
      if (typeof onProgress !== 'function') throw new TypeError('onProgress must be a function');
      const operation = cancellable(signal, maxWaitMs);
      try {
        const submitted = await fetchImpl(new URL(BUILD_PATH, parsedOrigin), {
          method: 'POST',
          headers: { 'content-type': 'application/json', accept: 'application/json' },
          cache: 'no-store',
          body: JSON.stringify(request),
          signal: operation.signal,
        });
        const initial = await readJson(submitted, operation.signal);
        if (submitted.status !== 202) throw responseError(submitted, initial);
        const job = validateSubmission(initial, parsedOrigin);
        onProgress('queued');

        while (true) {
          if (operation.signal.aborted) throw new DOMException('Aborted', 'AbortError');
          await sleep(pollIntervalMs, operation.signal);
          const response = await fetchImpl(job.statusURL, {
            method: 'GET', headers: { accept: 'application/json' },
            cache: 'no-store', signal: operation.signal,
          });
          const body = await readJson(response, operation.signal);
          if (!response.ok) throw responseError(response, body);
          const snapshot = validateSnapshot(body, job.id);
          if (snapshot.status === 'queued' || snapshot.status === 'running') {
            onProgress(snapshot.status);
            continue;
          }
          onProgress('succeeded');
          return snapshot;
        }
      } catch (error) {
        if (operation.timedOut()) throw new Error('The diagnostic build timed out.');
        if (signal?.aborted || error?.name === 'AbortError') throw new Error('The build request was canceled.');
        throw error;
      } finally {
        operation.dispose();
      }
    },
  });
}
