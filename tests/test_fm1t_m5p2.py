"""tools/fm1-transporter/fm1t_m5p2.py: the m5-plan-2 host tool, against the same
scripted fake of the FM-1 Transporter data port that tests/test_fm1t_m5.py uses
(after src/transporter_proto.c at kurogedelic FM-1-transporter 80c5012). No
serial port is opened by any test.

fm1t_m5p2.py is a copy of fm1t_m5.py with two pinned runs and a breadcrumb read
added. The code the two share is covered by tests/test_fm1t_m5.py;
test_only_the_pinned_lines_differ below fails if any other line changes, so
that coverage carries over. The tests here cover what differs: the two images
and their chunks, the per-run locks and their order, the bounds, and `crumbs`."""
import ast
import copy
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'fm1-transporter' / 'fm1t_m5p2.py'
M5_TOOL = ROOT / 'tools' / 'fm1-transporter' / 'fm1t_m5.py'
M5_TOOL_SHA256 = '9673ccd83622a208644ae2b467a1fa5964b01807d2639b3d409537d5136c1a72'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


t = _load('fm1t_m5p2', TOOL)
m5 = _load('fm1t_m5_for_m5p2_tests', M5_TOOL)
# The fake and its helpers, not its fixtures (those patch the M5 module only).
harness = _load('test_fm1t_m5_harness_for_m5p2', ROOT / 'tests' / 'test_fm1t_m5.py')
FakeTransporter, LOADER, crc = harness.FakeTransporter, harness.LOADER, harness.crc
PORT = harness.PORT
LOADER_SHA = hashlib.sha256(LOADER).hexdigest()

RUN1_SHA256 = 'aba6ed7ceaa0cac990dedcaf664b10707632a139be83b3bea5e0f62739bf968c'
RUN2_SHA256 = 'b63a643e14983ac07a883867d073368733f6f714b7f35116aa85a4e91d80421c'
IMAGE_BYTES = 7920                                        # 4,096 + 3,824, both images
IMG = {1: bytes((i * 11 + 9) & 0xFF for i in range(IMAGE_BYTES)),     # synthetic
       2: bytes((i * 7 + 3) & 0xFF for i in range(IMAGE_BYTES))}
SHA = {n: hashlib.sha256(d).hexdigest() for n, d in IMG.items()}
NAME = {1: 'm5p2.bin', 2: 'm5p2-mailbox.bin'}
LOCK1, LOCK2, CRUMBS_LOCK = ('fm1t_m5p2-ramrun.lock', 'fm1t_m5p2-mailbox-ramrun.lock',
                            'fm1t_m5p2-crumbs.lock')
JUMPED1, JUMPED2 = 'fm1t_m5p2-ramrun.jumped', 'fm1t_m5p2-mailbox-ramrun.jumped'

# The dev kit's c-read of m5p2-mailbox (notes/2026-11-14-m5-plan-2.md).
KIT_WORDS = [0x3250354d, 0x0000000d, 0x0000001c, 0x0001595e, 0x00015e84, 0x00001cb2,
             0x00000000, 0x00000000, 0x00002404, 0x00000003, 0x02ad7d92, 0xcdafcab2]
KIT_CRUMBS = b''.join(w.to_bytes(4, 'little') for w in KIT_WORDS)


def chunks(n):
    return [(0x01C02000, IMG[n][:4096]), (0x01C03000, IMG[n][4096:])]


@pytest.fixture
def approved(monkeypatch):
    """Admit the synthetic images (same size as the real ones, so the compiled
    chunk addresses still hold) and the synthetic loader. The real values stay
    in the tool and are checked by test_approved_constants."""
    runs = copy.deepcopy(t.RUNS)
    for n in runs:
        runs[n]['sha256'] = SHA[n]
    monkeypatch.setattr(t, 'RUNS', runs)
    monkeypatch.setattr(t, 'LOADER_SHA256', LOADER_SHA)


