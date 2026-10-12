// Real AudioWorklet/Wasm sequencer, file and render integration. No mock DSP.
// Run in the bounded Playwright LAN container: node sequencer-native.mjs WWW OUT
// BROWSER=chromium|firefox|webkit is handled by launch.mjs (Firefox needs audio).
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';

const [www = 'sim/web/www', out = 'scratch/sequencer-native'] = process.argv.slice(2);
await mkdir(out, { recursive: true });
const { server, url } = await serve(www, 18874, { prefix: '/lunar-modulator/' });
const { browser, name } = await launch();
const report = { browser: name, wasmSha256: createHash('sha256').update(await readFile(join(www, 'fm1.wasm'))).digest('hex'), scope: 'Real browser AudioWorklet, native Wasm state and offline worker; no hardware or listening acceptance.', checks: [], errors: [], wavs: [] };
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true });
page.setDefaultTimeout(20000);
page.on('pageerror', e => { report.errors.push(e.message); (report.errorStacks ??= []).push(e.stack); });
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
async function expandAutomation() {
  const controls = page.locator('.sq-automation-assign');
  if (!await controls.evaluate(e => e.open)) await controls.locator(':scope > summary').click();
}
async function reset() {
  await page.evaluate(async () => {
    const { emptySet, emptyClip, writeSet } = window.nativeTest.api;
    const doc = await fm1.editor.sequencerHost.fetchProject();
    doc.title = 'Native sequencer integration'; doc.master = [null, null]; doc.mod = { seed: 1, rack: [], cables: [] };
    doc.sounds = Array.from({ length: 4 }, () => ({ engine: 'test-sine', params: { Volume: .2 }, level: 50, inserts: [null, null], midi_fx: [] }));
    const set = emptySet(); set.bpmX100 = 30000; set.song = [0]; set.songEnd = 0;
    set.tracks[0].name = 'Native Bass';
    set.tracks[0].route = { kind: 1, index: 0 }; set.tracks[0].clips[0] = emptyClip(16);
    set.tracks[0].clips[0].notes = [{ tick: 0, gate: 96, pitch: 60, vel: 100, step: 0 }];
    doc.set = writeSet(set); await fm1.editor.sequencerHost.applyProject(doc, 'Native test fixture');
    await fm1.editor.sequencer.refresh();
  }); await idle();
}
async function openFile(file) {
  const chooser = page.waitForEvent('filechooser');
  await expandFiles();
  await page.locator('.ed-song-file-tools').getByRole('button', { name: 'Open…', exact: true }).click();
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
  await check('sidebar and native transport occupy their own pinned app-bar rows', async () => {
    const geometry = await page.evaluate(() => {
      const top = document.querySelector('.ed-topbars'), bar = top.querySelector('.ed-appbar');
      const host = top.querySelector('.ed-transport-tools'), transport = host.querySelector('.sq-transport');
      const children = [...bar.querySelector('.ed-appbar-start').children];
      const a = bar.getBoundingClientRect(), b = host.getBoundingClientRect();
      return { order: children.slice(0, 3).map(e => e.className), sticky: getComputedStyle(top).position,
        outsideWorkspace: !!transport && !transport.closest('.sq'), gap: b.top-a.bottom,
        aligned: Math.abs(a.left-b.left)<1 && Math.abs(a.width-b.width)<1 };
    });
    assert.deepEqual(geometry.order, ['layout-switch', 'ed-icon ed-sidebar-toggle', 'ed-title']);
    assert.equal(geometry.sticky, 'sticky'); assert.equal(geometry.outsideWorkspace, true);
    assert.ok(Math.abs(geometry.gap)<1 && geometry.aligned, JSON.stringify(geometry));
    for (const view of ['Arrangement', 'Clip', 'Automation', 'Mixer']) {
      await tab(view);
      assert.equal(await page.locator('.ed-transport-tools .sq-transport').count(), 1);
    }
    await page.evaluate(() => fm1.editor.select('s1', { view: 'sound' }));
    assert.equal(await page.locator('.ed-transport-tools').isHidden(), true);
    await page.evaluate(() => fm1.editor.select('s1', { view: 'sequencer' }));
    await idle();
    assert.equal(await page.locator('.ed-transport-tools').isVisible(), true);
  });
  await check('track header names survive native commit and project undo/redo', async () => {
    await tab('Scenes');
    const name = page.getByLabel('Track 1 name', { exact: true });
    await name.dblclick(); await name.fill(' Bass 1 '); await name.press('Enter'); await idle();
    assert.equal((await model()).tracks[0].name, ' Bass 1 ');
    const doc = await page.evaluate(async () => JSON.parse((await fm1.files.projectSnapshot()).text));
    assert(doc.set.includes('tn 0 2042617373203120'));
    await page.evaluate(() => fm1.editor.undo());
    await until(async () => (await model()).tracks[0].name === 'Native Bass', 'undo track name');
    // Native state is visible before restoreHistory finishes saving its snapshot.
    // Wait for the enabled-control contract before issuing the next command.
    await idle();
    await page.evaluate(() => fm1.editor.redo());
    await until(async () => (await model()).tracks[0].name === ' Bass 1 ', 'redo track name');
    await idle();
    await reset();
  });
  await check('assigned bases preserve linear, logarithmic and enum parameter positions', async () => {
    await tab('Automation');
    await expandAutomation();
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
    const actions = page.locator('.sq-clip-actions');
    assert.equal(await actions.getByRole('button', { name: 'Add note', exact: true }).isVisible(), true);
    assert.equal(await actions.getByLabel('New note pitch', { exact: true }).isVisible(), true);
    await page.locator('.sq-note').first().click();
    for (const label of ['MIDI pitch', 'Step', 'Gate · ticks', 'Velocity']) assert.equal(await page.getByLabel(label, { exact: true }).isVisible(), true);
    const advanced = page.locator('.sq-note-details details.sq-note-advanced');
    assert.equal(await advanced.evaluate(e => e.open), false);
    assert.equal(await page.getByLabel('Probability %', { exact: true }).isVisible(), false);
    const summary = page.locator('.sq-note-advanced > summary');
    await summary.focus(); await summary.press('Enter');
    assert.equal(await advanced.evaluate(e => e.open), true);
    await field('Velocity', 72); await field('Gate · ticks', 48); await field('Microtiming · ticks', 3); await field('Probability %', 70);
    assert.equal(await advanced.evaluate(e => e.open), true);
    assert.equal(await page.evaluate(() => document.activeElement.getAttribute('aria-label')), 'Probability %');
    await tab('Automation');
    await expandAutomation();
    await page.getByLabel('Automation target', { exact: true }).selectOption('mix'); await idle();
    await field('Lane 1, step 1 lock', 91);
    const m = await model(), c = m.tracks[0].clips[0];
    assert.deepEqual(c.notes[0], { tick: 3, gate: 48, pitch: 60, vel: 72, step: 0 });
    assert.equal(c.trigs[0].prob, 70); assert.equal(m.tracks[0].lanes[0].label, 'mix:Level'); assert.equal(m.tracks[0].lanes[0].base, 64); assert.equal(c.locks[0].value, 91);
  });
  await check('routing, native chain repeats and project undo/redo', async () => {
    await tab('Arrangement');
    assert.equal(await page.getByRole('button', { name: /Track 1, Scene 1, 1 note, 1 bar/ }).isVisible(), true);
    await page.getByLabel('Track 8 output', { exact: true }).selectOption('m16'); await idle();
    assert.deepEqual((await model()).tracks[7].route, { kind: 0, index: 16 });
    await page.locator('.sq-section-tools > summary').filter({ hasText: /^Section tools$/ }).click();
    await field('Repeats', 3); assert.equal((await model()).song.length, 3);
    await page.evaluate(() => fm1.editor.undo()); await until(async () => (await model()).song.length === 1, 'undo repeats'); await idle();
    await page.evaluate(() => fm1.editor.redo()); await until(async () => (await model()).song.length === 3, 'redo repeats'); await idle();
  });
  await check('native clip matrix launch advances real transport and playhead', async () => {
    await tab('Scenes');
    const visibleScenes = await page.locator('.sq-scene-head').count();
    assert.ok(visibleScenes > 0 && visibleScenes <= 8);
    assert.equal(await page.locator('.sq-scene-title [data-scene-launch]').count(), visibleScenes);
    assert.equal(await page.locator('.sq-matrix-cell [data-scene-launch]').count(), visibleScenes * 8);
    assert.equal(await page.getByRole('button', { name: 'Launch scene 1', exact: true }).isVisible(), true);
    assert.equal(await page.locator('.sq-scene-title [data-scene-launch]').first().innerText(), '▶');
    assert.match(await page.locator('.sq-matrix-cell [data-scene-launch]').first().innerText(), /^▶(?:\s|$)/);
    assert.equal(await page.locator('.sq-scene-title').first().evaluate(e => e.firstElementChild.hasAttribute('data-scene-launch')), true);
    assert.equal(await page.locator('.sq-matrix-cell').first().evaluate(e => e.firstElementChild.hasAttribute('data-scene-launch')), true);
    const slots = new Set(), next = page.getByRole('button', { name: 'Next scenes page', exact: true });
    for (let pageIndex = 0; pageIndex < 8; pageIndex++) {
      const visible = await page.locator('[data-live-track]').evaluateAll(cells => cells.map(c => `${c.dataset.liveTrack}:${c.dataset.liveScene}`));
      assert.ok(visible.length >= 8 && visible.length <= 64 && visible.length % 8 === 0);
      visible.forEach(slot => slots.add(slot));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      if (await next.isDisabled()) break;
      await next.click();
    }
    assert.deepEqual([...slots].sort(), Array.from({length: 8}, (_, t) => Array.from({length: 8}, (_, s) => `${t}:${s}`)).flat().sort());
    const previous = page.getByRole('button', { name: 'Previous scenes page', exact: true });
    while (!await previous.isDisabled()) await previous.click();
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
    const routingFx = page.getByRole('button', { name: 'Routing & FX', exact: true });
    assert.equal(await routingFx.getAttribute('aria-expanded'), 'true');
    assert.equal(await page.locator('.sq-track-routing').isVisible(), true);
    assert.equal(await page.locator('.sq-device-rack').first().isVisible(), true);
    await page.setViewportSize({ width: 844, height: 390 });
    await until(async () => await routingFx.getAttribute('aria-expanded') === 'false', 'landscape routing disclosure aria state');
    assert.equal(await routingFx.getAttribute('aria-expanded'), 'false');
    assert.equal(await page.locator('.sq-track-routing').isVisible(), false);
    await page.setViewportSize({ width: 1440, height: 1100 });
    await until(async () => await routingFx.getAttribute('aria-expanded') === 'true', 'desktop routing disclosure aria state');
    assert.equal(await routingFx.getAttribute('aria-expanded'), 'true');
    assert.equal(await page.locator('.sq-track-routing').isVisible(), true);
    const fader = page.getByRole('slider', { name: 'S1 level', exact: true });
    const before = Number(await fader.inputValue());
    await fader.focus(); await fader.press('ArrowUp');
    await until(async () => Number(await fader.inputValue()) === before + 1, 'keyboard fader value and native mirror update');
    await until(async () => Number(await page.evaluate(() => fm1.editor.state.mirror.levels[0])) === before + 1, 'native sound level update');
    assert.match(await fader.getAttribute('aria-valuetext'), /dB$/);
    report.checks.push('measured sound/master meters and keyboard fader edit update native mirror');
    await page.evaluate(() => fm1.editor.sequencer.refresh());
    await fader.focus();
    // Hold a real tab press across resize frames, including a frame after
    // pointerup: Firefox may paint there before dispatching the click.
    await page.setViewportSize({ width: 844, height: 1100 });
    await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
    const clipTab = page.getByRole('tab', { name: 'Clip', exact: true });
    await clipTab.scrollIntoViewIfNeeded();
    const tabBox = await clipTab.boundingBox();
    await page.mouse.move(tabBox.x + tabBox.width / 2, tabBox.y + tabBox.height / 2);
    await page.mouse.down();
    await page.evaluate(() => fm1.editor.sequencer.refresh(true));
    await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
    await clipTab.evaluate(e => { window.heldClipTab = e; e.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); });
    await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
    assert.equal(await page.evaluate(() => window.heldClipTab.isConnected), true, 'resize keeps the released target until click');
    await page.mouse.up();
    assert.equal(await clipTab.getAttribute('aria-selected'), 'true');
    await page.setViewportSize({ width: 1440, height: 1100 });
    assert.notEqual(await page.locator('[data-roll-playhead]').getAttribute('style'), null);
    await page.locator('.ed-transport-tools').getByRole('button', { name: 'Stop', exact: true }).click();
    await page.waitForFunction(() => !fm1.seq.playing);
    for (const [i, release] of ['cancel', 'outside', 'no-click', 'new-press'].entries()) {
      await page.evaluate(() => {
        window.resizeTarget = document.querySelector('[data-view="Clip"]');
        window.resizeTarget.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
      });
      await page.setViewportSize({ width: i % 2 ? 1440 : 844, height: 1100 });
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      await page.evaluate(kind => {
        const e = new PointerEvent(kind === 'cancel' ? 'pointercancel' : 'pointerup', { bubbles: true });
        (kind === 'outside' ? document.body : window.resizeTarget).dispatchEvent(e);
        if (kind === 'new-press') window.resizeTarget.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
      }, release);
      if (release === 'new-press') {
        await page.waitForTimeout(300);
        assert.equal(await page.evaluate(() => window.resizeTarget.isConnected), true, 'old release cannot end a new press');
        await page.evaluate(() => window.resizeTarget.dispatchEvent(new PointerEvent('pointercancel', { bubbles: true })));
      }
      await page.waitForFunction(() => !window.resizeTarget.isConnected, null, { timeout: 2000 });
    }
    await page.evaluate(async () => {
      window.refreshTarget = document.querySelector('[data-view="Clip"]');
      window.refreshTarget.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
      await fm1.editor.sequencer.refresh(true);
    });
    assert.equal(await page.evaluate(() => window.refreshTarget.isConnected), true, 'refresh-only redraw waits for gesture');
    await page.evaluate(() => window.refreshTarget.dispatchEvent(new PointerEvent('pointercancel', { bubbles: true })));
    await page.waitForFunction(() => !window.refreshTarget.isConnected, null, { timeout: 2000 });
    await page.evaluate(async () => {
      const host = fm1.editor.sequencerHost, doc = await host.fetchProject();
      doc.sounds[0].engine = 'macro'; doc.sounds[0].params = { Model: 0, Harmonics: .5 };
      await host.applyProject(doc, 'Compact inspector fixture'); await fm1.editor.sequencer.refresh();
    }); await idle(); await tab('Mixer');
    const instrument = page.getByRole('button', { name: 'S1 instrument', exact: true });
    await instrument.click();
    const dialog = page.getByRole('dialog', { name: 'Device controls', exact: true });
    await dialog.waitFor({ state: 'visible' });
    assert.equal(await dialog.locator('.ed-page').count() > 0, true);
    const compactTools = dialog.locator('.ed-inspector-more');
    assert.equal(await compactTools.count(), 1);
    assert.equal(await dialog.locator('.ed-info-body').isVisible(), false);
    await dialog.getByRole('button', { name: 'About Macro', exact: true }).click();
    assert.equal(await dialog.locator('.ed-info-body').isVisible(), true);
    await page.keyboard.press('Escape');
    assert.equal(await dialog.locator('.ed-info-body').isVisible(), false);
    assert.equal(await dialog.locator('.ed-page').first().evaluate((p, more) => !!(p.compareDocumentPosition(more) & Node.DOCUMENT_POSITION_FOLLOWING), await compactTools.elementHandle()), true);
    assert.equal(await dialog.locator('.sq-device-dialog-footer .sq-file-tools').count(), 0);
    assert.equal(await page.locator('.ed-song-file-tools > .sq-file-tools').count(), 1);
    const moreSummary = compactTools.locator(':scope > summary');
    await moreSummary.focus(); await moreSummary.press('Enter');
    assert.equal(await compactTools.locator('.ed-tools').isVisible(), true);
    await moreSummary.press('Escape');
    assert.equal(await instrument.getAttribute('aria-expanded'), 'false');
    assert.equal(await page.evaluate(() => document.activeElement.getAttribute('aria-label')), 'S1 instrument');
    assert.equal(await page.locator('.ed-song-file-tools > .sq-file-tools').count(), 1);
    assert.equal(await dialog.locator('.sq-device-dialog-footer .sq-file-tools').count(), 0);
    await reset();
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
      await page.locator('.ed-song-file-tools').getByRole('button', { name: button, exact: true }).click();
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
    const automatic = [];
    const collectDownload = download => automatic.push(download);
    page.on('download', collectDownload);
    await expandFiles();
    await page.locator('.ed-song-file-tools').getByRole('button', { name: 'Export WAV…', exact: true }).click();
    await page.getByLabel('Effect tail (seconds)').fill('0'); await page.getByTestId('audio-export-start').click();
    await page.waitForFunction(() => document.querySelector('[data-testid="audio-export-status"]').textContent.includes('WAV downloads started'), null, { timeout: 120000 });
    await until(() => automatic.length === 6, 'six automatic WAV downloads');
    page.off('download', collectDownload);
    const links = page.getByTestId('audio-export-files').locator('a'); assert.equal(await links.count(), 6);
    for (let i = 0; i < 6; i++) {
      const download = automatic[i];
      const path = join(out, download.suggestedFilename()); await download.saveAs(path); const wav = await readFile(path);
      assert.equal(wav.toString('ascii', 0, 4), 'RIFF'); assert.equal(wav.toString('ascii', 8, 12), 'WAVE');
      const channels = wav.readUInt16LE(22), bits = wav.readUInt16LE(34), rate = wav.readUInt32LE(24);
      assert.ok(channels === 2 || channels === 8); assert.equal(bits, 24); assert.equal(rate, 44118);
      let data = -1; for (let offset = 12; offset + 8 <= wav.length;) { const size = wav.readUInt32LE(offset + 4); if (wav.toString('ascii', offset, offset + 4) === 'data') { data = size; break; } offset += 8 + size + size % 2; }
      assert.ok(data > 0); assert.equal(data % (channels * 3), 0); assert.ok(Math.abs(data / (channels * 3) - 44118 * .8) < 256);
      report.wavs.push({ file: download.suggestedFilename(), channels, bits, rate, frames: data / (channels * 3) });
    }
    assert.deepEqual(report.wavs.map(w => w.channels).sort(), [2,2,2,2,2,8]);
    const retry = page.waitForEvent('download'); await links.first().click();
    assert.equal((await retry).suggestedFilename(), automatic[0].suggestedFilename());
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
      if (view === 'Mixer') {
        const toggle = page.getByRole('button', { name: 'Routing & FX', exact: true });
        assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
        assert.equal(await page.locator('.sq-track-routing').isVisible(), false);
        assert.equal(await page.locator('.sq-device-rack').first().isVisible(), false);
        await toggle.focus(); await toggle.press('Enter');
        assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
        assert.equal(await page.evaluate(() => document.activeElement.getAttribute('aria-label')), 'Routing & FX');
        assert.equal(await page.locator('.sq-track-routing').isVisible(), true);
        assert.equal(await page.locator('.sq-device-rack').first().isVisible(), true);
        await toggle.click();
      }
      await page.screenshot({path:join(out,`native-landscape-${view.toLowerCase()}.png`),fullPage:true});
    }
    await page.setViewportSize({width:1440,height:1100});
    assert.equal(await page.locator('.ed-card').isVisible(), true);
    // Empty panel-following status stays quiet; a real status must remain visible.
    assert.equal(await page.locator('.ed-heads').isVisible(), await page.locator('.ed-from:not([hidden])').count() > 0);
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
