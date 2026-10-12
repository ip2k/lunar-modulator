# The advanced editor

The advanced editor is a second way to play the virtual FM-1. It shows
everything the panel hides behind its pages: every parameter of a sound at
once, the whole signal flow, the modulation rack and its cables, and what each
choice would cost in memory before you make it. It does not replace the panel.
It edits the same instrument, so a knob turned on the panel moves its slider in
the editor, and a slider moved in the editor opens that page on the panel.

!!! note "In the simulator"
    The editor runs in the browser simulator, beside the panel or in its
    place. It edits what the simulator plays and nothing else: it never sends
    anything to a MIDI device, and nothing in it reaches an FM-1.

## Opening the editor

{{status sim}}

The switch at the top of the page has three positions. **Panel** is the
panel alone. **Workbench** puts the panel and the editor together. **Editor**
gives the editor the whole page and shows the FM-1's screen at its native
resolution in a small card beside it. Power the simulator on first; until
then the editor says so. A loaded project with a sequence opens **Song** the
first time you enter Workbench or Editor; your later view choices stay yours.

{{page editor-flow The editor on the example project First orbit: the outline on the left, the Flow in the middle with four sounds into the mix and the two master effects, and the FM-1’s screen in its card.}}

Along the top of the editor:

- **Files**, **Simulator** and **Changes** keep the page's file bar, simulator
  controls and edit history in menus while the editor is open. In **Panel**
  layout, the controls and file bar return to the page.
- The sidebar icon beside **Advanced editor** hides or brings back the
  outline and screen card. This choice is remembered by the browser.
- The keyboard/pen icon switches what the computer keyboard does. The
  keyboard means PLAY: keys play the instrument as on the panel. Click in the editor,
  or press <kbd>Ctrl</kbd>+<kbd>E</kbd> (<kbd>⌘</kbd>+<kbd>E</kbd> on a Mac), and
  the pen means EDIT: the keys edit and play nothing. <kbd>Esc</kbd> gives the
  keys back after any open popover or editor has closed. The shortcuts icon
  at the right opens the **Keyboard Shortcuts** guide.
- **Undo** and **Redo** cover what you do in the editor and what you turn on
  the panel, alike. Open **Changes** to see the recent history in a popover
  beside those buttons.
- **RAM** is how much of the FM-1's memory the project uses, as a percentage.
  Click it for the share of each part. Nothing the editor lets you do can go
  past 100 %.
- **CPU** measures browser audio rendering time against its block deadline.
  Click it for the measurement and its limits. It is not a measured estimate
  of CPU usage on the FM-1.

Below the screen, **Follow Panel** moves the editor to whatever the panel
shows. **Open on panel** does the reverse: choosing a block or parameter in
the editor opens its page on the panel.

The piano-keys icon beside **Cheat Sheet** opens MIDI learn. In Panel view it
sits beside the MIDI connection control. Highlighted controls turn teal;
click one, then press a controller key or move a CC to assign it. Its badge
shows the channel and note/CC, with an × to clear that assignment. Toggle the
icon again to use the controls. MIDI input is silent while learning. Custom
assignments are saved in the `.lunar` project and in this browser.

## The outline, the Flow and the sounds

{{status sim}}

The outline on the left lists the four sounds, **Flow and effects**,
**Modulation**, **Song**, and under *Project* the **Library**, **Compare A/B**,
**Memory** and **Search**. Click one to open it.

**Flow and effects** draws the signal path: each sound's engine into its two
inserts, the four sounds into the mix, and on into the two master effects.
Every block shows its name, a level bar and, when cables end on it, how many
(*2 cables*, or *1 cable, 1 refused* when one of them does not run). Click a
block and its values open below it. A long press on a block, a right click or
the keyboard's menu key opens a small menu for it: its page, another engine or
effect, *Swap with…*, *Export…*, *Save to my library* and *Copy a link*.

