"""MIT. Pure fixed five-read native/USBmon replay; no device authority.

Callers separately freeze accepted sources, registered boot lineage, original
reader plan/seal/marker, owned capture lifecycle and publication/absence files.
USBmon text proves only a response prefix (at most32 bytes), not the full64-byte
trace, process origin, CPU boot, reset cause or a recovery route.
"""
from dataclasses import dataclass
import hashlib
import json
import math

OPERATIONS = ((bytes.fromhex('120000002400'), 36),
    (bytes.fromhex('fd0701c028800040ffffffffffffffff'), 64),
    (bytes.fromhex('fd0701c034180004ffffffffffffffff'), 4),
    (bytes.fromhex('fd0701c028800040ffffffffffffffff'), 64),
    (bytes.fromhex('fd0701c034180004ffffffffffffffff'), 4))
TUR = bytes(16)
SENSE = bytes.fromhex('030000001200') + bytes(10)
INQUIRY = OPERATIONS[0][0] + bytes(10)
PREVENT = bytes.fromhex('1e0000000100') + bytes(10)
NOT_READY = bytes.fromhex('700002000000000a000000003a0000000000')
ILLEGAL_FIELD = bytes.fromhex('700005000000000a00000000240000000000')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def _events(raw, bound=65536):
    if type(raw) is not bytes or len(raw) > bound:
        raise ValueError('Bounded original event bytes required')
    rows = [json.loads(line) for line in raw.decode('utf8').splitlines()]
    if any(type(row) is not dict for row in rows) or len(rows) > 32:
        raise ValueError('Bounded object events required')
    times = [row.get('time') for row in rows]
    if (any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times)
            or times != sorted(times)):
        raise ValueError('Original finite event chronology required')
    return rows


def verify_native_receipt(native_raw, outer_raw, mapping, *, outcome):
    """Cross-check exact source2b787 ioctl grammar against the outer reader.

    A successful close has no native event. An ioctl return alone establishes
    no data/status acceptance; the separately replayed outer completion does.
    Missing/empty native log is only a stopped pre-ioctl shape, never success.
    """
    if outcome not in ('completed', 'stopped-ambiguous', 'consumed-pretransport-zero-cbw'):
        raise ValueError('Exact classified outer outcome required')
    outer = _events(outer_raw)
    intents, completions = [], []
    for row in outer:
        if row.get('event') == 'submit_intent':
            index = len(intents)
            if index >= 5 or canonical({k:v for k,v in row.items() if k != 'time'}) != canonical(dict(
                    event='submit_intent', index=index, cdb=OPERATIONS[index][0].hex(),
                    in_len=OPERATIONS[index][1], out_len=0, retry=False)):
                raise ValueError('Exact ordered outer request required')
            intents.append(row)
        elif row.get('event') == 'completion':
            index = len(completions)
            if type(row.get('index')) is not int or row['index'] != index or index >= len(intents):
                raise ValueError('Outer completion without exact preceding request')
            completions.append(row)
    if outcome == 'consumed-pretransport-zero-cbw' and (outer or native_raw):
        raise ValueError('Zero pretransport branch cannot contain native/outer events')
    rows = _events(native_raw)
    if rows and (not outer or rows[0]['time'] < outer[0]['time']):
        raise ValueError('Native open must follow original outer preparation')
    if not rows:
        if intents or outcome == 'completed':
            raise ValueError('Missing native evidence for intended requests')
        return dict(ioctl_intents=0, opened=False, native_completion_proven=False)
    first = rows[0]
    if canonical({k:v for k,v in first.items() if k != 'time'}) != canonical(dict(
            event='native_open_intent', advisory_lock=True, commands=5)):
        raise ValueError('Exact durable native open intent required')
    opened, failed, count = False, False, 0
    for row in rows[1:]:
        fields = {k:v for k,v in row.items() if k != 'time'}
        event = fields.get('event')
        if event == 'native_opened':
            if opened or failed or count or canonical(fields) != canonical(dict(
                    event=event, fd_identity=mapping['node_identity'])):
                raise ValueError('Exact single opened FD identity required')
            opened = True
        elif event == 'native_ioctl_intent':
            index = count
            if not opened or failed or index >= len(intents) or index >= 5:
                raise ValueError('Ioctl after failure or without outer intent')
            if canonical(fields) != canonical(dict(event=event, index=index,
                    cdb=OPERATIONS[index][0].hex(), in_len=OPERATIONS[index][1], out_len=0, retry=False)):
                raise ValueError('Exact ordered fixed native ioctl required')
            if row['time'] < intents[index]['time'] or (index < len(completions)
                    and row['time'] > completions[index]['time']):
                raise ValueError('Ioctl must lie inside original outer intent/completion')
            if index and (index-1 >= len(completions) or completions[index-1]['time'] > row['time']):
                raise ValueError('Next ioctl before preceding recorded completion')
            count += 1
        elif event == 'native_ioctl_exception':
            if (not opened or failed or not count or set(fields) !=
                    {'event','index','error','errno','completion_valid','retry'}
                    or type(fields['index']) is not int or fields['index'] != count-1
                    or len(completions) >= count or fields['completion_valid'] is not False
                    or fields['retry'] is not False):
                raise ValueError('Exact terminal failed ioctl required')
            _error(fields, errno=True); failed = True
        elif event == 'native_open_failed':
            if opened or failed or count or set(fields) != {'event','error','errno'}:
                raise ValueError('Exact pre-open failure required')
            _error(fields, errno=True); failed = True
        elif event == 'native_binding_failed':
            if set(fields) != {'event','error'}:
                raise ValueError('Exact binding failure required')
            _error(fields); failed = True
        elif event == 'native_close_failed':
            if set(fields) != {'event','error','errno'}:
                raise ValueError('Exact close failure required')
            _error(fields, errno=True); failed = True
        else:
            raise ValueError('Unknown native event or invented successful close')
    if len(completions) > count or len(intents)-count not in (0, 1):
        raise ValueError('Native/outer request prefix differs')
    if outcome == 'completed' and (failed or not opened or count != 5 or len(completions) != 5):
        raise ValueError('Complete five-request native sequence required')
    if outer and rows[-1]['time'] > outer[-1]['time']:
        raise ValueError('Native events after outer terminal record')
    return dict(ioctl_intents=count, opened=opened, native_failure_recorded=failed,
                native_completion_proven=False)


