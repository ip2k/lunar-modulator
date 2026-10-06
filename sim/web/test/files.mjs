// files.mjs -- the virtual FM-1's files in headless Chromium (stage W1,
// notes/2026-10-06-state-files.md §12 and §17). Runs in the Playwright
// container on aeon after screenshot.mjs (build-on-aeon.sh), never on the Mac:
//
//   node files.mjs WWW_DIR OUT_DIR
//
// Checks: Save… downloads the project and the current sound with the kind as
// a middle word in the name; Open… and a drop load .lunar files (a sound asks
// for its target); a file over the FM-1's RAM is refused on the page in the
// refusal colour, as a percent, and changes nothing; every load reaches the
// worklet as the binary container, after pass 1 in the shadow Worker, and the
// worklet refuses JSON; SAVE on the panel stores the project in IndexedDB;
// the autosave writes on its own timer and the next visit restores it;
// Recent keeps "Before …" and Undo load puts the project back byte for byte;
// ?load= takes allowlisted same-origin paths only (no request leaves for
// the others); #lunar= links round-trip, and one over 32 KiB or inflating
// past the cap is refused; ?embed=1 answers a same-origin parent (ready,
// power, query, save, highlight, transport) and nothing else; the localhost
// exception (owner, 2026-10-06): served from 127.0.0.1, the page answers a
// parent on another local port and loads ?load= from another local origin,
// while served from lunar.test (as the public site) it does neither; and the
// page at desktop and phone widths, with no page-wide horizontal scroll.
// MIT licence, like the rest of this repository.

import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { deflateRawSync } from 'node:zlib';
import { serve } from './serve.mjs';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const { chromium } = require('playwright');

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const PORT = 8766;
const { server, url } = await serve(www, PORT);
const origin = `http://127.0.0.1:${PORT}`;
const report = { checks: {}, logs: [] };
const browser = await chromium.launch({
  args: ['--autoplay-policy=no-user-gesture-required', '--host-resolver-rules=MAP lunar.test 127.0.0.1'],
});
report.browser = `Chromium ${browser.version()} (Playwright, headless)`;
const wait = (page, ms) => page.waitForTimeout(ms);
const example = (name) => join(www, 'examples', name);

