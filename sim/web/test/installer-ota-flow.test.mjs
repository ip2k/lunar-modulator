// SPDX-License-Identifier: GPL-3.0-only
// Offline tests of the install and roll-back panel with fake Web MIDI ports.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Document, Element, walk } from './fake-dom.mjs';
import { FakeAccess, same } from './fake-midi.mjs';
import { HS_QUERY, UPGRADE } from '../www/third_party/fm1-ota/fm1ota.js';
import { mountOtaInstallFlow, guidanceFor, listPortPairs, STOCK_PRODUCT } from '../www/installer-ota-flow.js';
import { mountInstallerPage } from '../www/installer-page.js';
import { OTA_STAGES } from '../www/native-ota-controller.js';

const PACKAGE = Uint8Array.of(9, 8, 7);
const hex = (bytes) => [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, '0')).join('');

function verifierFor(version) {
  return async (bytes) => {
    assert.deepEqual(bytes, PACKAGE);
    const logicalImage = Uint8Array.of(1, 2, 3, 4);
    const digest = await crypto.subtle.digest('SHA-256', logicalImage);
    return { format: 'lunar-native-package-admission-v1', product: `FM-1_${version}`,
      model: 'FM-1', version: Number(version), logicalImage, logicalImageSha256: hex(digest) };
  };
}

const find = (root, id) => walk(root).find((node) => node.id === id);
const tick = () => new Promise((resolve) => setImmediate(resolve));
async function until(predicate, what) {
  for (let i = 0; i < 400; i += 1) { if (predicate()) return; await tick(); }
  assert.fail(`timed out waiting for ${what}`);
}
const pageText = (root) => walk(root).map((node) => node._textContent).join('');
const stageStates = (root) => Object.fromEntries(walk(root)
  .filter((node) => node.getAttribute?.('data-stage')).map((node) => [node.getAttribute('data-stage'), node.getAttribute('data-state')]));

function rig({ version = '501', running = 'FM-1_015', loader = 'ota-FM-1_015', application = 'FM-1_501',
  requestMIDIAccess, pairOptions = {} } = {}) {
  const document = new Document();
  const root = new Element('div', document);
  const access = new FakeAccess();
  const log = { accessCalls: 0, sleeps: [] };
  const clock = { now: () => performance.now(), setTimeout: (fn, ms) => setTimeout(fn, ms === 30000 ? 2 : ms),
    clearTimeout, async sleep(ms) { log.sleeps.push(ms); } };
  const pairs = { running: access.addPair('running', running, pairOptions.running) };
  const flow = mountOtaInstallFlow(root, {
    requestMIDIAccess: requestMIDIAccess === undefined ? async (options) => {
      assert.deepEqual(options, { sysex: true });
      log.accessCalls += 1;
      return access;
    } : requestMIDIAccess,
    packageAdmission: { verify: verifierFor(version) }, clock,
    transferTimeouts: { idleTimeoutMs: 30, hardTimeoutMs: 100, responseDelayMs: 0 },
  });
  // The re-enumerated devices show up only after the user is asked for them.
  const appear = {
    loader: () => { pairs.loader = access.addPair('loader', loader, pairOptions.loader); },
    application: () => { pairs.application = access.addPair('application', application, pairOptions.application); },
  };
  const legend = { running: 'running FM-1', loader: 'OTA loader', application: 'new application' };
  async function choose(phase) {
    await until(() => walk(root).some((node) => node.tagName === 'LEGEND'
      && node._textContent.includes(legend[phase])), `${phase} pair prompt`);
    if (appear[phase] && !pairs[phase]) {
      appear[phase]();
      for (const listener of [...access.listeners]) listener({ port: pairs[phase].input });
    }
    const radio = walk(root).find((node) => node.type === 'radio' && node.getAttribute('data-input-id') === `${phase}-in`);
    assert.ok(radio, `${phase} pair is offered`);
    radio.checked = true;
    await radio.dispatch('change');
    const use = walk(root).find((node) => node.tagName === 'BUTTON' && node._textContent === 'Use this pair');
    assert.equal(use.disabled, false);
    await use.dispatch('click');
  }
  const start = () => find(root, 'installer-ota-start');
  return { document, root, access, pairs, flow, log, choose, start };
}

