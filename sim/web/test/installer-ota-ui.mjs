// SPDX-License-Identifier: GPL-3.0-only
// Real-browser check of the installer's install and roll-back panel. No hardware:
// navigator.requestMIDIAccess is mocked, and the flow itself runs against the
// scripted fake FM-1 of fake-midi.mjs. Usage: node installer-ota-ui.mjs [www] [out]
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';

const [www = 'sim/web/www', out = 'scratch/installer-ota-ui'] = process.argv.slice(2);
await mkdir(out, { recursive: true });
const { server, url } = await serve(www, 18931, { prefix: '/lunar-modulator/' });
const { browser, name } = await launch();
const report = { browser: name, checks: [], errors: [] };
const fakeMidi = (await readFile(new URL('./fake-midi.mjs', import.meta.url), 'utf8'))
  .replace("'../www/", "'/lunar-modulator/");
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
page.setDefaultTimeout(15000);
await page.route('**/__fake-midi.mjs', (route) => route.fulfill({ contentType: 'text/javascript', body: fakeMidi }));
page.on('pageerror', (error) => report.errors.push(error.message));
// Count permission requests: the production page must never make one here.
await page.addInitScript(() => {
  window.__midiRequests = 0;
  Object.defineProperty(navigator, 'requestMIDIAccess', { configurable: true,
    value: async () => { window.__midiRequests += 1; throw new Error('mocked: no MIDI in this test'); } });
});
async function check(label, fn) { await fn(); report.checks.push(label); console.log(`PASS ${label}`); }

