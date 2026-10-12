// Bounded real AudioWorklet metadata and in-place resource UI checks.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8797);
const { browser } = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const report = { checks: {}, metadata: null, errors: [] };
const check = (name, ok) => { report.checks[name] = !!ok; if (!ok) throw Error(name); };
page.on('pageerror', e => report.errors.push(e.message));
try {
 await page.goto(url);
 await page.click('[data-layout="workbench"]');
 await page.waitForFunction(() => window.fm1?.editor);
 check('off is unavailable', await page.locator('.ed-cpu-text').textContent() === '–');
 await page.click('#power-on');
 await page.waitForFunction(() => window.fm1.editor.state.cpu?.windowMs >= 1000 && window.fm1.editor.state.ram, null, { timeout: 20000 });
 report.metadata = await page.evaluate(() => window.fm1.editor.state.cpu);
 check('actual timing metadata', ['performance', 'date-now', 'unavailable'].includes(report.metadata.timingSource));
 check('actual load availability', report.metadata.timingSource === 'unavailable' ? report.metadata.loadPercent === null : Number.isFinite(report.metadata.loadPercent) && report.metadata.loadPercent >= 0);
 check('native RAM segment order', await page.locator('.ed-ram-bar').evaluate(e => [...e.children].map(x=>x.className.match(/ed-part-rest|ed-part-master|ed-s[1-4]/)?.[0]).filter(Boolean).every((c,i,a)=> i===0 || ['ed-part-rest','ed-part-master','ed-s1','ed-s2','ed-s3','ed-s4'].indexOf(c)>['ed-part-rest','ed-part-master','ed-s1','ed-s2','ed-s3','ed-s4'].indexOf(a[i-1]))));
 await page.locator('.ed-ram').click();
 check('RAM list order', (await page.locator('.ed-ram-list .ed-ram-name').allTextContents()).map(x=>x.split(' ')[0]).join(',') === 'Shared,Master,S1,S2,S3,S4,Free');
 await page.locator('.ed-ram').click();
 await page.locator('.ed-cpu').click();
 check('Memory RAM order', (await page.locator('.ed-mem-row .ed-mem-tag').allTextContents()).join(',') === 'Shared,Master,S1,S2,S3,S4,All,Free');
 await page.evaluate(() => { window.resourceRow = document.querySelector('.ed-mem-row'); window.cpuMeter = document.querySelector('.ed-cpu'); });
 await page.waitForTimeout(1250);
 check('stats preserve view and meter nodes', await page.evaluate(() => window.resourceRow === document.querySelector('.ed-mem-row') && window.cpuMeter === document.querySelector('.ed-cpu')));
 check('explicit browser/device distinction', /Browser DSP estimate; FM-1 CPU usage is unmeasured/.test(await page.locator('.ed-cpu-detail').textContent()));
 for (const width of [1440,1024,844,667]) {
  await page.setViewportSize({ width, height: 390 });
  await page.waitForTimeout(100);
  check(`no horizontal overflow ${width}`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await page.screenshot({ path: join(out, `${width}-resources.png`), fullPage: true });
 }
 await page.evaluate(() => window.fm1.editor.state.port.onmessage({ data: { type: 'stats', loadPercent: 150, busyMs:1500, windowMs:1000, timingSource:'date-now' } }));
 check('over-budget details', /50.0 % over budget/.test(await page.locator('.ed-cpu-detail').textContent()) && await page.locator('.ed-cpu.is-over').count() === 1);
 await page.evaluate(() => window.fm1.editor.state.port.onmessage({ data: { type: 'stats', loadPercent:null, windowMs:1000, timingSource:'unavailable' } }));
 check('unavailable is not zero', await page.locator('.ed-cpu-text').textContent() === '–');
 await page.evaluate(() => document.querySelector('#power-off').click());
 await page.waitForFunction(() => !window.fm1.editor.state.node);
 check('power off clears stale usage', await page.locator('.ed-cpu-text').textContent() === '–' && await page.locator('.ed-cpu').getAttribute('title').then(x=>x.includes('Audio is off')));
 check('no page errors', report.errors.length === 0);
 console.log('PASS browser DSP resource meter and native RAM display order');
} finally { writeFileSync(join(out,'result.json'),JSON.stringify(report,null,2)); await browser.close(); server.close(); }