const receive = (run) => run.flow.receivePackage({ file: { name: 'pkg.fwsc' }, bytes: PACKAGE });
async function runThrough(run, phases = ['running', 'loader', 'application']) {
  const done = run.start().dispatch('click');
  for (const phase of phases) await run.choose(phase);
  await done;
}

test('production verifier refuses an unadmitted package: no MIDI permission, disabled button', async () => {
  let accessCalls = 0;
  const document = new Document();
  const root = new Element('div', document);
  const flow = mountOtaInstallFlow(root, { requestMIDIAccess: async () => { accessCalls += 1; } });
  await flow.receivePackage({ file: { name: 'x.fwsc' }, bytes: Uint8Array.of(1, 2, 3) });
  assert.match(find(root, 'installer-ota-admission').textContent, /Not admitted: .*package admission blocked/);
  assert.match(find(root, 'installer-ota-admission').textContent, /Installation stays closed/);
  assert.equal(find(root, 'installer-ota-start').disabled, true);
  await find(root, 'installer-ota-start').dispatch('click');
  assert.equal(accessCalls, 0);
});

test('no Web MIDI in the browser: clear message, install stays disabled', async () => {
  const run = rig({ requestMIDIAccess: null });
  await receive(run);
  assert.equal(run.start().disabled, true);
  assert.match(find(run.root, 'installer-ota-admission').textContent, /no Web MIDI/);
});

test('full install: admission shown, every stage reported, fresh identity confirmed', async () => {
  const run = rig();
  assert.equal(run.start().disabled, true);
  await receive(run);
  assert.match(find(run.root, 'installer-ota-admission').textContent, /Admitted: FM-1_501\. Ready: nothing is sent/);
  assert.equal(run.start().disabled, false);
  assert.equal(run.access.sent.length, 0, 'nothing is sent before the click');
  assert.equal(run.log.accessCalls, 0, 'no MIDI permission before the click');
  await runThrough(run);
  assert.match(find(run.root, 'installer-ota-result').textContent, /Done: the unit reports FM-1_501\. Package SHA-256 [0-9a-f]{64}/);
  assert.equal(find(run.root, 'installer-ota-guidance').textContent, '');
  const states = stageStates(run.root);
  assert.deepEqual(Object.keys(states), OTA_STAGES);
  assert.ok(Object.values(states).every((state) => state === 'done'), JSON.stringify(states));
  assert.deepEqual(run.log.sleeps, [2000, 3000, 2000]);
  assert.deepEqual(run.access.sent.filter((sent) => same(sent.bytes, UPGRADE)).map((sent) => sent.phase), ['running', 'loader']);
  assert.equal(run.start().disabled, false, 'ready for another action afterwards');
  assert.equal(run.access.listeners.size, 0, 'no state-change listener is left behind');
});

test('roll back to the user’s own V15 package from a Lunar identity', async () => {
  const run = rig({ version: '015', running: 'FM-1_501', loader: 'ota-FM-1_501', application: 'FM-1_015' });
  await receive(run);
  find(run.root, 'installer-ota-mode').value = 'rollback';
  await find(run.root, 'installer-ota-mode').dispatch('change');
  assert.equal(run.start().textContent, 'Roll back');
  assert.equal(run.start().disabled, true, 'the running identity must be entered first');
  assert.match(find(run.root, 'installer-ota-admission').textContent, /enter the firmware the FM-1 is running now/);
  const running = find(run.root, 'installer-ota-running');
  running.value = 'FM-1_501';
  await running.dispatch('input');
  assert.equal(run.start().disabled, false);
  await runThrough(run);
  assert.match(find(run.root, 'installer-ota-result').textContent, /Done: the unit reports FM-1_015/);
});