@pytest.fixture(autouse=True)
def no_serial(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError('a test tried to open a real serial port')
    monkeypatch.setattr(t, 'open_port', refuse)
    monkeypatch.setattr(m5, 'open_port', refuse)


@pytest.fixture
def files(tmp_path):
    for n in IMG:
        (tmp_path / NAME[n]).write_bytes(IMG[n])
    (tmp_path / 'wl82loader.bin').write_bytes(LOADER)
    return tmp_path


def run(fake, argv, tmp_path, environ=None, log='log.jsonl', tool=None):
    opened = []

    def opener(port):
        opened.append(port)
        return fake

    code = (tool or t).main(['--port', PORT, '--log', str(tmp_path / log)] + argv,
                            environ=environ or {}, opener=opener)
    events = []
    if (tmp_path / log).exists():
        events = [json.loads(x) for x in (tmp_path / log).read_text().splitlines()]
    return code, events, opened


def ramrun_argv(files, n, sha=None, name=None):
    return ['ramrun', str(files / (name or NAME[n])), '--run', str(n), '--sha256', sha or SHA[n]]


def memw_line(addr, chunk):
    return f'memw {addr:#x} {len(chunk)} {crc(chunk):08X}'


def write_record(directory, n, kind, **change):
    """Run n's lock or jump marker as the tool writes it, with the hash pinned
    in t.RUNS at call time (the synthetic one under `approved`)."""
    rec = {'run': n, 'image_sha256': t.RUNS[n]['sha256']}
    rec.update(change)
    (directory / t.RUNS[n][kind]).write_text(json.dumps(rec) + '\n')


def jumped(directory, *runs):
    """A run directory in which each of `runs` took its lock and sent its jump."""
    for n in runs:
        write_record(directory, n, 'lock')
        write_record(directory, n, 'jumped')


def crumbs_with(**words):
    w = list(KIT_WORDS)
    for name, value in words.items():
        w[t.CRUMB_NAMES.index(name)] = value
    return b''.join(x.to_bytes(4, 'little') for x in w)


def crumbs_fake(data=KIT_CRUMBS, **kw):
    """A transporter back in the ROM after run 2's watchdog reset: SRAM holds
    the breadcrumbs, nothing else."""
    fake = FakeTransporter(**kw)
    for i, b in enumerate(data):
        fake.sram[0x01C05FC0 + i] = b
    return fake


# -- what is approved, and what M5 keeps -------------------------------------

def test_approved_constants():
    src = TOOL.read_text()
    assert f'"sha256": "{RUN1_SHA256}"' in src and f'"sha256": "{RUN2_SHA256}"' in src
    assert t.RUNS[1]['sha256'] == RUN1_SHA256 and t.RUNS[2]['sha256'] == RUN2_SHA256
    assert t.RUNS[1]['build_id'] == 'm5-plan-2' and t.RUNS[2]['build_id'] == 'm5-plan-2m'
    assert t.RUNS[1]['lock'] == LOCK1 and t.RUNS[2]['lock'] == LOCK2
    assert t.RUNS[1]['jumped'] == JUMPED1 and t.RUNS[2]['jumped'] == JUMPED2
    assert t.RUNS[1]['after'] is None and t.RUNS[2]['after'] == 1
    assert t.EXIT_SUSPECT == 4
    assert sorted(t.RUNS) == [1, 2] and t.APPROVED_IMAGE_BYTES == IMAGE_BYTES
    assert 'LOADER_SHA256 = "d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376"' in src
    assert t.RAM_BASE == 0x01C02000 and t.RAM_END == m5.RAM_END == 0x01C06000
    assert t.JUMP_ARG == 1
    assert set(t.RAMRUN_LOCKS) == {LOCK1, LOCK2} and m5.RAMRUN_LOCK not in t.RAMRUN_LOCKS
    assert set(t.OTHER_RAMRUN_LOCKS) == {m5.RAMRUN_LOCK, 'fm1t_m6-ramrun.lock'}
    assert t.CRUMBS_LOCK == CRUMBS_LOCK and CRUMBS_LOCK not in t.RAMRUN_LOCKS
    # The breadcrumbs sit above both images and inside the M5 window.
    assert (t.CRUMBS_ADDR, t.CRUMBS_BYTES, t.CRUMBS_MAGIC) == (0x01C05FC0, 48, 0x3250354D)
    assert t.RAM_BASE + IMAGE_BYTES == 0x01C03EF0 <= t.CRUMBS_ADDR
    assert t.CRUMBS_ADDR + t.CRUMBS_BYTES == 0x01C05FF0 <= t.RAM_END
    assert len(t.CRUMB_NAMES) == 12 and len(t.STAGES) == 14 and t.STAGES[13] == 'finishing'


def test_m5_tool_is_unchanged():
    assert hashlib.sha256(M5_TOOL.read_bytes()).hexdigest() == M5_TOOL_SHA256
    assert m5.APPROVED_IMAGE_SHA256.startswith('a60410de') and m5.APPROVED_IMAGE_BYTES == 4160


def test_no_override_flag_for_the_image():
    src = TOOL.read_text()
    assert 'allow-other-image' not in src and 'allow_other_image' not in src
    sub = t.build_parser()._subparsers._group_actions[0].choices
    for name in ('ramrun', 'crumbs'):
        for action in sub[name]._actions:
            assert not ({'--loader', '--addr', '--arg', '--clear', '--poke', '--read',
                         '--force'} & set(action.option_strings))
    for action in sub['crumbs']._actions:          # the address and length are fixed
        assert action.option_strings in (['-h', '--help'],)


def _code_lines(path):
    src = path.read_text()
    return src.splitlines()[ast.parse(src).body[0].end_lineno:]   # after the module docstring


EXPECTED_CODE_DIFF = [
    '-# -- What the owner approved (2026-11-09). Changing any of these needs a new',
    '-#    approval; there is deliberately no command-line override.',
    '-APPROVED_IMAGE_SHA256 = "a60410deb4ac5cedd5be2ab76c6155a604ae2efa43cea59430bf55c28d8d44e4"',
    '-APPROVED_IMAGE_BYTES = 4160',
    '-APPROVED_BUILD_ID = "m5-plan-1"',
    '+# -- What the owner approved (2026-11-14, HANDOFF "Owner decisions, 2026-11-14").',
    '+#    Changing any of these needs a new approval; there is deliberately no',
    '+#    command-line override. Run 2 only after run 1, in the same run directory.',
    '+RUNS = {',
    '+    1: {"sha256": "aba6ed7ceaa0cac990dedcaf664b10707632a139be83b3bea5e0f62739bf968c",',
    '+        "build_id": "m5-plan-2", "lock": "fm1t_m5p2-ramrun.lock",',
    '+        "jumped": "fm1t_m5p2-ramrun.jumped", "after": None},',
    '+    2: {"sha256": "b63a643e14983ac07a883867d073368733f6f714b7f35116aa85a4e91d80421c",',
    '+        "build_id": "m5-plan-2m", "lock": "fm1t_m5p2-mailbox-ramrun.lock",',
    '+        "jumped": "fm1t_m5p2-mailbox-ramrun.jumped", "after": 1},',
    '+}',
    '+APPROVED_IMAGE_BYTES = 7920      # both images',
    '-# One RAM-run attempt per run directory: created just before the first memw,',
    '-# next to the receipt. A second attempt (a retry) needs a new owner approval.',
    '-RAMRUN_LOCK = "fm1t_m5-ramrun.lock"',
    '+# One RAM-run attempt per run and run directory: created just before the first',
    '+# memw, next to the receipt. A second attempt (a retry) needs a new owner approval.',
    '+RAMRUN_LOCKS = tuple(r["lock"] for r in RUNS.values())',
    '+# A jump marker per run, written right after the jump line is sent: run 2',
    "+# and crumbs need the earlier run's lock and marker, both naming that run and",
    '+# its pinned image.',
    "+# M5's and M6's locks in the same directory also refuse: m5p2 needs its own.",
    '+OTHER_RAMRUN_LOCKS = ("fm1t_m5-ramrun.lock", "fm1t_m6-ramrun.lock")',
    '+',
    '+# The breadcrumbs (firmware/m5p2/m5p2.h): twelve little-endian words, word 0 the',
    '+# magic "M5P2", word 11 its complement. Read once, after run 2, from the ROM.',
    '+CRUMBS_ADDR = 0x01C05FC0',
    '+CRUMBS_BYTES = 48',
    '+CRUMBS_MAGIC = 0x3250354D',
    '+CRUMBS_LOCK = "fm1t_m5p2-crumbs.lock"',
    '+CRUMB_NAMES = ("magic", "stage", "wdt_con", "ticks_per_block", "max_gap", "kicks",',
    '+               "kick_failures", "panel", "elapsed_ms", "cycles", "ticks", "check")',
    '+STAGES = ("", "entry", "pa2_on", "timer_ok", "timer_dead", "measured", "cadence_a",',
    '+          "cadence_b", "spi_ok", "setup_ok", "display_on", "frame_done", "blinking",',
    '+          "finishing")',
    '+TIMER_DEAD_FLAG = 0x100          # in the stage word: TIMER4 failed at some point',
    '+PANEL_RESULTS = {0: "ok", 1: "invalid", 2: "transfer_failed", 3: "delay_failed",',
    '+                 0xFF: "not_run"}',
    '+EXIT_SUSPECT = 4                 # crumbs: magic valid, contents implausible',
    '+if not (RAM_BASE + APPROVED_IMAGE_BYTES <= CRUMBS_ADDR',
    '+        and CRUMBS_ADDR + CRUMBS_BYTES <= RAM_END):',
    '+    raise SystemExit("fm1t_m5p2: the image and the breadcrumbs overlap or leave the window")',
    '-                 "FM-1 OFF, run `fm1t_m5.py ... rekey --fm1-is-off`, reopen the console, wait "',
    '+                 "FM-1 OFF, run `fm1t_m5p2.py ... rekey --fm1-is-off`, reopen the console, wait "',
    '-_RAM_ADDRS = "|".join(f"{a:#x}" for a in range(RAM_BASE, RAM_END, MEMW_CHUNK))',
    '+# Only the chunk addresses of the approved images: 0x1c02000, 0x1c03000.',
    '+_RAM_ADDRS = "|".join(f"{a:#x}" for a in range(RAM_BASE, RAM_BASE + APPROVED_IMAGE_BYTES,',
    '+                                               MEMW_CHUNK))',
    '+    "crumbs_memr": rf"memr {CRUMBS_ADDR:#x} {CRUMBS_BYTES}",',
    '+    "crumbs": ("ping", "status", "crumbs_memr"),',
    '-def admit_image(path, sha256):',
    '-    """The image must fit the M5 window and be exactly the approved image."""',
    '+def admit_image(path, sha256, run):',
    '+    """The image must fit the M5 window and be exactly the image pinned for `run`."""',
    '+    if run not in RUNS:',
    '+        raise Refused(f"--run must be one of {sorted(RUNS)}")',
    '-    if digest != APPROVED_IMAGE_SHA256 or len(data) != APPROVED_IMAGE_BYTES:',
    '-        raise Refused(f"{path}: {digest} ({len(data)} B) is not the approved M5 image "',
    '-                      f"{APPROVED_IMAGE_SHA256} ({APPROVED_IMAGE_BYTES} B, build id "',
    '-                      f"{APPROVED_BUILD_ID}); another image needs a code change and a new "',
    '+    if digest != RUNS[run]["sha256"] or len(data) != APPROVED_IMAGE_BYTES:',
    '+        raise Refused(f"{path}: {digest} ({len(data)} B) is not the approved run {run} image "',
    '+                      f"{RUNS[run][\'sha256\']} ({APPROVED_IMAGE_BYTES} B, build id "',
    '+                      f"{RUNS[run][\'build_id\']}); another image needs a code change and a new "',
    '-    def __init__(self, port, mode, log, image=None):',
    '+    def __init__(self, port, mode, log, image=None, run=None):',
    '-            if image is None or hashlib.sha256(image).hexdigest() != APPROVED_IMAGE_SHA256 \\',
    '+            if run not in RUNS or image is None \\',
    '+                    or hashlib.sha256(image).hexdigest() != RUNS[run]["sha256"] \\',
    '-                raise Refused("refused: a RAM-run link needs the approved M5 image")',
    '+                raise Refused("refused: a RAM-run link needs the approved image of its run")',
    '+        elif name == "crumbs_memr":',
    '+            self.sealed = "the crumbs read"',
    '-    if st["uboot"] != 1:',
    '+    if st["uboot"] != 1 or st["v15"] != 0:',
    '-        return 3, (f"jump answered OK after {ms} ms: the image returned, which M5 never does; "',
    '+        return 3, (f"jump answered OK after {ms} ms: the image returned, which m5p2 never does; "',
    '-                   "that does not return. Image presumed running; the TFT and LEDs are the "',
    '-                   "proof. Nothing more is sent")',
    '+                   "that does not return. Image presumed running; the backlight, the TFT and "',
    '+                   "the LEDs are the proof. Nothing more is sent")',
    '+    run = RUNS[args.run]',
    '-    lock = args.log.parent / RAMRUN_LOCK',
    '+    if run["after"]:',
    '+        for kind in ("lock", "jumped"):',
    '+            why = run_record_problem(args.log.parent, run["after"], kind)',
    '+            if why:',
    '+                raise Stop(f"{why}: run {args.run} only after run {run[\'after\']} sent its "',
    '+                           "jump, from the same run directory")',
    '+    lock = args.log.parent / run["lock"]',
    '-                            "image_sha256": APPROVED_IMAGE_SHA256}) + "\\n")',
    '+                            "run": args.run, "image_sha256": run["sha256"]}) + "\\n")',
    '-    reply = link.request(f"jump {RAM_BASE:#x} {JUMP_ARG:#x}", TIMEOUT_JUMP)',
    '+    line = f"jump {RAM_BASE:#x} {JUMP_ARG:#x}"',
    '+    link.send_line(line)',
    '+    marker = args.log.parent / run["jumped"]',
    '+    try:',
    '+        with open(marker, "x") as f:     # the jump went out; run 2 and crumbs need this',
    '+            f.write(json.dumps({"time": round(time.time(), 3), "receipt": args.log.name,',
    '+                                "run": args.run, "image_sha256": run["sha256"],',
    '+                                "jump": line}) + "\\n")',
    '+        result["jumped"] = str(marker)',
    '+    except OSError as exc:',
    '+        result["jump_marker_error"] = f"{type(exc).__name__}: {exc}"',
    '+    reply = link.recv_line(TIMEOUT_JUMP)',
    '+    if "jump_marker_error" in result:',
    '+        code, verdict = 3, (f"{verdict}. The jump marker {marker} could not be written "',
    '+                            f"({result[\'jump_marker_error\']}): the later steps will refuse")',
    '+',
    '+',
    '+def run_record_problem(directory, run, kind):',
    '+    """None if `directory` holds run `run`\'s lock or jump marker (`kind`),',
    "+    recording that run and its pinned image; otherwise why not. The file's",
    '+    name alone is not trusted."""',
    '+    path = directory / RUNS[run][kind]',
    '+    try:',
    '+        rec = json.loads(path.read_text())',
    '+    except FileNotFoundError:',
    '+        return f"no {path.name} in {directory}"',
    '+    except (OSError, ValueError) as exc:',
    '+        return f"{path} is unreadable ({type(exc).__name__})"',
    '+    if (not isinstance(rec, dict) or rec.get("run") != run',
    '+            or rec.get("image_sha256") != RUNS[run]["sha256"]):',
    '+        return f"{path} does not record run {run} with its pinned image"',
    '+    return None',
    '+',
    '+',
    '+def decode_crumbs(data):',
    '+    """The twelve words by name, with the stage and the panel result spelled out."""',
    '+    words = [int.from_bytes(data[i:i + 4], "little") for i in range(0, CRUMBS_BYTES, 4)]',
    '+    out = dict(zip(CRUMB_NAMES, words))',
    '+    out["valid"] = words[0] == CRUMBS_MAGIC and words[11] == CRUMBS_MAGIC ^ 0xFFFFFFFF',
    '+    stage = words[1] & 0xFF',
    '+    out["stage_name"] = STAGES[stage] if 0 < stage < len(STAGES) else f"unknown {stage}"',
    '+    out["timer_dead"] = bool(words[1] & TIMER_DEAD_FLAG)',
    '+    out["panel_name"] = PANEL_RESULTS.get(words[7], f"unknown {words[7]}")',
    '+    doubts = []',
    '+    if words[1] & ~(0xFF | TIMER_DEAD_FLAG) or not 0 < stage < len(STAGES):',
    '+        doubts.append(f"stage word {words[1]:#x} is not a stage 1-{len(STAGES) - 1} "',
    '+                      "with at most the timer-dead flag")',
    '+    if words[7] not in PANEL_RESULTS:',
    '+        doubts.append(f"panel result {words[7]:#x} is unknown")',
    '+    if out["kick_failures"] > out["kicks"]:',
    '+        doubts.append(f"kick_failures {out[\'kick_failures\']} exceed kicks {out[\'kicks\']}")',
    '+    out["doubts"] = doubts',
    '+    return out',
    '+',
    '+',
    '+# Stops for crumbs: never "power off" while the breadcrumbs may still be in SRAM.',
    '+CRUMBS_STOP_V15 = ("status answers v15=1: the FM-1 booted V15 instead of returning to the "',
    '+                   "mask ROM, so the breadcrumbs are lost (docs/19 section 7.6, R6 (c)). "',
    '+                   "Send nothing else: photograph the unit, then power off (R8)")',
    '+CRUMBS_STOP_NO_UBOOT = ("status answers uboot=0: the transporter has not mounted the mask "',
    '+                        "ROM. Keep the FM-1 ON and do not rekey: power-off clears the "',
    '+                        "breadcrumbs. Replug the transporter\'s USB with the FM-1 left on "',
    '+                        "(docs/19 section 7.6), wait for `UBOOT READY`, then run crumbs again")',
    '+CRUMBS_STOP_LOADER_HELD = ("status answers loader=1: the transporter holds the flash loader "',
    '+                           "from an earlier step. Keep the FM-1 ON and do not rekey. Replug "',
    '+                           "the transporter\'s USB with the FM-1 left on (docs/19 section 7.6), "',
    '+                           "wait for `UBOOT READY`, then run crumbs again")',
    '+CRUMBS_STOP_LOADER_RUNNING = ("status answers loader_running=1: the flash loader runs at "',
    '+                              "0x1c02000, over the breadcrumbs, so they are lost. Send nothing "',
    '+                              "else; power off (docs/19 section 7.6, R8)")',
    '+',
    '+',
    '+def cmd_crumbs(link, args, result):',
    '+    st = read_status(link)',
    '+    result["status"] = st',
    '+    if st["v15"]:',
    '+        raise Stop(CRUMBS_STOP_V15)',
    '+    if st["uboot"] != 1:',
    '+        raise Stop(CRUMBS_STOP_NO_UBOOT)',
    '+    if st["loader_running"]:',
    '+        raise Stop(CRUMBS_STOP_LOADER_RUNNING)',
    '+    if st["loader"]:',
    '+        raise Stop(CRUMBS_STOP_LOADER_HELD)',
    '+    line = f"memr {CRUMBS_ADDR:#x} {CRUMBS_BYTES}"',
    '+    reply = link.request(line, TIMEOUT_MEM)',
    '+    if reply != f"DATA {CRUMBS_BYTES}":',
    '+        raise Stop(f"{line}: {reply!r}. No DATA came, so no crumbs lock was taken (with no "',
    '+                   "reply at all the read may still have happened; reading again is "',
    '+                   "harmless). Keep the FM-1 ON and do not rekey. If the console showed no "',
    '+                   "new `UBOOT READY` after the jump, the transporter\'s mount may be stale: "',
    '+                   "docs/19 section 7.6, then run crumbs again")',
    '+    data = b""',
    '+    try:',
    '+        data = link.recv_bytes(CRUMBS_BYTES, TIMEOUT_MEM)',
    '+        result["crumbs_hex"] = data.hex()        # raw, before anything else',
    '+        link._log("crumbs-raw", hex=data.hex())',
    '+    finally:',
    '+        lock = args.log.parent / CRUMBS_LOCK     # DATA came: the read happened',
    '+        with open(lock, "x") as f:               # FileExistsError: it happened before',
    '+            f.write(json.dumps({"time": round(time.time(), 3), "receipt": args.log.name,',
    '+                                "read": line, "crumbs_hex": data.hex()}) + "\\n")',
    '+        result["lock"] = str(lock)',
    '+    end = link.recv_line(TIMEOUT_MEM)',
    '+    if len(data) != CRUMBS_BYTES or end != f"END {crc32(data):08X}":',
    '+        raise Stop(f"{line}: transfer check failed ({end!r}); the raw bytes are in the receipt")',
    '+    crumbs = decode_crumbs(data)',
    '+    result["crumbs"] = crumbs',
    '+    for name in CRUMB_NAMES:',
    '+        print(f"{name:16} {crumbs[name]:#010x} {crumbs[name]}")',
    '+    print(f"stage {crumbs[\'stage_name\']}, timer_dead {crumbs[\'timer_dead\']}, "',
    '+          f"panel {crumbs[\'panel_name\']}, valid {crumbs[\'valid\']}")',
    '+    if not crumbs["valid"]:',
    '+        result["verdict"] = ("breadcrumbs read, but the magic or its complement does not match: "',
    '+                             "they did not survive, or were never written. Power off")',
    '+        print(result["verdict"])',
    '+        return 3',
    '+    if crumbs["doubts"]:',
    '+        result["verdict"] = ("breadcrumbs read and the magic is valid, but SUSPECT: "',
    '+                             + "; ".join(crumbs["doubts"])',
    '+                             + ". Keep the raw bytes; do not trust the decode")',
    '+        print(result["verdict"])',
    '+        return EXIT_SUSPECT',
    '+    result["verdict"] = f"breadcrumbs read and valid; last stage {crumbs[\'stage_name\']}"',
    '+    print(result["verdict"])',
    '+    return 0',
    '-        admit_image(args.image, args.sha256)',
    '-        print(f"image {args.image}: approved M5 image, {APPROVED_IMAGE_BYTES} B, "',
    '-              f"{APPROVED_IMAGE_SHA256}, ends at {RAM_BASE + APPROVED_IMAGE_BYTES:#010x}")',
    '+        digest = sha256_file(args.image)',
    '+        run = next((n for n, r in RUNS.items() if r["sha256"] == digest), 1)',
    '+        admit_image(args.image, args.sha256, run)',
    '+        print(f"image {args.image}: approved run {run} image ({RUNS[run][\'build_id\']}), "',
    '+              f"{APPROVED_IMAGE_BYTES} B, {digest}, ends at "',
    '+              f"{RAM_BASE + APPROVED_IMAGE_BYTES:#010x}")',
    '-# Upstream ramrun options that M5 refuses by name (note section 4.2).',
    '+# Upstream ramrun options that M5 and m5p2 refuse by name (M5 note section 4.2).',
    '-                 "dump": cmd_dump, "ramrun": cmd_ramrun}',
    '+                 "dump": cmd_dump, "ramrun": cmd_ramrun, "crumbs": cmd_crumbs}',
    '-    m = sub.add_parser("ramrun", help="load the approved M5 image at 0x01C02000 and jump once")',
    '+    m = sub.add_parser("ramrun", help="load run 1\'s or run 2\'s approved image at 0x01C02000 "',
    '+                       "and jump once")',
    '-    m.add_argument("--sha256", required=True, help=f"must be {APPROVED_IMAGE_SHA256}")',
    '+    m.add_argument("--run", type=int, required=True, choices=sorted(RUNS),',
    '+                   help="1: m5p2.bin; 2: m5p2-mailbox.bin, only after run 1")',
    '+    m.add_argument("--sha256", required=True, help="must be that run\'s pinned SHA-256")',
    '+    sub.add_parser("crumbs", help="after run 2: read the 48 B of breadcrumbs from the ROM, once")',
    '-        args.image_bytes = admit_image(args.image, args.sha256)',
    '-        if args.log and (args.log.parent / RAMRUN_LOCK).exists():',
    '-            raise Refused(f"{args.log.parent / RAMRUN_LOCK} exists: M5 was already attempted "',
    '-                          "from this run directory. There is no second attempt; another run "',
    '-                          "needs a new owner approval")',
    '+        args.image_bytes = admit_image(args.image, args.sha256, args.run)',
    '+        here = args.log.parent if args.log else None',
    '+        if here and (here / RUNS[args.run]["lock"]).exists():',
    '+            raise Refused(f"{here / RUNS[args.run][\'lock\']} exists: run {args.run} was already "',
    '+                          "attempted from this run directory. There is no second attempt; "',
    '+                          "another run needs a new owner approval")',
    '+        for other in OTHER_RAMRUN_LOCKS:',
    '+            if here and (here / other).exists():',
    '+                raise Refused(f"{here / other} exists: this is M5\'s or M6\'s run directory; "',
    '+                              "run m5p2 from a new one (docs/19 section 7)")',
    '+        after = RUNS[args.run]["after"]',
    '+        if here and after:',
    '+            for kind in ("lock", "jumped"):',
    '+                why = run_record_problem(here, after, kind)',
    '+                if why:',
    '+                    raise Refused(f"{why}: run {args.run} is allowed only after run {after} "',
    '+                                  "sent its jump, from the same run directory")',
    '+        if here and args.run == 1 and (here / RUNS[2]["lock"]).exists():',
    '+            raise Refused(f"{here / RUNS[2][\'lock\']} exists: run 1 never follows run 2")',
    '+    if args.cmd == "crumbs":',
    '+        if environ.get("FM1T_LOADER"):',
    '+            raise Refused("FM1T_LOADER is set in the environment; unset it: the loader would "',
    '+                          "overwrite the breadcrumbs")',
    '+        here = args.log.parent if args.log else None',
    '+        if here and (here / CRUMBS_LOCK).exists():',
    '+            raise Refused(f"{here / CRUMBS_LOCK} exists: the breadcrumbs were already read "',
    '+                          "from this run directory")',
    '+        if here:',
    '+            for kind in ("lock", "jumped"):',
    '+                why = run_record_problem(here, 2, kind)',
    '+                if why:',
    '+                    raise Refused(f"{why}: crumbs reads run 2\'s breadcrumbs, only after run 2 "',
    '+                                  "sent its jump, from run 2\'s run directory")',
    '-                print(f"fm1t_m5: refused: ramrun {flag}: {RAMRUN_REFUSED_FLAGS[flag]}",',
    '+                print(f"fm1t_m5p2: refused: ramrun {flag}: {RAMRUN_REFUSED_FLAGS[flag]}",',
    '-        print(f"fm1t_m5: {exc}", file=sys.stderr)',
    '+        print(f"fm1t_m5p2: {exc}", file=sys.stderr)',
    '-            build_id=APPROVED_BUILD_ID if args.cmd == "ramrun" else None)',
    '+            build_id=RUNS[args.run]["build_id"] if args.cmd == "ramrun" else None,',
    '+            run=getattr(args, "run", None))',
    '-            link = Link(port, args.cmd, log, image=getattr(args, "image_bytes", None))',
    '+            link = Link(port, args.cmd, log, image=getattr(args, "image_bytes", None),',
    '+                        run=getattr(args, "run", None))',
    '-            why = ("M5 was already attempted from this run directory; no second attempt"',
    '-                   if str(exc.filename).endswith(RAMRUN_LOCK) else "never overwritten")',
    '+            why = ("this run or read was already attempted from this run directory; no second "',
    '+                   "attempt" if str(exc.filename).endswith(RAMRUN_LOCKS + (CRUMBS_LOCK,))',
    '+                   else "never overwritten")',
    '-        print(f"fm1t_m5: {result.get(\'verdict\')}", file=sys.stderr)',
    '+        print(f"fm1t_m5p2: {result.get(\'verdict\')}", file=sys.stderr)',
]


def test_only_the_pinned_lines_differ():
    """Every line of fm1t_m5p2.py after its docstring equals fm1t_m5.py's except
    these. A change anywhere else needs this list updated, in review."""
    got = [l for l in difflib.unified_diff(_code_lines(M5_TOOL), _code_lines(TOOL),
                                           lineterm='', n=0)
           if l[:1] in '+-' and not l.startswith(('---', '+++'))]
    assert got == EXPECTED_CODE_DIFF


def test_real_constants_refuse_other_images(tmp_path):
    """With the real constants: each run admits only its own pinned hash."""
    for n in (1, 2):
        (tmp_path / NAME[n]).write_bytes(IMG[n])
        for run_no in (1, 2):
            with pytest.raises(t.Refused, match=f'not the approved run {run_no} image'):
                t.admit_image(tmp_path / NAME[n], SHA[n], run_no)
    with pytest.raises(t.Refused):
        t.admit_image(tmp_path / NAME[1], SHA[1], 3)
    with pytest.raises(t.Refused, match='approved image of its run'):
        t.Link(FakeTransporter(), 'ramrun', lambda *a, **k: None, image=IMG[1], run=1)
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(tmp_path, 1), tmp_path)
    assert code == 1 and opened == [] and fake.wire == b'' and events == []


