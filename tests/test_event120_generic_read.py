"""Fail-closed policy tests for generic, explicitly enumerated ROM reads."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fm1_event120_generic_rom_backup as read


def usb(devnum="55"):
    return {"path":"1-1", "busnum":"1", "devnum":devnum, "vid":"4c4a", "pid":"8057"}


def campaign():
    return {
        "schema":1, "kind":read.KIND, "adapter_sha256":"a"*64,
        "snapshot_path":"/private/snapshot.json", "snapshot_sha256":"b"*64,
        "loader_path":"/private/loader.bin", "profile_path":"/private/profile.json",
        "profile_source_path":"/private/profile.c", "usb_binding":usb(),
        "receipt_path":"/private/read", "expected_current_flash_sha256":"c"*64,
    }


def test_campaign_requires_external_raw_hash_and_explicit_enumeration():
    raw=read.canonical(campaign())
    assert read.validate_campaign(raw, read.digest(raw), "55")["usb_binding"] == usb()
    for expected, supplied in [("54",usb()), ("55",usb("54"))]:
        with pytest.raises(ValueError, match="Explicit expected USB"):
            read.validate_campaign(read.canonical(dict(campaign(),usb_binding=supplied)), read.digest(read.canonical(dict(campaign(),usb_binding=supplied))), expected)
    with pytest.raises(ValueError, match="externally pinned"):
        read.validate_campaign(raw, "0"*64, "55")
    with pytest.raises(ValueError, match="externally pinned"):
        read.validate_campaign(read.canonical(dict(campaign(),schema=True)), read.digest(read.canonical(dict(campaign(),schema=True))), "55")


def test_campaign_rejects_unknown_fields_and_bad_flash_hash():
    for value in (dict(campaign(), no_later_commands_attested=True), dict(campaign(), expected_current_flash_sha256="x")):
        raw=read.canonical(value)
        with pytest.raises(ValueError):
            read.validate_campaign(raw, read.digest(raw), "55")


def test_snapshot_freshness_and_usb_are_explicit():
    value={"schema":1,"kind":read.SNAPSHOT_KIND,"observed_at":1000,"usb_binding":usb(),"sg_binding":{}}
    assert read._snapshot(read.canonical(value),1000,usb()) == value
    with pytest.raises(ValueError,match="Fresh exact passive"):
        read._snapshot(read.canonical(dict(value,usb_binding=usb("54"))),1000,usb())
    with pytest.raises(ValueError,match="Fresh exact passive"):
        read._snapshot(read.canonical(dict(value,observed_at=879)),1000,usb())


def test_marker_is_per_observed_enumeration_and_mapping():
    first=read.marker_path("/private",usb("55"),{"node":"/dev/sg0"})
    assert first != read.marker_path("/private",usb("56"),{"node":"/dev/sg0"})
    assert first != read.marker_path("/private",usb("55"),{"node":"/dev/sg1"})
