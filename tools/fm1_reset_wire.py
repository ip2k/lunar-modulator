"""MIT. Evidence-only, narrow USBmon proof of one FC0C(arg=1) transmission.

This module never opens a device. Callers must separately freeze the capture,
owned capture lifecycle, source, SG journal and old/new USB lineage. A complete
CBW OUT proves transmission on the captured USB endpoint; neither it nor an
echo establishes CPU reset, application boot, RAM retention or SG completion.
Text USBmon displays at most 32 payload bytes, so INQUIRY content is a prefix.
"""
from dataclasses import dataclass
import hashlib
import json
import math

RESET_CDB = bytes.fromhex('fc0c00000001ffffffffffffffffffff')
TUR = bytes(16)
SENSE = bytes.fromhex('030000001200') + bytes(10)
INQUIRY = bytes.fromhex('120000002400') + bytes(10)
PREVENT = bytes.fromhex('1e0000000100') + bytes(10)
NOT_READY = bytes.fromhex('700002000000000a000000003a0000000000')
ILLEGAL_FIELD = bytes.fromhex('700005000000000a00000000240000000000')


@dataclass(frozen=True)
class _Record:
    token: str
    time: int
    action: str
    direction: str
    device: int
    status: int
    length: int
    data: bytes


def _bindings(old, new):
    for binding in (old, new):
        if (type(binding) is not dict or any(type(binding.get(k)) is not str
                for k in ('busnum', 'devnum', 'path')) or
                not binding['busnum'].isdigit() or not binding['devnum'].isdigit() or
                not 1 <= int(binding['busnum']) <= 999 or
                not 1 <= int(binding['devnum']) <= 127 or not binding['path']):
            raise ValueError('Exact USB binding required')
    if (old['busnum'] != new['busnum'] or old['path'] != new['path'] or
            old['devnum'] == new['devnum']):
        raise ValueError('Same-port changed USB address required')


def _records(raw, old, new):
    if type(raw) is not bytes or len(raw) > 16 * 1048576:
        raise ValueError('Bounded ASCII capture required')
    records = []
    previous = -1
    for line in raw.decode('ascii').splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        address = fields[3].split(':')
        if len(address) != 4 or address[0] not in ('Bo', 'Bi'):
            continue
        if address[1] != old['busnum']:
            continue
        try:
            device = int(address[2])
        except ValueError:
            raise ValueError('Malformed relevant USB address') from None
        if device not in (int(old['devnum']), int(new['devnum'])):
            continue
        if len(fields) < 6 or fields[2] not in ('S', 'C') or address[3] != '1':
            raise ValueError('Unsupported relevant bulk record')
        try:
            timestamp, status, length = map(int, (fields[1], fields[4], fields[5]))
            if len(fields) == 6:
                data = b''
            elif fields[6] == '=':
                data = bytes.fromhex(''.join(fields[7:]))
            elif (len(fields) == 7 and
                  (fields[6], fields[2], address[0]) in (('<','S','Bi'), ('>','C','Bo'))):
                data = b''
            else:
                raise ValueError
        except ValueError:
            raise ValueError('Malformed relevant bulk record') from None
        if timestamp < previous or timestamp < 0 or length < 0 or len(data) > 32:
            raise ValueError('Relevant capture chronology/geometry differs')
        previous = timestamp
        records.append(_Record(fields[0], timestamp, fields[2], address[0],
                               device, status, length, data))
    return records