test('mode mismatches are blocked before any MIDI access', async () => {
  const stock = rig({ version: '015' });
  await receive(stock);
  assert.equal(stock.start().disabled, true);
  assert.match(find(stock.root, 'installer-ota-admission').textContent, /use Roll back instead/);
  const lunar = rig();
  await receive(lunar);
  find(lunar.root, 'installer-ota-mode').value = 'rollback';
  await find(lunar.root, 'installer-ota-mode').dispatch('change');
  assert.equal(lunar.start().disabled, true);
  assert.match(find(lunar.root, 'installer-ota-admission').textContent, new RegExp(`needs your own ${STOCK_PRODUCT} package`));
  assert.equal(lunar.log.accessCalls + stock.log.accessCalls, 0);
});

test('wrong running identity never receives the upgrade command', async () => {
  const run = rig({ running: 'FM-1_099' });
  await receive(run);
  await runThrough(run, ['running']);
  assert.match(find(run.root, 'installer-ota-result').textContent, /Stopped: .*identity/);
  assert.match(find(run.root, 'installer-ota-guidance').textContent, /not what was expected/);
  assert.equal(run.access.sent.some((sent) => same(sent.bytes, UPGRADE)), false);
  assert.equal(stageStates(run.root)['running-identity'], 'failed');
});

test('wrong OTA loader identity stops before the write upgrade', async () => {
  const run = rig({ loader: 'ota-FM-2_015' });
  await receive(run);
  await runThrough(run, ['running', 'loader']);
  assert.match(find(run.root, 'installer-ota-result').textContent, /identity did not match ota-FM-1/);
  assert.equal(run.access.sent.some((sent) => sent.phase === 'loader' && same(sent.bytes, UPGRADE)), false);
  assert.equal(stageStates(run.root)['loader-identity'], 'failed');
});

test('interrupted transfer: a stalled device ends in guidance, not success', async () => {
  const run = rig({ pairOptions: { running: { stall: true } } });
  await receive(run);
  await runThrough(run, ['running']);
  assert.match(find(run.root, 'installer-ota-result').textContent, /verification transfer did not finish/);
  assert.match(find(run.root, 'installer-ota-guidance').textContent, /interrupted.*docs\/17/);
  assert.equal(stageStates(run.root)['verify-transfer'], 'failed');
  assert.equal(run.access.sent.some((sent) => sent.phase === 'loader'), false);
  assert.equal(run.start().disabled, false, 'the user can try again');
});

test('interrupted write: the loader stalls after the upgrade and nothing is reported as installed', async () => {
  const run = rig({ pairOptions: { loader: { stall: true } } });
  await receive(run);
  await runThrough(run, ['running', 'loader']);
  assert.match(find(run.root, 'installer-ota-result').textContent, /write transfer did not finish/);
  assert.equal(stageStates(run.root)['write-transfer'], 'failed');
  assert.equal(run.access.sent.some((sent) => sent.phase === 'application'), false);
});

test('port loss mid-transfer is a failure with reconnect guidance', async () => {
  const run = rig({ pairOptions: { running: { dropMidTransfer: true } } });
  await receive(run);
  await runThrough(run, ['running']);
  assert.match(find(run.root, 'installer-ota-result').textContent, /did not finish/);
  assert.match(find(run.root, 'installer-ota-guidance').textContent, /Replug USB/);
});

test('a finish ACK without re-enumeration points at replugging and the loader', async () => {
  const run = rig({ pairOptions: { running: { noDisconnect: true } } });
  await receive(run);
  await runThrough(run, ['running']);
  assert.match(find(run.root, 'installer-ota-result').textContent, /did not re-enumerate/);
  assert.match(find(run.root, 'installer-ota-guidance').textContent, /already in its OTA loader/);
});

