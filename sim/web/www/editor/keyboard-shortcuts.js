// A guide to the keyboard routes implemented by editor.js, project.js,
// song-shortcuts.js/sequencer.js and the simulated FM-1 panel in app.js.
// Keep each row's context explicit: the panel and editor do not own keys at
// the same time. MIT licence, like the rest of Lunar.

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function createKeyboardShortcutsGuide(isMac) {
  const mod = isMac ? '⌘' : 'Ctrl+';
  const groups = [
    ['Editor', 'Editor workspace; text fields keep their normal keys.', [
      [`${mod}E`, 'Switch between editor keys and FM-1 playing keys.'],
      [`${mod}K`, 'Search blocks, parameters and commands.'],
      [`${mod}Z`, 'Undo an editor change while keys edit.'],
      [isMac ? '⇧⌘Z' : 'Ctrl+Y / Ctrl+Shift+Z', 'Redo while keys edit.'],
      ['Esc', 'Give the keys back to the FM-1, outside a text field or dialog.'],
      ['X', 'Switch A/B snapshots after A is saved; edit mode only.'],
    ]],
    ['Song workspace', 'Focus the Song canvas, a note or a section; shortcuts pause in forms and dialogs.', [
      ['E / A / D', 'Open Clip / Automation / instrument controls.'],
      ['I', 'Show or hide the editor sidebar.'],
      ['Tab', 'Switch Arrangement and Mixer when the canvas has focus.'],
      ['Space / Shift+Space', 'Play or pause / restart when the canvas has focus.'],
      ['0 / Alt+A', 'Mute or unmute the selected track.'],
      [`${mod}D`, 'Duplicate a selected note or arrangement section.'],
      ['Delete / Backspace', 'Delete a selected note or arrangement section.'],
      ['Arrow keys', 'Move a selected Clip note by one step or semitone.'],
      ['F2 / Enter', 'Rename a track or selected section when available.'],
    ]],
    ['Editor controls', 'Focus a parameter slider or segmented choice in the advanced editor.', [
      ['Arrow keys', 'Change the value by one step; Shift makes ten steps, Alt one tenth.'],
      ['Page Up / Page Down', 'Change the value by ten steps.'],
      ['Home / End', 'Set the minimum / maximum value.'],
      ['D / Enter', 'Restore the default / edit the numeric value.'],
      ['C', 'Cable a parameter into Flow when available.'],
      ['Choice: arrows, Home / End', 'Pick the next option, or the first / last option.'],
    ]],
    ['FM-1 panel', 'Keys playing mode, outside form fields and dialogs.', [
      ["A W S E D R F G Y H U J K O L P ; [ '", 'Play F3–B4 across the computer keyboard.'],
      ['Z / X', 'Octave down / up.'],
      ['Space / Esc', 'Panel Play/Stop / release held keys and panic.'],
      ['← → / ↑ ↓', 'Turn Select / Presets.'],
      ['− / =', 'Turn Algorithm down / up.'],
      ['Focused knob: arrows', 'Turn that encoder, or adjust Master.'],
      ['SEQ: 1–8, C V B N M , . /', 'Press the 16 sequencer steps; hold Shift for SEL.'],
    ]],
  ];

  const dialog = element('dialog', 'ed-shortcuts-dialog');
  dialog.setAttribute('aria-labelledby', 'ed-shortcuts-title');
  dialog.id = 'ed-shortcuts-guide';
  const frame = element('div', 'ed-shortcuts-frame');
  const heading = element('header', 'ed-shortcuts-heading');
  const title = element('h2', '', 'Keyboard shortcuts');
  title.id = 'ed-shortcuts-title';
  const close = element('button', 'ed-shortcuts-close', '×');
  close.type = 'button';
  close.setAttribute('aria-label', 'Close keyboard shortcuts');
  close.addEventListener('click', () => dialog.close());
  heading.append(title, close);
  const content = element('div', 'ed-shortcuts-content');
  for (const [name, context, rows] of groups) {
    const section = element('section', 'ed-shortcuts-group');
    section.append(element('h3', '', name), element('p', 'ed-shortcuts-context', context));
    const list = element('dl', 'ed-shortcuts-list');
    for (const [keys, meaning] of rows) {
      const row = element('div', 'ed-shortcuts-row');
      const term = element('dt');
      term.append(element('kbd', '', keys));
      row.append(term, element('dd', '', meaning));
      list.append(row);
    }
    section.append(list);
    content.append(section);
  }
  frame.append(heading, content);
  dialog.append(frame);
  document.body.append(dialog);

  const button = element('button', 'ed-icon ed-shortcuts-trigger');
  button.type = 'button';
  button.title = 'Keyboard shortcuts';
  button.setAttribute('aria-label', 'Keyboard shortcuts');
  button.setAttribute('aria-haspopup', 'dialog');
  button.setAttribute('aria-controls', dialog.id);
  button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="3"/><path d="M5.5 8h2m3 0h2m3 0h2M5.5 11.5h2m10 0h1M6 16h3m6 0h3"/><path d="M11.5 12.5c-1.5-1.8-3.3.7-1.2 1.5m3.2-1.5c1.5-1.8 3.3.7 1.2 1.5m-3.2-1.5c-1.5 1.8.7 3.4 2 1.2m0 0c1.3 2.2 3.5.6 2-1.2"/></svg>';
  button.addEventListener('click', () => {
    if (dialog.open) return;
    dialog.showModal();
    close.focus();
  });
  dialog.addEventListener('close', () => button.focus({ preventScroll: true }));
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  // Let the native dialog handle Escape before the editor's global Escape
  // route can hand computer keys back to the panel.
  dialog.addEventListener('keydown', event => { if (event.key === 'Escape') event.stopPropagation(); });
  return button;
}
