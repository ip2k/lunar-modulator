// SPDX-License-Identifier: MIT
// Reusable chooser view for a future installer route. This module only builds
// the request accepted by the existing native preparation adapter; it does not
// fetch projects, build firmware, install, or make release claims.

import {
  buildNativeDemoSelectionRequest,
  describeNativeDemoCatalogue,
} from './native-demo-selection.js';

let instanceNumber = 0;

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
  const selected = [];
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
    ? 'No full-song default has been approved. Legacy examples are not approved showcases or defaults. Showcase candidates await musical review.'
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
    const title = text(document, 'span', `${project.title || project.id} (${categoryLabel(project)})`);
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
    item.append(text(document, 'p', project.owner_disposition || 'Owner disposition unavailable'));
    choices.append(item);
    projectControls.set(project.id, checkbox);
    addStartupOption(project);
  }

  section.append(choices, startup);
  section.append(text(document, 'p',
    'Durations are catalogue estimates from project metadata, not verified playback lengths.'));
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
  section.append(status, submit);
  root.append(section);

  return Object.freeze({
    destroy() { section.remove(); },
    getSelection() {
      return Object.freeze({ projectIds: Object.freeze([...selected]), startupId });
    },
  });
}