def _error(fields, errno=False):
    if type(fields['error']) is not str or not fields['error'] or len(fields['error']) > 128:
        raise ValueError('Bounded exact error class required')
    if errno and fields['errno'] is not None and type(fields['errno']) is not int:
        raise ValueError('Exact recorded errno required')


@dataclass(frozen=True)
class _Record:
    token: str
    time: int
    action: str
    direction: str
    status: int
    length: int
    data: bytes


def _records(raw, usb):
    if (type(raw) is not bytes or len(raw) > 16*1048576 or type(usb) is not dict
            or any(type(usb.get(k)) is not str or not usb[k].isdigit() for k in ('busnum','devnum'))
            or not 1 <= int(usb['busnum']) <= 999 or not 1 <= int(usb['devnum']) <= 127):
        raise ValueError('Bounded capture and exact USB address required')
    rows, previous = [], -1
    for line in raw.decode('ascii').splitlines():
        f = line.split()
        if len(f) < 4:
            continue
        a = f[3].split(':')
        if len(a) != 4 or a[0] not in ('Bo','Bi') or a[1] != usb['busnum']:
            continue
        try:
            device = int(a[2])
        except ValueError:
            raise ValueError('Malformed relevant USB address') from None
        if device != int(usb['devnum']):
            continue
        if len(f) < 6 or f[2] not in ('S','C') or a[3] != '1':
            raise ValueError('Exact relevant bulk endpoint/action required')
        try:
            timestamp, status, length = map(int, (f[1],f[4],f[5]))
            if len(f) == 6:
                data = b''
            elif f[6] == '=':
                data = bytes.fromhex(''.join(f[7:]))
            elif len(f) == 7 and (f[6],f[2],a[0]) in (('<','S','Bi'),('>','C','Bo')):
                data = b''
            else:
                raise ValueError
        except ValueError:
            raise ValueError('Malformed relevant bulk record') from None
        if timestamp < previous or timestamp < 0 or length < 0 or len(data) > 32:
            raise ValueError('Exact capture chronology/geometry required')
        previous = timestamp
        rows.append(_Record(f[0],timestamp,f[2],a[0],status,length,data))
    return rows


