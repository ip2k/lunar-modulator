//! movy-oracle: replay a verb script through Movy's `seq-core` and write the
//! shared event log (docs/13 stage M3; tools/movy-oracle/README.md).
//!
//! Our code, MIT. It drives `seq_core::engine::Engine` the way
//! `engine/crates/movy-dsp/src/lib.rs` does at Movy 9190e79:
//!
//! * `Instance::new` builds `Engine::new(host rate, DEFAULT_BPM_X100 = 12000)`.
//! * `set_param("cmd", batch)` runs `command::apply_batch`. Its events wait in
//!   the instance's `out` until the next `render`, which first calls
//!   `advance_block(frames)` and then drains `out`. So a block's events are
//!   its command events, then its tick events, all at the block's first frame:
//!   Movy has no sample offsets.
//! * `set_param("state", text)` runs `persist::load` and clears `dirty`.
//! * Every FFI entry point catches panics, and the instance carries on.
//!
//! * `on_midi` hands Move's MIDI realtime bytes to
//!   `Engine::on_external_realtime`, whose events also wait for the next
//!   `render`. A script's `rt <F8|FA|FB|FC>` line does the same.
//!
//! The master tick of each event is not visible from outside the engine, so
//! a second engine replays the same script one frame per `advance_block` call
//! and attributes each event to its tick and frame. On the internal clock a
//! frame services a tick when the public `clock.tick` moves and the transport
//! plays. In a block that starts following an external clock, or ends it
//! (`Engine::status`, `ext=`, before and after the block's input; only that
//! input can turn following on, and handing back resets `clock.tick`), the
//! tick count itself (`tick=`) is read around every frame. A frame may service at most one
//! tick, which the internal clock always satisfies and an external clock does
//! while its tempo is steady. Every block is checked to produce exactly the
//! events of the whole-block run, which is the one reported.

use std::fmt::Write as _;
use std::fs;
use std::io::{self, Write as _};
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Mutex;

use seq_core::command::apply_batch;
use seq_core::engine::{Engine, OutEvent};
use seq_core::persist;

const DEFAULT_RATE: u32 = 44118;
const DEFAULT_BLOCK: u32 = 128;
const DEFAULT_TRACKS: u32 = 8;
/// `seq_core::track::NUM_TRACKS`.
const MOVY_TRACKS: u32 = 16;
/// `movy-dsp/src/lib.rs`, `DEFAULT_BPM_X100`.
const DEFAULT_BPM_X100: u32 = 12000;
/// Movy reports automation as CC 102 + lane (`movy-dsp/src/lib.rs`, drain_out).
const LOCK_CC_BASE: u32 = 102;

const USAGE: &str = "\
usage:
  movy-oracle run SCRIPT.verbs [-o OUT.jsonl] [--frames block|tick]
                               [--state SET.movy1] [--movy1-out FILE]
  movy-oracle batch IN_DIR OUT_DIR [--frames block|tick] [--movy1]
  movy-oracle files OUT_DIR SCRIPT.verbs... [--frames block|tick] [--movy1]

A script's sibling <stem>.in.movy1, if present, is loaded before block 0
(movy-dsp's `state` param); --state overrides it. --frames tick reports each
tick's own frame instead of the block start (the FM-1's D1 offsets). batch
and files write OUT_DIR/<stem>.jsonl (and <stem>.out.movy1 with --movy1) and
print one summary line per script on stdout.";

#[derive(Clone, Copy, PartialEq)]
enum FrameMode {
    Block,
    Tick,
}

struct Cmd {
    line: usize,
    frame: u64,
    text: String,
    /// `rt XX`: MIDI realtime input instead of a `cmd` batch.
    realtime: Option<u8>,
}

struct Script {
    rate: u32,
    block: u32,
    tracks: u32,
    /// `end=<frames>`: the run length. Without it the run ends with the block
    /// in which the last command is applied.
    end: Option<u64>,
    cmds: Vec<Cmd>,
}

/// `rt F8|FA|FB|FC` (hex, either case): the status byte.
fn parse_realtime(cmd: &str) -> Option<Result<u8, String>> {
    let rest = cmd.strip_prefix("rt")?;
    if !rest.starts_with(char::is_whitespace) {
        return None;
    }
    let arg = rest.trim();
    Some(match u8::from_str_radix(arg, 16) {
        Ok(b @ (0xF8 | 0xFA | 0xFB | 0xFC)) if arg.len() == 2 => Ok(b),
        _ => Err(format!("rt takes F8, FA, FB or FC, not {arg:?}")),
    })
}

