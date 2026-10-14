// SPDX-License-Identifier: GPL-3.0-only
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  HS_QUERY, Link, MAXDATA, pack7, parseIdentity, parseRequest, serveRequests,
} from '../www/third_party/felucca-ota/fm1ota.js';
import { createNativeOtaAdapter } from '../www/native-ota-adapter.js';

function checksum(bytes) {
  return (~bytes.reduce((sum, byte) => sum + byte, 0)) & 0xFF;
}

function request({ addr, length, bodyLength = 8, flashType = 0 }) {
  const decoded = [0, 0x59, 0x30, bodyLength & 0xFF, bodyLength >> 8, 0,
    flashType, addr & 0xFF, (addr >>> 8) & 0xFF, (addr >>> 16) & 0xFF,
    (addr >>> 24) & 0xFF, length & 0xFF, (length >>> 8) & 0xFF, (length >>> 16) & 0xFF];
  decoded.push(checksum(decoded.slice(6)));
  return Uint8Array.from([0xF0, ...pack7(decoded), 0xF7]);
}

function identity(text, { bodyLength = 27, badChecksum = false } = {}) {
  const name = [...new TextEncoder().encode(text)];
  const decoded = [0, 0x59, 0x11, bodyLength & 0xFF, bodyLength >> 8, 0,
    ...name, ...new Array(27 - name.length).fill(0)];
  decoded.push(checksum(decoded.slice(6)) ^ (badChecksum ? 1 : 0));
  return Uint8Array.from([0xF0, ...pack7(decoded), 0xF7]);
}

class FakePorts {
  constructor(identityText = 'FM-1_015', { sendFailsAt = Infinity, queueLimit = 32,
    onSend = null, respondToHandshake = true } = {}) {
    this.opens = 0;
    this.closes = 0;
    this.sends = [];
    this.input = {
      id: 'input-1', name: 'FM-1', state: 'connected', onmidimessage: null,
      open: async () => { this.opens += 1; },
      close: async () => { this.closes += 1; },
    };
    this.output = {
      id: 'output-1', name: 'FM-1', state: 'connected', open: async () => { this.opens += 1; },
      close: async () => { this.closes += 1; },
      send: (bytes) => {
        this.sends.push(Array.from(bytes));
        onSend?.(bytes);
        if (this.sends.length === sendFailsAt) throw new Error('fake disconnected');
        if (respondToHandshake && Array.from(bytes).join(',') === Array.from(HS_QUERY).join(',')) {
          this.emit(identity(identityText));
        }
      },
    };
    this.queueLimit = queueLimit;
  }
  emit(data) { this.input.onmidimessage?.({ data: Uint8Array.from(data) }); }
}

function linkFor(fake, options) {
  return new Link(fake.input, fake.output, options);
}

test('strict request parser checks framing, body count, decoded size, and checksum', () => {
  const good = request({ addr: 0x1234, length: 512 });
  assert.deepEqual(parseRequest(good), { fl: 0, addr: 0x1234, len: 512 });
  const badLength = request({ addr: 1, length: 1, bodyLength: 9 });
  assert.equal(parseRequest(badLength), null);
  const badChecksum = Uint8Array.from(good);
  badChecksum[badChecksum.length - 2] ^= 1;
  assert.equal(parseRequest(badChecksum), null);
  assert.equal(parseRequest(Uint8Array.from([0xF0, 0, 0xF7])), null);
  assert.equal(parseRequest(Uint8Array.from([0xF0, ...good.slice(1, -1)])), null);
});

test('identity parser requires exact length, body count, checksum, and normalized ASCII identity', () => {
  assert.deepEqual(parseIdentity(identity('FM-1_015')), { text: 'FM-1_015', model: 'FM-1', version: 15 });
  assert.equal(parseIdentity(identity('FM-1_015', { bodyLength: 26 })), null);
  assert.equal(parseIdentity(identity('FM-1_015', { badChecksum: true })), null);
  assert.equal(parseIdentity(Uint8Array.from([0xF0, ...identity('FM-1_015').slice(1, -1)])), null);
  assert.equal(parseIdentity(identity('FM_15x')), null);
});

test('Link queue has a hard cap and reports overflow to pending readers', async () => {
  const fake = new FakePorts();
  const link = linkFor(fake, { queueLimit: 2 });
  fake.emit(request({ addr: 0, length: 1 }));
  fake.emit(request({ addr: 1, length: 1 }));
  fake.emit(request({ addr: 2, length: 1 }));
  await assert.rejects(link.read(1), { code: 'queue-overflow' });
  link.close();
  assert.equal(fake.input.onmidimessage, null);
});

test('transfer bounds reject zero length, 513 bytes, end offsets, and out-of-range reads', async () => {
  const image = new Uint8Array(1024);
  for (const [addr, length] of [[0, 0], [0, MAXDATA + 1], [1024, 0], [1023, 2]]) {
    const fake = new FakePorts();
    const link = linkFor(fake);
    fake.emit(request({ addr, length }));
    await assert.rejects(serveRequests(link, image, 0xE0000000,
      { idleTimeoutMs: 10, hardTimeoutMs: 20, responseDelayMs: 0 }), { code: 'badreq' });
    link.close();
  }
  assert.equal(MAXDATA, 512);
});

