// SPDX-License-Identifier: MIT
// Build the narrow native demo-selection request without coupling to simulator state.

import {
  BUILDER_GROUPS, missingD7000ProfileModules, validateNativeBuildSelection,
} from './native-build-selection.js';

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

const TRUSTED_SETS = Object.freeze({
  'replacement-showcase-event-horizon-companion-set': 'replacement-showcase-candidate-event-horizon',
});

function checkedProjects(catalogue) {
  if (!isRecord(catalogue) || catalogue.version !== 1 || !Array.isArray(catalogue.projects)) {
    fail('Unsupported native demo catalogue');
  }
  if (!isRecord(catalogue.groups)) fail('Invalid native demo module catalogue');
  for (const group of BUILDER_GROUPS) {
    if (!Array.isArray(catalogue.groups[group])
        || catalogue.groups[group].some((id) => typeof id !== 'string' || !id)
        || new Set(catalogue.groups[group]).size !== catalogue.groups[group].length) {
      fail('Invalid native demo module group: ' + group);
    }
  }
  const ids = new Set();
  for (const project of catalogue.projects) {
    if (!isRecord(project) || typeof project.id !== 'string' || !project.id
        || ids.has(project.id)) {
      fail('Invalid or duplicate native demo project ID');
    }
    const sourceDependencies = project.source_module_dependencies;
    if (project.source_dependency_scan_complete !== true || !isRecord(sourceDependencies)
        || BUILDER_GROUPS.some((group) => !Array.isArray(sourceDependencies[group])
          || sourceDependencies[group].some((id) => typeof id !== 'string' || !id
            || !catalogue.groups[group].includes(id))
          || new Set(sourceDependencies[group]).size !== sourceDependencies[group].length)) {
      fail('Project dependency preflight metadata is unavailable; refresh the catalogue');
    }
    ids.add(project.id);
  }
  const projectIds = ids;
  const sets = catalogue.sets ?? [];
  if (!Array.isArray(sets) || sets.length > 8) fail('Invalid native demo SET catalogue');
  const setIds = new Set();
  for (const set of sets) {
    const expectedParent = isRecord(set) ? TRUSTED_SETS[set.id] : null;
    if (!expectedParent || setIds.has(set.id) || typeof set.title !== 'string'
        || !projectIds.has(set.parent_project_id) || set.parent_project_id !== expectedParent
        || set.source_dependency_scan_complete !== false || set.dependency_scan_complete !== false) {
      fail('Invalid or unsupported companion SET metadata');
    }
    setIds.add(set.id);
  }
  const fullSongDefault = catalogue.full_song_default;
  if (!isRecord(fullSongDefault) || fullSongDefault.required !== true
      || typeof fullSongDefault.status !== 'string' || !Array.isArray(fullSongDefault.blockers)
      || fullSongDefault.blockers.some((blocker) => typeof blocker !== 'string')) {
    fail('Invalid full-song default disposition');
  }
  return { ids, sets, setIds, fullSongDefault };
}

/** Return UI-safe catalogue facts; musical approval remains separate from image admission. */
export function describeNativeDemoCatalogue(catalogue) {
  const { fullSongDefault, sets } = checkedProjects(catalogue);
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
    sets: Object.freeze(sets.map((set) => Object.freeze({
      id: set.id, title: set.title, parentProjectId: set.parent_project_id,
    }))),
    fullSongDefault: Object.freeze({
      required: fullSongDefault.required,
      status: fullSongDefault.status,
      musicalChoiceApproved: fullSongDefault.musical_choice_approved === true,
      projectId: fullSongDefault.project_id,
      blockers: Object.freeze([...fullSongDefault.blockers]),
    }),
  });
}

/** Build the version-1 selection request accepted by the native preparer.
 * Optional build configuration carries only the fixed D7000 song-diagnostic
 * pair; project bytes, paths, hashes and dependencies remain backend-owned.
 */
export function buildNativeDemoSelectionRequest(catalogue, profile, projectIds, startupIndex,
  setIds = [], buildConfiguration = undefined) {
  const { ids, setIds: knownSetIds, sets } = checkedProjects(catalogue);
  // The source-hash-bound catalogue provides immediate UX feedback. The backend
  // independently validates exact packed records before it writes a receipt.
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
  const missingByGroup = Object.fromEntries(BUILDER_GROUPS.map((group) => [group, new Set()]));
  for (const id of projectIds) {
    const project = catalogue.projects.find((item) => item.id === id);
    for (const group of BUILDER_GROUPS) {
      for (const dependency of project.source_module_dependencies[group]) {
        if (!modules.selectedByGroup[group].includes(dependency)) missingByGroup[group].add(dependency);
      }
    }
  }
  const missing = BUILDER_GROUPS
    .filter((group) => missingByGroup[group].size)
    .map((group) => `${group}: ${[...missingByGroup[group]].sort().join(', ')}`);
  if (missing.length) {
    const names = projectIds.map((id) => catalogue.projects.find((project) => project.id === id)?.title || id);
    fail(`Selected projects need omitted modules (${missing.join('; ')}). Enable these modules or remove the selected project${names.length === 1 ? '' : 's'}: ${names.join(', ')}`);
  }
  if (typeof startupIndex !== 'number' || !Number.isSafeInteger(startupIndex)
      || startupIndex < 0 || startupIndex >= projectIds.length) {
    fail('Startup index must select an ordered project');
  }

  if (!Array.isArray(setIds) || setIds.length > 8
      || setIds.some((id) => typeof id !== 'string' || !knownSetIds.has(id))) {
    fail('Select only known companion SETs');
  }
  if (new Set(setIds).size !== setIds.length) fail('Duplicate selected companion SET ID');
  for (const id of setIds) {
    const companion = sets.find((set) => set.id === id);
    if (!projectIds.includes(companion.parent_project_id)
        || projectIds[startupIndex] !== companion.parent_project_id) {
      fail('A companion SET requires its parent project as the startup project');
    }
  }

  if (buildConfiguration !== undefined) {
    const keys = ['flash_layout', 'runtime_mode'];
    if (buildConfiguration === null || typeof buildConfiguration !== 'object'
        || Array.isArray(buildConfiguration)
        || (Object.getPrototypeOf(buildConfiguration) !== Object.prototype
          && Object.getPrototypeOf(buildConfiguration) !== null)
        || Object.keys(buildConfiguration).length !== keys.length
        || keys.some((key) => !Object.hasOwn(buildConfiguration, key))
        || buildConfiguration.flash_layout !== 'expanded-d7000'
        || buildConfiguration.runtime_mode !== 'song-diagnostic'
        || Object.values(missingD7000ProfileModules(modules.selectedByGroup))
          .some((missing) => missing.length > 0)) {
      fail('The explicit native build configuration is invalid');
    }
  }

  const request = { version: 1 };
  for (const group of BUILDER_GROUPS) request[group] = Object.freeze([...modules.selectedByGroup[group]]);
  request.project_ids = Object.freeze([...projectIds]);
  request.startup_index = startupIndex;
  if (setIds.length) request.set_ids = Object.freeze([...setIds]);
  if (buildConfiguration !== undefined) {
    request.flash_layout = buildConfiguration.flash_layout;
    request.runtime_mode = buildConfiguration.runtime_mode;
  }
  return Object.freeze(request);
}
