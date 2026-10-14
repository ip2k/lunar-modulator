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

const project = (id, title, seconds) => ({
  id, title, category: 'legacy-example',
  duration_estimate: { nominal_seconds: seconds },
  owner_disposition: 'legacy example; not approved as a showcase or default',
  default_candidate: false,
  source_path: `private/${id}.lunar`, source_sha256: 'a'.repeat(64),
});
const catalogue = {
  version: 1,
  groups: { engines: ['macro'], effects: ['plate'], midi: ['arp'], modulation: ['lfo'] },
  projects: [project('relay', '<img src=x onerror=alert(1)>', 198.26), project('horizon', 'Event Horizon', 193.33)],
  full_song_default: { required: true, status: 'pending', blockers: ['Owner approval', 'Native playback and save/reload'] },
};
const profile = { version: 1, engines: ['macro'], effects: [], midi: [], modulation: [] };

function walk(root) {
  return [root, ...root.children.flatMap(walk)];
}

test('renders safe, explicit choices and sends only adapter request in user selection order', () => {
  const document = new Document();
  const root = new Element('div', document);
  const sent = [];
  const controller = mountNativeDemoSelectionView(root, catalogue, profile, (request) => sent.push(request));
  const nodes = walk(root);
  const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
  const radios = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'radio');
  const submit = nodes.find((node) => node.tagName === 'BUTTON');
  const textNodes = nodes.map((node) => node.textContent).join('\n');

  assert.equal(checkboxes.length, 2);
  assert.equal(radios.length, 2);
  assert.ok(nodes.some((node) => node.tagName === 'SPAN' &&
    node.textContent === 'Event Horizon (Legacy example)'));
  assert.equal(submit.disabled, true);
  assert.match(textNodes, /Full-song default status: pending/);
  assert.match(textNodes, /not approved showcases or defaults/);
  assert.match(textNodes, /Estimated duration 3:18/);
  assert.match(textNodes, /metadata, not verified playback lengths/);
  assert.match(textNodes, /<img src=x onerror=alert\(1\)>/);
  assert.equal(nodes.some((node) => node.tagName === 'IMG'), false);
  assert.equal(nodes.some((node) => 'innerHTML' in node && node.innerHTML), false);

  checkboxes[1].checked = true;
  checkboxes[1].dispatch('change');
  checkboxes[0].checked = true;
  checkboxes[0].dispatch('change');
  assert.equal(radios[0].disabled, false);
  assert.equal(radios[1].disabled, false);
  radios[0].checked = true;
  radios[0].dispatch('change');
  assert.equal(submit.disabled, false);
  submit.dispatch('click');

  assert.equal(sent.length, 1);
  assert.deepEqual(Object.keys(sent[0]), [
    'version', 'engines', 'effects', 'midi', 'modulation', 'project_ids', 'startup_index',
  ]);
  assert.deepEqual(sent[0].project_ids, ['horizon', 'relay']);
  assert.equal(sent[0].startup_index, 1);
  assert.equal('source_path' in sent[0], false);
  assert.equal('source_sha256' in sent[0], false);
  assert.deepEqual(controller.getSelection(), { projectIds: ['horizon', 'relay'], startupId: 'relay' });

  checkboxes[0].checked = false;
  checkboxes[0].dispatch('change');
  assert.equal(radios[0].disabled, true);
  assert.equal(radios[0].checked, false);
  assert.equal(submit.disabled, true);
  assert.deepEqual(controller.getSelection(), { projectIds: ['horizon'], startupId: null });
  controller.destroy();
  assert.equal(root.children[0].removed, true);
});

test('refuses empty selection and refuses proceeding without an explicit startup choice', () => {
  const document = new Document();
  const root = new Element('div', document);
  const sent = [];
  mountNativeDemoSelectionView(root, catalogue, profile, (request) => sent.push(request));
  let nodes = walk(root);
  const submit = nodes.find((node) => node.tagName === 'BUTTON');
  const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
  const status = nodes.find((node) => node.getAttribute('aria-live') === 'polite');

  submit.disabled = false; // Exercise defensive submit checks independently of disabled UI.
  submit.dispatch('click');
  assert.match(status.textContent, /Select one or more/);
  checkboxes[0].checked = true;
  checkboxes[0].dispatch('change');
  submit.disabled = false;
  submit.dispatch('click');
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
