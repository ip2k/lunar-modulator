// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mountNativeDemoSelectionView } from '../www/native-demo-selection-view.js';

class Element {
  constructor(tag, ownerDocument) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this._textContent = '';
    this.disabled = false;
    this.checked = false;
  }
  append(...children) { this.children.push(...children); }
  get textContent() { return this._textContent + this.children.map((child) => child.textContent).join(''); }
  set textContent(value) { this._textContent = String(value); this.children = []; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(callback);
  }
  dispatch(name) { return Promise.all((this.listeners.get(name) || []).map((fn) => fn({ target: this }))); }
  remove() { this.removed = true; }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
}

class Document {
  createElement(tag) { return new Element(tag, this); }
}

const project = (id, title, seconds, category = 'legacy-example') => ({
  id, title, category,
  duration_estimate: { nominal_seconds: seconds },
  owner_disposition: id === 'replacement-showcase-candidate-event-horizon'
    ? 'owner-approved musical full-song default; native playback and release admission pending'
    : 'legacy example; not approved as a showcase or default',
  default_candidate: false,
  source_path: `private/${id}.lunar`, source_sha256: 'a'.repeat(64),
  source_dependency_scan_complete: true,
  source_module_dependencies: { engines: ['macro'], effects: [], midi: [], modulation: [] },
});
const catalogue = {
  version: 1,
  groups: { engines: ['macro'], effects: ['plate'], midi: ['arp'], modulation: ['lfo'] },
  projects: [
    project('legacy-example-event-horizon', '<img src=x onerror=alert(1)>', 193.33),
    project('replacement-showcase-candidate-event-horizon', 'Event Horizon', 108.8,
      'replacement-showcase-candidate'),
    project('replacement-showcase-candidate-afterglow-relay', 'Afterglow Relay', 198,
      'replacement-showcase-candidate'),
    project('replacement-showcase-candidate-packet-bloom', 'Packet Bloom', 117,
      'replacement-showcase-candidate'),
    project('replacement-showcase-candidate-satellite-hearts', 'Satellite Hearts', 145,
      'replacement-showcase-candidate'),
  ],
  full_song_default: { required: true, status: 'owner-approved', project_id: 'replacement-showcase-candidate-event-horizon', musical_choice_approved: true, blockers: ['Exact packed-content and module-dependency validation', 'Native playback and save/reload'] },
};
const profile = { version: 1, engines: ['macro'], effects: [], midi: [], modulation: [] };

function walk(root) {
  return [root, ...root.children.flatMap(walk)];
}