fn parse_script(src: &str) -> Result<Script, String> {
    let mut s = Script {
        rate: DEFAULT_RATE,
        block: DEFAULT_BLOCK,
        tracks: DEFAULT_TRACKS,
        end: None,
        cmds: Vec::new(),
    };
    let mut header_seen = false;
    let mut last_frame = 0u64;
    for (i, raw) in src.lines().enumerate() {
        let n = i + 1;
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }
        if let Some(h) = line.strip_prefix("#!") {
            if header_seen {
                return Err(format!("line {n}: a second header"));
            }
            if !s.cmds.is_empty() {
                return Err(format!(
                    "line {n}: the header must come before the first command"
                ));
            }
            header_seen = true;
            for kv in h.split_whitespace() {
                let (k, v) = kv
                    .split_once('=')
                    .ok_or_else(|| format!("line {n}: header item {kv:?} is not key=value"))?;
                let v: u64 = v
                    .parse()
                    .map_err(|_| format!("line {n}: {k}={v:?} is not an unsigned integer"))?;
                let small = || {
                    u32::try_from(v).map_err(|_| format!("line {n}: {k}={v} is too large"))
                };
                match k {
                    "rate" => s.rate = small()?,
                    "block" => s.block = small()?,
                    "tracks" => s.tracks = small()?,
                    "end" => s.end = Some(v),
                    _ => return Err(format!("line {n}: unknown header key {k:?}")),
                }
            }
            continue;
        }
        if line.starts_with('#') {
            continue;
        }
        let rest = line
            .strip_prefix('@')
            .ok_or_else(|| format!("line {n}: expected '@<frame> <command>'"))?;
        let (f, cmd) = rest
            .split_once(char::is_whitespace)
            .ok_or_else(|| format!("line {n}: expected '@<frame> <command>'"))?;
        let frame: u64 = f
            .parse()
            .map_err(|_| format!("line {n}: frame {f:?} is not an unsigned integer"))?;
        let cmd = cmd.trim();
        if cmd.is_empty() {
            return Err(format!("line {n}: no command"));
        }
        if cmd.contains(';') {
            return Err(format!(
                "line {n}: one command per line (';' would split Movy's batch)"
            ));
        }
        if cmd.starts_with('#') {
            return Err(format!(
                "line {n}: a command may not start with '#' (Movy's batch tag)"
            ));
        }
        if frame < last_frame {
            return Err(format!(
                "line {n}: frame {frame} is before the previous command's {last_frame}"
            ));
        }
        last_frame = frame;
        let realtime = parse_realtime(cmd)
            .transpose()
            .map_err(|e| format!("line {n}: {e}"))?;
        s.cmds.push(Cmd {
            line: n,
            frame,
            text: cmd.to_string(),
            realtime,
        });
    }
    if !(1000..=768_000).contains(&s.rate) {
        return Err(format!("rate={} is outside 1000..768000", s.rate));
    }
    if !(1..=8192).contains(&s.block) {
        return Err(format!("block={} is outside 1..8192", s.block));
    }
    if !(1..=MOVY_TRACKS).contains(&s.tracks) {
        return Err(format!("tracks={} is outside 1..{MOVY_TRACKS}", s.tracks));
    }
    if s.cmds.is_empty() && s.end.is_none() {
        return Err("the script has no commands and no end=, so it has no length".into());
    }
    Ok(s)
}

// ── Panics ───────────────────────────────────────────────────────────────
// movy-dsp's `guard` catches a panic at the FFI boundary and the instance
// keeps running in whatever state the panic left. The oracle does the same,
// and reports each one.

static PANIC_MSG: Mutex<Option<String>> = Mutex::new(None);

fn install_panic_hook() {
    panic::set_hook(Box::new(|info| {
        let p = info.payload();
        let msg = if let Some(s) = p.downcast_ref::<&str>() {
            (*s).to_string()
        } else if let Some(s) = p.downcast_ref::<String>() {
            s.clone()
        } else {
            "panic".to_string()
        };
        let loc = info
            .location()
            .map(|l| {
                let f = l.file();
                let f = f.find("seq-core/").map_or(f, |i| &f[i..]);
                format!(" at {}:{}", f, l.line())
            })
            .unwrap_or_default();
        if let Ok(mut g) = PANIC_MSG.lock() {
            *g = Some(format!("{msg}{loc}"));
        }
    }));
}

