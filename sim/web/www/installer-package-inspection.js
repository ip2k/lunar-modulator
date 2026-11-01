// SPDX-License-Identifier: MIT
// Local package diagnostics only. File bytes stay in this page and never gain
// an install, download, or release-admission capability.
import { inspectNativePackage } from './native-package-admission.js';

export const MAX_INSPECTABLE_PACKAGE_BYTES = 2 * 1024 * 1024;

function describeInspection(file, inspection) {
  const lines = [
    `File: ${file.name || 'selected package'} (${file.size.toLocaleString()} bytes)`,
    `Format: ${inspection.kind}${inspection.identity ? ` · ${inspection.identity}` : ''}`,
  ];
  const envelope = inspection.envelope;
  if (envelope) {
    lines.push(`FWSC header CRC: ${envelope.headerCrcVerified ? 'passed' : 'not verified'}`);
    lines.push(`FWSC entry-list CRC: ${envelope.entryListCrcVerified ? 'passed' : 'not verified'}`);
    lines.push(`Entries: ${envelope.entries.map((entry) =>
      `${entry.name} (${entry.bytes.toLocaleString()} bytes, CRC ${entry.crcVerified ? 'passed' : 'not verified'})`).join('; ')}`);
    const nested = envelope.nestedInspection;
    lines.push(`Nested flash: ${nested.status === 'structure-crc-verified'
      ? `${nested.profile} structure and CRC checks passed`
      : nested.status === 'unsupported-profile' ? 'profile unsupported; not verified' : 'not verified'}`);
    if (nested.status === 'structure-crc-verified') {
      lines.push(`Flash region: ${nested.flashBytes.toLocaleString()} bytes; app record: ${nested.appBytes.toLocaleString()} bytes`);
    }
  } else if (inspection.reason) {
    lines.push(`Inspection: ${inspection.reason}`);
  }
  lines.push('Release admission: not established. Installation is unavailable.');
  return lines.join('\n');
}

/** Add a bounded local-file inspection panel. No bytes leave this page. */
export function mountLocalPackageInspection(root, {
  inspect = inspectNativePackage,
  maxBytes = MAX_INSPECTABLE_PACKAGE_BYTES,
} = {}) {
  if (!root?.ownerDocument || typeof root.append !== 'function') {
    throw new TypeError('A DOM root element is required');
  }
  if (typeof inspect !== 'function' || !Number.isSafeInteger(maxBytes)
      || maxBytes < 1 || maxBytes > MAX_INSPECTABLE_PACKAGE_BYTES) {
    throw new TypeError('Package inspection configuration is invalid');
  }

  const document = root.ownerDocument;
  const section = document.createElement('section');
  section.className = 'installer-package-inspection';
  const heading = document.createElement('h2');
  heading.textContent = 'Inspect a firmware package';
  const description = document.createElement('p');
  description.textContent = 'Checks run locally in this page. They do not establish release admission or installability.';
  const label = document.createElement('label');
  label.textContent = 'Choose an FWSC package (maximum 2 MiB) ';
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.fwsc,application/octet-stream';
  input.setAttribute('aria-label', 'Choose an FWSC package to inspect');
  label.append(input);
  const clear = document.createElement('button');
  clear.type = 'button';
  clear.textContent = 'Clear package';
  const report = document.createElement('pre');
  report.setAttribute('role', 'status');
  report.setAttribute('aria-live', 'polite');
  report.textContent = 'No package selected.';
  section.append(heading, description, label, clear, report);
  root.append(section);

  let generation = 0;
  const clearCurrent = (message = 'No package selected.') => {
    generation += 1;
    report.textContent = message;
  };
  input.addEventListener('change', async () => {
    const currentGeneration = ++generation;
    report.textContent = 'Inspecting selected file locally…';
    const file = input.files?.[0];
    if (!file) {
      report.textContent = 'No package selected.';
      return;
    }
    if (!Number.isSafeInteger(file.size) || file.size < 1 || file.size > maxBytes) {
      report.textContent = `Package must be between 1 byte and ${maxBytes.toLocaleString()} bytes.`;
      input.value = '';
      return;
    }
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (currentGeneration !== generation) return;
      if (bytes.byteLength !== file.size) throw new Error('File read length differs from the selected size.');
      const inspection = inspect(bytes);
      if (currentGeneration !== generation) return;
      report.textContent = describeInspection(file, inspection);
    } catch (error) {
      if (currentGeneration === generation) {
        report.textContent = `Inspection could not be completed: ${error instanceof Error ? error.message : 'invalid package data'}. Release admission remains closed.`;
      }
    }
  });
  clear.addEventListener('click', () => {
    clearCurrent();
    input.value = '';
  });
  input.addEventListener('cancel', () => {
    clearCurrent();
    input.value = '';
  });

  return Object.freeze({
    clear() { clearCurrent(); input.value = ''; },
    destroy() { clearCurrent(); section.remove(); },
  });
}