test('post-write wrong application identity is reported, never as success', async () => {
  const run = rig({ application: 'FM-1_015' });
  await receive(run);
  await runThrough(run);
  assert.match(find(run.root, 'installer-ota-result').textContent, /post-write application identity/);
  assert.doesNotMatch(find(run.root, 'installer-ota-result').textContent, /^Done/);
  assert.equal(stageStates(run.root)['fresh-identity'], 'failed');
});

test('cancelling at port selection sends nothing and re-enables the controls', async () => {
  const run = rig();
  await receive(run);
  const done = run.start().dispatch('click');
  await until(() => walk(run.root).some((node) => node.tagName === 'LEGEND'), 'pair prompt');
  const cancel = find(run.root, 'installer-ota-cancel');
  assert.equal(cancel.disabled, false);
  await cancel.dispatch('click');
  await done;
  assert.match(find(run.root, 'installer-ota-result').textContent, /port selection cancelled/);
  assert.match(find(run.root, 'installer-ota-guidance').textContent, /Stopped before anything was sent/);
  assert.equal(run.access.sent.length, 0);
  assert.equal(run.access.opens, 0);
  assert.equal(run.start().disabled, false);
  assert.equal(cancel.disabled, true);
  assert.equal(walk(run.root).some((node) => node.tagName === 'LEGEND'), false);
});

test('unrelated devices are excluded from port selection; others only on request', async () => {
  const run = rig();
  run.access.addPair('decoy1', 'IAC', { id: 'iac', name: 'IAC Driver Bus 1' });
  run.access.addPair('decoy2', 'KA6', { id: 'ka6', name: 'Komplete Audio 6 MIDI' });
  run.access.addPair('decoy3', 'syn', { id: 'syn', name: 'Some Synth' });
  const listing = listPortPairs(run.access);
  assert.deepEqual(listing.likely.map((pair) => pair.input.id), ['running-in']);
  assert.deepEqual(listing.other.map((pair) => pair.input.id), ['syn-in']);
  assert.equal(listing.hidden, 2);
  await receive(run);
  const done = run.start().dispatch('click');
  await until(() => walk(run.root).some((node) => node.type === 'radio'), 'pair list');
  const ids = () => walk(run.root).filter((node) => node.type === 'radio').map((node) => node.getAttribute('data-input-id'));
  assert.deepEqual(ids(), ['running-in']);
  assert.match(pageText(run.root), /2 unrelated MIDI ports/);
  const toggle = walk(run.root).find((node) => node.type === 'checkbox' && node.getAttribute('aria-label') === 'Show other MIDI devices');
  toggle.checked = true;
  await toggle.dispatch('change');
  assert.deepEqual(ids(), ['running-in', 'syn-in']);
  await find(run.root, 'installer-ota-cancel').dispatch('click');
  await done;
  assert.equal(run.access.sent.length, 0, 'nothing is ever sent to decoy or unchosen ports');
});

test('two same-named devices are ambiguous and cannot be selected', async () => {
  const run = rig();
  run.access.addPair('loader', 'ota-FM-1_015');
  const listing = listPortPairs(run.access);
  assert.equal(listing.likely.length, 0);
  assert.deepEqual(listing.ambiguous, ['USB Composite Device']);
  await receive(run);
  const done = run.start().dispatch('click');
  await until(() => walk(run.root).some((node) => node.tagName === 'LEGEND'), 'pair prompt');
  assert.equal(walk(run.root).some((node) => node.type === 'radio'), false);
  assert.match(pageText(run.root), /cannot be paired safely/);
  await find(run.root, 'installer-ota-cancel').dispatch('click');
  await done;
  assert.equal(run.access.sent.length, 0);
});

