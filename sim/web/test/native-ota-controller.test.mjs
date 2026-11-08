// SPDX-License-Identifier: GPL-3.0-only
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createNativeOtaController, OTA_STAGES } from '../www/native-ota-controller.js';
import { HS_QUERY, UPGRADE } from '../www/third_party/fm1-ota/fm1ota.js';
import { FakeAccess, same } from './fake-midi.mjs';

async function verifier(bytes) {
  assert.deepEqual(bytes, Uint8Array.of(9, 8, 7));
  const logicalImage = Uint8Array.of(1, 2, 3, 4);
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', logicalImage));
  return { format: 'lunar-native-package-admission-v1', product: 'FM-1_501',
    model: 'FM-1', version: 501, logicalImage,
    logicalImageSha256: [...digest].map((byte) => byte.toString(16).padStart(2, '0')).join('') };
}

function rig({ running = 'FM-1_015', loader = 'ota-FM-1_015', application = 'FM-1_501',
  failFinish = null, wrongPair = false, noDisconnect = false, onStage = null } = {}) {
  const access = new FakeAccess();
  const pairs = {
    running: access.addPair('running', running,
      { failFinish: failFinish === 'running', noDisconnect }),
    loader: null,
    application: null,
  };
  const sleeps = [];
  const clock = { now: () => performance.now(),
    setTimeout: (fn, ms) => setTimeout(fn, ms === 30000 ? 2 : ms), clearTimeout,
    async sleep(ms) { sleeps.push(ms); } };
  let accessCalls = 0;
  let verifyCalls = 0;
  const controller = createNativeOtaController({
    packageAdmission: { async verify(bytes) { verifyCalls += 1; return verifier(bytes); } },
    async requestMIDIAccess(options) {
      assert.deepEqual(options, { sysex: true });
      assert.equal(verifyCalls, 1, 'verification must precede MIDI access');
      accessCalls += 1;
      return access;
    },
    async selectPair({ phase }) {
      if (phase === 'loader' && !pairs.loader) pairs.loader = access.addPair('loader', loader,
        { failFinish: failFinish === 'loader' });
      if (phase === 'application' && !pairs.application) pairs.application = access.addPair('application', application);
      return wrongPair && phase === 'running' ? { input: pairs.running.input, output: pairs.loader?.output } : pairs[phase];
    },
    clock, transferTimeouts: { idleTimeoutMs: 30, hardTimeoutMs: 100, responseDelayMs: 0 }, onStage,
  });
  return { controller, access, pairs, sleeps, get accessCalls() { return accessCalls; } };
}

const start = (controller) => controller.installFromUserAction({ packageBytes: Uint8Array.of(9, 8, 7),
  expectedProduct: 'FM-1_501' });

test('public admission stays closed before MIDI permission or any port open', async () => {
  let calls = 0;
  const controller = createNativeOtaController({ requestMIDIAccess: async () => { calls += 1; } });
  await assert.rejects(controller.installFromUserAction({ packageBytes: Uint8Array.of(9),
    expectedProduct: 'FM-1_501' }),
    /package admission blocked/);
  assert.equal(calls, 0);
});

test('explicit offline flow verifies, re-enumerates, and confirms the fresh application identity', async () => {
  const run = rig();
  const result = await start(run.controller);
  assert.equal(result.status, 'application-identity-confirmed');
  assert.equal(result.product, 'FM-1_501');
  assert.equal(result.packageSha256.length, 64);
  assert.equal(run.accessCalls, 1);
  assert.equal(run.access.opens, 6);
  assert.deepEqual(run.sleeps, [2000, 3000, 2000]);
  assert.deepEqual(run.access.sent.filter((sent) => same(sent.bytes, UPGRADE)).map((sent) => sent.phase),
    ['running', 'loader']);
  assert.deepEqual(run.access.sent.filter((sent) => same(sent.bytes, HS_QUERY)).map((sent) => sent.phase),
    ['running', 'loader', 'application']);
  assert.equal(run.access.listeners.size, 0);
});

