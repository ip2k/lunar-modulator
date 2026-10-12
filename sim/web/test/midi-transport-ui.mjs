// Native sequencer/AudioWorklet; Web MIDI input only is mocked. MIT.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
const [www = 'sim/web/www', out = 'scratch/midi-transport-ui'] = process.argv.slice(2);
await mkdir(out, { recursive: true });
const { server, url } = await serve(www, 18922);
const { browser, name } = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const report = { browser: name, checks: [], errors: [] };
page.on('pageerror', e => report.errors.push(e.message));
await page.addInitScript(() => {
  const input = { id: '431288530', name: 'OXI E16 test input', state: 'connected' };
  Object.defineProperty(navigator, 'requestMIDIAccess', { configurable: true,
    value: async () => ({ inputs: new Map([[input.id, input]]) }) });
  window.emitCC = (number, value) => input.onmidimessage?.({ data: new Uint8Array([0xb0, number, value]) });
});
const check = async (label, test) => { await test(); report.checks.push(label); };
const ready = () => page.waitForFunction(() => fm1?.editor?.state?.mirror && !fm1.editor.state.sequenceBusy &&
  document.querySelector('.sq') && document.querySelector('.sq').getAttribute('aria-busy') !== 'true');
const state = (playing, paused = false) => page.waitForFunction(({playing,paused}) => !!fm1.seq?.playing === playing &&
  !!fm1.editor.sequencerHost.getTransport().paused === paused, {playing,paused});
