// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createInstallerBuildClient } from '../www/installer-build-client.js';

const id = 'a'.repeat(32);
const sha = 'b'.repeat(64);
const request = {
  version: 1, engines: ['macro'], effects: [], midi: [], modulation: [],
  project_ids: ['event-horizon', 'afterglow-relay'], startup_index: 0,
};

function response(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

test('submits the ordered v1 request same-origin and polls a verified diagnostic summary', async () => {
  const calls = [];
  const states = [
    { id, status: 'queued', kind: 'private-diagnostic-build' },
    { id, status: 'running', kind: 'private-diagnostic-build' },
    { id, status: 'succeeded', kind: 'private-diagnostic-build', result: {
      status: 'linked-private-diagnostic', artifact_sha256: sha,
      artifact_bytes: 785312, installable: false, hardware_tested: false,
      app_budget_bytes: 868836, remaining_bytes: 83524,
    } },
  ];
  const client = createInstallerBuildClient({ origin: 'https://lunar.test', pollIntervalMs: 100, maxWaitMs: 5000,
    fetchImpl: async (url, options) => {
      calls.push({ url: String(url), options });
      if (options.method === 'POST') return response(202, {
        id, status: 'queued', status_url: `/api/v1/builds/${id}`,
      });
      return response(200, states.shift());
    },
  });
  const progress = [];
  const result = await client.build(request, { onProgress: (state) => progress.push(state) });
  assert.deepEqual(progress, ['queued', 'queued', 'running', 'succeeded']);
  assert.deepEqual(result, {
    status: 'succeeded', artifactSha256: sha, artifactBytes: 785312,
    appBudgetBytes: 868836, remainingBytes: 83524,
    installable: false, hardwareTested: false,
  });
  assert.equal(calls[0].url, 'https://lunar.test/api/v1/builds');
  assert.equal(calls[0].options.method, 'POST');
  assert.deepEqual(JSON.parse(calls[0].options.body), request);
  assert.equal(calls[0].options.headers.authorization, undefined);
  assert.ok(calls.slice(1).every((call) => call.url === `https://lunar.test/api/v1/builds/${id}`));
  assert.ok(calls.every((call) => call.options.cache === 'no-store'));
});

test('posts the explicit D7000 song-diagnostic request without changing its schema', async () => {
  const d7000Request = {
    ...request,
    engines: ['macro', 'shapes'],
    flash_layout: 'expanded-d7000',
    runtime_mode: 'song-diagnostic',
  };
  let posted;
  const client = createInstallerBuildClient({ origin: 'https://lunar.test', fetchImpl: async (_url, options) => {
    posted = JSON.parse(options.body);
    return response(422, { detail: 'expected diagnostic rejection' });
  } });
  await assert.rejects(client.build(d7000Request), /request was rejected/);
  assert.deepEqual(posted, d7000Request);
});

test('rejects remote status URLs and diagnostic overclaims', async (t) => {
  await t.test('remote status URL', async () => {
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', fetchImpl: async () => response(202, {
      id, status: 'queued', status_url: `https://attacker.test/api/v1/builds/${id}`,
    }) });
    await assert.rejects(client.build(request), /invalid status address/);
  });
  await t.test('installable success claim', async () => {
    let calls = 0;
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', pollIntervalMs: 100,
      fetchImpl: async () => ++calls === 1
        ? response(202, { id, status: 'queued', status_url: `/api/v1/builds/${id}` })
        : response(200, { id, status: 'succeeded', kind: 'private-diagnostic-build', result: {
          status: 'linked-private-diagnostic', artifact_sha256: sha,
          artifact_bytes: 100, installable: true, hardware_tested: false,
        } }),
    });
    await assert.rejects(client.build(request), /receipt checks/);
  });
  await t.test('bad artifact hash', async () => {
    let calls = 0;
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', pollIntervalMs: 100,
      fetchImpl: async () => ++calls === 1
        ? response(202, { id, status: 'queued', status_url: `/api/v1/builds/${id}` })
        : response(200, { id, status: 'succeeded', kind: 'private-diagnostic-build', result: {
          status: 'linked-private-diagnostic', artifact_sha256: 'not-a-digest',
          artifact_bytes: 100, installable: false, hardware_tested: false,
        } }),
    });
    await assert.rejects(client.build(request), /receipt checks/);
  });
});

test('handles rejection and cancellation without additional polling', async () => {
  let calls = 0;
  const rejected = createInstallerBuildClient({ origin: 'https://lunar.test', fetchImpl: async () => {
    calls += 1;
    return response(422, { detail: 'invalid build request' });
  } });
  await assert.rejects(rejected.build(request), /request was rejected/);
  assert.equal(calls, 1);

  calls = 0;
  const controller = new AbortController();
  const client = createInstallerBuildClient({ origin: 'https://lunar.test', pollIntervalMs: 100,
    fetchImpl: async () => {
      calls += 1;
      return response(202, { id, status: 'queued', status_url: `/api/v1/builds/${id}` });
    },
  });
  await assert.rejects(client.build(request, {
    signal: controller.signal,
    onProgress: (state) => { if (state === 'queued') controller.abort(); },
  }), /canceled/);
  assert.equal(calls, 1);
});