test('a false send at the finish ACK never reports completion', async () => {
  const fake = new FakePorts('FM-1_015', { sendFailsAt: 1 });
  const link = linkFor(fake);
  fake.emit(request({ addr: 0xE0000000, length: 8 }));
  const result = await serveRequests(link, new Uint8Array(32), 0xE0000000,
    { idleTimeoutMs: 10, hardTimeoutMs: 20, responseDelayMs: 0 });
  assert.equal(result.finished, false);
  assert.equal(result.sendFailed, true);
});

test('absolute and idle deadlines stop an otherwise quiet transfer', async () => {
  const fake = new FakePorts();
  const link = linkFor(fake);
  const result = await serveRequests(link, new Uint8Array(64), 0xE0000000,
    { idleTimeoutMs: 10, hardTimeoutMs: 30, responseDelayMs: 0 });
  assert.equal(result.finished, false);
  assert.equal(result.timeout, true);
  link.close();
});

test('hard deadline stops valid requests that keep refreshing the idle deadline', async () => {
  let now = 0;
  let sent = 0;
  const link = {
    lost: false,
    async read() { return request({ addr: 0, length: 1 }); },
    send() { sent += 1; return true; },
  };
  const clock = {
    now: () => now,
    sleep: async (ms) => { now += ms; },
  };
  const result = await serveRequests(link, new Uint8Array(64), 0xE0000000,
    { clock, idleTimeoutMs: 100, hardTimeoutMs: 5, responseDelayMs: 1 });
  assert.equal(result.finished, false);
  assert.equal(result.timeout, true);
  assert.equal(sent, 4);
  assert.equal(now, 5);
});

