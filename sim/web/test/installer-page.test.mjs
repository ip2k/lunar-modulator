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
  getAttribute(name) { return this.attributes.get(name) ?? null; }
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
  constructor() { this.nodes = new Map(); this.defaultView = { location: { origin: 'https://lunar.test' } }; this.serviceMarker = null; }
  querySelector(selector) { return selector === 'meta[name="lunar-installer-build-service"]' ? this.serviceMarker : null; }
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
    engines: ['macro', 'shapes', 'sixop', 'drums'], effects: ['plate', 'hall'], midi: ['arp'], modulation: ['lfo'],
  },
  projects: ids.map((id) => ({
    id,
    title: id.split('-').slice(-2).join(' '),
    category: id.startsWith('replacement') ? 'replacement-showcase-candidate' : 'legacy-example',
    duration_estimate: { nominal_seconds: 100 },
    owner_disposition: id.startsWith('replacement')
      ? (id === 'replacement-showcase-candidate-event-horizon'
        ? 'Owner-approved musical full-song default; native playback and release admission pending.'
        : 'Replacement showcase candidate; owner musical acceptance pending.')
      : 'Legacy example; not approved as a showcase or default.',
    default_candidate: false,
    source_path: `private/${id}.lunar`,
    source_sha256: 'a'.repeat(64),
    dependency_validation: { status: 'pending-packed-backend-validation' },
    source_dependency_scan_complete: true,
    source_module_dependencies: { engines: ['macro'], effects: [], midi: [], modulation: [] },
  })),
  full_song_default: {
    required: true,
    status: 'owner-approved',
    project_id: 'replacement-showcase-candidate-event-horizon',
    musical_choice_approved: true,
    blockers: ['exact packed-content and module-dependency validation', 'native playback and save/reload'],
  },
  default_profile: {
    version: 1, engines: ['macro', 'shapes', 'sixop', 'drums'], effects: ['plate', 'hall'], midi: ['arp'],
    modulation: ['lfo'], content: [],
  },
};

test('loads generated catalogue, mounts the shared chooser and exports only a validated request', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const moduleRoot = new Element('div', document);
  const packageRoot = new Element('div', document);
  const loadStatus = new Element('p', document);
  const exportStatus = new Element('p', document);
  document.nodes.set('installer-load-status', loadStatus);
  document.nodes.set('installer-export-status', exportStatus);
  document.nodes.set('installer-modules', moduleRoot);
  document.nodes.set('installer-package-inspection', packageRoot);
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
    assert.equal(packageRoot.children[0].className, 'installer-package-inspection');
    assert.equal(walk(packageRoot).some((node) => node.type === 'file'), true);
    assert.equal(catalogue.full_song_default.status, 'owner-approved');
    assert.ok(catalogue.projects.every((project) => project.default_candidate === false));

    const nodes = walk(root);
    const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
    const radios = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'radio');
    const button = nodes.find((node) => node.tagName === 'BUTTON');
    assert.equal(checkboxes.length, 8);
    assert.equal(radios.length, 8);
    assert.equal(button.textContent, 'Download build request (JSON)');
    assert.equal(button.disabled, false);
    assert.match(root.textContent, /Full-song default status: owner-approved/);
    assert.match(root.textContent, /owner-approved musical full-song default/i);
    assert.match(root.textContent, /approval covers the song choice only/i);
    assert.equal(checkboxes[5].checked, true);
    assert.equal(radios[5].checked, true);

    checkboxes[4].checked = true;
    await checkboxes[4].dispatch('change');
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
    assert.deepEqual(exported.project_ids, [ids[5], ids[4], ids[1]]);
    assert.equal(exported.startup_index, 2);
    assert.deepEqual(exported.engines, catalogue.default_profile.engines);
    assert.equal('source_path' in exported, false);
    assert.equal('source_sha256' in exported, false);
    assert.equal('dependency_validation' in exported, false);
    assert.match(exportStatus.textContent, /Request exported\. No build or install was performed/);
    assert.equal(controller.getSelection().startupId, ids[1]);
    controller.destroy();
    assert.equal(packageRoot.children[0].removed, true);
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
        return { status: 'succeeded', artifactBytes: 1234, appBudgetBytes: 868836,
          remainingBytes: 867602, installable: false };
      },
    },
  });
  const nodes = walk(root);
  const checkboxes = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'checkbox');
  const radios = nodes.filter((node) => node.tagName === 'INPUT' && node.type === 'radio');
  const button = nodes.find((node) => node.tagName === 'BUTTON');
  assert.equal(button.textContent, 'Request private build check');
  assert.equal(submissions.length, 0, 'mounting the page must not submit a build');
  assert.equal(cancelButton.hidden, true);

  checkboxes[4].checked = true;
  await checkboxes[4].dispatch('change');
  checkboxes[1].checked = true;
  await checkboxes[1].dispatch('change');
  radios[1].checked = true;
  await radios[1].dispatch('change');
  await button.dispatch('click');

  assert.equal(submissions.length, 1);
  assert.deepEqual(submissions[0].project_ids, [ids[5], ids[4], ids[1]]);
  assert.equal(submissions[0].startup_index, 2);
  assert.deepEqual(submissions[0].engines, ['macro', 'shapes', 'sixop', 'drums']);
  assert.equal(exportStatus.textContent, 'Diagnostic build checks passed. Application flash: 1,234 / 868,836 bytes used; 867,602 bytes free. No installable firmware file is available.');
  assert.equal(cancelButton.hidden, true);
  assert.match(serviceNotice.textContent, /does not provide installable firmware/i);
  controller.destroy();
});