async function open(ctx, address = url) {
  const page = await ctx.newPage();
  page.on('pageerror', (e) => report.logs.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') report.logs.push(`error: ${m.text()}`); });
  await page.goto(address);
  return page;
}
async function powerOn(page) {
  await page.click('#power-on');
  await page.waitForFunction(() => window.fm1 && window.fm1.screens > 0 && window.fm1.files.powered, null, { timeout: 20000 });
  await wait(page, 300);
}
const notice = (page) => page.evaluate(() => {
  const n = document.getElementById('file-notice');
  const t = n.querySelector('.notice-text');
  return { shown: !n.hidden, tone: n.className, text: t ? t.textContent : '', color: t ? getComputedStyle(t).color : '' };
});
const waitNotice = (page, re, timeout = 8000) => page.waitForFunction(
  (src) => new RegExp(src).test(document.querySelector('#file-notice .notice-text')?.textContent || ''), re.source, { timeout });
const project = (page) => page.evaluate(() => window.fm1.files.saveText('project'));
async function drop(page, path, name) {
  const bytes = [...readFileSync(path)];
  await page.evaluate(({ bytes, name }) => {
    const dt = new DataTransfer();
    dt.items.add(new File([new Uint8Array(bytes)], name));
    for (const type of ['dragenter', 'dragover', 'drop']) {
      window.dispatchEvent(new DragEvent(type, { dataTransfer: dt, bubbles: true, cancelable: true }));
    }
  }, { bytes, name });
}

// Save…, Open…, drop, a refusal, the worker path, SAVE, autosave, Recent, Undo.
async function filesChecks() {
  const r = {};
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true });
  const page = await open(ctx);
  r.open_enabled_off = await page.evaluate(() => !document.getElementById('open').disabled);
  r.save_disabled_off = await page.evaluate(() => document.getElementById('save').disabled);
  await powerOn(page);
  // Save…: the project, then the current sound.
  const save = async (value) => {
    await page.selectOption('#save-kind', value);
    const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#save')]);
    return { name: dl.suggestedFilename(), text: readFileSync(await dl.path(), 'utf8') };
  };
  const p = await save('project');
  const s = await save('sound:current');
  r.save_names = [p.name, s.name];
  r.save_kinds = [JSON.parse(p.text).kind, JSON.parse(s.text).kind];
  // A drop: a sound asks where it goes; Sound 2.
  await drop(page, example('deep-bass.sound.lunar'), 'deep-bass.sound.lunar');
  await page.waitForSelector('#target-card:not([hidden])');
  r.target_title = await page.textContent('#target-title');
  r.slot_hidden = await page.evaluate(() => getComputedStyle(document.getElementById('target-slot-field')).display === 'none');
  await page.selectOption('#target-into', '1');
  await page.screenshot({ path: join(out, 'files-01-target.png') });
  await page.click('#target-ok');
  await waitNotice(page, /^Loaded sound/);
  r.sound_loaded = (await notice(page)).text;
  // Open…: the example project, through the file chooser.
  const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('#open')]);
  await chooser.setFiles(example('first-orbit.lunar'));
  await waitNotice(page, /^Loaded “First orbit”/);
  r.project_loaded = (await notice(page)).text;
  r.title = await page.evaluate(() => window.fm1.files.title);
  // The same sound over First orbit does not fit: refused, nothing changed.
  const before = await project(page);
  const recentCount = () => page.evaluate(async () => (await window.fm1.files.store.all('recent')).length);
  const recentBefore = await recentCount();
  await drop(page, example('deep-bass.sound.lunar'), 'deep-bass.sound.lunar');
  await page.waitForSelector('#target-card:not([hidden])');
  await page.selectOption('#target-into', '1');
  await page.click('#target-ok');
  await waitNotice(page, /was not loaded/);
  r.refusal = await notice(page);
  r.refuse_colour = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--rp-love').trim());
  r.unchanged = (await project(page)) === before && (await recentCount()) === recentBefore;
  await page.screenshot({ path: join(out, 'files-02-refused.png') });
  // The worker path: every load went to the worklet as binary; JSON sent
  // straight to the worklet is refused there.
  r.worklet_loads = await page.evaluate(() => window.fm1.files.workletLoads);
  r.shadow_calls = await page.evaluate(() => window.fm1.files.shadowCalls);
  r.json_to_worklet = await page.evaluate(() => new Promise((resolve) => {
    const port = window.fm1.node.port;
    const prev = port.onmessage;
    port.onmessage = (e) => {
      if (e.data.type === 'state-loaded' && e.data.id === 999999) { port.onmessage = prev; resolve(e.data); }
      else prev(e);
    };
    port.postMessage({ type: 'state-load', id: 999999, bytes: new TextEncoder().encode('{"lunar":"1.0","kind":"settings"}') });
  }));
  // SAVE on the panel: the project into IndexedDB.
  await page.evaluate(() => {
    const port = window.fm1.node.port;
    port.postMessage({ type: 'button', button: 9, down: true });
    setTimeout(() => port.postMessage({ type: 'button', button: 9, down: false }), 80);
  });
  await waitNotice(page, /^Saved “First orbit” in this browser/);
  r.saved = await page.evaluate(async () => (await window.fm1.files.store.all('files')).map((x) => [x.name, x.bin[0]]));
  // Autosave on its own timer: an edit, then 5 s quiet.
  const autosaves = await page.evaluate(() => window.fm1.files.autosaves);
  await page.evaluate(() => window.fm1.node.port.postMessage({ type: 'encoder', encoder: 4, delta: 3 }));
  await page.evaluate(() => window.fm1.files.touched());
  await wait(page, 6500);
  r.autosave_timer = (await page.evaluate(() => window.fm1.files.autosaves)) > autosaves;
  const edited = await project(page);
  // Recent and Undo load: after the load of First orbit, Undo puts back
  // what was there, byte for byte.
  r.recent = await page.evaluate(async () => (await window.fm1.files.store.all('recent')).map((x) => x.name));
  await page.click('details.library summary');
  await page.screenshot({ path: join(out, 'files-03-library.png'), fullPage: true });
  await page.close();
  // The next visit restores the autosave.
  const again = await open(ctx);
  await powerOn(again);
  await waitNotice(again, /^Restored “First orbit”/);
  r.restored = (await project(again)) === edited;
  // A link over that work: Before …, then Undo load.
  const [ch2] = await Promise.all([again.waitForEvent('filechooser'), again.click('#open')]);
  await ch2.setFiles(example('space-verbs.fx.lunar'));
  await again.waitForSelector('#target-card:not([hidden])');
  await again.click('#target-ok');                       // the master effects
  await waitNotice(again, /^Loaded effects “Space verbs” into the master effects/);
  r.fx_changed = (await project(again)) !== edited;
  await again.click('#file-notice >> text=Undo load');
  await waitNotice(again, /was undone/);
  r.undo_identical = (await project(again)) === edited;
  r.recent_after = await again.evaluate(async () => (await window.fm1.files.store.all('recent')).map((x) => x.name));
  await again.evaluate(() => { window.fm1.files.touched(); return window.fm1.files.autosave(); });
  const kept = await project(again);
  await again.close();
  // A refused link over that work: the work comes back, Recent is as it was.
  const broken = deflateRawSync(Buffer.from('{"lunar":"1.0","kind":"project","title":"Broken"'))
    .toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const third = await open(ctx, `${url}#lunar=${broken}`);
  await powerOn(third);
  await waitNotice(third, /was not loaded/);
  r.link_refused_kept = (await project(third)) === kept &&
    (await third.evaluate(async () => (await window.fm1.files.store.all('recent')).length)) === r.recent_after.length;
  await third.close();
  await ctx.close();
  r.pass = r.open_enabled_off && r.save_disabled_off &&
    r.save_names[0] === 'untitled.lunar' && /^untitled-s1\.sound\.lunar$/.test(r.save_names[1]) &&
    r.save_kinds.join() === 'project,sound' &&
    /Load sound “Deep space bass” into/.test(r.target_title) && r.slot_hidden &&
    /^Loaded sound “Deep space bass” into Sound 2/.test(r.sound_loaded) &&
    /^Loaded “First orbit”: 4 sounds, .*It takes \d+% of the FM-1's RAM\.$/.test(r.project_loaded) && r.title === 'First orbit' &&
    /refused/.test(r.refusal.tone) && /Needs \d+% of the FM-1's RAM\./.test(r.refusal.text) &&
    !/bytes|KB/.test(r.refusal.text) && r.refusal.color === 'rgb(235, 111, 146)' && r.unchanged &&
    r.worklet_loads.length >= 2 && r.worklet_loads.every((l) => l.binary) && r.shadow_calls > 0 &&
    r.json_to_worklet.ok === false && r.json_to_worklet.binary === false &&
    r.saved.length === 1 && r.saved[0][0] === 'First orbit' && r.saved[0][1] === 0x89 &&
    r.autosave_timer && r.recent.includes('Before First orbit') && r.restored && r.fx_changed && r.undo_identical &&
    r.recent_after.includes('Before Space verbs') && r.link_refused_kept;
  return r;
}

