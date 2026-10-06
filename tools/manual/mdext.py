"""Markdown additions for the Lunar Modulator manual (manual/README.md).

    [[SELECT]]              a printed control, indexed in the index of controls
    [[role:SHIFT]]          a sequencer role not yet given a button (docs/13 §4)
    {{status sim desktop}}  where a function runs today: sim, desktop, planned
    {{name args}}           on a line of its own: generated content (build.py)

Headings are numbered (5, 5.1, 5.1.1), and the build learns from the tree
which sections mention which controls and which carry a status. Python-Markdown
3.x; MIT licence, like the rest of this repository.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as etree
from dataclasses import dataclass, field

from markdown.extensions import Extension
from markdown.extensions.toc import stashedHTML2text, unescape
from markdown.inlinepatterns import InlineProcessor
from markdown.preprocessors import Preprocessor
from markdown.treeprocessors import Treeprocessor

STATUSES = {
    "sim": ("In the simulator", "Works today in the browser simulator"),
    "desktop": ("On the desktop", "Works today in the desktop tools (fm1-render, fm1-seq)"),
    "planned": ("Planned for the device", "Designed; not built for the FM-1 yet"),
}

DIRECTIVE_RE = re.compile(r"^\{\{([a-z][a-z0-9-]*)(?:[ \t]+([^}]*?))?[ \t]*\}\}[ \t]*$")
CONTROL_RE = r"\[\[(role:)?([A-Z0-9][A-Z0-9 +/\-]*?)\]\]"
STATUS_RE = r"\{\{status((?:[ \t]+[a-z]+)+)[ \t]*\}\}"


@dataclass
class Heading:
    level: int
    id: str
    number: str
    text: str


@dataclass
class ChapterState:
    """What one chapter's conversion learned (filled by the tree processor)."""
    slug: str
    number: str | None          # "5", or None for back matter
    headings: list[Heading] = field(default_factory=list)
    controls: list[tuple[str, bool, str]] = field(default_factory=list)  # name, role, heading id
    statuses: dict[str, set[str]] = field(default_factory=dict)          # h2 id -> statuses
    outlines: int = 0


class ManualContext:
    """Shared by every chapter of one build: the control vocabulary, the
    directive renderer and the problems found."""

    def __init__(self, vocabulary: dict[str, list[str]], roles: list[str], directive):
        self.vocabulary = {name: group for group, names in vocabulary.items() for name in names}
        self.roles = set(roles)
        self.directive = directive          # (name, args, chapter) -> list of str | ("html", str)
        self.errors: list[str] = []
        self.chapter: ChapterState | None = None


class DirectivePreprocessor(Preprocessor):
    """Replaces `{{name args}}` lines. Runs after fenced_code (priority 25), so
    code blocks are already stashed and never expanded."""

    def __init__(self, md, ctx: ManualContext):
        super().__init__(md)
        self.ctx = ctx

    def run(self, lines):
        out = []
        for line in lines:
            m = DIRECTIVE_RE.match(line)
            if not m or m.group(1) == "status":
                out.append(line)
                continue
            parts = self.ctx.directive(m.group(1), (m.group(2) or "").split(), self.ctx.chapter)
            for part in parts:
                if isinstance(part, tuple):            # ("html", markup): stash as one block
                    out.extend(["", self.md.htmlStash.store(part[1]), ""])
                else:
                    out.append(part)
        return out


class ControlPattern(InlineProcessor):
    def __init__(self, pattern, md, ctx: ManualContext):
        super().__init__(pattern, md)
        self.ctx = ctx

    def handleMatch(self, m, data):
        role, name = bool(m.group(1)), m.group(2).strip()
        el = etree.Element("kbd")
        el.text = name
        if role:
            el.set("class", "ctl role")
            el.set("title", "A sequencer function still to be given a button")
            if name not in self.ctx.roles:
                self.ctx.errors.append(f"unknown role [[role:{name}]] in {self.ctx.chapter.slug}")
        else:
            el.set("class", "ctl")
            if name not in self.ctx.vocabulary:
                self.ctx.errors.append(f"unknown control [[{name}]] in {self.ctx.chapter.slug} "
                                       "(manual.toml [controls])")
        el.set("data-ctl", ("role:" if role else "") + name)
        return el, m.start(0), m.end(0)