test('deployment marker enables only the fixed same-origin diagnostic API on explicit submit', async () => {
  const document = new Document();
  const marker = new Element('meta', document);
  marker.setAttribute('content', 'enabled');
  document.serviceMarker = marker;
  const root = new Element('div', document);
  const moduleRoot = new Element('div', document);
  const loadStatus = new Element('p', document);
  const exportStatus = new Element('p', document);
  const serviceNotice = new Element('p', document);
  document.nodes.set('installer-load-status', loadStatus);
  document.nodes.set('installer-export-status', exportStatus);
  document.nodes.set('installer-service-notice', serviceNotice);
  document.nodes.set('installer-modules', moduleRoot);
  const calls = [];
  const jobId = 'a'.repeat(32);
  const artifactSha = 'b'.repeat(64);
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (String(url) === './demo-image-catalogue.json') {
      return { ok: true, json: async () => structuredClone(catalogue) };
    }
    if (options.method === 'POST') {
      return new Response(JSON.stringify({ id: jobId, status: 'queued', status_url: '/api/v1/builds/' + jobId }), {
        status: 202, headers: { 'content-type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({ id: jobId, status: 'succeeded', kind: 'private-diagnostic-build', result: {
      status: 'linked-private-diagnostic', artifact_sha256: artifactSha, artifact_bytes: 785312,
      app_budget_bytes: 868836, remaining_bytes: 83524, installable: false, hardware_tested: false,
    } }), { status: 200, headers: { 'content-type': 'application/json' } });
  };
  const controller = await mountInstallerPage(root, { fetchImpl,
    buildConfiguration: { flash_layout: 'expanded-d7000', runtime_mode: 'song-diagnostic' },
  });
  const nodes = walk(root);
  const button = nodes.find((node) => node.tagName === 'BUTTON');
  assert.equal(button.textContent, 'Request private build check');
  assert.equal(calls.length, 1, 'page load reads only the generated catalogue');
  assert.match(serviceNotice.textContent, /availability is checked when you submit/i);
  await button.dispatch('click');
  assert.deepEqual(calls.map((call) => call.url), [
    './demo-image-catalogue.json',
    'https://lunar.test/api/v1/builds',
    'https://lunar.test/api/v1/builds/' + jobId,
  ]);
  assert.equal(calls[1].options.credentials, 'same-origin');
  assert.equal(calls[1].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls[1].options.body), {
    version: 1,
    engines: catalogue.default_profile.engines,
    effects: catalogue.default_profile.effects,
    midi: catalogue.default_profile.midi,
    modulation: catalogue.default_profile.modulation,
    project_ids: [ids[5]], startup_index: 0,
    flash_layout: 'expanded-d7000', runtime_mode: 'song-diagnostic',
  });
  assert.equal(calls[2].options.credentials, 'same-origin');
  assert.match(exportStatus.textContent, /785,312 \/ 868,836 bytes used; 83,524 bytes free/);
  assert.match(exportStatus.textContent, /No installable firmware file is available/);
  controller.destroy();
});