// ?load=: allowlisted same-origin paths only.
async function loadLinkChecks() {
  const r = { refused: {} };
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const bad = ['../fm1.wasm.json', 'fm1.wasm.json', 'schema/x.lunar', 'examples/../index.lunar',
    'examples%2F..%2Ffirst-orbit.lunar', 'examples/%2e%2e/first-orbit.lunar', '//lunar.test:8766/examples/first-orbit.lunar',
    'http://lunar.test:8766/examples/first-orbit.lunar', 'examples//first-orbit.lunar', 'examples/first-orbit.lunar?x=1',
    'examples\\first-orbit.lunar', 'javascript:alert(1)', 'data:text/plain,examples/x.lunar', 'examples/First-Orbit.lunar', 'examples/first-orbit.txt'];
  for (const path of bad) {
    const page = await ctx.newPage();
    const requests = [];
    page.on('request', (q) => {
      if (!q.isNavigationRequest() && (!q.url().startsWith(origin) || /examples|schema|\.lunar/.test(q.url()))) requests.push(q.url());
    });
    await page.goto(`${url}?load=${path.includes('%') ? path : encodeURIComponent(path)}`);
    await wait(page, 400);
    const n = await notice(page);
    const arrival = await page.evaluate(() => !document.getElementById('arrival').hidden);
    r.refused[path] = { notice: n.shown && /refused/.test(n.tone), arrival, requests };
    await page.close();
  }
  // The allowlisted path: the card, then the load.
  const page = await open(ctx, `${url}?load=examples/first-orbit.lunar&view=seq.track=2&hl=KNOB2,FX,PLAY&play=1`);
  await page.waitForSelector('#arrival:not([hidden])');
  r.card = await page.evaluate(() => ({ title: document.getElementById('arrival-title').textContent,
    button: document.getElementById('power-on').textContent }));
  await page.screenshot({ path: join(out, 'files-04-arrival.png') });
  await powerOn(page);
  await waitNotice(page, /^Loaded “First orbit”/);
  await page.waitForFunction(() => window.fm1.seq && window.fm1.seq.playing, null, { timeout: 5000 });
  r.mode = await page.evaluate(() => window.fm1.state.mode);
  r.highlighted = await page.evaluate(() => window.fm1.files.highlighted);
  r.address = await page.evaluate(() => location.search);
  await page.screenshot({ path: join(out, 'files-05-linked.png') });
  await page.close();
  await ctx.close();
  r.pass = Object.values(r.refused).every((x) => x.notice && !x.arrival && x.requests.length === 0) &&
    r.card.title === 'First orbit' && r.card.button === 'Power on and load' && r.mode === 3 &&
    r.highlighted.join() === 'KNOB2,FX,PLAY' && r.address === '';
  return r;
}