fn guarded<F: FnOnce()>(f: F) -> Option<String> {
    match panic::catch_unwind(AssertUnwindSafe(f)) {
        Ok(()) => None,
        Err(_) => Some(
            PANIC_MSG
                .lock()
                .ok()
                .and_then(|mut g| g.take())
                .unwrap_or_else(|| "panic".to_string()),
        ),
    }
}

// ── Output ───────────────────────────────────────────────────────────────

fn json_str(s: &str) -> String {
    let mut o = String::with_capacity(s.len() + 2);
    o.push('"');
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\r' => o.push_str("\\r"),
            '\t' => o.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                let _ = write!(o, "\\u{:04x}", c as u32);
            }
            c => o.push(c),
        }
    }
    o.push('"');
    o
}

fn opt(v: Option<u32>) -> String {
    v.map_or_else(|| "null".to_string(), |x| x.to_string())
}

struct Log {
    text: String,
    events: u64,
    tracks: u32,
}

impl Log {
    fn emit(&mut self, block: u64, frame: u64, tick: u64, ev: OutEvent) -> Result<(), String> {
        let (kind, track, a, b): (&str, Option<u8>, Option<u32>, Option<u32>) = match ev {
            OutEvent::NoteOn { track, pitch, vel } => {
                ("on", Some(track), Some(pitch as u32), Some(vel as u32))
            }
            OutEvent::NoteOff { track, pitch } => ("off", Some(track), Some(pitch as u32), None),
            OutEvent::Cc { track, lane, val } => (
                "cc",
                Some(track),
                Some(LOCK_CC_BASE + lane as u32),
                Some(val as u32),
            ),
            OutEvent::Click { accent } => ("click", None, Some(accent as u32), None),
            OutEvent::Start => ("start", None, None, None),
            OutEvent::Stop => ("stop", None, None, None),
            OutEvent::Clock => ("clock", None, None, None),
            OutEvent::MoveInject { .. } => {
                return Err(format!(
                    "block {block}: a MoveInject event; the shared format has no kind for it \
                     (do not send `link 1` with `minject 1`)"
                ))
            }
        };
        if let Some(t) = track {
            if t as u32 >= self.tracks {
                return Err(format!(
                    "block {block}: an event on track {t}, but the script declares tracks={}",
                    self.tracks
                ));
            }
        }
        let _ = writeln!(
            self.text,
            "{{\"block\":{block},\"frame\":{frame},\"tick\":{tick},\"kind\":\"{kind}\",\"track\":{},\"a\":{},\"b\":{}}}",
            opt(track.map(u32::from)),
            opt(a),
            opt(b)
        );
        self.events += 1;
        Ok(())
    }
}

/// A field of the status line the UI polls (`Engine::status`, `&self`).
fn status_field(e: &Engine, key: &str) -> Result<u64, String> {
    let s = e.status();
    s.split_whitespace()
        .find_map(|kv| kv.strip_prefix(key))
        .and_then(|v| v.parse().ok())
        .ok_or_else(|| format!("status has no {key} field"))
}

/// Movy's private `master_tick` (`tick=`).
fn master_tick(e: &Engine) -> Result<u64, String> {
    status_field(e, "tick=")
}

struct RunOut {
    log: String,
    summary: String,
    movy1: String,
}

fn run_length(script: &Script) -> Result<u64, String> {
    // An explicit end may intentionally exclude later commands. Do not
    // evaluate the implicit length at all in that case.
    if let Some(end) = script.end {
        return Ok(end);
    }
    let block = script.block as u64;
    let last = script.cmds.last().map_or(0, |c| c.frame);
    // Include the whole block whose start is at or after the last command.
    // Keep harness arithmetic checked even under Movy's release semantics.
    last.div_ceil(block)
        .checked_add(1)
        .and_then(|blocks| blocks.checked_mul(block))
        .ok_or_else(|| {
            format!(
                "default run length exceeds u64 for frame {last} and block {block}; \
                 specify end= to limit the run"
            )
        })
}

