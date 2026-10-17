// SPDX-License-Identifier: MIT
// Same-origin client for the private build API. The service returns
// a verified summary only; it does not expose firmware bytes or installation.
import { D7000_REQUIRED_BY_GROUP, CONTINUOUS_BUILD_PROFILE } from './native-build-selection.js';

const BUILD_PATH = '/api/v1/builds';
const OPAQUE_ID = /^[A-Za-z0-9_-]{32}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const MAX_RESPONSE_BYTES = 65536;
const MAX_ARTIFACT_BYTES = 1048576;

function fail(message) { throw new Error(message); }

function validateRequest(request) {
  const groups = ['engines', 'effects', 'midi', 'modulation'];
  const keys = ['version', ...groups, 'project_ids', 'startup_index'];
  const hasSets = request && Object.hasOwn(request, 'set_ids');
  const hasLayout = request && Object.hasOwn(request, 'flash_layout');
  const hasRuntime = request && Object.hasOwn(request, 'runtime_mode');
  const hasBuildConfiguration = hasLayout && hasRuntime;
  const allowedKeys = [
    ...keys,
    ...(hasSets ? ['set_ids'] : []),
    ...(hasBuildConfiguration ? ['flash_layout', 'runtime_mode'] : []),
  ];
  if (!request || typeof request !== 'object'
      || (Object.getPrototypeOf(request) !== Object.prototype && Object.getPrototypeOf(request) !== null)
      || request.version !== 1 || !Array.isArray(request.project_ids)
      || request.project_ids.length < 1 || request.project_ids.length > 8
      || Object.keys(request).length !== allowedKeys.length
      || allowedKeys.some((key) => !Object.hasOwn(request, key))
      || !Number.isInteger(request.startup_index)
      || request.startup_index < 0 || request.startup_index >= request.project_ids.length) {
    fail('The selected build request is invalid.');
  }
  if (hasLayout !== hasRuntime
      || (hasBuildConfiguration
        && (request.flash_layout !== 'expanded-d7000'
          || !['song-diagnostic', 'continuous'].includes(request.runtime_mode)))) {
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
  if (hasBuildConfiguration && request.runtime_mode === 'song-diagnostic' && Object.entries(D7000_REQUIRED_BY_GROUP).some(([group, required]) =>
    required.some((id) => !request[group].includes(id)))) {
    fail('The selected build request is invalid.');
  }
  if (hasSets && (!Array.isArray(request.set_ids) || request.set_ids.length > 8
      || request.set_ids.some((value) => typeof value !== 'string' || value.length === 0)
      || new Set(request.set_ids).size !== request.set_ids.length)) {
    fail('The selected build request is invalid.');
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
    const cancel = () => {
      try {
        const pending = reader.cancel();
        pending?.catch?.(() => {});
      } catch { /* Cleanup must never extend the caller's deadline. */ }
    };
    try {
      while (true) {
        let removeAbort;
        const aborted = new Promise((_, reject) => {
          const onAbort = () => {
            cancel();
            reject(new DOMException('Aborted', 'AbortError'));
          };
          if (signal?.aborted) {
            onAbort();
          } else if (signal) {
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
          cancel();
          fail('The build service returned an oversized response.');
        }
        chunks.push(value);
      }
      const bytes = new Uint8Array(byteLength);
      let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
      try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)); }
      catch { fail('The build service returned invalid data.'); }
    } finally {
      try { reader.releaseLock(); } catch { /* A pending read may already own cleanup. */ }
    }
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

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function exactKeys(value, keys) {
  return value && typeof value === 'object' && !Array.isArray(value)
    && sameJson(Object.keys(value).sort(), [...keys].sort());
}

function validateReceiptPreview(preview, result, request) {
  if (preview === undefined) return null; // Older private service deployments remain readable.
  const keys = ['flash_layout', 'runtime_mode', 'profile', 'modules', 'projects',
    'sets', 'packed_content', 'application', 'provenance'];
  if (!exactKeys(preview, keys)) {
    fail('The build receipt preview is malformed.');
  }
  const flashLayout = request.flash_layout ?? 'expanded-d9000';
  const runtimeMode = request.runtime_mode ?? 'diagnostic';
  if (preview.flash_layout !== flashLayout || preview.runtime_mode !== runtimeMode) {
    fail('The build receipt preview profile differs from the request.');
  }
  const profile = preview.profile;
  if (!profile || typeof profile !== 'object' || Array.isArray(profile)
      || profile.flash_layout !== flashLayout || profile.runtime_mode !== runtimeMode) {
    fail('The build receipt preview profile is malformed.');
  }
  const profileKeys = Object.keys(profile).sort();
  const expectedProfileKeys = runtimeMode === 'continuous'
    ? ['flash_layout', 'profile_id', 'profile_sha256', 'runtime_mode', 'shapes_voices']
    : flashLayout === 'expanded-d7000'
      ? ['flash_layout', 'profile_id', 'runtime_mode', 'shapes_voices', 'tuple_schema']
      : ['flash_layout', 'runtime_mode', 'shapes_voices'];
  if (!sameJson(profileKeys, expectedProfileKeys)) fail('The build receipt preview profile has unexpected fields.');
  if ((runtimeMode === 'continuous'
        && (profile.profile_id !== CONTINUOUS_BUILD_PROFILE.profileId
          || profile.profile_sha256 !== CONTINUOUS_BUILD_PROFILE.profileSha256
          || profile.shapes_voices !== 8))
      || (flashLayout === 'expanded-d7000' && runtimeMode !== 'continuous'
        && (profile.profile_id !== 'fm1-092-d7000' || profile.tuple_schema !== 2
          || profile.shapes_voices !== 8))
      || (flashLayout === 'expanded-d9000' && profile.shapes_voices !== 12)) {
    fail('The build receipt preview does not identify a supported verified profile.');
  }
  const modules = ['engines', 'effects', 'midi', 'modulation'].flatMap(group => request[group]);
  const projects = request.project_ids.map((id, index) => ({ id, startup: index === request.startup_index }));
  const sets = (request.set_ids ?? []).map(id => ({
    id, parent_project_id: request.project_ids[request.startup_index],
  }));
  if (!sameJson(preview.modules, modules) || !sameJson(preview.projects, projects)
      || !sameJson(preview.sets, sets)) {
    fail('The build receipt preview identities differ from the request.');
  }
  const packed = preview.packed_content;
  const expectedAssets = [...request.project_ids.map(id => ({ kind: 'project', id })),
    ...(request.set_ids ?? []).map(id => ({ kind: 'set', id,
      parent_project_id: request.project_ids[request.startup_index] }))];
  if (!packed || typeof packed !== 'object' || Array.isArray(packed)
      || !exactKeys(packed, ['bytes', 'assets'])
      || !Number.isSafeInteger(packed.bytes) || packed.bytes < 0
      || !Array.isArray(packed.assets) || packed.assets.length !== expectedAssets.length) {
    fail('The build receipt preview content is malformed.');
  }
  let packedBytes = 0;
  const assets = packed.assets.map((asset, index) => {
    const identity = expectedAssets[index];
    if (!asset || typeof asset !== 'object' || Array.isArray(asset)
        || !exactKeys(asset, identity.kind === 'set'
          ? ['kind', 'id', 'parent_project_id', 'bytes', 'sha256']
          : ['kind', 'id', 'bytes', 'sha256'])
        || asset.kind !== identity.kind || asset.id !== identity.id
        || (identity.kind === 'set' && asset.parent_project_id !== identity.parent_project_id)
        || (identity.kind === 'project' && Object.hasOwn(asset, 'parent_project_id'))
        || !Number.isSafeInteger(asset.bytes) || asset.bytes < 1 || asset.bytes > MAX_ARTIFACT_BYTES
        || typeof asset.sha256 !== 'string' || !SHA256.test(asset.sha256)) {
      fail('The build receipt preview content differs from the selected projects or SETs.');
    }
    packedBytes += asset.bytes;
    if (!Number.isSafeInteger(packedBytes) || packedBytes > MAX_ARTIFACT_BYTES) {
      fail('The build receipt preview content exceeds the supported bound.');
    }
    return Object.freeze({ kind: asset.kind, id: asset.id,
      ...(identity.kind === 'set' ? { parentProjectId: identity.parent_project_id } : {}),
      bytes: asset.bytes, sha256: asset.sha256 });
  });
  if (packed.bytes !== packedBytes) fail('The build receipt preview content total is inconsistent.');
  const application = preview.application;
  if (!application || typeof application !== 'object' || Array.isArray(application)
      || !exactKeys(application, ['sha256', 'bytes', 'budget_bytes', 'remaining_bytes'])
      || application.sha256 !== result.artifact_sha256
      || application.bytes !== result.artifact_bytes
      || application.budget_bytes !== result.app_budget_bytes
      || application.remaining_bytes !== result.remaining_bytes) {
    fail('The build receipt preview application does not match the verified build.');
  }
  const provenance = preview.provenance;
  if (!provenance || typeof provenance !== 'object' || Array.isArray(provenance)
      || !exactKeys(provenance, ['kind', 'sha256'])
      || typeof provenance.kind !== 'string' || provenance.kind.length > 80
      || typeof provenance.sha256 !== 'string' || !SHA256.test(provenance.sha256)
      || provenance.kind !== result.provenance?.kind
      || provenance.sha256 !== result.provenance?.sha256) {
    fail('The build receipt preview provenance is malformed.');
  }
  return Object.freeze({ flashLayout, runtimeMode, profile: Object.freeze({ ...profile }),
    modules: Object.freeze([...modules]), projects: Object.freeze(projects.map(Object.freeze)),
    sets: Object.freeze(sets.map(set => Object.freeze({ id: set.id, parentProjectId: set.parent_project_id }))),
    packedContentBytes: packed.bytes,
    assets: Object.freeze(assets), application: Object.freeze({
      sha256: application.sha256, bytes: application.bytes, budgetBytes: application.budget_bytes,
      remainingBytes: application.remaining_bytes,
    }), provenance: Object.freeze({ kind: provenance.kind, sha256: provenance.sha256 }) });
}

function validateSnapshot(body, id, request) {
  const continuous = request.runtime_mode === 'continuous';
  const kind = continuous ? 'private-continuous-build' : 'private-diagnostic-build';
  const status = continuous ? 'linked-private-continuous' : 'linked-private-diagnostic';
  if (!body || body.id !== id || body.kind !== kind
      || !['queued', 'running', 'succeeded', 'failed'].includes(body.status)) {
    fail('The build service returned an invalid job status.');
  }
  if (body.status === 'failed') fail('The private build failed. No firmware was produced.');
  if (body.status !== 'succeeded') return Object.freeze({ status: body.status });
  const result = body.result;
  if (!result || result.status !== status
      || typeof result.artifact_sha256 !== 'string' || !SHA256.test(result.artifact_sha256)
      || !Number.isInteger(result.artifact_bytes) || result.artifact_bytes < 1
      || result.artifact_bytes > MAX_ARTIFACT_BYTES
      || !Number.isInteger(result.app_budget_bytes)
      || result.app_budget_bytes < result.artifact_bytes
      || result.app_budget_bytes > MAX_ARTIFACT_BYTES
      || !Number.isInteger(result.remaining_bytes)
      || result.remaining_bytes !== result.app_budget_bytes - result.artifact_bytes
      || result.installable !== false || result.hardware_tested !== false) {
    fail('The build result did not pass private receipt checks.');
  }
  if (continuous) {
    const provenance = result.provenance;
    const profile = provenance?.profile;
    if (result.app_budget_bytes !== 860644
        || result.hardware_admitted !== false || result.native_ram_verified !== false
        || result.native_playback_verified !== false || result.full_song_default_accepted !== false
        || provenance?.kind !== 'private-continuous-build-provenance'
        || provenance.trusted_fwsc_packager_compatible !== false
        || typeof provenance.sha256 !== 'string' || !SHA256.test(provenance.sha256)
        || profile?.profile_id !== CONTINUOUS_BUILD_PROFILE.profileId
        || profile.profile_sha256 !== CONTINUOUS_BUILD_PROFILE.profileSha256
        || profile.flash_layout !== 'expanded-d7000' || profile.runtime_mode !== 'continuous'
        || profile.shapes_voices !== 8
        || provenance.output_bindings?.artifact_sha256 !== result.artifact_sha256
        || provenance.output_bindings?.artifact_bytes !== result.artifact_bytes) {
      fail('The continuous private link result did not pass receipt checks.');
    }
  }
  const receiptPreview = validateReceiptPreview(result.receipt_preview, result, request);
  return Object.freeze({
    status: 'succeeded',
    artifactSha256: result.artifact_sha256,
    artifactBytes: result.artifact_bytes,
    appBudgetBytes: result.app_budget_bytes,
    remainingBytes: result.remaining_bytes,
    ...(receiptPreview ? { receiptPreview } : {}),
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
          credentials: 'same-origin',
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
            credentials: 'same-origin',
            cache: 'no-store', signal: operation.signal,
          });
          const body = await readJson(response, operation.signal);
          if (!response.ok) throw responseError(response, body);
          const snapshot = validateSnapshot(body, job.id, request);
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