// #lunar=: a round trip, the 32 KiB cap and a decompression bomb.
async function hashChecks() {
  const r = {};
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin });
  const page = await open(ctx);
  await powerOn(page);
  const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('#open')]);
  await chooser.setFiles(example('first-orbit.lunar'));
  await waitNotice(page, /^Loaded “First orbit”/);
  const original = await project(page);
  await page.click('#copy-link');
  await waitNotice(page, /^Link copied|would not copy/);
  r.copied = (await notice(page)).text;
  const link = await page.evaluate(() => window.fm1.files.link);
  r.link_chars = link.length;
  await page.close();
  const p2 = await open(ctx, link);
  await p2.waitForSelector('#arrival:not([hidden])');
  await powerOn(p2);
  await waitNotice(p2, /^Loaded “First orbit”/);
  r.round_trip = (await project(p2)) === original;
  await p2.close();
  const big = 'A'.repeat(32769);
  const p3 = await open(ctx, `${url}#lunar=${big}`);
  await waitNotice(p3, /could not be read/);
  r.over_cap = (await notice(p3)).text;
  await p3.close();
  const bomb = deflateRawSync(Buffer.from(`{"lunar":"1.0","kind":"project","about":"${' '.repeat(4 << 20)}"}`))
    .toString('base64url');
  r.bomb_chars = bomb.length;
  const p4 = await open(ctx, `${url}#lunar=${bomb}`);
  await waitNotice(p4, /could not be read/);
  r.bomb = (await notice(p4)).text;
  await p4.close();
  await ctx.close();
  r.pass = r.round_trip && /^Link copied: \d+ KiB of the 32 KiB|would not copy/.test(r.copied) &&
    /more than 32 KiB/.test(r.over_cap) && r.bomb_chars <= 32768 && /larger than the 256 KiB/.test(r.bomb);
  return r;
}