def verify_reset_wire(raw, old_usb, new_usb):
    """Verify fully paired BOT traffic and one reset, without granting authority.

    Accepted terminal reset forms are exact echo+CSW, or requested IN16 with
    disconnect status -108/zero bytes/no CSW. Only exact TUR, REQUEST SENSE and
    INQUIRY forms are accepted otherwise. Optional new-ROM PREVENT(1) must fail
    with an immediately following exact illegal-field REQUEST SENSE response.
    No later old-address command, second reset, upload, NOR or eFuse is allowed.
    """
    _bindings(old_usb, new_usb)
    rows = _records(raw, old_usb, new_usb)
    old, new = int(old_usb['devnum']), int(new_usb['devnum'])
    index = 0
    reset = None
    commands = []
    required_sense = None

    def pair(direction, device, length, *, outbound=None, status=0, completed=None):
        nonlocal index
        if index + 1 >= len(rows):
            raise ValueError('Missing paired bulk transfer')
        submit, complete = rows[index:index + 2]
        if (submit.action != 'S' or submit.direction != direction or
                submit.device != device or submit.status != -115 or submit.length != length or
                (outbound is None and submit.data) or
                (outbound is not None and submit.data != outbound) or
                complete.token != submit.token or complete.action != 'C' or
                complete.direction != direction or complete.device != device or
                complete.status != status or
                complete.length != (length if completed is None else completed) or
                (direction == 'Bo' and complete.data)):
            raise ValueError('Paired bulk transfer/status/geometry differs')
        # Reuse after completion is permitted by USBmon; duplicate in-flight
        # identifiers cannot fit this complete adjacent-pair grammar.
        index += 2
        return complete.data

    while index < len(rows):
        row = rows[index]
        cbw = row.data
        if len(cbw) != 31 or cbw[:4] != b'USBC':
            raise ValueError('Only complete exact CBW OUT permitted')
        device = row.device
        pair('Bo', device, 31, outbound=cbw)
        tag, cdb = cbw[4:8], cbw[15:]
        length, direction = int.from_bytes(cbw[8:12], 'little'), cbw[12]
        if cdb == RESET_CDB:
            if (reset is not None or required_sense is not None or device != old or
                    cbw[8:15] != bytes.fromhex('10000000800010')):
                raise ValueError('Exactly one old-address FC0C arg1 required')
            if index + 1 >= len(rows):
                raise ValueError('Reset terminal IN pair required')
            terminal = rows[index + 1]
            if terminal.status == -108:
                data = pair('Bi', old, 16, status=-108, completed=0)
                if data:
                    raise ValueError('Detached reset must return no bytes')
                reset = 'detached_without_reply'
            else:
                data = pair('Bi', old, 16)
                if data != RESET_CDB:
                    raise ValueError('Exact reset echo required')
                csw = pair('Bi', old, 13)
                if csw != b'USBS' + tag + bytes(5):
                    raise ValueError('Exact successful reset CSW required')
                reset = 'echo_and_csw'
            commands.append((device, cdb.hex()))
            continue
        if (device == new and reset is None) or (device == old and reset is not None):
            raise ValueError('Old/new address command order differs')
        forms = {TUR: (0, 0), SENSE: (18, 128), INQUIRY: (36, 128), PREVENT: (0, 0)}
        if cbw[13:15] != b'\x00\x06' or cdb not in forms or forms[cdb] != (length, direction):
            raise ValueError('Nonallowlisted command/direction/geometry')
        if required_sense is not None and (device, cdb) != (required_sense[0], SENSE):
            raise ValueError('Immediate exact REQUEST SENSE required')
        if cdb == PREVENT and (device != new or any(c == PREVENT.hex() for _, c in commands)):
            raise ValueError('Unique new-ROM PREVENT only')
        data = pair('Bi', device, length) if length else b''
        if len(data) != min(length, 32):
            raise ValueError('Exact USBmon displayed data length required')
        csw = pair('Bi', device, 13)
        if len(csw) != 13 or csw[:8] != b'USBS' + tag or csw[8:12] != bytes(4) or csw[12] not in (0, 1):
            raise ValueError('Matching zero-residue CSW required')
        status = csw[12]
        if cdb in (SENSE, INQUIRY) and status != 0:
            raise ValueError('Standard data command must succeed')
        if cdb == SENSE:
            if required_sense is None or data != required_sense[1]:
                raise ValueError('Exact solicited sense response required')
            required_sense = None
        elif cdb == TUR and status == 1:
            required_sense = (device, NOT_READY)
        elif cdb == PREVENT:
            if status != 1:
                raise ValueError('PREVENT must have exact rejected response')
            required_sense = (device, ILLEGAL_FIELD)
        commands.append((device, cdb.hex()))
    if reset is None or required_sense is not None:
        raise ValueError('Complete reset and standard command sequence required')
    return dict(schema=1, reset_cbw_transmitted=True, terminal_reset_form=reset,
                reset_csw_observed=(reset == 'echo_and_csw'), paired_records=len(rows),
                command_count=len(commands), standard_command_count=len(commands) - 1,
                no_later_vendor_command=True, sg_request_completed=False,
                reset_core_observed=False, application_boot_observed=False,
                ram_retention_verified=False, process_origin_verified=False)