def verify_read_wire(raw, usb, *, ioctl_intents, outcome, raw_replies=None):
    """Verify exact read-only BOT inventory; stopped terminal transfer is unknown.

    ``ioctl_intents`` is independently replayed native evidence, not authority.
    Standard INQUIRY may be kernel-originated: process origin is never inferred.
    Full completion requires four FD07 responses and at least one ROM INQUIRY;
    a stopped prefix permits only the current intended transaction to end short.
    """
    if (type(ioctl_intents) is not int or not 0 <= ioctl_intents <= 5
            or outcome not in ('completed','stopped-ambiguous','consumed-pretransport-zero-cbw')):
        raise ValueError('Exact independently replayed request prefix required')
    replies = {} if raw_replies is None else raw_replies
    if (type(replies) is not dict or any(type(k) is not int or not 0 <= k < 5
            or type(v) is not bytes or len(v) != OPERATIONS[k][1] for k,v in replies.items())):
        raise ValueError('Exact actually published reply bytes required')
    rows = _records(raw, usb)
    if outcome == 'consumed-pretransport-zero-cbw':
        if ioctl_intents or any(r.action == 'S' and r.direction == 'Bo' for r in rows):
            raise ValueError('Zero-CBW branch contains outbound submission')
        if rows:
            raise ValueError('Unexplained pretransport bulk capture')
        return _result(raw, 0, 0, False, 0)
    index = vendor = inquiries = standards = 0
    truncated = False
    required_sense = None

    def pair(direction, length, outbound=None):
        nonlocal index, truncated
        if index >= len(rows):
            if outcome != 'completed':
                truncated = True; return None
            raise ValueError('Missing bulk submission')
        submit = rows[index]
        if (submit.action != 'S' or submit.direction != direction or submit.status != -115
                or submit.length != length or submit.data != (b'' if outbound is None else outbound)):
            raise ValueError('Exact bulk submission required')
        index += 1
        if index == len(rows):
            if outcome != 'completed':
                truncated = True; return None
            raise ValueError('Missing bulk completion')
        complete = rows[index]; index += 1
        if (complete.action != 'C' or complete.token != submit.token
                or complete.direction != direction or direction == 'Bo' and complete.data):
            raise ValueError('Matching paired bulk completion required')
        if complete.status != 0 or complete.length != length:
            if (outcome != 'completed' and index == len(rows) and complete.status != 0
                    and 0 <= complete.length <= length and len(complete.data) <= min(complete.length,32)):
                truncated = True; return None
            raise ValueError('Exact successful completion or terminal failure required')
        if direction == 'Bi' and len(complete.data) != min(length,32):
            raise ValueError('Exact displayed response prefix required')
        return complete.data

    while index < len(rows):
        cbw = rows[index].data
        if len(cbw) != 31 or cbw[:4] != b'USBC':
            raise ValueError('Complete exact read-only CBW required')
        cdb, tag = cbw[15:], cbw[4:8]
        length, direction = int.from_bytes(cbw[8:12],'little'), cbw[12]
        is_vendor = cdb[:2] == b'\xfd\x07'
        if is_vendor:
            op = vendor+1
            if (required_sense is not None or op >= ioctl_intents or op >= 5
                    or cbw[13:15] != b'\x00\x10' or cdb != OPERATIONS[op][0]
                    or (length,direction) != (OPERATIONS[op][1],128) or not inquiries):
                raise ValueError('Exact ordered intended trace/stage request required')
            vendor += 1
        else:
            forms = {TUR:(0,0), SENSE:(18,128), INQUIRY:(36,128), PREVENT:(0,0)}
            if cbw[13:15] != b'\x00\x06' or cdb not in forms or forms[cdb] != (length,direction):
                raise ValueError('Nonallowlisted command, OUT payload or CDB geometry')
            if required_sense is not None and cdb != SENSE:
                raise ValueError('Immediate solicited exact sense required')
            if cdb == SENSE and required_sense is None:
                raise ValueError('Unsolicited sense request')
            if vendor and cdb == PREVENT:
                raise ValueError('No new kernel lock after vendor read')
            standards += 1
        if pair('Bo',31,cbw) is None:
            break
        data = pair('Bi',length) if length else b''
        if truncated:
            break
        csw = pair('Bi',13)
        if truncated:
            break
        if len(csw) != 13 or csw[:8] != b'USBS'+tag or csw[8:12] != bytes(4) or csw[12] not in (0,1):
            raise ValueError('Exact matching zero-residue CSW required')
        status = csw[12]
        if is_vendor:
            if status:
                if outcome != 'completed' and index == len(rows):
                    truncated = True; break
                raise ValueError('Failed vendor read must terminate captured prefix')
            if op in replies and data != replies[op][:32]:
                raise ValueError('Captured prefix differs from published actual reply')
        elif cdb == INQUIRY:
            if status or data[8:16].strip() != b'WL82' or data[16:32].strip() != b'UBOOT1.00':
                raise ValueError('Exact successful original ROM inquiry prefix required')
            if 0 in replies and data != replies[0][:32]:
                raise ValueError('Captured inquiry differs from published reply')
            inquiries += 1
        elif cdb == SENSE:
            if status or data != required_sense:
                raise ValueError('Exact successful solicited sense required')
            required_sense = None
        elif cdb == TUR and status:
            required_sense = NOT_READY
        elif cdb == PREVENT:
            if status != 1:
                raise ValueError('PREVENT requires rejected response')
            required_sense = ILLEGAL_FIELD
    if index != len(rows) or required_sense is not None and not truncated:
        raise ValueError('Unconsumed traffic or missing solicited sense')
    if outcome == 'completed' and (ioctl_intents != 5 or vendor != 4 or not inquiries or truncated):
        raise ValueError('All four exact FD07 replies and inquiry required')
    return _result(raw,vendor,standards,truncated,len(rows))


def _result(raw,vendor,standards,truncated,records):
    return dict(capture_sha256=hashlib.sha256(raw).hexdigest(), fd07_requests=vendor,
        standard_commands=standards, terminal_transfer_ambiguous=truncated,
        captured_bulk_records=records, full_trace_bytes_verified=False,
        process_origin_verified=False, cpu_boot_observed=False,
        reset_cause_proven=False, returned_proof_granted=False)
