#!/usr/bin/env python3
"""Write engines/state/fm1_known.c from engines/known-ids.json and
engines/aliases.json: the ids a build may lack, with the reason a load
gives (notes/2026-10-06-state-files.md §9), and the names parameters and
list entries had before a rename. C reads them (the metadata export, and
the state reader's name tables in stage E3); the JSON files are what people
edit.

    python3 tools/gen_known.py          # write the C file
    python3 tools/gen_known.py --check  # exit 1 if it is not what this writes

tests/test_engine_names.py runs --check. MIT licence.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWN = ROOT / "engines" / "known-ids.json"
ALIASES = ROOT / "engines" / "aliases.json"
OUT = ROOT / "engines" / "state" / "fm1_known.c"


def c_string(s):
    out = ['"']
    for ch in s:
        if ch in '"\\':
            out.append("\\" + ch)
        elif 32 <= ord(ch) < 127:
            out.append(ch)
        else:
            raise ValueError(f"not printable ASCII: {s!r}")
    out.append('"')
    return "".join(out)


def generate():
    known = json.loads(KNOWN.read_text())["ids"]
    aliases = json.loads(ALIASES.read_text())
    lines = [
        "/* fm1_known.c -- written by tools/gen_known.py from engines/known-ids.json",
        " * and engines/aliases.json; do not edit (fm1_known.h). MIT licence. */",
        '#include "fm1_known.h"',
        "",
        "#include <string.h>",
        "",
        "const fm1_known_id_t fm1_known_ids[] = {",
    ]
    for k in known:
        since = c_string(k["since"]) if k.get("since") else "NULL"
        lines.append(f"  {{ {c_string(k['id'])}, {c_string(k['what'])}, {c_string(k['reason'])}, {since} }},")
    lines += ["  { NULL, NULL, NULL, NULL }", "};",
              f"const size_t fm1_known_id_count = {len(known)}u;", "",
              "const fm1_alias_t fm1_aliases[] = {"]
    rows = []
    for a in aliases["params"]:
        owner = "FM1_ALIAS_ENGINE" if "engine" in a else "FM1_ALIAS_MOD"
        rows.append((owner, a.get("engine", a.get("kind")), a["uid"], -1, a["alias"]))
    for a in aliases["entries"]:
        owner = "FM1_ALIAS_ENGINE" if "engine" in a else "FM1_ALIAS_MOD"
        rows.append((owner, a.get("engine", a.get("kind")), a["uid"], a["index"], a["alias"]))
    for a in aliases.get("retired", []):
        owner = "FM1_ALIAS_ENGINE" if "engine" in a else "FM1_ALIAS_MOD"
        rows.append((owner, a.get("engine", a.get("kind")), a["uid"], -2, a["name"]))
    for owner, oid, uid, entry, name in rows:
        lines.append(f"  {{ {owner}, {c_string(oid)}, {uid}u, {entry}, {c_string(name)} }},")
    lines += ["  { 0, NULL, 0u, 0, NULL }", "};", f"const size_t fm1_alias_count = {len(rows)}u;", "",
              "const fm1_known_id_t *fm1_known_id_find(const char *id) {",
              "  size_t i;",
              "  for (i = 0; id && i < fm1_known_id_count; ++i) {",
              "    if (strcmp(fm1_known_ids[i].id, id) == 0) return &fm1_known_ids[i];",
              "  }",
              "  return NULL;",
              "}", ""]
    return "\n".join(lines)


def main(argv):
    text = generate()
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"{OUT.relative_to(ROOT)} is stale: run tools/gen_known.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
