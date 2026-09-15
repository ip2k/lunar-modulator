"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    ready: false, maxBytes: 8 * 1024 * 1024,
    portsBusy: false, identityBusy: false, portsGeneration: 0,
    ports: {inputs: [], outputs: []}, identity: null,
    file: null, inspection: null, inspectionGeneration: 0, inspectionController: null,
    events: [], droppedEvents: 0, exportGeneration: 0, exportFilename: "",
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
    const generation = ++state.inspectionGeneration;
    state.inspectionController?.abort();
    state.inspectionController = new AbortController();
    $("drop-zone").removeAttribute("aria-busy");
    state.inspection = null;
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
    message("file-message", `Inspecting ${fileName(file)} (${size(file.size)})…`);
    $("drop-zone").setAttribute("aria-busy", "true");
    try {
      const report = await api(`/api/inspect?kind=${kind}`, {method: "POST", headers: {"Content-Type": "application/octet-stream"}, body: file, signal: state.inspectionController.signal});
      if (generation !== state.inspectionGeneration) return;
      state.inspection = {filename: fileName(file), report};
      renderInspection(report, fileName(file));
      message("file-message", `${fileName(file)} inspected. Results are below.`);
      log("INFO", `Inspected ${fileName(file)} (${size(report.size)}). SHA-256: ${report.sha256}`);
    } catch (error) {
      if (generation !== state.inspectionGeneration || error.name === "AbortError") return;
      message("file-message", error.message, true);
      log("ERROR", `Could not inspect ${fileName(file)}: ${error.message}`);
    } finally {
      if (generation === state.inspectionGeneration) $("drop-zone").removeAttribute("aria-busy");
    }
  }
  function exportReport() {
    state.exportGeneration++;
    const report = {schema_version: 1, tool: "FM-1 Workbench", exported_at: new Date().toISOString(),
      mode: "read-only", device: state.identity, inspection: state.inspection,
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
  async function start() {
    controls();
    try {
      const status = await api("/api/status");
      if (status.mode !== "read-only") throw new Error("A read-only local service is required.");
      state.ready = true;
      if (Number.isInteger(status.max_file_bytes) && status.max_file_bytes > 0) state.maxBytes = status.max_file_bytes;
      $("file-limit").textContent = `.fwsc or app.bin · up to ${size(state.maxBytes)}`;
      $("service-label").textContent = "Local service online";
      $("service-dot").classList.remove("offline");
      message("service-message", "Connected to the local service.");
      log("INFO", "Local service connected. Device access is read-only. Files are processed locally.");
      controls(); await refreshPorts();
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
  start();
})();