// ?embed=1: same-origin parent only.
const PARENT = `<!doctype html><meta charset="utf-8"><title>parent</title>
<iframe id="f" src="SRC" width="1200" height="800" allow="autoplay"></iframe>
<script>
window.got = [];
addEventListener('message', (e) => { window.got.push({ origin: e.origin, data: e.data }); });
window.call = (m) => new Promise((resolve) => {
  const id = Math.random();
  const on = (e) => { if (e.data && e.data.re === id) { removeEventListener('message', on); resolve(e.data); } };
  addEventListener('message', on);
  document.getElementById('f').contentWindow.postMessage({ lunar: 1, id, ...m }, '*');
  setTimeout(() => resolve({ timeout: true }), 3000);
});
</script>`;
async function embedChecks() {
  const r = {};
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route('**/__parent.html', (route) => route.fulfill({ contentType: 'text/html',
    body: PARENT.replace('SRC', `${origin}/index.html?embed=1&load=examples/first-orbit.lunar`) }));
  // Same origin.
  const page = await ctx.newPage();
  page.on('pageerror', (e) => report.logs.push(`embed pageerror: ${e.message}`));
  await page.goto(`${origin}/__parent.html`);
  await page.waitForFunction(() => window.got.some((g) => g.data.event === 'ready'), null, { timeout: 10000 });
  const frame = page.frameLocator('#f');
  r.embed_class = await frame.locator('body').evaluate((b) => b.classList.contains('embed'));
  r.query_off = await page.evaluate(() => window.call({ op: 'query', kind: 'project' }));
  await frame.locator('#power-on').click();
  await page.waitForFunction(() => window.got.some((g) => g.data.event === 'power' && g.data.on), null, { timeout: 20000 });
  await wait(page, 600);
  r.query = await page.evaluate(async () => {
    const q = await window.call({ op: 'query', kind: 'project' });
    return { ok: q.ok, kind: q.json && q.json.kind, title: q.json && q.json.title, sounds: q.json && q.json.sounds.length };
  });
  r.save = await page.evaluate(async () => { const s = await window.call({ op: 'save', kind: 'sound', into: 1 }); return { ok: s.ok, head: (s.text || '').slice(0, 40) }; });
  r.highlight = await page.evaluate(() => window.call({ op: 'highlight', controls: ['knob1', 'NOPE'] }));
  r.transport = await page.evaluate(() => window.call({ op: 'transport', play: true }));
  r.load = await page.evaluate(() => window.call({ op: 'load', kind: 'sound', into: 's3',
    text: '{"lunar":"1.0","kind":"sound","title":"Probe","sound":{"engine":"nope"}}' }));
  r.bad_op = await page.evaluate(() => window.call({ op: 'midi', port: 'FM-1' }));
  r.origins = await page.evaluate(() => [...new Set(window.got.map((g) => g.origin))]);
  await wait(page, 400);
  r.changed = await page.evaluate(() => window.got.some((g) => g.data.event === 'changed'));
  await page.close();
  // Another origin frames it: no event reaches it, and its calls get no answer.
  await ctx.route('**/__foreign.html', (route) => route.fulfill({ contentType: 'text/html',
    body: PARENT.replace('SRC', `${origin}/index.html?embed=1`) }));
  const foreign = await ctx.newPage();
  await foreign.goto(`http://lunar.test:${PORT}/__foreign.html`);
  await wait(foreign, 1500);
  r.foreign_reply = await foreign.evaluate(() => window.call({ op: 'query', kind: 'project' }));
  r.foreign_got = await foreign.evaluate(() => window.got.length);
  await foreign.close();
  await ctx.close();
  r.pass = r.embed_class && r.query_off.ok === false && r.query.ok && r.query.kind === 'project' &&
    r.query.title === 'First orbit' && r.query.sounds === 4 && r.save.ok && /"kind": "sound"/.test(r.save.head) &&
    r.highlight.ok && r.highlight.controls.join() === 'KNOB1' && r.transport.ok &&
    r.load.ok === false && r.load.report && r.load.report.code === 'UNKNOWN' &&
    r.bad_op.ok === false && r.origins.join() === origin && r.changed &&
    r.foreign_reply.timeout === true && r.foreign_got === 0;
  return r;
}

// The page at desktop and phone widths, a notice and the library open.
async function layoutChecks() {
  const r = {};
  for (const [name, vp] of [['desktop', { width: 1440, height: 1100 }], ['phone', { width: 390, height: 844 }]]) {
    const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: name === 'phone' ? 2 : 1 });
    const page = await open(ctx);
    await powerOn(page);
    const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('#open')]);
    await chooser.setFiles(example('first-orbit.lunar'));
    await waitNotice(page, /^Loaded/);
    await page.click('details.library summary');
    await wait(page, 300);
    await page.locator('.files').scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(out, `files-06-${name}.png`), fullPage: true });
    r[name] = await page.evaluate(() => ({
      scroll_width: document.documentElement.scrollWidth,
      smallest: Math.min(...[...document.querySelectorAll('.files button, .files select, #file-notice button, .library summary, .lib-actions button')]
        .map((e) => { const b = e.getBoundingClientRect(); return Math.min(b.width, b.height); })),
    }));
    await ctx.close();
  }
  r.pass = r.desktop.scroll_width <= 1440 && r.phone.scroll_width <= 390 && r.desktop.smallest >= 24 && r.phone.smallest >= 24;
  return r;
}

