// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildNativeDemoSelectionRequest,
  describeNativeDemoCatalogue,
} from '../www/native-demo-selection.js';
import { D7000_REQUIRED_BY_GROUP } from '../www/native-build-selection.js';

const projects = [
  { id: 'legacy-example-afterglow-relay', title: 'Afterglow Relay', category: 'legacy-example',
    duration_estimate: { nominal_seconds: 198.261 },
    owner_disposition: 'legacy example; not approved as a showcase or default', default_candidate: false,
    source_path: '../must-not-enter-request.lunar', source_sha256: 'a'.repeat(64),
    source_dependency_scan_complete: true, source_module_dependencies: { engines: ['macro'], effects: ['plate'], midi: [], modulation: [] } },
  { id: 'legacy-example-event-horizon', title: 'Event Horizon', category: 'legacy-example',
    duration_estimate: { nominal_seconds: 193.333 },
    owner_disposition: 'legacy example; not approved as a showcase or default', default_candidate: false,
    source_path: 'engines/state/examples/event-horizon.lunar', source_sha256: 'b'.repeat(64),
    source_dependency_scan_complete: true, source_module_dependencies: { engines: ['macro'], effects: ['plate'], midi: [], modulation: [] } },
  { id: 'replacement-showcase-candidate-packet-bloom', title: 'Packet Bloom',
    category: 'replacement-showcase-candidate',
    duration_estimate: { bpm: 82, bars: 40, scenes: 5, nominal_seconds: 117.073171 },
    owner_disposition: 'replacement showcase candidate; owner musical acceptance pending',
    default_candidate: false,
    source_path: 'engines/state/examples/replacement-showcases/packet-bloom-showcase.lunar',
    source_sha256: 'c'.repeat(64),
    dependency_validation: { status: 'pending-packed-backend-validation',
      dependency_scan_complete: false, validated_module_ids: [] },
    source_dependency_scan_complete: true, source_module_dependencies: { engines: ['macro'], effects: ['plate'], midi: [], modulation: [] } },
];
const catalogue = {
  version: 1,
  groups: { engines: ['macro', 'shapes', 'sixop', 'drums'], effects: ['plate', 'hall'], midi: ['arp'], modulation: ['lfo'] },
  projects,
  full_song_default: { required: true, status: 'pending', blockers: ['owner-approved full-song composition'] },
};
const profile = { version: 1, engines: ['macro', 'shapes'], effects: ['plate'], midi: [], modulation: ['lfo'] };
const d7000Profile = {
  version: 1, engines: ['macro', 'shapes', 'sixop', 'drums'],
  effects: ['plate', 'hall'], midi: [], modulation: ['lfo'],
};

test('names exact grouped prerequisites for the fixed D7000 profile', () => {
  assert.deepEqual(D7000_REQUIRED_BY_GROUP, {
    engines: ['macro', 'shapes', 'sixop', 'drums'], effects: ['hall'],
  });
});

test('builds exact backend keys while preserving selected order and startup index', () => {
  const request = buildNativeDemoSelectionRequest(catalogue, profile,
    ['legacy-example-event-horizon', 'legacy-example-afterglow-relay'], 1);
  assert.deepEqual(Object.keys(request), [
    'version', 'engines', 'effects', 'midi', 'modulation', 'project_ids', 'startup_index',
  ]);
  assert.deepEqual(request.project_ids,
    ['legacy-example-event-horizon', 'legacy-example-afterglow-relay']);
  assert.equal(request.startup_index, 1);
  assert.equal(request.project_ids[request.startup_index], 'legacy-example-afterglow-relay');
  assert.deepEqual(request, {
    version: 1, engines: ['macro', 'shapes'], effects: ['plate'], midi: [], modulation: ['lfo'],
    project_ids: ['legacy-example-event-horizon', 'legacy-example-afterglow-relay'], startup_index: 1,
  });
});

