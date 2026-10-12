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
try {
  await page.goto(url + '?view=sequencer');
  await page.getByRole('button', { name: 'Power on', exact: true }).click();
  await page.waitForFunction(() => fm1?.editor?.state?.mirror && document.querySelector('.sq-transport'));
  const keys = page.locator('.ed-keys');
  const initialKeys = await keys.getAttribute('aria-pressed');
  await keys.click();
  assert.notEqual(await keys.getAttribute('aria-pressed'), initialKeys);
  await keys.click();
  assert.equal(await keys.getAttribute('aria-pressed'), initialKeys);
  const playPause = page.locator('[data-transport-play-pause]');
  assert.equal(await playPause.getAttribute('aria-label'), 'Play');
  await playPause.click();
  await page.waitForFunction(() => document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label') === 'Pause');
  await playPause.click();
  await page.waitForFunction(() => document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label') === 'Resume');
  await playPause.click();
  await page.waitForFunction(() => document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label') === 'Pause');
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label') === 'Play');
  for (const [width, height] of [[1440, 900], [1024, 768], [844, 390], [667, 375], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(100);
    const geometry = await page.evaluate(() => {
      const rect = e => { const r = e.getBoundingClientRect(); return { x:r.x, y:r.y, w:r.width, h:r.height, right:r.right, bottom:r.bottom }; };
      const bar = document.querySelector('.ed-appbar'), tools = bar.querySelector('.ed-appbar-end');
      const visible = [...tools.children].filter(e => getComputedStyle(e).display !== 'none' && !e.hidden);
      const meter = [tools.querySelector('.ed-cpu'), tools.querySelector('.ed-ram')];
      const top = document.querySelector('.ed-topbars');
      const scene = document.querySelector('.sq-view-panel .sq-section h3');
      return {
        appbar:rect(bar), tools:visible.map(e => ({name:e.className, ...rect(e)})),
        meters:meter.map(rect), sidebar:rect(bar.querySelector('.ed-sidebar-toggle')),
        title:rect(bar.querySelector('.ed-title')), transport:rect(document.querySelector('.ed-transport-tools')),
        scene:scene ? rect(scene) : null, top:rect(top), scrollWidth:document.documentElement.scrollWidth,
        width:innerWidth, menuText:[...tools.querySelectorAll('summary')].map(e=>e.textContent.trim()),
        playPause:document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label'),
      };
    });
    report.push({ width, height, geometry });
    assert.equal(geometry.scrollWidth, width, `horizontal scroll at ${width}x${height}`);
    assert.ok(geometry.tools.every(t => Math.abs(t.y - geometry.tools[0].y) < 11), `tools row wrapped at ${width}x${height}`);
    assert.ok(geometry.sidebar.right <= geometry.title.x, `sidebar order at ${width}x${height}`);
    assert.ok(geometry.transport.y >= geometry.appbar.bottom, `transport should be below header at ${width}x${height}`);
    await page.screenshot({ path: `${out}/toolbar-${width}x${height}.png`, fullPage: false });
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
  await writeFile(`${out}/report.json`, JSON.stringify({ report, errors }, null, 2));
  assert.deepEqual(errors, []);
  console.log(`Compact toolbar checks passed at ${report.map(({width,height}) => `${width}x${height}`).join(', ')}`);
} finally { await browser.close(); server.close(); }
