"""Offline replay of retained physical v2 replies; no device or recovery authority."""
import hashlib
import json
from pathlib import Path
import struct
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'tools'))
from fm1_prepare_stop_trace_receipt import NAMES, verify_receipt
from fm1_sdk_trace_read import interpret_repeated
from fm1_sdk_trace_read_wire import verify_read_wire
from fm1_prepare_stop_capture_receipt import FILES, verify_capture

evidence = root / 'build/preparation-stop-trace-physical-v2-20261012'
run = evidence / 'fm1-stop-trace-capture-v2-20261012/run'
receipt = evidence / 'fm1-sdk-trace-entry-20261012-v7/stock-backup-001/physical-distinct-preparation-stop-trace-v2'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
owned = json.loads((run / 'owned-capture.json').read_bytes())
assert owned['native_campaign_sha256'] == sha((run / 'campaign.json').read_bytes())
for name, expected in owned['wrapper_files_sha256'].items():
    assert sha((run / name).read_bytes()) == expected, name
witness = json.loads((run / 'witness.json').read_bytes())
stop = json.loads((run / 'capture-stop.json').read_bytes())
raw_files = {name: (receipt / (name + '.raw.bin')).read_bytes() for name in NAMES}
parsed = verify_receipt((receipt / 'commands.jsonl').read_bytes(),
    (receipt / 'native.jsonl').read_bytes(), (receipt / 'campaign.json').read_bytes(),
    raw_files, witness['sg_binding'], interpret=interpret_repeated,
    evaluated_at=stop['time'], result_raw=(receipt / 'result.json').read_bytes())
wire = verify_read_wire((run / 'usbmon.txt').read_bytes(), witness['usb_binding'],
    ioctl_intents=parsed['native']['ioctl_intents'], outcome=parsed['outcome'],
    raw_replies={i: raw_files[name] for i, name in enumerate(NAMES)})
attempt = json.loads((run / 'wrapper-attempt.json').read_bytes())
capture = verify_capture((run / 'owned-capture.json').read_bytes(),
    {name: (run / name).read_bytes() for name in FILES},
    dict(wrapper_sha256=owned['wrapper_files_sha256']['execute-once.py'],
        child_sha256=owned['wrapper_files_sha256']['execute-child.py'],
        **{key: owned[key] for key in ('native_campaign_path', 'native_campaign_sha256',
                                     'preparation_stop_path', 'preparation_stop_sha256')},
        **{key: attempt[key] for key in ('native_sha256', 'reader_sha256', 'proof_sha256', 'usb_binding')}),
    read_outcome=parsed['outcome'], read_started=parsed['started_at'],
    read_terminal=parsed['terminal_at'])

# Check pcapng block framing and count packets without treating it as admission.
pcap = (evidence / 'cynthion-ram-read.pcapng').read_bytes()
assert pcap[:4] == b'\x0a\x0d\x0d\x0a'
byte_orders = {b'\x4d\x3c\x2b\x1a': '<', b'\x1a\x2b\x3c\x4d': '>'}
endian = byte_orders[pcap[8:12]]
offset = packets = blocks = 0
while offset < len(pcap):
    kind, length = struct.unpack_from(endian + 'II', pcap, offset)
    assert length >= 12 and length % 4 == 0 and offset + length <= len(pcap)
    assert struct.unpack_from(endian + 'I', pcap, offset + length - 4)[0] == length
    packets += kind == 6
    blocks += 1
    offset += length
assert packets == 34056
summary = dict(schema=1, scope='offline actual physical receipt and capture replay',
    receipt=parsed, wire=wire, capture=capture, owned_file_hashes_checked=len(owned['wrapper_files_sha256']),
    cynthion=dict(sha256=sha(pcap), size=len(pcap), enhanced_packet_blocks=packets,
        ui_packet_count=34058, blocks=blocks, byte_order=endian),
    recovery_authorized=False, display_observed=False, physical_boot_verified=False)
output = evidence / 'offline-replay.json'
output.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print(json.dumps(summary, sort_keys=True))
