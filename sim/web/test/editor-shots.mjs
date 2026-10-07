// editor-shots.mjs -- the pictures of the Advanced editor for the user manual
// (assets/screenshots/page-editor-*.png, shown by `{{page editor-flow ...}}`):
// the Flow, a sound, the modulation table, the Map with a module in focus, and
// the Memory page, of the "First orbit" example at 1,280 px, each the editor
// alone. Run in the Playwright container on aeon, never on the Mac:
//
//   node editor-shots.mjs WWW_DIR OUT_DIR
//
// then `node assets/web-editor/src/shrink.mjs` on the PNGs (palette form) before
// they are committed. MIT licence, like the rest of this repository.

import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';

const [www, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8773);
const { browser, name } = await launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.log(`pageerror: ${e.message}`));
await page.goto(`${url}?load=examples/first-orbit.lunar`);
await page.waitForTimeout(500);
await page.click('[data-layout="workbench"]');
await page.waitForFunction(() => window.fm1 && window.fm1.editor, null, { timeout: 15000 });
await page.click('#power-on');
await page.waitForFunction(() => window.fm1.editor.state.mirror && window.fm1.editor.state.panelView && window.fm1.editor.state.mirror.blocks.size > 6, null, { timeout: 30000 });
await page.click('[data-layout="editor"]');
await page.waitForTimeout(800);

const shot = async (file, setup) => {
  await page.evaluate(setup);
  await page.waitForTimeout(900);
  await page.locator('.ed').screenshot({ path: join(out, file) });
  console.log(`${name}: ${file}`);
};
await shot('page-editor-flow.png', () => { document.querySelector('.ed-out-fx').click(); });
await shot('page-editor-sound.png', () => { window.fm1.editor.select('s3', { view: 'sound' }); });
await shot('page-editor-table.png', () => { window.fm1.editor.state.modMap = false; document.querySelector('.ed-out-mod').click(); });
await shot('page-editor-map.png', () => {
  const ed = window.fm1.editor;
  ed.state.modMap = true; ed.state.mapMode = 'focus'; ed.state.mapSrc = null;
  ed.select('p3', { view: 'mod' });
});
await shot('page-editor-memory.png', () => { document.querySelector('.ed-out-mem').click(); });
await browser.close();
server.close();
