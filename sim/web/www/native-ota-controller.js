// SPDX-License-Identifier: GPL-3.0-only
// Offline orchestration seam. This module never calls navigator.requestMIDIAccess
// or selects a port itself. The public verifier still rejects every package.
import { verifyNativePackage } from './native-package-admission.js';
import { createNativeOtaAdapter } from './native-ota-adapter.js';

const defaultClock = {
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms),
  clearTimeout: (id) => globalThis.clearTimeout(id),
  sleep: (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms)),
  now: () => globalThis.performance?.now?.() ?? Date.now(),
};

function selectedPair(access, pair) {
  const { input, output } = pair ?? {};
  if (!input || !output || access.inputs?.get?.(input.id) !== input ||
      access.outputs?.get?.(output.id) !== output ||
      input.state !== 'connected' || output.state !== 'connected' ||
      input.type !== 'input' || output.type !== 'output') {
    throw new Error('select an available input/output pair from this MIDI access session');
  }
  return { input, output };
}

function watchDisconnect(access, pair, clock) {
  if (typeof access.addEventListener !== 'function' ||
      typeof access.removeEventListener !== 'function') {
    throw new TypeError('MIDI access must report port state changes');
  }
  let observed = false;
  let closed = false;
  let waiter = null;
  let timer = null;
  const onChange = (event) => {
    const port = event?.port;
    if (port?.state !== 'disconnected' ||
        (port.id !== pair.input.id && port.id !== pair.output.id)) return;
    observed = true;
    if (waiter) { waiter.resolve(); waiter = null; }
  };
  access.addEventListener('statechange', onChange);
  return {
    wait() {
      if (observed) return Promise.resolve();
      if (closed) return Promise.reject(new Error('re-enumeration watcher is closed'));
      if (waiter) throw new Error('re-enumeration already has a waiter');
      return new Promise((resolve, reject) => {
        waiter = { resolve, reject };
        // The timeout starts after the ACK, not before a long but valid transfer.
        timer = clock.setTimeout(() => {
          waiter = null;
          reject(new Error('the selected MIDI device did not re-enumerate'));
        }, 30000);
      });
    },
    close() {
      closed = true;
      access.removeEventListener('statechange', onChange);
      if (timer !== null) clock.clearTimeout(timer);
      if (waiter) { waiter.resolve(); waiter = null; }
    },
  };
}

function requireFinished(result, stage) {
  if (result?.finished !== true) {
    throw new Error(`${stage} transfer did not finish with an acknowledged device request`);
  }
}

export const OTA_STAGES = Object.freeze([
  'admission', 'midi-access', 'select-running', 'running-identity', 'upgrade-verify',
  'verify-transfer', 're-enumerate-loader', 'select-loader', 'loader-identity',
  'upgrade-write', 'write-transfer', 're-enumerate-application', 'select-application',
  'fresh-identity',
]);

/**
 * Call installFromUserAction only from an explicit install action after a
 * separate release verifier exists. There is deliberately no automatic UI or
 * global Web MIDI fallback here. The injected selector must make each pair an
 * explicit user choice; port names are not device-mode evidence.
 *
 * onStage(name, detail) reports each transition (see OTA_STAGES) with
 * detail.state of 'start' | 'done'; a throwing observer never affects the flow.
 * installFromUserAction accepts runningProduct (the identity the unit reports
 * before the update; default FM-1_015, the stock V15 the updater needs) and,
 * for a roll-back, a target older than the running application. startPhase
 * 'loader' resumes with a unit already sitting in its OTA loader.
 */