test('adapter does no port I/O before package admission and explicit pair selection', async () => {
  const image = Uint8Array.of(1, 2, 3, 4);
  const digestBytes = new Uint8Array(await crypto.subtle.digest('SHA-256', image));
  const imageSha = [...digestBytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  const fake = new FakePorts();
  const adapter = createNativeOtaAdapter({ packageAdmission: {
    async verify() {
      return { format: 'lunar-native-package-admission-v1', product: 'FM-1_015', model: 'FM-1',
        version: 15, logicalImage: image, logicalImageSha256: imageSha };
    },
  } });

  assert.equal(fake.opens, 0);
  assert.equal(fake.sends.length, 0);
  const admission = await adapter.admitPackage(Uint8Array.of(9), 'FM-1_015');
  assert.equal(fake.opens, 0);
  assert.equal(fake.sends.length, 0);
  await assert.rejects(adapter.connect({ admission: { ...admission }, input: fake.input, output: fake.output }), /not issued/);
  assert.equal(fake.opens, 0);
  assert.equal(fake.sends.length, 0);

  const session = await adapter.connect({ admission, input: fake.input, output: fake.output });
  assert.equal(session.identity, 'FM-1_015');
  assert.equal(fake.opens, 2);
  assert.equal(fake.sends.length, 1);
  assert.equal(await adapter.close(session), true);
  assert.equal(fake.closes, 2);
});

test('admission, session, and resume capabilities cannot cross adapter instances', async () => {
  const image = Uint8Array.of(2, 4, 6);
  const digestBytes = new Uint8Array(await crypto.subtle.digest('SHA-256', image));
  const imageSha = [...digestBytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  const packageAdmission = { async verify() {
    return { format: 'lunar-native-package-admission-v1', product: 'FM-1_015', model: 'FM-1',
      version: 15, logicalImage: image, logicalImageSha256: imageSha };
  } };
  const adapterA = createNativeOtaAdapter({ packageAdmission });
  const adapterB = createNativeOtaAdapter({ packageAdmission });
  const admissionA = await adapterA.admitPackage(Uint8Array.of(1));
  const fake = new FakePorts('ota-FM-1_015');
  await assert.rejects(adapterB.connect({ admission: admissionA, input: fake.input, output: fake.output }), /not issued/);
  assert.equal(fake.opens, 0);
  assert.equal(fake.sends.length, 0);
  const admissionB = await adapterB.admitPackage(Uint8Array.of(1));
  const sessionB = await adapterB.connect({ admission: admissionB, input: fake.input, output: fake.output, role: 'loader' });
  await assert.rejects(adapterA.serve({ admission: admissionB, session: sessionB, stage: 'verify' }), /not bound/);
  const tokenB = adapterB.createResumeToken({ admission: admissionB, session: sessionB });
  await assert.rejects(adapterA.resume({ admission: admissionA, token: tokenB,
    input: fake.input, output: fake.output }), /not bound to this exact admitted package/);
  assert.equal(await adapterB.close(sessionB), true);
});

test('connect timeout and identity mismatch detach listeners and close both ports', async () => {
  const image = Uint8Array.of(5, 7, 9);
  const digestBytes = new Uint8Array(await crypto.subtle.digest('SHA-256', image));
  const imageSha = [...digestBytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  const adapter = createNativeOtaAdapter({ packageAdmission: { async verify() {
    return { format: 'lunar-native-package-admission-v1', product: 'FM-1_015', model: 'FM-1',
      version: 15, logicalImage: image, logicalImageSha256: imageSha };
  } }, clock: { now: () => 0, setTimeout: (fn) => { queueMicrotask(fn); return 1; },
    clearTimeout() {}, sleep: async () => {} } });
  const admission = await adapter.admitPackage(Uint8Array.of(3));
  for (const fake of [new FakePorts('FM-1_015', { respondToHandshake: false }), new FakePorts('FM-2_015')]) {
    await assert.rejects(adapter.connect({ admission, input: fake.input, output: fake.output }), /selected device identity/);
    assert.equal(fake.input.onmidimessage, null);
    assert.equal(fake.closes, 2);
  }
});

test('abort during a pending port open releases the late-opened port', async () => {
  const image = Uint8Array.of(1, 3, 5);
  const digestBytes = new Uint8Array(await crypto.subtle.digest('SHA-256', image));
  const imageSha = [...digestBytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  const adapter = createNativeOtaAdapter({ packageAdmission: { async verify() {
    return { format: 'lunar-native-package-admission-v1', product: 'FM-1_015', model: 'FM-1',
      version: 15, logicalImage: image, logicalImageSha256: imageSha };
  } } });
  const admission = await adapter.admitPackage(Uint8Array.of(4));
  const fake = new FakePorts();
  let resolveOpen;
  fake.input.open = () => new Promise((resolve) => { resolveOpen = resolve; });
  const controller = new AbortController();
  const attempt = adapter.connect({ admission, input: fake.input, output: fake.output, signal: controller.signal });
  await Promise.resolve();
  controller.abort();
  await assert.rejects(attempt, { name: 'AbortError' });
  resolveOpen();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(fake.input.onmidimessage, null);
  assert.equal(fake.opens, 0);
  assert.equal(fake.closes >= 3, true);
  assert.equal(fake.sends.length, 0);
});

test('admission rejects inconsistent identity or bytes before opening ports', async () => {
  const image = Uint8Array.of(1, 2, 3);
  const wrongDigest = '0'.repeat(64);
  const fake = new FakePorts();
  const adapter = createNativeOtaAdapter({ packageAdmission: {
    async verify() {
      return { format: 'lunar-native-package-admission-v1', product: 'FM-1_015', model: 'FM-1',
        version: 15, logicalImage: image, logicalImageSha256: wrongDigest };
    },
  } });
  await assert.rejects(adapter.admitPackage(Uint8Array.of(9)), /digest does not match/);
  assert.equal(fake.opens, 0);
  assert.equal(fake.sends.length, 0);
  const untrustedFlagAdapter = createNativeOtaAdapter({ packageAdmission: {
    verify: async () => ({ installable: true }),
  } });
  await assert.rejects(untrustedFlagAdapter.admitPackage(Uint8Array.of(1)), /invalid admission record/);
});

test('resume token is bound to the exact adapter admission and package SHA', async () => {
  const image = Uint8Array.of(1, 2, 3);
  const digestBytes = new Uint8Array(await crypto.subtle.digest('SHA-256', image));
  const imageSha = [...digestBytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  const fake = new FakePorts('ota-FM-1_015');
  const adapter = createNativeOtaAdapter({ packageAdmission: {
    async verify() {
      return { format: 'lunar-native-package-admission-v1', product: 'FM-1_015', model: 'FM-1',
        version: 15, logicalImage: image, logicalImageSha256: imageSha };
    },
  } });
  const admission = await adapter.admitPackage(Uint8Array.of(9));
  const alternateAdmission = await adapter.admitPackage(Uint8Array.of(8));
  const session = await adapter.connect({ admission, input: fake.input, output: fake.output, role: 'loader' });
  const token = adapter.createResumeToken({ admission, session });
  assert.notEqual(token.packageSha256, token.sha256);
  await assert.rejects(adapter.resume({ admission: alternateAdmission, token, input: fake.input, output: fake.output }),
    /not bound to this exact admitted package/);
  const changedIdentity = new FakePorts('ota-FM-1_016');
  await assert.rejects(adapter.resume({ admission, token, input: changedIdentity.input, output: changedIdentity.output }),
    /identity does not match the pinned session identity/);
  assert.equal(changedIdentity.input.onmidimessage, null);
  await assert.rejects(adapter.resume({ admission: { ...admission }, token, input: fake.input, output: fake.output }),
    /not bound to this exact admitted package/);
  assert.equal(fake.opens, 2);
  assert.equal(fake.sends.length, 1);
  await adapter.close(session);
});

