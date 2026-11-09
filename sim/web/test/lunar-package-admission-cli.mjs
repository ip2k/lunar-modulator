// SPDX-License-Identifier: MIT
// Offline runner for tests/test_build_fwsc.py: verifies a package file with
// the browser admission module and prints the result as JSON. Reads files
// named on the command line only; sends nothing anywhere.
//   node lunar-package-admission-cli.mjs PACKAGE [--manifest FILE] [--profile FILE]
import { readFile } from 'node:fs/promises';
import { verifyNativePackage } from '../www/lunar-package-admission.js';

const args = process.argv.slice(2);
const option = (name) => {
  const at = args.indexOf(name);
  return at < 0 ? undefined : args[at + 1];
};
const packagePath = args[0];
const manifestPath = option('--manifest');
const profilePath = option('--profile');
try {
  const bytes = new Uint8Array(await readFile(packagePath));
  const options = {};
  if (manifestPath) options.manifest = await readFile(manifestPath, 'utf8');
  if (profilePath) options.profiles = [JSON.parse(await readFile(profilePath, 'utf8'))];
  const admitted = await verifyNativePackage(bytes, options);
  process.stdout.write(`${JSON.stringify({ admitted: true, kind: admitted.kind, product: admitted.product,
    logicalImageSha256: admitted.logicalImageSha256, manifest: admitted.manifest })}\n`);
} catch (error) {
  process.stdout.write(`${JSON.stringify({ admitted: false, reason: error.message })}\n`);
  process.exitCode = 1;
}
