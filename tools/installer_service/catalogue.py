# SPDX-License-Identifier: MIT
"""Load ID/kind membership from the trusted checked-out source tree."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def load_trusted_catalogue(root: Path = ROOT, *, include_sets=False):
    """Use fixed local Make/export metadata only; this does not compile firmware."""
    root = Path(root).resolve()
    for path in (root, root / "tools/native"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import tools.native.export_image_catalogue as export_catalogue
    import tools.native.module_selection as module_selection
    for module in (export_catalogue, module_selection):
        if Path(module.__file__).resolve() != root.joinpath(*module.__name__.split('.')).with_suffix('.py'):
            raise ValueError("catalogue import was not loaded from the pinned source")
    from tools.native.export_image_catalogue import PRELOAD_PROJECTS, PRELOAD_SETS
    from tools.native.module_selection import resolve_modules

    with tempfile.TemporaryDirectory(prefix="lunar-service-catalogue-") as scratch:
        _, report = resolve_modules(root, Path(scratch) / "all", "all")
    module_kinds = {
        row["id"]: row["kind"] for row in report["catalogue"]
        if not row["id"].startswith("test-")
    }
    project_ids = {row["id"] for row in PRELOAD_PROJECTS}
    if (not module_kinds or not project_ids or len(project_ids) > 11
            or len(project_ids) != len(PRELOAD_PROJECTS)):
        raise ValueError("trusted catalogue failed its expected bounds")
    if include_sets:
        return module_kinds, project_ids, {row['id']: row['parent_project_id'] for row in PRELOAD_SETS}
    return module_kinds, project_ids
