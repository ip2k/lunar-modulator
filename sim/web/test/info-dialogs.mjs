// Information dialogs stay available without crowding the simulator, and
// remain usable with a keyboard and a narrow, short viewport.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const { chromium, firefox, webkit } = require('playwright');
const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const PORT = Number(process.env.INFO_DIALOGS_PORT || 8788);
const { server, url } = await serve(www, PORT);
const report = { checks: {}, failures: [] };

const available = { chromium, firefox, webkit };
const selected = process.env.BROWSER ? { [process.env.BROWSER]: available[process.env.BROWSER] } : available;
for (const [name, type] of Object.entries(selected)) {
  if (!type) throw new Error(`Unsupported BROWSER=${name}`);
  let browser;
  try {
    browser = await type.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
    page.on('pageerror', (error) => report.failures.push(`${name}: ${error.message}`));
    await page.goto(url);
    const closedInitially = await page.locator('#cheat-sheet').evaluate((d) => !d.open) &&
      await page.locator('#copyright-info').evaluate((d) => !d.open);
    const shortPage = await page.evaluate(() => ({
      layoutAtTop: document.querySelector('#layout-switch').getBoundingClientRect().top < 100,
      controlsOutsideDialogs: !document.querySelector('.controls').closest('dialog'),
      bottomTriggersPresent: !!document.querySelector('#open-cheat-sheet') && !!document.querySelector('#open-copyright'),
    }));
    await page.screenshot({ path: join(out, `info-dialogs-${name}-page.png`) });
    await page.evaluate(() => Object.defineProperty(window, 'AudioWorkletNode', { value: undefined, configurable: true }));
    await page.click('#power-on');
    const failureStaysVisible = await page.locator('#status-alert').evaluate((e) =>
      !e.hidden && e.textContent.includes('cannot start the simulator audio'));
    await page.click('#open-cheat-sheet');
    const help = await page.evaluate(() => {
      const d = document.querySelector('#cheat-sheet');
      const c = d.querySelector('.dialog-content');
      const summary = d.querySelector('#library > summary');
      const summaryMinHeight = summary.getBoundingClientRect().height;
      const r = d.getBoundingClientRect();
      return {
        open: d.open,
        focusedClose: document.activeElement.matches('.dialog-close'),
        containsLiveContent: !!d.querySelector('#status') && !!d.querySelector('#library-lists'),
        fullErrorInStatus: d.querySelector('#status').textContent.includes('browser has no AudioWorklet'),
        libraryTargetUsable: summaryMinHeight >= 44,
        scrollable: c.scrollHeight > c.clientHeight && c.clientHeight > 0,
        inViewport: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
      };
    });
    await page.locator('#library > summary').click();
    const libraryOpens = await page.locator('#library').evaluate((details) => details.open);
    await page.locator('#library > summary').click();
    await page.screenshot({ path: join(out, `info-dialogs-${name}-cheat-sheet.png`) });
    await page.keyboard.press('Escape');
    const escRestoredFocus = await page.locator('#cheat-sheet').evaluate((d) => !d.open) &&
      await page.locator('#open-cheat-sheet').evaluate((b) => b === document.activeElement);
    await page.click('#open-copyright');
    const about = await page.evaluate(() => {
      const d = document.querySelector('#copyright-info');
      const text = d.textContent;
      const links = [...d.querySelectorAll('a')].map((a) => a.getAttribute('href'));
      return {
        open: d.open,
        identity: text.includes('Lunar Modulator') && text.includes('INTERGALACTIC MODULATION STATION'),
        intro: text.includes('An open firmware for the M-VAVE FM-1') && text.includes('240'),
        credits: text.includes('Audiowide') && text.includes('SIL Open Font License 1.1'),
        licenceTargets: links.includes('fonts/audiowide/OFL.txt') && links.includes('fonts/spleen/LICENSE'),
        hasRuntimeOffer: !!d.querySelector('#licence-note'),
      };
    });
    await page.screenshot({ path: join(out, `info-dialogs-${name}-copyright.png`) });
    await page.locator('#copyright-info .dialog-close').click();
    const closeRestoredFocus = await page.locator('#open-copyright').evaluate((b) => b === document.activeElement);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.click('#open-cheat-sheet');
    const phone = await page.evaluate(() => {
      const d = document.querySelector('#cheat-sheet');
      const c = d.querySelector('.dialog-content');
      const r = d.getBoundingClientRect();
      c.scrollTop = c.scrollHeight;
      return {
        inViewport: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
        internallyScrolls: c.scrollTop > 0,
        noPageOverflow: document.documentElement.scrollWidth <= innerWidth,
      };
    });
    await page.screenshot({ path: join(out, `info-dialogs-${name}-phone.png`) });
    await page.keyboard.press('Escape');
    const passed = closedInitially && shortPage.layoutAtTop && shortPage.controlsOutsideDialogs &&
      shortPage.bottomTriggersPresent && failureStaysVisible && help.open && help.focusedClose &&
      help.containsLiveContent && help.fullErrorInStatus &&
      help.libraryTargetUsable && libraryOpens && help.scrollable &&
      help.inViewport && escRestoredFocus && about.open && about.identity && about.intro && about.credits &&
      about.licenceTargets && about.hasRuntimeOffer && closeRestoredFocus && phone.inViewport &&
      phone.internallyScrolls && phone.noPageOverflow;
    report.checks[name] = { closedInitially, help, escRestoredFocus, about, closeRestoredFocus, phone, passed };
    await page.close();
  } catch (error) {
    report.failures.push(`${name}: ${error.stack || error}`);
    report.checks[name] = { passed: false };
  } finally {
    if (browser) await browser.close();
  }
}

server.close();
console.log(JSON.stringify(report, null, 2));
if (report.failures.length || Object.values(report.checks).some((check) => !check.passed)) process.exitCode = 1;