test('default Event Horizon plus selected companion SET reaches the service client and reports linked usage', async () => {
  const document = new Document();
  const marker = new Element('meta', document);
  marker.setAttribute('content', 'enabled');
  document.serviceMarker = marker;
  const root = new Element('div', document);
  const moduleRoot = new Element('div', document);
  const loadStatus = new Element('p', document);
  const exportStatus = new Element('p', document);
  const serviceNotice = new Element('p', document);
  document.nodes.set('installer-load-status', loadStatus);
  document.nodes.set('installer-export-status', exportStatus);
  document.nodes.set('installer-service-notice', serviceNotice);
  document.nodes.set('installer-modules', moduleRoot);

  const setId = 'replacement-showcase-event-horizon-companion-set';
  const setCatalogue = {
    ...structuredClone(catalogue),
    sets: [{
      id: setId,
      title: 'Event Horizon Companion Set',
      parent_project_id: ids[5],
      source_dependency_scan_complete: false,
      dependency_scan_complete: false,
    }],
  };
  const calls = [];
  const jobId = 'c'.repeat(32);
  const artifactSha = 'd'.repeat(64);
  const fetchImpl = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    if (String(url) === './demo-image-catalogue.json') {
      return { ok: true, json: async () => structuredClone(setCatalogue) };
    }
    if (options.method === 'POST') {
      return new Response(JSON.stringify({ id: jobId, status: 'queued',
        status_url: '/api/v1/builds/' + jobId }), {
        status: 202, headers: { 'content-type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({ id: jobId, status: 'succeeded',
      kind: 'private-diagnostic-build', result: {
        status: 'linked-private-diagnostic', artifact_sha256: artifactSha,
        artifact_bytes: 785312, app_budget_bytes: 868836, remaining_bytes: 83524,
        installable: false, hardware_tested: false,
        provenance: { kind: 'private-diagnostic-build-provenance', sha256: 'e'.repeat(64) },
        receipt_preview: {
          flash_layout: 'expanded-d9000', runtime_mode: 'diagnostic',
          profile: { flash_layout: 'expanded-d9000', runtime_mode: 'diagnostic', shapes_voices: 12 },
          modules: [...catalogue.default_profile.engines, ...catalogue.default_profile.effects,
            ...catalogue.default_profile.midi, ...catalogue.default_profile.modulation],
          projects: [{ id: ids[5], startup: true }],
          sets: [{ id: setId, parent_project_id: ids[5] }],
          packed_content: { bytes: 192, assets: [
            { kind: 'project', id: ids[5], bytes: 128, sha256: 'a'.repeat(64) },
            { kind: 'set', id: setId, parent_project_id: ids[5], bytes: 64, sha256: 'b'.repeat(64) },
          ] },
          application: { sha256: artifactSha, bytes: 785312, budget_bytes: 868836, remaining_bytes: 83524 },
          provenance: { kind: 'private-diagnostic-build-provenance', sha256: 'e'.repeat(64) },
        },
      } }), { status: 200, headers: { 'content-type': 'application/json' } });
  };

  const controller = await mountInstallerPage(root, { fetchImpl });
  const nodes = walk(root);
  const setCheckbox = nodes.find((node) => node.tagName === 'INPUT'
    && node.type === 'checkbox' && node.value === setId);
  const submit = nodes.find((node) => node.tagName === 'BUTTON'
    && node.textContent === 'Request private build check');
  assert.ok(setCheckbox, 'generated catalogue exposes the companion SET');
  assert.equal(setCheckbox.checked, false, 'companion SET remains opt-in');
  assert.equal(setCheckbox.disabled, false, 'default Event Horizon is the startup project');
  assert.ok(submit);

  setCheckbox.checked = true;
  await setCheckbox.dispatch('change');
  await submit.dispatch('click');

  assert.deepEqual(calls.map((call) => call.url), [
    './demo-image-catalogue.json',
    'https://lunar.test/api/v1/builds',
    'https://lunar.test/api/v1/builds/' + jobId,
  ]);
  const posted = JSON.parse(calls[1].options.body);
  assert.deepEqual(posted, {
    version: 1,
    engines: catalogue.default_profile.engines,
    effects: catalogue.default_profile.effects,
    midi: catalogue.default_profile.midi,
    modulation: catalogue.default_profile.modulation,
    project_ids: [ids[5]],
    startup_index: 0,
    set_ids: [setId],
  });
  assert.equal(calls[1].options.credentials, 'same-origin');
  assert.equal(calls[2].options.credentials, 'same-origin');
  assert.match(exportStatus.textContent,
    /785,312 \/ 868,836 bytes used; 83,524 bytes free/);
  assert.match(exportStatus.textContent, /No installable firmware file is available/);
  assert.match(serviceNotice.textContent, /measured summary only/i);
  const preview = nodes.find(node => node.className === 'installer-receipt-preview');
  assert.ok(preview && !preview.hidden);
  assert.match(preview.textContent, /Startup project: replacement-showcase-candidate-event-horizon/);
  assert.match(preview.textContent, /replacement-showcase-event-horizon-companion-set → replacement-showcase-candidate-event-horizon/);
  assert.match(preview.textContent, /browser cannot independently derive them from the catalogue/i);
  assert.match(preview.textContent, /not installable/);
  controller.destroy();
});

