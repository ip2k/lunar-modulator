"""Local firmware projects: immutable source/revisions and hash-bound analysis.

A .fm1proj is a private SQLite file containing firmware bytes. Do not commit or
share it as an analysis report. No device, browser, or vendor tool is involved.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import closing
from functools import lru_cache
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any

try:
    from . import fm1_package, fm1_rebuild
except ImportError:
    import fm1_package, fm1_rebuild


SCHEMA_VERSION = 1
MAX_PROJECT_BYTES = 512 * 1024 * 1024
MAX_REVISIONS = 128
MAX_JSON_BYTES = 32 * 1024 * 1024

SCHEMA_SQL = """
    CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE revisions (
        id INTEGER PRIMARY KEY,
        parent_id INTEGER REFERENCES revisions(id),
        label TEXT NOT NULL,
        sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
        size INTEGER NOT NULL CHECK(size > 0),
        data BLOB NOT NULL,
        manifest_json TEXT,
        CHECK(length(data) = size)
    );
    CREATE TABLE analyses (
        revision_id INTEGER PRIMARY KEY REFERENCES revisions(id),
        report_json TEXT NOT NULL
    );
    CREATE TRIGGER immutable_revision_update BEFORE UPDATE ON revisions
        BEGIN SELECT RAISE(ABORT, 'revisions are immutable'); END;
    CREATE TRIGGER immutable_revision_delete BEFORE DELETE ON revisions
        BEGIN SELECT RAISE(ABORT, 'revisions are immutable'); END;
    CREATE TRIGGER immutable_metadata_update BEFORE UPDATE ON metadata
        BEGIN SELECT RAISE(ABORT, 'metadata is immutable'); END;
    CREATE TRIGGER immutable_metadata_delete BEFORE DELETE ON metadata
        BEGIN SELECT RAISE(ABORT, 'metadata is immutable'); END;