const press = number => page.evaluate(number => { emitCC(number, 0); emitCC(number, 127); }, number);
async function learn(selector, cc) {
  await page.locator(selector).click(); await page.evaluate(cc => emitCC(cc, 127), cc);
  await page.waitForFunction(cc => [...fm1.midiLearn.map.bindings.values()].some(b => b.number === cc), cc);
  await page.evaluate(() => fm1.files.projectSnapshot()); await ready();
}
try {
  await page.goto(`${url}?load=examples/satellite-hearts.lunar&view=sequencer`);
  await page.getByRole('button', { name: 'Power on and load', exact: true }).click(); await ready();
  await check('mapping icon next to Panel MIDI connection and before Editor/Workbench Cheat Sheet', async () => {
    for (const layout of ['panel', 'workbench', 'editor']) {
      await page.locator(`button[data-layout=${layout}]`).focus(); await page.keyboard.press('Enter');
      await page.waitForFunction(layout => document.body.dataset.layout === layout &&
        document.getElementById('midi-learn').nextElementSibling?.id === (layout === 'panel' ? 'midi' : 'open-cheat-sheet'), layout);
    }
    await ready();
  });
  await page.click('#midi-learn');
  await page.getByRole('button', { name: 'Connect MIDI', exact: true }).click();
  await learn('[data-testid=seq-play]', 29); await learn('[data-midi-id="seq:transport:stop"]', 30);
  await check('closed Files menu is concealed and its controls cannot learn or dispatch MIDI', async () => {
    const result = await page.evaluate(async () => {
      const { nativeTarget, targetId } = await import('./midi-map.js');
      const tools = document.querySelector('.sq-file-tools'), summary = tools.querySelector('summary');
      const menu = tools.querySelector('.sq-file-menu'), controls = [...menu.querySelectorAll('button')];
      // Availability must respect disclosure state even if custom CSS leaves geometry.
      const oldDisplay = menu.style.display; menu.style.display = 'grid';
      const unavailable = controls.every(control => !nativeTarget(control).available());
      const summaryAvailable = nativeTarget(summary).available(); menu.style.display = oldDisplay;
      const hidden = getComputedStyle(menu).display === 'none';
      const unmarked = controls.every(control => ![...document.querySelectorAll('.midi-learn-target')]
        .some(mark => mark.dataset.target === targetId(control)));
      return { closed: !tools.open, hidden, unavailable, summaryAvailable, unmarked };
    });
    assert.ok(Object.values(result).every(Boolean), JSON.stringify(result));
  });
  await check('scrolled body highlights stop at the pinned toolbar; covered controls have no ghost targets', async () => {
    const geometry = await page.evaluate(async () => {
      const { targetId } = await import('./midi-map.js');
      const pager = document.querySelector('[aria-label="Next scenes page"]');
      const bar = document.querySelector('.ed-topbars');
      window.scrollBy(0, Math.max(0, pager.getBoundingClientRect().top - bar.getBoundingClientRect().bottom + 15));
      const bottom = bar.getBoundingClientRect().bottom;
      const controls = [...document.querySelectorAll('.ed-body button, .ed-body [role=button], .ed-body input, .ed-body select, .ed-body summary')];
      return { bodyIds: controls.map(targetId), covered: controls
        .filter(control => control.getClientRects().length && control.getBoundingClientRect().bottom <= bottom)
        .map(targetId) };
    });
    assert.ok(geometry.covered.length, 'fixture has body controls covered by the pinned toolbar');
    await page.waitForFunction(({covered, bodyIds}) => {
      const bottom = document.querySelector('.ed-topbars').getBoundingClientRect().bottom;
      const marks = [...document.querySelectorAll('.midi-learn-target')];
      return covered.every(id => !marks.some(mark => mark.dataset.target === id)) &&
        marks.filter(mark => bodyIds.includes(mark.dataset.target)).every(mark => {
          const r = mark.getBoundingClientRect();
          return r.bottom <= document.querySelector('.ed-topbars').getBoundingClientRect().top + .1 || r.top >= bottom - .1;
        });
    }, geometry);
    assert.ok(await page.locator('.midi-learn-target[data-target="seq:transport:play-pause"]').count(),
      'toolbar transport remains highlighted');
  });
  await check('teal CC29/CC30 badges remain on the actual controls with individual clear actions', async () => {
    await page.waitForFunction(() => !!document.querySelector('.midi-learn-target[data-target="seq:transport:play-pause"] .midi-learn-badge'));
    const geometry = await page.evaluate(() => ['seq:transport:play-pause', 'seq:transport:stop'].map(id => {
      const target = document.querySelector(`[data-midi-id="${id}"]`).getBoundingClientRect();
      const mark = document.querySelector(`.midi-learn-target[data-target="${id}"]`);
      const badge = mark.querySelector('.midi-learn-badge').getBoundingClientRect();
      const clear = mark.querySelector('button').getBoundingClientRect();
      return { id, text: mark.textContent, color: getComputedStyle(mark.querySelector('.midi-learn-badge')).backgroundColor,
        inside: badge.left >= target.left && badge.right <= target.right && badge.top >= target.top && badge.bottom <= target.bottom,
        clearInside: clear.left >= badge.left && clear.right <= badge.right && clear.top >= badge.top && clear.bottom <= badge.bottom };
    }));
    assert.ok(geometry.every(g => g.inside && g.clearInside), JSON.stringify(geometry));
    assert.ok(geometry.every(g => g.color.includes('85, 205, 177')));
    assert.ok(geometry[0].text.includes('CC29') && geometry[1].text.includes('CC30'));
    const clipping = await page.evaluate(() => [...document.querySelectorAll('.midi-learn-target')].map(mark => {
      const r = mark.getBoundingClientRect();
      return r.left >= -.1 && r.top >= -.1 && r.right <= innerWidth + .1 && r.bottom <= innerHeight + .1;
    }));
    assert.ok(clipping.every(Boolean), 'learn highlights stay inside the viewport');
    const gridClipping = await page.evaluate(async () => {
      const { targetId } = await import('./midi-map.js');
      const grid = document.querySelector('[data-scroll="scenes"]'), bounds = grid.getBoundingClientRect();
      return [...grid.querySelectorAll('button')].flatMap(control => {
        const mark = [...document.querySelectorAll('.midi-learn-target')].find(mark => mark.dataset.target === targetId(control));
        if (!mark) return [];
        const r = mark.getBoundingClientRect();
        return [r.top >= bounds.top + grid.clientTop - .1 && r.bottom <= bounds.top + grid.clientTop + grid.clientHeight + .1];
      });
    });
    assert.ok(gridClipping.length > 0 && gridClipping.every(Boolean), 'learn highlights respect the clipped Scenes grid');
    await page.screenshot({ path: `${out}/editor-teal-mappings.png` });
  });
  await page.click('#midi-learn');
  await check('CC29 presses play/pause/resume once per rising edge; CC30 stops at zero', async () => {
    await press(29); await state(true);
    await page.evaluate(() => { emitCC(29, 100); emitCC(29, 127); }); await state(true);
    await press(29); await state(false, true);
    await press(29); await state(true);
    await press(30); await state(false);
    assert.equal(await page.evaluate(() => fm1.seq.master_tick), 0);
  });
  await check('same-turn Clip redraw and MIDI press reach the replacement Play control', async () => {
    await page.evaluate(() => { document.querySelector('#sq-tab-Clip').click(); emitCC(29, 0); emitCC(29, 127); });
    await state(true); await press(30); await state(false);
  });
  await check('same assignments work in Workbench, Mixer and back in Editor', async () => {
    await page.locator('button[data-layout=workbench]').focus(); await page.keyboard.press('Enter'); await ready();
    await page.evaluate(() => { document.querySelector('#sq-tab-Mixer').click(); emitCC(29, 0); emitCC(29, 127); });
    await state(true); await press(30); await state(false);
    await page.locator('button[data-layout=editor]').focus(); await page.keyboard.press('Enter'); await ready();
    await press(29); await state(true); await press(30); await state(false);
  });
  await check('disabled transport cannot dispatch an edit', async () => {
    await page.evaluate(() => { const fieldset = document.querySelector('.sq-transport'); fieldset.disabled = true;
      emitCC(29, 0); emitCC(29, 127); fieldset.disabled = false; });
    assert.equal(await page.evaluate(() => fm1.seq.playing), false);
    await press(29); await state(true); await press(30); await state(false);
  });
  const stable = await page.evaluate(async () => JSON.parse((await fm1.files.projectSnapshot()).text));
  await check('stable transport mappings survive native project save/reload and another redraw', async () => {
    assert.deepEqual(stable.browser.midiMap.bindings.map(b => [b.target, b.number]),
      [['seq:transport:play-pause', 29], ['seq:transport:stop', 30]]);
    await page.evaluate(async doc => {
      fm1.midiLearn.map.import(null); await fm1.files.midiChanged();
      const result = await fm1.files.load(new TextEncoder().encode(JSON.stringify(doc)), {name:'transport.lunar', before:false, quiet:true});
      if (!result.ok) throw Error(JSON.stringify(result));
    }, stable); await ready();
    await press(29); await state(true); await press(30); await state(false);
  });
  await check('semantic legacy Play works; ambiguous Pause/Stop ordinals remain saved and inert', async () => {
    await page.evaluate(async () => {
      const legacy = {version:1, bindings:[
        {target:'ed/layout=editor/testid=seq-play/BUTTON.sq-button:0',source:'431288530',channel:0,kind:'cc',number:29},
        {target:'ed/layout=editor/BUTTON.sq-button:7',source:'431288530',channel:0,kind:'cc',number:30},
        {target:'ed/layout=editor/BUTTON.sq-button:8',source:'431288530',channel:0,kind:'cc',number:31},
      ]};
      fm1.midiLearn.map.import(legacy); await fm1.files.midiChanged();
      window.oldTargets = legacy.bindings.map(b=>b.target);
    });
    await press(29); await state(true);
    await press(30); await press(31); await state(true);
    await press(29); await state(false, true);
    assert.deepEqual(await page.evaluate(async () => JSON.parse((await fm1.files.projectSnapshot()).text).browser.midiMap.bindings.map(b=>b.target)),
      await page.evaluate(()=>oldTargets));
    await page.click('#midi-learn');
    await page.getByRole('button',{name:'Clear MIDI assignment for Resume',exact:true}).click();
    assert.equal(await page.evaluate(()=>fm1.midiLearn.map.export().bindings.length),2);
    await page.click('#midi-learn');
  });
  assert.deepEqual(report.errors, []);
  console.log(`${name}: native MIDI transport ${report.checks.length} checks passed`);
} catch(error) { report.failure = error.stack; throw error; }
finally { await writeFile(`${out}/report.json`, JSON.stringify(report,null,2)); await browser.close(); server.close(); }
