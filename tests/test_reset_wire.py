"""MIT. Fully modeled USBmon wire evidence; no device or opener."""
import struct
import hashlib
import json
import pytest
from tools import fm1_reset_wire as wire

OLD = dict(busnum='3', devnum='25', path='3-2')
NEW = dict(busnum='3', devnum='26', path='3-2')


def capture(form='detach', *, standards=False, lock=False):
    rows = []
    clock = 100
    ident = 0
    tag = 0
    def transfer(dev, direction, length, data=b'', status=0, completed=None):
        nonlocal clock, ident
        ident += 1
        submit = data if direction == 'Bo' else b''
        response = data if direction == 'Bi' else b''
        rows.append(f'{ident:x} {clock} S {direction}:3:{dev:03}:1 -115 {length}' +
                    (' = ' + submit.hex() if submit else ''))
        rows.append(f'{ident:x} {clock + 1} C {direction}:3:{dev:03}:1 {status} ' +
                    str(length if completed is None else completed) +
                    (' = ' + response.hex() if response else ''))
        clock += 2
    def cbw(dev, cdb, length, direction, cdb_length=6):
        nonlocal tag
        tag += 1
        transfer(dev, 'Bo', 31, b'USBC' + struct.pack('<II', tag, length) +
                 bytes((direction, 0, cdb_length)) + cdb)
        return tag
    def csw(dev, value, status=0):
        transfer(dev, 'Bi', 13, b'USBS' + struct.pack('<II', value, 0) + bytes((status,)))
    def standard(dev, cdb, response=b'', status=0):
        length, direction = {wire.TUR:(0,0), wire.SENSE:(18,128),
                             wire.INQUIRY:(36,128), wire.PREVENT:(0,0)}[cdb]
        value = cbw(dev, cdb, length, direction)
        if length:
            transfer(dev, 'Bi', length, response)
        csw(dev, value, status)
    if standards:
        standard(25, wire.TUR, status=1)
        standard(25, wire.SENSE, wire.NOT_READY)
        standard(25, wire.INQUIRY, b'WL82 UBOOT'.ljust(32, b' '))
    value = cbw(25, wire.RESET_CDB, 16, 128, 16)
    if form == 'detach':
        transfer(25, 'Bi', 16, status=-108, completed=0)
    else:
        transfer(25, 'Bi', 16, wire.RESET_CDB)
        csw(25, value)
    if lock:
        standard(26, wire.PREVENT, status=1)
        standard(26, wire.SENSE, wire.ILLEGAL_FIELD)
    return rows


def check(rows, old=OLD, new=NEW):
    return wire.verify_reset_wire(('\n'.join(rows)+'\n').encode(), old, new)


@pytest.mark.parametrize('form', ['detach', 'reply'])
@pytest.mark.parametrize('standards,lock', [(False,False),(True,False),(False,True),(True,True)])
def test_exact_transmission_has_only_bounded_claims(form, standards, lock):
    result = check(capture(form, standards=standards, lock=lock))
    assert result['reset_cbw_transmitted'] is True
    assert result['reset_csw_observed'] is (form == 'reply')
    assert not any(result[key] for key in ('sg_request_completed','reset_core_observed',
                                          'application_boot_observed','ram_retention_verified'))


@pytest.mark.parametrize('remove', [0,1,2,3])
def test_missing_transfer_record_rejects(remove):
    rows=capture(); rows.pop(remove)
    with pytest.raises(ValueError):check(rows)


@pytest.mark.parametrize('replacement', [
    '1 100 S Bo:3:025:1 -115 30 = {cbw}',
    '1 100 S Bo:3:025:2 -115 31 = {cbw}',
    '1 100 E Bo:3:025:1 -115 31 = {cbw}',
    '1 100 S Bo:3:025:1 0 31 = {cbw}',
])
def test_wrong_reset_submission(replacement):
    rows=capture(); cbw=rows[0].split(' = ')[1]; rows[0]=replacement.format(cbw=cbw)
    with pytest.raises(ValueError):check(rows)


