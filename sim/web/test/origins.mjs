// origins.mjs -- the simulator page's localhost exception (owner, 2026-10-06)
// as pure functions, under Node: served from localhost, 127.0.0.1 or [::1],
// the page trusts a parent and ?load= files on any local origin; served from
// anywhere else, its own origin only. tests/test_sim_origins.py runs it; the
// page itself is checked in headless Chromium by files.mjs.
//
//   node origins.mjs WWW_DIR
//
// MIT licence, like the rest of this repository.

import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const www = resolve(process.argv[2] || join(import.meta.dirname, '..', 'www'));
const { isLocalOrigin, trustedOrigin, loadUrl, parseSel } = await import(pathToFileURL(join(www, 'files.js')).href);
const fails = [];
const check = (what, got, want) => { if (got !== want) fails.push(`${what}: got ${got}, want ${want}`); };

for (const o of ['http://localhost:5173', 'http://127.0.0.1:8000', 'http://[::1]:8000', 'https://localhost', 'http://localhost']) {
  check(`local ${o}`, isLocalOrigin(o), true);
}
for (const o of ['https://ip2k.github.io', 'http://lunar.test:8766', 'http://localhost.evil.test', 'http://127.0.0.2:8000',
  'file://', 'null', '', 'http://localhost:5173/', 'ftp://localhost', 'http://user@localhost:5173', 'http://[::2]:80']) {
  check(`not local ${o}`, isLocalOrigin(o), false);
}

// Embedding: a local page trusts any local parent; the public site only itself.
const LOCAL = 'http://127.0.0.1:8766', PUBLIC = 'https://ip2k.github.io';
check('local page, own origin', trustedOrigin(LOCAL, LOCAL), true);
check('local page, another local port', trustedOrigin('http://localhost:5173', LOCAL), true);
check('local page, [::1]', trustedOrigin('http://[::1]:3000', LOCAL), true);
check('local page, a public parent', trustedOrigin(PUBLIC, LOCAL), false);
check('local page, a .test parent', trustedOrigin('http://lunar.test:8766', LOCAL), false);
check('public page, own origin', trustedOrigin(PUBLIC, PUBLIC), true);
check('public page, a local parent', trustedOrigin('http://localhost:5173', PUBLIC), false);
check('public page, null', trustedOrigin('null', PUBLIC), false);

// ?load=: relative allowlisted paths everywhere; absolute local URLs on a local page only.
const href = (u) => (u ? u.href : null);
check('local page, relative', href(loadUrl('examples/first-orbit.lunar', `${LOCAL}/index.html`, LOCAL)),
  `${LOCAL}/examples/first-orbit.lunar`);
check('public page, relative', href(loadUrl('examples/first-orbit.lunar', `${PUBLIC}/lunar/index.html`, PUBLIC)),
  `${PUBLIC}/lunar/examples/first-orbit.lunar`);
for (const ok of ['http://localhost:5173/missions/first.lunar', 'http://[::1]:8000/a/set.movy1', 'http://127.0.0.1:9000/x.syx',
  `${LOCAL}/examples/first-orbit.lunar`]) {
  check(`local page loads ${ok}`, href(loadUrl(ok, `${LOCAL}/index.html`, LOCAL)), ok);
  check(`public page refuses ${ok}`, loadUrl(ok, `${PUBLIC}/lunar/index.html`, PUBLIC), null);
}
for (const bad of ['http://localhost:5173/missions/first.lunar?x=1', 'http://localhost:5173/a.lunar#x',
  'http://user:pw@localhost:5173/a.lunar', 'http://localhost:5173/a/../b.lunar', 'http://localhost:5173/a/%2e%2e/b.lunar',
  'http://localhost:5173//a.lunar', 'http://localhost:5173/a.txt', 'http://localhost:5173/A.lunar',
  'http://lunar.test:8766/examples/first-orbit.lunar', 'https://ip2k.github.io/a.lunar', 'http://LOCALHOST:5173/a.lunar',
  'http://localhost.evil.test/a.lunar', 'javascript:alert(1)', '//localhost:5173/a.lunar']) {
  check(`local page refuses ${bad}`, loadUrl(bad, `${LOCAL}/index.html`, LOCAL), null);
}

// sel= (stage ED4): a block of the editor and a parameter's name, nothing else.
for (const [good, key, param] of [['s1', 's1', null], ['s3.in1:Cutoff', 's3.in1', 'Cutoff'], ['m2', 'm2', null],
  ['p8', 'p8', null], ['c32', 'c32', null], ['mix', 'mix', null], ['s2.mfx1:Gate', 's2.mfx1', 'Gate'], ['s1:Env Pitch', 's1', 'Env Pitch']]) {
  const v = parseSel(good);
  check(`sel ${good}`, v && `${v.key}|${v.param}`, `${key}|${param}`);
}
for (const bad of ['', 's0', 's5', 's1.in3', 'm3', 'p9', 'c0', 'c33', 'S1', 's1:', 's1::x', 's1:<img src=x onerror=alert(1)>',
  `p1:${'A'.repeat(40)}`, 'https://evil.example/a.lunar', '../s1', 's1 ', ' s1', 's1:a"b', 's1:a\nb', 'mix:Level\u0000',
  's1.in1:Cut;off', 'javascript:alert(1)', 'x'.repeat(100), null, 42]) {
  check(`sel refuses ${String(bad).slice(0, 30)}`, parseSel(bad), null);
}

console.log(JSON.stringify({ pass: fails.length === 0, fails }));
process.exit(fails.length ? 1 : 0);