def test_each_run_refuses_the_other_runs_image(approved, files, tmp_path):
    for n, other in ((1, 2), (2, 1)):
        fake = FakeTransporter()
        code, _, opened = run(fake, ramrun_argv(files, n, sha=SHA[other], name=NAME[other]),
                              tmp_path, log=f'{n}.jsonl')
        assert code == 1 and opened == [] and fake.wire == b''
        with pytest.raises(t.Refused, match='approved image of its run'):
            t.Link(FakeTransporter(), 'ramrun', lambda *a, **k: None, image=IMG[other], run=n)
    with pytest.raises(t.Refused, match='approved image of its run'):
        t.Link(FakeTransporter(), 'ramrun', lambda *a, **k: None, image=IMG[1], run=None)


# -- run 1 and run 2 ---------------------------------------------------------

def _assert_ramrun_wire(fake, n):
    cs = chunks(n)
    assert [len(c) for _, c in cs] == [4096, 3824]
    assert fake.lines == (['ping', 'status'] + [memw_line(a, c) for a, c in cs]
                          + ['memr 0x1c02000 4096', 'memr 0x1c03000 3824']
                          + ['jump 0x1c02000 0x1'])
    assert fake.wire == (b'ping\nstatus\n'
                         + b''.join(memw_line(a, c).encode() + b'\n' + c for a, c in cs)
                         + b'memr 0x1c02000 4096\nmemr 0x1c03000 3824\n'
                         + b'jump 0x1c02000 0x1\n')
    assert sorted(fake.sram) == list(range(0x01C02000, 0x01C03EF0))
    assert bytes(fake.sram[a] for a in sorted(fake.sram)) == IMG[n]
    assert fake.jumps == [(0x01C02000, 1)]
    assert not fake.softkey_sent and not fake.flash_written and not fake.runapp_sent
    assert fake.closed and fake.dropped == []