@pytest.mark.parametrize('field,value', [('busnum','4'),('devnum','25'),('path','3-3')])
def test_new_binding_is_changed_address_same_port(field,value):
    new=dict(NEW);new[field]=value
    with pytest.raises(ValueError):check(capture(),new=new)


@pytest.mark.parametrize('byte,value', [(8,0),(12,0),(13,1),(14,6),(20,2)])
def test_reset_cbw_geometry_and_arg_exact(byte,value):
    rows=capture();data=bytearray.fromhex(rows[0].split(' = ')[1]);data[byte]=value
    rows[0]=rows[0].split(' = ')[0]+' = '+data.hex()
    with pytest.raises(ValueError):check(rows)


def test_second_reset_and_later_old_command_rejected():
    rows=capture()+capture()
    # Keep chronology valid, while retaining the exact repeated request.
    for i in range(4,8):
        fields=rows[i].split();fields[1]=str(108+i);rows[i]=' '.join(fields)
    with pytest.raises(ValueError):check(rows)


def test_failed_out_cannot_prove_transmission():
    rows=capture();rows[1]=rows[1].replace(' 0 31',' -108 0')
    with pytest.raises(ValueError):check(rows)


def test_early_completion_duplicate_and_chronology_rejected():
    for rows in (capture()[1:]+capture()[:1], capture()[:1]+capture(),
                 [capture()[0],capture()[1].replace('101','99'),*capture()[2:]]):
        with pytest.raises(ValueError):check(rows)


@pytest.mark.parametrize('status,length,data', [(-110,0,b''),(-108,16,b''),(-108,0,b'x')])
def test_only_exact_disconnect_tail(status,length,data):
    rows=capture();rows[-1]=f'2 103 C Bi:3:025:1 {status} {length}' + (' = '+data.hex() if data else '')
    with pytest.raises(ValueError):check(rows)


def test_success_echo_and_csw_both_required():
    for row in (3,5):
        rows=capture('reply');prefix,data=rows[row].split(' = ')
        modified=bytearray.fromhex(data);modified[-1]^=1;rows[row]=prefix+' = '+modified.hex()
        with pytest.raises(ValueError):check(rows)


def test_vendor_write_upload_and_extra_payload_rejected():
    for opcode in (0xfb,0xfd,0xfc):
        rows=capture();data=bytearray.fromhex(rows[0].split(' = ')[1]);data[15]=opcode;data[16]=0x04
        rows[0]=rows[0].split(' = ')[0]+' = '+data.hex()
        with pytest.raises(ValueError):check(rows)
    rows=capture();rows.append('3 104 S Bo:3:026:1 -115 256 = 00')
    with pytest.raises(ValueError):check(rows)


def test_lock_sense_must_be_immediate_exact_and_successful():
    original=capture(lock=True)
    for row in (7,11):
        rows=list(original);prefix,data=rows[row].split(' = ');modified=bytearray.fromhex(data)
        modified[-1]^=1;rows[row]=prefix+' = '+modified.hex()
        with pytest.raises(ValueError):check(rows)
    with pytest.raises(ValueError):check(original[:-6])


def test_other_devices_and_control_transfers_grant_no_authority():
    rows=capture()+['aa 200 S Bo:3:027:1 -115 31 = 00','bb 201 C Ci:3:026:0 0 18 = 00']
    assert check(rows)['reset_cbw_transmitted'] is True
    with pytest.raises(ValueError):check(rows[4:])


def test_native_usbmon_direction_markers_are_exact():
    rows=capture();rows[1]+=' >';rows[2]+=' <'
    assert check(rows)['reset_cbw_transmitted']
    rows[1]=rows[1][:-1]+'<'
    with pytest.raises(ValueError):check(rows)


def test_ascii_and_size_bound():
    for raw in (b'\xff', b'x'*(16*1048576+1), 'text'):
        with pytest.raises((ValueError,UnicodeDecodeError)):wire.verify_reset_wire(raw,OLD,NEW)