for (const changed of ['module', 'project', 'startup', 'set']) {
  for (const outcome of ['resolve', 'reject']) {
    test(`invalidates ${outcome === 'resolve' ? 'completed' : 'failed'} build feedback after an in-flight ${changed} edit`, async () => {
      const document = new Document();
      const root = new Element('div', document);
      const moduleRoot = new Element('div', document);
      const status = new Element('p', document);
      document.nodes.set('installer-modules', moduleRoot);
      document.nodes.set('installer-export-status', status);
      const inputCatalogue = structuredClone(catalogue);
      inputCatalogue.sets = [{
        id: 'replacement-showcase-event-horizon-companion-set',
        title: 'Event Horizon Companion Set', parent_project_id: ids[5],
        source_dependency_scan_complete: false, dependency_scan_complete: false,
        source_path: 'private/set.lunar', source_sha256: 'b'.repeat(64), content_sha256: 'c'.repeat(64),
      }];
      let resolveBuild, rejectBuild, progress;
      await mountInstallerPage(root, {
        fetchImpl: async () => ({ ok: true, json: async () => inputCatalogue }),
        buildClient: { build(request, { onProgress }) {
          progress = onProgress;
          return new Promise((resolve, reject) => { resolveBuild = resolve; rejectBuild = reject; });
        } },
      });
      const nodes = walk(root);
      const submit = nodes.find(node => node.tagName === 'BUTTON');
      if (changed === 'startup') {
        const otherProject = nodes.find(node => node.tagName === 'INPUT' && node.type === 'checkbox' && node.value === ids[4]);
        otherProject.checked = true;
        await otherProject.dispatch('change');
      }
      const pending = submit.dispatch('click');
      const control = changed === 'module'
        ? walk(moduleRoot).find(node => node.tagName === 'INPUT' && node.value === 'hall')
        : nodes.find(node => node.tagName === 'INPUT'
          && (changed === 'set' ? node.value === 'replacement-showcase-event-horizon-companion-set'
            : node.value === ids[changed === 'startup' ? 4 : 5] && node.type === (changed === 'startup' ? 'radio' : 'checkbox')));
      control.checked = changed === 'set' || changed === 'startup';
      await control.dispatch('change');
      const changedMessage = 'Selection changed. Request a new build to measure flash usage.';
      assert.equal(status.textContent, changedMessage);
      progress('running');
      assert.equal(status.textContent, changedMessage, 'late progress must not replace invalidation');
      if (outcome === 'resolve') resolveBuild({ artifactBytes: 1234, appBudgetBytes: 868836, remainingBytes: 867602 });
      else rejectBuild(new Error('Old build failed'));
      await pending;
      assert.equal(status.textContent, changedMessage);
      const demoStatus = nodes.find(node => node.className === 'native-demo-selection-status');
      assert.equal(demoStatus.textContent, changedMessage);
      assert.doesNotMatch(status.textContent, /1,234|Old build failed|checks passed/);
    });
  }
}

