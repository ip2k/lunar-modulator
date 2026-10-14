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
  buildClient = null,
} = {}) {
  if (!root || !root.ownerDocument || typeof root.append !== 'function') {
    throw new TypeError('A DOM root element is required');
  }
  if (typeof fetchImpl !== 'function') throw new TypeError('Catalogue fetch is unavailable');
  const document = root.ownerDocument;
  const status = document.getElementById?.('installer-export-status');
  const loading = document.getElementById?.('installer-load-status');
  const moduleRoot = document.getElementById?.('installer-modules');
  const cancelButton = document.getElementById?.('installer-cancel-build');
  const serviceNotice = document.getElementById?.('installer-service-notice');
  if (buildClient !== null && typeof buildClient.build !== 'function') {
    throw new TypeError('buildClient must provide a build method');
  }
  let activeBuild = null;
  if (cancelButton) {
    cancelButton.hidden = true;
    cancelButton.addEventListener('click', () => {
      activeBuild?.abort();
      if (status) status.textContent = 'Stopped waiting for this build. The server may continue processing it.';
      cancelButton.hidden = true;
    });
  }
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
        if (buildClient) {
          activeBuild = new AbortController();
          if (cancelButton) cancelButton.hidden = false;
          if (serviceNotice) serviceNotice.textContent = 'This service returns a private diagnostic result only. It does not provide installable firmware.';
          if (status) status.textContent = 'Submitting the selected diagnostic build…';
          return buildClient.build(request, {
            signal: activeBuild.signal,
            onProgress: (phase) => {
              if (!status) return;
              status.textContent = phase === 'queued' ? 'Build request queued…'
                : phase === 'running' ? 'Checking the private diagnostic build…'
                  : 'Diagnostic result verified.';
            },
          }).then((result) => {
            if (status) status.textContent = `Diagnostic build checks passed. Application flash: ${result.artifactBytes.toLocaleString()} / ${result.appBudgetBytes.toLocaleString()} bytes used; ${result.remainingBytes.toLocaleString()} bytes free. No installable firmware file is available.`;
          }).catch((error) => {
            if (status) status.textContent = activeBuild?.signal.aborted
              ? 'Stopped waiting for this build. The server may continue processing it.'
              : error instanceof Error ? error.message : 'The diagnostic build could not be completed.';
            throw error;
          }).finally(() => {
            activeBuild = null;
            if (cancelButton) cancelButton.hidden = true;
          });
        }
        try {
          downloadRequest(request, document, status);
        } catch (error) {
          if (status) status.textContent = error instanceof Error
            ? `Request export failed: ${error.message}` : 'Request export failed.';
          throw error;
        }
      });
    const button = findButton(root);
    if (button) button.textContent = buildClient
      ? 'Request diagnostic build' : 'Download build request (JSON)';
    if (buildClient && serviceNotice) {
      serviceNotice.textContent = 'Private diagnostic build service connected. Results do not establish installability or hardware acceptance.';
    }
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
