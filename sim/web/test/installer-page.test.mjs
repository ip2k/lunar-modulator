// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mountInstallerPage } from '../www/installer-page.js';

class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.checked = false;
    this.disabled = false;
    this._textContent = '';
  }
  append(...children) { this.children.push(...children); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(callback);
  }
  async dispatch(name) {
    await Promise.all((this.listeners.get(name) ?? []).map((callback) => callback({ target: this })));
  }
  click() { this.wasClicked = true; }
  remove() { this.removed = true; }
  get textContent() { return this._textContent + this.children.map((child) => child.textContent).join(''); }
  set textContent(value) { this._textContent = String(value); this.children = []; }
}

class Document {
  constructor() { this.nodes = new Map(); }
  createElement(tagName) { return new Element(tagName, this); }
  createTextNode(value) { const node = new Element('#text', this); node.textContent = value; return node; }
  getElementById(id) { return this.nodes.get(id) ?? null; }
}

function walk(root) { return [root, ...root.children.flatMap(walk)]; }

const ids = [
  'legacy-example-afterglow-relay', 'legacy-example-event-horizon',
  'legacy-example-packet-bloom', 'legacy-example-neon-transit',
  'replacement-showcase-candidate-afterglow-relay',
  'replacement-showcase-candidate-event-horizon',
  'replacement-showcase-candidate-packet-bloom',
  'replacement-showcase-candidate-satellite-hearts',
];
const catalogue = {
  version: 1,
  groups: {
    engines: ['macro', 'shapes'], effects: ['plate'], midi: ['arp'], modulation: ['lfo'],
  },
  projects: ids.map((id) => ({
    id,
    title: id.split('-').slice(-2).join(' '),
    category: id.startsWith('replacement') ? 'replacement-showcase-candidate' : 'legacy-example',
    duration_estimate: { nominal_seconds: 100 },
    owner_disposition: id.startsWith('replacement')
      ? 'Replacement showcase candidate; owner musical acceptance pending.'
      : 'Legacy example; not approved as a showcase or default.',
    default_candidate: false,
    source_path: `private/${id}.lunar`,
    source_sha256: 'a'.repeat(64),
    dependency_validation: { status: 'pending-packed-backend-validation' },
  })),
  full_song_default: {
    required: true,
    status: 'pending',
    blockers: ['owner-approved composition', 'native playback and save/reload'],
  },
  default_profile: {
    version: 1, engines: ['macro', 'shapes'], effects: ['plate'], midi: ['arp'],
    modulation: ['lfo'], content: [],
  },
};

test('loads generated catalogue, mounts the shared chooser and exports only a validated request', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const moduleRoot = new Element('div', document);
  const loadStatus = new Element('p', document);
  const exportStatus = new Element('p', document);
  document.nodes.set('installer-load-status', loadStatus);
  document.nodes.set('installer-export-status', exportStatus);
  document.nodes.set('installer-modules', moduleRoot);
  const fetches = [];
  const originalCreate = URL.createObjectURL;
  const originalRevoke = URL.revokeObjectURL;
  let savedBlob;
  URL.createObjectURL = (blob) => { savedBlob = blob; return 'blob:test'; };
  URL.revokeObjectURL = () => {};
  try {
    const controller = await mountInstallerPage(root, {
      fetchImpl: async (url, options) => {
        fetches.push([url, options]);
        return { ok: true, json: async () => catalogue };
      },
    });
    assert.deepEqual(fetches, [['./demo-image-catalogue.json', { cache: 'no-store' }]]);
    assert.equal(loadStatus.textContent, '');
    assert.equal(moduleRoot.children[0].className, 'native-module-selection');
    assert.equal(moduleRoot.children[0].children.filter((node) => node.tagName === 'FIELDSET').length, 4);
    assert.equal(catalogue.full_song_default.status, 'pending');
    assert.ok(catalogue.projects.every((project) => project.default_candidate === false));

    const nodes = walk(root);
    const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
    const radios = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'radio');
    const button = nodes.find((node) => node.tagName === 'BUTTON');
    assert.equal(checkboxes.length, 8);
    assert.equal(radios.length, 8);
    assert.equal(button.textContent, 'Download build request (JSON)');
    assert.equal(button.disabled, true);
    assert.match(root.textContent, /Full-song default status: pending/);
    assert.match(root.textContent, /owner musical acceptance pending/i);
    assert.match(root.textContent, /not approved showcases or defaults/i);

    checkboxes[6].checked = true;
    await checkboxes[6].dispatch('change');
    checkboxes[1].checked = true;
    await checkboxes[1].dispatch('change');
    radios[1].checked = true;
    await radios[1].dispatch('change');
    assert.equal(button.disabled, false);
    await button.dispatch('click');

    const exported = JSON.parse(await savedBlob.text());
    assert.deepEqual(Object.keys(exported), [
      'version', 'engines', 'effects', 'midi', 'modulation', 'project_ids', 'startup_index',
    ]);
    assert.equal(exported.version, 1);
    assert.deepEqual(exported.project_ids, [ids[6], ids[1]]);
    assert.equal(exported.startup_index, 1);
    assert.deepEqual(exported.engines, catalogue.default_profile.engines);
    assert.equal('source_path' in exported, false);
    assert.equal('source_sha256' in exported, false);
    assert.equal('dependency_validation' in exported, false);
    assert.match(exportStatus.textContent, /Request exported\. No build or install was performed/);
    assert.equal(controller.getSelection().startupId, ids[1]);
    controller.destroy();
  } finally {
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
  }
});

