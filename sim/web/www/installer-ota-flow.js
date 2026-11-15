// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Lunar Modulator contributors
//
// Install and roll-back panel for the stock FM-1 OTA path. It imports the
// GPL-3.0-only controller, so this file is GPL-3.0-only too; see the licence
// note in installer.html. It never opens Web MIDI by itself: access is
// requested by the install click, after package admission, and every port
// pair is an explicit user choice.
//
// Admission is lunar-package-admission.js (MIT), the same rules as
// tools/jieli/build_fwsc.py: only the user's own stock V15 package byte for
// byte (roll back), or that package with only the application replaced by a
// Lunar FM-1_5xx app (install), every other byte (SPL, isd_config, ota.bin,
// cfg, flash head [0, 0x4000)) equal to stock. A package is admitted only if
// that check resolves to a well-formed record bound to these exact bytes;
// a missing verifier, a throwing or rejecting one, or a malformed record
// refuses the package, and the install button stays disabled. The click
// re-runs the same check before any MIDI permission is asked for.
import { verifyNativePackage } from './lunar-package-admission.js';
import { createNativeOtaController } from './native-ota-controller.js';

export const STOCK_PRODUCT = 'FM-1_015';
const PRODUCT_RE = /^FM-1_\d{3}$/;
const LUNAR_PRODUCT_RE = /^FM-1_5\d{2}$/;
const ADMISSION_FORMAT = 'lunar-native-package-admission-v1';

