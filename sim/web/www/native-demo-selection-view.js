// SPDX-License-Identifier: MIT
// Reusable chooser view for a future installer route. This module only builds
// the request accepted by the existing native preparation adapter; it does not
// fetch projects, build firmware, install, or make release claims.

import {
  buildNativeDemoSelectionRequest,
  describeNativeDemoCatalogue,
} from './native-demo-selection.js';

let instanceNumber = 0;
const PROPOSED_FULL_SONG_ID = 'replacement-showcase-candidate-event-horizon';

function text(document, tag, value, className) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = typeof value === 'string' ? value : '';
  return element;
}

function durationLabel(duration) {
  const seconds = duration && duration.nominal_seconds;
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) {
    return 'Duration estimate unavailable';
  }
  const whole = Math.round(seconds);
  const minutes = Math.floor(whole / 60);
  return `Estimated duration ${minutes}:${String(whole % 60).padStart(2, '0')}`;
}

function categoryLabel(project) {
  return project.category === 'legacy-example' ? 'Legacy example'
    : project.category === 'replacement-showcase-candidate' ? 'Showcase candidate' : 'Example project';
}

function selectionTitle(project) {
  return project.category === 'replacement-showcase-candidate'
    ? `${project.title || project.id} Showcase` : project.title || project.id;
}

function dispositionLabel(project) {
  const hostResult = {
    'legacy-example-afterglow-relay': 'Host startup diagnostic passed; hardware playback is unverified.',
    'legacy-example-packet-bloom': 'Host startup diagnostic passed; hardware playback is unverified.',
    'legacy-example-event-horizon': 'Host startup diagnostic refused allocation (report 5).',
    'legacy-example-neon-transit': 'Host startup diagnostic refused allocation (report 5).',
  }[project.id];
  return [project.owner_disposition || 'Owner disposition unavailable', hostResult]
    .filter(Boolean).join(' ');
}

/**
 * Mount an accessible native demo chooser into `root`.
 *
 * `onRequest` receives only the immutable request produced by
 * buildNativeDemoSelectionRequest. The caller owns transport and build steps.
 * Returns a small controller with destroy() for installer route teardown.
 */
