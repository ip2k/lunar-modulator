// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildNativeDemoSelectionRequest,
  describeNativeDemoCatalogue,
} from '../www/native-demo-selection.js';

const projects = [
  { id: 'legacy-example-afterglow-relay', title: 'Afterglow Relay', category: 'legacy-example',
    duration_estimate: { nominal_seconds: 198.261 },
    owner_disposition: 'legacy example; not approved as a showcase or default', default_candidate: false,
    source_path: '../must-not-enter-request.lunar', source_sha256: 'a'.repeat(64) },
  { id: 'legacy-example-event-horizon', title: 'Event Horizon', category: 'legacy-example',
    duration_estimate: { nominal_seconds: 193.333 },
    owner_disposition: 'legacy example; not approved as a showcase or default', default_candidate: false,
    source_path: 'engines/state/examples/event-horizon.lunar', source_sha256: 'b'.repeat(64) },
];
const catalogue = {
  version: 1,
  groups: { engines: ['macro', 'shapes'], effects: ['plate'], midi: ['arp'], modulation: ['lfo'] },
  projects,
  full_song_default: { required: true, status: 'pending', blockers: ['owner-approved full-song composition'] },
};
const profile = { version: 1, engines: ['macro', 'shapes'], effects: ['plate'], midi: [], modulation: ['lfo'] };

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
    ['category', 'default_candidate', 'duration_estimate', 'id', 'owner_disposition', 'title'].sort());
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
