# manual/ — the Lunar Modulator user manual

The user manual for Lunar Modulator, written like the booklet that ships with
an instrument: what each control does, how to play every engine and effect,
the sequencer, MIDI, specifications. It is published on GitHub Pages at
`/manual/` beside the browser simulator, as web pages and as one PDF, and it is
rebuilt whenever the manual, the engines, the simulator or the branding
change, because its reference tables are generated from the code.

```bash
python3 -m venv /tmp/manual-venv && /tmp/manual-venv/bin/pip install -r manual/requirements.txt
/tmp/manual-venv/bin/python tools/manual/build.py --serve     # build into _site/, preview on localhost:8000
/tmp/manual-venv/bin/python tools/manual/build.py --strict    # what CI checks, without the PDF
tools/manual/build-in-docker.sh                               # everything CI builds, PDF included (needs Docker)
python -m pytest tests/test_manual.py
```

Python 3.11 or newer. `build.py` runs `make -C engines` first (skip it with
`--no-make`, or point `--renderer` at an `fm1-render`). The site lands in
`_site/`: the simulator at its root when `sim/web/www` is in the tree,
otherwise a small front page linking to the manual; the manual in
`_site/manual/`. The PDF needs WeasyPrint and Pango (below).

## Layout

| Path | What |
| --- | --- |
| `manual.toml` | Title, tagline, page size, chapter order with one-line summaries, the control vocabulary |
| `chapters/*.md` | One Markdown file per chapter, plus the glossary and the index of controls |
| `data/seq-verbs.toml` | What each sequencer script verb does; the list of verbs itself comes from the code |
| `diagrams/*.toml`, `diagrams/*.svg` | The block and state diagrams: one source each, and the drawing made from it ([diagrams/README.md](diagrams/README.md)) |
| `theme/manual.css` | Screen styles: the Rosé Pine Dawn tokens, layout, tables, badges, admonitions |
| `theme/print.css` | The printed book: page size, running heads, page numbers, contents with page numbers |
| `theme/*.html` | Templates: a chapter page, the manual's front page, the book (`print.html`, the PDF's source), the site's front page when there is no simulator |
| `requirements.txt` | The build's two dependencies, pinned |
| `../tools/manual/build.py` | The build: Markdown to pages, the book, the PDF, the site, the checks |
| `../tools/manual/mdext.py` | The Markdown additions below |
| `../tools/manual/reference.py` | The generated tables |
| `../tools/manual/figures.py` | The panel drawings, as SVG, from the simulator's measurements |
| `../tools/manual/diagrams.py` | Lays out and draws the diagrams; `diagram_theme.py` their colours, `diagram_metrics.py` the type's widths, `diagram_check.py` the collision check |
| `../tools/manual/policy.py` | The words the published manual must not contain |
| `../tools/manual/build-in-docker.sh` | The CI build in Ubuntu 24.04, for machines without Pango |
| `../.github/workflows/pages.yml` | Builds on pull requests, deploys from main |

## Writing

Plain Markdown (Python-Markdown with tables, definition lists, footnotes and
smart quotes), British spelling, second person, short sentences. Each chapter
has exactly one `# ` title; `##` and `###` headings are numbered by the build
(5, 5.1, 5.1.1). Link to another chapter by its file: `[chapter 7](07-sequencer.md#clips)`.

Additions:

| Write | Get |
| --- | --- |
| `[[SELECT]]` | A control as the panel prints it, indexed in the index of controls. The name must be in `manual.toml`'s `[controls]`, or the build stops |
| `[[role:SHIFT]]` | A sequencer function still to be given a button (docs/13 §4), drawn dashed and indexed apart |
| `{{status sim desktop planned}}` | Where a function runs today: *In the simulator*, *On the desktop*, *Planned for the device*; any of the three |
| `!!! note`, `!!! tip`, `!!! caution`, `!!! warning` | The four boxes a product manual uses. Cautions are for hearing and data, warnings for the instrument |
| `!!! outline "To be written"` | A dashed *Draft* box for a section not written yet. While any is left, the front page and the PDF say *Draft* and count them |
| `{{engine-table ID}}` | An engine's or effect's knob map, parameter table and list values, from `fm1-render --list` |
| `{{engine-table ID gpl}}` | The same for a GPL module (CLAUDE.md, "The GPL switch"): a build made with `FM1_GPL_MODS=0` leaves the engine out, and the table becomes a note saying so instead of an error |
| `{{engine-summary sound}}`, `{{engine-summary audio_fx}}` | One row per engine or effect, linking to its section |
| `{{engine-others sound}}` | A section for every engine in the build that has no `{{engine-table}}` yet, so a new engine is never missing from the manual |
| `{{seq-glance}}`, `{{seq-memory}}`, `{{seq-verbs}}` | The sequencer's figures (`fm1_seq.h`), its memory by track count (`fm1-seq --sizes`) and its script verbs (`seq_cmd.c` with `data/seq-verbs.toml`) |
| `{{requires seq}}` | A note when this build lacks the sequencer's code |
| `{{figure panel}}`, `{{figure edge}}` | A numbered figure from `figures.py` |
| `{{diagram signal-flow}}` | A numbered block or state diagram from `diagrams/signal-flow.toml`, with the caption and the long description written there ([diagrams/README.md](diagrams/README.md)) |
| `{{screen params Caption text.}}` | A numbered figure of the firmware's screen, from the simulator's `assets/screenshots/screen-params.png` (left out, with a warning, when the file is missing). The caption is plain text: write the typographic apostrophe (’) yourself |
| `{{page editor-map Caption text.}}` | A numbered figure of the browser page, from `assets/screenshots/page-editor-map.png` (the advanced editor's pictures, made by `sim/web/test/editor-shots.mjs`; left out, with a warning, when the file is missing). Written like `{{screen}}` |
| `{{status-key}}`, `{{build-info}}`, `{{controls-index}}` | The status legend, the edition table, the generated index of controls |

Directives sit on a line of their own and are never expanded inside code
blocks.

### Honesty

Nothing in the manual may suggest that Lunar Modulator can be installed on an
FM-1 today. Every `##` section of a chapter marked `features = true` in
`manual.toml` must carry a `{{status ...}}` line, and the build stops if one
does not. *Planned for the device* means designed and documented, not built
for the hardware. Chapter 1 states the one rule (CLAUDE.md) and points to the
simulator instead.

The research docs' confidence marks (`[verified]`, `[reported]`,
`[inferred]`) stay out of the prose; the statuses carry that for functions,
and chapter 13's *source* column for the instrument's figures. Only write what
the docs or the code support; when they do not yet, write an outline box.

