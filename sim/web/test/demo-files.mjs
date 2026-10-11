// Browser file-path acceptance for the four preloaded demo projects.
// Run in the Playwright container: node demo-files.mjs WWW MANIFEST OUT
// MIT licence.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { basename, dirname, join, resolve } from 'node:path';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { serve } from './serve.mjs';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
const { chromium } = require('playwright');
const [www, manifest, out] = process.argv.slice(2);
assert(www && manifest && out, 'WWW MANIFEST OUT required');
mkdirSync(out, { recursive: true });
const songs = JSON.parse(readFileSync(manifest, 'utf8'));
assert.equal(songs.length, 4);
const { server, url } = await serve(www, 8771);
const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
const report = { browser: browser.version(), songs: [], errors: [], pass: false };
const state = (text) => {
  const { made, name, title, about, author, licence, view, ...doc } = JSON.parse(text);
  return doc;
};
try {
  for (const song of songs) {
    const file = basename(song.file);
    assert.deepEqual(readFileSync(join(www, 'examples', file)),
      readFileSync(resolve(dirname(resolve(manifest)), song.file)),
      'browser mirror equals authoritative project');
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
    const page = await ctx.newPage();
    page.on('pageerror', e => report.errors.push(e.message));
    await page.goto(`${url}?load=examples/${encodeURIComponent(file)}&play=1`);
    await page.click('#power-on');
    await page.waitForFunction(title => window.fm1?.files?.title === title && window.fm1?.seq?.playing,
      song.title, { timeout: 20000 });
    const listed = await page.evaluate(async title => {
      const { EXAMPLES } = await import('./files.js');
      return EXAMPLES.some(x => x.kind === 'project' && x.title === title);
    }, song.title);
    assert(listed, 'song is preloaded in the example library');
    await page.evaluate(() => window.fm1.node.port.postMessage({
      type: 'seq-line', bytes: new TextEncoder().encode('stop'),
    }));
    await page.waitForFunction(() => !window.fm1.seq.playing);
    const first = await page.evaluate(() => window.fm1.files.saveText('project'));
    await page.selectOption('#save-kind', 'project');
    const [download] = await Promise.all([page.waitForEvent('download'), page.click('#save')]);
    const savedPath = join(out, file);
    await download.saveAs(savedPath);
    assert.deepEqual(state(readFileSync(savedPath, 'utf8')), state(first), 'download preserves state');
    await page.screenshot({ path: join(out, `${file}.png`) });
    await page.close();
    // A clean browser context prevents autosave from disguising a failed Open.
    const fresh = await browser.newContext({ acceptDownloads: true });
    const reopened = await fresh.newPage();
    reopened.on('pageerror', e => report.errors.push(e.message));
    await reopened.goto(url);
    await reopened.click('#power-on');
    await reopened.waitForFunction(() => window.fm1?.files?.powered && window.fm1.screens > 0);
    const [chooser] = await Promise.all([reopened.waitForEvent('filechooser'), reopened.click('#open')]);
    await chooser.setFiles(savedPath);
    await reopened.waitForFunction(title => window.fm1.files.title === title, song.title);
    const second = await reopened.evaluate(() => window.fm1.files.saveText('project'));
    assert.deepEqual(state(second), state(first), 'Open in fresh context restores state');
    report.songs.push({ title: song.title, file, listed, playbackStarted: true, download: true, reopened: true });
    await fresh.close();
    await ctx.close();
  }
  assert.deepEqual(report.errors, [], 'no page exceptions');
  report.pass = true;
} finally {
  writeFileSync(join(out, 'demo-files.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
  server.close();
}
