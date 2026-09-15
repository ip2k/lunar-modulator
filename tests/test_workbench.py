"""Device output allowlist, identity validation, and loopback HTTP boundaries."""

from contextlib import contextmanager
import http.client
import json
import threading
from types import SimpleNamespace

import pytest

from tools import fm1_identify
from tools.fm1_workbench import BenchError, Workbench, make_server
from tests.test_tools import IDENTITY_REPLY, pack7


class FakePort:
    def __init__(self, midi, input_port):
        self.midi, self.input_port = midi, input_port
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def poll(self):
        return self.midi.pending.pop(0) if self.midi.pending else None

    def send(self, message):
        self.midi.sent.append(message)
        self.midi.pending.extend(self.midi.replies)


class FakeMidi:
    def __init__(self, reply=IDENTITY_REPLY):
        self.sent, self.pending, self.opened = [], [], []
        self.replies = ([SimpleNamespace(type="sysex", data=reply[1:-1])]
                        if reply is not None else [])
        self.inputs = ["FM-1 Midi 0"]
        self.outputs = ["Microsoft GS Wavetable Synth 0", "FM-1 Midi 1"]

    def get_input_names(self):
        return list(self.inputs)

    def get_output_names(self):
        return list(self.outputs)

    def open_input(self, name):
        assert name in self.inputs
        port = FakePort(self, True)
        self.opened.append(port)
        return port

    def open_output(self, name):
        assert name in self.outputs
        port = FakePort(self, False)
        self.opened.append(port)
        return port

    @staticmethod
    def Message(kind, data):
        return SimpleNamespace(type=kind, data=list(data))


def frame(body):
    return b"\xf0" + pack7(body) + b"\xf7"


@pytest.mark.parametrize("mutation", ["checksum", "length", "high-bit", "padding", "suffix", "tail"])
def test_identity_rejects_corrupted_hardware_reply(mutation):
    wire = bytearray(IDENTITY_REPLY)
    decoded = bytearray(fm1_identify.unpack7(wire[1:-1]))
    if mutation == "checksum":
        decoded[-1] ^= 1
    elif mutation == "length":
        decoded[3] = 26
    elif mutation == "suffix":
        decoded[14] = ord("!")
        decoded[-1] = ~sum(decoded[6:-1]) & 0xff
    elif mutation == "tail":
        wire[-1:-1] = b"\0"
    elif mutation == "high-bit":
        wire[12] |= 0x80
    elif mutation == "padding":
        wire[-2] |= 0x40
    reply = frame(decoded) if mutation in ("checksum", "length", "suffix") else bytes(wire)
    result = fm1_identify.decode(reply)
    assert "error" in result
    assert "identity" not in result


def test_live_query_sends_only_fixed_identity_and_closes_ports():
    midi = FakeMidi()
    result = Workbench(midi).identify("FM-1 Midi 0", "FM-1 Midi 1")
    assert result["identity"]["identity"] == "FM-1_015"
    assert result["read_only"] is True
    assert len(midi.sent) == 1
    assert midi.sent[0].type == "sysex" and midi.sent[0].data == fm1_identify.QUERY
    assert [e["direction"] for e in result["events"]] == ["TX", "RX"]
    assert all(p.closed for p in midi.opened)


@pytest.mark.parametrize("raw,expected", [(IDENTITY_REPLY, 0), (b"", 1),
                                           (IDENTITY_REPLY * 2, 0), (IDENTITY_REPLY[:-1], 1),
                                           (b"junk" + IDENTITY_REPLY, 1),
                                           (IDENTITY_REPLY[:-2] + b"\0\xf7", 1)])
def test_offline_identity_cli_exit_status(raw, expected, tmp_path, monkeypatch):
    path = tmp_path / "identity.syx"
    path.write_bytes(raw)
    monkeypatch.setattr("sys.argv", ["fm1_identify.py", "--decode-file", str(path)])
    assert fm1_identify.main() == expected


@pytest.mark.parametrize("input_name,output_name", [
    ("FM-1 Midi 0", "Microsoft GS Wavetable Synth 0"),
    ("FM-1 Midi 0", "ota-FM-1"),
    ("FM-1_BLE", "FM-1_BLE"),
    (None, "FM-1 Midi 1"),
    ("FM-1 Midi 0", "FM-1 Midi 99"),
])
def test_wrong_or_stale_target_never_opens_or_sends(input_name, output_name):
    midi = FakeMidi()
    with pytest.raises(BenchError):
        Workbench(midi).identify(input_name, output_name)
    assert not midi.opened and not midi.sent


