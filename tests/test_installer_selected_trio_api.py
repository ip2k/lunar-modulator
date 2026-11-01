# SPDX-License-Identifier: MIT
"""TestClient-only HTTP and lifecycle witnesses; no native work or listeners."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from tools.installer_service.api import (FakeJobAdapter, WorkerResult, WorkerSnapshot,
    WorkerTemplate, create_selected_trio_app)
from tools.installer_service import selected_trio_profile as profile
from tools.installer_service.request_contract import canonical_request
from tools.installer_service.docker_adapter import DockerJobAdapter

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


class ProductionCleanupAdapter(Adapter):
    """Synthetic submission/result, but the actual production cleanup method."""

    def delete(self, identifier):
        self.events.append("delete")
        DockerJobAdapter.delete(self, identifier)

    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime
        self.config = SimpleNamespace(profile_id=profile.SELECTED_TRIO_PROFILE)
        self.lock = threading.RLock()
        self.created, self.job_dirs, self.threads, self.processes = {}, {}, {}, {}
        self.cleanup_confirmed, self.cleanup_unconfirmed = set(), set()

    def submit(self, identifier, *args):
        super().submit(identifier, *args)
        base = self.runtime / identifier
        base.mkdir()
        (base / "private-evidence").write_bytes(b"owned synthetic evidence")
        self.created[identifier] = 0
        self.job_dirs[identifier] = base

    def complete(self, identifier, result=None):
        self.cleanup_confirmed.add(identifier)
        return super().complete(identifier, result)

    def fail(self, identifier):
        self.cleanup_confirmed.add(identifier)
        super().fail(identifier)

    def shutdown(self):
        self.events.append("shutdown")
        DockerJobAdapter.shutdown(self)


@pytest.mark.parametrize("failure", ["noop", "error"])
def test_actual_delete_keeps_capacity_and_evidence_until_confirmed_recovery(tmp_path, monkeypatch, failure):
    from tools.installer_service import docker_adapter
    adapter = ProductionCleanupAdapter(tmp_path)
    now = [0]
    original = docker_adapter.shutil.rmtree
    def refuse(*args, **kwargs):
        if failure == "error": raise PermissionError("synthetic removal denied")
    monkeypatch.setattr(docker_adapter.shutil, "rmtree", refuse)
    with TestClient(app(adapter, record_cap=1, clock=lambda:now[0], retention_seconds=60),
                    base_url="http://localhost") as client:
        identifier = submit(client)
        adapter.fail(identifier)
        base = adapter.job_dirs[identifier]
        now[0] = 61
        assert client.get(PATH + "/" + identifier).json()["status"] == "failed"
        assert client.post(PATH, json=request()).status_code == 429
        assert adapter.get(identifier).status == "failed"
        assert adapter.job_dirs[identifier] == base and identifier in adapter.created
        assert identifier in adapter.cleanup_confirmed
        assert (base / "private-evidence").read_bytes() == b"owned synthetic evidence"
        monkeypatch.setattr(docker_adapter.shutil, "rmtree", original)
        assert client.get(PATH + "/" + identifier).status_code == 404
        assert adapter.get(identifier) is None and not base.exists()
        assert identifier not in adapter.job_dirs and identifier not in adapter.created
        assert identifier not in adapter.cleanup_confirmed
        adapter.fail(submit(client))
    assert not adapter.jobs and not list(tmp_path.iterdir())


def test_actual_delete_shutdown_retains_failed_removal_for_later_recovery(tmp_path, monkeypatch):
    from tools.installer_service import docker_adapter
    adapter = ProductionCleanupAdapter(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(docker_adapter.shutil, "rmtree", lambda *a, **k:None)
        with TestClient(app(adapter, record_cap=1), base_url="http://localhost") as client:
            identifier = submit(client)
            adapter.fail(identifier)
            base = adapter.job_dirs[identifier]
        assert adapter.get(identifier).status == "failed" and base.is_dir()
    adapter.delete(identifier)
    assert adapter.get(identifier) is None and not base.exists()


@pytest.mark.parametrize("guard", ["container", "worker", "process", "queued", "running",
    "unconfirmed", "missing-owner", "symlink", "stat-error"])
def test_actual_delete_preserves_live_or_uncertain_ownership(tmp_path, monkeypatch, guard):
    from pathlib import Path
    from tools.installer_service import docker_adapter
    adapter = ProductionCleanupAdapter(tmp_path)
    identifier = "a" * 32
    adapter.submit(identifier, b"{}", "unused", TEMPLATE)
    adapter.fail(identifier)
    base = adapter.job_dirs[identifier]
    if guard == "container": adapter.cleanup_unconfirmed.add(identifier)
    elif guard == "worker": adapter.threads[identifier] = SimpleNamespace(is_alive=lambda:True)
    elif guard == "process": adapter.processes[identifier] = SimpleNamespace(poll=lambda:None)
    elif guard in ("queued", "running"): adapter.jobs[identifier] = WorkerSnapshot(guard)
    elif guard == "unconfirmed": adapter.cleanup_confirmed.clear()
    elif guard == "missing-owner": adapter.job_dirs.pop(identifier)
    elif guard == "symlink":
        moved = tmp_path / "foreign"
        base.rename(moved)
        base.symlink_to(moved, target_is_directory=True)
    elif guard == "stat-error":
        original = Path.lstat
        def inaccessible(path):
            if path == base: raise PermissionError("synthetic inaccessible entry")
            return original(path)
        monkeypatch.setattr(Path, "lstat", inaccessible)
    if guard != "symlink":
        monkeypatch.setattr(docker_adapter.shutil, "rmtree", lambda *a, **k:pytest.fail("no removal"))
    adapter.delete(identifier)
    assert adapter.get(identifier).status == (guard if guard in ("queued", "running") else "failed")
    assert identifier in adapter.created
    assert identifier in adapter.cleanup_confirmed or guard == "unconfirmed"
    assert (base / "private-evidence").read_bytes() == b"owned synthetic evidence"


def test_actual_delete_serializes_ownership_until_confirmed_absence(tmp_path, monkeypatch):
    from tools.installer_service import docker_adapter
    adapter = ProductionCleanupAdapter(tmp_path)
    identifier = "b" * 32
    adapter.submit(identifier, b"{}", "unused", TEMPLATE)
    adapter.fail(identifier)
    base = adapter.job_dirs[identifier]
    entered, release = threading.Event(), threading.Event()
    original = docker_adapter.shutil.rmtree
    def blocked(path):
        entered.set()
        assert release.wait(3)
        original(path)
    monkeypatch.setattr(docker_adapter.shutil, "rmtree", blocked)
    with ThreadPoolExecutor(max_workers=1) as executor:
        deletion = executor.submit(adapter.delete, identifier)
        try:
            assert entered.wait(2)
            assert not adapter.lock.acquire(blocking=False)
            assert identifier in adapter.jobs and adapter.job_dirs[identifier] == base
        finally: release.set()
        deletion.result(timeout=3)
    assert adapter.get(identifier) is None and not base.exists()


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
    ("package_admitted",True),("rom_return",True),("extra_claim","safe"),("set_ids",[])])
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


def test_selected_capacity_and_evidence_limits_are_separate_from_legacy():
    from tools.installer_service.api import SELECTED_MAX_PRIVATE_EVIDENCE_BYTES
    with pytest.raises(ValueError,match="four jobs"): app(Adapter(),record_cap=5)
    adapter=Adapter()
    with TestClient(app(adapter),base_url="http://localhost") as client:
        identifier=submit(client); result=adapter.complete(identifier)
        adapter.complete(identifier,replace(result,private_evidence={"large":b"x"*(SELECTED_MAX_PRIVATE_EVIDENCE_BYTES+1)}))
        assert client.get(PATH+"/"+identifier).status_code==502
        assert not adapter.calls


def test_unconfirmed_cleanup_keeps_record_capacity_until_actual_delete():
    now=[0]
    class RecoveryAdapter(Adapter):
        unconfirmed=True
        def delete(self,identifier):
            if not self.unconfirmed: super().delete(identifier)
    adapter=RecoveryAdapter()
    with TestClient(app(adapter,clock=lambda:now[0],retention_seconds=60),base_url="http://localhost") as client:
        identifiers=[]
        for _ in range(4):
            identifier=submit(client);identifiers.append(identifier);adapter.fail(identifier)
        assert client.post(PATH,json=request()).status_code==429
        now[0]=61
        assert client.get(PATH+"/"+identifiers[0]).json()["status"]=="failed"
        assert client.post(PATH,json=request()).status_code==429
        assert len(adapter.jobs)==4
        adapter.unconfirmed=False
        assert client.get(PATH+"/"+identifiers[0]).status_code==404
        submit(client)


@pytest.mark.parametrize("production_cleanup", [False, True])
def test_cancelled_http_waiter_does_not_release_verification_or_cleanup_early(monkeypatch, tmp_path, production_cleanup):
    import asyncio
    from tools.installer_service import api
    adapter=ProductionCleanupAdapter(tmp_path) if production_cleanup else Adapter()
    entered=threading.Event();release=threading.Event();draining=threading.Event()
    class ObservedExecutor(ThreadPoolExecutor):
        def shutdown(self,*args,**kwargs):
            draining.set()
            return super().shutdown(*args,**kwargs)
    monkeypatch.setattr(api,"ThreadPoolExecutor",ObservedExecutor)
    def blocked(value):
        entered.set()
        if not release.wait(5): raise AssertionError("test must release verifier")
        return value
    adapter.mutation=blocked
    selected_app=app(adapter)
    async def cancelled_get(identifier):
        # Invoke ASGI through TestClient's portal to cancel the HTTP waiter while
        # the real executor callback is running. No listener or socket is used.
        path=PATH+"/"+identifier
        scope=dict(type="http",asgi={"version":"3.0"},http_version="1.1",method="GET",
            scheme="http",path=path,raw_path=path.encode(),query_string=b"",root_path="",
            headers=[(b"host",b"localhost")],client=("127.0.0.1",1),server=("localhost",80))
        async def receive():
            await asyncio.Future()
        async def send(_): pass
        await selected_app(scope,receive,send)
    with ThreadPoolExecutor(max_workers=1) as observer:
        def release_on_shutdown():
            assert draining.wait(3)
            assert "shutdown" not in adapter.events and "delete" not in adapter.events
            assert client.post(PATH,json=request()).status_code==503
            assert client.get(PATH+"/"+identifier).status_code==503
            release.set()
        with TestClient(selected_app,base_url="http://localhost") as client:
            identifier=submit(client);adapter.complete(identifier)
            pending=client.portal.start_task_soon(cancelled_get,identifier)
            assert entered.wait(2)
            assert pending.cancel()
            assert client.get(PATH+"/"+identifier).status_code==503
            watcher=observer.submit(release_on_shutdown)
        watcher.result(timeout=3)
    assert adapter.events[-2:]==["shutdown","delete"]


def test_legacy_factory_stays_v1_only():
    from tools.installer_service.api import create_app
    legacy=create_app(adapter=Adapter(),template=TEMPLATE,module_kinds={"trio":"sound"},
                      project_ids={"init-starter-trio"})
    with TestClient(legacy) as client:
        assert client.post("/api/v1/builds",json=request()).status_code==422
        assert client.post(PATH,json=request()).status_code==404
        value=request(version=1)
        for key in ("profile_id","runtime_mode","flash_layout"): value.pop(key)
        assert client.post("/api/v1/builds",json=value).status_code==202



def test_selected_requires_active_lifespan_and_can_restart_cleanly():
    adapter=Adapter(); selected_app=app(adapter)
    client=TestClient(selected_app,base_url="http://localhost")
    assert client.post(PATH,json=request()).status_code==503
    assert not adapter.submissions
    client.close()
    for _ in range(2):
        with TestClient(selected_app,base_url="http://localhost") as running:
            identifier=submit(running);adapter.complete(identifier)
            assert running.get(PATH+"/"+identifier).status_code==200
        assert not adapter.jobs


def test_selected_deletes_owned_records_even_for_adapter_without_shutdown_method():
    adapter=FakeJobAdapter(1)
    selected_app=create_selected_trio_app(adapter=adapter,template=TEMPLATE,
        source_commit=COMMIT,source_tree_oid=TREE,verify_result=lambda *_:None,enable_private_builds=True)
    with TestClient(selected_app,base_url="http://localhost") as client: submit(client)
    assert not adapter.jobs and not adapter.submissions