test('a chosen pair that disconnects before confirmation cannot be used', async () => {
  const run = rig();
  await receive(run);
  const done = run.start().dispatch('click');
  await until(() => walk(run.root).some((node) => node.type === 'radio'), 'pair list');
  const radio = walk(run.root).find((node) => node.type === 'radio');
  radio.checked = true;
  await radio.dispatch('change');
  run.pairs.running.input.state = 'disconnected';
  run.pairs.running.output.state = 'disconnected';
  const use = walk(run.root).find((node) => node._textContent === 'Use this pair');
  await use.dispatch('click');
  assert.match(pageText(run.root), /Waiting for a matching device/);
  await find(run.root, 'installer-ota-cancel').dispatch('click');
  await done;
  assert.equal(run.access.sent.length, 0);
});

test('resume from the OTA loader skips the running-application stages', async () => {
  const run = rig();
  await receive(run);
  find(run.root, 'installer-ota-resume').checked = true;
  // The unit is in its OTA loader: the running application's ports are gone.
  run.pairs.running.input.state = 'disconnected';
  run.pairs.running.output.state = 'disconnected';
  const done = run.start().dispatch('click');
  await run.choose('loader');
  await run.choose('application');
  await done;
  assert.match(find(run.root, 'installer-ota-result').textContent, /^Done: the unit reports FM-1_501/);
  const states = stageStates(run.root);
  assert.equal(states['select-running'], 'skipped');
  assert.equal(states['write-transfer'], 'done');
  assert.equal(run.access.sent.some((sent) => sent.phase === 'running' && same(sent.bytes, HS_QUERY)), false);
});

test('clearing the package disables the action', async () => {
  const run = rig();
  await receive(run);
  assert.equal(run.start().disabled, false);
  await run.flow.receivePackage(null);
  assert.equal(run.start().disabled, true);
  assert.equal(find(run.root, 'installer-ota-admission').textContent, 'No package selected.');
});

test('failure guidance maps each controller message to a next step', () => {
  const cases = [
    ['package admission blocked (unknown)', /Nothing was sent/],
    ['SysEx permission is required', /Allow MIDI access/],
    ['select an available input/output pair from this MIDI access session', /no longer available/],
    ['the selected MIDI device did not re-enumerate', /unplug and replug/],
    ['write transfer did not finish with an acknowledged device request', /interrupted/],
    ['OTA loader identity does not match', /not what was expected/],
    ['something odd', /docs\/17/],
  ];
  for (const [message, pattern] of cases) assert.match(guidanceFor(new Error(message)), pattern);
  assert.match(guidanceFor(new Error('port selection cancelled'), 'select-loader'), /OTA loader/);
});

test('the page hands an inspected file to the install flow, even when the catalogue is missing', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const flowRoot = new Element('div', document);
  const packageRoot = new Element('div', document);
  document.nodes.set('installer-ota-flow', flowRoot);
  document.nodes.set('installer-package-inspection', packageRoot);
  const loading = new Element('p', document);
  document.nodes.set('installer-load-status', loading);
  let accessCalls = 0;
  const controller = await mountInstallerPage(root, {
    fetchImpl: async () => ({ ok: false }),
    otaOptions: { requestMIDIAccess: async () => { accessCalls += 1; } },
  });
  assert.equal(controller, null, 'the catalogue failure is reported as before');
  assert.match(loading.textContent, /catalogue is unavailable/);
  assert.equal(find(flowRoot, 'installer-ota-start').disabled, true);
  const input = walk(packageRoot).find((node) => node.type === 'file');
  const bytes = Uint8Array.of(1, 2, 3, 4);
  input.files = [{ name: 'x.fwsc', size: bytes.length, arrayBuffer: async () => bytes.buffer }];
  await input.dispatch('change');
  await until(() => /Not admitted/.test(find(flowRoot, 'installer-ota-admission').textContent), 'admission result');
  assert.equal(find(flowRoot, 'installer-ota-start').disabled, true);
  assert.equal(accessCalls, 0);
});