A sound opens as a page of sliders grouped by the panel's own pages. A slider
moves with the mouse or the arrow keys. <kbd>Shift</kbd> moves it ten steps,
<kbd>Alt</kbd> a tenth of a step, <kbd>Home</kbd> and <kbd>End</kbd> go to the
ends, and <kbd>Enter</kbd> lets you type a value. <kbd>D</kbd> puts a value back
to its default. A small *v* on a parameter means a cable can move it for each
note on its own (see [Modulation](08-modulation.md#per-voice)).

Where a cable moves a value, you see it on the slider as the screen shows it:
the parameter's name turns the modulation colour, a chip beside it names the
cable's source (click it to open the cable), a bracket shows how far the cables
can move the value either side of where you set it, and a white tick shows where
it is now. A per-voice cable draws one tick for each sounding note. The slider
says the same in words to a screen reader: “Cutoff, 420 hertz, modulated by 1 LFO
Out, plus 35 percent”. <kbd>C</kbd> on a parameter that takes a cable makes one
into it, from the first module's output, and opens it; on one that does not, the
editor says so in the instrument's words.

{{page editor-sound Sound 3 in the editor: its engine, two inserts and the cables into it, with a slider for every value.}}

## Choosing and moving effects

{{status sim}}

*Choose engine…*, *Choose effect…*, *Choose MIDI effect…* and *Choose
module…* list every choice with the memory the project would use with it, as a
percentage. A choice that does not fit says why, in the same words the panel
uses, and cannot be picked. An insert effect needs an engine in its sound;
the editor and panel both ask you to choose an engine first.

To move an effect, drag it onto another effect slot, of any sound or the
master. The two swap places, with their cables. Before you let go, the slot
under it says whether the swap fits and what the memory would be. With the
keyboard, <kbd>Space</kbd> picks the effect up, the arrow keys choose where,
<kbd>Space</kbd> drops it and <kbd>Esc</kbd> cancels; *Swap with…* in an
effect's box does the same from a list. Modules in the rack move the same way.

Effects show what goes in and what comes out. Comp, the output limiter and
Squash also show how much they are turning the sound down, as a thin bar and
*GR 4.8 dB* beside the *Out* meter, while they are doing it. Squash’s Snap
type also says **Gate open**, **Gate closing** or **Gate closed**, independently
of gain reduction, so a closed gate stays visible over silence. Its other
types have no gate readout.

## Modulation: the table

{{status sim}}

**Modulation** shows the rack and its cables. The default view is the table,
the one to use with a keyboard or a screen reader. The rack is eight cards,
each with its output drawn live. Under it, the matrix lists every cable: where
it comes from, its **VIA**, where it goes, its amount, its live value, and, if
it does not run, why.

{{page editor-table The modulation table: the rack as eight cards with live traces, and the matrix of cables below them.}}

A cable's number opens all of its settings: on or off, source, VIA, destination,
amount, offset, polarity, curve and per voice. Remove deletes it. *Add a
cable* puts a new one in the first free slot. A mark by the number says more at
a glance, in the instrument's own characters: *>* runs, *v* is per voice, *~*
runs a tick late, *!* does not run, and *–* is switched off. A cable that does not
run is kept as you wrote it, with the reason beside it, and runs once the reason
is put right; where the reason has a remedy, a button offers it (*Make it global*
for a per-voice cable aimed at an effect), and the instrument judges the result.
A cable marked *~* closes a loop: the cables run in rack order, so a cable that
goes back up the rack reads its source from the tick before. Its settings say
which modules the loop passes through. Curves are drawn, each on its button and
the chosen one larger, and a per-voice cable shows each sounding note's own value.

The amount is a percentage of the destination's range. Type a number and press
<kbd>Enter</kbd>, or use <kbd>↑</kbd> and <kbd>↓</kbd> (<kbd>Shift</kbd> for
ten).

## Modulation: the Map

{{status sim}}

**Map**, at the top right of Modulation, draws the same cables as a patch
bay. It is a second view of the same thirty-two slots: change a cable in the
table and the Map follows, and the other way round.

{{page editor-map The Map with the envelope in rack position 3 in focus: its two cables are bright with their amounts, and the other cables are dimmed.}}

The Map has three columns. **Sources** on the left are everything a cable can
start from: the notes and the clock, the sequencer's lanes, and each sound's own
notes. Sources in use are bright; the groups you are not using are folded under
a line such as *Sound 1’s notes · 5*. The **Rack** in the middle shows its modules with their
inputs on the left and their outputs on the right, each output with its live
value. **Destinations** on the right are the sounds, their effects, the master
and the host, listing the parameters that already have a cable and, behind
*13 more*, the rest.

A cable runs from a round or square **jack** on an output to one on an input.
Round jacks carry a continuous signal. Square ones carry gates and triggers.
Cables are drawn in the lanes between the columns and in a band above the rack;
they never cross a module or a label.

| The cable | Means |
| --- | --- |
| Dashed line | A modulation signal. The jacks at its ends are lit |
| Dotted line | A gate or trigger |
| Dashed line over a pale band, a *v* on its pill | A per-voice cable: each sounding note has its own value |
| Line in the refusal colour, ending in a cross | A cable that does not run. Its pill has a *!* |
| Any line, a *~* on its pill | A cable that runs a tick late. *A tick late* above the Map brings these forward |
| Thicker line in the selection colour | The cable chosen in the table below, or the one you clicked |

A **pill** beside a cable says its amount, and while the cable has something to
say, its live value. To keep the Map readable, pills appear only for the
selected cable, for the cables in focus, and for the refused ones.

### Focus

Thirty-two cables are too many to read at once. Click a module's name, a
destination's heading or a source's name and the Map goes into focus: that
block's cables stay bright and carry their amounts; every other cable dims and
loses its label. <kbd>F</kbd> does the same for the jack or block that has the
keys, and again to leave. <kbd>Esc</kbd>, or *All* above the Map, shows
everything again. *Refused* brings forward the cables that do not run, and *A tick late* the ones
that close a loop.

### Making a cable

Drag from an output jack to an input jack, or start at the input and drag
to an output. While the cable is in your hand every
destination opens, so any parameter can be a target. Over an input, the Map
asks the instrument what would happen and says so in the line above the Map:
*Runs*, or why not, in the refusal's own words. Let go to drop the cable. It
goes into the first free slot at 25 % and is selected, so its settings are open
under the Map; one **Undo** takes it away.

Select an existing cable and its two ends gain handles. Drag either handle
to another jack to reconnect that end in the same slot. The amount, VIA,
offset, curve and other settings stay with it; one Undo restores it.

Without a mouse: press <kbd>Enter</kbd> on either kind of jack, move between
the opposite jacks with the arrow keys, and press <kbd>Enter</kbd> again to drop
the cable. Edit an existing cable’s endpoints in the table or slot inspector.
<kbd>Esc</kbd> puts it back. There is one tab stop in each column; the arrow
keys walk within it, and every jack has a name. Screen readers should use the
table, which lists every cable in words.

An engine's information button opens a popover with its credits, group and
licence when those details are available.

### Room

The Map needs a window about 620 pixels wide for the editor. Below that, as on a
phone, the switch is not shown and Modulation stays a table, with each cable as
a small card.

## Songs, MIDI files and the mixer

{{status sim}}

Choose **Song** in the outline. Its five tabs show one task at a time:
**Scenes**, **Arrangement**, **Clip**, **Automation** and **Mixer**. The native
transport stays above the selected view as you switch tabs. **Files & export**
appears in the editor bar before Undo and Redo, with Open, Save `.lunar`,
Export `.movy1`, Export WAV, Import MIDI and Refresh. The five view tabs sit
below the active work area. On a phone, rotate to landscape; the portrait
prompt leaves playback running.

The pinned transport shows the native zero-based bar:beat:tick position and
total arrangement length, plus elapsed and estimated remaining time. Hover
over the icons for their meanings; remaining time is unavailable while
looping, parked or externally clocked. The play button becomes Pause during
playback and Resume while paused. Stop returns to `0:0:0`. Bar, clip and
scene navigation shows current/total counts and skips empty clips and scenes.
Tempo, metronome and the Song end choice (Loop, Park or Stop) are saved with
the `.lunar` project. The master meter at the right shows measured output level.

**Scenes** contains eight tracks and eight scene columns, with compact rows
that keep more of the matrix in view. Click a clip's body to open its piano
roll. The small play icon to its left launches that clip at the native bar
boundary. The play icon to the left of a scene title launches its column;
empty slots have a stop icon for their tracks. Click the blank
area of a track or scene header to select it; these headers are MIDI
mappable too. A translucent fill shows each playing clip's loop progress.
The arrows beside **Scenes** page through columns that fit the window, with
the visible scene range and total shown beside them.

Double-click a scene or track name to edit it; focus a name and press
<kbd>Enter</kbd> or <kbd>F2</kbd> to start editing with the keyboard. Press
<kbd>Enter</kbd> or leave the field to save, or <kbd>Esc</kbd> to cancel. Scene names allow up
to six printable characters without spaces, and the same scene name appears
wherever that scene is used, including repeated arrangement sections. Track names use
the native track-name field: up to 16 printable ASCII characters, including
spaces.

**Arrangement** builds a song from those same scenes. Its heading groups the
section pager, **＋ Add section**, **Section tools** and **Song ending**.
**＋ Add section** opens a chooser that appends the chosen scene without
changing which section is selected. **Section tools** starts collapsed and
holds copy, move, remove and repeat controls for the selected section.
Choose Loop, Park or Stop directly in the **Song ending** dropdown.
The arrows beside **Arrangement** page through the
sections that fit the window; condensed note previews show playback progress.
Repeats share their scene clips; copy a scene before editing a different variation.

**Clip** keeps Pitch, Step, Gate and Velocity visible for the selected note;
loop window, quantize and transpose remain clip controls. Click an empty cell
or use **Add note**. Drag a note to move it, or its right edge to change its
gate. Open **Advanced** for Microtiming and Probability. Microtiming uses
ticks, with 24 ticks per sixteenth step. Probability belongs to the note's
trigger. Opening a clip frames its first sounding note inside the loop and
scrolls that note into view; an empty clip opens at its loop start. The compact
step pager shows the visible range within longer clips. **Follow playhead**
turns pages automatically during playback; pitch navigation remains manual.
The clef icons move the pitch range by an octave. The ＋ menu copies or clears
scenes and clips; track and scene selectors sit below the grid.

**Automation** shows each assigned parameter-lock lane as a horizontal row,
up to eight native lanes per track. **Add automation** chooses an instrument,
sound insert, sound level or master-effect parameter. Enter step values from
0 to 127 across that parameter's range, or clear one to remove its lock. A lane
holds its last value until the next lock; the blocks show those stepped
changes and the native playhead follows playback. Several tracks routed to
one sound share that sound's parameters, inserts and level.

**Mixer** has four sound strips and Master, with vertical faders, dB readouts
and live peak/RMS meters. Instrument, insert and master-effect buttons open
their controls; Close or <kbd>Esc</kbd> returns to the button you used. Each
insert and master effect has input/output meters. **Routing & FX** opens the
track routes and device racks; it starts collapsed in short landscape windows.
Mute and Solo act on tracks routed to that sound. Saved sound levels belong to
the project; Master output level is the browser's volume preference.

The Song workspace's device inspectors put primary parameters first, with
less frequent settings and actions behind a disclosure. They open as modal
dialogs; focus moves to Close when a dialog opens, Escape closes it, and focus
returns to the control that opened it. **Files & export** remains available
from the Song workspace.

When the Song workspace owns the keyboard, its canvas shortcuts are
context-sensitive. <kbd>Space</kbd> plays or pauses and <kbd>Shift</kbd>+<kbd>Space</kbd>
restarts from the beginning and plays. <kbd>Tab</kbd> switches Arrangement and
Mixer; <kbd>E</kbd> and <kbd>A</kbd> open Clip and Automation. <kbd>D</kbd>
opens the selected track's routed instrument inspector, <kbd>I</kbd> toggles
the sidebar, and <kbd>0</kbd> or <kbd>Alt</kbd>+<kbd>A</kbd> toggles the
selected track's mute. <kbd>Enter</kbd> or <kbd>F2</kbd> renames a selected
track or Arrangement section. <kbd>Ctrl</kbd>/<kbd>⌘</kbd>+<kbd>D</kbd>
duplicates a selected note or Arrangement section; <kbd>Delete</kbd> or
<kbd>Backspace</kbd> removes it. Arrow keys move a selected note by one step
or semitone. Text fields, form controls, dialogs, Files & export and MIDI
preview keep their normal keys; ordinary Tab traversal and button activation
remain available. The editor continues to own Undo and Redo.

### Importing MIDI

Use **Files & export → Import MIDI…** to select one or several standard
`.mid` or `.midi` files. Type 0 and type 1 files are supported. The preview
lists their parts and lets you map each one to a native track and sound before
applying it. **Selected scene** puts one section into the scene you are editing.
Choose **New song chain on mapped tracks** to divide a longer part across
scene columns, and set **Bars per scene** to choose each section's length.
A warning explains unsupported data, and
an import that cannot fit is refused before changing the project.

An import batch accepts at most 16 files, 16 MiB per file, 32 MiB total and
64 parts total. Native sequencer content-generation changes refresh the visible
Song workspace after panel edits and invalidate a hidden view for refresh when
you return to it. Undo and Redo refuse a stale edit if another panel change
has changed the project in the meantime.

Lunar's limits remain eight tracks, eight scenes, a 256-step clip window,
64 scene presses in a song and 96 ticks per quarter note. It does not add
unbounded desktop-only tracks or audio clips. Instruments are chosen from
Lunar's sound engines; a MIDI file does not contain their audio.

### Saving projects and exporting audio

The same menu opens and saves `.lunar` projects and exports `.movy1`
sequencer sets. These are Lunar's native formats, shared with its panel and
sequencer core. Direct project access to hardware over USB-MIDI or Bluetooth
is future work; the FM-1 does not run Lunar yet.

**Export WAV…** renders the actual Wasm instrument in a separate worker.
Choose a stereo master, four stereo sound stems, one eight-channel WAV with
those sound pairs, or separate sequencer-track stems. The files use 24-bit PCM
at 44,118 Hz. Set a tail for effects; progress and Cancel remain available
during rendering. Completed files download automatically, and download links
remain if the browser blocks multiple downloads. Shared voices, modulation and nonlinear bus effects mean isolated
stems may not sum back to the master. Master effects are applied to the
stereo master; the export choices explain the other outputs.

## Files, the library and links

{{status sim}}

Every block takes files. Drop a `.lunar` sound on a sound, an effects file on
a sound's effects or on a master slot, a mod rack on the rack, or a whole project
anywhere. Before anything loads, the editor says what the file would do, what it
would replace and what it would bring, and how much memory the project would
use, or why it does not fit. **Load** goes ahead; nothing changes until you
choose it.

Each box has *Export…*, which saves that block as a file, *Save to my
library* and *Copy a link*, a link that opens that block's file in someone else's
browser. In Chromium you can also drag a sound's tag in the Flow (*S2*) to the
desktop, and it becomes the sound's file. The **Library** lists what you have saved in this browser, with Recent
and the examples; load a project from it, or drag a saved sound or effects onto
the block it fits, and the block says whether it fits while you hold it there.

**Search** (<kbd>Ctrl</kbd>+<kbd>K</kbd>, <kbd>⌘</kbd>+<kbd>K</kbd> on a Mac) finds
a sound, an effect, a parameter by name (*s2 cutoff*), a cable or a command.
Arrows choose, <kbd>Enter</kbd> goes there, <kbd>Esc</kbd> closes it.
<kbd>Shift</kbd>+<kbd>Enter</kbd> selects every match, including those beyond
the first sixty displayed. The selection lists what it contains before you
change anything. Compatible parameters can take one common value; cables
can be enabled, disabled or removed. Each batch is one Undo step. Mixed
selections and parameters with different ranges or units need a narrower search. A few
signs narrow it: *>cutoff* is the cables into a Cutoff, *lfo>* the cables out of
an LFO, *!* the cables that do not run, *~* the ones a tick late, *v* the per-voice
ones, *s2* what belongs to Sound 2, and a unit such as *hz* the parameters in
hertz. They combine (*>cutoff !*).

A link can open the editor at a place: add `?view=edit&sel=s1` or
`?view=edit&sel=s3.in1:Cutoff` to the simulator's address.

## Compare, Memory and Undo

{{status sim}}

**Compare A/B** keeps the project, or one sound, as A: choose *Keep as A*, then
edit as you like. <kbd>X</kbd> switches between A and what you made, B, and the
differences are listed, each with a choice of A or B. *Make B from the picks*
loads B with A's value in every row you chose from A and B's in the rest, as one
step you can undo, after the instrument has said whether it fits. A and B are
kept in this browser, so they are still there after a reload.

**Memory** shows how much each part takes, as a percentage of what the FM-1 has:
shared mix, sequencer and modulation first, then the two master effects, then
each sound with its inserts. It shows what is in use, what is left, and which
sounds and effects would still fit. The CPU section shows browser rendering
cost and its deadline budget; hardware CPU usage remains unmeasured.

{{page editor-memory The Memory page: the share of the FM-1’s memory by part, what is free, and what would still fit.}}

**Undo** goes back one change at a time. It covers a slider, a choice of engine
or effect, a swap, a module moved, a cable made, edited or removed, and a file
loaded. A change from the panel's knobs is one step too.

## Keys, the keyboard and screen readers

{{status sim}}

Everything in the editor can be done from the keyboard. <kbd>Tab</kbd> moves
through the controls, each with a name and a two-pixel ring around it. Sliders
say their value in words (“Cutoff, 420 hertz”). The editor announces your
changes and any refusal, at most once a second, and never a live value.

Colour is never the only signal: the marks *>*, *v*, *~*, *!* and *–* come with words,
cable styles differ by line as well as colour, and a memory share that does not
fit is spelt out as “over”. In forced-colours mode the cables use the system's
colours and keep their dashes. With reduced motion set, nothing flashes or
moves apart from the meters, which are information.

## Phones and tablets

{{status sim}}

On a tablet the outline becomes a narrow rail and the Workbench stacks the panel
above the editor. On a phone the switch has two tabs, **Panel** and **Edit**.
Edit shows the outline as a row of tabs along the top, a small screen, and the
modulation matrix as a list of cables with every setting named. *Add a cable*
asks in three steps, with a sheet at the bottom of the screen: where it comes
from, where it goes, and how much, with the instrument's verdict before you
make it. A long press on a block opens its menu. The Map is for wider windows.

## Browsers

{{status sim}}

The editor is tested in Chromium, Firefox and WebKit (the engine of Safari) on a
desktop. It needs a browser with audio worklets and workers; the simulator's own
requirements are in [chapter 2](02-getting-started.md). Its views are checked with axe-core's
rules at desktop, tablet and phone widths. It has not been tried on a phone or a
tablet itself, only at their window sizes, and not with a screen reader itself,
only with the accessibility tree a browser builds for one.

A sound comparison reuses its modulation connections, so repeated A/B
switches do not fill the rack. If a shared modulation source has changed,
use the project comparison to compare it too; the sound comparison refuses
to overwrite a changed source that another destination uses.