fn run(
    script: &Script,
    state: Option<&str>,
    mode: FrameMode,
    name: &str,
) -> Result<RunOut, String> {
    let total = run_length(script)?;
    // A: the reported run, whole blocks, as movy-dsp. B: one frame per call.
    let mut a = Engine::new(script.rate, DEFAULT_BPM_X100);
    let mut b = Engine::new(script.rate, DEFAULT_BPM_X100);
    if let Some(text) = state {
        if !persist::load(&mut a, text) || !persist::load(&mut b, text) {
            return Err("the state file is not a movy1 set".into());
        }
        a.dirty = false;
        b.dirty = false;
    }
    let mut log = Log {
        text: String::new(),
        events: 0,
        tracks: script.tracks,
    };
    let mut panics: Vec<String> = Vec::new();
    let block = script.block as u64;
    // The last command lands before the first block starting at or after its
    // frame; that block is the last one run. With end=, the run is that many
    // frames: whole blocks, the last one shorter if need be, and a command
    // due at the end frame itself is applied after them.

    let mut out_a: Vec<OutEvent> = Vec::with_capacity(256);
    let mut out_b: Vec<OutEvent> = Vec::with_capacity(256);
    let mut sub: Vec<OutEvent> = Vec::with_capacity(64);
    let mut tagged: Vec<(u64, u64, OutEvent)> = Vec::with_capacity(256);
    let mut ci = 0usize;
    let mut bi = 0u64;
    let mut start = 0u64;
    let mut was_following = false;

    loop {
        // Commands due by this block's start, each one `set_param("cmd")`,
        // or for `rt`, one `on_midi` byte.
        while ci < script.cmds.len() && script.cmds[ci].frame <= start {
            let c = &script.cmds[ci];
            let tick = master_tick(&a)?;
            let (pa, pb) = match c.realtime {
                Some(status) => (
                    guarded(|| a.on_external_realtime(status, &mut out_a)),
                    guarded(|| b.on_external_realtime(status, &mut out_b)),
                ),
                None => (
                    guarded(|| apply_batch(&mut a, &c.text, &mut out_a)),
                    guarded(|| apply_batch(&mut b, &c.text, &mut out_b)),
                ),
            };
            if pa != pb || out_a != out_b {
                return Err(format!(
                    "line {}: the two engines disagree on {:?}",
                    c.line, c.text
                ));
            }
            if let Some(p) = pa {
                panics.push(format!(
                    "{{\"block\":{bi},\"frame\":{start},\"line\":{},\"cmd\":{},\"panic\":{}}}",
                    c.line,
                    json_str(&c.text),
                    json_str(&p)
                ));
            }
            for ev in out_a.drain(..) {
                log.emit(bi, start, tick, ev)?;
            }
            out_b.clear();
            ci += 1;
        }

        if start >= total {
            break;
        }

        // The block itself.
        let frames = block.min(total - start);
        let pa = guarded(|| a.advance_block(frames as u32, &mut out_a));
        let mut mt = master_tick(&b)?;
        // Following can only start with a block's realtime input, and only
        // the block after following stops hands back to the internal clock,
        // so any other block runs on the internal clock throughout.
        let follows = was_following || status_field(&b, "ext=")? != 0;
        let mut pb = None;
        tagged.clear();
        for j in 0..frames {
            let before = mt;
            let t0 = b.clock.tick;
            let p = guarded(|| b.advance_block(1, &mut sub));
            if pb.is_none() {
                pb = p;
            }
            if follows {
                mt = master_tick(&b)?;
            } else if b.clock.tick.wrapping_sub(t0) > 1 {
                return Err(format!("block {bi}: two ticks in one frame"));
            } else if b.clock.tick != t0 && b.playing {
                mt += 1;
            }
            // Every event of a frame that serviced a tick belongs to that
            // tick: its F8, its service_tick and step_tick output, and a Start
            // pushed in the same call (which is then tick 0). Other events
            // carry the ticks serviced so far. A count that went down is a
            // restart inside advance_block (following an external clock from
            // its next bar); its events precede the restart.
            let fired = if mt >= before { mt - before } else { mt };
            if fired > 1 {
                return Err(format!(
                    "block {bi}: {fired} ticks in one frame (an external clock's tempo jumped?)"
                ));
            }
            if mt < before && fired > 0 {
                return Err(format!("block {bi}: a restart and a tick in one frame"));
            }
            for ev in sub.drain(..) {
                tagged.push((j, before, ev));
            }
        }
        // movy-dsp would drain a panicked block's events one block late; no
        // script has reached such a panic, so it stops the run rather than
        // producing a trace that places them differently.
        if let Some(p) = pa.as_ref().or(pb.as_ref()) {
            return Err(format!("block {bi}: Movy panicked in advance_block: {p}"));
        }
        let same =
            out_a.len() == tagged.len() && out_a.iter().zip(&tagged).all(|(x, (_, _, y))| x == y);
        if !same {
            return Err(format!(
                "block {bi}: the whole-block and frame-by-frame runs differ \
                 (whole: {} events, by frame: {} events)",
                out_a.len(),
                tagged.len()
            ));
        }
        let ma = master_tick(&a)?;
        if ma != mt || a.clock.tick != b.clock.tick {
            return Err(format!("block {bi}: tick bookkeeping lost sync ({ma}, {mt})"));
        }
        for &(j, t, ev) in &tagged {
            let frame = match mode {
                FrameMode::Block => start,
                FrameMode::Tick => start + j,
            };
            log.emit(bi, frame, t, ev)?;
        }
        out_a.clear();
        was_following = status_field(&b, "ext=")? != 0;
        start += frames;
        bi += 1;
    }

    let end_tick = master_tick(&a)?;
    let summary = format!(
        "{{\"script\":{},\"rate\":{},\"block\":{},\"tracks\":{},\"blocks\":{},\"events\":{},\"end_tick\":{},\"panics\":[{}]}}",
        json_str(name),
        script.rate,
        script.block,
        script.tracks,
        bi,
        log.events,
        end_tick,
        panics.join(",")
    );
    Ok(RunOut {
        log: log.text,
        summary,
        movy1: persist::serialize(&a),
    })
}

