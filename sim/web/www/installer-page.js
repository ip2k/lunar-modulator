// SPDX-License-Identifier: MIT
// The trusted build exports this catalogue into the static Pages artifact.
// Build requests stay disabled unless a private deployment sets the explicit
// same-origin marker in installer.html.
import { BUILDER_GROUPS } from './native-build-selection.js';
import { buildNativeDemoSelectionRequest } from './native-demo-selection.js';
import { createInstallerBuildClient } from './installer-build-client.js';
import { mountNativeDemoSelectionView } from './native-demo-selection-view.js';
import { mountNativeModuleSelectionView } from './native-module-selection-view.js';
import { mountLocalPackageInspection } from './installer-package-inspection.js';
// GPL-3.0-only (see installer.html): the install flow links the fm1-ota module.
import { mountOtaInstallFlow } from './installer-ota-flow.js';

export const MAX_SAVED_REQUEST_BYTES = 65536;

/** Strictly reopen our v1 export; reject ambiguous duplicate JSON keys before normalization. */
export function parseSavedRequest(source, catalogue) {
  if (typeof source !== 'string' || source.length > MAX_SAVED_REQUEST_BYTES
      || new TextEncoder().encode(source).length > MAX_SAVED_REQUEST_BYTES) {
    throw new TypeError('Request file must be at most 64 KiB of UTF-8 JSON.');
  }
  const request = JSON.parse(source);
  // JSON.parse checks grammar; this bounded token pass only detects duplicate keys,
  // including escaped spellings, which JSON.parse would otherwise silently overwrite.
  const scopes = [];
  const tokens = /"(?:[^"\\]|\\.)*"|[{}\[\]]/g;
  for (const token of source.matchAll(tokens)) {
    if (token[0] === '{') scopes.push(new Set());
    else if (token[0] === '[') scopes.push(null);
    else if (token[0] === '}' || token[0] === ']') scopes.pop();
    else if (/^\s*:/.test(source.slice(token.index + token[0].length))) {
      const key = JSON.parse(token[0]);
      const keys = scopes.at(-1);
      if (keys.has(key)) throw new TypeError('Duplicate request field: ' + key);
      keys.add(key);
    }
  }
  const required = ['version', ...BUILDER_GROUPS, 'project_ids', 'startup_index'];
  const allowed = [...required, 'set_ids', 'flash_layout', 'runtime_mode'];
  if (!request || typeof request !== 'object' || Array.isArray(request)
      || request.version !== 1 || BUILDER_GROUPS.some(group => !Array.isArray(request[group]))
      || required.some(key => !Object.hasOwn(request, key))
      || Object.keys(request).some(key => !allowed.includes(key))
      || Object.hasOwn(request, 'flash_layout') !== Object.hasOwn(request, 'runtime_mode')) {
    throw new TypeError('Expected an exact version-1 Lunar build request.');
  }
  const configuration = Object.hasOwn(request, 'runtime_mode') ? {
    flash_layout: request.flash_layout, runtime_mode: request.runtime_mode,
  } : undefined;
  // An explicit null is invalid, rather than the builder's optional default.
  if (Object.hasOwn(request, 'set_ids') && !Array.isArray(request.set_ids)) {
    throw new TypeError('Companion SET IDs must be an array.');
  }
  return buildNativeDemoSelectionRequest(catalogue, request, request.project_ids,
    request.startup_index, request.set_ids, configuration);
}

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
  buildConfiguration = undefined,
  otaOptions = {},
} = {}) {
  if (!root || !root.ownerDocument || typeof root.append !== 'function') {
    throw new TypeError('A DOM root element is required');
  }
  if (typeof fetchImpl !== 'function') throw new TypeError('Catalogue fetch is unavailable');
  const document = root.ownerDocument;
  const serviceMarker = document.querySelector?.('meta[name="lunar-installer-build-service"]');
  const serviceEnabled = serviceMarker?.getAttribute?.('content') === 'enabled';
  if (buildClient === null && serviceEnabled) {
    const origin = document.defaultView?.location?.origin ?? globalThis.location?.origin;
    if (typeof origin === 'string') {
      buildClient = createInstallerBuildClient({ fetchImpl, origin });
    }
  }
  const status = document.getElementById?.('installer-export-status');
  const receiptSummary = document.createElement('section');
  receiptSummary.className = 'installer-receipt-preview';
  receiptSummary.setAttribute('role', 'status');
  receiptSummary.setAttribute('aria-label', 'Verified private build receipt preview');
  receiptSummary.hidden = true;
  const loading = document.getElementById?.('installer-load-status');
  const moduleRoot = document.getElementById?.('installer-modules');
  const cancelButton = document.getElementById?.('installer-cancel-build');
  const serviceNotice = document.getElementById?.('installer-service-notice');
  const profileSelect = document.getElementById?.('installer-build-profile');
  let selectedBuildConfiguration = buildConfiguration;
  // The install flow does not depend on the catalogue, so it mounts before the fetch below.
  const otaRoot = document.getElementById?.('installer-ota-flow');
  const otaFlow = otaRoot ? mountOtaInstallFlow(otaRoot, otaOptions) : null;
  const packageInspectionRoot = document.getElementById?.('installer-package-inspection');
  const packageInspection = packageInspectionRoot
    ? mountLocalPackageInspection(packageInspectionRoot,
      otaFlow ? { onPackage: (offered) => { void otaFlow.receivePackage(offered); } } : {}) : null;
  if (buildClient !== null && typeof buildClient.build !== 'function') {
    throw new TypeError('buildClient must provide a build method');
  }
  let activeBuild = null;
  let selectionRevision = 0;
  const selectionChangedMessage = 'Selection changed. Request a new build to measure flash usage.';
  function selectionChanged() {
    selectionRevision++;
    receiptSummary.textContent = '';
    receiptSummary.hidden = true;
    if (status) status.textContent = buildClient
      ? selectionChangedMessage : 'Selection changed. Export a new build request for these choices.';
  }
  if (profileSelect) {
    if (buildConfiguration?.runtime_mode) profileSelect.value = buildConfiguration.runtime_mode;
    profileSelect.addEventListener('change', () => {
      selectedBuildConfiguration = profileSelect.value === 'legacy' ? undefined : {
        flash_layout: 'expanded-d7000', runtime_mode: profileSelect.value,
      };
      selectionChanged();
    });
  }
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
    const moduleController = mountNativeModuleSelectionView(moduleRoot, catalogue, profile, (nextProfile) => {
      Object.assign(profile, nextProfile);
      selectionChanged();
    });
    const demoRoot = document.getElementById?.('installer-selection') ?? root;
    const controller = mountNativeDemoSelectionView(demoRoot, catalogue, profile,
      (request) => {
        if (buildClient) {
          const label = request.runtime_mode === 'continuous' ? 'Continuous private link' : 'Diagnostic build';
          const submittedRevision = selectionRevision;
          activeBuild = new AbortController();
          if (cancelButton) cancelButton.hidden = false;
          if (serviceNotice) serviceNotice.textContent = `${label} returns a measured summary only. It does not provide installable firmware.`;
          if (status) status.textContent = `Submitting the selected ${label.toLowerCase()}…`;
          receiptSummary.textContent = '';
          receiptSummary.hidden = true;
          return buildClient.build(request, {
            signal: activeBuild.signal,
            onProgress: (phase) => {
              if (!status || submittedRevision !== selectionRevision) return;
              status.textContent = phase === 'queued' ? 'Build request queued…'
                : phase === 'running' ? `Checking the ${label.toLowerCase()}…`
                  : `${label} result verified.`;
            },
          }).then((result) => {
            if (submittedRevision !== selectionRevision) throw new Error(selectionChangedMessage);
            if (status) status.textContent = `${label} checks passed. Application flash: ${result.artifactBytes.toLocaleString()} / ${result.appBudgetBytes.toLocaleString()} bytes used; ${result.remainingBytes.toLocaleString()} bytes free. No installable firmware file is available.`;
            const preview = result.receiptPreview;
            if (preview) {
              const startup = preview.projects.find(project => project.startup)?.id;
              const lines = [
                `Profile: ${preview.profile.profile_id ?? preview.runtimeMode} · ${preview.flashLayout}`,
                `Modules (${preview.modules.length}): ${preview.modules.join(', ')}`,
                `Project order: ${preview.projects.map(project => project.id).join(', ')}`,
                `Startup project: ${startup}`,
                `Companion SETs: ${preview.sets.length ? preview.sets.map(set => `${set.id} → ${set.parentProjectId}`).join(', ') : 'none'}`,
                `Packed content: ${preview.packedContentBytes.toLocaleString()} bytes`,
                ...preview.assets.map(asset => `  ${asset.kind} ${asset.id}: ${asset.bytes.toLocaleString()} bytes · SHA-256 ${asset.sha256}`),
                `Application: ${preview.application.bytes.toLocaleString()} bytes · SHA-256 ${preview.application.sha256}`,
                `Provenance receipt: ${preview.provenance.kind} · SHA-256 ${preview.provenance.sha256}`,
                'Packed-content hashes are reported by the verified service; this browser cannot independently derive them from the catalogue.',
              ];
              receiptSummary.textContent = '';
              const heading = document.createElement('h3');
              heading.textContent = 'Private build receipt preview · service-verified summary · not installable';
              receiptSummary.append(heading);
              for (const line of lines) {
                const detail = document.createElement('p');
                detail.textContent = line;
                receiptSummary.append(detail);
              }
              receiptSummary.hidden = false;
            }
          }).catch((error) => {
            if (submittedRevision !== selectionRevision) {
              if (status) status.textContent = selectionChangedMessage;
              throw new Error(selectionChangedMessage);
            }
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
      }, () => selectedBuildConfiguration, selectionChanged);
    const importFile = document.getElementById?.('installer-request-file');
    const importButton = document.getElementById?.('installer-request-load');
    const importStatus = document.getElementById?.('installer-request-status');
    let destroyed = false;
    let reading = false;
    function restoreRequest(source) {
      if (destroyed) throw new Error('The customization page has been closed.');
      const request = parseSavedRequest(source, catalogue);
      const commitModules = moduleController.prepareRestore(request);
      const commitDemos = controller.prepareRestore(request, request);
      // Every operation that can reject has completed. Commits have no callbacks.
      commitModules();
      commitDemos();
      Object.assign(profile, moduleController.getProfile());
      selectedBuildConfiguration = request.runtime_mode === undefined ? undefined : {
        flash_layout: request.flash_layout, runtime_mode: request.runtime_mode,
      };
      if (profileSelect) profileSelect.value = request.runtime_mode ?? 'legacy';
      selectionChanged();
      return request;
    }
    if (importButton && importFile && importStatus) {
      importButton.disabled = false;
      importButton.addEventListener('click', async () => {
        if (reading || destroyed) return;
        reading = true;
        importButton.disabled = true;
        const revision = selectionRevision;
        try {
          const files = importFile.files;
          if (!files || files.length !== 1) throw new Error('Choose one saved request JSON file.');
          const file = files[0];
          if (!Number.isSafeInteger(file.size) || file.size < 0 || file.size > MAX_SAVED_REQUEST_BYTES) {
            throw new Error('Request file must be at most 64 KiB.');
          }
          const source = await file.text();
          if (revision !== selectionRevision) throw new Error('Choices changed while reading. Load the file again to replace them.');
          restoreRequest(source);
          importStatus.textContent = 'Request loaded. No build or install was performed.';
        } catch (error) {
          if (!destroyed) importStatus.textContent = `Request not loaded: ${error instanceof Error ? error.message : 'Unable to read JSON.'} Previous choices are unchanged.`;
        } finally {
          reading = false;
          if (!destroyed) importButton.disabled = false;
        }
      });
    }
    const button = findButton(root);
    root.append(receiptSummary);
    if (button) button.textContent = buildClient
      ? 'Request private build check' : 'Download build request (JSON)';
    if (buildClient && serviceNotice) {
      serviceNotice.textContent = 'Private build checks are enabled for this origin. Availability is checked when you submit. Results do not establish installability or hardware acceptance.';
    }
    if (loading) loading.textContent = '';
    return Object.freeze({
      destroy() {
        destroyed = true;
        if (importButton) importButton.disabled = true;
        controller.destroy(); moduleController.destroy(); packageInspection?.destroy(); otaFlow?.destroy();
      },
      restoreRequest,
      getRequest() {
        const selection = controller.getSelection();
        return buildNativeDemoSelectionRequest(catalogue, profile, selection.projectIds,
          selection.projectIds.indexOf(selection.startupId), selection.setIds, selectedBuildConfiguration);
      },
      getSelection() { return controller.getSelection(); },
    });
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
