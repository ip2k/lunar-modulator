// SPDX-License-Identifier: MIT
// DOM glue for recovery.html. All protocol and safety logic is in
// recovery-transporter.js; this file only wires buttons to it.
import { openSerialTransport, serialSupported, TRANSPORTER_USB } from './recovery-serial.js';
import { TransporterLink, RecoverySession, AFTER_WRITE_GUIDE, WRITE_MIN, WRITE_END, LOADER_SIZE, LOADER_SHA256, sha256Hex } from './recovery-transporter.js';

const $ = (id) => document.getElementById(id);
let link = null;
let session = null;
let loaderBytes = null;
let image = null;
let plan = null;
let confirmedOff = false;
let busy = false;

const log = (msg) => { const el = $('log'); el.textContent += `${new Date().toISOString().slice(11, 19)}  ${msg}\n`; el.scrollTop = el.scrollHeight; };
const say = (id, text, cls = '') => { const el = $(id); el.textContent = text; el.className = cls; };
const hex = (a) => `0x${a.toString(16)}`;
function download(name, bytes) {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }));
  a.download = name.replace('.bin', `-${stamp}.bin`);
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
}
function bar(id, stage, done, total) { const p = $(id); p.hidden = false; p.max = total; p.value = done; if (done === total) log(`${stage}: done`); }

function refresh() {
  const connected = Boolean(session);
  $('btn-rekey').disabled = !connected || !confirmedOff || busy;
  $('btn-reconnect').disabled = connected || busy;
  $('btn-wait').disabled = !connected || !confirmedOff || !loaderBytes || busy;
  $('btn-backup').disabled = !connected || !session?.booted || busy;
  $('btn-plan').disabled = !session?.backup || !image || busy;
  $('btn-write').disabled = !plan || !plan.sectors.length || busy;
}
async function run(statusId, fn) {
  busy = true; refresh();
  try { await fn(); } catch (e) {
    say(statusId, e.message, 'rec-err'); log(`ERROR ${e.code || ''} ${e.message}`);
    if (e.code === 'port-closed') { session = null; link = null; }
  } finally { busy = false; refresh(); }
}

async function pickPort() {
  const port = await navigator.serial.requestPort({ filters: [TRANSPORTER_USB] });
  const transport = await openSerialTransport(port);
  link = new TransporterLink(transport);
  session = new RecoverySession(link, {
    save: async (name, bytes) => { download(name, bytes); log(`saved ${name}`); },
    progress: (stage, d, t) => bar(stage === 'write' ? 'prog-write' : 'prog-backup', stage, d, t),
    log,
    confirm: async (m) => window.confirm(m),
  });
  session.setConfirmedOff(confirmedOff);
  try { await session.connect(); } catch (e) { await link.close(); session = null; link = null; throw e; }
  const st = await session.status();
  log(`connected: ${st.raw}`);
  if (st.v15) log('WARNING: a running stock V15 is attached to the transporter; flash commands are blocked.');
  return st;
}

$('btn-connect').onclick = () => run('connect-state', async () => {
  const st = await pickPort();
  say('connect-state', st.v15 ? 'Connected, but a running V15 is attached: disconnect the Pico from the FM-1.' : 'Connected.', st.v15 ? 'rec-err' : 'rec-ok');
});
$('btn-reconnect').onclick = $('btn-connect').onclick;

$('chk-off').onchange = (e) => { confirmedOff = e.target.checked; session?.setConfirmedOff(confirmedOff); refresh(); };

$('file-loader').onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  loaderBytes = null;
  try {
    const bytes = new Uint8Array(await f.arrayBuffer());
    // size and hash are checked now; upload happens when boot mode is reached
    if (bytes.length !== LOADER_SIZE) throw new Error(`Expected ${LOADER_SIZE} bytes, got ${bytes.length}.`);
    const sha = await sha256Hex(bytes);
    if (sha !== LOADER_SHA256) throw new Error(`SHA-256 ${sha} does not match the expected loader.`);
    loaderBytes = bytes;
    say('loader-state', 'Loader accepted.', 'rec-ok');
  } catch (err) { say('loader-state', err.message, 'rec-err'); }
  refresh();
};

$('btn-rekey').onclick = () => run('key-state', async () => {
  const msg = await session.rekey();
  say('key-state', msg); log('rekey sent; port will close');
  session = null; link = null;
});

$('btn-wait').onclick = () => run('key-state', async () => {
  say('key-state', 'Waiting for boot mode. Switch the FM-1 ON now (not before the key is running).');
  await session.waitUboot(90000, 700);
  await session.uploadLoader(loaderBytes);
  const info = await session.identify();
  session.booted = true;
  say('key-state', `Boot mode, ${info.slice(3)}.`, 'rec-ok');
  log(`identified: ${info}`);
});

$('btn-backup').onclick = () => run('backup-state', async () => {
  say('backup-state', 'Reading twice (about a minute each)...');
  const b = await session.backupFlash();
  say('backup-state', `Two dumps match. SHA-256 ${b.sha256}. Both files were saved.`, 'rec-ok');
  log(`backup sha256 ${b.sha256}`);
});

$('file-image').onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  image = null; plan = null;
  try {
    image = await RecoverySession.parseImage(new Uint8Array(await f.arrayBuffer()), f.name);
    say('image-state', `${image.kind === 'fwsc' ? 'Stock V15 package' : '1 MiB flash image'} accepted. SHA-256 ${image.sha256}`, 'rec-ok');
  } catch (err) { say('image-state', err.message, 'rec-err'); }
  refresh();
};

$('btn-plan').onclick = () => run('write-state', async () => {
  plan = await session.plan(image);
  const out = $('plan-out'); out.hidden = false;
  out.textContent = `${plan.sectors.length} sector(s) differ within ${hex(WRITE_MIN)}-${hex(WRITE_END - 1)}:\n`
    + (plan.sectors.map(hex).join(' ') || '(none: the flash already holds this image)')
    + (plan.beyondWindow.length ? `\nNote: the image also differs at ${plan.beyondWindow.map(hex).join(' ')}, above ${hex(WRITE_END)}. This route never writes there; those sectors stay as they are.` : '')
    + '\nThe flash equals your backup over 0x0-0x92FFF; the boot area is unchanged. Nothing has been written.';
  log(`dry run: ${plan.sectors.length} sectors`);
  say('write-state', 'Dry run complete. Review it, then press Write.');
});

$('btn-write').onclick = () => run('write-state', async () => {
  const res = await session.write(plan);
  plan = null;
  say('write-state', res.written ? `Written and verified: ${res.written} sector(s). Final read SHA-256 ${res.finalSha256}.` : 'Nothing to write.', 'rec-ok');
  log(`write done: ${res.written} sectors`);
  const list = $('after-list'); list.replaceChildren(...AFTER_WRITE_GUIDE.map((t) => { const li = document.createElement('li'); li.textContent = t; return li; }));
  $('after-write').hidden = false;
});

if (!serialSupported()) {
  say('support-note', 'This browser has no Web Serial. Open this page in Chrome or Edge.', 'rec-err');
  $('btn-connect').disabled = true;
} else if (!window.isSecureContext) {
  say('support-note', 'This page is not in a secure context (https or localhost); Web Serial will refuse.', 'rec-err');
}
refresh();
