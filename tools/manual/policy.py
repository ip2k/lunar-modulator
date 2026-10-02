"""Words that must never reach the published manual. Standard library only,
so the tests can use it without the manual's dependencies. MIT licence.

The patterns are generic on purpose: no machine or person is named in the
repository. To also refuse names of your own machines and accounts, list them
in the environment, comma-separated, where only your shell sees them:

    export MANUAL_PRIVATE_WORDS="hostname1,hostname2,username"
"""
from __future__ import annotations

import os
import re

FORBIDDEN = [
    (re.compile(r"\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
     "a private network address"),
    (re.compile(r"(?:/Users|/home)/[A-Za-z_][\w.-]*"), "a home directory path"),
    (re.compile(r"\b[a-z_][\w.-]*@(?:\d{1,3}\.){3}\d{1,3}\b|\bssh\s+[a-z_][\w.-]*@"), "a login to a machine"),
    (re.compile(r"\b[\w-]+\.(?:lan|localdomain)\b"), "a local network host name"),
    # The branding rules (CLAUDE.md, "The name"): no space agency's names or
    # marks, and never "Lunar Module" or "Lunar Mod".
    (re.compile(r"\bNASA\b"), "an agency name the branding rules forbid"),
    (re.compile(r"\bLunar Mod(?:ule)?\b"), "a forbidden short form of the name"),
]


def rules():
    """FORBIDDEN plus the words in MANUAL_PRIVATE_WORDS, if set."""
    extra = [w.strip() for w in os.environ.get("MANUAL_PRIVATE_WORDS", "").split(",") if w.strip()]
    out = list(FORBIDDEN)
    if extra:
        out.append((re.compile(r"\b(?:" + "|".join(re.escape(w) for w in extra) + r")\b", re.I),
                    "a private name (MANUAL_PRIVATE_WORDS)"))
    return out


def problems(text: str) -> list[tuple[str, str]]:
    """(match, why) for every rule the text breaks."""
    return [(m.group(0), why) for rx, why in rules() for m in [rx.search(text)] if m]
