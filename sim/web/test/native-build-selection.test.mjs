import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  CONTENT_LIMITS,
  summarizeLinkReceipt,
  validateNativeBuildSelection,
} from '../www/native-build-selection.js';

const catalogue = {
  version: 1,
  groups: {
    engines: ['macro', 'shapes'],
    effects: ['plate', 'echo'],
    midi: ['arp'],
    modulation: ['lfo'],
  },
};
const profile = {
  version: 1,
  engines: ['macro'], effects: ['plate'], midi: [], modulation: ['lfo'],
};

test('validates selectable groups and reports counts without estimating firmware size', () => {
  const result = validateNativeBuildSelection(catalogue, profile);
  assert.deepEqual(result.countsByGroup, { engines: 1, effects: 1, midi: 0, modulation: 1 });
  assert.equal(result.selectedModuleCount, 3);
  assert.equal(result.firmwareSizeStatus, 'unmeasured-until-link-receipt');
  assert.equal(result.installable, false);
});

test('rejects unknown, wrong-group, duplicate, and engine-free selections', () => {
  assert.throws(() => validateNativeBuildSelection({ ...catalogue, version: 2 }, profile),
    /Unsupported native module catalogue/);
  assert.throws(() => validateNativeBuildSelection(catalogue, { ...profile, version: 2 }),
    /Unsupported native image profile/);
  assert.throws(() => validateNativeBuildSelection(catalogue,
    { ...profile, engines: ['not-in-catalogue'] }), /Unknown module/);
  assert.throws(() => validateNativeBuildSelection(catalogue,
    { ...profile, effects: ['macro'] }), /belongs to engines/);
  assert.throws(() => validateNativeBuildSelection(catalogue,
    { ...profile, effects: ['plate', 'plate'] }), /Duplicate selected module/);
  assert.throws(() => validateNativeBuildSelection(catalogue,
    { ...profile, engines: [] }), /needs a sound engine/);
});

test('checks packed project byte bounds and complete dependencies', () => {
  const content = [{ kind: 'project', bytes: 1024, packed_sha256: 'a'.repeat(64), dependencies: ['macro'],
    dependency_scan_complete: true }];
  const result = validateNativeBuildSelection(catalogue, profile, content);
  assert.equal(result.packedContentBytes, 1024);
  assert.equal(result.assets[0].packedSha256, 'a'.repeat(64));
  assert.equal(result.contentDependencyStatus, 'complete-for-projects');
  assert.throws(() => validateNativeBuildSelection(catalogue, profile,
    [{ ...content[0], dependencies: ['shapes'] }]), /needs omitted modules/);
  assert.throws(() => validateNativeBuildSelection(catalogue, profile,
    [{ ...content[0], bytes: CONTENT_LIMITS.maxPackedFileBytes + 1 }]), /container bounds/);
  assert.throws(() => validateNativeBuildSelection(catalogue, profile,
    [{ ...content[0], packed_sha256: 'not-a-sha256' }]), /Invalid packed SHA-256/);
});

test('keeps set dependency coverage explicitly incomplete and enforces aggregate ceiling', () => {
  const set = { kind: 'set', bytes: 512, dependencies: [], dependency_scan_complete: false };
  assert.equal(validateNativeBuildSelection(catalogue, profile, [set]).contentDependencyStatus,
    'requires-backend-resolution');
  const tooLarge = Array.from({ length: 11 }, () => ({ ...set, bytes: 98304 }));
  assert.throws(() => validateNativeBuildSelection(catalogue, profile, tooLarge), /entire FM-1 flash/);
});

test('admits embedded content identity only for ordered per-asset kind, size, and SHA matches', () => {
  const content = [
    { kind: 'project', bytes: 1024, packed_sha256: 'a'.repeat(64), dependencies: ['macro'],
      dependency_scan_complete: true },
    { kind: 'project', bytes: 1024, packed_sha256: 'b'.repeat(64), dependencies: ['macro'],
      dependency_scan_complete: true },
  ];
  const selection = validateNativeBuildSelection(catalogue, profile, content);
  const receipt = { module_selection: { selected: ['macro', 'plate', 'lfo'] },
    app_bytes: 800000, app_budget_bytes: 868836,
    embedded_content: { packed_content_bytes: 2048, asset_count: 2, assets: [
      { kind: 'project', bytes: 1024, packed_sha256: 'a'.repeat(64) },
      { kind: 'project', bytes: 1024, packed_sha256: 'b'.repeat(64) },
    ] } };
  assert.deepEqual(summarizeLinkReceipt(receipt, selection), {
    status: 'measured-exact-selection', appBytes: 800000, budgetBytes: 868836,
    marginBytes: 68836, embeddedContentBytes: 2048,
    selectedContentBytesAreInThisReceipt: true, predictsOtherLinkSizes: false,
  });
  const withoutSelectionHashes = validateNativeBuildSelection(catalogue, profile,
    content.map(({ packed_sha256, ...asset }) => asset));
  assert.equal(summarizeLinkReceipt(receipt, withoutSelectionHashes)
    .selectedContentBytesAreInThisReceipt, false);
  const sameSizeDifferentContent = { ...receipt, embedded_content: { ...receipt.embedded_content,
    assets: [{ ...receipt.embedded_content.assets[0], packed_sha256: 'c'.repeat(64) },
      receipt.embedded_content.assets[1]] } };
  assert.equal(summarizeLinkReceipt(sameSizeDifferentContent, selection)
    .selectedContentBytesAreInThisReceipt, false);
  const reordered = { ...receipt, embedded_content: { ...receipt.embedded_content,
    assets: [...receipt.embedded_content.assets].reverse() } };
  assert.equal(summarizeLinkReceipt(reordered, selection)
    .selectedContentBytesAreInThisReceipt, false);
  const missingAssetIdentity = { ...receipt, embedded_content: { packed_content_bytes: 2048 } };
  assert.equal(summarizeLinkReceipt(missingAssetIdentity, selection)
    .selectedContentBytesAreInThisReceipt, false);
  assert.equal(summarizeLinkReceipt({ ...receipt, app_bytes: undefined }, selection).status,
    'unmeasured');
  assert.equal(summarizeLinkReceipt({ ...receipt, module_selection: { selected: ['macro'] } }, selection).status,
    'unmeasured-selection-mismatch');
});
