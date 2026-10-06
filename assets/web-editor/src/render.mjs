// render.mjs -- renders the web editor's mockups to ../NAME-WIDTH.png in a
// headless Chromium driven over the DevTools protocol (no npm packages: Node's
// own WebSocket), and prints each page's layout check (editor.js): text over
// text, text over a mark, a mark within 3 px of text, a cable over text,
// clipped text, sideways scroll.
//
//   CHROME=/path/to/chrome-headless-shell node render.mjs [NN ...]
//
// Desktop 1440 x 900 and tablet 1024 x 768, full page, 1x pixels.
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, readdirSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, '..');
const only = process.argv.slice(2);
const pages = readdirSync(here).filter((f) => /^\d\d-.*\.html$/.test(f))
  .filter((f) => !only.length || only.some((o) => f.startsWith(o)));
const SIZES = [[1440, 900], [1024, 768]];

const chrome = process.env.CHROME;
if (!chrome) { console.error('set CHROME to a Chromium headless shell'); process.exit(2); }
const profile = mkdtempSync(join(tmpdir(), 'lm-render-'));
const proc = spawn(chrome, ['--headless', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
  '--no-first-run', '--hide-scrollbars', '--force-device-scale-factor=1', '--allow-file-access-from-files',
  '--font-render-hinting=none', 'about:blank'], { stdio: 'ignore' });

const portFile = join(profile, 'DevToolsActivePort');
for (let i = 0; i < 100 && !existsSync(portFile); i++) await new Promise((r) => setTimeout(r, 100));
const [port, path] = readFileSync(portFile, 'utf8').trim().split('\n');
const ws = new WebSocket(`ws://127.0.0.1:${port}${path}`);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));

let id = 0;
const waiting = new Map();
const listeners = [];
ws.addEventListener('message', (e) => {
  const m = JSON.parse(e.data);
  if (m.id && waiting.has(m.id)) {
    const { ok, no } = waiting.get(m.id); waiting.delete(m.id);
    m.error ? no(new Error(m.error.message)) : ok(m.result);
  } else for (const f of listeners) f(m);
});
const send = (method, params = {}, sessionId) => new Promise((ok, no) => {
  const n = ++id; waiting.set(n, { ok, no });
  ws.send(JSON.stringify({ id: n, method, params, sessionId }));
});

const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId: s } = await send('Target.attachToTarget', { targetId, flatten: true });
const lines = [];
listeners.push((m) => {
  if (m.sessionId !== s) return;
  if (m.method === 'Runtime.consoleAPICalled') {
    const t = m.params.args.map((a) => a.value ?? a.description ?? '').join(' ');
    if (t.startsWith('LAYOUT')) lines.push(t);
  } else if (m.method === 'Runtime.exceptionThrown') lines.push('PAGEERROR ' + m.params.exceptionDetails.text + ' ' + (m.params.exceptionDetails.exception?.description || ''));
});
await send('Page.enable', {}, s);
await send('Runtime.enable', {}, s);

const evaluate = async (expr) => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }, s)).result.value;
let total = 0;
for (const f of pages) {
  for (const [w, h] of SIZES) {
    lines.length = 0;
    await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false }, s);
    await send('Page.navigate', { url: pathToFileURL(join(here, f)).href }, s);
    let ready = false;
    for (let i = 0; i < 100 && !ready; i++) {
      await new Promise((r) => setTimeout(r, 100));
      ready = await evaluate('document.documentElement.dataset.ready === "1"').catch(() => false);
    }
    if (!ready) lines.push('PAGEERROR not ready');
    if (process.env.EVAL) console.log('EVAL', JSON.stringify(await evaluate(process.env.EVAL)));
    const H = await evaluate('Math.ceil(document.documentElement.scrollHeight)');
    await send('Emulation.setDeviceMetricsOverride', { width: w, height: Math.max(h, H), deviceScaleFactor: 1, mobile: false }, s);
    await new Promise((r) => setTimeout(r, 150));
    // The layout may reflow at the taller window: check again at that size.
    lines.length = 0;
    await evaluate('window.MOCK && MOCK.relayout ? MOCK.relayout() : 0');
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, s);
    const name = f.replace('.html', `-${w}.png`);
    writeFileSync(join(out, name), Buffer.from(shot.data, 'base64'));
    const issues = lines.filter((l) => !l.startsWith('LAYOUT-SUMMARY'));
    total += issues.length;
    console.log(`${name}  ${H}px  ${lines.find((l) => l.startsWith('LAYOUT-SUMMARY')) || 'no summary'}`);
    for (const l of issues) console.log('   ' + l);
  }
}
console.log(`total issues: ${total}`);
ws.close();
await new Promise((r) => { proc.once('exit', r); proc.kill(); });
try { rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* a temp folder left behind */ }