// The localhost exception. OTHER is another local dev server (Playwright
// answers for it; nothing listens there); PUBLIC_SIM is this page served
// under a name that is not local, as the public site is.
const OTHER = 'http://localhost:8799';
async function localChecks() {
  const r = {};
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const bytes = readFileSync(example('first-orbit.lunar'));
  await ctx.route(`${OTHER}/**`, (route) => {
    const p = new URL(route.request().url()).pathname;
    if (p === '/missions/first-orbit.lunar') {
      route.fulfill({ contentType: 'application/json', body: bytes, headers: { 'Access-Control-Allow-Origin': '*' } });
    } else if (p === '/__local.html') {
      route.fulfill({ contentType: 'text/html', body: PARENT.replace('SRC', `${origin}/index.html?embed=1`) });
    } else if (p === '/__public.html') {
      route.fulfill({ contentType: 'text/html', body: PARENT.replace('SRC', `http://lunar.test:${PORT}/index.html?embed=1`) });
    } else route.fulfill({ status: 404, body: '' });
  });
  // A parent on another local port: the ready event reaches it, and its calls are answered.
  const page = await ctx.newPage();
  page.on('pageerror', (e) => report.logs.push(`local pageerror: ${e.message}`));
  await page.goto(`${OTHER}/__local.html`);
  await page.waitForFunction(() => window.got.some((g) => g.data.event === 'ready'), null, { timeout: 10000 });
  r.ready_origin = await page.evaluate(() => window.got.find((g) => g.data.event === 'ready').origin);
  r.reply = await page.evaluate(() => window.call({ op: 'query', kind: 'project' }));
  await page.close();
  // ?load= from another local origin: the arrival card, then the load.
  const p2 = await open(ctx, `${url}?load=${encodeURIComponent(`${OTHER}/missions/first-orbit.lunar`)}`);
  await p2.waitForSelector('#arrival:not([hidden])', { timeout: 8000 });
  r.card = await p2.evaluate(() => document.getElementById('arrival-title').textContent);
  await p2.close();
  // The page served under a name that is not local: a local parent gets nothing...
  const p3 = await ctx.newPage();
  await p3.goto(`${OTHER}/__public.html`);
  await wait(p3, 1500);
  r.public_reply = await p3.evaluate(() => window.call({ op: 'query', kind: 'project' }));
  r.public_got = await p3.evaluate(() => window.got.length);
  await p3.close();
  // ...and ?load= from a local origin is refused, with no request made.
  const p4 = await ctx.newPage();
  const requests = [];
  p4.on('request', (q) => { if (!q.isNavigationRequest() && /\.lunar/.test(q.url())) requests.push(q.url()); });
  await p4.goto(`http://lunar.test:${PORT}/index.html?load=${encodeURIComponent(`${OTHER}/missions/first-orbit.lunar`)}`);
  await wait(p4, 600);
  const n = await notice(p4);
  r.public_load = { notice: n.shown && /refused/.test(n.tone), arrival: await p4.evaluate(() => !document.getElementById('arrival').hidden), requests };
  await p4.close();
  await ctx.close();
  r.pass = r.ready_origin === origin && r.reply.timeout !== true && r.reply.ok === false && r.card === 'First orbit' &&
    r.public_reply.timeout === true && r.public_got === 0 &&
    r.public_load.notice && !r.public_load.arrival && r.public_load.requests.length === 0;
  return r;
}

try {
  report.checks.files = await filesChecks();
  report.checks.load_link = await loadLinkChecks();
  report.checks.hash = await hashChecks();
  report.checks.embed = await embedChecks();
  report.checks.local = await localChecks();
  report.checks.layout = await layoutChecks();
} catch (err) {
  report.error = String(err && err.stack || err);
} finally {
  await browser.close();
  server.close();
}
const c = report.checks;
report.pass = !report.error && ['files', 'load_link', 'hash', 'embed', 'local', 'layout'].every((k) => c[k] && c[k].pass) &&
  !report.logs.some((l) => l.includes('pageerror'));
writeFileSync(join(out, 'files-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ pass: report.pass, browser: report.browser,
  ...Object.fromEntries(Object.entries(c).map(([k, v]) => [k, v.pass])), error: report.error, logs: report.logs.slice(0, 10) }));
process.exit(report.pass ? 0 : 1);
