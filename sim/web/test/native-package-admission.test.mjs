// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { inspectNativePackage, verifyNativePackage } from '../www/native-package-admission.js';

function fwscMarkerFixture(identity = 'FM-1_990') {
  const bytes = new Uint8Array(20 * 48 + 32);
  for (let index = 0; index < 20; index += 1) {
    const char = identity.charCodeAt(index);
    bytes[index * 48 + 47] = index < identity.length ? (char + index + 1) & 0xff : 125;
  }
  bytes.set(new TextEncoder().encode('JLUFW'), bytes.length - 16);
  return bytes;
}

test('bare app, ELF, and raw image are never admitted as OTA packages', async () => {
  const app = Uint8Array.of(1, 2, 3, 4);
  const elf = Uint8Array.of(0x7f, 0x45, 0x4c, 0x46);
  for (const [bytes, kind] of [[app, 'unknown'], [elf, 'elf'], [new Uint8Array(1024 * 1024), 'raw-flash-candidate']]) {
    const inspected = inspectNativePackage(bytes);
    assert.equal(inspected.kind, kind);
    assert.equal(inspected.admissible, false);
    assert.equal('logicalImage' in inspected, false);
    await assert.rejects(verifyNativePackage(bytes), /package admission blocked/);
  }
});

test('FWSC marker candidate is identified but remains blocked without structural/release proof', async () => {
  const candidate = fwscMarkerFixture();
  const inspected = inspectNativePackage(candidate);
  assert.equal(inspected.kind, 'jieli-fwsc-candidate');
  assert.equal(inspected.identity, 'FM-1_990');
  assert.equal(inspected.admissible, false);
  assert.equal('logicalImage' in inspected, false);
  await assert.rejects(verifyNativePackage(candidate), /incomplete/);
});

test('malformed and unrecognized bytes fail closed', () => {
  const malformed = fwscMarkerFixture();
  malformed[47] ^= 1;
  assert.equal(inspectNativePackage(malformed).kind, 'unknown');
  assert.equal(inspectNativePackage(new Uint8Array()).kind, 'empty');
  assert.throws(() => inspectNativePackage(new ArrayBuffer(4)), /Uint8Array/);
});

test('optional output of the private Python OTA composer is recognized but never admitted', async (t) => {
  const fixturePath = process.env.LUNAR_PRIVATE_FWSC_FIXTURE;
  if (!fixturePath) return t.skip('private stock-derived composer output is not available in this checkout');
  const fixture = new Uint8Array(await readFile(fixturePath));
  const inspected = inspectNativePackage(fixture);
  assert.equal(inspected.kind, 'jieli-fwsc-candidate');
  assert.equal(inspected.admissible, false);
  assert.equal('logicalImage' in inspected, false);
});
