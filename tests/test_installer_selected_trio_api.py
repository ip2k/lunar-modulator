# SPDX-License-Identifier: MIT
"""TestClient-only HTTP and lifecycle witnesses; no native work or listeners."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import threading

from fastapi.testclient import TestClient
import pytest

from tools.installer_service.api import (FakeJobAdapter, WorkerResult, WorkerSnapshot,
    WorkerTemplate, create_selected_trio_app)
from tools.installer_service import selected_trio_profile as profile
from tools.installer_service.request_contract import canonical_request

PATH = "/api/v2/offline-builds"
COMMIT, TREE = "a" * 40, "b" * 40
TEMPLATE = WorkerTemplate("sha256:" + "c" * 64, "test-private")


def request(**changes):
    value = dict(version=2, profile_id=profile.SELECTED_TRIO_PROFILE, runtime_mode="offline",
        flash_layout="stock-sized-diagnostic", engines=["trio"], effects=[], midi=[],
        modulation=[], project_ids=["init-starter-trio"], startup_index=0)
    value.update(changes)
    return value


def summary(raw, result):
    # A synthetic callback fixture tests API binding only, never target acceptance.
    sha = lambda data: hashlib.sha256(data).hexdigest()
    return dict(version=2, profile_id=profile.SELECTED_TRIO_PROFILE, runtime_mode="offline",
        flash_layout="stock-sized-diagnostic", request_sha256=sha(raw), source_commit=COMMIT,
        source_tree_oid=TREE, receipt_sha256=sha(result.receipt), artifact_sha256=sha(result.artifact),
        elf_sha256=sha(result.elf), artifact_bytes=len(result.artifact), app_budget_bytes=profile.APP_BUDGET,
        remaining_bytes=profile.APP_BUDGET-len(result.artifact), internal_dependencies=["arp"], **profile.DENIED)


class Adapter(FakeJobAdapter):
    def __init__(self):
        super().__init__(2)
        self.calls, self.events = [], []
        self.mutation = lambda value: value

    def verify(self, identifier, raw, result):
        self.calls.append((identifier, raw, result, threading.current_thread().name))
        self.events.append("verify")
        return self.mutation(summary(raw, result))

    def complete(self, identifier, result=None):
        result = result or WorkerResult(b"synthetic flat", b"synthetic receipt", b"synthetic elf",
                                       b"synthetic provenance", {"evidence": b"bounded fixture"})
        self.jobs[identifier] = WorkerSnapshot("succeeded", result)
        return result

    def shutdown(self):
        self.events.append("shutdown")

    def delete(self, identifier):
        self.events.append("delete")
        super().delete(identifier)


def app(adapter, **changes):
    values = dict(adapter=adapter, template=TEMPLATE, source_commit=COMMIT,
                  source_tree_oid=TREE, verify_result=adapter.verify, enable_private_builds=True)
    values.update(changes)
    return create_selected_trio_app(**values)


def submit(client):
    response = client.post(PATH, json=request())
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["status_url"] == PATH + "/" + response.json()["id"]
    return response.json()["id"]


@pytest.mark.parametrize("change", [dict(enable_private_builds=False),dict(enable_private_builds=1),
    dict(verify_result=None),dict(source_commit="main"),dict(source_tree_oid="HEAD")])
def test_factory_requires_explicit_enablement_pins_and_callback(change):
    with pytest.raises(ValueError): app(Adapter(), **change)


def test_fixed_success_is_bound_private_offline_and_not_installable():
    adapter = Adapter()
    with TestClient(app(adapter), base_url="http://localhost") as client:
        identifier = submit(client)
        result = adapter.complete(identifier)
        response = client.get(PATH + "/" + identifier)
        assert response.status_code == 200
        assert response.json() == dict(id=identifier,status="succeeded",
            kind="private-selected-trio-offline-build",result=summary(canonical_request(request()), result))
        assert adapter.calls[0][:3] == (identifier, canonical_request(request()), result)
        assert adapter.calls[0][3].startswith("lunar-offline-verification")
        text = response.text
        assert "synthetic" not in text and "provenance" not in text and "evidence" not in text
        for field in profile.DENIED: assert response.json()["result"][field] is False
    assert adapter.events[-2:] == ["shutdown", "delete"]


@pytest.mark.parametrize("changes", [{"version":1},{"runtime_mode":"diagnostic"},
    {"flash_layout":"expanded-d9000"},{"engines":["dx7"]},{"effects":["hall"]},
    {"midi":["arp"]},{"modulation":["lfo"]},{"set_ids":["set"]},
    {"project_ids":["another"]},{"command":"builder"},{"installable":True}])
def test_invalid_fixed_tuple_never_submits(changes):
    adapter=Adapter()
    with TestClient(app(adapter), base_url="http://localhost") as client:
        assert client.post(PATH,json=request(**changes)).status_code == 422
        assert not adapter.submissions


@pytest.mark.parametrize("raw,status,headers", [(b'{"version":2,"version":2}',422,{}),
    (b'{"version":NaN}',422,{}),(b'{"version":1e999}',422,{}),(b'\xff',422,{}),
    (b' '*65537,413,{}),(b'{}',415,{"Content-Type":"text/plain"}),
    (b'{}',415,{"Content-Encoding":"gzip"})])
def test_shared_bounded_json_refusals(raw,status,headers):
    with TestClient(app(Adapter()), base_url="http://localhost") as client:
        assert client.post(PATH,content=raw,headers={"Content-Type":"application/json",**headers}).status_code == status


@pytest.mark.parametrize("field,value", [("version",1),("source_commit","f"*40),
    ("source_tree_oid","f"*40),("request_sha256","0"*64),("artifact_sha256","0"*64),
    ("elf_sha256","0"*64),("receipt_sha256","0"*64),("artifact_bytes",True),
    ("app_budget_bytes",1048576),("remaining_bytes",0),("profile_id","other"),
    ("runtime_mode","diagnostic"),("internal_dependencies",[]),("installable",True),
    ("package_admitted",True),("rom_return",True),("extra_claim","safe")])
def test_self_claimed_summary_must_match_admitted_inputs(field,value):
    adapter=Adapter()
    adapter.mutation=lambda result:{**result,field:value}
    with TestClient(app(adapter),base_url="http://localhost") as client:
        identifier=submit(client);adapter.complete(identifier)
        response=client.get(PATH+"/"+identifier)
        assert response.status_code==502
        assert response.json()=={"detail":"build result failed verification"}


@pytest.mark.parametrize("field,value", [("artifact",b""),("artifact",b"x"*(profile.APP_BUDGET+1)),
    ("elf",b""),("receipt",b"x"*(profile.MAX_RECEIPT+1)),("provenance",None),
    ("private_evidence",None),("private_evidence",{"bad":True})])
def test_invalid_or_oversized_result_refuses_before_callback(field,value):
    adapter=Adapter()
    with TestClient(app(adapter),base_url="http://localhost") as client:
        identifier=submit(client); result=adapter.complete(identifier)
        adapter.complete(identifier,replace(result,**{field:value}))
        assert client.get(PATH+"/"+identifier).status_code==502
        assert not adapter.calls


def test_callback_errors_are_generic_and_raw_result_is_not_trusted():
    adapter=Adapter()
    def fail(_):raise RuntimeError("/private/proprietary/path and raw logs")
    adapter.mutation=fail
    with TestClient(app(adapter),base_url="http://localhost") as client:
        identifier=submit(client);adapter.complete(identifier)
        assert client.get(PATH+"/"+identifier).json()=={"detail":"build result failed verification"}


def test_only_offline_routes_with_loopback_host_and_no_download_docs_or_cors():
    with TestClient(app(Adapter()),base_url="http://localhost") as client:
        identifier=submit(client)
        assert client.get("/api/v1/builds/"+identifier).status_code==404
        for path in ["/docs","/redoc","/openapi.json",PATH+"/"+identifier+"/artifact"]:
            assert client.get(path).status_code==404
        assert client.post(PATH,json=request(),headers={"Host":"attacker.invalid"}).status_code==400
        response=client.options(PATH,headers={"Origin":"https://attacker.invalid",
            "Access-Control-Request-Method":"POST","Access-Control-Request-Headers":"content-type"})
        assert "access-control-allow-origin" not in response.headers
        assert client.post("/api/v1/builds",json=request()).status_code==404


def test_one_verification_slot_keeps_event_loop_responsive_and_defers_expiry():
    adapter=Adapter(); entered=threading.Event(); release=threading.Event(); now=[0]
    def blocked(value):
        entered.set()
        if not release.wait(5): raise AssertionError("test failed to release verification")
        return value
    adapter.mutation=blocked
    with TestClient(app(adapter,clock=lambda:now[0],retention_seconds=60),base_url="http://localhost") as client:
        identifier=submit(client);adapter.complete(identifier)
        with ThreadPoolExecutor(max_workers=1) as caller:
            pending=caller.submit(client.get,PATH+"/"+identifier)
            try:
                assert entered.wait(2)
                now[0]=61
                # This must respond while the worker thread is blocked. It must
                # neither queue another future nor expire live verification.
                busy=client.get(PATH+"/"+identifier)
                assert busy.status_code==503 and busy.headers["Retry-After"]=="1"
                assert "delete" not in adapter.events
                assert client.get(PATH+"/"+"x"*32).status_code==404
            finally:release.set()
            assert pending.result(timeout=3).status_code==200
        assert client.get(PATH+"/"+identifier).status_code==404