async function sha256Hex(bytes) {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new Error('Web Crypto SHA-256 is required to bind admission to the package');
  const digest = new Uint8Array(await subtle.digest('SHA-256', bytes));
  return [...digest].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Run `packageAdmission.verify` on a copy of `bytes` and return its record
 * once checked, or throw. Fails closed: anything but a well-formed record for
 * these exact bytes (kind and identity consistent, logical image and its
 * digest present, package digest equal to the bytes') is a refusal.
 */
export async function verifiedAdmission(packageAdmission, bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length === 0) {
    throw new TypeError('package admission blocked: no package bytes');
  }
  const verify = packageAdmission?.verify;
  if (typeof verify !== 'function') {
    throw new TypeError('package admission blocked: no admission verifier is available');
  }
  const snapshot = Uint8Array.from(bytes);
  const record = await verify.call(packageAdmission, Uint8Array.from(snapshot));
  if (!record || typeof record !== 'object' || record.format !== ADMISSION_FORMAT
      || typeof record.product !== 'string' || !PRODUCT_RE.test(record.product)
      || !(record.logicalImage instanceof Uint8Array) || record.logicalImage.length === 0
      || typeof record.logicalImageSha256 !== 'string' || typeof record.packageSha256 !== 'string') {
    throw new TypeError('package admission blocked: the verifier returned an invalid admission record');
  }
  if (!((record.kind === 'stock-rollback' && record.product === STOCK_PRODUCT)
      || (record.kind === 'lunar-install' && LUNAR_PRODUCT_RE.test(record.product)))) {
    throw new TypeError('package admission blocked: the verifier returned an invalid admission record (kind and identity disagree)');
  }
  if (record.packageSha256.toLowerCase() !== await sha256Hex(snapshot)) {
    throw new Error('package admission blocked: the admission record is for different bytes');
  }
  return record;
}

// Ports which are never the FM-1, whatever the user picks (the handshake still
// checks the identity afterwards; this only keeps the list honest).
const UNRELATED_PORT_RE = /IAC|Midi Through|Bluetooth|Network|Session|Komplete|Native Instruments|loopMIDI|Virtual|Audio ?6/i;
// Names an FM-1 is reported to use; others stay hidden unless asked for.
const LIKELY_PORT_RE = /FM-?1|M-?VAVE|USB Composite|USB[- ]?MIDI|ota-/i;

const STAGE_LABELS = Object.freeze({
  admission: 'Package admission re-checked',
  'midi-access': 'Web MIDI access with SysEx granted',
  'select-running': 'Running FM-1 port pair chosen',
  'running-identity': 'Running identity read and matched',
  'upgrade-verify': 'Upgrade command (7F) sent, then 2 s updater pause',
  'verify-transfer': 'Verification transfer served (finish E0000000)',
  're-enumerate-loader': 'Unit re-enumerated into its OTA loader',
  'select-loader': 'OTA loader port pair chosen',
  'loader-identity': 'OTA loader identity read and matched (ota-FM-1_nnn)',
  'upgrade-write': 'Upgrade command (7F) sent to the loader, then 2 s pause',
  'write-transfer': 'Write transfer served (finish F0000000)',
  're-enumerate-application': 'Unit re-enumerated after the write',
  'select-application': 'New application port pair chosen',
  'fresh-identity': 'Fresh application identity read and matched',
});
const RESUME_SKIPPED = new Set(['select-running', 'running-identity', 'upgrade-verify',
  'verify-transfer', 're-enumerate-loader']);

const PHASE_HELP = Object.freeze({
  running: 'Choose the FM-1 you are updating (the running application).',
  loader: 'The unit restarts into its OTA loader, which shows up as a new MIDI device. Wait for it to appear, then choose it. If it does not appear, unplug and replug the USB cable.',
  application: 'The unit restarts into the new application, which shows up as a new MIDI device. Wait for it to appear, then choose it.',
});

/** Next steps for a failure, from the controller's own messages. */
export function guidanceFor(error, lastStage) {
  const message = error instanceof Error ? error.message : String(error ?? '');
  if (/package admission blocked|invalid admission|verifier/i.test(message)) {
    return 'Nothing was sent to the FM-1. This package has not passed release admission, so it cannot be installed.';
  }
  if (lastStage === 'admission') {
    return 'The admission check could not complete, so nothing was sent to the FM-1. Choose the package again and retry.';
  }
  if (/cancelled/i.test(message)) {
    return lastStage && !/^(admission|midi-access|select-running)$/.test(lastStage)
      ? 'You stopped part-way. The unit may be in its OTA loader. Replug USB, tick "My FM-1 is already in its OTA loader" and run again, or follow docs/17 to recover.'
      : 'Stopped before anything was sent to the FM-1.';
  }
  if (/SysEx permission|requestMIDIAccess|Web MIDI/i.test(message)) {
    return 'Allow MIDI access with SysEx when the browser asks, then try again. Nothing was sent to the FM-1.';
  }
  if (/select an available/i.test(message)) {
    return 'That port pair is no longer available. Reconnect the FM-1 and choose a pair again.';
  }
  if (/did not re-enumerate/i.test(message)) {
    return 'The FM-1 did not restart as expected. Wait a minute, unplug and replug USB, then tick "My FM-1 is already in its OTA loader" if it shows up as ota-FM-1_nnn, and run again. Do not power the unit off during a write.';
  }
  if (/transfer did not finish/i.test(message)) {
    return 'The transfer was interrupted (cable, port or timeout). Do not power off. Replug USB and run the install again, ticking "already in its OTA loader" if the unit now shows up that way. If it does not return to normal operation, follow docs/17 (recovery).';
  }
  if (/identity/i.test(message)) {
    return 'The device that answered is not what was expected, so the flow stopped before sending the next command. Check that you chose the FM-1 pair, that the "running now" identity is right, and try again.';
  }
  return 'The install stopped. Replug USB, check the stage list above for the last step that completed, and try again. If the unit does not return to normal operation, follow docs/17 (recovery).';
}

/**
 * Connected input/output pairs, split into likely and other. A pair is offered
 * only when exactly one connected input and one connected output carry the same
 * name: with two same-named devices attached the match would be a guess, so the
 * name is reported as ambiguous instead and nothing under it can be selected.
 */
export function listPortPairs(access) {
  const names = new Map();
  const note = (port, side) => {
    if (port.state !== 'connected') return;
    const entry = names.get(port.name) ?? { inputs: [], outputs: [] };
    entry[side].push(port);
    names.set(port.name, entry);
  };
  for (const input of access?.inputs?.values?.() ?? []) note(input, 'inputs');
  for (const output of access?.outputs?.values?.() ?? []) note(output, 'outputs');
  const likely = [];
  const other = [];
  const ambiguous = [];
  let hidden = 0;
  for (const [name, { inputs, outputs }] of names) {
    if (!inputs.length || !outputs.length) continue;
    if (UNRELATED_PORT_RE.test(name ?? '')) { hidden += 1; continue; }
    if (inputs.length !== 1 || outputs.length !== 1) { ambiguous.push(name); continue; }
    (LIKELY_PORT_RE.test(name ?? '') ? likely : other).push({ input: inputs[0], output: outputs[0] });
  }
  return { likely, other, hidden, ambiguous };
}

export function mountOtaInstallFlow(root, {
  requestMIDIAccess = globalThis.navigator?.requestMIDIAccess?.bind(globalThis.navigator) ?? null,
  packageAdmission = { verify: verifyNativePackage },
  clock,
  transferTimeouts,
} = {}) {
  if (!root?.ownerDocument || typeof root.append !== 'function') {
    throw new TypeError('A DOM root element is required');
  }
  const document = root.ownerDocument;
  const el = (tag, props = {}, ...kids) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) node[key] = value;
    node.append(...kids);
    return node;
  };

  const section = el('section', { className: 'installer-ota-flow' });
  section.setAttribute('aria-labelledby', 'installer-ota-heading');
  const heading = el('h2', { id: 'installer-ota-heading', textContent: 'Install or roll back on an FM-1' });
  const intro = el('p', { textContent: 'This uses the FM-1’s stock update path over Web MIDI. Choose a package above; it is checked for release admission before anything else happens. Only two kinds of package are admitted: your own stock V15 package (FM-1_015) byte for byte, to roll back, and that same package with only the application replaced by a Lunar build (FM-1_5xx), to install. Everything else is refused and the button stays disabled. No Lunar package has yet been installed on an FM-1 this way: it is untested on hardware.' });

  const modeLabel = el('label', { textContent: 'Action ' });
  const modeSelect = el('select', { id: 'installer-ota-mode' });
  modeSelect.setAttribute('aria-label', 'Action');
  const installOption = el('option', { value: 'install', textContent: 'Install an admitted package' });
  const rollbackOption = el('option', { value: 'rollback', textContent: `Roll back to my own stock package (${STOCK_PRODUCT})` });
  modeSelect.append(installOption, rollbackOption);
  modeSelect.value = 'install';
  modeLabel.append(modeSelect);

  const runningLabel = el('label', { textContent: 'Firmware the FM-1 is running now ' });
  const runningInput = el('input', { id: 'installer-ota-running', type: 'text', value: STOCK_PRODUCT });
  runningInput.setAttribute('aria-label', 'Firmware the FM-1 is running now');
  runningInput.setAttribute('placeholder', 'FM-1_nnn');
  runningInput.disabled = true;
  runningLabel.append(runningInput);

  const resumeLabel = el('label', { textContent: 'My FM-1 is already in its OTA loader (resume an interrupted install) ' });
  const resumeBox = el('input', { id: 'installer-ota-resume', type: 'checkbox' });
  resumeBox.setAttribute('aria-label', 'My FM-1 is already in its OTA loader');
  resumeLabel.append(resumeBox);

  const admission = el('p', { id: 'installer-ota-admission', textContent: 'No package selected.' });
  admission.setAttribute('role', 'status');
  admission.setAttribute('aria-live', 'polite');

  const actions = el('div', { className: 'installer-ota-actions' });
  const startButton = el('button', { id: 'installer-ota-start', type: 'button', textContent: 'Install' });
  startButton.disabled = true;
  const cancelButton = el('button', { id: 'installer-ota-cancel', type: 'button', textContent: 'Cancel' });
  cancelButton.disabled = true;
  actions.append(startButton, cancelButton);

  const pairs = el('div', { className: 'installer-ota-pairs' });
  pairs.setAttribute('aria-live', 'polite');
  const stageList = el('ol', { className: 'installer-ota-stages' });
  stageList.setAttribute('aria-label', 'Update stages');
  const stageItems = new Map();
  const result = el('p', { id: 'installer-ota-result', textContent: '' });
  result.setAttribute('role', 'status');
  result.setAttribute('aria-live', 'polite');
  const guidance = el('p', { id: 'installer-ota-guidance', className: 'installer-ota-guidance', textContent: '' });
  guidance.setAttribute('role', 'alert');

  section.append(heading, intro, modeLabel, runningLabel, resumeLabel, admission, actions,
    pairs, stageList, result, guidance);
  root.append(section);

  let pkg = null; // { name, bytes, product, admitted, reason }
  let running = false;
  let destroyed = false;
  let generation = 0;
  let cancelPairSelection = null;
  let lastStage = null;

  function resetStages(resume = false) {
    stageList.textContent = '';
    stageItems.clear();
    for (const [name, label] of Object.entries(STAGE_LABELS)) {
      const item = el('li', { textContent: label });
      const skipped = resume && RESUME_SKIPPED.has(name);
      item.setAttribute('data-stage', name);
      item.setAttribute('data-state', skipped ? 'skipped' : 'pending');
      if (skipped) item.textContent = `${label} (skipped: resuming from the loader)`;
      stageItems.set(name, item);
      stageList.append(item);
    }
  }
  resetStages();

  function setStage(name, { state, ...detail } = {}) {
    const item = stageItems.get(name);
    if (!item) return;
    const base = STAGE_LABELS[name];
    if (state === 'start') { item.setAttribute('data-state', 'active'); lastStage = name; }
    else if (state === 'done') item.setAttribute('data-state', 'done');
    else if (state === 'progress') {
      item.textContent = `${base} – ${detail.served} request${detail.served === 1 ? '' : 's'} served`;
    }
  }

  function targetFor(mode) {
    return mode === 'rollback' ? STOCK_PRODUCT : pkg?.product ?? null;
  }

  function refresh() {
    const mode = modeSelect.value;
    runningInput.disabled = mode !== 'rollback' || running;
    if (mode !== 'rollback') runningInput.value = STOCK_PRODUCT;
    startButton.textContent = mode === 'rollback' ? 'Roll back' : 'Install';
    modeSelect.disabled = running;
    resumeBox.disabled = running;
    cancelButton.disabled = cancelPairSelection === null;
    if (running) { startButton.disabled = true; return; }
    const reason = blockReason(mode);
    startButton.disabled = reason !== null;
    if (pkg?.admitted) {
      admission.textContent = reason === null
        ? `Admitted: ${pkg.product}. Ready: nothing is sent until you press ${startButton.textContent}.`
        : `Admitted: ${pkg.product}, but ${reason}`;
    }
  }

  function blockReason(mode) {
    if (!pkg) return 'no package is selected.';
    if (!pkg.admitted) return 'the package was not admitted.';
    if (typeof requestMIDIAccess !== 'function') return 'this browser has no Web MIDI.';
    if (mode === 'rollback') {
      if (pkg.product !== STOCK_PRODUCT || pkg.kind !== 'stock-rollback') {
        return `a roll back needs your own ${STOCK_PRODUCT} package, not ${pkg.product}.`;
      }
      if (!PRODUCT_RE.test(runningInput.value) || runningInput.value === STOCK_PRODUCT) {
        return `enter the firmware the FM-1 is running now (FM-1_nnn, not ${STOCK_PRODUCT}).`;
      }
    } else if (pkg.product === STOCK_PRODUCT) {
      return `this is the stock ${STOCK_PRODUCT} package; use Roll back instead.`;
    } else if (pkg.kind !== 'lunar-install') {
      return 'only a Lunar install package can be installed.';
    }
    return null;
  }

  async function receivePackage(next) {
    const mine = ++generation;
    guidance.textContent = '';
    result.textContent = '';
    if (!next) {
      pkg = null;
      admission.textContent = 'No package selected.';
      refresh();
      return;
    }
    pkg = { name: next.file?.name ?? 'selected package', bytes: Uint8Array.from(next.bytes),
      product: null, kind: null, admitted: false };
    admission.textContent = 'Checking release admission…';
    refresh();
    try {
      const admitted = await verifiedAdmission(packageAdmission, pkg.bytes);
      if (mine !== generation || destroyed) return;
      pkg.product = admitted.product;
      pkg.kind = admitted.kind;
      pkg.admitted = true;
    } catch (error) {
      if (mine !== generation || destroyed) return;
      pkg.admitted = false;
      admission.textContent = `Not admitted: ${error instanceof Error ? error.message : 'unknown reason'}. Installation stays closed.`;
    }
    refresh();
  }

  // ---- explicit port-pair selection -------------------------------------
  function selectPair({ phase, access }) {
    return new Promise((resolve, reject) => {
      let chosen = null;
      let done = false;
      const finish = (fn, value) => {
        if (done) return;
        done = true;
        cancelPairSelection = null;
        cancelButton.disabled = true;
        access.removeEventListener?.('statechange', render);
        pairs.textContent = '';
        fn(value);
      };
      cancelPairSelection = () => finish(reject, new Error('port selection cancelled'));
      cancelButton.disabled = false;
      function render() {
        if (done) return;
        pairs.textContent = '';
        const { likely, other, hidden, ambiguous } = listPortPairs(access);
        const box = el('fieldset', { className: 'installer-ota-pairset' });
        box.append(el('legend', { textContent: `Port pair for the ${phase === 'running' ? 'running FM-1'
          : phase === 'loader' ? 'OTA loader' : 'new application'}` }));
        box.append(el('p', { textContent: PHASE_HELP[phase] }));
        const showOther = el('input', { type: 'checkbox', checked: render.showOther === true });
        showOther.setAttribute('aria-label', 'Show other MIDI devices');
        const radios = [];
        const addPair = (pair) => {
          const radio = el('input', { type: 'radio', name: 'installer-ota-pair' });
          radio.setAttribute('data-input-id', pair.input.id);
          radio.checked = chosen?.input === pair.input && chosen?.output === pair.output;
          radio.addEventListener('change', () => {
            if (radio.checked) { chosen = pair; useButton.disabled = false; }
          });
          radios.push(radio);
          box.append(el('label', {}, radio, ` ${pair.input.name} (${pair.input.id})`));
        };
        likely.forEach(addPair);
        if (render.showOther) other.forEach(addPair);
        if (!likely.length && !(render.showOther && other.length)) {
          box.append(el('p', { className: 'installer-ota-waiting',
            textContent: 'Waiting for a matching device…' }));
        }
        if (chosen && !radios.some((radio) => radio.checked)) chosen = null;
        const useButton = el('button', { type: 'button', textContent: 'Use this pair' });
        useButton.disabled = chosen === null;
        useButton.addEventListener('click', () => {
          if (chosen && chosen.input.state === 'connected' && chosen.output.state === 'connected') {
            finish(resolve, chosen);
          } else { chosen = null; render(); }
        });
        showOther.addEventListener('change', () => { render.showOther = showOther.checked; render(); });
        box.append(useButton, el('label', {}, showOther, ' Show other MIDI devices'));
        if (ambiguous.length) box.append(el('p', { className: 'installer-ota-ambiguous',
          textContent: `More than one connected device is named ${ambiguous.map((n) => `\u201c${n}\u201d`).join(', ')}, so its ports cannot be paired safely. Unplug the other devices with that name and wait.` }));
        if (hidden) box.append(el('p', { textContent: `${hidden} unrelated MIDI port${hidden === 1 ? '' : 's'} (virtual, audio-interface or network) hidden.` }));
        pairs.append(box);
      }
      access.addEventListener?.('statechange', render);
      render();
    });
  }

  async function start() {
    if (running || destroyed) return;
    const mode = modeSelect.value;
    if (blockReason(mode) !== null) return;
    running = true;
    const resume = resumeBox.checked;
    guidance.textContent = '';
    result.textContent = '';
    resetStages(resume);
    lastStage = null;
    refresh();
    const chosen = pkg; // the package admitted when the click happened
    const expectedProduct = targetFor(mode);
    const runningProduct = runningInput.value;
    try {
      const controller = createNativeOtaController({
        // The click re-runs the same checks; the kind must still be the one shown.
        packageAdmission: { async verify(bytes) {
          const record = await verifiedAdmission(packageAdmission, bytes);
          if (record.kind !== chosen.kind || record.product !== chosen.product) {
            throw new Error('package admission blocked: the package no longer matches its earlier admission');
          }
          return record;
        } },
        requestMIDIAccess, selectPair,
        ...(clock ? { clock } : {}), ...(transferTimeouts ? { transferTimeouts } : {}),
        onStage: setStage,
      });
      const outcome = await controller.installFromUserAction({
        packageBytes: Uint8Array.from(chosen.bytes), expectedProduct,
        runningProduct, startPhase: resume ? 'loader' : 'running',
      });
      result.textContent = `Done: the unit reports ${outcome.product}. Package SHA-256 ${outcome.packageSha256}.`;
    } catch (error) {
      const active = lastStage && stageItems.get(lastStage);
      if (active && active.getAttribute('data-state') === 'active') active.setAttribute('data-state', 'failed');
      result.textContent = `Stopped: ${error instanceof Error ? error.message : 'unknown error'}.`;
      guidance.textContent = guidanceFor(error, lastStage);
    } finally {
      cancelPairSelection?.();
      running = false;
      if (!destroyed) refresh();
    }
  }

  startButton.addEventListener('click', () => start());
  cancelButton.addEventListener('click', () => cancelPairSelection?.());
  modeSelect.addEventListener('change', refresh);
  runningInput.addEventListener('input', refresh);
  runningInput.addEventListener('change', refresh);
  if (typeof requestMIDIAccess !== 'function') {
    result.textContent = 'This browser does not provide Web MIDI. Use a Chromium-based browser to install.';
  }
  refresh();

  return Object.freeze({
    receivePackage,
    destroy() { destroyed = true; generation++; cancelPairSelection?.(); section.remove(); },
  });
}
