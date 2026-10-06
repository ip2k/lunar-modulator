// shell.js -- the editor's frame, the same on every mockup: the app bar, the outline
// (with the FM-1's screen following the editor), the status bar. Each page gives its
// own <main> and a few data attributes on <body>. MIT like the repository.
(function () {
  const b = document.body.dataset;
  const layout = b.layout || 'editor';
  const page = b.page || 'sound';
  const UNDO = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3 L1.5 6.5 L5 10 M2 6.5 H10 a4 4 0 0 1 0 8 H7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const REDO = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M11 3 L14.5 6.5 L11 10 M14 6.5 H6 a4 4 0 0 0 0 8 H9" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const L = (n, cur) => `<span class="${cur ? 'on' : ''}">${n}</span>`;
  const keys = b.keys || 'EDIT';
  const appbar = `<header class="appbar">
    <div class="brand"><span class="w">Lunar Modulator</span><span class="sub">Advanced editor</span></div>
    <div class="project"><span class="n">First orbit</span><span class="k">Project · 4 sounds · edited</span></div>
    <div class="layouts" role="radiogroup" aria-label="Layout">${L('Panel')}${L('Workbench', layout === 'workbench')}${L('Editor', layout === 'editor')}</div>
    <div class="search" role="search"><span aria-hidden="true">⌕</span><span class="q">Search</span><kbd>⌘K</kbd></div>
    <span class="spacer"></span>
    <span class="chip"><span class="dot"></span><span class="only-wide">Live on the virtual FM-1</span><span class="only-tab">Live</span></span>
    <span class="chip"><span class="kw">Keys</span> <span class="mode">${keys}</span><span class="only-wide">· ${keys === 'PLAY' ? '⌘E edits' : 'Esc plays'}</span></span>
    <span class="btn" aria-label="Undo">${UNDO}</span><span class="btn" aria-label="Redo" aria-disabled="true">${REDO}</span>
    <span class="btn">File ▾</span>
    <div class="ram" title="300,672 of 387,924 bytes at 44,118 Hz">
      <div class="top"><span class="what">RAM <b>293.6</b> / 378.8 KB</span><b>78 %</b></div>
      <div class="bar"><span class="sg-fixed" style="width:16.8%"></span><span class="sg-gap"></span><span class="sg-s1" style="width:2.6%"></span><span class="sg-gap"></span><span class="sg-s2" style="width:25.4%"></span><span class="sg-gap"></span><span class="sg-s3" style="width:8.6%"></span><span class="sg-gap"></span><span class="sg-s4" style="width:21%"></span><span class="sg-gap"></span><span class="sg-m" style="width:3.2%"></span></div>
    </div>
  </header>`;
  const N = (ic, t, n, cur, cls = '') => `<div class="nav${cur ? ' cur' : ''}${cls}">${ic}<span class="t">${t}</span>${n ? `<span class="n">${n}</span>` : ''}</div>`;
  const S = (k, eng, cur) => N(`<span class="tag s${k}">S${k}</span>`, eng, '', cur);
  const sub = (t, n, cur) => `<div class="nav sub${cur ? ' cur' : ''}"><span class="t">${t}</span>${n ? `<span class="n">${n}</span>` : ''}</div>`;
  const cs = +(b.sound || 0);
  const screen = b.screen ? `<div class="screen-card"><div class="h">On the FM-1<span class="dot"></span></div><img src="img/${b.screen}" alt="${b.screenAlt || ''}"><div class="c">${b.screenCap || ''}</div></div>` : '';
  const side = `<aside class="side" aria-label="Outline">
    <h4>Sounds</h4>
    ${S(1, 'Drums', cs === 1)}${S(2, 'Macro', cs === 2)}${cs === 2 ? sub('Arp', 'on') + sub('Engine', 'Wavetable') + sub('Inserts', '1') : ''}${S(3, 'Macro', cs === 3)}${S(4, 'FM6', cs === 4)}
    <h4>Signal</h4>
    ${N('<span class="ic">FX</span>', 'Flow and effects', '8', page === 'flow')}
    <h4>Modulation</h4>
    ${N('<span class="ic">RK</span>', 'Rack', '6/8', page === 'rack')}${N('<span class="ic">MX</span>', 'Matrix and map', '10/32', page === 'mod')}
    <h4>Project</h4>
    ${N('<span class="ic">AB</span>', 'Compare', '', page === 'compare')}${N('<span class="ic">RAM</span>', 'Memory', '78 %', page === 'memory')}${N('<span class="ic">FI</span>', 'Files and history', '', page === 'project')}
    ${screen}
  </aside>`;
  const status = `<footer class="statusbar"><span class="dot"></span><span class="grow"><b>Saved in this browser</b> · autosave 4 s ago · ${b.status || 'last change: <span class="src">panel</span> KNOB2, S3 In1 Cutoff 1.20 kHz → 420 Hz'}</span><span>Licences and credits</span><span>lunar 1.0 · metadata 1.0</span></footer>`;
  const main = document.querySelector('main');
  const app = document.createElement('div');
  app.className = 'app' + (layout === 'workbench' ? ' rail' : '');
  app.innerHTML = appbar + `<div class="body">${side}</div>` + status;
  document.body.prepend(app);
  app.querySelector('.body').appendChild(main);
})();
