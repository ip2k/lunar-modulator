// SPDX-License-Identifier: MIT
// Inspection-only boundary. No current artifact has completed release admission.

const FWSC_HEADER_BYTES = 20 * 48;
const RAW_FLASH_BYTES = 1024 * 1024;

function bytesOf(input) {
  if (!(input instanceof Uint8Array)) throw new TypeError('package must be supplied as Uint8Array');
  return input;
}

function fwscIdentity(bytes) {
  if (bytes.length < FWSC_HEADER_BYTES) return null;
  const markers = [];
  for (let index = 0; index < 20; index += 1) markers.push(bytes[index * 48 + 47]);
  const end = markers.indexOf(125);
  if (end < 0 || markers.slice(end).some((value) => value !== 125)) return null;
  const text = markers.slice(0, end).map((value, index) => String.fromCharCode((value - index - 1) & 0xff)).join('');
  return /^FM-1_[0-9]{3}$/.test(text) ? text : null;
}

function blocked(kind, reason, identity = null) {
  return Object.freeze({ schema: 'lunar-browser-package-inspection-v1', kind, identity,
    admissible: false, reason });
}

/** Classify known input shapes for UI diagnostics; never creates an install capability. */
export function inspectNativePackage(input) {
  const bytes = bytesOf(input);
  if (bytes.length === 0) return blocked('empty', 'empty artifact');
  const identity = fwscIdentity(bytes);
  if (identity) {
    return blocked('jieli-fwsc-candidate', 'FWSC inspection is incomplete and release admission is not established', identity);
  }
  if (bytes.length === RAW_FLASH_BYTES) return blocked('raw-flash-candidate', 'raw flash geometry is not an admitted OTA package');
  if (bytes.length >= 4 && bytes[0] === 0x7f && bytes[1] === 0x45 && bytes[2] === 0x4c && bytes[3] === 0x46) {
    return blocked('elf', 'ELF is a build artifact, not an OTA package');
  }
  return blocked('unknown', 'unrecognized artifact format; admission is closed');
}

/** Adapter-compatible verifier which always rejects until an audited release verifier exists. */
export async function verifyNativePackage(input) {
  const inspection = inspectNativePackage(input);
  throw new Error(`package admission blocked (${inspection.kind}): ${inspection.reason}`);
}
