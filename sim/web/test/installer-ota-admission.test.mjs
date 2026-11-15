// SPDX-License-Identifier: GPL-3.0-only
// The install panel's admission gate, offline: lunar-package-admission.js
// decides, and anything else (a refused package, a missing, throwing or
// malformed verifier) leaves the button disabled with no MIDI permission asked
// and nothing sent. Packages are synthetic (lunar-package-fixture.mjs) against
// a synthetic stock profile, so no vendor byte is needed. Every MIDI port is a
// fake; nothing reaches a device.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { Document, Element, walk } from './fake-dom.mjs';
import { FakeAccess, request, same } from './fake-midi.mjs';
import { HS_QUERY, UPGRADE, unpack7 } from '../www/third_party/fm1-ota/fm1ota.js';
import { mountOtaInstallFlow, verifiedAdmission, guidanceFor } from '../www/installer-ota-flow.js';
import { createNativeOtaAdapter } from '../www/native-ota-adapter.js';
import { logicalImage, sha256Hex, verifyNativePackage } from '../www/lunar-package-admission.js';
import {
  ADDR, FB, FO, LUNAR, PROFILE, SLOT, STOCK, STOCK_LOG, install, lunarApp, physical, repack,
} from './lunar-package-fixture.mjs';

const realVerify = (bytes) => verifyNativePackage(bytes, { profiles: [PROFILE] });
const SOFT_KEY = [0xf0, 0x22, 0x24, 0x35, 0x7d, 0xf7];
const find = (root, id) => walk(root).find((node) => node.id === id);
const tick = () => new Promise((resolve) => setImmediate(resolve));
async function until(predicate, what) {
  for (let i = 0; i < 400; i += 1) { if (predicate()) return; await tick(); }
  assert.fail(`timed out waiting for ${what}`);
}

/** A Lunar package with one rule broken and every CRC repaired. */
const tampered = (edit) => physical(repack(logicalImage(LUNAR), edit), 'FM-1_501');

function mount(options = {}) {
  const document = new Document();
  const root = new Element('div', document);
  const access = new FakeAccess();
  const log = { accessCalls: 0 };
  const flow = mountOtaInstallFlow(root, {
    requestMIDIAccess: async () => { log.accessCalls += 1; return access; },
    clock: { now: () => performance.now(), setTimeout: (fn, ms) => setTimeout(fn, ms === 30000 ? 2 : ms),
      clearTimeout, async sleep() {} },
    transferTimeouts: { idleTimeoutMs: 30, hardTimeoutMs: 100, responseDelayMs: 0 },
    ...options,
  });
  const offer = (bytes) => flow.receivePackage({ file: { name: 'pkg.fwsc' }, bytes });
  return { root, access, log, flow, offer, start: () => find(root, 'installer-ota-start'),
    admission: () => find(root, 'installer-ota-admission').textContent };
}

async function assertRefused(run, pattern) {
  assert.match(run.admission(), /^Not admitted: package admission blocked: /);
  if (pattern) assert.match(run.admission(), pattern);
  assert.equal(run.start().disabled, true, 'install stays disabled');
  await run.start().dispatch('click');
  assert.equal(run.log.accessCalls, 0, 'no MIDI permission is requested');
  assert.equal(run.access.sent.length, 0, 'nothing is sent');
  assert.equal(run.access.opens, 0, 'no port is opened');
}

test('an admitted Lunar package enables Install only; the roll-back mode refuses it', async () => {
  const run = mount({ packageAdmission: { verify: realVerify } });
  await run.offer(LUNAR);
  assert.match(run.admission(), /^Admitted: FM-1_501\. Ready: nothing is sent until you press Install\./);
  assert.equal(run.start().disabled, false);
  find(run.root, 'installer-ota-mode').value = 'rollback';
  await find(run.root, 'installer-ota-mode').dispatch('change');
  assert.equal(run.start().disabled, true);
  assert.equal(run.log.accessCalls + run.access.sent.length, 0);
});

test('the stock package is admitted for Roll back only', async () => {
  const run = mount({ packageAdmission: { verify: realVerify } });
  await run.offer(STOCK);
  assert.match(run.admission(), /Admitted: FM-1_015, but this is the stock FM-1_015 package; use Roll back instead/);
  assert.equal(run.start().disabled, true);
  find(run.root, 'installer-ota-mode').value = 'rollback';
  await find(run.root, 'installer-ota-mode').dispatch('change');
  const running = find(run.root, 'installer-ota-running');
  running.value = 'FM-1_501';
  await running.dispatch('input');
  assert.equal(run.start().disabled, false);
});

test('refused: a changed SPL / flash head [0, 0x4000), even with every CRC repaired', async () => {
  const run = mount({ packageAdmission: { verify: realVerify } });
  await run.offer(tampered({ log: (l) => { l[FO + 0x10] ^= 1; } }));
  await assertRefused(run, /flash head differs from stock: the bootloader would change/);
});

