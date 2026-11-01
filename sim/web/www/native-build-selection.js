// Pure request validation for the future native image builder UI.
// This validates catalogue choices and packed-input bounds; it does not build
// or admit a firmware image. Keep it independent of the simulator state.

export const BUILDER_GROUPS = Object.freeze(['engines', 'effects', 'midi', 'modulation']);
export const CONTENT_LIMITS = Object.freeze({
  maxAssets: 64,
  minPackedFileBytes: 32,
  maxPackedFileBytes: 98304,
  maxPackedTotalBytes: 1048576,
});

// Must match tools/native/diagnostic_profile_contract.py. These are explicit
// caller-selected groups for the fixed private Hall O2 stage7 profile.
export const D7000_REQUIRED_BY_GROUP = Object.freeze({
  engines: Object.freeze(['macro', 'shapes', 'sixop', 'drums']),
  effects: Object.freeze(['hall']),
});

// Cross-language policy binding is checked in test_installer_continuous_profile.py.
export const CONTINUOUS_BUILD_PROFILE = Object.freeze({
  profileId: 'fm1-500-d7000-continuous-selected-v1',
  profileSha256: 'fcfba36ad8d98a15367db8d5ad0e9959e879238a2122940d215d702baff6fce0',
});

export function missingD7000ProfileModules(selectedByGroup) {
  return Object.fromEntries(Object.entries(D7000_REQUIRED_BY_GROUP).map(([group, required]) => [
    group, required.filter((id) => !selectedByGroup[group].includes(id)),
  ]));
}

const fail = (message) => { throw new TypeError(message); };
const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const isByteCount = (value) => Number.isSafeInteger(value) && value >= 0;
const isSha256 = (value) => typeof value === 'string' && /^[\da-f]{64}$/i.test(value);

function checkedGroups(catalogue) {
  if (!isRecord(catalogue) || catalogue.version !== 1 || !isRecord(catalogue.groups)) {
    fail('Unsupported native module catalogue');
  }
  const groups = {};
  const owners = new Map();
  for (const group of BUILDER_GROUPS) {
    const ids = catalogue.groups[group];
    if (!Array.isArray(ids) || ids.length === 0 || ids.some((id) => typeof id !== 'string' || !id)) {
      fail(`Invalid catalogue group: ${group}`);
    }
    if (new Set(ids).size !== ids.length) fail(`Duplicate catalogue ID in ${group}`);
    for (const id of ids) {
      if (owners.has(id)) fail(`Catalogue ID appears in multiple groups: ${id}`);
      owners.set(id, group);
    }
    groups[group] = new Set(ids);
  }
  return { groups, owners };
}

/** Validate a selection and prepared-content summary against exporter metadata.
 * `content` entries use the checked backend manifest fields: kind, bytes,
 * dependencies, and dependency_scan_complete. No image-size prediction occurs.
 */
export function validateNativeBuildSelection(catalogue, profile, content = []) {
  const { groups, owners } = checkedGroups(catalogue);
  if (!isRecord(profile) || profile.version !== 1) fail('Unsupported native image profile');

  const selectedByGroup = {};
  const selected = new Set();
  for (const group of BUILDER_GROUPS) {
    const ids = profile[group] ?? [];
    if (!Array.isArray(ids) || ids.some((id) => typeof id !== 'string' || !id)) {
      fail(`Invalid selected module group: ${group}`);
    }
    if (new Set(ids).size !== ids.length) fail(`Duplicate selected module in ${group}`);
    for (const id of ids) {
      if (!groups[group].has(id)) {
        const actualGroup = owners.get(id);
        fail(actualGroup ? `Module ${id} belongs to ${actualGroup}, not ${group}` : `Unknown module: ${id}`);
      }
      if (selected.has(id)) fail(`Module selected more than once: ${id}`);
      selected.add(id);
    }
    selectedByGroup[group] = Object.freeze([...ids]);
  }
  if (selectedByGroup.engines.length === 0) fail('Profile needs a sound engine');
  if (!Array.isArray(content) || content.length > CONTENT_LIMITS.maxAssets) {
    fail(`Content must contain at most ${CONTENT_LIMITS.maxAssets} assets`);
  }

  let packedContentBytes = 0;
  let dependenciesComplete = true;
  const assets = content.map((asset, index) => {
    if (!isRecord(asset) || !isByteCount(asset.bytes)
        || asset.bytes < CONTENT_LIMITS.minPackedFileBytes
        || asset.bytes > CONTENT_LIMITS.maxPackedFileBytes) {
      fail(`Packed asset ${index} is outside native container bounds`);
    }
    if (asset.kind !== 'project' && asset.kind !== 'set') fail(`Unsupported packed asset kind at ${index}`);
    if (asset.packed_sha256 !== undefined && !isSha256(asset.packed_sha256)) {
      fail(`Invalid packed SHA-256 for asset ${index}`);
    }
    if (!Array.isArray(asset.dependencies)
        || asset.dependencies.some((dependency) => typeof dependency !== 'string' || !dependency)) {
      fail(`Invalid dependency list for packed asset ${index}`);
    }
    if (new Set(asset.dependencies).size !== asset.dependencies.length) {
      fail(`Duplicate dependency for packed asset ${index}`);
    }
    const complete = asset.kind === 'project' && asset.dependency_scan_complete === true;
    dependenciesComplete &&= complete;
    if (complete) {
      const missing = asset.dependencies.filter((dependency) => !selected.has(dependency));
      if (missing.length) fail(`Packed asset ${index} needs omitted modules: ${missing.join(',')}`);
    }
    packedContentBytes += asset.bytes;
    if (!Number.isSafeInteger(packedContentBytes)
        || packedContentBytes > CONTENT_LIMITS.maxPackedTotalBytes) {
      fail('Packed content exceeds entire FM-1 flash input bound');
    }
    return Object.freeze({ kind: asset.kind, bytes: asset.bytes,
      ...(asset.packed_sha256 === undefined ? {} : { packedSha256: asset.packed_sha256.toLowerCase() }),
      dependencies: Object.freeze([...asset.dependencies]),
      dependencyScanComplete: complete });
  });

  return Object.freeze({
    selectedByGroup: Object.freeze(selectedByGroup),
    selectedModuleCount: selected.size,
    countsByGroup: Object.freeze(Object.fromEntries(BUILDER_GROUPS.map(
      (group) => [group, selectedByGroup[group].length]))),
    assets: Object.freeze(assets),
    assetCount: assets.length,
    packedContentBytes,
    packedContentInputBoundBytes: CONTENT_LIMITS.maxPackedTotalBytes,
    contentDependencyStatus: dependenciesComplete ? 'complete-for-projects' : 'requires-backend-resolution',
    firmwareSizeStatus: 'unmeasured-until-link-receipt',
    installable: false,
  });
}