test('serializes only the explicit supported D7000 diagnostic build configuration', () => {
  const request = buildNativeDemoSelectionRequest(catalogue, d7000Profile,
    ['legacy-example-event-horizon'], 0, [], {
      flash_layout: 'expanded-d7000', runtime_mode: 'song-diagnostic',
    });
  assert.deepEqual(request, {
    version: 1, engines: ['macro', 'shapes', 'sixop', 'drums'], effects: ['plate', 'hall'], midi: [], modulation: ['lfo'],
    project_ids: ['legacy-example-event-horizon'], startup_index: 0,
    flash_layout: 'expanded-d7000', runtime_mode: 'song-diagnostic',
  });
  assert.equal(Object.isFrozen(request), true);
});

test('rejects incomplete or incompatible explicit build configuration', () => {
  const projectIds = ['legacy-example-event-horizon'];
  for (const configuration of [
    { flash_layout: 'expanded-d7000' },
    { flash_layout: 'expanded-d7000', runtime_mode: 'diagnostic' },
    { flash_layout: 'expanded-d9000', runtime_mode: 'song-diagnostic' },
    { flash_layout: 'expanded-d7000', runtime_mode: 'song-diagnostic', extra: true },
  ]) {
    assert.throws(() => buildNativeDemoSelectionRequest(catalogue, d7000Profile,
      projectIds, 0, [], configuration));
  }
  const completeConfiguration = { flash_layout: 'expanded-d7000', runtime_mode: 'song-diagnostic' };
  for (const incompleteModules of [
    { ...d7000Profile, engines: ['macro', 'shapes', 'drums'] },
    { ...d7000Profile, engines: ['macro', 'shapes', 'sixop'] },
    { ...d7000Profile, engines: ['shapes', 'sixop', 'drums'] },
    { ...d7000Profile, effects: ['plate'] },
    { ...d7000Profile, engines: ['macro', 'shapes', 'drums', 'hall'], effects: ['plate'] },
  ]) {
    assert.throws(() => buildNativeDemoSelectionRequest(catalogue, incompleteModules,
      projectIds, 0, [], completeConfiguration));
  }
});

test('rejects unknown, repeated, empty and unavailable project selections', () => {
  assert.throws(() => buildNativeDemoSelectionRequest(catalogue, profile, ['unknown'], 0), /known/);
  assert.throws(() => buildNativeDemoSelectionRequest(catalogue, profile,
    ['legacy-example-afterglow-relay', 'legacy-example-afterglow-relay'], 0), /Duplicate/);
  assert.throws(() => buildNativeDemoSelectionRequest(catalogue, profile, [], 0), /one or more/);
  assert.throws(() => buildNativeDemoSelectionRequest({ ...catalogue, projects: [] }, profile,
    ['legacy-example-afterglow-relay'], 0), /known/);
  assert.throws(() => buildNativeDemoSelectionRequest({ ...catalogue,
    projects: [projects[0], projects[0]] }, profile, ['legacy-example-afterglow-relay'], 0), /duplicate/);
});

test('requires an integer startup index inside the selected ordering', () => {
  for (const startupIndex of [-1, 1, 0.5, '0', Number.NaN]) {
    assert.throws(() => buildNativeDemoSelectionRequest(catalogue, profile,
      ['legacy-example-afterglow-relay'], startupIndex), /Startup index/);
  }
});

test('exposes current catalogue disposition without promoting examples or a default', () => {
  const disposition = describeNativeDemoCatalogue(catalogue);
  assert.equal(disposition.fullSongDefault.required, true);
  assert.equal(disposition.fullSongDefault.status, 'pending');
  assert.equal(disposition.projects[0].category, 'legacy-example');
  assert.equal(disposition.projects[0].default_candidate, false);
  assert.match(disposition.projects[0].owner_disposition, /not approved/);
  assert.deepEqual(Object.keys(disposition.projects[0]).sort(),
    ['category', 'default_candidate', 'duration_estimate', 'id', 'owner_disposition', 'reservation', 'title'].sort());
});