test('refused: changed entries after flash.bin (isd_config, ota.bin)', async () => {
  // One digest (post_flash_sha256) pins everything after flash.bin: in V15 that is
  // USR, isd_config, ota.bin and the tail. The synthetic package has no separate
  // isd_config entry, so a byte is flipped in its ota.bin entry and in its tail.
  for (const at of [FO + FB + 4, FO + FB + 40]) {
    const run = mount({ packageAdmission: { verify: realVerify } });
    await run.offer(tampered({ log: (l) => { l[at] ^= 1; } }));
    await assertRefused(run, /entries after flash\.bin \(USR, isd_config, ota\.bin, tail\) differ from stock/);
  }
});

test('refused: a changed cfg / reserved descriptor in the app area', async () => {
  const run = mount({ packageAdmission: { verify: realVerify } });
  await run.offer(tampered({ area: (a) => { a[ADDR + SLOT + 2] ^= 1; } }));
  await assertRefused(run, /app directory, cfg or reserved descriptors differ from stock/);
});

test('refused: an app that is not a Lunar FM-1_5xx build', async () => {
  const run = mount({ packageAdmission: { verify: realVerify } });
  await run.offer(install(STOCK_LOG, lunarApp('FM-1_092'), 'FM-1_092'));
  await assertRefused(run, /neither the pinned stock package nor a Lunar FM-1_5xx/);
});

test('fails closed: a verifier that throws, rejects, or is missing', async () => {
  const verifiers = {
    'throws synchronously': { verify() { throw new Error('boom'); } },
    rejects: { verify: async () => { throw new Error('boom'); } },
    'missing verify': {},
    'verify not a function': { verify: 'yes' },
    'no packageAdmission': null,
  };
  for (const [name, packageAdmission] of Object.entries(verifiers)) {
    const run = mount({ packageAdmission });
    await run.offer(LUNAR);
    assert.match(run.admission(), /^Not admitted: /, name);
    assert.equal(run.start().disabled, true, name);
    await run.start().dispatch('click');
    assert.equal(run.log.accessCalls + run.access.sent.length + run.access.opens, 0, name);
  }
});

test('fails closed: a malformed record or one for other bytes', async () => {
  const good = await realVerify(LUNAR);
  const records = {
    'no record': undefined,
    'wrong format': { ...good, format: 'lunar-native-package-admission-v0' },
    'no kind': { ...good, kind: undefined },
    'kind and identity disagree': { ...good, kind: 'stock-rollback' },
    'stock identity as a Lunar install': { ...good, product: 'FM-1_015' },
    'no logical image': { ...good, logicalImage: undefined },
    'empty logical image': { ...good, logicalImage: new Uint8Array(0) },
    'no package digest': { ...good, packageSha256: undefined },
    'digest of other bytes': { ...good, packageSha256: await sha256Hex(STOCK) },
  };
  for (const [name, record] of Object.entries(records)) {
    const run = mount({ packageAdmission: { verify: async () => record } });
    await run.offer(LUNAR);
    await assertRefused(run).catch((error) => { throw new Error(`${name}: ${error.message}`); });
  }
  await assert.rejects(verifiedAdmission({ verify: realVerify }, new Uint8Array(0)), /no package bytes/);
});

test('admission is re-run at the click: a verifier that now throws stops before MIDI access', async () => {
  let calls = 0;
  const run = mount({ packageAdmission: { async verify(bytes) {
    calls += 1;
    if (calls > 1) throw new Error('package admission blocked: changed its mind');
    return realVerify(bytes);
  } } });
  await run.offer(LUNAR);
  assert.equal(run.start().disabled, false);
  await run.start().dispatch('click');
  await until(() => /Stopped/.test(find(run.root, 'installer-ota-result').textContent), 'stop');
  assert.match(find(run.root, 'installer-ota-guidance').textContent, /Nothing was sent to the FM-1/);
  assert.equal(run.log.accessCalls + run.access.sent.length + run.access.opens, 0);
  assert.match(guidanceFor(new Error('odd'), 'admission'), /nothing was sent/);
});

test('default wiring: lunar-package-admission.js, pinned to stock V15, refuses a synthetic package', async () => {
  const run = mount();                       // no packageAdmission: the production default
  await run.offer(LUNAR);
  await assertRefused(run, /package is \d+ B; the pinned profile has 699956 B/);
  for (const file of ['installer-ota-flow.js', 'native-ota-controller.js']) {
    const source = await readFile(new URL(`../www/${file}`, import.meta.url), 'utf8');
    assert.match(source, /^import \{ verifyNativePackage \} from '\.\/lunar-package-admission\.js';$/m, file);
    assert.doesNotMatch(source, /native-package-admission\.js/, file);
  }
});

