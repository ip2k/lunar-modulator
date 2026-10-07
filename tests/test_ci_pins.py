"""The CI's editor page-test job runs in the Playwright container, with the
npm packages, that sim/web/build-on-aeon.sh uses: the page tests mean the same
thing in both places only while the versions are the same one. This test holds
the two files to each other (and to the workflow's own pins)."""
import re

from tests.engine_helpers import ROOT

SCRIPT = (ROOT / "sim" / "web" / "build-on-aeon.sh").read_text()
WORKFLOW = (ROOT / ".github" / "workflows" / "ci.yml").read_text()


def _var(name):
    return re.search(r"^%s=(\S+)" % name, SCRIPT, re.M).group(1)


def test_the_ci_playwright_pins_are_build_on_aeon_sh_s():
    job = WORKFLOW[WORKFLOW.index("  editor-page-tests:"):]
    job = job[:job.index("\n  dongle-firmware:")]
    assert f"image: {_var('PLAYWRIGHT_IMAGE')}" in job
    assert _var("PLAYWRIGHT_NPM") in job and _var("AXE_NPM") in job
    # The container's image and the npm package are one version.
    image = re.search(r"playwright:v([0-9.]+)-", _var("PLAYWRIGHT_IMAGE")).group(1)
    assert _var("PLAYWRIGHT_NPM") == f"playwright@{image}"


def test_the_ci_job_runs_every_editor_page_test():
    """Every editor page test that needs no native build is run by the job."""
    job = WORKFLOW[WORKFLOW.index("  editor-page-tests:"):]
    for name in ("editor-unit", "editor-ui", "editor-reach", "editor-map", "editor-v1", "editor.mjs", "screenshot", "files"):
        assert name in job, name
    tests = {p.stem for p in (ROOT / "sim" / "web" / "test").glob("editor*.mjs")}
    # editor-shots makes the manual's pictures and is not a check.
    assert tests - {"editor-shots"} <= {"editor", "editor-unit", "editor-ui", "editor-reach", "editor-map", "editor-v1"}
    assert "chromium, firefox, webkit" in job