test('rejects missing or inconsistent application flash capacity', async () => {
  for (const capacity of [
    {},
    { app_budget_bytes: 99, remaining_bytes: -1 },
    { app_budget_bytes: 200, remaining_bytes: 101 },
    { app_budget_bytes: 200.5, remaining_bytes: 100.5 },
    { app_budget_bytes: Number.MAX_SAFE_INTEGER, remaining_bytes: Number.MAX_SAFE_INTEGER - 100 },
  ]) {
    let calls = 0;
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', pollIntervalMs: 100,
      fetchImpl: async () => ++calls === 1
        ? response(202, { id, status: 'queued', status_url: `/api/v1/builds/${id}` })
        : response(200, { id, status: 'succeeded', kind: 'private-diagnostic-build', result: {
          status: 'linked-private-diagnostic', artifact_sha256: sha,
          artifact_bytes: 100, installable: false, hardware_tested: false, ...capacity,
        } }),
    });
    await assert.rejects(client.build(request), /receipt checks/);
  }
});

test('bounds timing configuration and rejects invalid selected request', async () => {
  assert.throws(() => createInstallerBuildClient({ origin: 'https://lunar.test', pollIntervalMs: 1 }), /timing limits/);
  const client = createInstallerBuildClient({ origin: 'https://lunar.test', fetchImpl: async () => assert.fail('must not fetch') });
  await assert.rejects(client.build({ ...request, startup_index: 9 }), /request is invalid/);
  await assert.rejects(client.build({ ...request, engines: [] }), /request is invalid/);
  for (const invalid of [
    { ...request, flash_layout: 'expanded-d7000' },
    { ...request, flash_layout: 'expanded-d7000', runtime_mode: 'diagnostic' },
    { ...request, engines: ['macro'], flash_layout: 'expanded-d7000', runtime_mode: 'song-diagnostic' },
  ]) {
    await assert.rejects(client.build(invalid), /request is invalid/);
  }
  await assert.rejects(client.build([]), /request is invalid/);
  const largeSelection = Object.fromEntries(['engines', 'effects', 'midi', 'modulation']
    .map((key) => [key, Array.from({ length: 128 }, (_, index) => `${String(index).padStart(3, '0')}${'🎛'.repeat(62)}`)]));
  await assert.rejects(client.build({ ...request, ...largeSelection }), /too large/);
});

test('rejects chunked oversized responses and includes response reads in deadline', async (t) => {
  await t.test('oversized streamed body', async () => {
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', fetchImpl: async () =>
      new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(new Uint8Array(40000));
          controller.enqueue(new Uint8Array(30000));
          controller.close();
        },
      }), { status: 202, headers: { 'content-type': 'application/json' } }) });
    await assert.rejects(client.build(request), /oversized response/);
  });
  await t.test('oversized stream with a stalled cancel does not extend the deadline', async () => {
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', maxWaitMs: 1000,
      fetchImpl: async () => new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(new Uint8Array(65537));
        },
        cancel() { return new Promise(() => {}); },
      }), { status: 202, headers: { 'content-type': 'application/json' } }) });
    const started = Date.now();
    await assert.rejects(client.build(request), /oversized response/);
    assert.ok(Date.now() - started < 500, 'cleanup should not wait for the stream cancel promise');
  });
  await t.test('abort with a stalled cancel settles without awaiting cleanup', async () => {
    const controller = new AbortController();
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', maxWaitMs: 5000,
      fetchImpl: async () => new Response(new ReadableStream({ cancel() { return new Promise(() => {}); } }), {
        status: 202, headers: { 'content-type': 'application/json' },
      }) });
    const started = Date.now();
    const pending = client.build(request, { signal: controller.signal });
    setTimeout(() => controller.abort(), 20);
    await assert.rejects(pending, /canceled/);
    assert.ok(Date.now() - started < 500, 'abort should not wait for the stream cancel promise');
  });
  await t.test('abort settles when both the pending read and stream cancel never settle', async () => {
    const controller = new AbortController();
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', maxWaitMs: 5000,
      fetchImpl: async () => new Response(new ReadableStream({
        pull() { return new Promise(() => {}); },
        cancel() { return new Promise(() => {}); },
      }), { status: 202, headers: { 'content-type': 'application/json' } }) });
    const started = Date.now();
    const pending = client.build(request, { signal: controller.signal });
    setTimeout(() => controller.abort(), 20);
    await assert.rejects(pending, /canceled/);
    assert.ok(Date.now() - started < 500, 'abort must independently reject the in-flight read race');
  });
  await t.test('body read observes timeout', async () => {
    const client = createInstallerBuildClient({ origin: 'https://lunar.test', maxWaitMs: 1000,
      fetchImpl: async () => new Response(new ReadableStream({
        start() {},
        cancel() {},
      }), { status: 202, headers: { 'content-type': 'application/json' } }) });
    await assert.rejects(client.build(request), /timed out/);
  });
});


test('forwards only bounded unique SET identifiers in the optional request field', async () => {
  const setRequest = { ...request, set_ids: ['replacement-showcase-event-horizon-companion-set'] };
  let posted;
  const client = createInstallerBuildClient({ origin: 'https://lunar.test', pollIntervalMs: 100,
    fetchImpl: async (_url, options) => {
      posted = JSON.parse(options.body);
      return response(422, { detail: 'expected diagnostic rejection' });
    },
  });
  await assert.rejects(client.build(setRequest), /request was rejected/);
  assert.deepEqual(posted, setRequest);
  for (const setIds of [['x', 'x'], [''], [{}], Array.from({ length: 9 }, (_, i) => `set-${i}`)]) {
    await assert.rejects(client.build({ ...request, set_ids: setIds }), /request is invalid/);
  }
  await assert.rejects(client.build({ ...request, set_ids: ['set'], local_path: '/tmp/private' }), /request is invalid/);
});