test('a full install sends only identity queries, 7F upgrades and data responses from the admitted image', async () => {
  const run = mount({ packageAdmission: { verify: realVerify } });
  const pairs = { running: run.access.addPair('running', 'FM-1_015') };
  await run.offer(LUNAR);
  const done = run.start().dispatch('click');
  const legends = { running: 'running FM-1', loader: 'OTA loader', application: 'new application' };
  const products = { loader: 'ota-FM-1_015', application: 'FM-1_501' };
  for (const phase of ['running', 'loader', 'application']) {
    await until(() => walk(run.root).some((node) => node.tagName === 'LEGEND'
      && node._textContent.includes(legends[phase])), `${phase} prompt`);
    if (!pairs[phase]) {
      pairs[phase] = run.access.addPair(phase, products[phase]);
      for (const listener of [...run.access.listeners]) listener({ port: pairs[phase].input });
    }
    const radio = walk(run.root).find((node) => node.type === 'radio' && node.getAttribute('data-input-id') === `${phase}-in`);
    radio.checked = true;
    await radio.dispatch('change');
    await walk(run.root).find((node) => node.tagName === 'BUTTON' && node._textContent === 'Use this pair').dispatch('click');
  }
  await done;
  assert.match(find(run.root, 'installer-ota-result').textContent, /Done: the unit reports FM-1_501\./);
  const image = logicalImage(LUNAR);
  let upgrades = 0;
  let responses = 0;
  const commands = [];
  for (const { bytes } of run.access.sent) {
    assert.equal(same(bytes, SOFT_KEY), false, 'the soft key is never sent');
    if (same(bytes, UPGRADE)) { upgrades += 1; commands.push('7F'); continue; }
    // Everything else is a 00 59 <cmd> frame (docs/03 §4). Decode it and check the
    // command byte: 0x11 (17) is the identity query, 0x30 (48) the read response.
    const body = unpack7(bytes.slice(1, -1));
    assert.ok(bytes[0] === 0xf0 && bytes.at(-1) === 0xf7 && body, 'a framed SysEx message');
    assert.notDeepEqual(body.slice(0, 3), [0x5a, 0xaa, 0xa5], 'no 5A AA A5 online-tool frame');
    assert.deepEqual(body.slice(0, 2), [0, 0x59]);
    commands.push(body[2]);
    if (same(bytes, HS_QUERY)) continue;
    assert.equal(body[2], 0x30, 'only syscmd 0x11 and 0x30 are sent; never 0x21-0x24');
    const addr = (body[7] | (body[8] << 8) | (body[9] << 16) | (body[10] << 24)) >>> 0;
    const length = body[11] | (body[12] << 8) | (body[13] << 16);
    const data = body.slice(14, 14 + length);
    if (addr === 0xe0000000 || addr === 0xf0000000) {
      assert.deepEqual(data, [...new TextEncoder().encode('success'), 0]);
    } else {
      assert.deepEqual(data, [...image.subarray(addr, addr + length)], 'served bytes come from the admitted image');
    }
    responses += 1;
  }
  // Each phase: identity (0x11), then 7F, and only then read responses (0x30).
  assert.deepEqual(commands, [0x11, '7F', 0x30, 0x30, 0x11, '7F', 0x30, 0x30, 0x11]);
  assert.equal(upgrades, 2, 'one 7F to the running app, one to the OTA loader');
  assert.equal(responses, 4);
});

test('a read request before the 7F upgrade is never answered', async () => {
  // A device that volunteers a read request with its identity reply, and has the
  // wrong identity: the flow stops after the identity query and answers nothing.
  const run = mount({ packageAdmission: { verify: realVerify } });
  const pair = run.access.addPair('running', 'FM-1_092');
  const send = pair.output.send;
  pair.output.send = (bytes) => { pair.input.onmidimessage?.({ data: request(0) }); send(bytes); };
  await run.offer(LUNAR);
  const done = run.start().dispatch('click');
  await until(() => walk(run.root).some((node) => node.tagName === 'LEGEND'), 'running prompt');
  const radio = walk(run.root).find((node) => node.type === 'radio' && node.getAttribute('data-input-id') === 'running-in');
  radio.checked = true;
  await radio.dispatch('change');
  await walk(run.root).find((node) => node.tagName === 'BUTTON' && node._textContent === 'Use this pair').dispatch('click');
  await done;
  await until(() => /Stopped/.test(find(run.root, 'installer-ota-result').textContent), 'stop');
  assert.ok(run.access.sent.length > 0);
  assert.ok(run.access.sent.every(({ bytes }) => same(bytes, HS_QUERY)), 'only identity queries were sent');
});

test('the adapter refuses to serve read requests on a session that has not sent 7F', async () => {
  const access = new FakeAccess();
  const adapter = createNativeOtaAdapter({ packageAdmission: { verify: realVerify } });
  const admission = await adapter.admitPackage(LUNAR, 'FM-1_501');
  const { input, output } = access.addPair('running', 'FM-1_015');
  const session = await adapter.connect({ admission, input, output, role: 'running' });
  input.onmidimessage?.({ data: request(0) });
  await assert.rejects(adapter.serve({ admission, session, stage: 'verify' }), /upgrade command must precede transfer/);
  assert.ok(access.sent.every(({ bytes }) => same(bytes, HS_QUERY)), 'only identity queries were sent');
  await adapter.close(session);
});
