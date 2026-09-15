"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    ready: false, maxBytes: 8 * 1024 * 1024,
    portsBusy: false, identityBusy: false, portsGeneration: 0,
    ports: {inputs: [], outputs: []}, identity: null,
    file: null, inspection: null, inspectionGeneration: 0, inspectionController: null,
    events: [], droppedEvents: 0, exportGeneration: 0, exportFilename: "",
    source: null, patches: [], preview: null, workBusy: false,
    project: null, revisionId: null, projects: [], maxProjectBytes: 64 * 1024 * 1024,
    hexGeneration: 0, hexPosition: 0, hexLength: 256,
  };

  function node(tag, className, value) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (value !== undefined) result.textContent = String(value);
    return result;
  }
  function message(id, value, isError = false) {
    $(id).textContent = value;
    $(id).classList.toggle("error", isError);
  }
  function badge(id, value, status = "") {
    $(id).textContent = value;
    $(id).className = `quiet-badge ${status}`.trim();
  }
  function printable(value) {
    if (value === undefined || value === null) return "Not reported";
    if (typeof value === "boolean") return value ? "Passed" : "Failed";
    return typeof value === "object" ? JSON.stringify(value) : String(value);
  }
  function size(bytes) {
    if (!Number.isFinite(bytes)) return "Unknown size";
    if (bytes < 1024) return `${bytes.toLocaleString()} B`;
    return `${(bytes / (bytes < 1048576 ? 1024 : 1048576)).toFixed(2)} ${bytes < 1048576 ? "KiB" : "MiB"}`;
  }
  function offset(value) {
    return Number.isInteger(value) ? `0x${value.toString(16).toUpperCase().padStart(6, "0")}` : printable(value);
  }
  function fileName(file) {
    // A browser File.name is a basename; also strip separators defensively.
    return file.name.split(/[\\/]/).pop();
  }
  function fm1Port(name) {
    return /(^|[^\w-])FM-1(?![\w-])/i.test(name) && !/ota|ble|bluetooth/i.test(name);
  }
  function selectedFm1Ports() {
    return fm1Port($("input-port").value) && fm1Port($("output-port").value);
  }
  async function api(path, options = {}) {
    const response = await fetch(path, {cache: "no-store", credentials: "same-origin", ...options});
    let body;
    try { body = await response.json(); }
    catch (_) { throw new Error(`The local service returned an unreadable response (${response.status}).`); }
    if (!response.ok || body.error) {
      const error = new Error(body.error || `Request failed (${response.status}).`);
      error.events = body.events;
      throw error;
    }
    return body;
  }
  function addEvents(events) {
    if (!Array.isArray(events)) return;
    for (const item of events) {
      if (!item || typeof item !== "object") continue;
      state.events.push({
        time: String(item.time || new Date().toISOString()),
        direction: ["TX", "RX", "INFO", "ERROR"].includes(item.direction) ? item.direction : "INFO",
        message: String(item.message || "").slice(0, 16384),
        ...(item.hex ? {hex: String(item.hex).slice(0, 16384)} : {}),
      });
    }
    if (state.events.length > 500) {
      state.droppedEvents += state.events.length - 500;
      state.events.splice(0, state.events.length - 500);
    }
    renderLog();
  }
  function log(direction, value) { addEvents([{time: new Date().toISOString(), direction, message: value}]); }
  function renderLog() {
    const window = $("log-window");
    const atEnd = window.scrollHeight - window.scrollTop - window.clientHeight < 60;
    const filter = $("log-filter").value;
    const search = $("log-search").value.toLowerCase();
    const events = state.events.filter((item) => (filter === "ALL" || filter === item.direction)
      && `${item.message} ${item.hex || ""}`.toLowerCase().includes(search));
    $("log-entries").replaceChildren();
    for (const item of events) {
      const row = node("li", "log-entry");
      const date = new Date(item.time);
      const time = node("time", "log-time", Number.isNaN(date.getTime()) ? "—" : date.toLocaleTimeString([], {hour12: false}));
      if (!Number.isNaN(date.getTime())) time.dateTime = date.toISOString();
      time.title = item.time;
      const content = node("span", "log-message", item.message);
      if (item.hex) content.append(node("code", "log-hex", item.hex));
      row.append(time, node("span", `log-direction ${item.direction}`, item.direction), content);
      $("log-entries").append(row);
    }
    $("log-count").textContent = `${events.length}${events.length !== state.events.length ? ` / ${state.events.length}` : ""} events`;
    $("log-empty").hidden = events.length > 0;
    if (!events.length) {
      $("log-empty").replaceChildren(node("span", "", "· · ·"),
        node("p", "", state.events.length ? "No matching events." : "No events yet."),
        node("small", "", state.events.length ? "Change the filter or search text." : "Device messages and file results appear here."));
    }
    if (atEnd) window.scrollTop = window.scrollHeight;
  }
  function controls() {
    const deviceBusy = state.portsBusy || state.identityBusy;
    $("input-port").disabled = !state.ready || deviceBusy || !state.ports.inputs.length;
    $("output-port").disabled = !state.ready || deviceBusy || !state.ports.outputs.length;
    $("refresh-ports").disabled = !state.ready || deviceBusy;
    $("identify").disabled = !state.ready || deviceBusy || !selectedFm1Ports();
    $("identify").textContent = state.identityBusy ? "Reading identity…" : "Read identity ↗";
    $("refresh-ports").textContent = state.portsBusy ? "Refreshing…" : "Refresh ports";
    $("choose-file").disabled = !state.ready;
    $("file-kind").disabled = !state.ready;
    developmentControls();
  }
  function populatePorts(id, names, previous) {
    const select = $(id);
    select.replaceChildren();
    const placeholder = node("option", "", names.length ? "Choose a MIDI port…" : "No MIDI ports found");
    placeholder.value = "";
    select.append(placeholder);
    for (const name of names) {
      const option = node("option", "", name);
      option.value = name;
      select.append(option);
    }
    const matches = names.filter(fm1Port);
    select.value = names.includes(previous) ? previous : matches.length === 1 ? matches[0] : "";
  }
  function invalidateIdentity() {
    state.identity = null;
    $("identity-result").hidden = true;
    $("identity-result").replaceChildren();
    badge("device-badge", "Not read");
  }
  async function refreshPorts() {
    const generation = ++state.portsGeneration;
    state.portsBusy = true;
    const previousInput = $("input-port").value;
    const previousOutput = $("output-port").value;
    invalidateIdentity();
    controls();
    message("device-message", "Loading MIDI ports…");
    try {
      const data = await api("/api/ports");
      if (generation !== state.portsGeneration) return;
      state.ports = {inputs: data.inputs.filter((item) => typeof item === "string"), outputs: data.outputs.filter((item) => typeof item === "string")};
      populatePorts("input-port", state.ports.inputs, previousInput);
      populatePorts("output-port", state.ports.outputs, previousOutput);
      message("device-message", selectedFm1Ports() ? "Ports selected." : "Select the normal FM-1 USB MIDI input and output.");
      log("INFO", `MIDI ports refreshed: ${state.ports.inputs.length} input(s), ${state.ports.outputs.length} output(s).`);
    } catch (error) {
      if (generation !== state.portsGeneration) return;
      state.ports = {inputs: [], outputs: []};
      populatePorts("input-port", [], ""); populatePorts("output-port", [], "");
      message("device-message", error.message, true);
      log("ERROR", error.message);
    } finally {
      if (generation === state.portsGeneration) { state.portsBusy = false; controls(); }
    }
  }
  function details(parent, data) {
    const disclosure = node("details", "report-details");
    disclosure.append(node("summary", "", "Full report · JSON"));
    disclosure.addEventListener("toggle", () => {
      if (disclosure.open && !disclosure.querySelector("pre")) disclosure.append(node("pre", "", JSON.stringify(data, null, 2)));
    });
    parent.append(disclosure);
  }
  function renderIdentity(info) {
    const result = $("identity-result");
    result.replaceChildren();
    result.hidden = false;
    const valid = !info.error && info.checksum_ok === true;
    result.classList.toggle("error", !valid);
    const title = node("div", "identity-title");
    title.append(node("strong", "", info.identity || "Unrecognized reply"), node("span", `quiet-badge ${valid ? "success" : "error"}`, valid ? "Checksum passed" : "Check reply"));
    const list = node("dl", "detail-list");
    for (const [label, value] of [["Source", "Device identity reply"], ["Model", info.model], ["Version field", info.version]]) {
      const row = node("div"); row.append(node("dt", "", label), node("dd", "", printable(value))); list.append(row);
    }
    result.append(title, list);
    if (info.error) result.append(node("p", "inline-message error", info.error));
    details(result, info);
    badge("device-badge", valid ? "Identity received" : "Review reply", valid ? "success" : "error");
  }
  async function identify() {
    if ($("identify").disabled) return;
    state.identityBusy = true;
    invalidateIdentity(); controls();
    const ports = {input: $("input-port").value, output: $("output-port").value};
    message("device-message", "Waiting for the FM-1 identity reply…");
    try {
      const data = await api("/api/identify", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(ports)});
      addEvents(data.events);
      state.identity = {ports, ...data.identity};
      renderIdentity(data.identity);
      message("device-message", "Identity received.");
    } catch (error) {
      addEvents(error.events);
      message("device-message", error.message, true);
      badge("device-badge", "Read failed", "error");
      log("ERROR", error.message);
    } finally { state.identityBusy = false; controls(); }
  }
  function metric(label, value, note) {
    const result = node("div", "metric");
    result.append(node("span", "metric-label", label), node("strong", "metric-value", value));
    if (note) result.append(node("p", "metric-note", note));
    return result;
  }
  function renderInspection(report, filename) {
    const result = $("inspection-result");
    result.replaceChildren();
    $("inspection-panel").hidden = false;
    badge("inspection-badge", "Inspection complete", "success");
    const heading = node("div", "file-heading");
    const name = node("div");
    name.append(node("h3", "", filename), node("p", "", report.kind === "fm1-package" ? "Firmware package" : "Application image"));
    heading.append(name, node("span", "file-size", size(report.size)));
    result.append(heading);
    const metrics = node("div", "metrics");
    if (report.kind === "fm1-package") {
      metrics.append(metric("Package identity", report.identity?.value || "Not found", "Stored in the file. Authenticity is unverified."));
      metrics.append(metric("Package checks", `${report.integrity?.entries_verified ?? 0} entry CRCs passed`, "Header and entry-table CRCs also passed. CRCs cannot confirm the file's source."));
      metrics.append(metric("Package entries", String(report.entries?.length ?? 0), "Logical UFW offsets, with interleaved markers removed."));
    } else {
      metrics.append(metric("Image size", `${Number(report.size).toLocaleString()} bytes`, "Unpacked application image."));
      metrics.append(metric("Identity strings", String(report.embedded_identities?.length ?? 0), "Identity text found in the application file."));
      metrics.append(metric("Possible msfa tables", String(report.msfa_tables?.length ?? 0), "Compared with the msfa algorithm table."));
    }
    result.append(metrics);
    if (report.identity?.matches_application === false) {
      result.append(node("p", "inline-message error", "Package and application identities differ. See the full report."));
    }
    const hash = node("div", "hash-row"); hash.append(node("span", "", "SHA-256"), node("code", "", report.sha256)); result.append(hash);
    if (Array.isArray(report.entries)) {
      result.append(node("h3", "subheading", "Package contents"));
      const wrap = node("div", "table-wrap");
      const table = node("table");
      const caption = node("caption", "visually-hidden", "Firmware package entries");
      const head = node("thead"); const header = node("tr");
      for (const label of ["Entry", "Logical offset", "Size", "CRC16", "CRC scope"]) { const cell = node("th", "", label); cell.scope = "col"; header.append(cell); }
      head.append(header);
      const body = node("tbody");
      for (const entry of report.entries) {
        const row = node("tr");
        for (const value of [entry.name, offset(entry.offset), size(entry.size), printable(entry.crc16), printable(entry.crc_scope)]) row.append(node("td", "", value));
        body.append(row);
      }
      table.append(caption, head, body); wrap.append(table); result.append(wrap);
    }
    const app = report.kind === "fm1-application" ? report : report.application;
    if (app) {
      result.append(node("h3", "subheading", "Application"));
      if (app.status === "unsupported") {
        result.append(node("p", "analysis-note", app.reason || "Cannot extract this application format. Package checks are shown above."));
      } else {
        if (report.kind === "fm1-package") {
          result.append(node("p", "analysis-note", `Unpacked app.bin · ${size(app.size)} (${Number(app.size).toLocaleString()} bytes)${app.status === "verified" ? " · Application CRC passed" : ""}`));
          const appHash = node("div", "hash-row application-hash");
          appHash.append(node("span", "", "APP SHA-256"), node("code", "", app.sha256));
          result.append(appHash);
        }
        const findings = node("ul", "findings");
        for (const table of app.msfa_tables || []) {
          const item = node("li", "finding"); const content = node("div");
          const labels = {"msfa-original": "Original msfa table", "dexed-feedback-variant": "Dexed feedback variant", "truncated": "Truncated msfa candidate", "other-variant": "Modified msfa candidate"};
          content.append(node("strong", "", `${labels[table.classification] || printable(table.classification)} · ${offset(table.offset)}`));
          content.append(node("p", "", `${printable(table.matching_rows)} / 32 rows match original msfa. Offsets refer to the unpacked application.`));
          if (table.differences?.length) {
            const algorithms = [...new Set(table.differences.map((difference) => difference.algorithm))];
            content.append(node("p", "", `Differences in algorithm${algorithms.length === 1 ? "" : "s"} ${algorithms.join(", ")}. See the full report for byte comparisons.`));
          }
          item.append(node("span", "finding-mark", "↳"), content); findings.append(item);
        }
        if (!app.msfa_tables?.length) {
          const item = node("li", "finding");
          item.append(node("span", "finding-mark", "·"), node("p", "", "No matching msfa algorithm table found."));
          findings.append(item);
        }
        result.append(findings);
        if (app.embedded_identities?.length) result.append(node("p", "analysis-note", `Identity strings: ${app.embedded_identities.map(printable).join(" · ")}`));
      }
    }
    if (Array.isArray(report.unchecked_layers) && report.unchecked_layers.length) {
      result.append(node("h3", "subheading", "Not checked"));
      const limits = node("ul", "scope-notes");
      for (const layer of report.unchecked_layers) limits.append(node("li", "", printable(layer)));
      result.append(limits);
    }
    result.append(node("p", "analysis-note", "These checks do not show whether the file is safe to install."));
    details(result, report);
  }
  async function inspectFile(file, inferKind = true) {
    if (state.workBusy) { message("file-message", "Wait for the current file operation to finish.", true); return; }
    const generation = ++state.inspectionGeneration;
    state.inspectionController?.abort();
    state.inspectionController = new AbortController();
    $("drop-zone").removeAttribute("aria-busy");
    state.inspection = null;
    state.source = null;
    state.project = null;
    state.revisionId = null;
    state.preview = null;
    state.patches = [];
    $("development-panel").hidden = true;
    $("inspection-panel").hidden = true;
    state.file = file;
    if (!state.ready) { message("file-message", "Connect to the local service to inspect files.", true); return; }
    if (!file || !file.size) { message("file-message", "Choose a non-empty firmware file.", true); return; }
    if (file.size > state.maxBytes) {
      const error = `File size: ${size(file.size)}. Maximum: ${size(state.maxBytes)}.`;
      message("file-message", error, true); log("ERROR", error); return;
    }
    if (inferKind) {
      if (/\.fwsc$/i.test(file.name)) $("file-kind").value = "fwsc";
      else if (/\.bin$/i.test(file.name)) $("file-kind").value = "app";
      else { message("file-message", "Choose a .fwsc firmware package or a .bin application image.", true); return; }
    }
    const kind = $("file-kind").value;
    state.workBusy = true;
    developmentControls();
    message("file-message", `Inspecting ${fileName(file)} (${size(file.size)})…`);
    $("drop-zone").setAttribute("aria-busy", "true");
    try {
      const source = await api(`/api/analyze?kind=${kind}`, {method: "POST", headers: {"Content-Type": "application/octet-stream"}, body: file, signal: state.inspectionController.signal});
      if (generation !== state.inspectionGeneration) return;
      const report = source.inspection;
      acceptSource(source, fileName(file));
      message("file-message", `${fileName(file)} inspected. Results are below.`);
      log("INFO", `Inspected ${fileName(file)} (${size(report.size)}). SHA-256: ${report.sha256}`);
    } catch (error) {
      if (generation !== state.inspectionGeneration || error.name === "AbortError") return;
      message("file-message", error.message, true);
      log("ERROR", `Could not inspect ${fileName(file)}: ${error.message}`);
    } finally {
      if (generation === state.inspectionGeneration) {
        $("drop-zone").removeAttribute("aria-busy");
        state.workBusy = false;
        developmentControls();
      }
    }
  }
  function exportReport() {
    state.exportGeneration++;
    const report = {schema_version: 1, tool: "FM-1 Workbench", exported_at: new Date().toISOString(),
      mode: "read-only", device: state.identity, inspection: state.inspection,
      analysis: state.source?.analysis || null, rebuild: state.preview?.manifest || null,
      log: {events: state.events, omitted_older_events: state.droppedEvents}};
    $("report-text").value = JSON.stringify(report, null, 2) + "\n";
    state.exportFilename = `fm1-bench-${report.exported_at.replace(/[:.]/g, "-")}.json`;
    $("copy-report").disabled = false;
    $("copy-report").textContent = "Copy report";
    message("report-message", "Includes file names, without local file paths.");
    $("report-dialog").showModal();
    $("report-text").setSelectionRange(0, 0);
    $("report-text").scrollTop = 0;
  }
  async function copyReport() {
    const generation = state.exportGeneration;
    $("copy-report").disabled = true;
    $("copy-report").textContent = "Copying…";
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard access is unavailable.");
      await navigator.clipboard.writeText($("report-text").value);
      if (generation !== state.exportGeneration || !$("report-dialog").open) return;
      message("report-message", "Report copied to clipboard.");
      log("INFO", "Report copied to clipboard.");
    } catch (_) {
      if (generation !== state.exportGeneration || !$("report-dialog").open) return;
      $("report-text").focus();
      $("report-text").select();
      message("report-message", "Automatic copy is unavailable. Report text is selected; press Ctrl+C (⌘C on Mac).", true);
    } finally {
      if (generation === state.exportGeneration) {
        $("copy-report").disabled = false;
        $("copy-report").textContent = "Copy report";
      }
    }
  }
  function downloadReport() {
    const url = URL.createObjectURL(new Blob([$("report-text").value], {type: "application/json"}));
    const link = node("a"); link.href = url;
    link.download = state.exportFilename;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    message("report-message", "Download requested. If your browser does not save the file, use Copy report.");
    log("INFO", "JSON report download requested.");
  }

  function developmentControls() {
    const available = state.ready && !state.workBusy;
    const source = available && state.source;
    for (const id of ["choose-file", "file-kind", "refresh-projects", "import-project", "project-select"]) $(id).disabled = !available;
    for (const id of ["hex-go", "hex-previous", "hex-next", "hex-use-offset", "patch-read", "patch-add", "preview-rebuild", "choose-rollback", "create-project"]) $(id).disabled = !source;
    $("load-revision").disabled = !available || !$("project-select").value || !$("revision-select").value;
    $("revision-select").disabled = !available || !$("project-select").value;
    $("save-revision").disabled = !source || !state.project || !state.preview || !state.revisionId || state.project.id !== $("project-select").value;
    for (const button of $("patch-list").querySelectorAll("button")) button.disabled = !available;
  }

  async function work(messageId, operation) {
    if (state.workBusy) return;
    state.workBusy = true;
    developmentControls();
    try { await operation(); }
    catch (error) { message(messageId, error.message, true); log("ERROR", error.message); }
    finally { state.workBusy = false; developmentControls(); }
  }

  function post(path, body) {
    return api(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  }

  function downloadLink(id, path) {
    const link = $(id);
    if (typeof path !== "string" || !/^\/api\/artifact\/[A-Za-z0-9_-]+$/.test(path)) {
      link.hidden = true;
      link.removeAttribute("href");
      return;
    }
    link.href = path;
    link.hidden = false;
  }

  function acceptSource(source, filename, project = null, revisionId = null) {
    state.source = source;
    state.inspection = {filename, report: source.inspection};
    state.patches = [];
    state.preview = null;
    state.project = project;
    state.revisionId = revisionId;
    renderInspection(source.inspection, filename);
    $("development-panel").hidden = false;
    $("rebuild-result").hidden = true;
    $("record-details").hidden = true;
    $("project-label").value = filename.replace(/\.(fwsc|bin)$/i, "").slice(0, 120);
    const analysis = source.analysis;
    const profile = analysis.profile || {};
    badge("analysis-profile", profile.matched ? profile.name || "Known image" : "Unrecognized image", profile.matched ? "success" : "");
    $("source-description").textContent = `${size(source.application_size)} application · Source SHA-256 ${source.sha256}`;
    $("analysis-coverage").textContent = JSON.stringify({profile, unresolved: analysis.unresolved || [], dsp: analysis.dsp || {}}, null, 2);
    renderAnalysis();
    renderPatches();
    if (project) showProject(project, revisionId);
    else {
      $("project-select").value = "";
      $("revision-select").replaceChildren(node("option", "", "Choose a project"));
      $("revision-select").firstChild.value = "";
      $("download-project").hidden = true;
      message("project-message", "No project loaded. Create one to retain this file and its revisions.");
    }
    $("hex-offset").value = "0x0";
    readHex();
    developmentControls();
  }

  function recordOffset(record) {
    if (Number.isInteger(record.file_offset)) return record.file_offset;
    const location = record.locations?.find((item) => Number.isInteger(item.file_offset));
    return location?.file_offset;
  }

  function renderAnalysis() {
    if (!state.source) return;
    const type = $("analysis-type").value;
    const columns = {
      strings: [["text", "Text"], ["file_offset", "File offset"], ["address", "Address"], ["category", "Category"]],
      regions: [["name", "Name"], ["file_offset", "File offset"], ["size", "Bytes"], ["runtime_address", "Address"], ["permissions", "Access"]],
      functions: [["name", "Name"], ["file_offset", "File offset"], ["address", "Address"], ["size", "Bytes"], ["confidence", "Evidence"]],
      features: [["name", "Name"], ["category", "Category"], ["confidence", "Evidence"], ["locations", "Locations"]],
    }[type];
    const search = $("analysis-search").value.toLowerCase();
    const records = (state.source.analysis[type] || []).filter((record) =>
      `${JSON.stringify(record)} ${offset(recordOffset(record))} ${offset(record.address)}`.toLowerCase().includes(search));
    const head = $("analysis-table").querySelector("thead");
    const body = $("analysis-table").querySelector("tbody");
    head.replaceChildren(); body.replaceChildren();
    const heading = node("tr");
    for (const [, label] of columns) { const th = node("th", "", label); th.scope = "col"; heading.append(th); }
    head.append(heading);
    for (const record of records.slice(0, 500)) {
      const row = node("tr");
      columns.forEach(([key], index) => {
        const cell = node("td");
        let value = record[key];
        if (["file_offset", "address", "runtime_address"].includes(key)) value = value == null ? "—" : offset(value);
        else if (key === "locations") value = (value || []).map((location) => offset(location.file_offset)).join(", ");
        else value = printable(value);
        if (!index) {
          const button = node("button", "record-button", value);
          button.addEventListener("click", () => {
            $("record-details").hidden = false;
            $("record-details").open = true;
            $("record-json").textContent = JSON.stringify(record, null, 2);
            const position = recordOffset(record);
            if (position === undefined) message("analysis-message", "No confirmed file offset for this record.");
            else { $("hex-offset").value = offset(position); readHex(); }
          });
          cell.append(button);
        } else cell.textContent = value;
        row.append(cell);
      });
      body.append(row);
    }
    $("analysis-count").textContent = `${Math.min(500, records.length)} / ${records.length} matches`;
    message("analysis-message", records.length ? "Select a record to view its details and application bytes." : "No results for this view or filter.");
  }

  function numberOffset(value) {
    const text = value.trim();
    if (!/^(0x[0-9a-f]+|[0-9]+)$/i.test(text)) throw new Error("Enter a decimal offset or hexadecimal offset starting with 0x.");
    const result = Number(text);
    if (!Number.isSafeInteger(result) || result < 0) throw new Error("Offset is outside the supported range.");
    return result;
  }

  function hexBytes(value) {
    const text = value.replace(/\s+/g, "");
    if (!text || !/^(?:[0-9a-f]{2})+$/i.test(text)) throw new Error("Enter complete hexadecimal bytes, such as 00 1A FF.");
    return text.toLowerCase();
  }

  async function readHex() {
    if (!state.source) return;
    const generation = ++state.hexGeneration;
    const sourceId = state.source.source_id;
    try {
      const position = numberOffset($("hex-offset").value);
      message("hex-message", "Reading application bytes…");
      const data = await api(`/api/hex?source_id=${encodeURIComponent(sourceId)}&offset=${position}&length=256`);
      if (generation !== state.hexGeneration || sourceId !== state.source?.source_id) return;
      state.hexPosition = position;
      const bytes = data.hex.replace(/\s+/g, "").match(/.{2}/g) || [];
      const lines = ["OFFSET    00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F  ASCII", ""];
      for (let index = 0; index < bytes.length; index += 16) {
        const row = bytes.slice(index, index + 16);
        const ascii = row.map((byte) => { const value = parseInt(byte, 16); return value >= 32 && value < 127 ? String.fromCharCode(value) : "."; }).join("");
        lines.push(`${(position + index).toString(16).toUpperCase().padStart(8, "0")}  ${row.join(" ").toUpperCase().padEnd(47, " ")}  ${ascii}`);
      }
      $("hex-view").textContent = lines.join("\n");
      message("hex-message", `${bytes.length} bytes at ${offset(position)}. Offsets refer to the decoded application file.`);
    } catch (error) {
      if (generation !== state.hexGeneration) return;
      $("hex-view").textContent = "";
      message("hex-message", error.message, true);
    }
  }

  function stepHex(step) {
    if (!state.source) return;
    $("hex-offset").value = offset(Math.max(0, Math.min(state.source.application_size - 1, state.hexPosition + step)));
    readHex();
  }

  async function readPatchBytes() {
    if (!state.source) return;
    try {
      const sourceId = state.source.source_id;
      const position = numberOffset($("patch-offset").value);
      const count = $("patch-after").value.trim() ? hexBytes($("patch-after").value).length / 2 : 1;
      if (count > 256) throw new Error("Read at most 256 current bytes at a time.");
      const data = await api(`/api/hex?source_id=${encodeURIComponent(sourceId)}&offset=${position}&length=${count}`);
      if (sourceId !== state.source?.source_id || position !== numberOffset($("patch-offset").value)) return;
      $("patch-before").value = data.hex;
      message("patch-message", "Current bytes loaded from the source application.");
    } catch (error) { message("patch-message", error.message, true); }
  }

  function addPatch() {
    try {
      const position = numberOffset($("patch-offset").value);
      const before = hexBytes($("patch-before").value);
      const after = hexBytes($("patch-after").value);
      if (before.length !== after.length) throw new Error("Expected and new bytes must have the same length.");
      if (position + before.length / 2 > state.source.application_size) throw new Error("The change extends beyond the application file.");
      if (state.patches.some((patch) => position < patch.offset + patch.expected_hex.length / 2 && patch.offset < position + before.length / 2)) throw new Error("Changes must not overlap.");
      state.patches.push({offset: position, expected_hex: before, replacement_hex: after, label: $("patch-label").value.trim()});
      state.preview = null;
      $("rebuild-result").hidden = true;
      renderPatches();
    } catch (error) { message("patch-message", error.message, true); }
  }

  function renderPatches() {
    $("patch-list").replaceChildren();
    state.patches.forEach((patch, index) => {
      const row = node("div", "patch-row");
      const description = node("div");
      description.append(node("strong", "", `${offset(patch.offset)}${patch.label ? ` · ${patch.label}` : ""}`));
      description.append(node("code", "", `${patch.expected_hex} → ${patch.replacement_hex}`));
      const remove = node("button", "text-button", "Remove");
      remove.setAttribute("aria-label", `Remove change at ${offset(patch.offset)}`);
      remove.addEventListener("click", () => { state.patches.splice(index, 1); state.preview = null; $("rebuild-result").hidden = true; renderPatches(); });
      row.append(description, remove);
      $("patch-list").append(row);
    });
    message("patch-message", state.patches.length ? `${state.patches.length} change(s) queued. Preview verifies the source hash and expected bytes.` : "No changes queued. A rebuild with no changes must reproduce the original file.");
    developmentControls();
  }

  function showRebuild(source) {
    state.preview = source;
    $("rebuild-result").hidden = false;
    $("rebuild-description").textContent = `${source.manifest.operation === "rollback" ? "Restored" : "Rebuilt"} ${size(source.size)} · SHA-256 ${source.sha256}. The current source is unchanged.`;
    $("rebuild-json").textContent = JSON.stringify(source.manifest, null, 2);
    downloadLink("download-rebuilt", source.download_url);
    downloadLink("download-manifest", source.manifest_download_url);
    message("patch-message", "Output checked. Download the firmware and manifest together, or save a project revision.");
    log("INFO", `Local ${source.manifest.operation} complete. Output SHA-256: ${source.sha256}`);
    developmentControls();
  }

  async function previewRebuild() {
    await work("patch-message", async () => {
      message("patch-message", "Checking changes and rebuilding in memory…");
      showRebuild(await post("/api/rebuild", {source_id: state.source.source_id, expected_source_sha256: state.source.sha256, patches: state.patches}));
    });
  }

  async function rollbackFile(file) {
    if (!file) return;
    await work("patch-message", async () => {
      if (file.size > state.maxBytes) throw new Error("The manifest exceeds the 8 MiB limit.");
      const manifest = JSON.parse(await file.text());
      message("patch-message", "Checking the manifest and restoring bytes in memory…");
      showRebuild(await post("/api/rollback", {source_id: state.source.source_id, manifest}));
    });
  }

  function showProject(project, selectedRevision) {
    state.project = project;
    const select = $("project-select");
    if (![...select.options].some((option) => option.value === project.id)) {
      const option = node("option", "", project.summary.label || project.id); option.value = project.id; select.append(option);
    }
    select.value = project.id;
    $("revision-select").replaceChildren();
    for (const revision of project.revisions || []) {
      const option = node("option", "", `${revision.id}: ${revision.label || "Revision"} · ${revision.sha256.slice(0, 12)}`);
      option.value = String(revision.id);
      $("revision-select").append(option);
    }
    if (selectedRevision != null) $("revision-select").value = String(selectedRevision);
    downloadLink("download-project", project.download_url);
    message("project-message", `${project.summary.label || "Project"} · ${project.revisions.length} revision(s). Original firmware is retained.`);
    developmentControls();
  }

  async function refreshProjects() {
    try {
      const result = await api("/api/projects");
      state.projects = result.projects;
      const current = $("project-select").value;
      const empty = node("option", "", "Choose a project…"); empty.value = "";
      $("project-select").replaceChildren(empty);
      for (const project of state.projects) { const option = node("option", "", project.summary.label || project.id); option.value = project.id; $("project-select").append(option); }
      $("project-select").value = current;
      developmentControls();
    } catch (error) { message("project-message", error.message, true); }
  }

  async function loadProject(projectId, revisionId) {
    await work("project-message", async () => {
      message("project-message", "Loading project revision…");
      const source = await post("/api/projects/load", {project_id: projectId, revision_id: revisionId});
      state.file = null;
      $("file-kind").value = source.kind;
      acceptSource(source, `${source.project.summary.label || "Project"} · revision ${source.revision_id}`, source.project, source.revision_id);
      message("file-message", "Project revision loaded.");
    });
  }

  async function createProject() {
    await work("project-message", async () => {
      const label = $("project-label").value.trim();
      if (!label) throw new Error("Enter a project name.");
      message("project-message", "Saving original firmware and analysis…");
      const project = await post("/api/projects/create", {source_id: state.source.source_id, label});
      state.revisionId = 1;
      showProject(project, 1);
      log("INFO", "Project created with original firmware.");
    });
  }

  async function saveRevision() {
    await work("project-message", async () => {
      message("project-message", "Saving rebuilt bytes as a new revision…");
      const preview = state.preview;
      const project = await post("/api/projects/revision", {project_id: state.project.id, parent_id: state.revisionId,
        source_id: preview.source_id, manifest: preview.manifest, label: "Edited application"});
      const revision = project.revisions[project.revisions.length - 1];
      acceptSource(preview, `${project.summary.label || "Project"} · revision ${revision.id}`, project, revision.id);
      message("project-message", `Revision ${revision.id} saved and loaded. Original firmware is retained.`);
    });
  }

  async function importProject(file) {
    if (!file) return;
    await work("project-message", async () => {
      if (file.size > state.maxProjectBytes) throw new Error(`Project exceeds the ${size(state.maxProjectBytes)} import limit.`);
      message("project-message", "Importing project…");
      const project = await api("/api/projects/import", {method: "POST", headers: {"Content-Type": "application/octet-stream"}, body: file});
      const revision = project.revisions[project.revisions.length - 1];
      const source = await post("/api/projects/load", {project_id: project.id, revision_id: revision.id});
      state.file = null;
      $("file-kind").value = source.kind;
      acceptSource(source, `${project.summary.label || "Project"} · revision ${revision.id}`, source.project, source.revision_id);
    });
  }

  async function start() {
    controls();
    try {
      const status = await api("/api/status");
      if (status.mode !== "read-only") throw new Error("A read-only local service is required.");
      state.ready = true;
      if (Number.isInteger(status.max_file_bytes) && status.max_file_bytes > 0) state.maxBytes = status.max_file_bytes;
      if (Number.isInteger(status.max_project_bytes) && status.max_project_bytes > 0) state.maxProjectBytes = status.max_project_bytes;
      $("file-limit").textContent = `.fwsc or app.bin · up to ${size(state.maxBytes)}`;
      $("service-label").textContent = "Local service online";
      $("service-dot").classList.remove("offline");
      message("service-message", "Connected to the local service.");
      log("INFO", "Local service connected. Device access is read-only. Files are processed locally.");
      controls(); await Promise.allSettled([refreshPorts(), refreshProjects()]);
    } catch (error) {
      state.ready = false; controls();
      $("service-label").textContent = "Service unavailable";
      $("service-dot").classList.add("offline");
      message("service-message", `${error.message} Start the local service and reload this page.`, true);
      message("device-message", "MIDI ports are unavailable while the service is offline.", true);
      log("ERROR", error.message);
    }
  }

  $("refresh-ports").addEventListener("click", refreshPorts);
  $("identify").addEventListener("click", identify);
  for (const id of ["input-port", "output-port"]) $(id).addEventListener("change", () => {
    invalidateIdentity(); controls();
    message("device-message", selectedFm1Ports() ? "Ports changed. Read identity again." : "Select the normal FM-1 USB MIDI input and output.");
  });
  $("choose-file").addEventListener("click", () => $("firmware-file").click());
  $("firmware-file").addEventListener("change", (event) => {
    const file = event.target.files[0]; if (file) inspectFile(file); event.target.value = "";
  });
  $("file-kind").addEventListener("change", () => { if (state.file) inspectFile(state.file, false); });
  let dragDepth = 0;
  $("drop-zone").addEventListener("dragenter", (event) => { event.preventDefault(); dragDepth++; if (state.ready) $("drop-zone").classList.add("dragging"); });
  $("drop-zone").addEventListener("dragover", (event) => { event.preventDefault(); event.dataTransfer.dropEffect = state.ready ? "copy" : "none"; });
  $("drop-zone").addEventListener("dragleave", () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) $("drop-zone").classList.remove("dragging"); });
  $("drop-zone").addEventListener("drop", (event) => {
    event.preventDefault(); dragDepth = 0; $("drop-zone").classList.remove("dragging");
    if (event.dataTransfer.files.length !== 1) { message("file-message", "Drop one firmware file at a time.", true); return; }
    inspectFile(event.dataTransfer.files[0]);
  });
  // Prevent a missed drop from navigating the browser away from the bench.
  window.addEventListener("dragover", (event) => event.preventDefault());
  window.addEventListener("drop", (event) => event.preventDefault());
  $("log-filter").addEventListener("change", renderLog);
  $("log-search").addEventListener("input", renderLog);
  $("clear-log").addEventListener("click", () => { state.events = []; state.droppedEvents = 0; renderLog(); });
  $("export-report").addEventListener("click", exportReport);
  $("copy-report").addEventListener("click", copyReport);
  $("download-report").addEventListener("click", downloadReport);
  $("close-report").addEventListener("click", () => $("report-dialog").close());
  $("report-dialog").addEventListener("close", () => $("export-report").focus());
  $("analysis-type").addEventListener("change", renderAnalysis);
  $("analysis-search").addEventListener("input", renderAnalysis);
  $("hex-go").addEventListener("click", readHex);
  $("hex-offset").addEventListener("keydown", (event) => { if (event.key === "Enter") readHex(); });
  $("hex-previous").addEventListener("click", () => stepHex(-256));
  $("hex-next").addEventListener("click", () => stepHex(256));
  $("hex-use-offset").addEventListener("click", () => { $("patch-offset").value = offset(state.hexPosition); readPatchBytes(); $("patch-after").focus(); });
  $("patch-read").addEventListener("click", readPatchBytes);
  $("patch-add").addEventListener("click", addPatch);
  $("preview-rebuild").addEventListener("click", previewRebuild);
  $("choose-rollback").addEventListener("click", () => $("rollback-file").click());
  $("rollback-file").addEventListener("change", (event) => { rollbackFile(event.target.files[0]); event.target.value = ""; });
  $("refresh-projects").addEventListener("click", refreshProjects);
  $("project-select").addEventListener("change", () => {
    if ($("project-select").value) loadProject($("project-select").value, 1);
    else {
      state.project = null; state.revisionId = null;
      $("download-project").hidden = true;
      message("project-message", "No project selected.");
      developmentControls();
    }
  });
  $("revision-select").addEventListener("change", developmentControls);
  $("load-revision").addEventListener("click", () => loadProject($("project-select").value, Number($("revision-select").value)));
  $("create-project").addEventListener("click", createProject);
  $("save-revision").addEventListener("click", saveRevision);
  $("import-project").addEventListener("click", () => $("project-file").click());
  $("project-file").addEventListener("change", (event) => { importProject(event.target.files[0]); event.target.value = ""; });
  start();
})();