/** Surface only exact-selection link evidence; never extrapolate between builds.
 * Current receipts without module_selection or app_bytes remain unmeasured.
 */
export function summarizeLinkReceipt(receipt, selection) {
  if (!isRecord(receipt) || !isRecord(selection)) fail('Link receipt and selection are required');
  const measuredSelection = receipt.module_selection?.selected;
  const appBytes = receipt.app_bytes;
  const budgetBytes = receipt.app_budget_bytes;
  if (!Array.isArray(measuredSelection) || !isByteCount(appBytes)
      || !isByteCount(budgetBytes) || appBytes > budgetBytes) {
    return Object.freeze({ status: 'unmeasured', appBytes: null, budgetBytes: null, marginBytes: null });
  }
  const requested = BUILDER_GROUPS.flatMap((group) => selection.selectedByGroup[group] ?? []).sort();
  const measured = [...measuredSelection].sort();
  if (requested.length !== measured.length || requested.some((id, index) => id !== measured[index])) {
    return Object.freeze({ status: 'unmeasured-selection-mismatch', appBytes: null,
      budgetBytes: null, marginBytes: null });
  }
  const embedded = receipt.embedded_content;
  const embeddedBytes = embedded?.packed_content_bytes;
  const selectedContentBytesAreInThisReceipt = embeddedContentMatchesSelection(embedded, selection);
  return Object.freeze({ status: 'measured-exact-selection', appBytes, budgetBytes,
    marginBytes: budgetBytes - appBytes,
    embeddedContentBytes: isByteCount(embeddedBytes) ? embeddedBytes : null,
    selectedContentBytesAreInThisReceipt,
    predictsOtherLinkSizes: false,
  });
}

function embeddedContentMatchesSelection(embedded, selection) {
  const selectedAssets = selection.assets;
  const receiptAssets = embedded?.assets;
  if (!Array.isArray(selectedAssets) || !Array.isArray(receiptAssets)
      || selectedAssets.length !== receiptAssets.length
      || embedded.asset_count !== receiptAssets.length
      || !isByteCount(embedded.packed_content_bytes)) return false;

  let totalBytes = 0;
  for (let index = 0; index < selectedAssets.length; index += 1) {
    const selected = selectedAssets[index];
    const included = receiptAssets[index];
    if (!isRecord(selected) || !isRecord(included)
        || !isByteCount(selected.bytes) || !isByteCount(included.bytes)
        || selected.kind !== included.kind
        || selected.bytes !== included.bytes
        || !isSha256(selected.packedSha256)
        || !isSha256(included.packed_sha256)
        || selected.packedSha256.toLowerCase() !== included.packed_sha256.toLowerCase()) {
      return false;
    }
    totalBytes += included.bytes;
    if (!Number.isSafeInteger(totalBytes)) return false;
  }
  return totalBytes === embedded.packed_content_bytes;
}