test('keeps replacement candidates pending and confines source/dependency metadata to trusted catalogue', () => {
  const disposition = describeNativeDemoCatalogue(catalogue);
  const candidate = disposition.projects.find(
    (project) => project.id === 'replacement-showcase-candidate-packet-bloom');
  assert.equal(disposition.fullSongDefault.status, 'pending');
  assert.equal(candidate.category, 'replacement-showcase-candidate');
  assert.equal(candidate.default_candidate, false);
  assert.match(candidate.owner_disposition, /owner musical acceptance pending/);
  assert.deepEqual(Object.keys(candidate).sort(),
    ['category', 'default_candidate', 'duration_estimate', 'id', 'owner_disposition', 'reservation', 'title'].sort());
  assert.equal(candidate.reservation.status, 'rejected');
  assert.equal(candidate.reservation.label, 'This arrangement exceeds available playback memory.');

  assert.throws(() => buildNativeDemoSelectionRequest(catalogue, profile,
    ['replacement-showcase-candidate-packet-bloom'], 0), /Unavailable under the current profile/);
  assert.equal('source_path' in candidate, false);
  assert.equal('source_sha256' in candidate, false);
  assert.equal('dependency_validation' in candidate, false);
  assert.equal('source_module_dependencies' in candidate, false);
  assert.equal('dependencies' in candidate, false);
});

test('request is immutable and snapshots arrays without paths, hashes or dependency claims', () => {
  const ids = ['legacy-example-afterglow-relay'];
  const originalEngines = [...profile.engines];
  const request = buildNativeDemoSelectionRequest(catalogue, profile, ids, 0);
  ids.push('legacy-example-event-horizon');
  profile.engines.reverse();
  assert.deepEqual(request.project_ids, ['legacy-example-afterglow-relay']);
  assert.deepEqual(request.engines, originalEngines);
  assert.equal(Object.isFrozen(request), true);
  assert.equal(Object.isFrozen(request.engines), true);
  assert.equal(Object.isFrozen(request.project_ids), true);
  assert.equal('source_path' in request, false);
  assert.equal('source_sha256' in request, false);
  assert.equal('dependencies' in request, false);
});

test('allocator dispositions apply only to exact replacement IDs and rejected projects fail closed', () => {
  const extra = [
    { ...projects[0], id: 'replacement-showcase-candidate-afterglow-relay', title: 'Afterglow Relay' },
    { ...projects[1], id: 'replacement-showcase-candidate-event-horizon', title: 'Event Horizon' },
    { ...projects[2], id: 'replacement-showcase-candidate-satellite-hearts', title: 'Satellite Hearts' },
    { ...projects[1], id: 'legacy-example-neon-transit', title: 'Neon Transit' },
  ];
  const expanded = { ...catalogue, projects: [...projects, ...extra] };
  const view = describeNativeDemoCatalogue(expanded);
  const statusOf = (id) => view.projects.find((project) => project.id === id).reservation.status;
  assert.equal(statusOf('replacement-showcase-candidate-event-horizon'), 'allocator-fit');
  assert.equal(statusOf('replacement-showcase-candidate-afterglow-relay'), 'allocator-fit');
  assert.equal(statusOf('replacement-showcase-candidate-satellite-hearts'), 'rejected');
  assert.equal(statusOf('legacy-example-neon-transit'), 'pending');
  assert.doesNotThrow(() => buildNativeDemoSelectionRequest(expanded, profile,
    ['replacement-showcase-candidate-event-horizon'], 0));
  assert.doesNotThrow(() => buildNativeDemoSelectionRequest(expanded, profile,
    ['replacement-showcase-candidate-afterglow-relay'], 0));
  assert.throws(() => buildNativeDemoSelectionRequest(expanded, profile,
    ['replacement-showcase-candidate-satellite-hearts'], 0), /Unavailable/);
  assert.equal(expanded.full_song_default.status, 'pending');
});