// ── CLI ──────────────────────────────────────────────────────────────────

fn sibling_state(script: &Path) -> Option<PathBuf> {
    let stem = script.file_stem()?.to_str()?;
    let p = script.with_file_name(format!("{stem}.in.movy1"));
    p.is_file().then_some(p)
}

fn read(p: &Path) -> Result<String, String> {
    fs::read_to_string(p).map_err(|e| format!("{}: {e}", p.display()))
}

fn write(p: &Path, s: &str) -> Result<(), String> {
    fs::write(p, s).map_err(|e| format!("{}: {e}", p.display()))
}

fn run_file(path: &Path, state: Option<&Path>, mode: FrameMode) -> Result<RunOut, String> {
    let name = path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("?")
        .to_string();
    let script = parse_script(&read(path)?).map_err(|e| format!("{}: {e}", path.display()))?;
    let state_path = state.map(Path::to_path_buf).or_else(|| sibling_state(path));
    let state_text = match &state_path {
        Some(p) => Some(read(p)?),
        None => None,
    };
    run(&script, state_text.as_deref(), mode, &name).map_err(|e| format!("{}: {e}", path.display()))
}

fn parse_frames(v: Option<&String>) -> Result<FrameMode, String> {
    match v.map(String::as_str) {
        Some("block") => Ok(FrameMode::Block),
        Some("tick") => Ok(FrameMode::Tick),
        _ => Err("--frames takes block or tick".into()),
    }
}

fn main_inner(args: &[String]) -> Result<bool, String> {
    let mut mode = FrameMode::Block;
    let mut out: Option<PathBuf> = None;
    let mut state: Option<PathBuf> = None;
    let mut movy1_out: Option<PathBuf> = None;
    let mut movy1 = false;
    let mut pos: Vec<&String> = Vec::new();
    let mut it = args.iter();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--frames" => mode = parse_frames(it.next())?,
            "-o" => out = Some(it.next().ok_or("-o takes a file")?.into()),
            "--state" => state = Some(it.next().ok_or("--state takes a file")?.into()),
            "--movy1-out" => movy1_out = Some(it.next().ok_or("--movy1-out takes a file")?.into()),
            "--movy1" => movy1 = true,
            "-h" | "--help" => {
                println!("{USAGE}");
                return Ok(true);
            }
            s if s.starts_with('-') => return Err(format!("unknown option {s}\n{USAGE}")),
            _ => pos.push(a),
        }
    }
    match pos.first().map(|s| s.as_str()) {
        Some("run") if pos.len() == 2 => {
            let r = run_file(Path::new(pos[1]), state.as_deref(), mode)?;
            match &out {
                Some(p) => write(p, &r.log)?,
                None => io::stdout()
                    .write_all(r.log.as_bytes())
                    .map_err(|e| e.to_string())?,
            }
            if let Some(p) = &movy1_out {
                write(p, &r.movy1)?;
            }
            eprintln!("{}", r.summary);
            Ok(true)
        }
        Some("batch") if pos.len() == 3 => {
            let ind = Path::new(pos[1]);
            let mut scripts: Vec<PathBuf> = fs::read_dir(ind)
                .map_err(|e| format!("{}: {e}", ind.display()))?
                .filter_map(|e| e.ok().map(|e| e.path()))
                .filter(|p| p.extension().is_some_and(|x| x == "verbs"))
                .collect();
            scripts.sort();
            run_many(Path::new(pos[2]), &scripts, mode, movy1)
        }
        Some("files") if pos.len() >= 2 => {
            let scripts: Vec<PathBuf> = pos[2..].iter().map(PathBuf::from).collect();
            run_many(Path::new(pos[1]), &scripts, mode, movy1)
        }
        _ => Err(USAGE.to_string()),
    }
}

