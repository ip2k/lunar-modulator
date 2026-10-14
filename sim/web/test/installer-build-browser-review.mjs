// SPDX-License-Identifier: MIT
// Browser integration check for the injected same-origin diagnostic client.
// Run in the pinned Playwright image with a static site and writable output dir.
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
  throw new Error('Expected static site, output directory and pinned image digest.');
}
await mkdir(artifactRoot, { recursive: true });
const catalogue = JSON.parse(await readFile(path.join(siteRoot, 'demo-image-catalogue.json'), 'utf8'));
const eventHorizon = catalogue.projects.find((project) => project.category === 'replacement-showcase-candidate'
  && /event horizon/i.test(project.title));
const anotherProject = catalogue.projects.find((project) => project.category === 'replacement-showcase-candidate'
  && /afterglow relay/i.test(project.title));
if (!eventHorizon || !anotherProject) throw new Error('Expected Event Horizon and Afterglow Relay catalogue entries.');

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
  if (pathname === '/installer-review.html') {
    const html = (await readFile(path.join(siteRoot, 'installer.html'), 'utf8'))
      .replace('<meta name="lunar-installer-build-service" content="disabled">',
        '<meta name="lunar-installer-build-service" content="enabled">')
      .replace('<script type="module" src="installer-page.js"></script>', '');
    response.writeHead(200, { 'content-type': mime.get('.html') }).end(html);
    return;
  }
  if (pathname === '/installer-page.js') {
    const source = await readFile(path.join(siteRoot, 'installer-page.js'), 'utf8');
    if (!new URL(request.url, "http://localhost").searchParams.has("manual-review")) { response.writeHead(200, { "content-type": mime.get(".js") }).end(source); return; }
    const bootstrap = /\nif \(typeof document !== 'undefined'\) \{\n  const root = document\.getElementById\('installer-selection'\);\n  if \(root\) void mountInstallerPage\(root\);\n\}\s*$/;
    if (!bootstrap.test(source)) { response.writeHead(500).end('Expected installer bootstrap was not found'); return; }
    response.writeHead(200, { 'content-type': mime.get('.js') }).end(source.replace(bootstrap, '\n'));
    return;
  }
  const filename = path.resolve(siteRoot, '.' + pathname);
  if (!filename.startsWith(siteRoot + path.sep)) { response.writeHead(403).end(); return; }
  try {
    const metadata = await stat(filename);
    if (!metadata.isFile()) throw new Error('not a file');
    response.writeHead(200, { 'content-type': mime.get(path.extname(filename)) || 'application/octet-stream' });
    createReadStream(filename).pipe(response);
  } catch { response.writeHead(404).end('Not found'); }
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch();
const errors = [];
const report = {
  browser: `Chromium ${browser.version()} / Playwright 1.63.0`,
  image_digest: imageDigest,
  origin: 'loopback inside isolated container',
  errors,
  scenarios: [],
  screenshots: [],
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

async function mountClient(page) {
  await page.goto(origin + '/installer-review.html', { waitUntil: 'networkidle' });
  await page.evaluate(async () => {
    const { mountInstallerPage } = await import('./installer-page.js?manual-review=1');
    await mountInstallerPage(document.getElementById('installer-selection'));
  }).catch((error) => { throw new Error(`${error.message}; browser errors: ${errors.join(' | ')}`); });
  await page.getByRole('heading', { name: 'Choose demo projects' }).waitFor();
  await page.evaluate(() => document.fonts.ready);
}

async function selectBuild(page) {
  const proposedFullSong = page.locator(`input[type=checkbox][value="${eventHorizon.id}"]`);
  if (!await proposedFullSong.isChecked()) throw new Error('Expected the proposed Event Horizon selection to start checked.');
  await proposedFullSong.uncheck();
  await page.locator('input[type=checkbox][value="plate"]').uncheck();
  await page.locator(`input[type=checkbox][value="${anotherProject.id}"]`).check();
  await proposedFullSong.check();
  await page.locator(`input[type=radio][value="${eventHorizon.id}"]`).check();
}

try {
  report.inputs = await hashTree(siteRoot);
  const offlinePage = await browser.newPage({ viewport: { width: 375, height: 812 } });
  let offlineApiCalls = 0;
  await offlinePage.route('**/api/v1/builds**', async (route) => {
    offlineApiCalls += 1;
    await route.abort();
  });
  const offlineErrors = [];
  offlinePage.on('pageerror', (error) => offlineErrors.push(error.message));
  offlinePage.on('console', (message) => { if (message.type() === 'error') offlineErrors.push(message.text()); });
  offlinePage.on('response', (response) => offlineErrors.push('response ' + response.status() + ' ' + response.url()));
  offlinePage.on('requestfailed', (request) => offlineErrors.push('failed ' + request.url()));
  await offlinePage.goto(origin + '/installer.html', { waitUntil: 'networkidle' });
  const offlineButton = offlinePage.getByRole('button', { name: 'Download build request (JSON)' });
  try { await offlineButton.waitFor({ timeout: 5000 }); } catch (error) {
    throw new Error('Default page did not mount: ' + await offlinePage.locator('#installer-load-status').textContent() + '; ' + offlineErrors.join(' | '));
  }
  const [offlineDownload] = await Promise.all([
    offlinePage.waitForEvent('download'),
    offlineButton.click(),
  ]);
  const offlineBytes = await readFile(await offlineDownload.path());
  const offlineRequest = JSON.parse(offlineBytes.toString('utf8'));
  const offlineStatus = await offlinePage.locator('#installer-export-status').textContent();
  if (offlineApiCalls !== 0 || offlineRequest.project_ids[0] !== eventHorizon.id
      || offlineRequest.startup_index !== 0
      || !offlineStatus.includes('No build or install was performed')) {
    throw new Error('The default disabled marker did not preserve offline request export.');
  }
  report.scenarios.push({ name: 'default-static-page-offline-export', api_calls: offlineApiCalls,
    download_name: offlineDownload.suggestedFilename(), default_project: offlineRequest.project_ids[0] });
  await offlinePage.close();

  const successfulRequests = [];
  for (const viewport of [
    { name: 'desktop', width: 1440, height: 1000 },
    { name: 'mobile', width: 375, height: 812 },
  ]) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
    page.on('pageerror', (error) => errors.push(`${viewport.name}: pageerror ${error.message}`));
    page.on('console', (message) => { if (message.type() === 'error') errors.push(`${viewport.name}: console ${message.text()}`); });
    page.on('requestfailed', (request) => errors.push(`${viewport.name}: requestfailed ${request.url()} ${request.failure()?.errorText}`));
    page.on('response', (response) => { if (response.status() >= 400) errors.push(`${viewport.name}: HTTP ${response.status()} ${response.url()}`); });
    let poll = 0;
    await page.route('**/api/v1/builds**', async (route) => {
      const request = route.request();
      if (request.method() === 'POST') {
        successfulRequests.push(JSON.parse(request.postData()));
        await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({
          id: 'A'.repeat(32), status: 'queued', status_url: `/api/v1/builds/${'A'.repeat(32)}`,
        }) });
      } else {
        poll += 1;
        const body = poll === 1 ? { id: 'A'.repeat(32), status: 'queued', kind: 'private-diagnostic-build' }
          : poll === 2 ? { id: 'A'.repeat(32), status: 'running', kind: 'private-diagnostic-build' }
            : { id: 'A'.repeat(32), status: 'succeeded', kind: 'private-diagnostic-build', result: {
              status: 'linked-private-diagnostic', artifact_sha256: 'c'.repeat(64), artifact_bytes: 785312,
              app_budget_bytes: 868836, remaining_bytes: 83524,
              installable: false, hardware_tested: false,
            } };
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
      }
    });
    await mountClient(page);
    await selectBuild(page);
    const button = page.getByRole('button', { name: 'Request diagnostic build' });
    if (successfulRequests.length !== (viewport.name === 'desktop' ? 0 : 1)) {
      throw new Error(`${viewport.name}: a build was submitted before explicit action`);
    }
    await button.click();
    await page.getByText(/No installable firmware file is available/).waitFor();
    const state = await page.evaluate(() => ({
      pageWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
      fullSongPending: document.body.innerText.includes('Full-song default status: pending'),
      status: document.getElementById('installer-export-status').textContent,
      overflow: document.documentElement.scrollWidth > window.innerWidth,
    }));
    if (state.overflow || !state.fullSongPending) throw new Error(`${viewport.name}: clipping or pending status check failed`);
    await page.screenshot({ path: path.join(artifactRoot, `installer-${viewport.name}.png`), fullPage: true });
    report.screenshots.push({ name: viewport.name, ...viewport, ...state });
    report.scenarios.push({ name: `${viewport.name}-success`, polls: poll, request: successfulRequests.at(-1) });
    await page.close();
  }

  if (successfulRequests.length !== 2
      || successfulRequests.some((item) => item.project_ids.join(',') !== `${anotherProject.id},${eventHorizon.id}`
        || item.startup_index !== 1 || item.effects.includes('plate'))) {
    throw new Error('The browser request did not preserve chosen module/project order and startup index.');
  }

  const cancelPage = await browser.newPage({ viewport: { width: 375, height: 812 } });
  let cancelPolls = 0;
  await cancelPage.route('**/api/v1/builds**', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({
        id: 'D'.repeat(32), status: 'queued', status_url: `/api/v1/builds/${'D'.repeat(32)}`,
      }) });
    } else {
      cancelPolls += 1;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        id: 'D'.repeat(32), status: 'queued', kind: 'private-diagnostic-build',
      }) });
    }
  });
  await mountClient(cancelPage);
  await selectBuild(cancelPage);
  await cancelPage.getByRole('button', { name: 'Request diagnostic build' }).click();
  await cancelPage.getByRole('button', { name: 'Stop waiting' }).waitFor();
  await cancelPage.getByRole('button', { name: 'Stop waiting' }).click();
  await cancelPage.getByText(/Stopped waiting for this build/).waitFor();
  await new Promise((resolve) => setTimeout(resolve, 250));
  const pollsAfterCancel = cancelPolls;
  await cancelPage.close();
  if (pollsAfterCancel > 1) throw new Error('Client continued polling after browser cancellation.');
  report.scenarios.push({ name: 'cancel-wait', pollsBeforeStop: pollsAfterCancel, serverJobCancellation: false });

  const rejectPage = await browser.newPage({ viewport: { width: 375, height: 812 } });
  await rejectPage.route('**/api/v1/builds**', async (route) => route.fulfill({
    status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'invalid build request' }),
  }));
  await mountClient(rejectPage);
  await selectBuild(rejectPage);
  await rejectPage.getByRole('button', { name: 'Request diagnostic build' }).click();
  await rejectPage.locator('#installer-export-status').getByText(/build request was rejected/i).waitFor();
  report.scenarios.push({ name: 'request-rejected' });
  await rejectPage.close();

  if (errors.length) throw new Error(errors.join('\n'));
  report.checks = {
    explicit_action_required: true,
    selected_project_order: successfulRequests[0].project_ids,
    startup_index: successfulRequests[0].startup_index,
    omitted_effect: 'plate',
    result_non_installable: true,
    no_artifact_download: true,
    no_server_cancel_endpoint: true,
    errors,
  };
  const output = JSON.stringify(report, null, 2) + '\n';
  await writeFile(path.join(artifactRoot, 'installer-build-browser-report.json'), output);
  const digest = createHash('sha256').update(output).digest('hex');
  await writeFile(path.join(artifactRoot, 'installer-build-browser-report.sha256'), `${digest}  installer-build-browser-report.json\n`);
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