class StatusPattern(InlineProcessor):
    def __init__(self, pattern, md, ctx: ManualContext):
        super().__init__(pattern, md)
        self.ctx = ctx

    def handleMatch(self, m, data):
        keys = m.group(1).split()
        wrap = etree.Element("span", {"class": "status-line"})
        lead = etree.SubElement(wrap, "span", {"class": "status-lead"})
        lead.text = "Status:"
        seen = []
        for key in keys:
            if key not in STATUSES:
                self.ctx.errors.append(f"unknown status '{key}' in {self.ctx.chapter.slug}; "
                                       f"use {', '.join(STATUSES)}")
                continue
            if key in seen:
                continue
            seen.append(key)
            label, title = STATUSES[key]
            badge = etree.SubElement(wrap, "span", {
                "class": f"status status-{key}", "title": title, "data-status": key})
            badge.text = label
        return wrap, m.start(0), m.end(0)


class StructureProcessor(Treeprocessor):
    """Numbers h1-h3 and records headings, control mentions, statuses and
    outline boxes. Runs after toc (priority 5) has given headings their ids."""

    def __init__(self, md, ctx: ManualContext):
        super().__init__(md)
        self.ctx = ctx

    def run(self, root):
        ch = self.ctx.chapter
        counters = [0, 0, 0]
        current = None        # the heading id controls are filed under
        current_h2 = None
        for el in root.iter():
            tag = el.tag
            if tag in ("h1", "h2", "h3"):
                level = int(tag[1])
                if level == 1:
                    number = ch.number or ""
                elif ch.number:
                    counters[level - 1] += 1
                    for k in range(level, 3):
                        counters[k] = 0
                    number = ".".join([ch.number] + [str(c) for c in counters[1:level]])
                else:
                    number = ""
                # Smart quotes and other entities sit in the HTML stash as
                # placeholders until the page is serialised: resolve them, as
                # toc does, so "The sound's page" is not "The soundwzxhzdk:10s page".
                raw = stashedHTML2text(unescape("".join(el.itertext())), self.md,
                                       strip_entities=False)
                text = html.unescape(raw).strip()
                hid = el.get("id", "")
                if number:
                    span = etree.Element("span", {"class": "secno"})
                    span.text = number
                    span.tail = " " + (el.text or "")
                    el.text = None
                    el.insert(0, span)
                ch.headings.append(Heading(level, hid, number, text))
                current = hid
                if level == 2:
                    current_h2 = hid
                    ch.statuses.setdefault(hid, set())
                elif level == 1:
                    current_h2 = None
            elif tag == "kbd" and "ctl" in (el.get("class") or ""):
                ctl = el.get("data-ctl", "")
                role = ctl.startswith("role:")
                ch.controls.append((ctl[5:] if role else ctl, role, current or ""))
            elif tag == "span" and el.get("data-status"):
                if current_h2 is not None:
                    ch.statuses[current_h2].add(el.get("data-status"))
            elif tag == "div" and "admonition" in (el.get("class") or "").split() \
                    and "outline" in (el.get("class") or "").split():
                ch.outlines += 1
        return None


class ManualExtension(Extension):
    def __init__(self, ctx: ManualContext, **kwargs):
        self.ctx = ctx
        super().__init__(**kwargs)

    def extendMarkdown(self, md):
        md.preprocessors.register(DirectivePreprocessor(md, self.ctx), "manual_directives", 20)
        md.inlinePatterns.register(ControlPattern(CONTROL_RE, md, self.ctx), "manual_control", 175)
        md.inlinePatterns.register(StatusPattern(STATUS_RE, md, self.ctx), "manual_status", 176)
        md.treeprocessors.register(StructureProcessor(md, self.ctx), "manual_structure", 4)
