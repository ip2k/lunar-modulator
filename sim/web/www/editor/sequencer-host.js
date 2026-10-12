// Native project transactions and offline export for the Song workspace. MIT.
import { parseSet, writeSet, validateSet } from './sequence-model.js';
import { exportAudio as renderAudio } from './audio-export.js';

const encoder = new TextEncoder();
const stableSet = (set) => JSON.stringify(writeSet(parseSet(set)));
const stableValue = (v) => Array.isArray(v) ? v.map(stableValue) : v && typeof v === 'object'
  ? Object.fromEntries(Object.keys(v).sort().map(k => [k, stableValue(v[k])])) : v;
const projectState = (text) => {
  const doc = JSON.parse(text);
  doc.set = writeSet(parseSet(doc.set));
  return JSON.stringify(stableValue(doc));
};
const message = (r) => r?.report?.message || r?.error || 'The native sequencer refused this project.';

export function makeSequencerHost({ sim, files, st, history, snapshot, say, onSettled }) {
  let busy = false;
  let observedGen = sim.seq?.contentGen, panelTimer = 0;
  const versions = new WeakMap();
  const css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = new URL('sequencer-host.css', import.meta.url).href;
  document.head.append(css);

  // Native sequencer edits have their own generation, separate from parameter
  // history and playback ticks. Coalesce recording/knob bursts without polling
  // or serializing a project during unchanged playback. The callback also
  // invalidates a hidden workspace so it refreshes when reopened.
  sim.seqListeners ||= new Set();
  sim.seqListeners.add(transport => {
    const gen = transport.contentGen;
    if (!Number.isInteger(gen) || gen < 0 || gen > 0xffffffff) return;
    const changed = observedGen !== undefined && observedGen !== gen;
    observedGen = gen;
    if (!changed || panelTimer) return;
    panelTimer = setTimeout(() => {
      panelTimer = 0;
      // An in-flight host transaction already refreshes on settlement.
      if (sim.node && !busy) onSettled?.();
    }, 100);
  });

  async function fetchProject() {
    // Initial load notifications can invalidate a snapshot that is already
    // in flight. Retrying a read is safe; write transactions never retry.
    for (let attempt = 0; attempt < 3; attempt++) {
      const node = sim.node;
      if (!node) throw new Error('Power on the simulator first.');
      const gen = st.gen;
      const snap = await files.projectSnapshot();
      if (sim.node !== node) throw new Error('The simulator restarted while reading. Open the Song view again.');
      if (st.gen !== gen) continue;
      const doc = JSON.parse(snap.text);
      versions.set(doc, { gen, hash: snap.hash });
      return doc;
    }
    throw new Error('The project kept changing while reading. Retry the edit.');
  }

  async function loadChecked(doc, options = {}, expectedCurrent) {
    const model = parseSet(doc.set);
    const verdict = validateSet(model);
    if (!verdict.valid) throw new Error(verdict.errors.join('; '));
    if (model.unknown.length) throw new Error('This set contains extensions the native editor cannot preserve. Export a backup before editing it.');
    const gen = st.gen;
    const snap = await files.projectSnapshot();
    if (st.gen !== gen || (versions.has(doc) && versions.get(doc).hash !== snap.hash)) {
      throw new Error('The project changed while checking. Retry the edit.');
    }
    if (expectedCurrent !== undefined && projectState(snap.text) !== projectState(expectedCurrent)) {
      throw new Error('The project changed after this sequencer edit. Undo or redo would overwrite later changes.');
    }
    const before = snap.text;
    const old = await files.shadow('pack', { text: before });
    if (!old.ok) throw new Error(message(old));
    const bytes = encoder.encode(JSON.stringify(doc));
    if (bytes.length > 256 * 1024) throw new Error('The project exceeds Lunar’s 256 KiB text-file limit.');
    const checked = await files.shadow('check', { bytes, kind: 1, into: 0, slot: 0, flags: 0, live: old.bin });
    if (!checked.ok) throw new Error(message(checked));
    const candidate = await files.shadow('save', { kind: 1, arg: 0, live: checked.bin });
    if (!candidate.ok) throw new Error(message(candidate));
    // C's importer has bounded pools. Prove it kept every sequencer field
    // before replacing the running project, including notes and lock lanes.
    if (stableSet(JSON.parse(candidate.text).set) !== stableSet(doc.set)) {
      throw new Error('The native sequencer could not preserve this set exactly. Nothing was loaded.');
    }
    if (st.gen !== gen) throw new Error('The project changed while checking. Retry the edit.');
    st.ab.quietUntil = performance.now() + 1500;
    const result = await files.load(bytes, { name: files.fileName('project'), ask: false, before: false, quiet: true, same: true, ...options, expectedHash: snap.hash });
    if (!result.ok) throw new Error(message(result));
    await snapshot();
    return { before, after: await files.saveText('project') };
  }

  async function applyProject(doc, label = 'Edit sequencer') {
    if (busy) throw new Error('Finish the current sequencer edit first.');
    if (versions.has(doc) && versions.get(doc).gen !== st.gen) throw new Error('The project changed. Retry with its latest state.');
    busy = st.sequenceBusy = true;
    try {
      const { before, after } = await loadChecked(doc);
      if (before !== after) history.record({ target: 'sequencer', label, before: 'before', after: 'after', origin: 'editor', how: 'sequence',
        info: { struct: true, sequencer: true, beforeText: before, afterText: after } });
      say(label);
      return JSON.parse(after);
    } finally { busy = st.sequenceBusy = false; onSettled?.(); }
  }

  async function restoreHistory(entry, redo) {
    if (busy) return false;
    busy = st.sequenceBusy = true;
    try {
      await loadChecked(JSON.parse(redo ? entry.info.afterText : entry.info.beforeText), {},
        redo ? entry.info.beforeText : entry.info.afterText);
      say(`${redo ? 'Redone' : 'Undone'}: ${entry.label}`);
      return true;
    } catch (err) { say(err.message, true); return false; }
    finally { busy = st.sequenceBusy = false; onSettled?.(); }
  }

  function download(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = name;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  async function exportFile(format) {
    const set = format === 'movy1';
    download(new Blob([await files.saveText(set ? 'set' : 'project')], { type: set ? 'text/plain' : 'application/json' }),
      files.fileName(set ? 'set' : 'project'));
  }
  function openFile() {
    const input = document.createElement('input'); input.type = 'file'; input.accept = '.lunar,.movy1';
    input.addEventListener('change', async () => {
      const file = input.files?.[0]; if (!file) return;
      let owned = false;
      try {
        if (file.size > 256 * 1024) throw new Error('The project exceeds Lunar’s text-file limit.');
        const bytes = new Uint8Array(await file.arrayBuffer());
        const d = files.describe(bytes, file.name);
        if (d.enc !== 1 && !['project', 'set'].includes(d.kind)) throw new Error('Open a .lunar project or .movy1 sequencer set here.');
        if (busy) throw new Error('Finish the current sequencer edit first.');
        busy = st.sequenceBusy = owned = true;
        let doc;
        if (d.enc === 1) {
          const snap = await files.projectSnapshot();
          const live = await files.shadow('pack', { text: snap.text });
          if (!live.ok) throw new Error(message(live));
          const checked = await files.shadow('check', { bytes, kind: 0, into: 0, slot: 0, flags: 0, live: live.bin });
          if (!checked.ok) throw new Error(message(checked));
          if (checked.report?.kind !== 'project') throw new Error('Open a complete .lunar project or .movy1 sequencer set here.');
          const saved = await files.shadow('save', { kind: 1, arg: 0, live: checked.bin });
          if (!saved.ok) throw new Error(message(saved));
          doc = JSON.parse(saved.text);
        } else {
          const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
          doc = d.kind === 'project' ? JSON.parse(text) : await fetchProject();
          if (d.kind === 'set') doc.set = text.split(/\r?\n/).filter(Boolean);
        }
        await loadChecked(doc, { name: file.name, ui: true, same: false, before: true });
        history.clear();
        say(`Opened ${file.name}`);
      } catch (err) { say(err.message, true); }
      finally { if (owned) { busy = st.sequenceBusy = false; onSettled?.(); } input.remove(); }
    });
    input.click();
  }

  function exportAudio() {
    const existing = document.querySelector('dialog.sq-export');
    if (existing) { existing.focus(); return existing; }
    const urls = new Set();
    let retainedBytes = 0;
    const dialog = document.createElement('dialog'); dialog.className = 'sq-export';
    dialog.setAttribute('aria-label', 'Export audio');
    const heading = document.createElement('h2'); heading.textContent = 'Export audio';
    const note = document.createElement('p'); note.textContent = 'One complete song pass, followed by an effect tail. Stems include inserts and bypass master effects; nonlinear master processing can make their sum differ from the stereo master.';
    const form = document.createElement('form'); form.method = 'dialog';
    const choices = [];
    for (const [mode, label] of [['mix', 'Stereo master'], ['sound-stems', 'Four stereo sound stems'], ['multichannel', 'Multichannel WAV (four stereo sounds, eight channels)'], ['track-stems', 'Eight sequencer-track stems']]) {
      const line = document.createElement('label'); const check = document.createElement('input');
      check.type = 'checkbox'; check.checked = mode !== 'track-stems'; check.dataset.mode = mode;
      line.append(check, document.createTextNode(label)); form.append(line); choices.push(check);
    }
    const tailLabel = document.createElement('label'); tailLabel.textContent = 'Effect tail (seconds) ';
    const tail = document.createElement('input'); tail.type = 'number'; tail.min = '0'; tail.max = '30'; tail.step = '1'; tail.value = '3';
    tailLabel.append(tail); form.append(tailLabel);
    const status = document.createElement('p'); status.setAttribute('role', 'status'); status.dataset.testid = 'audio-export-status';
    const progress = document.createElement('progress'); progress.max = 1; progress.value = 0;
    const results = document.createElement('ul'); results.dataset.testid = 'audio-export-files';
    const start = document.createElement('button'); start.type = 'button'; start.textContent = 'Render WAVs'; start.dataset.testid = 'audio-export-start';
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.textContent = 'Close';
    const actions = document.createElement('div'); actions.className = 'sq-export-actions'; actions.append(start, cancel);
    form.append(status, progress, results, actions); dialog.append(heading, note, form); document.body.append(dialog);
    let controller = null;
    const clearResults = () => { for (const url of urls) URL.revokeObjectURL(url); urls.clear(); retainedBytes = 0; results.replaceChildren(); };
    const dispose = () => { clearResults(); dialog.remove(); };
    dialog.addEventListener('close', dispose);
    dialog.addEventListener('cancel', (e) => { if (controller) { e.preventDefault(); controller.abort(); } });
    cancel.onclick = () => { if (controller) controller.abort(); else dialog.close(); };
    start.onclick = async () => {
      const modes = choices.filter((c) => c.checked).map((c) => c.dataset.mode);
      const tailSeconds = Number(tail.value);
      if (!modes.length || !Number.isFinite(tailSeconds) || tailSeconds < 0 || tailSeconds > 30) { status.textContent = 'Choose a format and a tail between 0 and 30 seconds.'; return; }
      clearResults();
      controller = new AbortController(); start.disabled = true; cancel.textContent = 'Cancel render';
      for (const c of choices) c.disabled = true; tail.disabled = true;
      try {
        const project = await fetchProject();
        for (let i = 0; i < modes.length; ++i) {
          const result = await renderAudio({ project, mode: modes[i], tail: tailSeconds, sampleRate: 44118, masterVolume: sim.master,
            signal: controller.signal, onProgress: (p) => { progress.value = (i + (typeof p === 'number' ? p : p.fraction || 0)) / modes.length; status.textContent = `Rendering ${modes[i]}…`; },
            onFile: (file) => {
              if (retainedBytes + file.blob.size > 256 * 1024 * 1024) throw new Error('Downloads exceed the 256 MiB memory limit. Download these files, then render the remaining formats separately.');
              retainedBytes += file.blob.size;
              const li = document.createElement('li'); const a = document.createElement('a'); const url = URL.createObjectURL(file.blob); urls.add(url);
              a.href = url; a.download = file.name; a.textContent = `${file.name} · ${file.channels} channels`; li.append(a); results.append(li);
              a.click();
            } });
          if (result.warnings?.length) { const li = document.createElement('li'); li.textContent = result.warnings.join(' '); results.append(li); }
        }
        progress.value = 1; status.textContent = 'WAV downloads started. If your browser blocks multiple downloads, allow them or use the file links below.';
      } catch (err) { status.textContent = controller.signal.aborted ? 'Render cancelled.' : err.message; }
      finally { controller = null; start.disabled = false; cancel.textContent = 'Close'; for (const c of choices) c.disabled = false; tail.disabled = false; }
    };
    dialog.showModal();
    return dialog;
  }

  const verb = (text) => { if (sim.node) sim.node.port.postMessage({ type: 'seq-line', bytes: encoder.encode(text) }); };
  return { fetchProject, applyProject, restoreHistory, openFile, exportFile, exportAudio,
    getTransport: () => sim.seq || {}, playPause: () => verb(sim.seq?.playing ? 'pause' : 'resume'), restart: () => { verb('rewind'); verb('resume'); }, play: () => verb('resume'), pause: () => verb('pause'), stop: () => verb('rewind'), seekBar: bar => verb(`seekbar ${bar}`), get busy() { return busy; } };
}