test('wrong or already-installed running identity never receives upgrade', async () => {
  for (const running of ['FM-2_015', 'FM-1_501']) {
    const run = rig({ running });
    await assert.rejects(start(run.controller), /identity|already has the target/);
    assert.equal(run.access.sent.some((sent) => same(sent.bytes, UPGRADE)), false);
    assert.equal(run.access.listeners.size, 0);
  }
});

test('unselected or ambiguous pair is rejected before port open', async () => {
  const run = rig({ wrongPair: true });
  await assert.rejects(start(run.controller), /select an available input\/output pair/);
  assert.equal(run.access.opens, 0);
  assert.equal(run.access.sent.length, 0);
});

test('loader identity mismatch prevents image serving and write upgrade', async () => {
  const run = rig({ loader: 'ota-FM-2_015' });
  await assert.rejects(start(run.controller), /identity/);
  assert.equal(run.access.sent.some((sent) => sent.phase === 'loader' && same(sent.bytes, UPGRADE)), false);
  assert.equal(run.access.sent.filter((sent) => sent.phase === 'loader').every((sent) => same(sent.bytes, HS_QUERY)), true);
});

test('finish ACK send failure and post-write identity mismatch never report success', async () => {
  const failedAck = rig({ failFinish: 'loader' });
  await assert.rejects(start(failedAck.controller), /write transfer did not finish/);
  assert.equal(failedAck.access.sent.some((sent) => sent.phase === 'application'), false);
  const wrongApp = rig({ application: 'FM-1_015' });
  await assert.rejects(start(wrongApp.controller), /post-write application identity/);
  assert.equal(wrongApp.access.sent.some((sent) => sent.phase === 'application' && same(sent.bytes, HS_QUERY)), true);
});

test('a finish ACK without re-enumeration is still a failure', async () => {
  const run = rig({ noDisconnect: true });
  await assert.rejects(start(run.controller), /did not re-enumerate/);
  assert.equal(run.access.sent.some((sent) => sent.phase === 'loader'), false);
  assert.equal(run.access.listeners.size, 0);
});

test('stage observer sees every transition in order, and cannot break the transfer', async () => {
  const seen = [];
  const run = rig({ onStage: (name, detail) => { seen.push(`${name}:${detail.state}`); throw new Error('observer'); } });
  const result = await start(run.controller);
  assert.equal(result.status, 'application-identity-confirmed');
  const started = seen.filter((entry) => entry.endsWith(':start')).map((entry) => entry.split(':')[0]);
  assert.deepEqual(started, OTA_STAGES);
  assert.equal(seen.filter((entry) => entry.endsWith(':done')).length, OTA_STAGES.length);
  assert.ok(seen.some((entry) => entry === 'verify-transfer:progress') && seen.some((entry) => entry === 'write-transfer:progress'));
});

test('roll back: a Lunar running identity and an older target identity', async () => {
  const run = rig({ running: 'FM-1_099', loader: 'ota-FM-1_099', application: 'FM-1_501' });
  const result = await run.controller.installFromUserAction({ packageBytes: Uint8Array.of(9, 8, 7),
    expectedProduct: 'FM-1_501', runningProduct: 'FM-1_099' });
  assert.equal(result.product, 'FM-1_501');
  await assert.rejects(rig().controller.installFromUserAction({ packageBytes: Uint8Array.of(9, 8, 7),
    expectedProduct: 'FM-1_501', runningProduct: 'FM-1_501' }), /already has the target/);
  await assert.rejects(rig().controller.installFromUserAction({ packageBytes: Uint8Array.of(9, 8, 7),
    expectedProduct: 'FM-1_501', runningProduct: 'nonsense' }), /running FM-1 identity/);
});

test('resume from the OTA loader never talks to the running application', async () => {
  const run = rig();
  const result = await run.controller.installFromUserAction({ packageBytes: Uint8Array.of(9, 8, 7),
    expectedProduct: 'FM-1_501', startPhase: 'loader' });
  assert.equal(result.status, 'application-identity-confirmed');
  assert.equal(run.access.sent.some((sent) => sent.phase === 'running'), false);
  await assert.rejects(rig().controller.installFromUserAction({ packageBytes: Uint8Array.of(9, 8, 7),
    expectedProduct: 'FM-1_501', startPhase: 'bogus' }), /startPhase/);
});