export function createNativeOtaController({
  packageAdmission = { verify: verifyNativePackage },
  requestMIDIAccess = null,
  selectPair = null,
  clock = defaultClock,
  transferTimeouts = {},
  onStage = null,
} = {}) {
  const adapter = createNativeOtaAdapter({ packageAdmission, clock });
  if (requestMIDIAccess !== null && typeof requestMIDIAccess !== 'function') {
    throw new TypeError('requestMIDIAccess must be a function');
  }
  if (selectPair !== null && typeof selectPair !== 'function') {
    throw new TypeError('selectPair must be a function');
  }
  if (onStage !== null && typeof onStage !== 'function') {
    throw new TypeError('onStage must be a function');
  }
  let inFlight = false;
  const stage = (name, state, detail = {}) => {
    try { onStage?.(name, { state, ...detail }); } catch { /* observers cannot affect the transfer */ }
  };
  const progress = (name) => (served) => stage(name, 'progress', { served });

  async function installFromUserAction({ packageBytes, expectedProduct,
    runningProduct = 'FM-1_015', startPhase = 'running' } = {}) {
    if (inFlight) throw new Error('an OTA session is already in progress');
    inFlight = true;
    let runningSession;
    let loaderSession;
    let applicationSession;
    let watcher;
    try {
      if (!/^FM-1_\d{3}$/.test(expectedProduct ?? '')) {
        throw new TypeError('an exact FM-1 target identity must be selected');
      }
      if (!/^FM-1_\d{3}$/.test(runningProduct)) {
        throw new TypeError('an exact running FM-1 identity must be selected');
      }
      if (startPhase !== 'running' && startPhase !== 'loader') {
        throw new TypeError('startPhase must be running or loader');
      }
      // Admission completes before permission prompts, port enumeration or opens.
      stage('admission', 'start');
      const admission = await adapter.admitPackage(packageBytes, expectedProduct);
      stage('admission', 'done', { product: admission.product });
      if (runningProduct === admission.product) {
        throw new Error('running application identity is wrong or already has the target version');
      }
      if (typeof requestMIDIAccess !== 'function' || typeof selectPair !== 'function') {
        throw new Error('an explicit Web MIDI access and port selector are required');
      }
      stage('midi-access', 'start');
      const access = await requestMIDIAccess({ sysex: true });
      if (!access || access.sysexEnabled !== true) throw new Error('SysEx permission is required');
      stage('midi-access', 'done');
      if (startPhase === 'running') {
        stage('select-running', 'start');
        const runningPair = selectedPair(access, await selectPair({ phase: 'running', access }));
        stage('select-running', 'done');
        stage('running-identity', 'start');
        runningSession = await adapter.connect({ admission, ...runningPair, role: 'running' });
        if (runningSession.identity !== runningProduct) {
          throw new Error('running application identity is wrong or already has the target version');
        }
        stage('running-identity', 'done', { identity: runningSession.identity });

        watcher = watchDisconnect(access, runningPair, clock);
        stage('upgrade-verify', 'start');
        adapter.upgrade({ admission, session: runningSession });
        await clock.sleep(2000); // Stock updater pause before read-request service.
        stage('upgrade-verify', 'done');
        stage('verify-transfer', 'start');
        requireFinished(await adapter.serve({ admission, session: runningSession,
          stage: 'verify', timeouts: { ...transferTimeouts, onProgress: progress('verify-transfer') } }),
        'verification');
        stage('verify-transfer', 'done');
        stage('re-enumerate-loader', 'start');
        await watcher.wait();
        watcher.close();
        watcher = null;
        stage('re-enumerate-loader', 'done');
      }

      stage('select-loader', 'start');
      const loaderPair = selectedPair(access, await selectPair({ phase: 'loader', access }));
      stage('select-loader', 'done');
      stage('loader-identity', 'start');
      loaderSession = await adapter.connect({ admission, ...loaderPair, role: 'loader' });
      if (loaderSession.identity !== `ota-${runningProduct}`) {
        throw new Error('OTA loader identity does not match the verified running application');
      }
      // The adapter binds this recovery token to this exact package and loader
      // identity. The controller does not persist or expose it as a public install.
      adapter.createResumeToken({ admission, session: loaderSession });
      stage('loader-identity', 'done', { identity: loaderSession.identity });

      watcher = watchDisconnect(access, loaderPair, clock);
      stage('upgrade-write', 'start');
      adapter.upgrade({ admission, session: loaderSession });
      await clock.sleep(2000);
      stage('upgrade-write', 'done');
      stage('write-transfer', 'start');
      requireFinished(await adapter.serve({ admission, session: loaderSession,
        stage: 'write', timeouts: { ...transferTimeouts, onProgress: progress('write-transfer') } }),
      'write');
      stage('write-transfer', 'done');
      stage('re-enumerate-application', 'start');
      await watcher.wait();
      watcher.close();
      watcher = null;
      stage('re-enumerate-application', 'done');

      stage('select-application', 'start');
      const applicationPair = selectedPair(access, await selectPair({ phase: 'application', access }));
      stage('select-application', 'done');
      stage('fresh-identity', 'start');
      applicationSession = await adapter.connect({ admission, ...applicationPair, role: 'running' });
      if (applicationSession.identity !== admission.product) {
        throw new Error('post-write application identity does not match the admitted package');
      }
      stage('fresh-identity', 'done', { identity: applicationSession.identity });
      return Object.freeze({ status: 'application-identity-confirmed',
        product: admission.product, packageSha256: admission.packageSha256,
        logicalImageSha256: admission.sha256 });
    } finally {
      watcher?.close();
      await Promise.all([adapter.close(runningSession), adapter.close(loaderSession),
        adapter.close(applicationSession)]);
      inFlight = false;
    }
  }

  return Object.freeze({ installFromUserAction });
}
