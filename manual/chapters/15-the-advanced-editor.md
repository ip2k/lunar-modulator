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
gives the editor the whole page and shows the FM-1's screen in a small card
beside it, headed *On the FM-1*, so you can see what the panel shows while you
work. Power the simulator on first; until then the editor says so.

{{page editor-flow The editor on the example project First orbit: the outline on the left, the Flow in the middle with four sounds into the mix and the two master effects, and the FM-1’s screen in its card.}}

Along the top of the editor:

- **Keys PLAY** or **Keys EDIT** says what the computer keyboard does. In PLAY
  the keys play the instrument, as they do on the panel. Click in the editor,
  or press <kbd>Ctrl</kbd>+<kbd>E</kbd> (<kbd>⌘</kbd>+<kbd>E</kbd> on a Mac), and
  it reads EDIT: the keys edit and play nothing, so a stray letter never
  changes a view while you mean to play. <kbd>Esc</kbd> gives the keys back.
- **Follow the panel** moves the editor to whatever the panel shows. **Open on
  the panel** does the reverse: choosing a block or a parameter in the editor
  opens its page on the panel.
- **Undo** and **Redo** cover what you do in the editor and what you turn on
  the panel, alike.
- **RAM** is how much of the FM-1's memory the project uses, as a percentage.
  Click it for the share of each part. Nothing the editor lets you do can go
  past 100 %.

## The outline, the Flow and the sounds

{{status sim}}

The outline on the left lists the four sounds, **Flow and effects**,
**Modulation**, and under *Project* the **Library**, **Compare A/B**,
**Memory** and **Search**. Click one to open it.

**Flow and effects** draws the signal path: each sound's engine into its two
inserts, the four sounds into the mix, and on into the two master effects.
Every block shows its name and a meter. Click a block and its values open below
it.

A sound opens as a page of sliders grouped by the panel's own pages. A slider
moves with the mouse or the arrow keys. <kbd>Shift</kbd> moves it ten steps,
<kbd>Alt</kbd> a tenth of a step, <kbd>Home</kbd> and <kbd>End</kbd> go to the
ends, and <kbd>Enter</kbd> lets you type a value. <kbd>D</kbd> puts a value back
to its default. A small *v* on a parameter means a cable can move it for each
note on its own (see [Modulation](08-modulation.md#per-voice)).

{{page editor-sound Sound 3 in the editor: its engine, two inserts and the cables into it, with a slider for every value.}}

## Choosing and moving effects

{{status sim}}

*Choose engine…*, *Choose effect…*, *Choose MIDI effect…* and *Choose
module…* list every choice with the memory the project would use with it, as a
percentage. A choice that does not fit says why, in the same words the panel
uses, and cannot be picked.

To move an effect, drag it onto another effect slot, of any sound or the
master. The two swap places, with their cables. Before you let go, the slot
under it says whether the swap fits and what the memory would be. With the
keyboard, <kbd>Space</kbd> picks the effect up, the arrow keys choose where,
<kbd>Space</kbd> drops it and <kbd>Esc</kbd> cancels; *Swap with…* in an
effect's box does the same from a list. Modules in the rack move the same way.

Effects show what goes in and what comes out. Comp, the output limiter and
Squash also show how much they are turning the sound down, as a thin bar and
*GR 4.8 dB* beside the *Out* meter, while they are doing it.

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
a glance: *v* is per voice, *!* is a cable that does not run, and *–* is one
that is switched off. A cable that does not run is kept as you wrote it, with
the reason beside it, and runs once the reason is put right.

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
everything again. *Refused* brings forward the cables that do not run.

### Making a cable

Drag from an output jack to an input jack. While the cable is in your hand every
destination opens, so any parameter can be a target. Over an input, the Map
asks the instrument what would happen and says so in the line above the Map:
*Runs*, or why not, in the refusal's own words. Let go to drop the cable. It
goes into the first free slot at 25 % and is selected, so its settings are open
under the Map; one **Undo** takes it away.

Without a mouse: press <kbd>Enter</kbd> on an output jack, move between inputs
with the arrow keys, and press <kbd>Enter</kbd> again to drop the cable.
<kbd>Esc</kbd> puts it back. There is one tab stop in each column; the arrow
keys walk within it, and every jack has a name. Screen readers should use the
table, which lists every cable in words.

### Room

The Map needs a window about 620 pixels wide for the editor. Below that, as on a
phone, the switch is not shown and Modulation stays a table, with each cable as
a small card.

## Files, the library and links

{{status sim}}

Every block takes files. Drop a `.lunar` sound on a sound, an effects file on
a sound's effects or on a master slot, a mod rack on the rack, or a whole project
anywhere. Before anything loads, the editor says what the file would do, what it
would replace and what it would bring, and how much memory the project would
use, or why it does not fit. **Load** goes ahead; nothing changes until you
choose it.

Each box has *Export…*, which saves that block as a file, and *Save to my
library*. The **Library** lists what you have saved in this browser, with Recent
and the examples; load a project from it, or drag a saved sound or effects onto
the block it fits, and the block says whether it fits while you hold it there.

**Search** (<kbd>Ctrl</kbd>+<kbd>K</kbd>, <kbd>⌘</kbd>+<kbd>K</kbd> on a Mac) finds
a sound, an effect, a parameter by name (*s2 cutoff*) or a command. Arrows
choose, <kbd>Enter</kbd> goes there, <kbd>Esc</kbd> closes it.

A link can open the editor at a place: add `?view=edit&sel=s1` or
`?view=edit&sel=s3.in1:Cutoff` to the simulator's address.

## Compare, Memory and Undo

{{status sim}}

**Compare A/B** keeps the project, or one sound, as A: choose *Keep as A*, then
edit as you like. <kbd>X</kbd> switches between A and what you made, B, and the
differences are listed.

**Memory** shows how much each part takes, as a percentage of what the FM-1 has:
each sound with its inserts, the two master effects, and what is shared (the
mix, the sequencer and the modulation), then what is in use, what is left, and
which sounds and effects would still fit in it.

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

Colour is never the only signal: the marks *v*, *!* and *–* come with words,
cable styles differ by line as well as colour, and a memory share that does not
fit is spelt out as “over”. In forced-colours mode the cables use the system's
colours and keep their dashes. With reduced motion set, nothing flashes or
moves apart from the meters, which are information.

## Phones and tablets

{{status sim}}

On a tablet the outline becomes a narrow rail and the Workbench stacks the panel
above the editor. On a phone the switch has two tabs, **Panel** and **Edit**.
Edit shows the outline as a row of tabs along the top, a small screen, and the
modulation matrix as a list of cables with every setting named. The Map is for
wider windows.

## Browsers

{{status sim}}

The editor is tested in Chromium, Firefox and WebKit (the engine of Safari) on a
desktop. It needs a browser with audio worklets and workers; the simulator's own
requirements are in [chapter 2](02-getting-started.md). It has not been tried on a phone
or a tablet itself, only at their window sizes, and not with a screen reader
itself, only with the accessibility tree a browser builds for one.