def test_duplicate_port_names_are_ambiguous():
    midi = FakeMidi()
    midi.inputs *= 2
    with pytest.raises(BenchError, match="ambiguous"):
        Workbench(midi).identify("FM-1 Midi 0", "FM-1 Midi 1")
    assert not midi.sent


def test_invalid_identity_is_not_a_success_and_preserves_log():
    broken = bytearray(IDENTITY_REPLY)
    broken[11] ^= 1
    midi = FakeMidi(broken)
    with pytest.raises(BenchError, match="Invalid identity") as caught:
        Workbench(midi).identify("FM-1 Midi 0", "FM-1 Midi 1")
    assert len(caught.value.events) == 2
    assert len(midi.sent) == 1 and all(p.closed for p in midi.opened)


def test_unexpected_valid_identity_stops_without_followup():
    body = b"\x00\x59\x11\x1b\0\0" + b"OTHER_015".ljust(27, b"\0")
    midi = FakeMidi(frame(body + bytes([~sum(body[6:]) & 0xff])))
    with pytest.raises(BenchError, match="Unexpected device identity"):
        Workbench(midi).identify("FM-1 Midi 0", "FM-1 Midi 1")
    assert len(midi.sent) == 1


def test_decoder_uses_the_entire_validated_identity_field():
    field = b"A" * 23 + b"_123"
    body = b"\x00\x59\x11\x1b\0\0" + field
    result = fm1_identify.decode(frame(body + bytes([~sum(field) & 0xff])))
    assert "error" not in result
    assert result["version"] == 123


def test_timeout_closes_ports_and_keeps_tx():
    midi = FakeMidi(None)
    with pytest.raises(BenchError, match="No identity reply") as caught:
        Workbench(midi).identify("FM-1 Midi 0", "FM-1 Midi 1", timeout=0.01)
    assert [e["direction"] for e in caught.value.events] == ["TX"]
    assert all(p.closed for p in midi.opened)


def test_busy_query_is_rejected():
    midi = FakeMidi()
    bench = Workbench(midi)
    with bench._lock:
        with pytest.raises(BenchError, match="in progress"):
            bench.identify("FM-1 Midi 0", "FM-1 Midi 1")
    assert not midi.sent


@contextmanager
def running_server():
    midi = FakeMidi()
    server = make_server(0, Workbench(midi))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, midi
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection(*server.server_address, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        return response.status, dict(response.headers), data
    finally:
        connection.close()


def test_http_hardware_requires_same_origin_explicit_target():
    with running_server() as (server, midi):
        origin = "http://127.0.0.1:" + str(server.server_address[1])
        payload = json.dumps({"input": "FM-1 Midi 0", "output": "FM-1 Midi 1"})
        for foreign in (None, "https://example.com", "null"):
            headers = {"Content-Type": "application/json"}
            if foreign:
                headers["Origin"] = foreign
            assert request(server, "POST", "/api/identify", payload, headers)[0] == 403
        assert not midi.sent
        status, headers, data = request(server, "POST", "/api/identify", payload,
                                       {"Origin": origin, "Content-Type": "application/json"})
        assert status == 200 and json.loads(data)["identity"]["identity"] == "FM-1_015"
        assert len(midi.sent) == 1
        assert "Access-Control-Allow-Origin" not in headers


def test_http_blocks_rebinding_traversal_unknown_and_oversized_requests():
    with running_server() as (server, midi):
        assert request(server, "GET", "/api/ports", headers={"Host": "evil.test"})[0] == 403
        for path in ("/../README.md", "/%2e%2e/README.md", "/scratch/private.json", "/api/flash"):
            assert request(server, "GET", path)[0] == 404
        origin = "http://127.0.0.1:" + str(server.server_address[1])
        assert request(server, "POST", "/api/identify", b" " * 4097,
                       {"Origin": origin, "Content-Type": "application/json"})[0] == 413
        assert request(server, "POST", "/api/identify", b"{}",
                       {"Origin": origin, "Content-Type": "text/plain"})[0] == 415
        assert request(server, "POST", "/api/identify", b"{bad json",
                       {"Origin": origin, "Content-Type": "application/json"})[0] == 400
        assert not midi.sent


def test_port_listing_and_offline_inspection_do_not_open_hardware():
    with running_server() as (server, midi):
        assert request(server, "GET", "/api/ports")[0] == 200
        origin = "http://127.0.0.1:" + str(server.server_address[1])
        status, _, body = request(server, "POST", "/api/inspect?kind=app", b"synthetic image",
                                  {"Origin": origin, "Content-Type": "application/octet-stream"})
        assert status == 200 and json.loads(body)["kind"] == "fm1-application"
        assert not midi.opened and not midi.sent