def validate(raw, boot_commands, config, old_usb, fresh_rom, terminal_time):
    """Bind the wire observation to a complete trace-reset command envelope.

    ``config`` and ``boot_commands`` are the original bounded file bytes, not
    reconstructed JSON. ``fresh_rom`` is the original passive snapshot with
    observed_at/usb_binding; it does not acquire a new timestamp here. The
    caller owns install proof, file freezing, owned process/capture lifecycle,
    marker and current ROM/SG mapping validation. This result grants no opener.
    """
    if (type(config) is not bytes or len(config) > 65536 or
            type(boot_commands) is not bytes or len(boot_commands) > 65536):
        raise ValueError('Bounded original reset evidence bytes required')
    campaign = json.loads(config)
    events = [json.loads(line) for line in boot_commands.decode('utf8').splitlines()]
    if type(campaign) is not dict or not 3 <= len(events) <= 4 or any(type(e) is not dict for e in events):
        raise ValueError('Complete bounded one-reset event envelope required')
    times = [e.get('time') for e in events]
    if (any(type(t) not in (float, int) or not math.isfinite(t) or t < 0 for t in times) or
            times != sorted(times) or type(terminal_time) not in (int, float) or
            not math.isfinite(terminal_time) or times[-1] != terminal_time):
        raise ValueError('Original finite terminal chronology required')
    if (type(fresh_rom) is not dict or type(fresh_rom.get('observed_at')) not in (int, float) or
            not math.isfinite(fresh_rom['observed_at']) or
            fresh_rom['observed_at'] < terminal_time or
            campaign.get('usb_binding') != old_usb):
        raise ValueError('Original post-terminal ROM snapshot required')
    fresh_usb = fresh_rom.get('usb_binding')
    _bindings(old_usb, fresh_usb)
    if (old_usb.get('vid') != '4c4a' or old_usb.get('pid') != '8057' or
            fresh_usb.get('vid') != '4c4a' or fresh_usb.get('pid') != '8057'):
        raise ValueError('Old loader and returned ROM USB identities required')
    first, intent, terminal = events[0], events[1], events[-1]
    first_fields = {'time','event','campaign_sha256','install_campaign_sha256',
                    'install_commands_sha256','target_sha256','trace_nonce','backup_manifest_sha256',
                    'adapter_sha256','usb_binding','sg_binding','commands','flash_operations',
                    'upload_operations','kernel_exclusivity','boot_observed','display_observed',
                    'physical_recovery_verified'}
    pins = ('adapter_sha256','install_campaign_sha256','install_commands_sha256','target_sha256')
    if (set(first) != first_fields or
            any(type(campaign.get(k)) is not str or len(campaign[k]) != 64 or
                any(c not in '0123456789abcdef' for c in campaign[k]) for k in pins) or
            type(campaign.get('sg_binding')) is not dict or
            first.get('event') != 'trace_target_reset_prepared' or
            first.get('campaign_sha256') != hashlib.sha256(config).hexdigest() or
            any(first.get(k) != campaign.get(k) for k in
                ('adapter_sha256', 'install_campaign_sha256', 'install_commands_sha256',
                 'target_sha256', 'usb_binding', 'sg_binding')) or
            first.get('commands') != 1 or type(first.get('commands')) is not int or
            first.get('flash_operations') != 0 or type(first.get('flash_operations')) is not int or
            first.get('upload_operations') != 0 or type(first.get('upload_operations')) is not int or
            any(first.get(k) is not False for k in
                ('kernel_exclusivity', 'boot_observed', 'display_observed', 'physical_recovery_verified'))):
        raise ValueError('Exact trace-reset preparation/configuration required')
    if (set(intent) != {'time','event','phase','cdb','in_len','out_len','retry','boot_observed'} or
            intent['event'] != 'reset_submit_intent' or intent['phase'] != 'active-fixed-loader' or
            intent['cdb'] != RESET_CDB.hex() or type(intent['in_len']) is not int or
            intent['in_len'] != 16 or type(intent['out_len']) is not int or intent['out_len'] != 0 or
            intent['retry'] is not False or intent['boot_observed'] is not False):
        raise ValueError('Exactly one unchanged reset intent required')
    if len(events) == 4:
        completion = events[2]
        fields = {'time','event','status','masked','msg','host','driver','resid','info',
                  'sense_len','sense_hex','retry','boot_observed'}
        if (set(completion) != fields or completion['event'] != 'reset_sg_completion' or
                completion['retry'] is not False or completion['boot_observed'] is not False or
                any(type(completion[k]) is not int or not 0 <= completion[k] <= 2**32-1
                    for k in ('status','masked','msg','host','driver','info','sense_len')) or
                type(completion['resid']) is not int or not -(2**31) <= completion['resid'] < 2**31 or
                type(completion['sense_hex']) is not str):
            raise ValueError('Exact structured SG completion envelope required')
        try:
            sense = bytes.fromhex(completion['sense_hex'])
        except ValueError:
            raise ValueError('Bounded structured SG sense required') from None
        if len(sense) != min(completion['sense_len'], 32):
            raise ValueError('Bounded structured SG sense required')
    if terminal.get('event') == 'reset_request_completed':
        if (set(terminal) != {'time','event','request_completion','core_reset_observed',
                'boot_observed','retry','display_observed','physical_recovery_verified'} or
                len(events) != 4 or any(events[2][k] != 0 for k in
                ('status','masked','msg','host','driver','resid','sense_len')) or events[2]['info'] & 1 or
                terminal.get('request_completion') is not True or terminal.get('retry') is not False or
                any(terminal.get(k) is not False for k in
                    ('core_reset_observed','boot_observed','display_observed','physical_recovery_verified'))):
            raise ValueError('Exact completed request envelope required')
    elif terminal.get('event') == 'reset_stopped_ambiguous':
        if (set(terminal) != {'time','event','error','detail','retry','core_reset_observed',
                'boot_observed','display_observed','physical_recovery_verified'} or
                terminal.get('retry') is not False or
                any(type(terminal.get(k)) is not str or not 0 < len(terminal[k]) <= 4096
                    for k in ('error','detail')) or
                any(terminal.get(k) is not False for k in
                    ('core_reset_observed','boot_observed','display_observed','physical_recovery_verified'))):
            raise ValueError('Exact terminal caught ambiguity required')
    else:
        raise ValueError('Terminal completed/ambiguous reset event required')
    result = verify_reset_wire(raw, old_usb, fresh_usb)
    if terminal['event'] == 'reset_request_completed' and result['terminal_reset_form'] != 'echo_and_csw':
        raise ValueError('Claimed request completion lacks exact wire response')
    return dict(result, capture_sha256=hashlib.sha256(raw).hexdigest(),
                commands_sha256=hashlib.sha256(boot_commands).hexdigest(),
                campaign_sha256=hashlib.sha256(config).hexdigest(),
                reset_terminal_event=terminal['event'], reset_terminal_time=terminal_time,
                rom_observed_at=fresh_rom['observed_at'], upload_operations=0, flash_operations=0)