The build also refuses private network addresses, home-directory paths,
logins and local host names, any space agency's name and the forbidden short
forms of the project's name (`tools/manual/policy.py`). The patterns name no
machine or person; to refuse your own host and account names as well, list
them in `MANUAL_PRIVATE_WORDS` (comma-separated) in your shell, never in the
repository.

## What is generated, and from where

| Table | Source | Without it |
| --- | --- | --- |
| Engines and effects, their parameters, pages, ranges, defaults, list values, voices and credits | `engines/build/fm1-render --list` | The build cannot run |
| List value names (Model, Shape, Patch, Pad) | `names` in `--list`; Six-Op FM's are the public build's descriptive names | The table says the names are not reported, and the build warns |
| The sequencer at a glance | `engines/include/fm1_seq.h` | A note in place of the table |
| Script verbs | `kVerbs` in `engines/seq/seq_cmd.c`, described in `data/seq-verbs.toml` | A note; an undescribed or stale verb warns |
| Sequencer memory | `engines/build/fm1-seq --sizes` | Left out |
| Index of controls | Every `[[...]]` in the text, plus each group's section in the panel tour (`[control_home]`) | — |
| Edition line | The commit (`MANUAL_COMMIT`, `GITHUB_SHA` or `git`) and the build date (UTC, or `SOURCE_DATE_EPOCH`) | "unknown" |

`_site/manual/reference.json` holds the engine data the tables came from.

The published simulator page (the copy in `_site/`, never `sim/web/www`)
gains two links to the manual: one in its opening paragraph and a *Manual*
row in its help list.

## Checks

`--strict` (CI) fails on: an unknown control, role, status or directive; an
`{{engine-table}}` naming no engine; a chapter without exactly one title; a
feature section without a status; a link to a page or anchor that does not
exist, or a missing asset; a forbidden word; a Markdown placeholder
(`wzxhzdk`) left in a page. Warnings (missing list names,
undescribed verbs, engines without a section, no branding fonts) are printed,
as GitHub annotations in Actions, and do not fail the build.
`tests/test_manual.py` checks the palette and its contrast, the generated
tables, the sequencer parsing, the figures against the simulator's
measurements, and runs the strict build. A diagram that cannot be laid out,
or whose drawing lets a word touch a word, a box, a line or the edge, stops
the build too; `tests/test_manual_diagrams.py` checks the same, the
diagrams' colours, and that the committed SVGs match their sources.

## The look

Colours are [Rosé Pine Dawn](https://rosepinetheme.com/palette/) (MIT,
mvllow), as published on 2026-10-01; Dawn's text colour is `#464261` there.
Words are set only in *text* and *pine*, which reach 8.7:1 and 5.6:1 on the
base; the other accents mark borders, badges and shapes. Headings and the
cover use Audiowide from `assets/branding/fonts/` (SIL OFL 1.1, served
unmodified with its `OFL.txt`) when the branding is in the tree, and fall
back to the body face otherwise. Body text is IBM Plex Sans (SIL OFL 1.1)
where installed: CI and the Docker build install Ubuntu's `fonts-ibm-plex`
for the PDF; on the web the reader's system sans stands in. No font is
loaded from another site.

The PDF is A5, the size of a booklet in a box (`paper` in `manual.toml`):
cover, an about page with the status key, contents with page numbers, one
chapter per page break, running heads, page numbers that match a PDF
viewer's, bookmarks from the headings, and page numbers in the index of
controls.

## Why this toolchain

A small generator of our own on Python-Markdown, with WeasyPrint for the PDF,
rather than MkDocs with the Material theme:

- **Fewer moving parts.** Two pinned dependencies (both BSD) instead of MkDocs,
  its theme and a PDF plugin. MkDocs itself has had no release since 1.6.1 in
  August 2024 (PyPI, checked 2026-10-01).
- **The generated content is the point.** Directives, the control index, the
  status check and the link check are a few hundred lines here; as MkDocs
  plugins and hooks they would be as much code, plus the framework.
- **Print quality.** WeasyPrint implements CSS paged media: page-numbered
  contents and index, running heads, bookmarks. Browser printing does none of
  the first two.
- **The theme is ours.** One stylesheet of Rosé Pine Dawn tokens instead of
  overriding another theme's variables.

What it gives up: a search box (the contents, the index of controls and the
PDF stand in for now) and MkDocs' plugin ecosystem.

## Publishing

`.github/workflows/pages.yml` builds on pull requests that touch the manual,
the engines, the simulator or the branding (the PDF is attached to the run)
and deploys on main. The repository's Pages source must be set to *GitHub
Actions* once, in Settings → Pages.