"""


class ProjectError(ValueError):
    """Project or revision does not satisfy its recorded integrity constraints."""


def _schema_signature(db: sqlite3.Connection) -> tuple:
    # GLOB treats '_' literally; LIKE 'sqlite_%' would also hide sqliteXevil.
    count = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'").fetchone()[0]
    if count != 7:
        raise ProjectError("project database has a noncanonical schema")
    rows = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' ORDER BY type,name")
    return tuple((row[0], row[1], row[2], " ".join((row[3] or "").split())) for row in rows)


@lru_cache(maxsize=1)
def _canonical_schema() -> tuple:
    with closing(sqlite3.connect(":memory:")) as db:
        db.executescript(SCHEMA_SQL)
        return _schema_signature(db)


def _verify_schema(db: sqlite3.Connection) -> None:
    if _schema_signature(db) != _canonical_schema():
        raise ProjectError("project database has a noncanonical schema")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True)
    if len(encoded) > MAX_JSON_BYTES:
        raise ProjectError("project metadata exceeds the size limit")
    return encoded


def _parse_json(encoded: str) -> Any:
    if not isinstance(encoded, str) or len(encoded) > MAX_JSON_BYTES:
        raise ProjectError("project metadata has an invalid type or exceeds the size limit")
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProjectError("project metadata contains duplicate JSON keys")
            result[key] = value
        return result
    return json.loads(encoded, object_pairs_hook=unique_keys)


def _inspect(data: bytes, kind: str) -> dict:
    if kind == "fwsc":
        return fm1_package.inspect_package(data)
    if kind == "app":
        return fm1_package.inspect_application(data)
    raise ProjectError("firmware kind must be 'fwsc' or 'app'")


def _label(label: str) -> str:
    if not isinstance(label, str) or len(label) > 256 or any(ord(c) < 32 for c in label):
        raise ProjectError("label must be printable text of at most 256 characters")
    # Paths belong to the file picker, not to portable project metadata.
    if "/" in label or "\\" in label:
        raise ProjectError("use a label, not a filesystem path")
    return label


class FirmwareProject:
    """A single project file. Methods can be called from worker threads.

    Each method opens its own short-lived connection. Byte-bearing revisions
    are append-only. Analyses can be replaced, but only for their exact hash.
    """

    def __init__(self, path: Path):
        self.path = path

    @classmethod
    def create(cls, path: str | Path, data: bytes, kind: str, label: str = "") -> "FirmwareProject":
        target = Path(path).resolve()
        if target.suffix.lower() != ".fm1proj":
            raise ProjectError("project filenames must end in .fm1proj")
        label = _label(label)
        _inspect(data, kind)
        # Exclusive creation prevents replacing a source, project, or existing file.
        with target.open("xb"):
            pass
        project = cls(target)
        try:
            with project._connect() as db:
                db.executescript(SCHEMA_SQL)
                db.executemany("INSERT INTO metadata VALUES (?, ?)", [
                    ("schema_version", str(SCHEMA_VERSION)), ("kind", kind),
                    ("label", label), ("source_sha256", _hash(data)),
                ])
                db.execute("INSERT INTO revisions VALUES (1, NULL, ?, ?, ?, ?, NULL)",
                           ("Original", _hash(data), len(data), data))
            return cls.open(target)
        except Exception:
            # Only remove the new file owned by this failed create operation.
            target.unlink(missing_ok=True)
            raise

    @classmethod
    def open(cls, path: str | Path) -> "FirmwareProject":
        project = cls(Path(path).resolve(strict=True))
        if not project.path.is_file() or project.path.stat().st_size > MAX_PROJECT_BYTES:
            raise ProjectError("project file is missing or exceeds the size limit")
        try:
            with project._connect(readonly=True) as db:
                db.execute("BEGIN")
                _verify_schema(db)
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ProjectError("project database integrity check failed")
                metadata = project._metadata(db)
                count = db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
                if not 0 < count <= MAX_REVISIONS:
                    raise ProjectError("invalid project revision count")
                hashes = {}
                for row in db.execute("SELECT * FROM revisions ORDER BY id"):
                    project._verify_revision(row)
                    if row["id"] == 1:
                        if row["parent_id"] is not None or row["manifest_json"] is not None:
                            raise ProjectError("original revision cannot have a parent or change manifest")
                        if row["sha256"] != metadata["source_sha256"]:
                            raise ProjectError("original firmware hash does not match project metadata")
                    else:
                        parent_hash = hashes.get(row["parent_id"])
                        project._verify_manifest(row["manifest_json"], parent_hash, row["sha256"], metadata["kind"])
                    hashes[row["id"]] = row["sha256"]
                if 1 not in hashes:
                    raise ProjectError("project has no original revision")
                for row in db.execute("SELECT * FROM analyses"):
                    project._verify_analysis(row["report_json"], hashes.get(row["revision_id"]))
            return project
        except (sqlite3.DatabaseError, KeyError, TypeError, json.JSONDecodeError, RecursionError) as error:
            raise ProjectError(f"invalid firmware project: {error}") from error

    def _connect(self, readonly: bool = False) -> _ClosingConnection:
        if readonly:
            db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=10)
        else:
            db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA trusted_schema=OFF")
            if hasattr(db, "setlimit"):  # Added in Python 3.11; schema/file bounds also cover 3.10.
                db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_JSON_BYTES + fm1_package.MAX_INPUT_SIZE + 65536)
            return _ClosingConnection(db)
        except Exception:
            db.close()
            raise

    @staticmethod
    def _metadata(db: sqlite3.Connection) -> dict:
        metadata = dict(db.execute("SELECT key, value FROM metadata"))
        if metadata.get("schema_version") != str(SCHEMA_VERSION):
            raise ProjectError("unsupported project schema version")
        if metadata.get("kind") not in ("fwsc", "app"):
            raise ProjectError("invalid project firmware kind")
        if not metadata.get("source_sha256") or len(metadata["source_sha256"]) != 64:
            raise ProjectError("invalid original firmware hash")
        return metadata

    @staticmethod
    def _verify_revision(row: sqlite3.Row) -> None:
        data = row["data"]
        if not isinstance(data, bytes) or not 0 < len(data) <= fm1_package.MAX_INPUT_SIZE:
            raise ProjectError("revision has an invalid firmware size")
        if len(data) != row["size"] or _hash(data) != row["sha256"]:
            raise ProjectError(f"revision {row['id']} firmware hash/size mismatch")

    @staticmethod
    def _verify_manifest(encoded: str, parent_hash: str | None, result_hash: str, kind: str) -> dict:
        manifest = _parse_json(encoded) if encoded else None
        if not isinstance(manifest, dict) or not parent_hash:
            raise ProjectError("revision requires an existing parent and a change manifest")
        if manifest.get("source_sha256") != parent_hash or manifest.get("result_sha256") != result_hash:
            raise ProjectError("change manifest hashes do not match parent and result firmware")
        if manifest.get("input_kind") != {"fwsc": "package", "app": "application"}[kind]:
            raise ProjectError("change manifest has a different firmware kind")
        if (manifest.get("kind") != fm1_rebuild.MANIFEST_KIND
                or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1
                or manifest.get("operation") not in ("rebuild", "rollback")):
            raise ProjectError("change manifest has an unsupported format")
        unsealed = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        if fm1_rebuild._seal(unsealed)["manifest_sha256"] != manifest.get("manifest_sha256"):
            raise ProjectError("change manifest digest does not match its contents")
        if (not isinstance(manifest.get("source"), dict) or not isinstance(manifest.get("output"), dict)
                or manifest["source"].get("sha256") != parent_hash
                or manifest["output"].get("sha256") != result_hash):
            raise ProjectError("change manifest metadata hashes disagree")
        return manifest

    @staticmethod
    def _verify_analysis(encoded: str, source_hash: str | None) -> dict:
        report = _parse_json(encoded)
        if not isinstance(report, dict) or not source_hash:
            raise ProjectError("analysis requires an existing firmware revision")
        if report.get("source_sha256", report.get("sha256")) != source_hash:
            raise ProjectError("analysis hash does not match firmware revision")
        return report

    def summary(self) -> dict:
        with self._connect(readonly=True) as db:
            result = self._metadata(db)
            result["revision_count"] = db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
            return result

    def revisions(self) -> list[dict]:
        with self._connect(readonly=True) as db:
            rows = db.execute("SELECT id, parent_id, label, sha256, size, manifest_json FROM revisions ORDER BY id").fetchall()
            return [{**{key: row[key] for key in ("id", "parent_id", "label", "sha256", "size")},
                     "manifest": _parse_json(row["manifest_json"]) if row["manifest_json"] else None} for row in rows]

    def read_revision(self, revision_id: int = 1) -> bytes:
        with self._connect(readonly=True) as db:
            row = db.execute("SELECT * FROM revisions WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise ProjectError("revision does not exist")
            self._verify_revision(row)
            return row["data"]

    def add_revision(self, data: bytes, manifest: dict, parent_id: int = 1, label: str = "") -> int:
        label = _label(label)
        encoded = _json(manifest)
        summary = self.summary()
        _inspect(data, summary["kind"])
        result_hash = _hash(data)
        with self._connect() as db:
            # Reserve a write transaction before checking the revision count and parent.
            db.execute("BEGIN IMMEDIATE")
            _verify_schema(db)
            metadata = self._metadata(db)
            if metadata["kind"] != summary["kind"]:
                raise ProjectError("project firmware kind changed during the operation")
            if db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] >= MAX_REVISIONS:
                raise ProjectError("project revision limit reached")
            parent = db.execute("SELECT * FROM revisions WHERE id=?", (parent_id,)).fetchone()
            if parent is None:
                raise ProjectError("parent revision does not exist")
            self._verify_revision(parent)
            checked_manifest = self._verify_manifest(encoded, parent["sha256"], result_hash, metadata["kind"])
            reverse = fm1_rebuild.rollback_package if metadata["kind"] == "fwsc" else fm1_rebuild.rollback_application
            try:
                restored, _ = reverse(data, checked_manifest)
            except ValueError as error:
                raise ProjectError(f"change manifest cannot reverse this revision: {error}") from error
            if restored != parent["data"]:
                raise ProjectError("change manifest does not restore the exact parent revision")
            if self.path.stat().st_size + len(data) + len(encoded) > MAX_PROJECT_BYTES:
                raise ProjectError("project size limit reached")
            row = db.execute("INSERT INTO revisions (parent_id,label,sha256,size,data,manifest_json) VALUES (?,?,?,?,?,?)",
                             (parent_id, label or "Modified", result_hash, len(data), data, encoded))
            return row.lastrowid

    def record_analysis(self, revision_id: int, report: dict) -> None:
        encoded = _json(report)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            _verify_schema(db)
            row = db.execute("SELECT sha256 FROM revisions WHERE id=?", (revision_id,)).fetchone()
            self._verify_analysis(encoded, row[0] if row else None)
            if self.path.stat().st_size + len(encoded) > MAX_PROJECT_BYTES:
                raise ProjectError("project size limit reached")
            db.execute("INSERT INTO analyses VALUES (?,?) ON CONFLICT(revision_id) DO UPDATE SET report_json=excluded.report_json",
                       (revision_id, encoded))

    def snapshot_bytes(self) -> bytes:
        """Export a checked, consistent SQLite backup while other methods run."""
        with TemporaryDirectory(prefix=".fm1-snapshot-", dir=self.path.parent) as temporary:
            target = Path(temporary) / "snapshot.fm1proj"
            with self._connect(readonly=True) as source:
                source.execute("BEGIN")
                _verify_schema(source)
                with closing(sqlite3.connect(target)) as destination:
                    source.backup(destination)
            self.open(target)
            return target.read_bytes()

    def analysis(self, revision_id: int) -> dict | None:
        with self._connect(readonly=True) as db:
            row = db.execute("SELECT a.report_json, r.sha256 FROM analyses a JOIN revisions r ON a.revision_id=r.id WHERE a.revision_id=?",
                             (revision_id,)).fetchone()
            return self._verify_analysis(row[0], row[1]) if row else None

    def export_revision(self, revision_id: int, path: str | Path) -> dict:
        data = self.read_revision(revision_id)
        suffix = ".fwsc" if self.summary()["kind"] == "fwsc" else ".bin"
        target = Path(path).resolve()
        if target.suffix.lower() != suffix:
            raise ProjectError(f"this firmware revision must be exported as {suffix}")
        with target.open("xb") as output:
            output.write(data)
        return {"sha256": _hash(data), "size": len(data), "revision_id": revision_id}


class _ClosingConnection:
    """SQLite's own context manager commits but does not close the connection."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def __enter__(self) -> sqlite3.Connection:
        return self.connection.__enter__()

    def __exit__(self, *args) -> bool:
        try:
            return self.connection.__exit__(*args)
        finally:
            self.connection.close()
