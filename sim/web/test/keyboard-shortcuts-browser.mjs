import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const out = process.argv[3] || 'scratch/keyboard-shortcuts-browser';
await mkdir(out, { recursive: true });
const { server, url } = await serve(process.argv[2] || 'sim/web/www', 18921);
const { browser, name } = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
const report = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto(url + '?view=sequencer');
  await page.getByRole('button', { name: 'Power on', exact: true }).click();
  await page.waitForFunction(() => fm1?.editor?.state?.mirror && document.querySelector('.sq-transport'));
  const trigger = page.getByRole('button', { name: 'Keyboard shortcuts', exact: true });
  const dialog = page.getByRole('dialog', { name: 'Keyboard shortcuts' });
  assert.equal(await trigger.count(), 1);
  assert.equal(await trigger.getAttribute('title'), 'Keyboard shortcuts');
  assert.equal(await trigger.getAttribute('aria-haspopup'), 'dialog');
  assert.equal(await trigger.locator('svg').count(), 1);
  const keys = page.locator('.ed-keys');
  if (await keys.getAttribute('aria-pressed') !== 'false') await keys.click();
  assert.equal(await keys.getAttribute('aria-pressed'), 'false');
  await trigger.click();
  await dialog.waitFor({ state: 'visible' });
  assert.equal(await keys.getAttribute('aria-pressed'), 'false', 'opening guide should preserve playing mode');
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('aria-label')), 'Close keyboard shortcuts');
  assert.deepEqual(await dialog.locator('h3').allTextContents(), ['Editor', 'Song workspace', 'Editor controls', 'FM-1 panel']);
  assert.ok((await dialog.locator('.ed-shortcuts-row').count()) >= 25);

  for (const [width, height] of [[1440, 900], [844, 390], [667, 375], [390, 844]]) {
    await page.setViewportSize({ width, height });
    const geometry = await page.evaluate(() => {
      const rect = element => { const r = element.getBoundingClientRect(); return { left:r.left, top:r.top, right:r.right, bottom:r.bottom, width:r.width, height:r.height }; };
      const dialog = document.querySelector('#ed-shortcuts-guide');
      const content = dialog.querySelector('.ed-shortcuts-content');
      const header = document.querySelector('.ed-appbar');
      const mid = header.querySelector('.ed-appbar-mid');
      const trigger = mid.querySelector('.ed-shortcuts-trigger');
      const rows = [...dialog.querySelectorAll('.ed-shortcuts-row')].map(row => ({ dt:rect(row.querySelector('dt')), dd:rect(row.querySelector('dd')) }));
      return { dialog:rect(dialog), content:rect(content), mid:rect(mid), trigger:rect(trigger), rows,
        screen:{ width:innerWidth, height:innerHeight, scrollWidth:document.documentElement.scrollWidth },
        contentScrollWidth:content.scrollWidth, contentClientWidth:content.clientWidth };
    });
    report.push({ width, height, geometry });
    await page.screenshot({ path: `${out}/guide-${width}x${height}.png` });
    assert.equal(geometry.screen.scrollWidth, width, `page horizontal scroll at ${width}x${height}`);
    assert.ok(geometry.dialog.left >= 0 && geometry.dialog.right <= width && geometry.dialog.top >= 0 && geometry.dialog.bottom <= height,
      `dialog clipped at ${width}x${height}: ${JSON.stringify(geometry.dialog)}`);
    assert.ok(geometry.contentScrollWidth <= geometry.contentClientWidth + 1, `guide horizontal scroll at ${width}x${height}`);
    assert.ok(geometry.rows.every(row => row.dt.right <= row.dd.left + 1), `guide keys overlap descriptions at ${width}x${height}`);
    assert.ok(geometry.trigger.left >= geometry.mid.left && geometry.trigger.right <= geometry.mid.right + 1,
      `shortcut icon spills header at ${width}x${height}`);
  }

  await page.keyboard.press('Escape');
  await dialog.waitFor({ state: 'hidden' });
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('aria-label')), 'Keyboard shortcuts');
  assert.equal(await keys.getAttribute('aria-pressed'), 'false', 'Escape from guide should keep playing mode');
  await trigger.click();
  await dialog.getByRole('button', { name: 'Close keyboard shortcuts' }).click();
  await dialog.waitFor({ state: 'hidden' });
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('aria-label')), 'Keyboard shortcuts');
  await writeFile(`${out}/report.json`, JSON.stringify({ browser:name, report, errors }, null, 2));
  assert.deepEqual(errors, []);
  console.log(`Keyboard shortcuts guide passed in ${name} at ${report.map(({width,height}) => `${width}x${height}`).join(', ')}`);
} finally {
  await browser.close();
  server.close();
}
