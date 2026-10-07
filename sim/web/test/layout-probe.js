// layout-probe.js -- the editor's layout check, run inside the page by
// test/editor-ui.mjs (Playwright's addScriptTag) and by hand in any browser:
//
//   window.lunarLayoutProbe(root = '.ed')  ->  [string, ...]  (empty: clean)
//
// Reports (notes/2026-10-06-web-editor.md §14, §17; stage ED5a):
//   - the page scrolling sideways;
//   - text, or a control, running outside the page's width;
//   - text clipped by an ancestor that hides its overflow (not by one that
//     scrolls, nor an ellipsis), judged on the text's own line boxes;
//   - two pieces of text, or a control and a piece of text, whose boxes
//     overlap by more than 2 px each way (not inside one another's parent,
//     not a popup or dialog laid over the page on purpose).
// Text in `.ed-sr` (the screen-reader-only class), in a hidden or aria-hidden
// element, or invisible is left out. MIT licence, like the rest of this
// repository.
(function () {
  const POPUP = '.ed-search, .ed-ram-list, [role="dialog"], .ed-toast, .ed-drag, .ed-pick';
  function intersects(a, b) {
    const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    return w > 2 && h > 2;
  }
  window.lunarLayoutProbe = function (rootSel) {
    const bad = [];
    const root = document.querySelector(rootSel || '.ed');
    const vw = document.documentElement.clientWidth;
    if (!root) return ['no editor to check'];
    if (document.documentElement.scrollWidth > vw + 1) bad.push(`page scrolls sideways (${document.documentElement.scrollWidth} > ${vw})`);
    const items = [];
    const visible = (el) => {
      const cs = getComputedStyle(el);
      return cs.visibility !== 'hidden' && cs.display !== 'none' && Number(cs.opacity) !== 0;
    };
    const range = document.createRange();
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const text = n.nodeValue.trim();
      const el = n.parentElement;
      if (!text || !el || el.closest('.ed-sr, [hidden], [aria-hidden="true"], script, style, canvas, option, noscript') || !visible(el)) continue;
      range.selectNodeContents(n);
      const rects = [...range.getClientRects()].filter((r) => r.width > 1 && r.height > 1);
      if (rects.length) items.push({ el, text: text.slice(0, 28), rects, kind: 'text' });
    }
    for (const el of root.querySelectorAll('input:not([type="checkbox"]):not([type="radio"]), select, textarea')) {
      if (!visible(el) || el.closest('[hidden], .ed-sr')) continue;
      const r = el.getBoundingClientRect();
      if (r.width > 1 && r.height > 1) items.push({ el, text: el.getAttribute('aria-label') || el.name || el.tagName.toLowerCase(), rects: [r], kind: 'control' });
    }
    // Outside the page, or clipped by an ancestor that hides what is past it.
    for (const it of items) {
      const cs0 = getComputedStyle(it.el);
      for (const r of it.rects) {
        let scrollsX = false, scrollsY = false;
        for (let a = it.el; a && a !== document.body; a = a.parentElement) {
          const cs = getComputedStyle(a);
          const hideX = cs.overflowX === 'hidden' || cs.overflowX === 'clip';
          const hideY = cs.overflowY === 'hidden' || cs.overflowY === 'clip';
          if (cs.overflowX === 'auto' || cs.overflowX === 'scroll') scrollsX = true;
          if (cs.overflowY === 'auto' || cs.overflowY === 'scroll') scrollsY = true;
          if ((hideX || hideY) && !(a === it.el && cs0.textOverflow === 'ellipsis')) {
            const ar = a.getBoundingClientRect();
            if ((hideX && (r.left < ar.left - 1 || r.right > ar.right + 1)) || (hideY && (r.top < ar.top - 1 || r.bottom > ar.bottom + 1))) {
              bad.push(`"${it.text}" is clipped by ${a.tagName.toLowerCase()}.${String(a.className).split(' ')[0]}`);
              break;
            }
          }
        }
        if (!scrollsX && (r.left < -1 || r.right > vw + 1)) { bad.push(`"${it.text}" runs past the page (${Math.round(r.left)}..${Math.round(r.right)} of ${vw})`); break; }
      }
    }
    // Overlaps.
    for (let i = 0; i < items.length; ++i) {
      for (let j = i + 1; j < items.length; ++j) {
        const a = items[i], b = items[j];
        if (a.el === b.el || a.el.parentElement === b.el.parentElement) continue;
        if (a.el.contains(b.el) || b.el.contains(a.el)) { if (a.kind === 'control' || b.kind === 'control') continue; }
        const pa = a.el.closest(POPUP), pb = b.el.closest(POPUP);
        if (pa !== pb) continue;                                 // a popup over the page is on purpose
        if (a.rects.some((x) => b.rects.some((y) => intersects(x, y)))) bad.push(`"${a.text}" overlaps "${b.text}"`);
      }
    }
    return bad.slice(0, 12);
  };
})();
