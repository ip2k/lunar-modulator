// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mountLocalPackageInspection, MAX_INSPECTABLE_PACKAGE_BYTES } from '../www/installer-package-inspection.js';

class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.value = '';
    this._textContent = '';
  }
  append(...children) { this.children.push(...children); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  addEventListener(name, callback) { this.listeners.set(name, callback); }
  async dispatch(name) { return this.listeners.get(name)?.({ target: this }); }
  remove() { this.removed = true; }
  get textContent() { return this._textContent + this.children.map((child) => child.textContent).join(''); }
  set textContent(value) { this._textContent = String(value); this.children = []; }
}
class Document {
  createElement(name) { return new Element(name, this); }
}
function mounted(options) {
  const document = new Document(), root = new Element('div', document);
  const controller = mountLocalPackageInspection(root, options);
  const section = root.children[0];
  return { root, controller, input: section.children[2].children[0], clear: section.children[3], report: section.children[4] };
}
function file(name, bytes, arrayBuffer = async () => bytes.buffer) {
  return { name, size: bytes.byteLength, arrayBuffer };
}

test('reports local structural findings, but states release admission and installation remain unavailable', async () => {
  const expected = new Uint8Array([1, 2, 3]);
  let inspected;
  const view = mounted({ inspect(bytes) {
    inspected = bytes;
    return { kind: 'jieli-fwsc-candidate', identity: 'FM-1_092', admissible: false,
      reason: 'FWSC structure and CRC checks passed; protected-stock correspondence and release admission are not established',
      envelope: { headerCrcVerified: true, entryListCrcVerified: true,
        entries: [{ name: 'flash.bin', bytes: 100, crcVerified: true }],
        nestedInspection: { profile: 'FM-1_092-D7000', status: 'structure-crc-verified', flashBytes: 100,
          appBytes: 20, admissible: false } } };
  } });
  view.input.files = [file('candidate.fwsc', expected)];
  await view.input.dispatch('change');
  assert.deepEqual([...inspected], [1, 2, 3]);
  assert.match(view.report.textContent, /FM-1_092/);
  assert.match(view.report.textContent, /header CRC: passed/);
  assert.match(view.report.textContent, /flash\.bin \(100 bytes, CRC passed\)/);
  assert.match(view.report.textContent, /structure and CRC checks passed/);
  assert.match(view.report.textContent, /Release admission: not established\. Installation is unavailable\./);
  assert.equal(view.report.textContent.includes('1,2,3'), false);
  view.controller.destroy();
  assert.equal(view.root.children[0].removed, true);
});

test('rejects oversized files before reading and clears previous report immediately on change', async () => {
  let reads = 0;
  const view = mounted();
  view.input.files = [file('too-large.fwsc', new Uint8Array(MAX_INSPECTABLE_PACKAGE_BYTES + 1), async () => {
    reads += 1; return new ArrayBuffer(0);
  })];
  await view.input.dispatch('change');
  assert.equal(reads, 0);
  assert.match(view.report.textContent, /maximum|between 1 byte/i);
  assert.equal(view.input.value, '');
  view.input.files = [file('malformed.fwsc', Uint8Array.of(1, 2, 3))];
  await view.input.dispatch('change');
  assert.match(view.report.textContent, /unknown/);
  assert.match(view.report.textContent, /Release admission: not established/);
});

test('clear invalidates an in-flight read so stale inspection cannot replace the cleared result', async () => {
  let resolveRead;
  const view = mounted();
  const old = file('old.fwsc', Uint8Array.of(4, 5), () => new Promise((resolve) => { resolveRead = resolve; }));
  view.input.files = [old];
  const pending = view.input.dispatch('change');
  assert.match(view.report.textContent, /Inspecting selected file/);
  await view.clear.dispatch('click');
  assert.equal(view.report.textContent, 'No package selected.');
  resolveRead(Uint8Array.of(4, 5).buffer);
  await pending;
  assert.equal(view.report.textContent, 'No package selected.');
  assert.equal(view.input.value, '');
});

test('shows controlled read and inspection failures without opening an admission path', async () => {
  const view = mounted({ inspect() { throw new Error('synthetic CRC mismatch'); } });
  view.input.files = [file('broken.fwsc', Uint8Array.of(1))];
  await view.input.dispatch('change');
  assert.match(view.report.textContent, /synthetic CRC mismatch/);
  assert.match(view.report.textContent, /Release admission remains closed/);
  view.input.files = [file('unreadable.fwsc', Uint8Array.of(1), async () => { throw new Error('read denied'); })];
  await view.input.dispatch('change');
  assert.match(view.report.textContent, /read denied/);
  assert.match(view.report.textContent, /Release admission remains closed/);
});
