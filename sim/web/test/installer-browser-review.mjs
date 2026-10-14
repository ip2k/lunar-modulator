// SPDX-License-Identifier: MIT
// Read-only browser review helper. Run in the pinned Playwright container:
// node installer-browser-review.mjs <static-site-dir> <artifact-dir> <image-digest>
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire('/pw/');
const { chromium } = require('playwright');
const siteRoot = path.resolve(process.argv[2] || '');
const artifactRoot = path.resolve(process.argv[3] || '');
const imageDigest = process.argv[4] || '';
if (!process.argv[2] || !process.argv[3] || !imageDigest.startsWith('sha256:')) {
  throw new Error('Expected static-site dir, artifact dir and pinned sha256 image digest.');
}
await mkdir(artifactRoot, { recursive: true });

const mime = new Map([
  ['.css', 'text/css; charset=utf-8'], ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'], ['.json', 'application/json; charset=utf-8'],
  ['.ttf', 'font/ttf'],
]);
const server = createServer(async (request, response) => {
  let pathname;
  try { pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname); }
  catch { response.writeHead(400).end(); return; }
  if (pathname === '/') pathname = '/installer.html';
  const filename = path.resolve(siteRoot, '.' + pathname);
  if (!filename.startsWith(siteRoot + path.sep)) { response.writeHead(403).end(); return; }
  try {
    const metadata = await stat(filename);
    if (!metadata.isFile()) throw new Error('not a file');
    response.writeHead(200, { 'content-type': mime.get(path.extname(filename)) || 'application/octet-stream' });
    createReadStream(filename).pipe(response);
  } catch {
    response.writeHead(404).end('Not found');
  }
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const address = server.address();
const origin = 'http://127.0.0.1:' + address.port;
const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
const errors = [];
const report = {
  browser: 'Chromium ' + browser.version() + ' / Playwright 1.63.0',
  image_digest: imageDigest,
  origin: 'loopback inside isolated container',
  screenshots: [],
  errors,
};

async function hashTree(root, relative = '') {
  const names = await readdir(path.join(root, relative), { withFileTypes: true });
  const result = [];
  for (const entry of names.sort((a, b) => a.name.localeCompare(b.name))) {
    const name = path.posix.join(relative, entry.name);
    if (entry.isDirectory()) result.push(...await hashTree(root, name));
    else {
      const bytes = await readFile(path.join(root, name));
      result.push({ path: name, sha256: createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length });
    }
  }
  return result;
}

try {
  report.inputs = await hashTree(siteRoot);
  for (const viewport of [
    { name: 'desktop', width: 1440, height: 1000 },
    { name: 'mobile', width: 375, height: 812 },
  ]) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
    page.on('pageerror', (error) => errors.push('pageerror: ' + error.message));
    page.on('console', (message) => { if (message.type() === 'error') errors.push('console: ' + message.text()); });
    page.on('requestfailed', (request) => errors.push('requestfailed: ' + request.url() + ' ' + request.failure()?.errorText));
    const response = await page.goto(origin + '/installer.html', { waitUntil: 'networkidle' });
    if (!response || !response.ok()) throw new Error(viewport.name + ': installer page HTTP failure');
    await page.getByRole('heading', { name: 'Choose demo projects' }).waitFor();
    await page.evaluate(() => document.fonts.ready);
    const secondModuleInstance = await page.evaluate(async () => {
      const catalogue = await (await fetch('./demo-image-catalogue.json')).json();
      const { mountNativeModuleSelectionView } = await import('./native-module-selection-view.js');
      const existing = new Set([...document.querySelectorAll('.native-module-selection input')].map((input) => input.id));
      const root = document.createElement('div');
      document.body.append(root);
      const controller = mountNativeModuleSelectionView(root, catalogue, catalogue.default_profile, () => {});
      const ids = [...root.querySelectorAll('input')].map((input) => input.id);
      const overlaps = ids.some((id) => existing.has(id));
      controller.destroy();
      root.remove();
      return { count: ids.length, allUnique: new Set(ids).size === ids.length, overlaps };
    });
    if (!secondModuleInstance.allUnique || secondModuleInstance.overlaps) throw new Error('Module view instances reuse control IDs');
    const initial = await page.evaluate(() => ({
      viewport: { width: innerWidth, height: innerHeight },
      document: { width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight },
      fontLoaded: document.fonts.check('14px Audiowide') && document.fonts.check('14px "Exo 2"'),
      moduleGroups: [...document.querySelectorAll('.native-module-selection fieldset')].map((fieldset) => ({
        name: fieldset.querySelector('legend')?.textContent,
        checked: fieldset.querySelectorAll('input:checked').length,
        total: fieldset.querySelectorAll('input').length,
      })),
      fullSongStatus: document.querySelector('.native-demo-default-status h3')?.textContent,
      fullSongNotice: document.querySelector('.native-demo-default-status p')?.textContent,
      serviceStatus: document.querySelector('.installer-status')?.innerText,
      cardBounds: [...document.querySelectorAll('.native-demo-selection article')].map((card) => {
        const box = card.getBoundingClientRect();
        return { x: box.x, y: box.y, width: box.width, height: box.height };
      }),
    }));
    if (initial.document.width > initial.viewport.width) throw new Error(viewport.name + ': horizontal overflow');
    if (!initial.fontLoaded) throw new Error(viewport.name + ': local fonts did not load');
    if (initial.moduleGroups.length !== 4 || initial.moduleGroups.some((group) => group.checked === 0)) {
      throw new Error(viewport.name + ': module group defaults are incomplete');
    }
    if (initial.cardBounds.length !== 8) throw new Error(viewport.name + ': expected eight catalogue cards');
    if (initial.fullSongStatus !== 'Full-song default status: owner-approved') throw new Error('Approved full-song status changed');
    if (!/does not build or install firmware/i.test(initial.serviceStatus)) throw new Error('Build/install status claim is missing');
    if (!initial.fullSongNotice.includes('owner-approved musical full-song default') || !initial.fullSongNotice.includes('installability are unverified')) throw new Error('Musical approval or hardware-status disclosure missing');

    const moduleRoot = page.locator('.native-module-selection');
    const effectBox = moduleRoot.locator('fieldset').nth(1).locator('input[type=checkbox]').first();
    const omittedEffect = await effectBox.getAttribute('value');
    await effectBox.uncheck();
    const engineBoxes = moduleRoot.locator('fieldset').first().locator('input[type=checkbox]');
    for (let i = 0; i < await engineBoxes.count() - 1; i++) await engineBoxes.nth(i).uncheck();
    const lastEngine = engineBoxes.last();
    await lastEngine.click(); // Invalid last-engine removal is reverted by the shared validator.
    if (!(await lastEngine.isChecked())) throw new Error(viewport.name + ': invalid empty engine group was not rolled back');
    if (!/needs a sound engine/i.test(await moduleRoot.locator('[role=status]').textContent())) {
      throw new Error(viewport.name + ': rollback status was not announced');
    }
    for (const groupIndex of [0, 2, 3]) {
      const controls = moduleRoot.locator('fieldset').nth(groupIndex).locator('input[type=checkbox]');
      for (let i = 0; i < await controls.count(); i++) {
        if (!(await controls.nth(i).isChecked())) await controls.nth(i).check();
      }
    }

    const checkboxes = page.locator('.native-demo-selection article input[type=checkbox]');
    await checkboxes.nth(5).check(); // Event Horizon Showcase is preselected as the approved default.
    await page.locator('.native-demo-selection fieldset:nth-of-type(2) input[type=radio][value="replacement-showcase-candidate-event-horizon"]').check();
    const companion = page.getByLabel('Event Horizon Companion Set');
    if (!(await companion.isEnabled())) throw new Error(viewport.name + ': companion set did not enable for its startup project');
    await companion.check();
    const requestDownload = page.getByRole('button', { name: 'Download build request (JSON)' });
    if (viewport.name === 'desktop') {
      const downloadWait = page.waitForEvent('download');
      await requestDownload.click();
      const download = await downloadWait;
      await download.saveAs(path.join(artifactRoot, 'installer-request.json'));
      const exported = JSON.parse(await readFile(path.join(artifactRoot, 'installer-request.json'), 'utf8'));
      const keys = ['version', 'engines', 'effects', 'midi', 'modulation', 'project_ids', 'startup_index', 'set_ids'];
      if (JSON.stringify(Object.keys(exported)) !== JSON.stringify(keys)) throw new Error('Download schema keys differ');
      if (JSON.stringify(exported.project_ids) !== JSON.stringify(['replacement-showcase-candidate-event-horizon'])) throw new Error('Downloaded project selection differs');
      if (exported.startup_index !== 0) throw new Error('Downloaded startup index differs');
      if (JSON.stringify(exported.set_ids) !== JSON.stringify(['replacement-showcase-event-horizon-companion-set'])) throw new Error('Downloaded companion SET selection differs');
      for (const [index, group] of ['engines', 'effects', 'midi', 'modulation'].entries()) {
        const selected = await moduleRoot.locator('fieldset').nth(index).locator('input:checked').evaluateAll((inputs) => inputs.map(input => input.value));
        if (JSON.stringify(exported[group]) !== JSON.stringify(selected)) throw new Error('Downloaded ' + group + ' selection differs from controls');
      }
      if (exported.effects.includes(omittedEffect)) throw new Error('Deselected effect remained in request');
      for (const key of ['source_path', 'source_sha256', 'dependency_validation']) {
        if (key in exported) throw new Error('Download leaked trusted metadata: ' + key);
      }
      const status = await page.locator('#installer-export-status').textContent();
      if (!/Request exported\. No build or install was performed/.test(status)) throw new Error('Download status is misleading');
      report.download = {
        keys: Object.keys(exported),
        project_ids: exported.project_ids,
        startup_index: exported.startup_index,
        omitted_effect: omittedEffect,
        engine_count: exported.engines.length,
        effect_count: exported.effects.length,
        sha256: createHash('sha256').update(JSON.stringify(exported, null, 2) + '\n').digest('hex'),
        status,
      };
    } else {
      if (!(await requestDownload.isEnabled())) throw new Error('Selected mobile request button is disabled');
    }

    const selectedOverview = await page.evaluate(() => ({
      selectedCards: [...document.querySelectorAll('.native-demo-selection article input[type=checkbox]:checked')]
        .map((input) => input.value),
      checkedStartup: document.querySelector('.native-demo-selection input[type=radio]:checked')?.value,
      status: document.querySelector('.installer-export-status')?.textContent || '',
      selectedSets: [...document.querySelectorAll('.native-demo-selection input[type=checkbox]:checked')]
        .map((input) => input.value).filter((id) => id.includes('companion-set')),
    }));
    if (JSON.stringify(selectedOverview.selectedCards) !== JSON.stringify(['replacement-showcase-candidate-event-horizon'])) throw new Error(viewport.name + ': selection not rendered correctly');
    if (selectedOverview.checkedStartup !== 'replacement-showcase-candidate-event-horizon') {
      throw new Error(viewport.name + ': selected startup project not rendered');
    }
    if (JSON.stringify(selectedOverview.selectedSets) !== JSON.stringify(['replacement-showcase-event-horizon-companion-set'])) {
      throw new Error(viewport.name + ': selected companion SET not rendered');
    }
    // Keep the saved screenshots in the clean default state after exercising
    // deselection and validator rollback above.
    for (let groupIndex = 0; groupIndex < 4; groupIndex++) {
      const controls = moduleRoot.locator('fieldset').nth(groupIndex).locator('input[type=checkbox]');
      for (let i = 0; i < await controls.count(); i++) {
        if (!(await controls.nth(i).isChecked())) await controls.nth(i).check();
      }
    }
    const screenshot = 'installer-' + viewport.name + '.png';
    await page.screenshot({ path: path.join(artifactRoot, screenshot), fullPage: true });
    report.screenshots.push({ path: screenshot, viewport: initial.viewport, document: initial.document, fontLoaded: initial.fontLoaded });
    report[viewport.name] = initial;
    await page.close();
  }
  if (errors.length) throw new Error('Browser emitted errors: ' + errors.join(' | '));
  await writeFile(path.join(artifactRoot, 'installer-browser-report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
