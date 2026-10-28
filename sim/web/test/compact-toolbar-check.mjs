import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const out = process.argv[3] || 'scratch/compact-toolbar-browser';
await mkdir(out, { recursive: true });
const { server, url } = await serve(process.argv[2] || 'sim/web/www', 18918);
const { browser } = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push(e.message));
const report = [];
let phase = 'startup';
try {
  await page.goto(url + '?view=sequencer');
  await page.getByRole('button', { name: 'Power on', exact: true }).click();
  await page.waitForFunction(() => fm1?.editor?.state?.mirror && document.querySelector('.sq-transport'));
  await page.evaluate(() => {
    window.toolbarTransportTrace = [];
    fm1.seqListeners.add(t => {
      toolbarTransportTrace.push({ at: performance.now(), playing: t.playing,
        paused: t.paused, tick: t.master_tick });
      if (toolbarTransportTrace.length > 32) toolbarTransportTrace.shift();
    });
  });
  const keys = page.locator('.ed-keys');
  const initialKeys = await keys.getAttribute('aria-pressed');
  await keys.click();
  assert.notEqual(await keys.getAttribute('aria-pressed'), initialKeys);
  await keys.click();
  assert.equal(await keys.getAttribute('aria-pressed'), initialKeys);
  const playPause = page.locator('[data-transport-play-pause]');
  assert.equal(await playPause.getAttribute('aria-label'), 'Play');
  phase = 'play';
  await playPause.click();
  await page.waitForFunction(() => document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label') === 'Pause');
  phase = 'pause';
  await playPause.click();
  await page.waitForFunction(() => document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label') === 'Resume');
  phase = 'resume';
  await playPause.click();
  await page.waitForFunction(() => document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label') === 'Pause');
  phase = 'stop';
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label') === 'Play');
  phase = 'toolbar geometry';
  for (const [width, height] of [[1440, 900], [1024, 768], [844, 390], [667, 375], [390, 844], [375, 812], [320, 812]]) {
    for (const layout of width <= 640 ? ['editor'] : ['editor', 'workbench']) {
      await page.locator(`button[data-layout="${layout}"]`).click();
      // Module Files adds a third menu; exercise the fuller toolbar as well as
      // worst-case meter values rather than relying on an empty default song.
      for (const view of ['sequencer', 'flow']) {
        await page.locator(view === 'sequencer' ? '.ed-out-seq' : '.ed-out-fx').click();
        await page.setViewportSize({ width, height });
        await page.waitForTimeout(100);
        if (view === 'sequencer') await page.waitForFunction(() => {
          const content = document.querySelector('.sq-content');
          if (!content.getClientRects().length) return true; // Portrait rotate prompt.
          const capacity = Math.max(1, Math.floor((Math.max(240, content.getBoundingClientRect().width - 28) - 140) / 150));
          return document.querySelectorAll('.sq-scene-head').length === Math.min(8, capacity);
        }, null, { timeout: 5000 });
        const geometry = await page.evaluate(() => {
          const rect = e => { const r = e.getBoundingClientRect(); return { x:r.x, y:r.y, w:r.width, h:r.height, right:r.right, bottom:r.bottom }; };
          const bar = document.querySelector('.ed-appbar'), tools = bar.querySelector('.ed-appbar-end');
          tools.querySelector('.ed-cpu-text').textContent = '100.0 %';
          tools.querySelector('.ed-ram-text').textContent = '100 %';
          const visible = [...tools.children].filter(e => getComputedStyle(e).display !== 'none' && !e.hidden);
          const meter = [tools.querySelector('.ed-cpu'), tools.querySelector('.ed-ram')];
          const top = document.querySelector('.ed-topbars');
          const scene = document.querySelector('.sq-view-panel .sq-section h3');
          return {
            appbar:rect(bar), tools:visible.map(e => ({name:e.className, ...rect(e)})),
            meters:meter.map(rect), sidebar:rect(bar.querySelector('.ed-sidebar-toggle')),
            meterOverflow:meter.map(e => ({name:e.className, scroll:e.scrollWidth, client:e.clientWidth})),
            meterContents:[...bar.querySelectorAll('.ed-cpu-text, .ed-cpu-bar, .ed-ram-text, .ed-ram-bar')]
              .map(e => ({name:e.className, child:rect(e), parent:rect(e.closest('.ed-cpu, .ed-ram'))})),
            title:rect(bar.querySelector('.ed-title')), keys:rect(bar.querySelector('.ed-keys')),
            transport:document.querySelector('.ed-transport-tools').hidden ? null : rect(document.querySelector('.ed-transport-tools')),
            scene:scene ? rect(scene) : null, top:rect(top), scrollWidth:document.documentElement.scrollWidth,
            sceneHeaders:[...document.querySelectorAll('.sq-scene-head')].map(rect),
            width:innerWidth, menuText:[...tools.querySelectorAll('summary')].map(e=>e.textContent.trim()),
            playPause:document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label'),
          };
        });
        report.push({ layout, view, width, height, geometry });
        await writeFile(`${out}/report.json`, JSON.stringify({ report, errors }, null, 2));
        assert.equal(geometry.scrollWidth, width, `horizontal scroll at ${width}x${height}`);
        assert.ok(geometry.tools.every(t => t.w >= 24 && t.h >= 24), `toolbar targets below 24 px at ${width}x${height}`);
        assert.ok(geometry.tools.every(t => Math.abs(t.y - geometry.tools[0].y) < 11), `tools row wrapped at ${width}x${height}`);
        assert.ok(geometry.tools.every(t => t.x >= geometry.appbar.x - 1 && t.right <= geometry.appbar.right + 1),
          `toolbar control escapes header at ${layout} ${width}x${height}: ${JSON.stringify(geometry.tools)}`);
        assert.ok(geometry.meterContents.every(({child,parent}) => child.x >= parent.x - 1 && child.right <= parent.right + 1),
          `meter content spills outside its control at ${width}x${height}: ${JSON.stringify(geometry.meterContents)}`);
        assert.ok(geometry.meterOverflow.every(({scroll,client}) => scroll <= client + 1),
          `meter text overflows at ${layout} ${width}x${height}: ${JSON.stringify(geometry.meterOverflow)}`);
        assert.ok(geometry.sidebar.right <= geometry.title.x, `sidebar order at ${width}x${height}`);
        assert.ok(geometry.title.right <= geometry.keys.x, `title overlaps Keys at ${width}x${height}`);
        assert.ok(!geometry.transport || geometry.transport.y >= geometry.appbar.bottom, `transport should be below header at ${width}x${height}`);
        await page.screenshot({ path: `${out}/toolbar-${layout}-${view}-${width}x${height}.png`, fullPage: false });
        for (const menu of await page.locator('.ed-appbar-end details').all()) {
          if (!(await menu.isVisible())) continue;
          await menu.locator('summary').first().click();
          const bounds = await menu.locator('.ed-footer-menu-body, .sq-file-menu').first().evaluate(e => {
            const r = e.getBoundingClientRect(); return { left:r.left, right:r.right, width:r.width };
          });
          assert.ok(bounds.left >= 0 && bounds.right <= width, `menu clipped at ${width}x${height}: ${JSON.stringify(bounds)}`);
          await menu.locator('summary').first().click();
        }
        await page.locator('.ed-ram').click();
        const ramBounds = await page.locator('.ed-ram-list').evaluate(e => { const r = e.getBoundingClientRect(); return { left:r.left, right:r.right }; });
        assert.ok(ramBounds.left >= 0 && ramBounds.right <= width, `RAM menu clipped at ${width}x${height}: ${JSON.stringify(ramBounds)}`);
        await page.locator('.ed-ram').click();
      }
    }
  }
  await writeFile(`${out}/report.json`, JSON.stringify({ report, errors }, null, 2));
  assert.deepEqual(errors, []);
  console.log(`Compact toolbar checks passed at ${report.map(({layout,view,width,height}) => `${layout}/${view} ${width}x${height}`).join(', ')}`);
} catch (error) {
  const state = await page.evaluate(() => {
    const button = document.querySelector('[data-transport-play-pause]');
    return { trace: window.toolbarTransportTrace, transport: window.fm1?.seq,
      audioContext: window.fm1?.ctx?.state, label: button?.getAttribute('aria-label'),
      disabled: button?.matches(':disabled'), busy: document.querySelector('.sq')?.getAttribute('aria-busy') };
  }).catch(e => ({ unavailable: String(e) }));
  await writeFile(`${out}/compact-toolbar-failure.json`, JSON.stringify({ phase, state, errors, error: String(error) }, null, 2));
  await page.screenshot({ path: `${out}/compact-toolbar-failure.png` }).catch(() => {});
  throw error;
} finally { await browser.close(); server.close(); }