def envelope(completed=False):
    old = dict(OLD,vid='4c4a',pid='8057')
    fresh = dict(observed_at=12,usb_binding=dict(NEW,vid='4c4a',pid='8057'))
    config = dict(usb_binding=old,sg_binding={'node':'/dev/sg0'},adapter_sha256='a'*64,
                  install_campaign_sha256='b'*64,install_commands_sha256='c'*64,target_sha256='d'*64)
    raw = json.dumps(config).encode()
    first = dict(config,time=10,event='trace_target_reset_prepared',
                 campaign_sha256=hashlib.sha256(raw).hexdigest(),trace_nonce='e'*32,
                 backup_manifest_sha256='f'*64,commands=1,flash_operations=0,upload_operations=0,
                 kernel_exclusivity=False,boot_observed=False,display_observed=False,
                 physical_recovery_verified=False)
    intent = dict(time=10.1,event='reset_submit_intent',phase='active-fixed-loader',
                  cdb=wire.RESET_CDB.hex(),in_len=16,out_len=0,retry=False,boot_observed=False)
    if completed:
        sg=dict(time=10.2,event='reset_sg_completion',status=0,masked=0,msg=0,host=0,driver=0,
                resid=0,info=0,sense_len=0,sense_hex='',retry=False,boot_observed=False)
        terminal=dict(time=11,event='reset_request_completed',request_completion=True,
                      core_reset_observed=False,boot_observed=False,retry=False,
                      display_observed=False,physical_recovery_verified=False)
        events=[first,intent,sg,terminal]
    else:
        terminal=dict(time=11,event='reset_stopped_ambiguous',error='ValueError',
                      detail='Exactly one SG device on pinned topology required',retry=False,
                      core_reset_observed=False,boot_observed=False,display_observed=False,
                      physical_recovery_verified=False)
        events=[first,intent,terminal]
    return raw,events,old,fresh


def validate_events(raw,events,old,fresh,form='detach'):
    commands=('\n'.join(json.dumps(e) for e in events)+'\n').encode()
    return wire.validate(('\n'.join(capture(form))+'\n').encode(),commands,raw,old,fresh,11)


@pytest.mark.parametrize('completed',[False,True])
def test_complete_trace_envelope_preserves_original_hashes_and_ambiguity(completed):
    raw,events,old,fresh=envelope(completed)
    result=validate_events(raw,events,old,fresh,'reply' if completed else 'detach')
    assert result['campaign_sha256']==hashlib.sha256(raw).hexdigest()
    assert result['reset_terminal_time']==11 and result['rom_observed_at']==12
    assert result['upload_operations']==result['flash_operations']==0
    assert result['sg_request_completed'] is False


@pytest.mark.parametrize('index,key,value',[
    (0,'campaign_sha256','0'*64),(0,'target_sha256','0'*64),(0,'flash_operations',1),
    (0,'commands',True),(0,'upload_operations',1),(0,'boot_observed',True),
    (1,'retry',True),(1,'out_len',1),(1,'cdb','fc1200000001ffffffffffffffffffff'),
    (2,'event','reset_request_completed'),(2,'core_reset_observed',True),
    (2,'time',float('nan')),
])
def test_inconsistent_trace_envelope_rejects(index,key,value):
    raw,events,old,fresh=envelope();events[index][key]=value
    with pytest.raises(ValueError):validate_events(raw,events,old,fresh)


def test_bare_intent_missing_terminal_or_completion_without_csw_rejects():
    raw,events,old,fresh=envelope()
    with pytest.raises(ValueError):validate_events(raw,events[:2],old,fresh)
    raw,events,old,fresh=envelope(True)
    with pytest.raises(ValueError):validate_events(raw,events,old,fresh)


@pytest.mark.parametrize('mutation', ['old_snapshot','wrong_pid','wrong_port','same_address'])
def test_original_fresh_rom_lineage_required(mutation):
    raw,events,old,fresh=envelope()
    if mutation=='old_snapshot':fresh['observed_at']=10
    elif mutation=='wrong_pid':fresh['usb_binding']['pid']='c755'
    elif mutation=='wrong_port':fresh['usb_binding']['path']='3-4'
    else:fresh['usb_binding']['devnum']='25'
    with pytest.raises(ValueError):validate_events(raw,events,old,fresh)
