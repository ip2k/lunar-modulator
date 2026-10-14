// SPDX-License-Identifier: MIT
// Build the narrow native demo-selection request without coupling to simulator state.

import { BUILDER_GROUPS, validateNativeBuildSelection } from './native-build-selection.js';

const fail = (message) => { throw new TypeError(message); };
const RESERVATIONS = Object.freeze({
  'replacement-showcase-candidate-event-horizon': Object.freeze({
    status: 'allocator-fit',
    label: 'The recorded playback-memory check passed; device playback remains unverified.',
  }),
  'replacement-showcase-candidate-afterglow-relay': Object.freeze({
    status: 'allocator-fit',
    label: 'The recorded playback-memory check passed; device playback remains unverified.',
  }),
  'replacement-showcase-candidate-packet-bloom': Object.freeze({
    status: 'rejected',
    label: 'This arrangement exceeds available playback memory.',
  }),
  'replacement-showcase-candidate-satellite-hearts': Object.freeze({
    status: 'rejected',
    label: 'Unavailable with the current voice count.',
  }),
});

function reservationFor(project) {
  return RESERVATIONS[project.id] || Object.freeze({
    status: 'pending',
    label: 'Current-profile allocation reservation has not been established.',
  });
}
const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

function checkedProjects(catalogue) {
  if (!isRecord(catalogue) || catalogue.version !== 1 || !Array.isArray(catalogue.projects)) {
    fail('Unsupported native demo catalogue');
  }
  const ids = new Set();
  for (const project of catalogue.projects) {
    if (!isRecord(project) || typeof project.id !== 'string' || !project.id
        || ids.has(project.id)) {
      fail('Invalid or duplicate native demo project ID');
    }
    ids.add(project.id);
  }
  const fullSongDefault = catalogue.full_song_default;
  if (!isRecord(fullSongDefault) || fullSongDefault.required !== true
      || typeof fullSongDefault.status !== 'string' || !Array.isArray(fullSongDefault.blockers)
      || fullSongDefault.blockers.some((blocker) => typeof blocker !== 'string')) {
    fail('Invalid full-song default disposition');
  }
  return { ids, fullSongDefault };
}

/** Return UI-safe catalogue facts without implying approval or default admission. */
export function describeNativeDemoCatalogue(catalogue) {
  const { fullSongDefault } = checkedProjects(catalogue);
  const projects = catalogue.projects.map((project) => Object.freeze({
    id: project.id,
    title: project.title,
    category: project.category,
    duration_estimate: project.duration_estimate,
    owner_disposition: project.owner_disposition,
    default_candidate: project.default_candidate,
    reservation: reservationFor(project),
  }));
  return Object.freeze({
    projects: Object.freeze(projects),
    fullSongDefault: Object.freeze({
      required: fullSongDefault.required,
      status: fullSongDefault.status,
      blockers: Object.freeze([...fullSongDefault.blockers]),
    }),
  });
}

/** Build the exact version-1 request accepted by prepare_demo_selection.py.
 * Project bytes, paths, hashes and dependencies remain backend-owned.
 */
export function buildNativeDemoSelectionRequest(catalogue, profile, projectIds, startupIndex) {
  const { ids } = checkedProjects(catalogue);
  // Reuse the established module validator; no client-supplied packed metadata
  // is passed, so dependency resolution remains a backend preparation gate.
  const modules = validateNativeBuildSelection(catalogue, profile);
  if (!Array.isArray(projectIds) || projectIds.length === 0
      || projectIds.some((id) => typeof id !== 'string' || !ids.has(id))) {
    fail('Select one or more known native demo project IDs');
  }
  if (new Set(projectIds).size !== projectIds.length) fail('Duplicate selected demo project ID');
  const rejected = projectIds.filter((id) => reservationFor({ id }).status === 'rejected');
  if (rejected.length) {
    const names = rejected.map((id) => catalogue.projects.find((project) => project.id === id)?.title || id);
    fail(`Unavailable under the current profile: ${names.join(', ')}`);
  }
  if (typeof startupIndex !== 'number' || !Number.isSafeInteger(startupIndex)
      || startupIndex < 0 || startupIndex >= projectIds.length) {
    fail('Startup index must select an ordered project');
  }

  const request = { version: 1 };
  for (const group of BUILDER_GROUPS) request[group] = Object.freeze([...modules.selectedByGroup[group]]);
  request.project_ids = Object.freeze([...projectIds]);
  request.startup_index = startupIndex;
  return Object.freeze(request);
}
