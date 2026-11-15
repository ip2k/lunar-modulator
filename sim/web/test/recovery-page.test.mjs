// SPDX-License-Identifier: MIT
// Static checks on the recovery page: wiring and the D2 soft-key rule.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const www = new URL('../www/', import.meta.url);
const read = (n) => fs.readFileSync(new URL(n, www), 'utf8');
const html = read('recovery.html'), page = read('recovery-page.js'), proto = read('recovery-transporter.js');

test('every element id the page script uses exists in recovery.html', () => {
  const ids = [...page.matchAll(/\$\('([\w-]+)'\)/g)].map((m) => m[1]);
  assert.ok(ids.length > 20);
  for (const id of new Set(ids)) assert.match(html, new RegExp(`id="${id}"`), id);
});

test('no source file builds a soft-key or other banned request', () => {
  for (const [name, src] of [['page', page], ['proto', proto]]) {
    assert.doesNotMatch(src, /request\(\s*[`'"](uboot|runapp|jump|memw|memr)/, name);
    assert.doesNotMatch(src, /F0 22 24 35 7D|0xF0, *0x22/i, name);
  }
  assert.match(proto, /ALLOWED_COMMANDS = Object\.freeze\(\['ping', 'status', 'rekey', 'info', 'read', 'ldr', 'wsec'\]\)/);
});

test('the page links no third-party binary and says what it needs', () => {
  assert.doesNotMatch(html, /href="[^"]+\.(uf2|bin|fwsc)"/i);
  assert.match(html, /tools\/fm1-transporter\/build\.sh/);
  assert.match(html, /BOOTSEL/);
  assert.match(html, /never sends that command/);
});

test('(b) the page drops a link in one place, closing it before forgetting it', () => {
  const nulls = [...page.matchAll(/\blink = null/g)];
  assert.equal(nulls.length, 2, 'the declaration and dropLink only');
  const drop = page.slice(page.indexOf('async function dropLink()'), page.indexOf('async function showImage()'));
  assert.ok(drop.indexOf('await old.close()') >= 0 && drop.indexOf('await old.close()') < drop.indexOf('link = null'));
  assert.match(drop, /plan = null/);
  // port-closed, rekey and every (re)connect go through it
  assert.match(page, /if \(e\.code === 'port-closed'\) await dropLink\(\);/);
  assert.match(page, /async function pickPort\(\) \{\n {2}await dropLink\(\);/);
  assert.match(page.slice(page.indexOf("$('btn-rekey').onclick")), /^[\s\S]*?await dropLink\(\);/);
  assert.doesNotMatch(page, /session\.booted/);
});

test('(e)-(g) page text: image description, reconnect wording, modified boot areas', () => {
  assert.match(page, /describeImage\(image, session\?\.backup \|\| null\)/);
  assert.doesNotMatch(html, /loader must be chosen again/i);
  assert.match(html, /loader file stays accepted/);
  assert.match(html, /Felucca and SLOOP install a different <code>uboot\.boot<\/code>/);
  const doc = fs.readFileSync(new URL('../../../docs/17-pico2w-recovery.md', import.meta.url), 'utf8');
  assert.match(doc, /A unit with a replaced boot area refuses a stock restore, by design/);
});
