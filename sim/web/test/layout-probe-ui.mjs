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
