"""Local web workbench state, offline development operations, and project storage."""

from collections import OrderedDict
import json
from pathlib import Path
import re
import threading
from uuid import uuid4

try:
    from . import fm1_package, fm1_rebuild
    from .fm1_project import FirmwareProject
except ImportError:
    import fm1_package
    import fm1_rebuild
    from fm1_project import FirmwareProject


MAX_SOURCES = 8
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_IMPORT_BYTES = 64 * 1024 * 1024
MAX_PROJECTS = 64
DEFAULT_PROJECT_DIR = Path(__file__).resolve().parents[1] / "scratch" / "projects"


class WorkspaceError(ValueError):
    pass


def _id(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise WorkspaceError("Invalid local source or project ID.")
    return value


def _fields(data, required, optional=()):
    if not isinstance(data, dict) or not set(required) <= data.keys() or set(data) - set(required) - set(optional):
        raise WorkspaceError("Request fields do not match this operation.")


class DevelopmentWorkspace:
    """Only explicit project saves persist uploads; transient sources are bounded."""

    def __init__(self, project_dir=None):
        self.project_dir = Path(project_dir or DEFAULT_PROJECT_DIR).resolve()
        self.sources = OrderedDict()
        self.lock = threading.RLock()

    def source(self, source_id):
        with self.lock:
            source_id = _id(source_id)
            if source_id not in self.sources:
                raise WorkspaceError("This file is no longer loaded. Reopen it or load its saved project.")
            self.sources.move_to_end(source_id)
            return self.sources[source_id]

    def analyze(self, raw, kind, manifest=None):
        if not raw or len(raw) > MAX_FILE_BYTES:
            raise WorkspaceError("Choose a nonempty firmware file of at most 8 MiB.")
        if kind == "fwsc":
            inspection, app = fm1_package.inspect_and_extract(raw)
        elif kind == "app":
            inspection, app = fm1_package.inspect_application(raw), raw
        else:
            raise WorkspaceError("Choose fwsc or app.")
        if __package__:
            from .fm1_decode import analyze_application
        else:
            from fm1_decode import analyze_application
        analysis = analyze_application(app)
        source_id = uuid4().hex
        summary = {"source_id": source_id, "kind": kind, "sha256": inspection["sha256"],
                   "size": len(raw), "application_size": len(app), "inspection": inspection,
                   "analysis": analysis, "download_url": f"/api/artifact/source/{source_id}"}
        if manifest is not None:
            summary["manifest"] = manifest
            summary["manifest_download_url"] = f"/api/artifact/manifest/{source_id}"
        with self.lock:
            self.sources[source_id] = {"raw": raw, "app": app, "summary": summary}
            while len(self.sources) > MAX_SOURCES:
                self.sources.popitem(last=False)
        return summary

    def hex_view(self, source_id, offset, length):
        if type(offset) is not int or type(length) is not int or not 1 <= length <= 4096:
            raise WorkspaceError("Hex length must be between 1 and 4096 bytes.")
        app = self.source(source_id)["app"]
        if not 0 <= offset < len(app):
            raise WorkspaceError("Offset is outside the decoded application.")
        data = app[offset:offset + length]
        return {"offset": offset, "size": len(data), "application_size": len(app),
                "hex": data.hex(" ").upper(),
                "ascii": "".join(chr(byte) if 32 <= byte < 127 else "." for byte in data)}

    def rebuild(self, request):
        _fields(request, ("source_id", "expected_source_sha256", "patches"))
        source = self.source(request["source_id"])
        kind = source["summary"]["kind"]
        function = fm1_rebuild.rebuild_package if kind == "fwsc" else fm1_rebuild.rebuild_application
        result, manifest = function(source["raw"], request["patches"],
                                    expected_source_sha256=request["expected_source_sha256"])
        return self.analyze(result, kind, manifest)

    def rollback(self, request):
        _fields(request, ("source_id", "manifest"))
        source = self.source(request["source_id"])
        kind = source["summary"]["kind"]
        function = fm1_rebuild.rollback_package if kind == "fwsc" else fm1_rebuild.rollback_application
        result, manifest = function(source["raw"], request["manifest"])
        return self.analyze(result, kind, manifest)

    def _project_path(self, project_id):
        target = self.project_dir / (_id(project_id) + ".fm1proj")
        # Reject a replaced symlink as well as all user-supplied filesystem paths.
        if target.is_symlink() or target.resolve().parent != self.project_dir:
            raise WorkspaceError("Project path is outside local project storage.")
        return target

    def _project(self, project_id):
        target = self._project_path(project_id)
        if not target.is_file():
            raise WorkspaceError("Local project was not found.")
        return FirmwareProject.open(target)

    def project_details(self, project_id, project=None):
        project = project or self._project(project_id)
        return {"id": project_id, "summary": project.summary(), "revisions": project.revisions(),
                "download_url": f"/api/artifact/project/{project_id}"}

    def projects(self):
        result = []
        if self.project_dir.exists():
            for path in sorted(self.project_dir.glob("*.fm1proj"))[:MAX_PROJECTS]:
                if not re.fullmatch(r"[0-9a-f]{32}", path.stem):
                    continue
                try:
                    result.append({"id": path.stem, "summary": self._project(path.stem).summary()})
                except (ValueError, OSError):
                    result.append({"id": path.stem, "error": "Project failed validation."})
        return {"projects": result}

    def _new_project_id(self):
        self.project_dir.mkdir(parents=True, exist_ok=True)
        if len(list(self.project_dir.glob("*.fm1proj"))) >= MAX_PROJECTS:
            raise WorkspaceError("Local project limit reached. Export and manage projects before adding more.")
        return uuid4().hex

    @staticmethod
    def _record(project, revision_id, source):
        summary = source["summary"]
        project.record_analysis(revision_id, {"source_sha256": summary["sha256"],
                                             "inspection": summary["inspection"], "analysis": summary["analysis"]})

    def create_project(self, request):
        _fields(request, ("source_id", "label"))
        source = self.source(request["source_id"])
        with self.lock:
            project_id = self._new_project_id()
            project = FirmwareProject.create(self._project_path(project_id), source["raw"],
                                             source["summary"]["kind"], request["label"])
            self._record(project, 1, source)
        return self.project_details(project_id, project)

    def import_project(self, raw):
        if not raw or len(raw) > MAX_IMPORT_BYTES:
            raise WorkspaceError("Project imports must contain 1 to 64 MiB.")
        with self.lock:
            project_id = self._new_project_id()
            path = self._project_path(project_id)
            with path.open("xb") as output:
                output.write(raw)
            try:
                project = FirmwareProject.open(path)
                # Firmware-size limits apply to all revisions, not just the selected one.
                if any(row["size"] > MAX_FILE_BYTES for row in project.revisions()):
                    raise WorkspaceError("A project revision exceeds the workbench's 8 MiB firmware limit.")
            except Exception:
                path.unlink(missing_ok=True)
                raise
        return self.project_details(project_id, project)

    def load_project(self, request):
        _fields(request, ("project_id", "revision_id"))
        if type(request["revision_id"]) is not int:
            raise WorkspaceError("Choose a numeric revision ID.")
        project = self._project(request["project_id"])
        result = self.analyze(project.read_revision(request["revision_id"]), project.summary()["kind"])
        result["project"] = self.project_details(request["project_id"], project)
        result["revision_id"] = request["revision_id"]
        revision = next(row for row in result["project"]["revisions"] if row["id"] == request["revision_id"])
        if revision["manifest"] is not None:
            result["manifest"] = revision["manifest"]
            result["manifest_download_url"] = f"/api/artifact/manifest/{result['source_id']}"
        return result

    def add_revision(self, request):
        _fields(request, ("project_id", "parent_id", "source_id", "manifest", "label"))
        if type(request["parent_id"]) is not int:
            raise WorkspaceError("Choose a numeric parent revision ID.")
        source = self.source(request["source_id"])
        project = self._project(request["project_id"])
        if project.summary()["kind"] != source["summary"]["kind"]:
            raise WorkspaceError("The firmware kind does not match this project.")
        revision_id = project.add_revision(source["raw"], request["manifest"], request["parent_id"], request["label"])
        self._record(project, revision_id, source)
        return {**self.project_details(request["project_id"], project), "revision_id": revision_id}

    def artifact(self, category, artifact_id):
        if category == "project":
            project = self._project(artifact_id)
            return project.snapshot_bytes(), "application/octet-stream", f"fm1-project-{artifact_id[:8]}.fm1proj"
        source = self.source(artifact_id)
        summary = source["summary"]
        if category == "source":
            suffix = "fwsc" if summary["kind"] == "fwsc" else "bin"
            return source["raw"], "application/octet-stream", f"fm1-{summary['sha256'][:12]}.{suffix}"
        if category == "manifest" and "manifest" in summary:
            return (json.dumps(summary["manifest"], indent=2).encode("utf-8"), "application/json",
                    f"fm1-changes-{summary['sha256'][:12]}.json")
        raise WorkspaceError("Artifact was not found.")