def test_run1_happy_path(approved, files, tmp_path):
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(files, 1), tmp_path, log='run1.jsonl')
    assert code == 0 and opened == [PORT]
    _assert_ramrun_wire(fake, 1)
    start, end = events[0], events[-1]
    assert start['build_id'] == 'm5-plan-2' and start['run'] == 1
    assert start['image_sha256'] == SHA[1]
    assert start['tool_sha256'] == hashlib.sha256(TOOL.read_bytes()).hexdigest()
    assert end['exit'] == 0 and end['readback'] == 'equal'
    assert 'presumed running' in end['verdict'] and 'backlight' in end['verdict']
    lock = json.loads((tmp_path / LOCK1).read_text())
    assert lock['receipt'] == 'run1.jsonl' and lock['run'] == 1 and lock['image_sha256'] == SHA[1]
    marker = json.loads((tmp_path / JUMPED1).read_text())
    assert marker['receipt'] == 'run1.jsonl' and marker['run'] == 1
    assert marker['image_sha256'] == SHA[1] and marker['jump'] == 'jump 0x1c02000 0x1'
    assert end['jumped'] == str(tmp_path / JUMPED1)
    assert not (tmp_path / LOCK2).exists() and not (tmp_path / JUMPED2).exists()


def test_run2_after_run1_in_the_same_directory(approved, files, tmp_path):
    assert run(FakeTransporter(), ramrun_argv(files, 1), tmp_path, log='run1.jsonl')[0] == 0
    fake = FakeTransporter()
    code, events, _ = run(fake, ramrun_argv(files, 2), tmp_path, log='run2.jsonl')
    assert code == 0
    _assert_ramrun_wire(fake, 2)
    assert events[0]['build_id'] == 'm5-plan-2m' and events[0]['run'] == 2
    assert json.loads((tmp_path / LOCK2).read_text())['run'] == 2
    assert json.loads((tmp_path / JUMPED2).read_text())['image_sha256'] == SHA[2]


