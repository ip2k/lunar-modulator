"""The build-time module list (FM1_MODULES; engines/modules/catalogue.mk;
DEVELOPERS.md, "Choosing the modules").

A build can have only chosen sound engines, effects, MIDI effects and
modulation kinds. This file checks:

- the list's forms (`all`, a list file by name or path, ids with commas)
  and its refusals (an unknown id, a list without a sound engine), and that
  the GPL switch comes first (a GPL id in a list is dropped with it off);
- `engines/modules/default.list`, the proposed FM-1 list, names only
  modules the catalogue has, and every module it leaves out is one the
  catalogue lists;
- each module's objects (FM1_OBJ.<id>) are what it needs: no object of the
  core (everything no module owns) refers to a module's object except the
  three registries through a module's entry, and a module's objects refer
  to no other module's object they do not list (read from the objects'
  symbols, nm);
- a reduced build (sim/web/build/native-mods) lists exactly its modules in
  fm1-render --list, --list-mod and the virtual FM-1's catalogue; says so
  in --build-info and the metadata export (build.modules, the left-out
  modules as known ids with the reason `list`, and its own meta_id); refuses
  a file naming a left-out module with that reason; and links no symbol
  that only a left-out module's objects define.
"""
import json
import os
import re
import subprocess

import pytest

from tests.engine_helpers import ENGINES, GPL_MODS, ROOT, renderer  # noqa: F401

SIM = ROOT / "sim" / "web"
LIST = ["shapes", "plate", "echo", "arp", "lfo", "env"]
# Every make here says its list; none takes one from the environment.
ENV = {k: v for k, v in os.environ.items() if k != "FM1_MODULES"}
ENV["FM1_GPL_MODS"] = str(int(GPL_MODS))


def make(*args, build=None, check=True):
    cmd = ["make", "-s", "-C", str(ENGINES), "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"),
           "-f", str(ROOT / "tools" / "jieli" / "objects.mk"), f"SIM={SIM}"]
    if build:
        cmd.append(f"BUILD={build}")
    return subprocess.run(cmd + list(args), capture_output=True, text=True, check=check, env=ENV)


def modules(*args, build=None):
    """print-modules: {id: (kind, chosen, [objects])}, and the list's name."""
    out, name = {}, None
    for line in make("print-modules", *args, build=build).stdout.splitlines():
        w = line.split()
        if w[0] == "list":
            name = w[1]
        else:
            out[w[0]] = (w[1], w[2] == "1", w[3:])
    return out, name


def call(tool, *args):
    return subprocess.run([str(tool), *args], check=True, capture_output=True, text=True).stdout


# ---- The list's forms and refusals -----------------------------------------------------------

def test_every_module_by_default():
    mods, name = modules()
    assert name == "all" and mods and all(chosen for _, chosen, _ in mods.values())
    kinds = {k for k, _, _ in mods.values()}
    assert kinds == {"sound", "audio_fx", "midi_fx", "mod"}


def test_ids_with_commas_and_a_list_file(tmp_path):
    mods, name = modules("FM1_MODULES=" + ",".join(LIST))
    assert name == "custom" and {m for m, (_, c, _) in mods.items() if c} == set(LIST)
    f = tmp_path / "small.list"
    f.write_text("# a comment\nshapes plate   # and another\narp\n")
    mods, name = modules(f"FM1_MODULES={f}")
    assert name == "small" and {m for m, (_, c, _) in mods.items() if c} == {"shapes", "plate", "arp"}


@pytest.mark.parametrize("spec,words", [("shapes,nope", 'no module "nope"'),
                                        ("plate,arp", "has no sound engine"),
                                        ("missing.list", 'no list file "missing.list"')])
def test_a_bad_list_is_refused(spec, words):
    res = make("print-modules", f"FM1_MODULES={spec}", check=False)
    assert res.returncode != 0 and words in res.stderr, res.stderr


def test_the_gpl_switch_comes_first():
    mods, _ = modules("FM1_GPL_MODS=0", "FM1_MODULES=shapes,comet,acid-gen")
    assert {m for m, (_, c, _) in mods.items() if c} == {"shapes"}
    assert "comet" not in mods and "acid-gen" not in mods


def test_the_default_list_names_catalogue_modules():
    """engines/modules/default.list, the FM-1's proposed list (DEVELOPERS.md,
    "Choosing the modules"): every id is in the catalogue, it has a sound
    engine, and what it leaves out is named in its comments."""
    text = (ENGINES / "modules" / "default.list").read_text()
    ids = re.sub(r"#.*", "", text).split()
    full, _ = modules()
    assert ids and len(set(ids)) == len(ids) and set(ids) <= set(full)
    mods, name = modules("FM1_MODULES=default")
    assert name == "default"
    chosen = {m for m, (_, c, _) in mods.items() if c}
    assert chosen == set(ids) & set(full) and any(mods[m][0] == "sound" for m in chosen)
    for m in set(full) - set(ids):
        assert re.search(rf"\b{re.escape(m)}\b", text), f"{m} is left out without a word in default.list"


# ---- Each module's objects are what it needs ----------------------------------------------------

def nm_symbols(path):
    """(defined globals, undefined) of an object file, names as nm prints them."""
    res = subprocess.run(["nm", str(path)], check=True, capture_output=True, text=True)
    d, u = set(), set()
    for line in res.stdout.splitlines():
        p = line.split()
        if len(p) == 2 and p[0] == "U":
            u.add(p[1])
        elif len(p) == 3 and p[1] in "TDSBRCVWI":
            d.add(p[2])
    return d, u