test('preselects the owner-approved musical default reversibly and submits ordered selection', () => {
  const document = new Document();
  const root = new Element('div', document);
  const sent = [];
  const controller = mountNativeDemoSelectionView(root, catalogue, profile, (request) => sent.push(request));
  const nodes = walk(root);
  const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
  const radios = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'radio');
  const submit = nodes.find((node) => node.tagName === 'BUTTON');
  const textNodes = nodes.map((node) => node.textContent).join('\n');

  assert.equal(checkboxes.length, 5);
  assert.equal(radios.length, 5);
  assert.ok(nodes.some((node) => node.tagName === 'SPAN' &&
    node.textContent === 'Event Horizon Showcase (Showcase candidate)'));
  assert.equal(checkboxes[0].checked, false);
  assert.equal(checkboxes[1].checked, true);
  assert.equal(checkboxes[2].disabled, false);
  assert.equal(checkboxes[3].disabled, true);
  assert.equal(checkboxes[4].disabled, true);
  assert.match(textNodes, /The recorded playback-memory check passed; device playback remains unverified/);
  assert.match(textNodes, /This arrangement exceeds available playback memory/);
  assert.match(textNodes, /Unavailable with the current voice count/);
  assert.equal(radios[0].disabled, true);
  assert.equal(radios[1].disabled, false);
  assert.equal(radios[1].checked, true);
  assert.equal(submit.disabled, false);
  assert.match(textNodes, /Full-song default status: owner-approved/);
  assert.match(textNodes, /owner-approved musical full-song default/);
  assert.match(textNodes, /preselected here/);
  assert.match(textNodes, /approval covers the song choice only/);
  assert.match(textNodes, /108\.8-second host render is an offline diagnostic only/);
  assert.match(textNodes, /module-dependency validation, native playback, and save\/reload acceptance remain pending/);
  assert.match(textNodes, /Estimated duration 1:49/);
  assert.match(textNodes, /metadata, not verified playback lengths/);
  assert.match(textNodes, /Host startup diagnostic refused allocation \(report 5\)/);
  assert.match(textNodes, /<img src=x onerror=alert\(1\)>/);
  assert.equal(nodes.some((node) => node.tagName === 'IMG'), false);
  assert.equal(nodes.some((node) => 'innerHTML' in node && node.innerHTML), false);

  // The proposed default is an ordinary selected project; callers can change it.
  checkboxes[0].checked = true;
  checkboxes[0].dispatch('change');
  radios[0].checked = true;
  radios[0].dispatch('change');
  assert.equal(submit.disabled, false);
  submit.dispatch('click');

  assert.equal(sent.length, 1);
  assert.deepEqual(Object.keys(sent[0]), [
    'version', 'engines', 'effects', 'midi', 'modulation', 'project_ids', 'startup_index',
  ]);
  assert.deepEqual(sent[0].project_ids, [
    'replacement-showcase-candidate-event-horizon', 'legacy-example-event-horizon',
  ]);
  assert.equal(sent[0].startup_index, 1);
  assert.equal('source_path' in sent[0], false);
  assert.equal('source_sha256' in sent[0], false);
  assert.deepEqual(controller.getSelection(), {
    projectIds: ['replacement-showcase-candidate-event-horizon', 'legacy-example-event-horizon'],
    startupId: 'legacy-example-event-horizon', setIds: [],
  });

  checkboxes[0].checked = false;
  checkboxes[0].dispatch('change');
  assert.equal(radios[0].disabled, true);
  assert.equal(radios[0].checked, false);
  assert.equal(submit.disabled, true);
  assert.deepEqual(controller.getSelection(), {
    projectIds: ['replacement-showcase-candidate-event-horizon'], startupId: null, setIds: [],
  });
  controller.destroy();
  assert.equal(root.children[0].removed, true);
});

test('blocks rejected candidates in controls, event handlers, and request preflight', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const sent = [];
  mountNativeDemoSelectionView(root, catalogue, profile, (request) => sent.push(request));
  const nodes = walk(root);
  const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
  const status = nodes.find((node) => node.getAttribute('aria-live') === 'polite');
  const submit = nodes.find((node) => node.tagName === 'BUTTON');

  assert.equal(checkboxes[3].disabled, true);
  assert.equal(checkboxes[4].disabled, true);
  checkboxes[3].checked = true;
  await checkboxes[3].dispatch('change');
  assert.equal(checkboxes[3].checked, false);
  assert.match(status.textContent, /exceeds available playback memory/);
  assert.equal(submit.disabled, false); // Proposed EH remains selected/startup.
  await submit.dispatch('click');
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].project_ids, ['replacement-showcase-candidate-event-horizon']);
});

test('allows removing the approved default and still requires an explicit startup choice', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const sent = [];
  mountNativeDemoSelectionView(root, catalogue, profile, (request) => sent.push(request));
  let nodes = walk(root);
  const submit = nodes.find((node) => node.tagName === 'BUTTON');
  const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
  const status = nodes.find((node) => node.getAttribute('aria-live') === 'polite');

  assert.equal(submit.disabled, false);
  checkboxes[1].checked = false;
  await checkboxes[1].dispatch('change');
  assert.equal(submit.disabled, true);
  submit.disabled = false; // Exercise defensive submit checks independently of disabled UI.
  await submit.dispatch('click');
  assert.match(status.textContent, /Select one or more/);
  checkboxes[0].checked = true;
  await checkboxes[0].dispatch('change');
  submit.disabled = false;
  await submit.dispatch('click');
  assert.match(status.textContent, /Choose a startup project/);
  assert.deepEqual(sent, []);
});