def test_run2_refused_before_run1(approved, files, tmp_path, capsys):
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(files, 2), tmp_path)
    assert code == 1 and opened == [] and fake.wire == b'' and events == []
    assert 'only after run 1' in capsys.readouterr().err
    assert not (tmp_path / LOCK2).exists()


@pytest.mark.parametrize('gone', [LOCK1, JUMPED1])
def test_run1_record_vanishing_mid_session_stops_run2(approved, files, tmp_path, gone):
    jumped(tmp_path, 1)
    fake = FakeTransporter()
    orig = fake._poll

    def racing(line, payload):
        orig(line, payload)
        if line == 'status':
            (tmp_path / gone).unlink()
    fake._poll = racing
    code, events, _ = run(fake, ramrun_argv(files, 2), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status'] and fake.sram == {}
    assert not (tmp_path / LOCK2).exists()
    assert f'no {gone}' in events[-1]['verdict']
    assert 'only after run 1 sent its jump' in events[-1]['verdict']


@pytest.mark.parametrize('setup,why', [
    (lambda d: write_record(d, 1, 'lock'), 'no fm1t_m5p2-ramrun.jumped'),
    (lambda d: write_record(d, 1, 'jumped'), 'no fm1t_m5p2-ramrun.lock'),
    (lambda d: (jumped(d, 1), write_record(d, 1, 'jumped', run=2)), 'does not record run 1'),
    (lambda d: (jumped(d, 1), write_record(d, 1, 'lock', image_sha256='0' * 64)),
     'does not record run 1'),
    (lambda d: (jumped(d, 1), (d / JUMPED1).write_text('{}\n')), 'does not record run 1'),
    (lambda d: (jumped(d, 1), (d / JUMPED1).write_text('[1]\n')), 'does not record run 1'),
    (lambda d: (jumped(d, 1), (d / LOCK1).write_text('not json')), 'is unreadable'),
])
def test_run2_needs_run1s_lock_and_jump_marker_by_content(approved, files, tmp_path, capsys,
                                                          setup, why):
    setup(tmp_path)
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(files, 2), tmp_path)
    assert code == 1 and opened == [] and fake.wire == b'' and events == []
    err = capsys.readouterr().err
    assert why in err and 'only after run 1 sent its jump' in err
    assert not (tmp_path / LOCK2).exists()


def test_jump_marker_is_written_only_after_the_jump_line(approved, files, tmp_path):
    fake = FakeTransporter()
    orig = fake._poll
    seen = []

    def watch(line, payload):
        seen.append((line, (tmp_path / JUMPED1).exists()))
        orig(line, payload)
    fake._poll = watch
    assert run(fake, ramrun_argv(files, 1), tmp_path)[0] == 0
    assert seen[-1] == ('jump 0x1c02000 0x1', False)
    assert all(not exists for _, exists in seen)
    assert (tmp_path / JUMPED1).exists()


def test_no_jump_marker_when_stopped_before_the_jump(approved, files, tmp_path):
    fake = FakeTransporter(corrupt_memr=True)
    code, events, _ = run(fake, ramrun_argv(files, 1), tmp_path)
    assert code == 3 and 'not jumping' in events[-1]['verdict'] and not fake.jumps
    assert (tmp_path / LOCK1).exists() and not (tmp_path / JUMPED1).exists()
    # So run 2 is refused: run 1 never jumped.
    again = FakeTransporter()
    code, _, opened = run(again, ramrun_argv(files, 2), tmp_path, log='run2.jsonl')
    assert code == 1 and opened == [] and again.wire == b''


def test_jump_marker_write_failure_is_a_stop(approved, files, tmp_path):
    (tmp_path / JUMPED1).write_text('left over\n')       # open(..., "x") fails
    fake = FakeTransporter()
    code, events, _ = run(fake, ramrun_argv(files, 1), tmp_path)
    assert code == 3 and fake.jumps == [(0x01C02000, 1)]
    assert 'FileExistsError' in events[-1]['jump_marker_error']
    assert 'could not be written' in events[-1]['verdict']
    assert 'presumed running' in events[-1]['verdict']
    assert (tmp_path / JUMPED1).read_text() == 'left over\n'


@pytest.mark.parametrize('n', [1, 2])
def test_second_attempt_of_a_run_is_refused(approved, files, tmp_path, n):
    if n == 2:
        jumped(tmp_path, 1)
    assert run(FakeTransporter(), ramrun_argv(files, n), tmp_path, log='first.jsonl')[0] == 0
    again = FakeTransporter()
    code, events, opened = run(again, ramrun_argv(files, n), tmp_path, log='second.jsonl')
    assert code == 1 and opened == [] and again.wire == b'' and events == []


def test_run1_never_follows_run2(approved, files, tmp_path, capsys):
    (tmp_path / LOCK2).write_text('{}\n')
    fake = FakeTransporter()
    code, _, opened = run(fake, ramrun_argv(files, 1), tmp_path)
    assert code == 1 and opened == [] and fake.wire == b''
    assert 'never follows run 2' in capsys.readouterr().err


@pytest.mark.parametrize('other', ['fm1t_m5-ramrun.lock', 'fm1t_m6-ramrun.lock'])
@pytest.mark.parametrize('n', [1, 2])
def test_m5_and_m6_run_directories_are_refused(approved, files, tmp_path, capsys, other, n):
    (tmp_path / other).write_text('{}\n')
    if n == 2:
        (tmp_path / LOCK1).write_text('{}\n')
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(files, n), tmp_path)
    assert code == 1 and opened == [] and fake.wire == b'' and events == []
    assert "M5's or M6's run directory" in capsys.readouterr().err