try {
  await page.goto(`${url}installer.html`);
  await check('panel, licence note and source links render without the catalogue', async () => {
    await page.locator('#installer-ota-start').waitFor();
    assert.equal(await page.locator('#installer-ota-start').isDisabled(), true);
    const licence = page.locator('.installer-licence');
    assert.match(await licence.innerText(), /GPL-3\.0-only/);
    for (const href of ['third_party/fm1-ota/fm1ota.js', 'licences/GPL-3.0.txt', 'https://github.com/hugelton/Felucca']) {
      assert.equal(await licence.locator(`a[href="${href}"]`).count(), 1, href);
    }
    for (const href of ['third_party/fm1-ota/fm1ota.js', 'licences/GPL-3.0.txt']) {
      const response = await page.request.get(new URL(href, `${url}installer.html`).href);
      assert.equal(response.status(), 200, href);
    }
    assert.equal(await page.locator('#installer-ota-flow .installer-ota-stages li').count(), 14);
  });
  await check('an unadmitted package is refused and no MIDI permission is requested', async () => {
    await page.locator('input[type=file]').first().setInputFiles({ name: 'x.fwsc', mimeType: 'application/octet-stream',
      buffer: Buffer.from([1, 2, 3, 4]) });
    await page.waitForFunction(() => /Not admitted/.test(document.getElementById('installer-ota-admission').textContent));
    assert.equal(await page.locator('#installer-ota-start').isDisabled(), true);
    assert.equal(await page.evaluate(() => window.__midiRequests), 0);
  });
  await check('no horizontal scroll at phone width, with the panel visible', async () => {
    await page.setViewportSize({ width: 375, height: 812 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const wide = overflow <= 0 ? [] : await page.evaluate(() => [...document.querySelectorAll('body *')]
      .filter((node) => node.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
      .slice(0, 6).map((node) => `${node.tagName}.${node.className}#${node.id}`));
    assert.ok(overflow <= 0, `horizontal overflow ${overflow}px: ${wide.join(' ')}`);
    await page.locator('.installer-ota-flow').screenshot({ path: `${out}/installer-ota-mobile.png` });
    await page.setViewportSize({ width: 1280, height: 1000 });
  });

  // The full flow in a real DOM, against fake ports and an injected verifier.
  await page.evaluate(async () => {
    const fake = await import('/lunar-modulator/__fake-midi.mjs');
    const host = document.createElement('div');
    host.id = 'flow-under-test';
    document.body.append(host);
    const { mountOtaInstallFlow } = await import('/lunar-modulator/installer-ota-flow.js');
    const access = new fake.FakeAccess();
    const pairs = { running: access.addPair('running', 'FM-1_015') };
    window.__t = { access, pairs, fake, requests: 0 };
    window.__flow = mountOtaInstallFlow(host, {
      requestMIDIAccess: async () => { window.__t.requests += 1; return access; },
      packageAdmission: { async verify(bytes) {
        const logicalImage = Uint8Array.of(1, 2, 3, 4);
        const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', logicalImage));
        return { format: 'lunar-native-package-admission-v1', product: 'FM-1_501', model: 'FM-1', version: 501,
          logicalImage, logicalImageSha256: [...digest].map((b) => b.toString(16).padStart(2, '0')).join('') };
      } },
      clock: { now: () => performance.now(), setTimeout: (fn, ms) => setTimeout(fn, ms === 30000 ? 2 : ms),
        clearTimeout: (id) => clearTimeout(id), sleep: () => Promise.resolve() },
      transferTimeouts: { idleTimeoutMs: 300, hardTimeoutMs: 3000, responseDelayMs: 0 },
    });
    await window.__flow.receivePackage({ file: { name: 'fake.fwsc' }, bytes: Uint8Array.of(9, 8, 7) });
  });
  const flow = page.locator('#flow-under-test');
  const choose = async (phase, label, add) => {
    await flow.locator('legend', { hasText: label }).waitFor();
    if (add) {
      await page.evaluate(({ phase, add }) => {
        const t = window.__t;
        t.pairs[phase] = t.access.addPair(phase, add);
        for (const listener of [...t.access.listeners]) listener({ port: t.pairs[phase].input });
      }, { phase, add });
    }
    await flow.locator(`input[type=radio][data-input-id="${phase}-in"]`).check();
    await flow.getByRole('button', { name: 'Use this pair' }).click();
  };
  await check('admitted package: install button is the only way in; stages complete one by one', async () => {
    assert.match(await flow.locator('#installer-ota-admission').innerText(), /Admitted: FM-1_501/);
    assert.equal(await page.evaluate(() => window.__t.requests), 0);
    await flow.getByRole('button', { name: 'Install', exact: true }).click();
    await choose('running', 'running FM-1');
    await choose('loader', 'OTA loader', 'ota-FM-1_015');
    await choose('application', 'new application', 'FM-1_501');
    await flow.locator('#installer-ota-result', { hasText: 'Done: the unit reports FM-1_501' }).waitFor();
    const states = await flow.locator('li[data-stage]').evaluateAll((items) => items.map((li) => li.dataset.state));
    assert.equal(states.length, 14);
    assert.ok(states.every((state) => state === 'done'), states.join(','));
    await flow.screenshot({ path: `${out}/installer-ota-done.png` });
  });
  await check('cancelling at port selection stops cleanly with guidance', async () => {
    await page.evaluate(() => {
      const t = window.__t;
      t.access.sent.length = 0;
      t.pairs.running.input.state = 'connected'; t.pairs.running.output.state = 'connected';
      t.access.inputs.set(t.pairs.running.input.id, t.pairs.running.input);
      t.access.outputs.set(t.pairs.running.output.id, t.pairs.running.output);
      for (const key of ['loader', 'application']) {
        t.access.inputs.delete(`${key}-in`); t.access.outputs.delete(`${key}-out`);
      }
    });
    await flow.getByRole('button', { name: 'Install', exact: true }).click();
    await flow.locator('legend').waitFor();
    await flow.getByRole('button', { name: 'Cancel' }).click();
    await flow.locator('#installer-ota-result', { hasText: 'port selection cancelled' }).waitFor();
    assert.match(await flow.locator('#installer-ota-guidance').innerText(), /Stopped before anything was sent/);
    assert.equal(await page.evaluate(() => window.__t.access.sent.length), 0);
  });
  assert.deepEqual(report.errors, []);
  await writeFile(`${out}/installer-ota-ui-report.json`, JSON.stringify(report, null, 2));
  console.log(`${report.checks.length} checks passed in ${name}`);
} catch (error) {
  await page.screenshot({ path: `${out}/installer-ota-failure.png`, fullPage: true }).catch(() => {});
  console.error(error);
  process.exitCode = 1;
} finally {
  await browser.close();
  server.close();
}
