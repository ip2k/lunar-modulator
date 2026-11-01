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

/**
 * Call installFromUserAction only from an explicit install action after a
 * separate release verifier exists. There is deliberately no automatic UI or
 * global Web MIDI fallback here. The injected selector must make each pair an
 * explicit user choice; port names are not device-mode evidence.
 */
export function createNativeOtaController({
  packageAdmission = { verify: verifyNativePackage },
  requestMIDIAccess = null,
  selectPair = null,
  clock = defaultClock,
  transferTimeouts = {},
} = {}) {
  const adapter = createNativeOtaAdapter({ packageAdmission, clock });
  if (requestMIDIAccess !== null && typeof requestMIDIAccess !== 'function') {
    throw new TypeError('requestMIDIAccess must be a function');
  }
  if (selectPair !== null && typeof selectPair !== 'function') {
    throw new TypeError('selectPair must be a function');
  }
  let inFlight = false;

  async function installFromUserAction({ packageBytes, expectedProduct } = {}) {
    if (inFlight) throw new Error('an OTA session is already in progress');
    inFlight = true;
    const runningProduct = 'FM-1_015';
    let runningSession;
    let loaderSession;
    let applicationSession;
    let watcher;
    try {
      if (!/^FM-1_\d{3}$/.test(expectedProduct ?? '')) {
        throw new TypeError('an exact FM-1 target identity must be selected');
      }
      // Admission completes before permission prompts, port enumeration or opens.
      const admission = await adapter.admitPackage(packageBytes, expectedProduct);
      if (typeof requestMIDIAccess !== 'function' || typeof selectPair !== 'function') {
        throw new Error('an explicit Web MIDI access and port selector are required');
      }
      const access = await requestMIDIAccess({ sysex: true });
      if (!access || access.sysexEnabled !== true) throw new Error('SysEx permission is required');
      const runningPair = selectedPair(access, await selectPair({ phase: 'running', access }));
      runningSession = await adapter.connect({ admission, ...runningPair, role: 'running' });
      if (runningSession.identity !== runningProduct || runningProduct === admission.product) {
        throw new Error('running application identity is wrong or already has the target version');
      }

      watcher = watchDisconnect(access, runningPair, clock);
      adapter.upgrade({ admission, session: runningSession });
      await clock.sleep(2000); // Stock updater pause before read-request service.
      requireFinished(await adapter.serve({ admission, session: runningSession,
        stage: 'verify', timeouts: transferTimeouts }), 'verification');
      await watcher.wait();
      watcher.close();
      watcher = null;

      const loaderPair = selectedPair(access, await selectPair({ phase: 'loader', access }));
      loaderSession = await adapter.connect({ admission, ...loaderPair, role: 'loader' });
      if (loaderSession.identity !== `ota-${runningProduct}`) {
        throw new Error('OTA loader identity does not match the verified running application');
      }
      // The adapter binds this recovery token to this exact package and loader
      // identity. The controller does not persist or expose it as a public install.
      adapter.createResumeToken({ admission, session: loaderSession });

      watcher = watchDisconnect(access, loaderPair, clock);
      adapter.upgrade({ admission, session: loaderSession });
      await clock.sleep(2000);
      requireFinished(await adapter.serve({ admission, session: loaderSession,
        stage: 'write', timeouts: transferTimeouts }), 'write');
      await watcher.wait();
      watcher.close();
      watcher = null;

      const applicationPair = selectedPair(access, await selectPair({ phase: 'application', access }));
      applicationSession = await adapter.connect({ admission, ...applicationPair, role: 'running' });
      if (applicationSession.identity !== admission.product) {
        throw new Error('post-write application identity does not match the admitted package');
      }
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