def test_lock_created_by_a_parallel_run_stops_before_memw(approved, files, tmp_path):
    fake = FakeTransporter()
    orig = fake._poll

    def racing(line, payload):
        orig(line, payload)
        if line == 'status':
            (tmp_path / LOCK1).write_text('{}\n')
    fake._poll = racing
    code, events, _ = run(fake, ramrun_argv(files, 1), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status'] and fake.sram == {}
    assert 'already attempted' in events[-1]['verdict']


@pytest.mark.parametrize('kw', [{'uboot': False}, {'uboot': True, 'v15': True},
                                {'loader': True}, {'loader_running': True}])
def test_ramrun_needs_a_fresh_rom_entry(approved, files, tmp_path, kw):
    fake = FakeTransporter(**kw)
    code, _, _ = run(fake, ramrun_argv(files, 1), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status'] and fake.sram == {}
    assert not (tmp_path / LOCK1).exists() and not (tmp_path / JUMPED1).exists()


@pytest.mark.parametrize('mode,ms,code', [
    ('timeout', 2003, 0), ('timeout', 1499, 3), ('timeout', 10001, 3),
    ('ok', None, 3), ('fast', None, 3), ('silent', None, 3), ('garbage', None, 3)])
def test_jump_verdicts(approved, files, tmp_path, mode, ms, code):
    fake = FakeTransporter(jump=mode, jump_ms=ms or 2003)
    got, events, _ = run(fake, ramrun_argv(files, 1), tmp_path)
    assert got == code
    assert fake.lines.count('jump 0x1c02000 0x1') == 1 and fake.lines[-1] == 'jump 0x1c02000 0x1'
    assert fake.closed and events[-1]['exit'] == code
    # The jump line went out, whatever came back: the marker records that.
    assert json.loads((tmp_path / JUMPED1).read_text())['jump'] == 'jump 0x1c02000 0x1'
    if mode == 'ok':
        assert 'm5p2 never does' in events[-1]['verdict']


def test_ramrun_refuses_fm1t_loader_env_and_upstream_flags(approved, files, tmp_path):
    fake = FakeTransporter()
    code, _, opened = run(fake, ramrun_argv(files, 1), tmp_path,
                          environ={'FM1T_LOADER': str(files / 'wl82loader.bin')})
    assert code == 1 and opened == [] and fake.wire == b''
    for flag in ('--loader', '--addr', '--arg', '--clear', '--poke', '--read'):
        fake = FakeTransporter()
        code, _, opened = run(fake, ramrun_argv(files, 1) + [flag, 'x'], tmp_path,
                              log=f'{flag[2:]}.jsonl')
        assert code in (1, 2) and opened == [] and fake.wire == b''
    for bad in (['--run', '3'], ['--run', '0']):
        argv = ramrun_argv(files, 1)
        argv[argv.index('--run') + 1] = bad[1]
        with pytest.raises(SystemExit):
            run(FakeTransporter(), argv, tmp_path, log='bad.jsonl')


def test_preflight_names_the_run_by_hash(approved, files, capsys):
    for n in (1, 2):
        code = t.main(['preflight', '--image', str(files / NAME[n]), '--sha256', SHA[n],
                       '--loader', str(files / 'wl82loader.bin')], environ={},
                      opener=lambda p: pytest.fail('preflight opened a port'))
        assert code == 0
        out = capsys.readouterr().out
        assert f'approved run {n} image ({t.RUNS[n]["build_id"]}), 7920 B' in out


def test_info_and_dump_still_pass_the_ldr_gate(approved, files, tmp_path):
    for cmd in (['info', '--loader', str(files / 'wl82loader.bin')],
                ['dump', str(tmp_path / 'out.bin'), '--loader', str(files / 'wl82loader.bin')]):
        fake = FakeTransporter()
        code, events, _ = run(fake, cmd, tmp_path, log=f'{cmd[0]}.jsonl')
        assert code == 0 and events[-1]['exit'] == 0
        assert not fake.sram and not fake.jumps and not fake.flash_written


# -- crumbs ------------------------------------------------------------------

def _run2_dir(tmp_path):
    """Run 2's directory as the real runs leave it (real hashes: no `approved`)."""
    jumped(tmp_path, 1, 2)


def test_crumbs_reads_once_and_decodes_the_kit_vector(tmp_path, capsys):
    _run2_dir(tmp_path)
    fake = crumbs_fake()
    code, events, opened = run(fake, ['crumbs'], tmp_path, log='crumbs.jsonl')
    assert code == 0 and opened == [PORT]
    assert fake.lines == ['ping', 'status', 'memr 0x1c05fc0 48']
    assert fake.wire == b'ping\nstatus\nmemr 0x1c05fc0 48\n'
    assert not fake.jumps and not fake.softkey_sent and not fake.flash_written
    assert fake.loader_have == 0 and not fake.runapp_sent
    end = events[-1]
    assert end['exit'] == 0 and end['crumbs_hex'] == KIT_CRUMBS.hex()
    c = end['crumbs']
    assert c['valid'] and c['stage_name'] == 'finishing' and not c['timer_dead']
    assert (c['wdt_con'], c['ticks_per_block'], c['max_gap'], c['kicks']) == (0x1C, 88414, 89732, 7346)
    assert (c['kick_failures'], c['panel_name'], c['elapsed_ms'], c['cycles'], c['ticks']) == \
        (0, 'ok', 9220, 3, 44924306)
    # The raw bytes are in the receipt before the END line is checked.
    kinds = [e['event'] for e in events]
    raw = kinds.index('crumbs-raw')
    assert events[raw]['hex'] == KIT_CRUMBS.hex()
    assert events[raw + 1]['event'] == 'rx' and events[raw + 1]['line'].startswith('END ')
    lock = json.loads((tmp_path / CRUMBS_LOCK).read_text())
    assert lock['receipt'] == 'crumbs.jsonl' and lock['crumbs_hex'] == KIT_CRUMBS.hex()
    assert c['doubts'] == [] and 'SUSPECT' not in end['verdict']
    assert 'last stage finishing' in capsys.readouterr().out


def test_crumbs_decode_flags_and_unknowns():
    words = list(KIT_WORDS)
    words[1] = 0x100 | 4
    words[7] = 0xFF
    d = t.decode_crumbs(b''.join(w.to_bytes(4, 'little') for w in words))
    assert d['valid'] and d['timer_dead'] and d['stage_name'] == 'timer_dead'
    assert d['panel_name'] == 'not_run'
    words[1], words[7], words[11] = 0x2A, 9, 0
    d = t.decode_crumbs(b''.join(w.to_bytes(4, 'little') for w in words))
    assert not d['valid'] and d['stage_name'] == 'unknown 42' and d['panel_name'] == 'unknown 9'


@pytest.mark.parametrize('words,doubt', [
    ({'stage': 0}, 'stage word 0x0 is not a stage 1-13'),
    ({'stage': 14}, 'stage word 0xe is not a stage 1-13'),
    ({'stage': 0x100 | 14}, 'stage word 0x10e'),
    ({'stage': 0x200 | 13}, 'stage word 0x20d'),
    ({'stage': 0x10000 | 13}, 'stage word 0x1000d'),
    ({'panel': 4}, 'panel result 0x4 is unknown'),
    ({'panel': 0x100}, 'panel result 0x100 is unknown'),
    ({'kick_failures': 0x1cb3}, 'kick_failures 7347 exceed kicks 7346'),
])
def test_crumbs_with_a_valid_magic_but_odd_words_are_suspect(tmp_path, capsys, words, doubt):
    _run2_dir(tmp_path)
    data = crumbs_with(**words)
    code, events, _ = run(crumbs_fake(data), ['crumbs'], tmp_path)
    end = events[-1]
    assert code == t.EXIT_SUSPECT == 4 and end['exit'] == 4
    assert end['crumbs']['valid'] and any(doubt in d for d in end['crumbs']['doubts'])
    assert end['verdict'].startswith('breadcrumbs read and the magic is valid, but SUSPECT: ')
    assert doubt in end['verdict'] and end['crumbs_hex'] == data.hex()
    assert json.loads((tmp_path / CRUMBS_LOCK).read_text())['crumbs_hex'] == data.hex()
    assert 'SUSPECT' in capsys.readouterr().out


def test_crumbs_timer_dead_flag_on_a_known_stage_is_not_suspect(tmp_path):
    _run2_dir(tmp_path)
    code, events, _ = run(crumbs_fake(crumbs_with(stage=0x100 | 4, kick_failures=0x1cb2)),
                          ['crumbs'], tmp_path)
    assert code == 0 and events[-1]['crumbs']['timer_dead']
    assert events[-1]['crumbs']['doubts'] == []


def test_crumbs_without_the_magic_exit_3_and_keep_the_bytes(tmp_path):
    _run2_dir(tmp_path)
    fake = crumbs_fake(bytes(48))
    code, events, _ = run(fake, ['crumbs'], tmp_path)
    assert code == 3 and events[-1]['crumbs_hex'] == '00' * 48
    assert not events[-1]['crumbs']['valid'] and 'does not match' in events[-1]['verdict']
    assert (tmp_path / CRUMBS_LOCK).exists()


def test_crumbs_transfer_failure_keeps_the_raw_bytes(tmp_path):
    _run2_dir(tmp_path)
    fake = crumbs_fake()
    orig = fake._poll

    def bad_end(line, payload):
        if line.startswith('memr'):
            fake._tx('DATA 48')
            fake.out += KIT_CRUMBS
            fake._tx('END 00000000')
            return
        orig(line, payload)
    fake._poll = bad_end
    code, events, _ = run(fake, ['crumbs'], tmp_path)
    assert code == 3 and 'transfer check failed' in events[-1]['verdict']
    assert events[-1]['crumbs_hex'] == KIT_CRUMBS.hex() and 'crumbs' not in events[-1]
    assert (tmp_path / CRUMBS_LOCK).exists()


@pytest.mark.parametrize('setup,why', [
    (lambda d: None, 'no fm1t_m5p2-mailbox-ramrun.lock'),
    (lambda d: jumped(d, 1), 'no fm1t_m5p2-mailbox-ramrun.lock'),
    (lambda d: (jumped(d, 1), write_record(d, 2, 'lock')), 'no fm1t_m5p2-mailbox-ramrun.jumped'),
    (lambda d: (jumped(d, 1, 2), write_record(d, 2, 'jumped', run=1)), 'does not record run 2'),
    (lambda d: (jumped(d, 1, 2), write_record(d, 2, 'lock', image_sha256=RUN1_SHA256)),
     'does not record run 2'),
    (lambda d: (jumped(d, 1, 2), (d / JUMPED2).write_text('{}\n')), 'does not record run 2'),
    (lambda d: (jumped(d, 1, 2), (d / JUMPED2).write_bytes(b'\xff\xfe')), 'is unreadable'),
])
def test_crumbs_needs_run2s_lock_and_jump_marker_by_content(tmp_path, capsys, setup, why):
    setup(tmp_path)
    fake = crumbs_fake()
    code, events, opened = run(fake, ['crumbs'], tmp_path)
    assert code == 1 and opened == [] and fake.wire == b'' and events == []
    err = capsys.readouterr().err
    assert why in err and 'only after run 2 sent its jump' in err


def test_crumbs_refused_once_read(tmp_path, capsys):
    _run2_dir(tmp_path)
    (tmp_path / CRUMBS_LOCK).write_text('{}\n')
    fake = crumbs_fake()
    code, events, opened = run(fake, ['crumbs'], tmp_path)
    assert code == 1 and opened == [] and fake.wire == b'' and events == []
    assert 'already read' in capsys.readouterr().err


def test_crumbs_refuses_fm1t_loader_env(tmp_path):
    _run2_dir(tmp_path)
    fake = crumbs_fake()
    code, _, opened = run(fake, ['crumbs'], tmp_path, environ={'FM1T_LOADER': 'x'})
    assert code == 1 and opened == [] and fake.wire == b''


CRUMBS_STOPS = {
    'uboot=0': ("status answers uboot=0: the transporter has not mounted the mask ROM. Keep "
                "the FM-1 ON and do not rekey: power-off clears the breadcrumbs. Replug the "
                "transporter's USB with the FM-1 left on (docs/19 section 7.6), wait for "
                "`UBOOT READY`, then run crumbs again"),
    'v15=1': ("status answers v15=1: the FM-1 booted V15 instead of returning to the mask ROM, "
              "so the breadcrumbs are lost (docs/19 section 7.6, R6 (c)). Send nothing else: "
              "photograph the unit, then power off (R8)"),
    'loader=1': ("status answers loader=1: the transporter holds the flash loader from an "
                 "earlier step. Keep the FM-1 ON and do not rekey. Replug the transporter's USB "
                 "with the FM-1 left on (docs/19 section 7.6), wait for `UBOOT READY`, then run "
                 "crumbs again"),
    'loader_running=1': ("status answers loader_running=1: the flash loader runs at 0x1c02000, "
                         "over the breadcrumbs, so they are lost. Send nothing else; power off "
                         "(docs/19 section 7.6, R8)"),
}


@pytest.mark.parametrize('kw,stop', [
    ({'uboot': False}, 'uboot=0'), ({'uboot': False, 'v15': True}, 'v15=1'),
    ({'uboot': True, 'v15': True}, 'v15=1'), ({'loader': True}, 'loader=1'),
    ({'loader_running': True}, 'loader_running=1'),
    ({'loader': True, 'loader_running': True}, 'loader_running=1')])
def test_crumbs_needs_the_rom_without_the_loader(tmp_path, kw, stop):
    """The stop text says exactly what to do. Where the breadcrumbs may still be
    in SRAM it never says to power off or rekey (USB_KEY_STEPS would)."""
    _run2_dir(tmp_path)
    fake = crumbs_fake(**kw)
    code, events, _ = run(fake, ['crumbs'], tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status']
    assert not (tmp_path / CRUMBS_LOCK).exists()
    assert events[-1]['verdict'] == 'STOP: ' + CRUMBS_STOPS[stop]
    if stop in ('uboot=0', 'loader=1'):
        assert 'power off' not in events[-1]['verdict'] and 'OFF, run' not in events[-1]['verdict']


def test_crumbs_err_reply_takes_no_lock_and_may_be_retried(tmp_path):
    """A stale mount (docs/19 section 7.6): the ROM read fails, nothing was
    read, so the read may be tried again; once DATA came, never again."""
    _run2_dir(tmp_path)
    fake = crumbs_fake()
    orig = fake._poll

    def stale(line, payload):
        if line.startswith('memr'):
            fake._tx('ERR memr at 01C05FC0')
            return
        orig(line, payload)
    fake._poll = stale
    code, events, _ = run(fake, ['crumbs'], tmp_path, log='first.jsonl')
    assert code == 3 and fake.lines == ['ping', 'status', 'memr 0x1c05fc0 48']
    assert 'no crumbs lock' in events[-1]['verdict'] and not (tmp_path / CRUMBS_LOCK).exists()
    assert 'Keep the FM-1 ON and do not rekey' in events[-1]['verdict']
    assert 'reading again is harmless' in events[-1]['verdict']
    code, events, _ = run(crumbs_fake(), ['crumbs'], tmp_path, log='second.jsonl')
    assert code == 0 and (tmp_path / CRUMBS_LOCK).exists()
    third = crumbs_fake()
    code, _, opened = run(third, ['crumbs'], tmp_path, log='third.jsonl')
    assert code == 1 and opened == [] and third.wire == b''


def test_crumbs_lock_created_by_a_parallel_read_stops_after_data(tmp_path):
    _run2_dir(tmp_path)
    fake = crumbs_fake()
    orig = fake._poll

    def racing(line, payload):
        if line.startswith('memr'):
            (tmp_path / CRUMBS_LOCK).write_text('{}\n')
        orig(line, payload)
    fake._poll = racing
    code, events, _ = run(fake, ['crumbs'], tmp_path)
    assert code == 3 and 'already attempted' in events[-1]['verdict']
    # The bytes were logged before the lock was tried, so they are kept.
    assert events[-1]['crumbs_hex'] == KIT_CRUMBS.hex()
    assert any(e['event'] == 'crumbs-raw' for e in events)
    assert (tmp_path / CRUMBS_LOCK).read_text() == '{}\n'


def test_crumbs_lock_is_taken_even_when_the_bytes_do_not_arrive(tmp_path):
    """DATA came, so the read happened: the lock is taken in a finally."""
    _run2_dir(tmp_path)
    fake = crumbs_fake()
    orig = fake._poll

    def short(line, payload):
        if line.startswith('memr'):
            fake._tx('DATA 48')
            fake.out += KIT_CRUMBS[:20]
            return
        orig(line, payload)
    fake._poll = short
    code, events, _ = run(fake, ['crumbs'], tmp_path)
    assert code == 3 and events[-1]['exit'] == 3
    assert (tmp_path / CRUMBS_LOCK).exists()


def test_nothing_is_sent_after_the_crumbs_read():
    link = t.Link(FakeTransporter(), 'crumbs', lambda *a, **k: None)
    link.request('ping', 1)
    link.send_line('memr 0x1c05fc0 48')
    for line in ('ping', 'status', 'memr 0x1c05fc0 48'):
        with pytest.raises(t.Refused, match='after the crumbs read'):
            link.send_line(line)


@pytest.mark.parametrize('line', [
    'memr 0x1c05fc0 47', 'memr 0x1c05fc0 49', 'memr 0x1c05fc0 048', 'memr 0x1c05fc0 0x30',
    'memr 0x01c05fc0 48', 'memr 0x1C05FC0 48', 'memr 0x1c05fc4 44', 'memr 0x1c02000 48',
    'memr 0x1c05000 4096', 'memr 0x1c05fc0 48 ', 'memw 0x1c05fc0 48 00000000',
    'memw 0x1c02000 4096 00000000', 'jump 0x1c02000 0x1', 'ldr 0 4096 00000000', 'info',
    'read 0x0 1048576', 'rekey'])
def test_crumbs_mode_sends_only_the_one_read(line):
    with pytest.raises(t.Refused):
        t.check_line('crumbs', line)
    assert t.check_line('crumbs', 'memr 0x1c05fc0 48') == 'crumbs_memr'


def test_the_crumbs_read_is_refused_outside_crumbs_mode():
    for mode in set(t.ALLOWED) - {'crumbs'}:
        with pytest.raises(t.Refused):
            t.check_line(mode, 'memr 0x1c05fc0 48')


# -- bounds ------------------------------------------------------------------

@pytest.mark.parametrize('line', [
    'memw 0x1c03000 3825 00000000',            # one byte past the image
    'memw 0x1c03000 4096 00000000', 'memr 0x1c03000 3825', 'memr 0x1c03000 4096',
    'memw 0x1c04000 4 00000000', 'memw 0x1c05000 4 00000000', 'memw 0x1c05fc0 4 00000000',
    'memw 0x1c03ef0 4 00000000', 'memw 0x1c02000 4097 00000000',
    'memr 0x1c04000 4', 'memr 0x1c05000 4',
    'memw 0x0 4 00000000', 'memw 0x2000 4 00000000', 'memw 0x2000000 4 00000000',
    'memw 0x1c00000 4 00000000', 'memw 0x1c01000 4 00000000',
    'jump 0x1c03000 0x1', 'jump 0x1c02000 0x0', 'jump 0x1c05fc0 0x1',
])
def test_writes_and_reads_outside_the_image_refused(line):
    for mode in t.ALLOWED:
        with pytest.raises(t.Refused):
            t.check_line(mode, line)


def test_image_range_admitted():
    for line in ('memw 0x1c02000 4096 0123ABCD', 'memw 0x1c03000 3824 0123ABCD',
                 'memr 0x1c03000 3824', 'memr 0x1c02000 4096'):
        assert t.check_line('ramrun', line) == line.split()[0]
    assert set(t._RAM_ADDRS.split('|')) == {'0x1c02000', '0x1c03000'}


@pytest.mark.parametrize('line', [
    'memw 0x1c02000 04096 0123ABCD', 'memw 0x1c03000 03824 0123ABCD',
    'memw 0x1c02000 0 0123ABCD', 'memr 0x1c03000 03824', 'memr 0x1c02000 0x10',
    'ldr 0 04096 0123ABCD', 'memr 0x1c05fc0 060'])
def test_lengths_the_transporter_would_read_differently_are_refused(line):
    for mode in t.ALLOWED:
        with pytest.raises(t.Refused):
            t.check_line(mode, line)


@pytest.mark.parametrize('mode', sorted(t.ALLOWED))
def test_forbidden_lines_unsendable_in_every_mode(mode):
    lines = ['uboot', 'k', 'runapp', 'wsec 0x4000 00000000', 'wsec 0x92000 DEADBEEF',
             'read 0x4000 4096', 'read 0x0 4096', 'read 0x0 16384', 'read 0x0 1048577',
             'status ', ' status', 'status\nuboot', 'ping\r', 'uboot ', 'UBOOT', 'wsec',
             'erase', 'write', 'selftest-write', '\xf0"$5}\xf7', 'F0 22 24 35 7D F7',
             'F0 22 24 35 7F F7', '5A AA A5', 'ldr 24064 1 00000000', '',
             'FC12', 'fc12', 'A1', 'efuse', 'efuse 0 0', 'memw 0x1c80108 4 00000000',
             'memr 0x1c80108 4', 'memw 0x0 16384 00000000']
    lines += [chr(c) for c in range(0x20, 0x7F)]       # console one-letter commands
    for line in lines:
        with pytest.raises(t.Refused):
            t.check_line(mode, line)


def test_random_and_mutated_lines_never_escape():
    rng = random.Random(13)
    allowed = re.compile('|'.join(t.PATTERNS.values()))
    seeds = ['ping', 'status', 'jump 0x1c02000 0x1', 'memw 0x1c03000 3824 0123ABCD',
             'memr 0x1c03000 3824', 'memr 0x1c05fc0 48', 'read 0x0 1048576']
    alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789x ABCDEF'
    for i in range(6000):
        if i % 2:
            line = ''.join(rng.choice(alphabet) for _ in range(rng.randint(1, 40)))
        else:
            chars = list(rng.choice(seeds))
            for _ in range(rng.randint(1, 3)):
                pos = rng.randrange(len(chars))
                if rng.random() < 0.5:
                    chars[pos] = rng.choice(alphabet)
                else:
                    chars.insert(pos, rng.choice(alphabet))
            line = ''.join(chars)
        for mode in t.ALLOWED:
            try:
                name = t.check_line(mode, line)
            except t.Refused:
                continue
            assert allowed.fullmatch(line) and name in t.ALLOWED[mode]
            if name in ('memw', 'memr'):
                addr, n = int(line.split()[1], 16), int(line.split()[2])
                assert 0x01C02000 <= addr and addr + n <= 0x01C03EF0 and 1 <= n <= 4096
            if name == 'crumbs_memr':
                assert line == 'memr 0x1c05fc0 48' and mode == 'crumbs'
            if name in ('memw', 'memr', 'ldr'):
                assert int(line.split()[2], 0) == int(line.split()[2])


# -- the gate holds the image ------------------------------------------------

def test_gate_holds_the_approved_image(approved):
    for n in (1, 2):
        for bad in (None, bytes(IMAGE_BYTES), IMG[n][:-1], IMG[n] + b'\0'):
            with pytest.raises(t.Refused, match='approved image of its run'):
                t.Link(FakeTransporter(), 'ramrun', lambda *a, **k: None, image=bad, run=n)
    fake = FakeTransporter()
    link = t.Link(fake, 'ramrun', lambda *a, **k: None, image=IMG[2], run=2)
    cs = chunks(2)
    with pytest.raises(t.Refused, match='before the whole approved image'):
        link.send_line('jump 0x1c02000 0x1')
    with pytest.raises(t.Refused, match='out of order'):
        link.send_line(memw_line(*cs[1]))
    link.send_line(memw_line(*cs[0]))
    link.send_payload(cs[0][1])
    assert link.recv_line(1) == 'OK'
    with pytest.raises(t.Refused, match='4096 of 7920'):
        link.send_line('jump 0x1c02000 0x1')
    other = IMG[1][4096:]
    link.send_line(memw_line(0x01C03000, other))
    with pytest.raises(t.Refused, match="not the approved image's bytes"):
        link.send_payload(other)
    assert max(fake.sram) == 0x01C02FFF


def test_nothing_sent_after_jump_and_no_resend(approved):
    fake = FakeTransporter()
    link = t.Link(fake, 'ramrun', lambda *a, **k: None, image=IMG[1], run=1)
    link.request('ping', 1)
    for addr, chunk in chunks(1):
        link.send_line(memw_line(addr, chunk))
        link.send_payload(chunk)
        assert link.recv_line(1) == 'OK'
    with pytest.raises(t.Refused, match='never resent'):
        link.send_line(memw_line(*chunks(1)[0]))
    link.request('jump 0x1c02000 0x1', 1)
    wire = bytes(fake.wire)
    for line in ('status', 'ping', 'jump 0x1c02000 0x1', 'memr 0x1c02000 64'):
        with pytest.raises(t.Refused, match='after the jump'):
            link.send_line(line)
    assert fake.wire == wire and fake.jumps == [(0x01C02000, 1)]


# -- the tool's shape --------------------------------------------------------

def test_link_is_the_only_writer_and_no_soft_key():
    tree = ast.parse(TOOL.read_text())
    writers = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == 'write'
                        and isinstance(sub.func.value, ast.Attribute)
                        and sub.func.value.attr == '_port'):
                    writers.append(node.name)
    assert set(writers) == {'Link', '_write'}
    data = TOOL.read_bytes()
    assert b'\xf0\x22\x24\x35\x7d\xf7' not in data and b'\xf0\x22\x24\x35\x7f\xf7' not in data
    text = TOOL.read_text()
    for banned in ('04 F0 22 24 07 35', '5A AA A5', '0xFC12', '0xfc12', '0xA1 ', 'wsec(',
                   'runapp(', 'eFuse'):
        assert banned not in text
