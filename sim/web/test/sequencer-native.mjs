// Real AudioWorklet/Wasm sequencer, file and render integration. No mock DSP.
// Run in the bounded Playwright LAN container: node sequencer-native.mjs WWW OUT
// BROWSER=chromium|firefox|webkit is handled by launch.mjs (Firefox needs audio).
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';

const [www = 'sim/web/www', out = 'scratch/sequencer-native'] = process.argv.slice(2);
await mkdir(out, { recursive: true });
const { server, url } = await serve(www, 18874, { prefix: '/lunar-modulator/' });
const { browser, name } = await launch();
const report = { browser: name, scope: 'Real browser AudioWorklet, native Wasm state and offline worker; no hardware or listening acceptance.', checks: [], errors: [], wavs: [] };
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true });
page.setDefaultTimeout(20000);
page.on('pageerror', e => report.errors.push(e.message));
async function check(label, fn) { await fn(); report.checks.push(label); console.log(`PASS ${label}`); }
async function tab(name) { await page.getByRole('tab', {name, exact:true}).click(); }
async function model() { return page.evaluate(async () => window.nativeTest.model()); }
async function until(fn, label) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) { if (await fn()) return; await page.waitForTimeout(80); }
  throw Error(`Timed out: ${label}; status=${await page.locator('.sq-status').allTextContents()}`);
}
async function idle() { await page.waitForFunction(() => !fm1.editor.state.sequenceBusy && document.querySelector('.sq') && document.querySelector('.sq').getAttribute('aria-busy') !== 'true'); }
async function field(label, value) {
  await idle(); const input = page.getByLabel(label, { exact: true });
  await input.fill(String(value)); await input.dispatchEvent('change'); await idle();
}
async function expandFiles() {
  const menu = page.locator('.sq-file-tools');
  if (!await menu.evaluate(e => e.open)) await menu.locator(':scope > summary').click();
}
async function reset() {
  await page.evaluate(async () => {
    const { emptySet, emptyClip, writeSet } = window.nativeTest.api;
    const doc = await fm1.editor.sequencerHost.fetchProject();
    doc.title = 'Native sequencer integration'; doc.master = [null, null]; doc.mod = { seed: 1, rack: [], cables: [] };
    doc.sounds = Array.from({ length: 4 }, () => ({ engine: 'test-sine', params: { Volume: .2 }, level: 50, inserts: [null, null], midi_fx: [] }));
    const set = emptySet(); set.bpmX100 = 30000; set.song = [0]; set.songEnd = 0;
    set.tracks[0].route = { kind: 1, index: 0 }; set.tracks[0].clips[0] = emptyClip(16);
    set.tracks[0].clips[0].notes = [{ tick: 0, gate: 96, pitch: 60, vel: 100, step: 0 }];
    doc.set = writeSet(set); await fm1.editor.sequencerHost.applyProject(doc, 'Native test fixture');
    await fm1.editor.sequencer.refresh();
  }); await idle();
}
async function openFile(file) {
  const chooser = page.waitForEvent('filechooser');
  await expandFiles();
  await page.locator('.sq').getByRole('button', { name: 'Open…', exact: true }).click();
  await (await chooser).setFiles(file);
  await until(async () => (await page.locator('.ed-sr').allTextContents()).join(' ').includes(`Opened ${file.name}`) ||
    await page.evaluate(name => fm1.editor.state.projectName === name, file.name), `open ${file.name}`);
  await idle();
}
try {
  await page.goto(`${url}?view=sequencer`);
  await page.getByRole('button', { name: 'Power on', exact: true }).click();
  await page.waitForFunction(() => window.fm1?.editor?.state.mirror && window.fm1.editor.sequencerHost, null, { timeout: 30000 });
  await page.evaluate(async () => {
    const api = await import('/lunar-modulator/editor/sequence-model.js');
    window.nativeTest = { api, model: async () => api.parseSet(JSON.parse((await fm1.files.projectSnapshot()).text).set),
      canonical: async () => JSON.stringify(api.writeSet(api.parseSet(JSON.parse((await fm1.files.projectSnapshot()).text).set))) };
  });
  await check('native fixture loads without discarded sequencer fields', async () => { await reset(); assert.equal((await model()).tracks[0].clips[0].notes[0].gate, 96); });
  await check('assigned bases preserve linear, logarithmic and enum parameter positions', async () => {
    await tab('Automation');
    await page.getByRole('button', { name: 'Assign parameter', exact: true }).click(); await idle();
    assert.equal((await model()).tracks[0].lanes[0].base, 25); // Volume .2 on 0..1, rounded to seven bits.
    await page.evaluate(async () => {
      const host = fm1.editor.sequencerHost, doc = await host.fetchProject();
      doc.sounds[0].inserts[0] = { engine: 'filter', params: { Type: 'Sallen-Key', Cutoff: 600 } };
      await host.applyProject(doc, 'Parameter law fixture'); await fm1.editor.sequencer.refresh();
    }); await idle();
    await page.getByLabel('Automation target', { exact: true }).selectOption('in1'); await idle();
    let lane = (await model()).tracks[0].lanes[0];
    assert.equal(lane.label, 'in1:Type'); assert.equal(lane.base, 64); // enum index3 of6: floor(64*6/128)=3.
    await page.getByLabel('Parameter', { exact: true }).selectOption('in1:Cutoff'); await idle();
    lane = (await model()).tracks[0].lanes[0];
    assert.equal(lane.label, 'in1:Cutoff'); assert.equal(lane.base, 64); // sqrt(20*18000)=600, midpoint in log space.
    await field('Base · 0–127', 73);
    await page.getByLabel('Parameter', { exact: true }).selectOption('in1:Cutoff'); await idle();
    assert.equal((await model()).tracks[0].lanes[0].base, 73); // Selecting the same assignment keeps the authored base.
    await reset();
  });
  await check('UI note articulation, probability and mix lock survive native load', async () => {
    await tab('Clip');
    await page.locator('.sq-note').first().click();
    await field('Velocity', 72); await field('Gate · ticks', 48); await field('Microtiming · ticks', 3); await field('Probability %', 70);
    await tab('Automation');
    await page.getByLabel('Automation target', { exact: true }).selectOption('mix'); await idle();
    await field('Lane 1, step 1 lock', 91);
    const m = await model(), c = m.tracks[0].clips[0];
    assert.deepEqual(c.notes[0], { tick: 3, gate: 48, pitch: 60, vel: 72, step: 0 });
    assert.equal(c.trigs[0].prob, 70); assert.equal(m.tracks[0].lanes[0].label, 'mix:Level'); assert.equal(m.tracks[0].lanes[0].base, 64); assert.equal(c.locks[0].value, 91);
  });
  await check('routing, native chain repeats and project undo/redo', async () => {
    await tab('Arrangement');
    await page.getByLabel('Track 8 output', { exact: true }).selectOption('m16'); await idle();
    assert.deepEqual((await model()).tracks[7].route, { kind: 0, index: 16 });
    await field('Repeats', 3); assert.equal((await model()).song.length, 3);
    await page.evaluate(() => fm1.editor.undo()); await until(async () => (await model()).song.length === 1, 'undo repeats');
    await page.evaluate(() => fm1.editor.redo()); await until(async () => (await model()).song.length === 3, 'redo repeats');
  });
  await check('native clip matrix launch advances real transport and playhead', async () => {
    await tab('Scenes');
    assert.equal(await page.locator('[data-live-track]').count(), 64);
    await page.getByRole('button', { name: 'Launch clip 1 scene 1', exact: true }).click();
    await page.waitForFunction(() => fm1.seq?.playing && fm1.seq.tracks[0].playing === 0 && fm1.seq.tracks[0].posTick > 0);
    await page.screenshot({ path: join(out, 'native-matrix.png'), fullPage: true });
    await tab('Mixer');
    await until(async () => {
      const sound = Number(await page.getByRole('meter', { name: 'S1 post-fader level', exact: true }).getAttribute('aria-valuenow'));
      const master = Number(await page.getByRole('meter', { name: 'Final master output level', exact: true }).getAttribute('aria-valuenow'));
      return sound > -60 && master > -60;
    }, 'measured sound and master output meters');
    await page.screenshot({ path: join(out, 'native-mixer-meter.png'), fullPage: true });
    const fader = page.getByRole('slider', { name: 'S1 level', exact: true });
    const before = Number(await fader.inputValue());
    await fader.focus(); await fader.press('ArrowUp');
    await until(async () => Number(await fader.inputValue()) === before + 1, 'keyboard fader value and native mirror update');
    await until(async () => Number(await page.evaluate(() => fm1.editor.state.mirror.levels[0])) === before + 1, 'native sound level update');
    assert.match(await fader.getAttribute('aria-valuetext'), /dB$/);
    report.checks.push('measured sound/master meters and keyboard fader edit update native mirror');
    await tab('Clip');
    assert.notEqual(await page.locator('[data-roll-playhead]').getAttribute('style'), null);
    await page.locator('.sq').getByRole('button', { name: 'Stop', exact: true }).click();
    await page.waitForFunction(() => !fm1.seq.playing);
    await tab('Arrangement');
  });
  await check('stale host documents and atomic worklet expectedHash preserve newer native edits', async () => {
    const r = await page.evaluate(async () => {
      const host = fm1.editor.sequencerHost, api = nativeTest.api;
      const stale = await host.fetchProject(), snap = await fm1.files.projectSnapshot();
      const current = await host.fetchProject(), m = api.parseSet(current.set); m.swing = 61; current.set = api.writeSet(m);
      await host.applyProject(current, 'Concurrent native edit');
      let refused = ''; try { await host.applyProject(stale, 'Stale test'); } catch (e) { refused = e.message; }
      const atomic = await fm1.files.load(new TextEncoder().encode(snap.text), { ask: false, before: false, quiet: true, same: true, expectedHash: snap.hash });
      return { refused, atomic, swing: (await nativeTest.model()).swing };
    });
    assert.match(r.refused, /changed/i); assert.equal(r.atomic.ok, false); assert.match(JSON.stringify(r.atomic), /CHANGED|changed/); assert.equal(r.swing, 61);
  });
  await check('two MIDI files preview, occupied-clip refusal and explicit replacement import', async () => {
    const midi = Buffer.from([77,84,104,100,0,0,0,6,0,0,0,1,0,96,77,84,114,107,0,0,0,12,0,144,67,100,96,128,67,0,0,255,47,0]);
    await expandFiles();
    await page.getByLabel('Import MIDI files', { exact: true }).setInputFiles(['Lead.mid', 'Bass.mid'].map(name => ({ name, mimeType: 'audio/midi', buffer: midi })));
    await page.getByTestId('midi-import-preview').waitFor();
    const before = await page.evaluate(() => nativeTest.canonical());
    await page.getByTestId('apply-midi-import').click(); await idle();
    assert.match((await page.locator('.sq-status').allTextContents()).join(' '), /occupied|existing|empty/i);
    assert.equal(await page.evaluate(() => nativeTest.canonical()), before);
    await page.getByLabel('Existing clips', { exact: true }).selectOption('replace');
    await page.getByTestId('apply-midi-import').click();
    await until(async () => (await model()).tracks[1].clips[0]?.notes.length === 1, 'two-file native import');
    assert.equal((await model()).tracks[0].clips[0].notes[0].pitch, 67);
  });
  await check('download and reopen text project, Movy set and binary project retain native set', async () => {
    const canonical = await page.evaluate(() => nativeTest.canonical());
    for (const [button, fileName] of [['Save .lunar', 'roundtrip.lunar'], ['Export .movy1', 'roundtrip.movy1']]) {
      await expandFiles();
      const pending = page.waitForEvent('download');
      await page.locator('.sq').getByRole('button', { name: button, exact: true }).click();
      const download = await pending; const path = join(out, fileName); await download.saveAs(path);
      await reset(); await openFile({ name: fileName, mimeType: 'application/octet-stream', buffer: await readFile(path) });
      assert.equal(await page.evaluate(() => nativeTest.canonical()), canonical);
    }
    const bytes = await page.evaluate(async () => Array.from((await fm1.files.shadow('pack', { text: (await fm1.files.projectSnapshot()).text })).bin));
    await reset(); await openFile({ name: 'binary.lunar', mimeType: 'application/octet-stream', buffer: Buffer.from(bytes) });
    assert.equal(await page.evaluate(() => nativeTest.canonical()), canonical);
  });
  await reset();
  await check('actual offline worker produces six downloadable WAVs with exact channel counts', async () => {
    await expandFiles();
    await page.locator('.sq').getByRole('button', { name: 'Export WAV…', exact: true }).click();
    await page.getByLabel('Effect tail (seconds)').fill('0'); await page.getByTestId('audio-export-start').click();
    await page.waitForFunction(() => document.querySelector('[data-testid="audio-export-status"]').textContent.includes('WAVs ready'), null, { timeout: 120000 });
    const links = page.getByTestId('audio-export-files').locator('a'); assert.equal(await links.count(), 6);
    for (let i = 0; i < 6; i++) {
      const pending = page.waitForEvent('download'); await links.nth(i).click(); const download = await pending;
      const path = join(out, download.suggestedFilename()); await download.saveAs(path); const wav = await readFile(path);
      assert.equal(wav.toString('ascii', 0, 4), 'RIFF'); assert.equal(wav.toString('ascii', 8, 12), 'WAVE');
      const channels = wav.readUInt16LE(22), bits = wav.readUInt16LE(34), rate = wav.readUInt32LE(24);
      assert.ok(channels === 2 || channels === 8); assert.equal(bits, 24); assert.equal(rate, 44118);
      let data = -1; for (let offset = 12; offset + 8 <= wav.length;) { const size = wav.readUInt32LE(offset + 4); if (wav.toString('ascii', offset, offset + 4) === 'data') { data = size; break; } offset += 8 + size + size % 2; }
      assert.ok(data > 0); assert.equal(data % (channels * 3), 0); assert.ok(Math.abs(data / (channels * 3) - 44118 * .8) < 256);
      report.wavs.push({ file: download.suggestedFilename(), channels, bits, rate, frames: data / (channels * 3) });
    }
    assert.deepEqual(report.wavs.map(w => w.channels).sort(), [2,2,2,2,2,8]);
  });
  await check('repeated render clears downloads and cancellation releases dialog', async () => {
    await page.getByLabel('Effect tail (seconds)').fill('30');
    const cleared = await page.getByTestId('audio-export-start').evaluate(button => { button.click(); return document.querySelectorAll('[data-testid="audio-export-files"] a').length; });
    assert.equal(cleared, 0);
    await page.getByRole('button', { name: 'Cancel render', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('[data-testid="audio-export-status"]').textContent.includes('cancelled'));
    assert.equal(await page.getByTestId('audio-export-start').isEnabled(), true);
    await page.getByRole('button', { name: 'Close', exact: true }).click();
    await page.locator('dialog.sq-export').waitFor({ state: 'detached' });
  });
  await check('focused views, phone rotate prompt and landscape native editing', async () => {
    await tab('Scenes');
    await page.getByRole('button', {name:'Edit track 1 scene 1',exact:true}).click();
    assert.equal(await page.getByRole('tab', {name:'Clip',exact:true}).getAttribute('aria-selected'), 'true');
    assert.equal(await page.getByRole('tabpanel').count(), 1);
    assert.equal(await page.getByTestId('scene-matrix').count(), 0);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.getByTestId('song-rotate-prompt').isVisible(), true);
    assert.equal(await page.getByRole('tab', {name:'Clip',exact:true}).isVisible(), false);
    await page.screenshot({path:join(out,'native-portrait.png'),fullPage:true});
    await page.setViewportSize({width:844,height:390});
    assert.equal(await page.getByTestId('song-rotate-prompt').isVisible(), false);
    assert.equal(await page.locator('.ed-card').isVisible(), false);
    assert.equal(await page.locator('.ed-heads').isVisible(), false);
    await page.locator('.sq-note').first().click(); await field('Velocity', 69);
    assert.equal((await model()).tracks[0].clips[0].notes[0].vel,69);
    for (const view of ['Clip','Automation','Mixer','Arrangement','Scenes']) {
      await tab(view);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth),false);
      await page.screenshot({path:join(out,`native-landscape-${view.toLowerCase()}.png`),fullPage:true});
    }
    await page.setViewportSize({width:1440,height:1100});
    assert.equal(await page.locator('.ed-card').isVisible(), true);
    assert.equal(await page.locator('.ed-heads').isVisible(), true);
    for (const view of ['Clip','Automation','Mixer','Arrangement','Scenes']) {
      await tab(view);
      await page.screenshot({path:join(out,`native-desktop-${view.toLowerCase()}.png`),fullPage:true});
    }
  });
  await page.screenshot({ path: join(out, 'native-final.png'), fullPage: true });
  assert.deepEqual(report.errors, []); report.passed = true;
} catch (error) {
  report.passed = false; report.failure = error.stack;
  await page.screenshot({ path: join(out, 'failure.png'), fullPage: true }).catch(() => {});
  console.error(error); process.exitCode = 1;
} finally {
  await writeFile(join(out, 'results.json'), JSON.stringify(report, null, 2));
  await browser.close(); await new Promise(resolve => server.close(resolve));
}
