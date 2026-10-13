"""Device-free post-child binding checks using the real wrapper function."""
import json
from types import SimpleNamespace
import pytest
from test_outer_lifecycle import load

@pytest.fixture
def binding():
    usb=dict(path='1-1',busnum='1',devnum='13',vid='4c4a',pid='8057')
    observed=dict(node='/dev/sg0',node_identity=(6,1464,5376),
        class_identity=(19,46829,0),device_identity=(19,46770,0),
        usb_identity=(19,46586,0))
    retained=json.loads(json.dumps(observed))
    bridge=SimpleNamespace(usb_snapshot=lambda _:dict(usb),validate_usb=lambda _:None,
        discover_sg=lambda _:observed)
    prepared=SimpleNamespace(bridge=bridge,snapshot=json.dumps({'sg_binding':retained}).encode(),
        mapping=json.dumps(retained).encode())
    return usb,observed,prepared

@pytest.mark.parametrize('mode',['backup','restore'])
def test_tuple_stat_identity_matches_retained_json(binding,mode):
    usb,observed,prepared=binding
    receipt=load('owned-admitted-backup-restore-once.py').passive_snapshot(prepared,mode,usb,'a'*64)
    assert receipt['sg_binding']==observed
    assert receipt['quiet_state']=='same-loader-no-later-commands'

@pytest.mark.parametrize('mode',['backup','restore'])
@pytest.mark.parametrize('field',['node_identity','class_identity','device_identity','usb_identity'])
@pytest.mark.parametrize('replacement',[(19,99999,0),('19',46829,0)])
def test_changed_identity_or_numeric_type_is_rejected(binding,mode,field,replacement):
    usb,observed,prepared=binding;observed[field]=replacement
    with pytest.raises(ValueError,match='passive SG mapping changed'):
        load('owned-admitted-backup-restore-once.py').passive_snapshot(prepared,mode,usb,'a'*64)

@pytest.mark.parametrize('mode',['backup','restore'])
def test_extra_binding_field_is_rejected(binding,mode):
    usb,observed,prepared=binding;observed['unexpected']='changed'
    with pytest.raises(ValueError,match='passive SG mapping changed'):
        load('owned-admitted-backup-restore-once.py').passive_snapshot(prepared,mode,usb,'a'*64)
