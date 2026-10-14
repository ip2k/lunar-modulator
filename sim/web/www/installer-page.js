// SPDX-License-Identifier: MIT
// The trusted build exports this catalogue into the static Pages artifact.
// This route exports a request only; it does not call a build service.
import { mountNativeDemoSelectionView } from './native-demo-selection-view.js';
import { mountNativeModuleSelectionView } from './native-module-selection-view.js';

function downloadRequest(request, document, status) {
  const payload = `${JSON.stringify(request, null, 2)}\n`;
  const blob = new Blob([payload], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'lunar-build-request-v1.json';
  anchor.click();
  URL.revokeObjectURL(url);
  status.textContent = 'Request exported. No build or install was performed.';
}

function findButton(root) {
  for (const child of root.children ?? []) {
    if (child.tagName === 'BUTTON') return child;
    const nested = findButton(child);
    if (nested) return nested;
  }
  return null;
}

/** Load build-generated catalogue data and mount the shared validated chooser. */
export async function mountInstallerPage(root, {
  fetchImpl = globalThis.fetch,
} = {}) {
  if (!root || !root.ownerDocument || typeof root.append !== 'function') {
    throw new TypeError('A DOM root element is required');
  }
  if (typeof fetchImpl !== 'function') throw new TypeError('Catalogue fetch is unavailable');
  const document = root.ownerDocument;
  const status = document.getElementById?.('installer-export-status');
  const loading = document.getElementById?.('installer-load-status');
  const moduleRoot = document.getElementById?.('installer-modules');
  try {
    const response = await fetchImpl('./demo-image-catalogue.json', { cache: 'no-store' });
    if (!response?.ok) throw new Error('The generated project catalogue is unavailable.');
    const catalogue = await response.json();
    const profile = catalogue.default_profile;
    mountNativeModuleSelectionView(moduleRoot, catalogue, profile, (nextProfile) => {
      Object.assign(profile, nextProfile);
    });
    const demoRoot = document.getElementById?.('installer-selection') ?? root;
    const controller = mountNativeDemoSelectionView(demoRoot, catalogue, profile,
      (request) => {
        try {
          downloadRequest(request, document, status);
        } catch (error) {
          if (status) status.textContent = error instanceof Error
            ? `Request export failed: ${error.message}` : 'Request export failed.';
          throw error;
        }
      });
    const button = findButton(root);
    if (button) button.textContent = 'Download build request (JSON)';
    if (loading) loading.textContent = '';
    return controller;
  } catch (error) {
    if (loading) {
      loading.textContent = error instanceof Error
        ? error.message : 'The generated project catalogue could not be loaded.';
    }
    return null;
  }
}

if (typeof document !== 'undefined') {
  const root = document.getElementById('installer-selection');
  if (root) void mountInstallerPage(root);
}