test('clears a completed flash measurement when module choices change', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const moduleRoot = new Element('div', document);
  const status = new Element('p', document);
  document.nodes.set('installer-modules', moduleRoot);
  document.nodes.set('installer-export-status', status);
  await mountInstallerPage(root, {
    fetchImpl: async () => ({ ok: true, json: async () => structuredClone(catalogue) }),
    buildClient: { async build() { return { artifactBytes: 1234, appBudgetBytes: 868836, remainingBytes: 867602 }; } },
  });
  await walk(root).find(node => node.tagName === 'BUTTON').dispatch('click');
  assert.match(status.textContent, /Application flash: 1,234/);
  const hall = walk(moduleRoot).find(node => node.tagName === 'INPUT' && node.value === 'hall');
  hall.checked = false;
  await hall.dispatch('change');
  assert.equal(status.textContent, 'Selection changed. Request a new build to measure flash usage.');
});


test('profile selector explicitly changes runtime, preserves choices and clears measured flash', async () => {
  const document = new Document();
  const root = new Element('div', document);
  const status = new Element('p', document);
  document.nodes.set('installer-modules', new Element('div', document));
  const select = new Element('select', document);
  select.value = 'legacy';
  document.nodes.set('installer-export-status', status);
  document.nodes.set('installer-build-profile', select);
  const requests = [];
  await mountInstallerPage(root, {
    fetchImpl: async () => ({ ok: true, json: async () => structuredClone(catalogue) }),
    buildClient: { async build(request) {
      requests.push(request);
      return { artifactBytes: 1234, appBudgetBytes: 860644, remainingBytes: 859410 };
    } },
  });
  const button = walk(root).find(node => node.tagName === 'BUTTON');
  await button.dispatch('click');
  assert.equal(requests[0].runtime_mode, undefined, 'diagnostic default remains unchanged');
  assert.match(status.textContent, /1,234/);
  select.value = 'continuous';
  await select.dispatch('change');
  assert.equal(status.textContent, 'Selection changed. Request a new build to measure flash usage.');
  assert.equal(requests.length, 1, 'profile change does not submit automatically');
  await button.dispatch('click');
  assert.deepEqual(requests[1], { ...requests[0], flash_layout: 'expanded-d7000', runtime_mode: 'continuous' });
  assert.match(status.textContent, /Continuous/);
  select.value = 'song-diagnostic';
  await select.dispatch('change');
  await button.dispatch('click');
  assert.deepEqual(requests[2], { ...requests[0], flash_layout: 'expanded-d7000', runtime_mode: 'song-diagnostic' });
});
