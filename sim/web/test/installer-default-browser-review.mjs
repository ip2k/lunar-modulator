// SPDX-License-Identifier: MIT
// Render the private installer chooser and verify its proposed default in Chromium.
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
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
const candidate = catalogue.projects.find((project) => project.id === 'replacement-showcase-candidate-event-horizon');
const secondProject = catalogue.projects.find((project) => project.id === 'replacement-showcase-candidate-packet-bloom');
if (!candidate || !secondProject) throw new Error('Expected Event Horizon and Packet Bloom candidates.');

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
      .replace('<script type="module" src="installer-page.js"></script>', '');
    response.writeHead(200, { 'content-type': mime.get('.html') }).end(html);
    return;
  }
  if (pathname === '/installer-page.js') {
    const source = await readFile(path.join(siteRoot, 'installer-page.js'), 'utf8');
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
const report = { browser: `Chromium ${browser.version()} / Playwright 1.63.0`, image_digest: imageDigest,
  origin: 'loopback inside isolated container', errors, screenshots: [], scenarios: [] };

async function mount(page) {
  await page.goto(origin + '/installer-review.html', { waitUntil: 'networkidle' });
  await page.evaluate(async () => {
    const { mountInstallerPage } = await import('./installer-page.js');
    await mountInstallerPage(document.getElementById('installer-selection'));
  });
  await page.getByRole('heading', { name: 'Choose demo projects' }).waitFor();
  await page.evaluate(() => document.fonts.ready);
}

try {
  for (const viewport of [
    { name: 'desktop', width: 1440, height: 1000 },
    { name: 'mobile', width: 375, height: 812 },
  ]) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
    page.on('pageerror', (error) => errors.push(`${viewport.name}: ${error.message}`));
    page.on('console', (message) => { if (message.type() === 'error') errors.push(`${viewport.name}: ${message.text()}`); });
    page.on('response', (response) => { if (response.status() >= 400) errors.push(`${viewport.name}: HTTP ${response.status()} ${response.url()}`); });
    await mount(page);
    const proposed = page.locator(`input[type=checkbox][value="${candidate.id}"]`);
    const startup = page.locator(`input[type=radio][value="${candidate.id}"]`);
    if (!await proposed.isChecked() || !await startup.isChecked()) throw new Error(`${viewport.name}: proposed full-song default not selected`);
    const status = await page.locator('.native-demo-default-status').innerText();
    if (!status.includes('status: pending') || !status.includes('not owner musical acceptance or release admission')
        || !status.includes('108.8-second host render') || !status.includes('packed dependency validation')) {
      throw new Error(`${viewport.name}: pending proposal evidence is inaccurate`);
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    if (overflow) throw new Error(`${viewport.name}: page overflows viewport width`);
    await page.screenshot({ path: path.join(artifactRoot, `installer-${viewport.name}.png`), fullPage: true });
    report.screenshots.push({ ...viewport, horizontal_overflow: overflow });

    if (viewport.name === 'desktop') {
      await page.locator(`input[type=checkbox][value="${secondProject.id}"]`).check();
      await page.locator(`input[type=radio][value="${secondProject.id}"]`).check();
      const downloadPromise = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Download build request (JSON)' }).click();
      const download = await downloadPromise;
      const artifact = await download.createReadStream();
      const chunks = [];
      for await (const chunk of artifact) chunks.push(chunk);
      const payload = Buffer.concat(chunks).toString('utf8');
      const request = JSON.parse(payload);
      if (request.project_ids.join(',') !== `${candidate.id},${secondProject.id}` || request.startup_index !== 1) {
        throw new Error('Downloaded request did not preserve preselected project order and changed startup choice.');
      }
      if (request.installable !== undefined || request.full_song_default_accepted !== undefined) {
        throw new Error('Selection request must not imply release admission.');
      }
      await writeFile(path.join(artifactRoot, 'installer-request.json'), payload);
      report.scenarios.push({ name: 'reversible-proposal-and-download', project_ids: request.project_ids,
        startup_index: request.startup_index, no_acceptance_flags: true, status: await page.locator('#installer-export-status').innerText() });
    }
    await page.close();
  }
  if (errors.length) throw new Error(errors.join('\n'));
  report.admission_flags = { candidate_default: candidate.default_candidate, full_song_default: catalogue.full_song_default.status,
    catalogue_installable: catalogue.installable };
  if (candidate.default_candidate !== false || catalogue.full_song_default.status !== 'pending' || catalogue.installable !== false) {
    throw new Error('Catalogue admission state changed unexpectedly.');
  }
  const output = JSON.stringify(report, null, 2) + '\n';
  await writeFile(path.join(artifactRoot, 'installer-default-browser-report.json'), output);
  const digest = createHash('sha256').update(output).digest('hex');
  await writeFile(path.join(artifactRoot, 'installer-default-browser-report.sha256'), `${digest}  installer-default-browser-report.json\n`);
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
