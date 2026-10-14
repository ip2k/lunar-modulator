// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Lunar Modulator contributors
//
// Narrow, unwired adapter for the GPL-3.0-only protocol support in
// third_party/felucca-ota/fm1ota.js. It intentionally never requests
// MIDIAccess, enumerates ports, or probes a device. A future caller must supply
// an audited packageAdmission.verify implementation and explicit selected ports.

import { Link, handshake, serveRequests } from './third_party/felucca-ota/fm1ota.js';

const admissions = new WeakMap();
const sessions = new WeakMap();
const resumes = new WeakMap();

const defaultClock = {
  now: () => globalThis.performance?.now?.() ?? Date.now(),
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms),
  clearTimeout: (id) => globalThis.clearTimeout(id),
  sleep: (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms)),
};

function exactProduct(value) {
  const match = /^([A-Za-z0-9-]+)_(\d{1,3})$/.exec(value ?? '');
  if (!match) throw new TypeError('package admission must contain an exact model_version identity');
  return { product: value, model: match[1], version: Number(match[2]) };
}

function validPortPair(input, output) {
  if (!input || !output || typeof input.id !== 'string' || !input.id ||
      typeof output.id !== 'string' || !output.id || typeof input.name !== 'string' ||
      !input.name || output.name !== input.name || typeof input.open !== 'function' ||
      typeof output.open !== 'function' || typeof output.send !== 'function') {
    throw new TypeError('an explicitly selected matching MIDI input/output pair is required');
  }
  if (input.state === 'disconnected' || output.state === 'disconnected') {
    throw new Error('selected MIDI ports are disconnected');
  }
}

async function sha256Hex(bytes) {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new Error('Web Crypto SHA-256 is required for artifact pinning');
  const digest = new Uint8Array(await subtle.digest('SHA-256', bytes));
  return [...digest].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function createNativeOtaAdapter({ packageAdmission, clock = defaultClock } = {}) {
  if (!packageAdmission || typeof packageAdmission.verify !== 'function') {
    throw new TypeError('an audited packageAdmission.verify implementation is required');
  }

  // This interface deliberately requires a verifier-produced record, not an
  // `installable: true` flag. No firmware package parser/admission is supplied
  // here; the future installer must provide the audited implementation.
  async function admitPackage(packageBytes, expectedProduct) {
    if (!(packageBytes instanceof Uint8Array) || packageBytes.length === 0) {
      throw new TypeError('package bytes must be a nonempty Uint8Array');
    }
    const verified = await packageAdmission.verify(packageBytes.slice());
    if (!verified || verified.format !== 'lunar-native-package-admission-v1' ||
        !(verified.logicalImage instanceof Uint8Array) || verified.logicalImage.length === 0 ||
        typeof verified.logicalImageSha256 !== 'string') {
      throw new TypeError('package verifier returned an invalid admission record');
    }
    const target = exactProduct(verified.product);
    if (verified.model !== target.model || verified.version !== target.version) {
      throw new TypeError('package verifier returned inconsistent identity fields');
    }
    if (expectedProduct !== undefined && verified.product !== expectedProduct) {
      throw new Error('verified package identity does not match the selected target');
    }
    const image = verified.logicalImage.slice();
    const digest = await sha256Hex(image);
    const packageDigest = await sha256Hex(packageBytes);
    if (digest !== verified.logicalImageSha256.toLowerCase()) {
      throw new Error('package verifier logical-image digest does not match its bytes');
    }
    const handle = Object.freeze({ product: target.product, sha256: digest, packageSha256: packageDigest });
    admissions.set(handle, Object.freeze({ ...target, image, sha256: digest, packageSha256: packageDigest }));
    return handle;
  }

  async function connect({ admission, input, output, role = 'running' } = {}) {
    const admitted = admissions.get(admission);
    if (!admitted) throw new TypeError('package admission handle was not issued by this adapter');
    if (role !== 'running' && role !== 'loader') throw new TypeError('role must be running or loader');
    validPortPair(input, output);
    await input.open();
    await output.open();
    const link = new Link(input, output, { clock });
    const identity = await handshake(link, { clock, tries: 2, timeoutMs: 1000 });
    const expectedModel = role === 'loader' ? `ota-${admitted.model}` : admitted.model;
    if (!identity || identity.model !== expectedModel) {
      link.close();
      throw new Error(`selected device identity did not match ${expectedModel}`);
    }
    const session = Object.freeze({ role, product: admitted.product, sha256: admitted.sha256,
      packageSha256: admitted.packageSha256,
      identity: identity.text, inputId: input.id, outputId: output.id, portName: input.name });
    sessions.set(session, { admission, link, input, output, image: admitted.image,
      model: admitted.model, role, sha256: admitted.sha256, packageSha256: admitted.packageSha256 });
    return session;
  }

  async function serve({ admission, session, stage, timeouts = {} } = {}) {
    const admitted = admissions.get(admission);
    const active = sessions.get(session);
    if (!admitted || !active || active.admission !== admission || active.sha256 !== admitted.sha256 ||
        active.packageSha256 !== admitted.packageSha256) {
      throw new TypeError('session is not bound to this verified artifact');
    }
    if (stage !== 'verify' && stage !== 'write') throw new TypeError('stage must be verify or write');
    if (stage === 'write' && active.role !== 'loader') throw new Error('write stage requires an explicitly selected OTA loader');
    const finishAddr = stage === 'verify' ? 0xE0000000 : 0xF0000000;
    const result = await serveRequests(active.link, active.image, finishAddr, { clock, ...timeouts });
    if (result.finished) {
      active.link.close();
      sessions.delete(session);
    }
    return result;
  }

  function createResumeToken({ admission, session } = {}) {
    const admitted = admissions.get(admission);
    const active = sessions.get(session);
    if (!admitted || !active || active.admission !== admission || active.sha256 !== admitted.sha256 ||
        active.packageSha256 !== admitted.packageSha256) {
      throw new TypeError('cannot resume from a session bound to another artifact');
    }
    if (active.role !== 'loader') throw new Error('resume token requires an OTA-loader identity');
    const token = Object.freeze({ product: admitted.product, sha256: admitted.sha256,
      packageSha256: admitted.packageSha256, model: admitted.model, identity: active.identity });
    resumes.set(token, { admission, sha256: admitted.sha256,
      packageSha256: admitted.packageSha256, model: admitted.model, identity: active.identity });
    return token;
  }

  async function resume({ admission, token, input, output } = {}) {
    const admitted = admissions.get(admission);
    const saved = resumes.get(token);
    if (!admitted || !saved || saved.admission !== admission || saved.sha256 !== admitted.sha256 ||
        saved.packageSha256 !== admitted.packageSha256 || saved.model !== admitted.model ||
        token.sha256 !== admitted.sha256 || token.packageSha256 !== admitted.packageSha256 ||
        token.product !== admitted.product || token.identity !== saved.identity) {
      throw new TypeError('resume token is not bound to this exact admitted package');
    }
    // No port scan: the caller must explicitly select the re-enumerated pair.
    const session = await connect({ admission, input, output, role: 'loader' });
    if (session.identity !== saved.identity) {
      close(session);
      throw new Error('resumed OTA loader identity does not match the pinned session identity');
    }
    return session;
  }

  function close(session) {
    const active = sessions.get(session);
    if (!active) return false;
    active.link.close();
    sessions.delete(session);
    return true;
  }

  return Object.freeze({ admitPackage, connect, serve, createResumeToken, resume, close });
}
