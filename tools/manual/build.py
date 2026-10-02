#!/usr/bin/env python3
"""Build the Lunar Modulator user manual: a website and a PDF.

    python tools/manual/build.py                    # HTML into _site/manual/
    python tools/manual/build.py --pdf --strict     # and the PDF; fail on any error (CI)
    python tools/manual/build.py --site _site       # the whole Pages site: simulator at /, manual at /manual/
    python tools/manual/build.py --serve            # build, then preview on http://localhost:8000/

Sources are manual/ (manual.toml, chapters/*.md, theme/, data/). Reference
tables are generated from the code at build time: `make -C engines`, then
`engines/build/fm1-render --list` and, when the sequencer is in the tree, its
header, its verb table and `fm1-seq --sizes` (tools/manual/reference.py).
Needs Python 3.11+ and manual/requirements.txt (Markdown; WeasyPrint for
--pdf). manual/README.md has the details. MIT licence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import markdown  # noqa: E402
from markdown.extensions.toc import slugify  # noqa: E402

import figures  # noqa: E402
import policy  # noqa: E402
import reference  # noqa: E402
from mdext import STATUSES, ChapterState, ManualContext, ManualExtension  # noqa: E402

REPO = HERE.parent.parent
FENCE_RE = re.compile(r"^(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")
DIRECTIVE_LINE = re.compile(r"^\{\{([a-z][a-z0-9-]*)(?:[ \t]+([^}]*?))?[ \t]*\}\}[ \t]*$")
CONTROLS_INDEX_TOKEN = "<!-- manual:controls-index -->"

@dataclass
class Chapter:
    file: str
    slug: str
    number: str | None
    features: bool
    summary: str
    backmatter: bool
    source: str = ""
    title: str = ""
    html: str = ""
    state: ChapterState | None = None
    figures: int = 0

    @property
    def page(self) -> str:
        return f"{self.slug}.html"

    @property
    def anchor(self) -> str:
        return "c" + (self.number.zfill(2) if self.number else self.slug)


@dataclass
class Build:
    cfg: dict
    repo: Path
    out: Path
    commit: str
    commit_short: str
    date: str
    engines: list
    seq: object
    branding: Path | None
    chapters: list[Chapter] = field(default_factory=list)
    engine_sections: dict[str, tuple[str, str]] = field(default_factory=dict)  # id -> (page, anchor)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sim_dir: Path | None = None
    screens: set = field(default_factory=set)        # assets/screenshots/screen-*.png in use


# ---- inputs ------------------------------------------------------------------------------

def git(repo: Path, *args) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                              text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def commit_info(repo: Path) -> tuple[str, str]:
    sha = os.environ.get("MANUAL_COMMIT") or os.environ.get("GITHUB_SHA")
    dirty = False
    if not sha:
        sha = git(repo, "rev-parse", "HEAD") or "unknown"
        dirty = bool(git(repo, "status", "--porcelain", "--untracked-files=no"))
    short = sha[:7] if sha != "unknown" else sha
    return sha, short + (" with local changes" if dirty else "")


def build_date() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    when = dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc) if epoch else dt.datetime.now(dt.timezone.utc)
    return when.strftime("%Y-%m-%d")


def load_engines(args, repo: Path):
    if args.list_json:
        return reference.parse_list(json.loads(Path(args.list_json).read_text()))
    renderer = Path(args.renderer) if args.renderer else repo / "engines" / "build" / "fm1-render"
    if not args.renderer and not args.no_make:
        print("manual: make -C engines", file=sys.stderr)
        subprocess.run(["make", "-C", str(repo / "engines"), f"-j{os.cpu_count() or 2}"], check=True,
                       stdout=subprocess.DEVNULL)
    if not renderer.is_file():
        raise SystemExit(f"manual: no renderer at {renderer}; run make -C engines, or pass --renderer or --list-json")
    return reference.parse_list(reference.run_list(renderer))


# ---- pre-scan: where each engine has its section -----------------------------------------

def prescan(b: Build) -> None:
    """Finds the heading each {{engine-table ID}} sits under, so summaries can
    link to it before that chapter is converted."""
    known = {e.id for e in b.engines}
    for ch in b.chapters:
        fenced, heading = False, None
        for line in ch.source.splitlines():
            if FENCE_RE.match(line):
                fenced = not fenced
                continue
            if fenced:
                continue
            m = HEADING_RE.match(line)
            if m:
                heading = m.group(2)
                continue
            d = DIRECTIVE_LINE.match(line)
            if d and d.group(1) == "engine-table":
                eid = (d.group(2) or "").strip()
                if eid not in known:
                    b.errors.append(f"{ch.file}: {{{{engine-table {eid}}}}} names no engine in this build")
                    continue
                if heading is None:
                    b.errors.append(f"{ch.file}: {{{{engine-table {eid}}}}} has no heading above it")
                    continue
                b.engine_sections[eid] = (ch.page, slugify(heading, "-"))


# ---- directives ------------------------------------------------------------------------------

def make_directive(b: Build):
    verbs = reference.load_verb_notes(b.repo / "manual" / "data" / "seq-verbs.toml")

    def note(text: str):
        return [("html", f"<p class='generated-note'>{html.escape(text)}</p>")]

    def directive(name: str, args: list[str], state: ChapterState):
        ch = next(c for c in b.chapters if c.slug == state.slug)
        if name == "engine-table":
            e = next((e for e in b.engines if e.id == (args[0] if args else "")), None)
            if e is None:
                return note("This engine is not in this build.")
            return [("html", reference.engine_table(e))]
        if name == "engine-summary":
            kind = args[0] if args else "sound"
            links = {eid: (f"#{anchor}" if page == ch.page else f"{page}#{anchor}")
                     for eid, (page, anchor) in b.engine_sections.items()}
            return [("html", reference.engine_summary(b.engines, kind, links))]
        if name == "engine-others":
            kind = args[0] if args else "sound"
            lines = []
            for e in b.engines:
                if e.kind != kind or e.id in b.engine_sections:
                    continue
                if e.id.startswith("test-"):
                    continue
                b.warnings.append(f"{e.id} ({e.name}) has no section in the manual; "
                                  f"{ch.file} lists it with its generated table only")
                lines += [f"## {e.name}", "", "{{status desktop}}", "",
                          f"{e.name} is in the firmware’s list of "
                          f"{'sound engines' if kind == 'sound' else 'effects'}, and this manual "
                          "does not describe it yet. Its parameters, generated from the code:", "",
                          ("html", reference.engine_table(e)), ""]
            return lines
        if name in ("seq-glance", "seq-memory", "seq-verbs"):
            if b.seq is None:
                return note("This table is generated from the sequencer’s code, which is not "
                            "part of this build yet.")
            if name == "seq-glance":
                out = reference.seq_glance(b.seq)
            elif name == "seq-memory":
                out = reference.seq_memory(b.seq)
            else:
                out = reference.seq_verbs(b.seq, verbs, b.warnings)
            return [("html", out)] if out else note("The sequencer in this build does not report this table.")
        if name == "figure":
            key = args[0] if args else ""
            if key not in figures.FIGURES:
                b.errors.append(f"{ch.file}: unknown figure '{key}'")
                return []
            ch.figures += 1
            draw, caption, alt = figures.FIGURES[key]
            label = f"Figure {ch.number}.{ch.figures}" if ch.number else f"Figure {ch.figures}"
            m = re.search(r"width='([\d.]+)' height='([\d.]+)'", draw())
            size = f" width='{m.group(1)}' height='{m.group(2)}'" if m else ""
            return [("html", f"<figure id='figure-{key}'><a href='assets/figures/{key}.svg'>"
                             f"<img class='figure-svg' src='assets/figures/{key}.svg'"
                             f"{size} alt='{html.escape(alt)}'></a><figcaption><span class='fig-label'>"
                             f"{label}</span>{html.escape(caption)}</figcaption></figure>")]
        if name == "screen":
            # {{screen KEY caption}}: the firmware's own screen, from the simulator's
            # screenshots (assets/screenshots/screen-KEY.png, 480 x 480, each pixel doubled).
            key = args[0] if args else ""
            caption = " ".join(args[1:])
            src = b.repo / "assets" / "screenshots" / f"screen-{key}.png"
            if not re.fullmatch(r"[a-z0-9-]+", key) or not caption:
                b.errors.append(f"{ch.file}: {{{{screen}}}} wants a name and a caption")
                return []
            if not src.is_file():
                b.warnings.append(f"{ch.file}: no {src.relative_to(b.repo)}; that screen is left out")
                return []
            b.screens.add(src)
            ch.figures += 1
            label = f"Figure {ch.number}.{ch.figures}" if ch.number else f"Figure {ch.figures}"
            return [("html", f"<figure class='screen' id='screen-{key}'>"
                             f"<img class='screen-shot' src='assets/screens/{src.name}' width='240' "
                             f"height='240' alt='The screen. {html.escape(caption)}'>"
                             f"<figcaption><span class='fig-label'>{label}</span>"
                             f"{html.escape(caption)}</figcaption></figure>")]
        if name == "controls-index":
            return [("html", CONTROLS_INDEX_TOKEN)]
        if name == "requires":
            # {{requires seq}}: say so when the chapter describes code this build lacks.
            what = args[0] if args else ""
            if what == "seq" and b.seq is None:
                return [("html", "<div class='admonition note'><p class='admonition-title'>Not in this "
                                 "build yet</p><p>The sequencer’s code is still being reviewed and is "
                                 "not part of the build this edition was made from, so the tables "
                                 "generated from it are missing. Where this chapter says <em>On the "
                                 "desktop</em>, it refers to that code under review.</p></div>")]
            if what not in ("seq",):
                b.errors.append(f"{ch.file}: {{{{requires {what}}}}}: unknown requirement")
            return []
        if name == "status-key":
            rows = "".join(
                f"<p><span class='status status-{k}'>{html.escape(label)}</span> {html.escape(title)}.</p>"
                for k, (label, title) in STATUSES.items())
            return [("html", f"<div class='status-key'>{rows}</div>")]
        if name == "build-info":
            return [("html", build_info(b))]
        b.errors.append(f"{ch.file}: unknown directive {{{{{name}}}}}")
        return []

    return directive


def build_info(b: Build) -> str:
    sounds = [e.name for e in b.engines if e.kind == "sound"]
    fx = [e.name for e in b.engines if e.kind == "audio_fx"]
    rows = [
        ("Generated on", b.date),
        ("From commit", f"<a href='{b.cfg['repository']}/commit/{b.commit}'><code>{html.escape(b.commit_short)}</code></a>"
         if b.commit != "unknown" else "unknown"),
        ("Sound engines in the build", html.escape(", ".join(sounds))),
        ("Effects in the build", html.escape(", ".join(fx))),
        ("Sequencer in the build", "yes" if b.seq is not None else "not yet"),
        ("Browser simulator published with it", "yes" if b.sim_dir else "not yet"),
        ("Tools", f"Python-Markdown {markdown.__version__}"),
    ]
    body = "".join(f"<tr><th scope='row'>{k}</th><td>{v}</td></tr>" for k, v in rows)
    return f"<table class='build-info'><caption>This edition</caption><tbody>{body}</tbody></table>"


# ---- conversion -------------------------------------------------------------------------------

def convert(b: Build, ctx: ManualContext, ch: Chapter) -> None:
    ch.state = ChapterState(ch.slug, ch.number, ch.features)
    ctx.chapter = ch.state
    md = markdown.Markdown(
        extensions=["extra", "admonition", "sane_lists", "smarty", "toc", ManualExtension(ctx)],
        extension_configs={"toc": {"permalink": False, "toc_depth": "1-3"},
                           "smarty": {"smart_angled_quotes": False}},
        output_format="html")
    body = md.convert(ch.source)
    h1 = [h for h in ch.state.headings if h.level == 1]
    if len(h1) != 1:
        b.errors.append(f"{ch.file}: needs exactly one '# ' title, has {len(h1)}")
        ch.title = ch.slug
    else:
        ch.title = h1[0].text
    running = f"{ch.number} · {ch.title}" if ch.number else ch.title
    body = re.sub(r"<h1([^>]*)>", lambda m: f'<h1{m.group(1)} data-running="{html.escape(running)}">', body, count=1)
    body = re.sub(r'href="([^":#]+)\.md(#[^"]*)?"', lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"', body)
    body = body.replace("<table", "<div class=\"table-wrap\"><table").replace("</table>", "</table></div>")
    ch.html = body
    if ch.features:
        for h in ch.state.headings:
            if h.level == 2 and not ch.state.statuses.get(h.id):
                b.errors.append(f"{ch.file}: section '{h.text}' says nothing about where it runs; "
                                "add a {{status ...}} line (manual/README.md, \"Honesty\")")


def controls_index(b: Build, vocab: dict[str, list[str]], roles: list[str]) -> str:
    """Every control, with links to the sections that mention it."""
    where: dict[tuple[str, bool], list[tuple[Chapter, object]]] = {}
    for ch in b.chapters:
        if ch.state is None:
            continue
        heads = {h.id: h for h in ch.state.headings}
        for name, role, hid in ch.state.controls:
            h = heads.get(hid)
            if h is None or h.level == 1:
                h = next((x for x in ch.state.headings if x.level == 1), None)
            lst = where.setdefault((name, role), [])
            if all(not (c is ch and x is h) for c, x in lst):
                lst.append((ch, h))
    # Each group's section in the panel tour comes first ([control_home] in manual.toml).
    homes = {}
    for key, target in b.cfg.get("control_home", {}).items():
        slug, _, hid = target.partition("#")
        ch = next((c for c in b.chapters if c.slug == slug and c.state), None)
        h = next((x for x in ch.state.headings if x.id == hid), None) if ch else None
        if h is None:
            b.errors.append(f"manual.toml [control_home] {key} = '{target}' names no section")
        else:
            homes[key] = (ch, h)
    groups = [("Encoders", "encoders"), ("Potentiometer", "potentiometers"), ("Buttons", "buttons"),
              ("Labels under the black keys", "key_labels"), ("Connectors", "connectors")]
    out = []
    for title, key in groups:
        names = vocab.get(key, [])
        if not names:
            continue
        out.append(f"<h2 id='idx-{key}'>{html.escape(title)}</h2><dl class='controls-index'>")
        home = homes.get(key)
        for name in names:
            out.append(f"<dt><kbd class='ctl'>{html.escape(name)}</kbd></dt>")
            refs = list(where.get((name, False), []))
            if home:
                # First, whether or not the text mentions the control there.
                refs = [home] + [(c, h) for c, h in refs if not (c is home[0] and h is home[1])]
            if not refs:
                out.append("<dd>Not described yet.</dd>")
                continue
            items = []
            for i, (ch, h) in enumerate(refs):
                label = (f"{h.number} {h.text}" if h.number else h.text) if h else ch.title
                href = f"{ch.page}#{h.id}" if h else ch.page
                cls = "xref home" if home and i == 0 else "xref"
                items.append(f"<a class='{cls}' href='{href}'>{html.escape(label)}</a>")
            out.append(f"<dd>{'; '.join(items)}</dd>")
        out.append("</dl>")
    if roles:
        out.append("<h2 id='idx-roles'>Sequencer functions without a button yet</h2>"
                   "<p>These functions are planned for the sequencer, and which button or "
                   "combination carries each one is still to be decided.</p><dl class='controls-index'>")
        for name in roles:
            refs = where.get((name, True), [])
            out.append(f"<dt><kbd class='ctl role'>{html.escape(name)}</kbd></dt>")
            items = [f"<a class='xref' href='{ch.page}#{h.id}'>{html.escape(f'{h.number} {h.text}' if h.number else h.text)}</a>"
                     for ch, h in refs if h]
            out.append(f"<dd>{'; '.join(items) or 'Not described yet.'}</dd>")
        out.append("</dl>")
    return "".join(out)


# ---- output -----------------------------------------------------------------------------------

def tmpl(name: str) -> Template:
    return Template((REPO / "manual" / "theme" / name).read_text())


def edition(b: Build) -> str:
    sha = b.commit_short
    link = (f"<a href='{b.cfg['repository']}/commit/{b.commit}'>{html.escape(sha)}</a>"
            if b.commit != "unknown" else "an unknown commit")
    draft = sum(c.state.outlines for c in b.chapters if c.state)
    extra = f" Draft: {draft} sections are still outlines." if draft else ""
    return f"Generated on {b.date} from commit {link}.{extra}"


def sidebar(b: Build, current: Chapter | None) -> str:
    out = []
    for c in b.chapters:
        cur = ' aria-current="page"' if c is current else ""
        num = c.number or ""
        out.append(f'        <li><a href="{c.page}"{cur}><span class="num">{num}</span>'
                   f'<span>{html.escape(c.title)}</span></a></li>')
    return "\n".join(out)


def write_site(b: Build) -> None:
    out = b.out
    assets = out / "assets"
    (assets / "figures").mkdir(parents=True, exist_ok=True)
    theme = b.repo / "manual" / "theme"
    shutil.copy2(theme / "manual.css", assets / "manual.css")
    shutil.copy2(theme / "print.css", assets / "print.css")
    shutil.copy2(theme / "icon.svg", assets / "icon.svg")
    for key, (draw, _caption, _alt) in figures.FIGURES.items():
        (assets / "figures" / f"{key}.svg").write_text(draw() + "\n")
    if b.screens:
        (assets / "screens").mkdir(exist_ok=True)
        for src in sorted(b.screens):
            shutil.copy2(src, assets / "screens" / src.name)
    font_link = ""
    banner_screen = banner_print = None
    if b.branding:
        ttf = b.branding / "fonts" / "Audiowide-Regular.ttf"
        ofl = b.branding / "fonts" / "OFL.txt"
        if ttf.is_file() and ofl.is_file():
            (assets / "fonts").mkdir(exist_ok=True)
            shutil.copy2(ttf, assets / "fonts" / ttf.name)
            shutil.copy2(ofl, assets / "fonts" / "OFL.txt")
            (assets / "fonts.css").write_text(
                "/* Audiowide, (c) 2012 Brian J. Bonislawsky DBA Astigmatic (AOETI), SIL Open Font\n"
                " * License 1.1 with the Reserved Font Name \"Audiowide\" (fonts/OFL.txt). The file is\n"
                " * unmodified, as in assets/branding/fonts/. */\n"
                "@font-face { font-family: \"Audiowide\"; src: url(\"fonts/Audiowide-Regular.ttf\") "
                "format(\"truetype\"); font-weight: 400; font-style: normal; font-display: swap; }\n")
            font_link = '<link rel="stylesheet" href="assets/fonts.css">\n'
        for name in ("banner.svg", "banner.png"):
            if (b.branding / name).is_file():
                shutil.copy2(b.branding / name, assets / name)
        banner_screen = "banner.svg" if (assets / "banner.svg").is_file() else (
            "banner.png" if (assets / "banner.png").is_file() else None)
        banner_print = "banner.png" if (assets / "banner.png").is_file() else banner_screen
    if not font_link:
        b.warnings.append("no branding fonts (assets/branding/fonts/); display lines fall back to the body font")

    common = dict(manual_title=b.cfg["title"], document=b.cfg["document"], commit=b.commit_short,
                  pdf_name=b.cfg["pdf_name"], font_link=font_link, edition=edition(b))
    page = tmpl("page.html")
    for i, c in enumerate(b.chapters):
        prev_c = b.chapters[i - 1] if i else None
        next_c = b.chapters[i + 1] if i + 1 < len(b.chapters) else None
        pager = []
        if prev_c:
            pager.append(f'      <a class="prev" href="{prev_c.page}"><span class="dir">Previous</span>'
                         f'{html.escape(prev_c.title)}</a>')
        if next_c:
            pager.append(f'      <a class="next" href="{next_c.page}"><span class="dir">Next</span>'
                         f'{html.escape(next_c.title)}</a>')
        h2s = [h for h in c.state.headings if h.level == 2]
        onpage = ""
        if h2s:
            onpage = "    <p>On this page</p>\n    <ol>\n" + "\n".join(
                f'      <li><a href="#{h.id}">{html.escape((h.number + " " if h.number else "") + h.text)}</a></li>'
                for h in h2s) + "\n    </ol>"
        desc = c.summary or f"{c.title}: {b.cfg['title']} {b.cfg['document']}"
        (out / c.page).write_text(page.substitute(
            common, title=html.escape(c.title), description=html.escape(desc),
            body_class="backmatter" if c.backmatter else "chapter",
            article_class="chapter backmatter" if c.backmatter else "chapter",
            sidebar=sidebar(b, c), body=c.html, pager="\n".join(pager), onpage=onpage))

    hero = ""
    if banner_screen:
        hero = (f'<div class="cover-hero"><img src="assets/{banner_screen}" width="1280" height="320" '
                f'alt="{html.escape(b.cfg["title"])}: {html.escape(b.cfg["tagline"])}"></div>')
    cards = []
    for c in b.chapters:
        num = c.number or ""
        cards.append(f'    <li><a href="{c.page}"><span class="num">{num}</span>'
                     f'<span class="t">{html.escape(c.title)}</span>'
                     f'<span class="d">{html.escape(c.summary)}</span></a></li>')
    draft_flag = ' <span class="draft-flag">Draft</span>' if any(c.state.outlines for c in b.chapters) else ""
    (out / "index.html").write_text(tmpl("cover.html").substitute(
        common, hero=hero, tagline=html.escape(b.cfg["tagline"]),
        descriptor=html.escape(b.cfg["descriptor"]), descriptor_lc=html.escape(b.cfg["descriptor"][0].lower() + b.cfg["descriptor"][1:]),
        first_chapter=b.chapters[0].page, contents="\n".join(cards), draft_flag=draft_flag))

    # The book: every chapter in one document, ids prefixed per chapter.
    pages = {c.page: c for c in b.chapters}
    parts, toc = [], []
    for c in b.chapters:
        p = c.anchor
        body = c.html

        def fix_href(m, c=c, p=p):
            target = m.group(1)
            if target.startswith("#"):
                return f'href="#{p}-{target[1:]}"'
            page_name, _, frag = target.partition("#")
            if page_name in pages:
                t = pages[page_name]
                return f'href="#{t.anchor}-{frag}"' if frag else f'href="#{t.anchor}"'
            return m.group(0)

        # A figure links to its SVG on the web; in the book the link would point at a file.
        body = re.sub(r"<a href='assets/figures/[^']+'>(<img[^>]*>)</a>", r"\1", body)
        body = re.sub(r'\bid=(["\'])([^"\']+)\1', lambda m: f'id={m.group(1)}{p}-{m.group(2)}{m.group(1)}', body)
        body = re.sub(r'\baria-labelledby=(["\'])([^"\']+)\1',
                      lambda m: "aria-labelledby=" + m.group(1) + " ".join(f"{p}-{x}" for x in m.group(2).split()) + m.group(1), body)
        body = re.sub(r'href="([^"]+)"', fix_href, body)
        body = re.sub(r"href='([^']+)'", lambda m: fix_href(m).replace('"', "'"), body)
        cls = "chapter backmatter" if c.backmatter else "chapter"
        parts.append(f'<article class="{cls}" id="{p}">\n{body}\n</article>')
        num = f'<span class="tn">{c.number}</span>' if c.number else '<span class="tn"></span>'
        toc.append(f'    <li class="l1"><a href="#{p}">{num}{html.escape(c.title)}</a></li>')
        for h in c.state.headings:
            if h.level == 2:
                toc.append(f'    <li class="l2"><a href="#{p}-{h.id}"><span class="tn">{h.number}</span>'
                           f'{html.escape(h.text)}</a></li>')
    cover_banner = (f'  <img class="banner" src="assets/{banner_print}" alt="">' if banner_print else "")
    front = front_matter(b)
    (out / "print.html").write_text(tmpl("book.html").substitute(
        common, tagline=html.escape(b.cfg["tagline"]), descriptor=html.escape(b.cfg["descriptor"]),
        date=b.date, edition_short=f"generated {b.date} from {b.commit_short}",
        paper=b.cfg.get("paper", "A5"), cover_banner=cover_banner, draft_flag=draft_flag,
        front=front, toc="\n".join(toc), chapters="\n".join(parts)))

    (out / "reference.json").write_text(json.dumps({
        "generated": b.date, "commit": b.commit,
        "engines": [{"id": e.id, "name": e.name, "kind": e.kind, "voices": e.max_voices,
                     "credits": e.credits,
                     "params": [{"name": p.name, "list": p.is_list, "min": p.min, "max": p.max,
                                 "default": p.default, "page": p.page + 1, "names": p.names}
                                for p in e.params]} for e in b.engines]}, indent=1) + "\n")


def front_matter(b: Build) -> str:
    t = html.escape(b.cfg["title"])
    keys = "".join(f"<p><span class='status status-{k}'>{html.escape(label)}</span> {html.escape(title)}.</p>"
                   for k, (label, title) in STATUSES.items())
    return (
        f"<h1 style='bookmark-level: 1'>About this manual</h1>"
        f"<p>This manual describes {t}, {html.escape(b.cfg['descriptor'][0].lower() + b.cfg['descriptor'][1:])}. "
        "It is generated from the project’s sources: the reference tables come from the code that "
        "the firmware is built from, so they change when the code does.</p>"
        "<p><strong>Nothing in it runs on an FM-1 yet.</strong> Every function carries a status that "
        "says where it works today:</p>"
        f"<div class='status-key'>{keys}</div>"
        "<p>Chapter 1 explains why nothing is offered for the device until it can be restored "
        "safely, and chapter 2 shows how to play the simulator in a browser.</p>"
        f"<p class='edition'>{edition(b)} The newest edition is online at "
        f"<a href='{b.cfg['site_url']}manual/'>{html.escape(b.cfg['site_url'])}manual/</a>.</p>"
        "<h2>Trademarks and licences</h2>"
        f"<p>{t} is an independent project. It is not made, endorsed or supported by M-VAVE or Cuvave; "
        "“FM-1” names the instrument the firmware is written for. Mutable Instruments module names "
        "identify where code came from; they are not product names here. Chapter 13 credits every "
        "source and licence.</p>"
        f"<p>The manual and the firmware’s own code are under the MIT licence. Set in IBM Plex Sans and "
        "Audiowide (SIL Open Font License 1.1). Colours: Rosé Pine Dawn (MIT).</p>")


def link_simulator_to_manual(b: Build, page: Path) -> None:
    """The published simulator page links to the manual beside it. Only the
    copy in the site is changed: sim/web/www has no manual/ folder, so its own
    page must not link there. Warns, and leaves the page alone, if the page's
    markup no longer has the two places the links go."""
    text = page.read_text()
    lede = re.search(r'(<p class="lede">.*?)(</p>)', text, re.S)
    help_dl = text.rfind("</dl>")
    if not lede or help_dl < 0:
        b.warnings.append("sim/web/www/index.html: no lede or help list to link the manual from")
        return
    pdf = html.escape(b.cfg["pdf_name"])
    row = (f'      <div><dt>Manual</dt><dd>The <a href="manual/">user manual</a> describes every control, '
           f'engine and effect; also as a <a href="manual/{pdf}">PDF</a>.</dd></div>\n    ')
    text = text[:help_dl] + row + text[help_dl:]
    text = (text[:lede.start()] + lede.group(1).rstrip()
            + ' Read the <a href="manual/">user manual</a>.' + lede.group(2) + text[lede.end():])
    page.write_text(text)


def assemble_site(b: Build, site: Path) -> None:
    sim = b.repo / "sim" / "web" / "www"
    if (sim / "index.html").is_file():
        for item in sim.iterdir():
            if item.name.startswith(".") or item.name == "manual":
                continue
            dest = site / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
        link_simulator_to_manual(b, site / "index.html")
        print(f"manual: simulator from {sim.relative_to(b.repo)} is the site's front page", file=sys.stderr)
    else:
        font_link = ('<link rel="stylesheet" href="manual/assets/fonts.css">\n'
                     if (b.out / "assets" / "fonts.css").is_file() else "")
        banner = next((n for n in ("banner.svg", "banner.png") if (b.out / "assets" / n).is_file()), None)
        hero = (f'<div class="cover-hero"><img src="manual/assets/{banner}" width="1280" height="320" '
                f'alt="{html.escape(b.cfg["title"])}: {html.escape(b.cfg["tagline"])}"></div>') if banner else ""
        (site / "index.html").write_text(tmpl("landing.html").substitute(
            manual_title=b.cfg["title"], tagline=html.escape(b.cfg["tagline"]),
            descriptor=html.escape(b.cfg["descriptor"]),
            descriptor_lc=html.escape(b.cfg["descriptor"][0].lower() + b.cfg["descriptor"][1:]),
            font_link=font_link, hero=hero, pdf_name=b.cfg["pdf_name"], repository=b.cfg["repository"],
            edition=edition(b)))
        print("manual: no sim/web/www; the site's front page links to the manual", file=sys.stderr)


# ---- checks -------------------------------------------------------------------------------------

def check_links(b: Build) -> None:
    ids: dict[str, set[str]] = {}
    for f in b.out.glob("*.html"):
        ids[f.name] = set(re.findall(r'\bid=["\']([^"\']+)["\']', f.read_text()))
    for f in sorted(b.out.glob("*.html")):
        text = f.read_text()
        for target in re.findall(r'\b(?:href|src)=["\']([^"\']+)["\']', text):
            if re.match(r"^[a-z]+:", target) or target.startswith("../") or target == b.cfg["pdf_name"]:
                continue
            page, _, frag = target.partition("#")
            page = page or f.name
            if page.startswith("assets/"):
                if not (b.out / page).is_file():
                    b.errors.append(f"{f.name}: missing file {target}")
                continue
            if page not in ids:
                b.errors.append(f"{f.name}: link to a page that does not exist: {target}")
            elif frag and frag not in ids[page]:
                b.errors.append(f"{f.name}: link to a missing anchor: {target}")


def check_words(b: Build) -> None:
    files = [(c.file, c.source) for c in b.chapters]
    files += [(p.name, p.read_text()) for p in b.out.glob("*.html")]
    for name, text in files:
        for word, why in policy.problems(text):
            b.errors.append(f"{name}: '{word}' is {why} (tools/manual/policy.py)")
    # Python-Markdown's stash placeholders must never reach a page: one did,
    # in the index of controls, for a heading with an apostrophe.
    for p in b.out.glob("*.html"):
        if re.search(r"wzxhzdk|[\x02\x03]", p.read_text()):
            b.errors.append(f"{p.name}: an unresolved Markdown placeholder (wzxhzdk) in the output")


def make_pdf(b: Build) -> Path:
    try:
        import weasyprint
    except (ImportError, OSError) as err:
        raise SystemExit(
            "manual: the PDF needs WeasyPrint and Pango (manual/requirements.txt).\n"
            f"  {err.__class__.__name__}: {str(err).splitlines()[0] if str(err) else ''}\n"
            "  macOS: brew install pango, or run tools/manual/build-in-docker.sh") from None
    target = b.out / b.cfg["pdf_name"]
    print(f"manual: WeasyPrint {weasyprint.__version__} -> {target.name}", file=sys.stderr)
    doc = weasyprint.HTML(filename=str(b.out / "print.html")).render()
    doc.metadata.title = f"{b.cfg['title']} {b.cfg['document']}"
    doc.metadata.authors = [f"The {b.cfg['title']} project"]
    doc.metadata.description = f"{b.cfg['descriptor']}. Generated {b.date} from {b.commit_short}."
    doc.metadata.keywords = ["M-VAVE FM-1", "firmware", "synthesizer", "user manual"]
    doc.write_pdf(str(target))
    print(f"manual: {len(doc.pages)} pages, {target.stat().st_size // 1024} KB", file=sys.stderr)
    return target


def report(b: Build) -> None:
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    for w in b.warnings:
        print(f"::warning title=manual::{w}" if gha else f"manual: warning: {w}", file=sys.stderr)
    for e in b.errors:
        print(f"::error title=manual::{e}" if gha else f"manual: error: {e}", file=sys.stderr)


def serve(root: Path, port: int) -> None:
    import functools
    import http.server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"manual: serving {root} on http://localhost:{port}/ (Ctrl-C stops)", file=sys.stderr)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


# ---- main ----------------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", type=Path, default=Path("_site"),
                    help="site root (default _site); the manual goes to SITE/manual")
    ap.add_argument("--only-manual", action="store_true",
                    help="write the manual only, without the site's front page")
    ap.add_argument("--pdf", action="store_true", help="also make the PDF (WeasyPrint)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any error (CI)")
    ap.add_argument("--renderer", help="an fm1-render binary to read (skips make)")
    ap.add_argument("--list-json", help="read engines from this JSON instead of fm1-render --list")
    ap.add_argument("--no-make", action="store_true", help="do not run make -C engines first")
    ap.add_argument("--branding", type=Path, help="branding directory (default assets/branding)")
    ap.add_argument("--repo", type=Path, default=REPO, help=argparse.SUPPRESS)
    ap.add_argument("--serve", action="store_true", help="after building, serve the site locally")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)

    repo = args.repo.resolve()
    cfg = tomllib.loads((repo / "manual" / "manual.toml").read_text())
    site = args.site if args.site.is_absolute() else Path.cwd() / args.site
    out = site / "manual"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    engines = load_engines(args, repo)
    seq_tool = repo / "engines" / "build" / "fm1-seq"
    seq = reference.load_seq(repo, seq_tool)
    branding = args.branding or repo / "assets" / "branding"
    sha, short = commit_info(repo)
    b = Build(cfg=cfg, repo=repo, out=out, commit=sha, commit_short=short, date=build_date(),
              engines=engines, seq=seq, branding=branding if branding.is_dir() else None)
    sim = repo / "sim" / "web" / "www"
    b.sim_dir = sim if (sim / "index.html").is_file() and not args.only_manual else None
    for e in engines:
        b.warnings.extend(reference.check_engine(e))
    if seq is None:
        b.warnings.append("no engines/include/fm1_seq.h: the sequencer tables are skipped")

    n = 0
    for entry in cfg.get("chapter", []):
        n += 1
        f = entry["file"]
        b.chapters.append(Chapter(f, Path(f).stem, str(n), bool(entry.get("features")),
                                  entry.get("summary", ""), False))
    for entry in cfg.get("backmatter", []):
        f = entry["file"]
        b.chapters.append(Chapter(f, Path(f).stem, None, bool(entry.get("features")),
                                  entry.get("summary", ""), True))
    for ch in b.chapters:
        ch.source = (repo / "manual" / "chapters" / ch.file).read_text()

    prescan(b)
    controls = cfg.get("controls", {})
    vocab = {k: v for k, v in controls.items() if k != "roles"}
    ctx = ManualContext(vocab, controls.get("roles", []), make_directive(b))
    for ch in b.chapters:
        convert(b, ctx, ch)
    b.errors.extend(ctx.errors)
    b.warnings.extend(ctx.warnings)
    index_html = controls_index(b, vocab, controls.get("roles", []))
    for ch in b.chapters:
        ch.html = ch.html.replace(f"<p>{CONTROLS_INDEX_TOKEN}</p>", index_html).replace(CONTROLS_INDEX_TOKEN, index_html)

    write_site(b)
    if not args.only_manual:
        assemble_site(b, site)
    check_links(b)
    check_words(b)
    if args.pdf and not (args.strict and b.errors):
        make_pdf(b)
    report(b)
    outlines = sum(c.state.outlines for c in b.chapters)
    print(f"manual: {len(b.chapters)} chapters, {len(b.engines)} engines and effects, "
          f"sequencer {'in' if seq else 'not in'} the build, {outlines} outline boxes; "
          f"{len(b.errors)} errors, {len(b.warnings)} warnings -> {out}", file=sys.stderr)
    if args.strict and b.errors:
        return 1
    if args.serve:
        serve(site, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