export function mountNativeDemoSelectionView(root, catalogue, profile, onRequest) {
  if (!root || typeof root.append !== 'function' || !root.ownerDocument) {
    throw new TypeError('A DOM root element is required');
  }
  if (typeof onRequest !== 'function') throw new TypeError('onRequest must be a function');

  const document = root.ownerDocument;
  const view = describeNativeDemoCatalogue(catalogue);
  const instance = ++instanceNumber;
  const radioName = `native-demo-startup-${instance}`;
  const proposedFullSong = view.fullSongDefault.status === 'pending'
    ? view.projects.find((project) => project.id === PROPOSED_FULL_SONG_ID
      && project.category === 'replacement-showcase-candidate') : null;
  const selected = proposedFullSong ? [proposedFullSong.id] : [];
  const projectControls = new Map();
  let startupId = null;
  let busy = false;

  const section = text(document, 'section', undefined, 'native-demo-selection');
  section.setAttribute('aria-labelledby', `native-demo-title-${instance}`);
  const heading = text(document, 'h2', 'Choose demo projects');
  heading.id = `native-demo-title-${instance}`;
  section.append(heading);
  section.append(text(document, 'p',
    'Choose one or more examples, then explicitly choose which selected project opens first. Selection order is preserved.'));

  const defaultNotice = text(document, 'aside', undefined, 'native-demo-default-status');
  defaultNotice.setAttribute('role', 'note');
  defaultNotice.append(text(document, 'h3',
    `Full-song default status: ${view.fullSongDefault.status}`));
  defaultNotice.append(text(document, 'p', view.fullSongDefault.status === 'pending'
    ? 'Legacy examples remain selectable, but none are approved showcases or defaults. Event Horizon Showcase is preselected as the proposed full-song default for this request. This is a reversible chooser selection, not owner musical acceptance or release admission. Its 108.8-second host render completed in an offline diagnostic; packed dependency validation and musical review remain pending.'
    : 'Selectable legacy examples are not approved showcases or defaults.'));
  if (view.fullSongDefault.blockers.length) {
    const blockers = document.createElement('ul');
    for (const blocker of view.fullSongDefault.blockers) blockers.append(text(document, 'li', blocker));
    defaultNotice.append(blockers);
  }
  section.append(defaultNotice);

  const choices = document.createElement('fieldset');
  choices.append(text(document, 'legend', 'Available examples'));
  const startup = document.createElement('fieldset');
  startup.append(text(document, 'legend', 'Startup project'));
  const startupHint = text(document, 'p', 'Select at least one project, then choose its startup radio option.');
  startup.append(startupHint);
  const startupControls = new Map();

  function syncSubmit() {
    submit.disabled = busy || selected.length === 0 || startupId === null;
  }

  function addStartupOption(project) {
    const id = `native-demo-startup-option-${instance}-${startupControls.size}`;
    const label = document.createElement('label');
    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = radioName;
    radio.value = project.id;
    radio.disabled = true;
    radio.addEventListener('change', () => {
      startupId = radio.checked ? project.id : startupId;
      syncSubmit();
    });
    const title = text(document, 'span', `${selectionTitle(project)} (${categoryLabel(project)})`);
    label.htmlFor = id;
    radio.id = id;
    label.append(radio, title);
    startup.append(label);
    startupControls.set(project.id, radio);
  }

  for (const project of view.projects) {
    const label = document.createElement('label');
    const checkbox = document.createElement('input');
    const id = `native-demo-project-${instance}-${projectControls.size}`;
    checkbox.type = 'checkbox';
    checkbox.id = id;
    checkbox.value = project.id;
    checkbox.checked = project.id === proposedFullSong?.id;
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        if (!selected.includes(project.id)) selected.push(project.id);
        const radio = startupControls.get(project.id);
        radio.disabled = false;
      } else {
        const at = selected.indexOf(project.id);
        if (at !== -1) selected.splice(at, 1);
        const radio = startupControls.get(project.id);
        radio.checked = false;
        radio.disabled = true;
        if (startupId === project.id) startupId = null;
      }
      syncSubmit();
    });
    label.htmlFor = id;
    label.append(checkbox, text(document, 'strong', project.title || project.id));
    const item = document.createElement('article');
    item.append(label);
    item.append(text(document, 'p', durationLabel(project.duration_estimate)));
    item.append(text(document, 'p', categoryLabel(project)));
    item.append(text(document, 'p', dispositionLabel(project)));
    choices.append(item);
    projectControls.set(project.id, checkbox);
    addStartupOption(project);
    if (project.id === proposedFullSong?.id) {
      const radio = startupControls.get(project.id);
      radio.disabled = false;
      radio.checked = true;
      startupId = project.id;
    }
  }

  section.append(choices, startup);
  section.append(text(document, 'p',
    'Durations are catalogue estimates from project metadata, not verified playback lengths. The Event Horizon host render is an offline diagnostic and does not establish target playback, release approval, or installability.'));
  const status = text(document, 'p', '', 'native-demo-selection-status');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  const submit = text(document, 'button', 'Use this selection');
  submit.type = 'button';
  submit.disabled = true;
  submit.addEventListener('click', async () => {
    if (busy) return;
    status.textContent = '';
    if (!selected.length) {
      status.textContent = 'Select one or more projects before continuing.';
      return;
    }
    const startupIndex = selected.indexOf(startupId);
    if (startupIndex < 0) {
      status.textContent = 'Choose a startup project from the selected projects.';
      return;
    }
    try {
      const request = buildNativeDemoSelectionRequest(catalogue, profile, selected, startupIndex);
      busy = true;
      syncSubmit();
      status.textContent = 'Preparing selection…';
      await onRequest(request);
      status.textContent = 'Selection submitted.';
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : 'The selection is invalid.';
    } finally {
      busy = false;
      syncSubmit();
    }
  });
  syncSubmit();
  section.append(status, submit);
  root.append(section);

  return Object.freeze({
    destroy() { section.remove(); },
    getSelection() {
      return Object.freeze({ projectIds: Object.freeze([...selected]), startupId });
    },
  });
}
