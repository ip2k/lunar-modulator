// Real browser/AudioWorklet project defaults; no hardware or listening claim. MIT.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
const [www = 'sim/web/www', out = 'scratch/initial-view-ui'] = process.argv.slice(2);
await mkdir(out, { recursive: true });
const { server, url } = await serve(www, 18879, { prefix: '/lunar-modulator/' });
const { browser, name } = await launch();
const report = { browser: name, checks: [], errors: [] };
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
page.setDefaultTimeout(20000); page.on('pageerror', e => report.errors.push(e.message));
const waitView = view => page.waitForFunction(v => fm1.editor?.state.view === v && fm1.editor.state.mirror && !fm1.editor.state.loading, view);
async function check(label, fn) { await fn(); report.checks.push(label); console.log(`PASS ${label}`); }
async function load(sequence, options = {}) {
  return page.evaluate(async ({ sequence, options }) => {
    const { emptySet, emptyClip, writeSet } = await import('/lunar-modulator/editor/sequence-model.js');
    const doc = JSON.parse((await fm1.files.projectSnapshot()).text);
    const set = emptySet();
    if (sequence) {
      set.tracks[0].clips[0] = emptyClip();
      set.tracks[0].clips[0].notes = [{ tick: 0, gate: 24, pitch: 60, vel: 90, step: 0 }];
      set.song = [0];
    }
    doc.set = writeSet(set);
    const r = await fm1.files.load(new TextEncoder().encode(JSON.stringify(doc)), {
      d: { enc: 0, kind: 'project', title: sequence ? 'Sequence fixture' : 'Sound fixture' }, quiet: true, ...options,
    });
    if (!r.ok) throw Error(JSON.stringify(r));
  }, { sequence, options });
}
try {
  await page.goto(url);
  await page.getByRole('button', { name: 'Power on', exact: true }).click();
  await page.waitForFunction(() => fm1.state && Number.isInteger(fm1.seq?.contentGen));
  await check('sequence loaded in Panel opens Song on first Workbench entry', async () => {
    await load(true);
    assert.equal(await page.evaluate(() => !!fm1.editor), false);
    await page.locator('[data-layout="workbench"]').click(); await waitView('sequencer');
    await page.waitForFunction(() => !!document.querySelector('.sq'));
  });
  await check('explicit sound selection survives delayed snapshots and layout changes', async () => {
    await page.locator('button.ed-s1').click(); await waitView('sound');
    await page.evaluate(async () => {
      await fm1.editor.sequencerHost.applyProject(await fm1.editor.sequencerHost.fetchProject(), 'Same-project refresh');
    });
    await waitView('sound');
    await page.locator('[data-layout="panel"]').click();
    await page.locator('button[data-layout="editor"]').focus(); await page.keyboard.press('Enter'); await waitView('sound');
  });
  await check('new sound-only project defaults to Flow; next sequence project defaults to Song', async () => {
    await load(false); await waitView('flow');
    await page.locator('.ed-out-lib').click(); await waitView('library');
    await page.locator('button[data-layout="panel"]').focus(); await page.keyboard.press('Enter');
    await load(true); await waitView('sequencer');
    assert.equal(await page.evaluate(() => document.body.dataset.layout), 'panel');
    await page.locator('button[data-layout="workbench"]').focus(); await page.keyboard.press('Enter'); await waitView('sequencer');
  });
  await check('explicit selection link wins over an in-flight project snapshot', async () => {
    await page.evaluate(() => {
      const shadow = fm1.files.shadow;
      fm1.files.shadow = async (...args) => {
        const r = await shadow(...args);
        if (args[0] === 'save' && args[1].mod) await new Promise(resolve => setTimeout(resolve, 1000));
        return r;
      };
    });
    await load(true);
    await page.evaluate(() => fm1.editor.applyLink({ edit: true, sel: { key: 's1' } }));
    await waitView('flow'); await page.waitForTimeout(1100); await waitView('flow');
    await page.evaluate(() => fm1.editor.applyLink({ sequencer: true })); await waitView('sequencer');
  });
  await check('command palette selection wins over an in-flight project snapshot', async () => {
    await load(true);
    await page.evaluate(() => fm1.editor.project.openSearch());
    await page.locator('.ed-search-in').fill('Library');
    await page.getByRole('option', { name: 'Library', exact: true }).click();
    await waitView('library'); await page.waitForTimeout(1100); await waitView('library');
  });
  await check('editor opened before native project loading uses the loaded sequence', async () => {
    const early = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    early.on('pageerror', e => report.errors.push(e.message));
    await early.goto(`${url}?load=examples/afterglow-relay.lunar&view=edit`);
    await early.locator('button[data-layout="editor"]').focus(); await early.keyboard.press('Enter');
    await early.waitForFunction(() => !!fm1.editor);
    await early.locator('.ed-power').click();
    await early.waitForFunction(() => fm1.editor.state.view === 'sequencer' && fm1.editor.state.mirror && !fm1.editor.state.loading);
    await early.screenshot({ path: `${out}/sequence-initial-editor.png`, fullPage: true });
    await early.close();
  });
  await check('URL selection survives native load and later canonical refresh', async () => {
    const linked = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    linked.on('pageerror', e => report.errors.push(e.message));
    await linked.goto(`${url}?load=examples/afterglow-relay.lunar&view=edit&sel=s1`);
    await linked.getByRole('button', { name: 'Power on and load', exact: true }).click();
    await linked.waitForFunction(() => fm1.editor?.state.view === 'flow' && fm1.editor.state.selected === 's1' && !fm1.editor.state.loading);
    await linked.evaluate(async () => {
      const host = fm1.editor.sequencerHost;
      await host.applyProject(await host.fetchProject(), 'Linked same-project refresh');
    });
    assert.equal(await linked.evaluate(() => fm1.editor.state.view), 'flow');
    await linked.close();
  });
  assert.deepEqual(report.errors, []);
} catch (error) { report.failure = error.stack; throw error; }
finally { await writeFile(`${out}/report.json`, JSON.stringify(report, null, 2)); await browser.close(); server.close(); }