test('blocks duplicate asynchronous submissions and exposes rejection for retry', async () => {
  const document = new Document();
  const root = new Element('div', document);
  let reject;
  let calls = 0;
  mountNativeDemoSelectionView(root, catalogue, profile, () => {
    calls++;
    return new Promise((resolve, failure) => { reject = failure; });
  });
  const nodes = walk(root);
  const checkbox = nodes.find((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
  const radio = nodes.find((node) => node.tagName === 'INPUT' && node.type === 'radio');
  const submit = nodes.find((node) => node.tagName === 'BUTTON');
  const status = nodes.find((node) => node.getAttribute('aria-live') === 'polite');
  checkbox.checked = true;
  await checkbox.dispatch('change');
  radio.checked = true;
  await radio.dispatch('change');
  const pending = submit.dispatch('click');
  assert.equal(submit.disabled, true);
  await submit.dispatch('click');
  assert.equal(calls, 1);
  reject(new Error('Build preparation unavailable'));
  await pending;
  assert.equal(status.textContent, 'Build preparation unavailable');
  assert.equal(submit.disabled, false);
});


test('shows an actionable preflight error and sends nothing when a required module is unchecked', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const sent = [];
  const partialProfile = { version: 1, engines: ['shapes'], effects: [], midi: [], modulation: [] };
  const expandedCatalogue = { ...catalogue, groups: { ...catalogue.groups, engines: ['macro', 'shapes'] } };
  mountNativeDemoSelectionView(root, expandedCatalogue, partialProfile, (request) => sent.push(request));
  const nodes = walk(root);
  const submit = nodes.find((node) => node.tagName === 'BUTTON');
  const status = nodes.find((node) => node.getAttribute('aria-live') === 'polite');

  await submit.dispatch('click');
  assert.equal(sent.length, 0);
  assert.match(status.textContent, /engines: macro/);
  assert.match(status.textContent, /Enable these modules or remove the selected project/);

  partialProfile.engines = ['macro', 'shapes'];
  await submit.dispatch('click');
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].project_ids, ['replacement-showcase-candidate-event-horizon']);
});

test('shows an accessible companion choice only while its parent is selected to start', async () => {
  const companionId = 'replacement-showcase-event-horizon-companion-set';
  const parentId = 'replacement-showcase-candidate-event-horizon';
  const expanded = {
    ...catalogue,
    projects: catalogue.projects,
    sets: [{ id: companionId, title: 'Event Horizon Companion Set',
      parent_project_id: parentId, source_dependency_scan_complete: false,
      dependency_scan_complete: false, source_path: 'private/source.lunar',
      source_sha256: 'b'.repeat(64), content_sha256: 'c'.repeat(64) }],
    full_song_default: { required: true, status: 'owner-approved', project_id: parentId,
      musical_choice_approved: true, blockers: [] },
  };
  const document = new Document();
  const root = new Element('div', document);
  const sent = [];
  const controller = mountNativeDemoSelectionView(root, expanded, profile, (request) => sent.push(request));
  const nodes = walk(root);
  const setCheckbox = nodes.find((node) => node.tagName === 'INPUT' && node.type === 'checkbox'
    && node.value === companionId);
  const radios = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'radio');
  const submit = nodes.find((node) => node.tagName === 'BUTTON');
  const parentRadio = radios.find((radio) => radio.value === parentId);
  assert.ok(setCheckbox);
  assert.equal(setCheckbox.disabled, false);
  assert.ok(nodes.some((node) => node.tagName === 'SPAN' && node.textContent === 'Event Horizon Companion Set'));
  setCheckbox.checked = true;
  await setCheckbox.dispatch('change');
  await submit.dispatch('click');
  assert.deepEqual(sent[0].set_ids, [companionId]);
  assert.deepEqual(controller.getSelection().setIds, [companionId]);

  const otherRadio = radios.find((radio) => radio.value === 'replacement-showcase-candidate-afterglow-relay');
  otherRadio.checked = true;
  await otherRadio.dispatch('change');
  assert.equal(setCheckbox.checked, false);
  assert.equal(setCheckbox.disabled, true);
  assert.deepEqual(controller.getSelection().setIds, []);
  assert.match(nodes.find((node) => node.getAttribute('aria-live') === 'polite').textContent,
    /needs Event Horizon selected as the startup project/);

  const parentCheckbox = nodes.find((node) => node.tagName === 'INPUT' && node.type === 'checkbox'
    && node.value === parentId);
  parentCheckbox.checked = false;
  await parentCheckbox.dispatch('change');
  assert.equal(setCheckbox.disabled, true);
  assert.equal(parentRadio.disabled, true);
  controller.destroy();
});