@pytest.fixture(scope="module")
def graph():
    """Every object the JieLi check compiles (tools/jieli/objects.mk), built
    natively in sim/web/build/native, with its symbols."""
    build = SIM / "build" / "native"
    objs = make("print-objs", build=build).stdout.split()
    make("-j8", *objs, build=build)
    syms = {o: nm_symbols(o) for o in objs}
    owner = {}
    for o, (d, _) in syms.items():
        for s in d:
            owner[s] = o
    edges = {o: {owner[s] for s in u if s in owner} for o, (_, u) in syms.items()}
    mods, _ = modules(build=build)
    owned = {m: {str(build / x) for x in objs_} for m, (_, _, objs_) in mods.items()}
    return {"objs": set(objs), "edges": edges, "owned": owned, "build": build}


def test_the_core_needs_no_modules_object(graph):
    """Leaving a module out drops its objects: nothing but the registries
    may refer to them (the app layer reaches FM6's bank and the Resonator's
    readout only under FM1_WITH_DX7 and FM1_WITH_RESONATOR)."""
    all_owned = set().union(*graph["owned"].values())
    assert all_owned <= graph["objs"]
    registries = {o for o in graph["objs"] if o.endswith(("/our/src/registry.o", "/midi_fx/registry.o",
                                                          "/mod/mod/mod_registry.o"))}
    assert len(registries) == 3
    # The two references the app layer makes under FM1_WITH_DX7 and
    # FM1_WITH_RESONATOR (the reduced build below links without them).
    guarded = {("sim/src/fm1_app.o", "our/src/msfa_dx7.o"), ("sim/src/fm1_mod_ui.o", "mod/mod/kinds/mod_resonator.o")}
    b = str(graph["build"]) + "/"
    for o in graph["objs"] - all_owned - registries:
        bad = {x for x in graph["edges"][o] & all_owned if (o[len(b):], x[len(b):]) not in guarded}
        assert not bad, f"{o} (core) needs {sorted(bad)}"


def test_each_modules_objects_are_complete(graph):
    """A module's objects refer to no module-owned object they do not list,
    so the module links with its own objects and the core alone."""
    all_owned = set().union(*graph["owned"].values())
    for m, objs in graph["owned"].items():
        for o in objs:
            missing = (graph["edges"][o] & all_owned) - objs
            assert not missing, f"{m}: {o} needs {sorted(missing)}"


# ---- A reduced build -------------------------------------------------------------------------

@pytest.fixture(scope="module")
def small():
    out = SIM / "build" / "native-mods"
    targets = [out / "fm1-render", out / "fm1-sim-render"]
    res = subprocess.run(["make", "-C", str(ENGINES), "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"),
                          f"SIM={SIM}", f"BUILD={out}", "FM1_MODULES=" + ",".join(LIST), "-j8",
                          *map(str, targets)], env=ENV, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-3000:]
    return {"dir": out, "render": targets[0], "sim": targets[1]}


def test_a_reduced_build_lists_only_its_modules(small):
    ids = [e["id"] for e in json.loads(call(small["render"], "--list"))]
    assert ids == ["shapes", "plate", "echo", "arp"]
    assert [e["id"] for e in json.loads(call(small["sim"], "--list"))] == ids
    kinds = [k["id"] for k in json.loads(call(small["render"], "--list-mod"))["kinds"]]
    assert kinds == ["lfo", "env"]
    info = json.loads(call(small["render"], "--build-info"))
    full, _ = modules()
    assert info["modules"] == "custom" and info["engines"] == 3 and info["midi_fx"] == 1
    assert info["mod_kinds"] == 2 and info["left_out"] == len(full) - len(LIST)


def test_a_reduced_build_names_what_it_left_out(small, renderer):  # noqa: F811
    meta = json.loads(call(small["render"], "--meta"))
    full_meta = json.loads(call(renderer, "--meta"))
    assert meta["build"]["modules"] == "custom" and full_meta["build"]["modules"] == "all"
    full, _ = modules()
    left = {k["id"]: k for k in meta["known_ids"] if k["reason"] == "list"}
    assert set(left) == set(full) - set(LIST)
    assert all(k["what"] == full[i][0] for i, k in left.items())
    assert not {e["id"] for e in meta["engines"]} & set(left)
    assert meta["meta_id"] != full_meta["meta_id"]
    assert {"reason": "list", "words": "left out of this build"} in meta["refusals"]["known"]


def test_a_file_naming_a_left_out_module_is_refused_with_its_reason(small, tmp_path):
    f = tmp_path / "m.sound.lunar"
    f.write_text(json.dumps({"lunar": "1.0", "kind": "sound", "made": {"by": "hand"},
                             "sound": {"engine": "macro", "params": {}}}))
    res = subprocess.run([str(small["render"]), "--load", str(f), "--seconds", "0.1",
                          "--out", str(tmp_path / "o.wav")], capture_output=True, text=True)
    assert res.returncode != 0
    assert "left out of this build" in res.stderr, res.stderr


def test_a_reduced_build_links_none_of_a_left_out_modules_code(small, graph):
    """No symbol defined only by the objects of the modules left out is in
    the reduced programs."""
    left = set(graph["owned"]) - set(LIST)
    keep = set().union(*(graph["owned"][m] for m in LIST if m in graph["owned"]))
    dropped = set().union(*(graph["owned"][m] for m in left)) - keep
    assert dropped
    syms = set()
    for o in dropped:
        syms |= nm_symbols(o)[0]
    have = nm_symbols(small["render"])[0] | nm_symbols(small["sim"])[0]
    assert not syms & have, sorted(syms & have)[:20]
