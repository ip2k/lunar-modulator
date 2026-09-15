#!/usr/bin/env python3
"""Local FM-1 research workbench. Device output is restricted to QUERY.

Run: python tools/fm1_workbench.py [--port 8765] [--open]
Only mido/python-rtmidi are needed for hardware; inspection uses the stdlib.
Files stay local. Explicit project saves retain firmware and revision history.
"""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import parse_qs, urlsplit
import webbrowser

if __package__:
    from . import fm1_identify
else:
    import fm1_identify

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


class BenchError(ValueError):
    def __init__(self, message, events=None):
        super().__init__(message)
        self.events = events or []


def event(direction, message, packet=None):
    result = {"time": datetime.now(timezone.utc).isoformat(),
              "direction": direction, "message": message}
    if packet is not None:
        result["hex"] = fm1_identify.hexs(packet)
    return result


def fm1_port(name):
    """Normal USB names across RtMidi backends; reject OTA/BLE endpoint names."""
    return (isinstance(name, str) and len(name) <= 512
            and re.search(r"(?<![\w-])FM-1(?![\w-])", name, re.I) is not None
            and not re.search(r"ota|ble|bluetooth", name, re.I))


class Workbench:
    def __init__(self, midi=None):
        self._midi = midi
        self._lock = threading.Lock()

    def midi(self):
        if self._midi is None:
            try:
                import mido
                self._midi = mido
            except ImportError as exc:
                raise BenchError("Install mido and python-rtmidi to use MIDI. Offline inspection is available.") from exc
        return self._midi

    def ports(self):
        with self._lock:
            return self._ports()

    def _ports(self):
        try:
            midi = self.midi()
            return {"inputs": midi.get_input_names(), "outputs": midi.get_output_names()}
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise BenchError("MIDI is unavailable. Install mido and python-rtmidi, then check the device connection.") from exc

    def identify(self, input_name, output_name, timeout=3.0):
        if not fm1_port(input_name) or not fm1_port(output_name):
            raise BenchError("Select the normal FM-1 USB MIDI input and output.")
        if not self._lock.acquire(blocking=False):
            raise BenchError("Another MIDI operation is in progress.")
        events = []
        try:
            ports = self._ports()
            if ports["inputs"].count(input_name) != 1 or ports["outputs"].count(output_name) != 1:
                raise BenchError("Selected ports changed or are ambiguous. Refresh ports and select again.")
            midi = self.midi()
            with midi.open_input(input_name) as inp, midi.open_output(output_name) as out:
                # Bound stale-message draining so a MIDI clock stream cannot hang a request.
                for _ in range(256):
                    if inp.poll() is None:
                        break
                else:
                    raise BenchError("Input is busy; stop the MIDI stream and retry.")
                out.send(midi.Message("sysex", data=fm1_identify.QUERY))
                events.append(event("TX", "Read identity", bytes([0xF0, *fm1_identify.QUERY, 0xF7])))
                deadline = time.monotonic() + timeout
                observed = 0
                while time.monotonic() < deadline:
                    msg = inp.poll()
                    if msg is None:
                        time.sleep(0.01)
                        continue
                    observed += 1
                    if observed > 256:
                        raise BenchError("Too much incoming MIDI traffic; stop the stream and retry.", events)
                    if msg.type != "sysex":
                        continue
                    if len(msg.data) > 4096:
                        raise BenchError("Oversized SysEx reply; stopped reading.", events)
                    packet = bytes([0xF0, *msg.data, 0xF7])
                    decoded = fm1_identify.decode(packet)
                    events.append(event("RX", decoded.get("error", decoded.get("identity", "SysEx reply")), packet))
                    if "error" in decoded:
                        raise BenchError("Invalid identity reply: " + decoded["error"], events)
                    if decoded.get("model") != "FM-1":
                        raise BenchError("Unexpected device identity; stopped. Preserve the log before proceeding.", events)
                    return {"identity": decoded, "events": events, "read_only": True}
                raise BenchError("No identity reply within 3 seconds. Check the selected ports and close other MIDI clients.", events)
        except BenchError:
            raise
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise BenchError("Cannot open or read the MIDI ports. Check the connection and close other MIDI clients.", events) from exc
        finally:
            self._lock.release()

    def inspect(self, raw, kind):
        if not raw or len(raw) > MAX_FILE_BYTES:
            raise BenchError("Choose a nonempty file of at most 8 MiB.")
        if __package__:
            from . import fm1_package
        else:
            import fm1_package
        if kind == "fwsc":
            return fm1_package.inspect_package(raw)
        if kind == "app":
            return fm1_package.inspect_application(raw)
        raise BenchError("Unknown file kind. Choose fwsc or app.")