/// Run each script into `outd`. A failing script is reported on stderr and
/// the rest still run; the result is false if any failed.
fn run_many(
    outd: &Path,
    scripts: &[PathBuf],
    mode: FrameMode,
    movy1: bool,
) -> Result<bool, String> {
    fs::create_dir_all(outd).map_err(|e| format!("{}: {e}", outd.display()))?;
    let mut ok = true;
    for p in scripts {
        let stem = p
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("?")
            .to_string();
        match run_file(p, None, mode) {
            Ok(r) => {
                write(&outd.join(format!("{stem}.jsonl")), &r.log)?;
                if movy1 {
                    write(&outd.join(format!("{stem}.out.movy1")), &r.movy1)?;
                }
                println!("{}", r.summary);
            }
            Err(e) => {
                eprintln!("movy-oracle: {e}");
                ok = false;
            }
        }
    }
    Ok(ok)
}

fn main() -> ExitCode {
    install_panic_hook();
    let args: Vec<String> = std::env::args().skip(1).collect();
    match main_inner(&args) {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::from(1),
        Err(e) => {
            eprintln!("movy-oracle: {e}");
            ExitCode::from(2)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn implicit_length_includes_the_command_block() {
        for (last, expected) in [(0, 128), (1, 256), (128, 256), (129, 384)] {
            let script = parse_script(&format!("@{last} stop\n")).unwrap();
            assert_eq!(run_length(&script).unwrap(), expected);
        }
    }

    #[test]
    fn implicit_length_checks_addition_and_multiplication_boundaries() {
        for block in [1u64, 2, 128, 8192] {
            let largest_total = u64::MAX / block * block;
            let last = largest_total - block;
            let script = parse_script(&format!("#! block={block}\n@{last} stop\n")).unwrap();
            assert_eq!(run_length(&script).unwrap(), largest_total);

            // One frame later needs one more whole block than u64 can hold.
            for rejected in [last + 1, u64::MAX] {
                let script =
                    parse_script(&format!("#! block={block}\n@{rejected} stop\n")).unwrap();
                let error = run_length(&script).unwrap_err();
                assert!(error.contains("default run length exceeds u64"), "{error}");
            }
        }
    }

    #[test]
    fn impossible_implicit_run_fails_before_replay() {
        let script = parse_script("#! block=1\n@18446744073709551615 play\n").unwrap();
        let error = run(&script, None, FrameMode::Block, "overflow.verbs")
            .err()
            .unwrap();
        assert!(error.contains("default run length exceeds u64"), "{error}");
    }

    #[test]
    fn explicit_end_avoids_unused_implicit_overflow() {
        for block in [1, 128, 8192] {
            let script = parse_script(&format!(
                "#! block={block} end=0\n@18446744073709551615 play\n"
            ))
            .unwrap();
            assert_eq!(run_length(&script).unwrap(), 0);
            let output = run(&script, None, FrameMode::Block, "limited.verbs").unwrap();
            assert!(output.log.is_empty());
            assert!(output.summary.contains("\"blocks\":0,\"events\":0"));
        }
        let script = parse_script("#! end=18446744073709551615\n").unwrap();
        assert_eq!(run_length(&script).unwrap(), u64::MAX);
    }
}
