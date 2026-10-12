// Focused semantic regressions for the editor's layout probe. Run with
// `node sim/web/test/layout-probe-ui.mjs` in the configured Playwright env.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { launch } from './launch.mjs';

test('layout probe ignores non-rendered disclosure and SR-only content while checking popover internals', async () => {
  const { browser } = await launch();
  try {
    const page = await browser.newPage({ viewport: { width: 640, height: 360 } });
    await page.setContent(`<!doctype html><style>
      body { margin: 0; } .ed { position: relative; width: 640px; height: 360px; }
      .visually-hidden { position: absolute; left: 30px; top: 40px; }
      details:not([open]) > .closed-content { display: block; position: absolute; left: 30px; top: 40px; }
      .ed-footer-menu-body { position: absolute; left: 180px; top: 80px; width: 200px; height: 100px; }
      .popup-a, .popup-b { position: absolute; left: 12px; top: 12px; }
      .popup-b { left: 16px; top: 14px; }
      .page-under-popup { position: absolute; left: 192px; top: 92px; }
    </style><main class="ed">
      <details><summary>Disclosure</summary><span class="closed-content">closed-detail-leak</span></details>
      <span class="visually-hidden">visually-hidden-leak</span>
      <span class="page-under-popup">page-background</span>
      <div class="ed-footer-menu-body"><div><span class="popup-a">inside-popup-a</span></div><div><span class="popup-b">inside-popup-b</span></div></div>
    </main>`);
    await page.addScriptTag({ path: fileURLToPath(new URL('./layout-probe.js', import.meta.url)) });
    const out = await page.evaluate(() => ({
      faults: window.lunarLayoutProbe('.ed'),
      disclosureRects: document.querySelector('.closed-content').getClientRects().length
    }));
    assert.ok(out.disclosureRects > 0, 'fixture should retain a box for the closed-details child where the browser exposes one');
    assert.ok(out.faults.some((x) => x.includes('inside-popup-a') && x.includes('inside-popup-b')), `overlap inside open popover must remain visible to probe: ${out.faults}`);
    assert.ok(!out.faults.some((x) => x.includes('closed-detail-leak')), `closed details content must be excluded: ${out.faults}`);
    assert.ok(!out.faults.some((x) => x.includes('visually-hidden-leak')), `visually-hidden content must be excluded: ${out.faults}`);
    assert.ok(!out.faults.some((x) => x.includes('page-background')), `popover/background overlap is intentional: ${out.faults}`);
  } finally {
    await browser.close();
  }
});

test('layout probe bounds effective ellipsis without hiding ancestor or vertical clipping', async () => {
  const { browser } = await launch();
  try {
    const page = await browser.newPage({ viewport: { width: 640, height: 360 } });
    await page.setContent(`<!doctype html><style>
      body { margin:0; } .ed { width:640px; }
      .row { position:relative; width:90px; height:36px; overflow:hidden; }
      .label { display:block; width:80px; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
      .wide { width:180px; } .vertical { height:4px; }
      .ineffective { overflow:visible; }
      .neighbor { position:absolute; left:95px; top:0; }
      .allowed { overflow:visible; }
    </style><main class="ed">
      <div class="row allowed"><div><span class="label">intentional-long-title-label</span></div><div class="neighbor">neighbor</div></div>
      <div class="row"><span class="label wide">oversized-ellipsis-element</span></div>
      <div class="row"><span class="label vertical">vertical-ellipsis-clipping</span></div>
      <div class="row"><span class="label ineffective">ineffective-ellipsis-clipping</span></div>
    </main>`);
    await page.addScriptTag({ path: fileURLToPath(new URL('./layout-probe.js', import.meta.url)) });
    const faults = await page.evaluate(() => window.lunarLayoutProbe('.ed'));
    assert.ok(!faults.some(x => x.includes('intentional-long-title-label')), `effective ellipsis is intentional: ${faults}`);
    for (const text of ['oversized-ellipsis-element', 'vertical-ellipsis-clipping', 'ineffective-ellipsis-clipping']) {
      assert.ok(faults.some(x => x.includes(text.slice(0, 28)) && x.includes('clipped')), `must retain ${text}: ${faults}`);
    }
  } finally { await browser.close(); }
});
