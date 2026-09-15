"""Private project persistence, revision integrity, and overwrite protection."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import sqlite3

import pytest

from tools.fm1_project import FirmwareProject, ProjectError
from tools import fm1_rebuild


SOURCE = b"FM-1_015\0synthetic application\0"
RESULT = SOURCE.replace(b"application", b"Application")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest(before=SOURCE, after=RESULT):
    patches = [{"offset": index, "expected_hex": bytes([left]).hex(), "replacement_hex": bytes([right]).hex()}
               for index, (left, right) in enumerate(zip(before, after)) if left != right]
    rebuilt, report = fm1_rebuild.rebuild_application(before, patches, expected_source_sha256=sha(before))
    assert rebuilt == after
    return report


def test_reopen_keeps_original_and_branch_history(tmp_path):
    path = tmp_path / "project.fm1proj"
    project = FirmwareProject.create(path, SOURCE, "app", "Synthetic firmware")
    changed = project.add_revision(RESULT, manifest(), label="Text change")
    restored = project.add_revision(SOURCE, manifest(RESULT, SOURCE), parent_id=changed, label="Restore")
    reopened = FirmwareProject.open(path)
    assert reopened.read_revision() == SOURCE
    assert reopened.read_revision(changed) == RESULT
    assert reopened.read_revision(restored) == SOURCE
    assert reopened.summary()["revision_count"] == 3
    assert [r["parent_id"] for r in reopened.revisions()] == [None, 1, changed]
    assert reopened.summary()["source_sha256"] == sha(SOURCE)


@pytest.mark.parametrize("field,bad", [
    ("source_sha256", "0" * 64), ("result_sha256", "0" * 64), ("input_kind", "package"),
])
def test_failed_revision_is_atomic(tmp_path, field, bad):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    invalid = {**manifest(), field: bad}
    with pytest.raises(ProjectError):
        project.add_revision(RESULT, invalid)
    assert project.summary()["revision_count"] == 1
    assert project.read_revision() == SOURCE


def test_analysis_cannot_be_attached_to_other_version(tmp_path):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    with pytest.raises(ProjectError, match="analysis hash"):
        project.record_analysis(1, {"source_sha256": sha(RESULT), "functions": []})
    report = {"source_sha256": sha(SOURCE), "analysis": {"functions": []}}
    project.record_analysis(1, report)
    assert project.analysis(1) == report
    assert FirmwareProject.open(project.path).analysis(1) == report


def test_source_and_metadata_are_immutable(tmp_path):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    with sqlite3.connect(project.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM revisions WHERE id=1")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE metadata SET value='bad' WHERE key='source_sha256'")


def test_reopen_and_export_detect_corrupted_revision(tmp_path):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    with sqlite3.connect(project.path) as db:
        trigger = db.execute("SELECT sql FROM sqlite_master WHERE name='immutable_revision_update'").fetchone()[0]
        db.execute("DROP TRIGGER immutable_revision_update")
        db.execute("UPDATE revisions SET data=? WHERE id=1", (RESULT,))
        db.execute(trigger)
    with pytest.raises(ProjectError, match="hash/size mismatch"):
        FirmwareProject.open(project.path)
    with pytest.raises(ProjectError, match="hash/size mismatch"):
        project.export_revision(1, tmp_path / "out.bin")
    assert not (tmp_path / "out.bin").exists()


def test_never_overwrites_existing_project_or_export(tmp_path):
    path = tmp_path / "p.fm1proj"
    project = FirmwareProject.create(path, SOURCE, "app")
    with pytest.raises(FileExistsError):
        FirmwareProject.create(path, RESULT, "app")
    target = tmp_path / "original.bin"
    target.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        project.export_revision(1, target)
    assert target.read_bytes() == b"keep"
    assert FirmwareProject.open(path).read_revision() == SOURCE
    assert project.export_revision(1, tmp_path / "new.bin")["sha256"] == sha(SOURCE)


def test_worker_threads_share_project_without_shared_sqlite_connection(tmp_path):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(project.add_revision, RESULT, manifest(), 1, f"Variant {n}") for n in range(2)]
        ids = [future.result() for future in futures]
    assert len(set(ids)) == 2
    assert FirmwareProject.open(project.path).summary()["revision_count"] == 3


def test_invalid_inputs_do_not_create_project(tmp_path):
    path = tmp_path / "bad.fm1proj"
    with pytest.raises(ValueError):
        FirmwareProject.create(path, b"bad package", "fwsc")
    assert not path.exists()
    with pytest.raises(ProjectError, match="label"):
        FirmwareProject.create(path, SOURCE, "app", "C:\\private\\file.bin")
    assert not path.exists()


def test_unknown_schema_is_rejected(tmp_path):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    with sqlite3.connect(project.path) as db:
        trigger = db.execute("SELECT sql FROM sqlite_master WHERE name='immutable_metadata_update'").fetchone()[0]
        db.execute("DROP TRIGGER immutable_metadata_update")
        db.execute("UPDATE metadata SET value='999' WHERE key='schema_version'")
        db.execute(trigger)
    with pytest.raises(ProjectError, match="schema"):
        FirmwareProject.open(project.path)


def test_imported_trigger_cannot_rewrite_original_on_revision_insert(tmp_path):
    project = FirmwareProject.create(tmp_path / "poison.fm1proj", SOURCE, "app")
    with closing(sqlite3.connect(project.path)) as db:
        db.executescript("""
            DROP TRIGGER immutable_revision_update;
            DROP TRIGGER immutable_metadata_update;
            CREATE TRIGGER poison AFTER INSERT ON revisions WHEN NEW.id > 1
            BEGIN
                UPDATE revisions SET data=NEW.data,sha256=NEW.sha256,size=NEW.size WHERE id=1;
                UPDATE metadata SET value=NEW.sha256 WHERE key='source_sha256';
            END;
        """)
    with pytest.raises(ProjectError, match="noncanonical schema"):
        FirmwareProject.open(project.path)
    # A previously opened handle also rechecks the schema under the write lock.
    with pytest.raises(ProjectError, match="noncanonical schema"):
        project.add_revision(RESULT, manifest())
    with pytest.raises(ProjectError, match="noncanonical schema"):
        project.record_analysis(1, {"source_sha256": sha(SOURCE)})
    assert project.read_revision(1) == SOURCE


@pytest.mark.parametrize("schema_change", [
    "DROP TRIGGER immutable_revision_update",
    "DROP TABLE analyses; CREATE VIEW analyses AS SELECT 1 AS revision_id, '{}' AS report_json",
    "CREATE TRIGGER sqliteXextra AFTER INSERT ON analyses BEGIN SELECT 1; END",
    "DROP TRIGGER immutable_revision_update; CREATE TRIGGER immutable_revision_update BEFORE UPDATE ON revisions BEGIN SELECT 1; END",
])
def test_missing_extra_and_changed_schema_objects_are_rejected(tmp_path, schema_change):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    with closing(sqlite3.connect(project.path)) as db:
        db.executescript(schema_change)
    with pytest.raises(ProjectError, match="noncanonical schema"):
        FirmwareProject.open(project.path)


def test_even_resealed_manifest_must_reverse_to_exact_parent(tmp_path):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    false_claim = manifest()
    false_claim["patches"] = []
    fm1_rebuild._seal(false_claim)
    with pytest.raises(ProjectError, match="cannot reverse"):
        project.add_revision(RESULT, false_claim)
    assert project.summary()["revision_count"] == 1
    assert project.read_revision() == SOURCE


def test_reopened_project_rejects_tampered_manifest_digest(tmp_path):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    project.add_revision(RESULT, manifest())
    bad = manifest()
    bad["patches"][0]["label"] = "altered without resealing"
    with closing(sqlite3.connect(project.path)) as db:
        trigger = db.execute("SELECT sql FROM sqlite_master WHERE name='immutable_revision_update'").fetchone()[0]
        db.execute("DROP TRIGGER immutable_revision_update")
        db.execute("UPDATE revisions SET manifest_json=? WHERE id=2", (json.dumps(bad),))
        db.execute(trigger)
        db.commit()
    with pytest.raises(ProjectError, match="digest"):
        FirmwareProject.open(project.path)


def test_snapshot_is_a_valid_revision_snapshot_during_concurrent_appends(tmp_path):
    project = FirmwareProject.create(tmp_path / "p.fm1proj", SOURCE, "app")
    genuine = manifest()
    def append():
        return [project.add_revision(RESULT, genuine, label=f"Branch {index}") for index in range(4)]
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(append)
        for index in range(3):
            target = tmp_path / f"snapshot-{index}.fm1proj"
            target.write_bytes(project.snapshot_bytes())
            snapshot = FirmwareProject.open(target)
            assert snapshot.read_revision(1) == SOURCE
            for revision in snapshot.revisions()[1:]:
                assert revision["parent_id"] == 1
                assert snapshot.read_revision(revision["id"]) == RESULT
        assert len(future.result()) == 4
    assert project.summary()["revision_count"] == 5
    assert not list(tmp_path.glob(".fm1-snapshot-*"))
