# manual/diagrams/ — the manual's block and state diagrams

One source per diagram, `NAME.toml`, and the drawing made from it,
`NAME.svg`. A chapter shows one with `{{diagram NAME}}`; the build lays every
source out again (`tools/manual/diagrams.py`), so the manual always matches
its sources, and `tests/test_manual_diagrams.py` fails when a committed SVG is
stale or when anything in a drawing touches anything else.

```bash
python3 tools/manual/diagrams.py --write              # after editing a source: rewrite the SVGs
python3 tools/manual/diagrams.py --check              # what the tests check
python3 tools/manual/diagrams.py --png /tmp/d signal-flow   # look at one (needs rsvg-convert)
```

Draw only what the code does today, and say in the source's opening comment
which code that is. A part that is planned is left out, or named as planned
in its words.

## The format

```toml
# What this shows, and the code it was read from.
title = "Signal flow"              # the SVG's title
caption = "..."                    # the figure's caption in the manual
alt = "..."                        # the long description: what a reader who cannot see it needs
equal_cols = true                  # optional: every column as wide as the widest
equal_gaps = true                  # optional: every gap between columns as wide as the widest
legend = ["audio", "notes"]        # optional: the kinds to explain; default every kind used.
                                   # { kind = "press", label = "a launch" } renames one;
                                   # { role = "s1", label = "Sound 1" } adds a colour swatch

[[node]]                           # a box
id = "keys"
label = "Keys and MIDI IN"         # its name, in the heavier weight
sub = "play the current sound"     # further lines: a string, or a list of strings
col = 0                            # its cell: column and row, from 0
row = 0
cols = 2                           # optional: columns and rows it covers
rows = 1
stretch = true                     # optional: fill those cells
align = "left"                     # optional: left, center (default) or right in its cells
role = "s1"                        # optional: its colour, below
shape = "box"                      # box, state (round corners), hollow (dashed: an empty slot),
                                   # note (words beside a rule), start (a state diagram's dot),
                                   # cells (a strip: cells = ["LFO1", "LFO2", ""])

[[group]]                          # a frame around boxes
id = "s1"
label = "Sound 1"
members = ["e1", "a1", "b1", "l1"]
role = "s1"
title = "bottom"                   # optional: the title at the frame's foot

[[edge]]                           # a connection
from = "keys"                      # a box or a frame
to = "seq"
kind = "notes"                     # below
label = ["the focused track:", "recording, Capture"]
role = "s1"                        # optional: another colour than the kind's
exit = "right"                     # optional: the sides it may leave and enter by
enter = ["top", "left"]
marker = "refused"                 # optional: arrow (default), refused (a cross) or none
```

Nothing is placed by coordinates. Choose cells so that what flows together
sits together; leave a cell empty where lines need room. When a line cannot
be routed or a label has no room, the build says which, and a different cell
or an `exit`/`enter` usually solves it.

**Kinds**, each with its own line, so colour is never the only cue:

| Kind | Line | For |
| --- | --- | --- |
| `audio` | thick, solid | sound |
| `notes` | dotted, grey | notes and their routing |
| `mod` | dashed, modulation's colour | a modulation cable |
| `gate` | dotted, modulation's colour | a gate cable |
| `refused` | dashed, refusal's colour | a cable that is refused |
| `press` | thin, solid | a state change on a button press |
| `event` | thin, short dashes | a state change that happens by itself |
| `clock` | thin, dash and dot, grey | the tempo's ticks, Start and Stop |
| `link` | hairline | a state diagram's start |

**Roles** follow the screen's colour map (notes/2026-10-06-ui-audit.md §5):
`mod` and `live` (foam: modulation and live signal, PLAY), `select` (iris:
selection and editing), `held` (gold: held, locked, waiting for a bar),
`refuse` (love: refusal and recording), `s1` to `s4` (the four sounds), and
`neutral`, `ink`, `audio`, `empty`. `tools/manual/diagram_theme.py` derives
their Dawn colours and says how.
