// launch.mjs -- starts the browser a page test runs in (stage ED5b): Chromium
// by default, or Firefox or WebKit with BROWSER=firefox|webkit, as Playwright
// ships them. The tests that name a host to resolve (files.mjs, screenshot.mjs)
// need Chromium's resolver rules and stay on Chromium; the editor's tests
// (editor.mjs, editor-ui.mjs, editor-reach.mjs, editor-map.mjs, editor-v1.mjs) run in all three.
// Firefox needs an audio device: in a headless container with no sound card its
// AudioContext never leaves "suspended" (its null-context pref does not help), so
// the worklet never runs. A PulseAudio null sink does it (the commands are in
// sim/web/README.md, "Stage ED5b"; build-on-aeon.sh runs only Chromium); the clock
// is then the sink's, not a card's.
// MIT licence, like the rest of this repository.

import { createRequire } from 'node:module';

const require = createRequire(`${process.env.PLAYWRIGHT_DIR || '/pw'}/`);
export const which = process.env.BROWSER || 'chromium';

// { browser, name }: `name` for a report ("Firefox 150.0 (Playwright, headless)").
export async function launch() {
  const pw = require('playwright');
  if (!pw[which]) throw new Error(`BROWSER=${which}: chromium, firefox or webkit`);
  const opts = which === 'chromium' ? { args: ['--autoplay-policy=no-user-gesture-required'] }
    : which === 'firefox' ? { firefoxUserPrefs: { 'media.autoplay.default': 0, 'media.autoplay.blocking_policy': 0 } } : {};
  const browser = await pw[which].launch(opts);
  return { browser, name: `${which[0].toUpperCase()}${which.slice(1)} ${browser.version()} (Playwright, headless)` };
}
