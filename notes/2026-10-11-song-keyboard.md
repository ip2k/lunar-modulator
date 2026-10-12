# Song keyboard shortcuts — 2026-10-11

The Song workspace maps existing editor operations to these keys. [verified: `song-shortcuts.js`, `sequencer.js`, focused policy tests]

| Key | Action |
| --- | --- |
| Space | Play or pause, when the Song canvas has focus |
| Shift+Space | Restart from the beginning and play, on the canvas |
| Tab | Switch Arrangement/Mixer, on the canvas |
| E / A | Open Clip / Automation |
| D | Open the selected track's routed instrument inspector |
| I | Toggle the editor sidebar, through the host callback |
| 0 / Alt+A | Toggle selected track mute |
| Enter / F2 | Rename the selected track, or selected Arrangement section |
| Ctrl/Cmd+D | Duplicate a selected Clip note or Arrangement section |
| Delete / Backspace | Delete a selected Clip note or Arrangement section |
| Arrow Left / Right | Nudge the selected Clip note one step |
| Arrow Up / Down | Nudge the selected Clip note one semitone |

Canvas means the workspace itself, the noninteractive piano roll, or its surrounding view panel. A focused note or Arrangement section also accepts the relevant selection commands. Normal Tab traversal and Space activation remain available on buttons and tabs. Enter is restricted to canvas focus; a focused name field already supports Enter and F2. [verified: policy tests and browser harness]

Text fields, selects, sliders, contenteditable regions, modal dialogs, open Files & export menus, and MIDI import previews retain their own keys. The existing editor handles Undo/Redo and Escape/Ctrl/Cmd+E ownership switching. Modifiers other than the documented combinations, IME composition, already handled events and held-key repeats are left alone. The editor routes consumed Song commands in capture phase ahead of the simulator's global synth key handler. Song commands during a pending native transaction are consumed without queuing another operation. [verified: source, policy tests, browser harness]

Note duplication copies gate, velocity, exact microtiming and an associated probability/condition trigger to the next step. It refuses a stale source, an out-of-window destination, or a matching destination note/trigger. Note movement preserves microtiming and clamps to the clip window and MIDI pitch range. Section operations preserve the repeat count, native validators enforce arrangement limits, and all content edits use the existing native project admission and undo transaction path. Failed native admission restores selection and reports the refusal. [verified: pure note tests, browser mock admission/refusal checks, existing `edit()` implementation]

No keys imply unsupported audio tracks, new hardware tracks, clip stretching/joining, interpolation or new pointer/draw/erase modes. The available native click/draw operations stay as they are. [verified: keymap source]

Validation: six focused Node tests and 36 existing editor unit checks pass. The isolated Hera Playwright harness passes in Chromium, Firefox and WebKit. It covers callbacks, view switches, contextual note/section edits, rename, mute, native form and button activation, modal guards, pending admission, refusal rollback, lifecycle removal and key propagation. The harness uses a canonical mock host; actual native pause/resume/restart, undo acknowledgements and the combined rebuilt Wasm are the parent integration stream's acceptance dependency. No physical hardware acceptance or device write is claimed. [verified: saved test logs under ignored `scratch/song-shortcuts/`]

The semantic MCPs still selected the primary checkout rather than this worktree; Serena's configuration exposed C++ only. This subtask used file inspection and focused tests rather than retargeting another active agent's shared session. Rarefaction status and Serena initial/config checks ran, but neither was used as a verified semantic index for the edited JavaScript worktree. [verified: session tool output]