test('preflights source dependencies for selected projects but ignores unrelated modules', () => {
  const needsSound = { ...projects[1], source_module_dependencies: {
    engines: ['macro'], effects: [], midi: [], modulation: [],
  } };
  const needsEffect = { ...projects[0], source_module_dependencies: {
    engines: [], effects: ['plate'], midi: [], modulation: [],
  } };
  const expanded = { ...catalogue, projects: [needsSound, needsEffect] };
  const moduleProfile = { version: 1, engines: ['shapes'], effects: [], midi: [], modulation: [] };
  assert.throws(() => buildNativeDemoSelectionRequest(expanded, moduleProfile, [needsSound.id], 0),
    /engines: macro.*Enable these modules or remove the selected project/);
  const effectProfile = { version: 1, engines: ['macro'], effects: [], midi: [], modulation: [] };
  assert.throws(() => buildNativeDemoSelectionRequest(expanded, effectProfile, [needsEffect.id], 0),
    /effects: plate.*Enable these modules or remove the selected project/);

  const valid = { version: 1, engines: ['macro', 'shapes'], effects: ['plate'], midi: [], modulation: ['lfo'] };
  const request = buildNativeDemoSelectionRequest(expanded, valid, [needsSound.id, needsEffect.id], 1);
  assert.deepEqual(request.project_ids, [needsSound.id, needsEffect.id]);
  assert.equal(request.startup_index, 1);
  assert.deepEqual(request.engines, ['macro', 'shapes']);
  assert.deepEqual(request.effects, ['plate']);
});

test('fails closed when source dependency preflight metadata is missing or outside canonical groups', () => {
  for (const project of [
    { ...projects[0], source_dependency_scan_complete: false },
    { ...projects[0], source_module_dependencies: { ...projects[0].source_module_dependencies, engines: ['not-canonical'] } },
  ]) {
    assert.throws(() => buildNativeDemoSelectionRequest({ ...catalogue, projects: [project] }, profile,
      [project.id], 0), /dependency preflight metadata is unavailable/);
  }
});

test('companion SET is optional, trusted, ordered, and bound to its parent startup', () => {
  const companion = {
    id: 'replacement-showcase-event-horizon-companion-set',
    title: 'Event Horizon Companion Set',
    parent_project_id: 'replacement-showcase-candidate-event-horizon',
    source_path: 'private/event-horizon.lunar', source_sha256: 'd'.repeat(64),
    content_sha256: 'e'.repeat(64), source_dependency_scan_complete: false,
    dependency_scan_complete: false,
  };
  const parent = { ...projects[1], id: companion.parent_project_id, title: 'Event Horizon Showcase',
    category: 'replacement-showcase-candidate' };
  const expanded = { ...catalogue, projects: [...projects, parent], sets: [companion] };
  const described = describeNativeDemoCatalogue(expanded);
  assert.deepEqual(described.sets, [{ id: companion.id, title: companion.title,
    parentProjectId: companion.parent_project_id }]);
  const request = buildNativeDemoSelectionRequest(expanded, profile, [parent.id], 0, [companion.id]);
  assert.deepEqual(request.set_ids, [companion.id]);
  assert.equal(Object.keys(request).includes('source_path'), false);
  assert.throws(() => buildNativeDemoSelectionRequest(expanded, profile, [parent.id], 0, ['unknown-set']), /known companion SETs/);
  assert.throws(() => buildNativeDemoSelectionRequest(expanded, profile, [parent.id], 0, [companion.id, companion.id]), /Duplicate/);
  assert.throws(() => buildNativeDemoSelectionRequest(expanded, profile,
    [parent.id, 'legacy-example-afterglow-relay'], 1, [companion.id]), /startup project/);
  assert.throws(() => buildNativeDemoSelectionRequest(expanded, profile,
    ['legacy-example-afterglow-relay'], 0, [companion.id]), /startup project/);
  for (const bad of [
    { ...companion, dependency_scan_complete: true },
    { ...companion, parent_project_id: 'legacy-example-afterglow-relay' },
    { ...companion, source_dependency_scan_complete: true },
    { ...companion, id: 'caller-selected-path' },
  ]) {
    assert.throws(() => describeNativeDemoCatalogue({ ...expanded, sets: [bad] }), /unsupported companion SET/);
  }
});


test('explicit continuous profile preserves custom modules and selected startup project', () => {
  const request = buildNativeDemoSelectionRequest(catalogue, profile,
    ['legacy-example-event-horizon', 'legacy-example-afterglow-relay'], 1, [], {
      flash_layout: 'expanded-d7000', runtime_mode: 'continuous',
    });
  assert.deepEqual(request, { version: 1, engines: [...profile.engines], effects: ['plate'], midi: [],
    modulation: ['lfo'], project_ids: ['legacy-example-event-horizon', 'legacy-example-afterglow-relay'],
    startup_index: 1, flash_layout: 'expanded-d7000', runtime_mode: 'continuous' });
});