test('reports catalogue-generation or fetch failure without mounting a chooser', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const loadStatus = new Element('p', document);
  document.nodes.set('installer-load-status', loadStatus);
  const controller = await mountInstallerPage(root, {
    fetchImpl: async () => ({ ok: false }),
  });
  assert.equal(controller, null);
  assert.equal(root.children.length, 0);
  assert.match(loadStatus.textContent, /generated project catalogue is unavailable/);
});

test('uses injected build client only after explicit selection and preserves module/project order', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const moduleRoot = new Element('div', document);
  const loadStatus = new Element('p', document);
  const exportStatus = new Element('p', document);
  const serviceNotice = new Element('p', document);
  const cancelButton = new Element('button', document);
  document.nodes.set('installer-load-status', loadStatus);
  document.nodes.set('installer-export-status', exportStatus);
  document.nodes.set('installer-service-notice', serviceNotice);
  document.nodes.set('installer-cancel-build', cancelButton);
  document.nodes.set('installer-modules', moduleRoot);
  const submissions = [];
  const controller = await mountInstallerPage(root, {
    fetchImpl: async () => ({ ok: true, json: async () => structuredClone(catalogue) }),
    buildClient: {
      async build(request, { onProgress }) {
        submissions.push(request);
        onProgress('queued');
        onProgress('running');
        onProgress('succeeded');
        return { status: 'succeeded', artifactBytes: 1234, installable: false };
      },
    },
  });
  const nodes = walk(root);
  const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
  const radios = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'radio');
  const button = nodes.find((node) => node.tagName === 'BUTTON');
  assert.equal(button.textContent, 'Request diagnostic build');
  assert.equal(submissions.length, 0, 'mounting the page must not submit a build');
  assert.equal(cancelButton.hidden, true);

  checkboxes[6].checked = true;
  await checkboxes[6].dispatch('change');
  checkboxes[1].checked = true;
  await checkboxes[1].dispatch('change');
  radios[1].checked = true;
  await radios[1].dispatch('change');
  await button.dispatch('click');

  assert.equal(submissions.length, 1);
  assert.deepEqual(submissions[0].project_ids, [ids[6], ids[1]]);
  assert.equal(submissions[0].startup_index, 1);
  assert.deepEqual(submissions[0].engines, ['macro', 'shapes']);
  assert.equal(exportStatus.textContent, 'Diagnostic build checks passed (1234 bytes). No installable firmware file is available.');
  assert.equal(cancelButton.hidden, true);
  assert.match(serviceNotice.textContent, /does not provide installable firmware/i);
  controller.destroy();
});
