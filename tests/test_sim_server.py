"""Exercise the actual loopback test server's file boundary (audit batch 5)."""

import shutil
import subprocess

import pytest

from tests.engine_helpers import ROOT


@pytest.mark.parametrize("prefix", ["/", "/preview/"])
def test_page_server_rejects_sibling_traversal_and_bad_urls(tmp_path, prefix):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    www = tmp_path / "lunar-www"
    private = tmp_path / "lunar-www-private"
    www.mkdir()
    private.mkdir()
    (www / "index.html").write_text("public index")
    (www / "asset.txt").write_text("public asset")
    (private / "secret.txt").write_text("outside secret")
    (www / "escape").symlink_to(private, target_is_directory=True)
    script = r"""
import assert from 'node:assert/strict';
import { get } from 'node:http';
import { pathToFileURL } from 'node:url';
const { serve } = await import(pathToFileURL(process.argv[1]));
const prefix = process.argv[3];
const { server } = await serve(process.argv[2], 0, { prefix });
const request = (path) => new Promise((resolve, reject) => {
  const req = get({ host: '127.0.0.1', port: server.address().port, path }, res => {
    let body = '';
    res.setEncoding('utf8');
    res.on('data', x => body += x);
    res.on('end', () => resolve({ status: res.statusCode, body }));
  });
  req.on('error', reject);
});
try {
  assert.deepEqual(await request(prefix), { status: 200, body: 'public index' });
  assert.deepEqual(await request(prefix + 'asset.txt'), { status: 200, body: 'public asset' });
  for (const path of ['..%2flunar-www-private/secret.txt', 'escape/secret.txt', 'missing.txt']) {
    const response = await request(prefix + path);
    assert.equal(response.status, 404, path);
    assert.equal(response.body, '', path);
  }
  assert.equal((await request(prefix + '%FF')).status, 400);
  // A malformed URL must not stop subsequent valid requests.
  assert.equal((await request(prefix + 'asset.txt')).status, 200);
} finally { await new Promise(resolve => server.close(resolve)); }
"""
    subprocess.run(
        [node, "--input-type=module", "-e", script,
         str(ROOT / "sim/web/test/serve.mjs"), str(www), prefix],
        check=True, capture_output=True, text=True, timeout=10,
    )
