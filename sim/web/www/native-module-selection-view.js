// SPDX-License-Identifier: MIT
import { BUILDER_GROUPS, validateNativeBuildSelection } from './native-build-selection.js';

const GROUP_NAMES = Object.freeze({
  engines: 'Sound engines', effects: 'Effects', midi: 'MIDI processors', modulation: 'Modulation',
});
let instanceCount = 0;

/** Native controls for catalogue-owned modules; changes are validated atomically. */
export function mountNativeModuleSelectionView(root, catalogue, profile, onChange) {
  if (!root?.ownerDocument || typeof root.append !== 'function'
      || typeof onChange !== 'function') throw new TypeError('A DOM root and change handler are required');
  const initial = validateNativeBuildSelection(catalogue, profile);
  const document = root.ownerDocument;
  const instance = ++instanceCount;
  const section = document.createElement('section');
  section.className = 'native-module-selection';
  const heading = document.createElement('h2');
  heading.textContent = 'Choose engines and effects';
  section.append(heading);
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  const controls = new Map();
  let current = { version: 1, ...initial.selectedByGroup };

  function snapshot() {
    return snapshotFrom(current);
  }

  for (const group of BUILDER_GROUPS) {
    const fieldset = document.createElement('fieldset');
    const legend = document.createElement('legend');
    legend.textContent = GROUP_NAMES[group];
    fieldset.append(legend);
    for (const [index, id] of catalogue.groups[group].entries()) {
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = id;
      input.id = `native-module-${instance}-${group}-${index}`;
      input.checked = current[group].includes(id);
      label.htmlFor = input.id;
      const name = document.createElement('span');
      name.textContent = id;
      label.append(input, name);
      fieldset.append(label);
      controls.set(id, input);
      input.addEventListener('change', () => {
        const candidate = snapshot();
        candidate[group] = catalogue.groups[group].filter(module => controls.get(module).checked);
        try {
          validateNativeBuildSelection(catalogue, candidate);
          onChange(snapshotFrom(candidate));
          current = candidate;
          status.textContent = '';
        } catch (error) {
          input.checked = current[group].includes(id);
          status.textContent = error instanceof Error ? error.message : 'The module selection is invalid.';
        }
      });
    }
    section.append(fieldset);
  }
  section.append(status);
  root.append(section);
  return Object.freeze({ getProfile: snapshot, destroy() { section.remove(); } });
}

function snapshotFrom(profile) {
  return { version: 1, ...Object.fromEntries(BUILDER_GROUPS.map(group => [group, [...profile[group]]])) };
}