class Handler(BaseHTTPRequestHandler):
    # A bounded local tool, not a network-facing deployment server.
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        pass                         # no uploaded names, machine paths or MIDI IDs in logs

    def respond(self, status, body, content_type="application/json; charset=utf-8", filename=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if filename is not None:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def local_request(self, write=False):
        host = self.headers.get("Host", "")
        if host not in self.server.allowed_hosts:
            self.respond(403, {"error": "Use the workbench loopback address."})
            return False
        origin = self.headers.get("Origin")
        if (write and origin is None) or (origin is not None and origin != "http://" + host):
            self.respond(403, {"error": "Only same-origin workbench requests are allowed."})
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.respond(403, {"error": "Cross-site requests are not allowed."})
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        parsed = urlsplit(self.path)
        path = parsed.path
        if path in STATIC:
            name, content_type = STATIC[path]
            self.respond(200, (WEB_ROOT / name).read_bytes(), content_type)
        elif path == "/api/status":
            self.respond(200, {"mode": "read-only", "device_mode": "read-only",
                               "file_modifications": True, "max_file_bytes": MAX_FILE_BYTES,
                               "max_project_bytes": 64 * 1024 * 1024})
        elif path == "/api/ports":
            try:
                self.respond(200, self.server.bench.ports())
            except BenchError as exc:
                self.respond(503, {"error": str(exc)})
        elif path == "/api/projects" or path == "/api/hex" or path.startswith("/api/artifact/"):
            try:
                if path == "/api/projects":
                    self.respond(200, self.server.workspace.projects())
                elif path == "/api/hex":
                    query = parse_qs(parsed.query)
                    if set(query) != {"source_id", "offset", "length"} or any(len(value) != 1 for value in query.values()):
                        raise BenchError("Provide one source ID, offset and length.")
                    self.respond(200, self.server.workspace.hex_view(query["source_id"][0],
                                                                   int(query["offset"][0]), int(query["length"][0])))
                else:
                    parts = path.split("/")
                    if len(parts) != 5:
                        raise BenchError("Invalid artifact URL.")
                    raw, content_type, filename = self.server.workspace.artifact(parts[3], parts[4])
                    self.respond(200, raw, content_type, filename)
            except ValueError as exc:
                self.respond(400, {"error": str(exc)})
            except OSError:
                self.respond(500, {"error": "The local project file could not be accessed."})
        else:
            self.respond(404, {"error": "Not found."})

    def do_POST(self):
        if not self.local_request(write=True):
            return
        parsed = urlsplit(self.path)
        binary_paths = {"/api/inspect", "/api/analyze", "/api/projects/import"}
        json_paths = {"/api/identify", "/api/rebuild", "/api/rollback", "/api/projects/create",
                      "/api/projects/load", "/api/projects/revision"}
        if parsed.path not in binary_paths | json_paths:
            self.respond(404, {"error": "Not found."})
            return
        limit = (4096 if parsed.path == "/api/identify" else 64 * 1024 * 1024 if parsed.path == "/api/projects/import"
                 else MAX_FILE_BYTES if parsed.path in binary_paths else MAX_JSON_BYTES)
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isdigit():
            self.respond(400, {"error": "One Content-Length is required."})
            return
        length = int(lengths[0])
        if length <= 0 or length > limit:
            self.respond(413, {"error": "Request body is empty or too large."})
            return
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip()
        expected = "application/json" if parsed.path in json_paths else "application/octet-stream"
        if content_type != expected:
            self.respond(415, {"error": "Unsupported content type."})
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise BenchError("Incomplete request body.")
            if parsed.path == "/api/identify":
                data = json.loads(raw)
                if not isinstance(data, dict) or set(data) != {"input", "output"}:
                    raise BenchError("Provide exactly an input and output port.")
                result = self.server.bench.identify(data["input"], data["output"])
            elif parsed.path in ("/api/inspect", "/api/analyze"):
                query = parse_qs(parsed.query)
                if set(query) != {"kind"} or len(query["kind"]) != 1:
                    raise BenchError("Choose exactly one file kind.")
                if parsed.path == "/api/inspect":
                    result = self.server.bench.inspect(raw, query["kind"][0])
                else:
                    result = self.server.workspace.analyze(raw, query["kind"][0])
            elif parsed.path == "/api/projects/import":
                result = self.server.workspace.import_project(raw)
            else:
                data = json.loads(raw)
                operations = {"/api/rebuild": self.server.workspace.rebuild,
                              "/api/rollback": self.server.workspace.rollback,
                              "/api/projects/create": self.server.workspace.create_project,
                              "/api/projects/load": self.server.workspace.load_project,
                              "/api/projects/revision": self.server.workspace.add_revision}
                result = operations[parsed.path](data)
            self.respond(200, result)
        except (ValueError, UnicodeError) as exc:
            self.respond(400, {"error": str(exc), "events": getattr(exc, "events", [])})
        except TimeoutError:
            self.respond(408, {"error": "Request timed out."})
        except OSError:
            self.respond(500, {"error": "The local project file could not be accessed."})


def make_server(port=8765, bench=None, project_dir=None):
    if __package__:
        from .fm1_workspace import DevelopmentWorkspace
    else:
        from fm1_workspace import DevelopmentWorkspace
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.bench = bench or Workbench()
    server.workspace = DevelopmentWorkspace(project_dir)
    actual = server.server_address[1]
    server.allowed_hosts = {f"127.0.0.1:{actual}", f"localhost:{actual}"}
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="open the local workbench in your browser")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        server = make_server(args.port)
    except OSError as exc:
        parser.exit(1, f"Cannot start workbench: {exc}\n")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"FM-1 Workbench: {url}\nOffline firmware development; device access is read-only. Ctrl+C to stop.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
