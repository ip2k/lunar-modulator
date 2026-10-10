import { test } from 'node:test';
import assert from 'node:assert/strict';
import { connectOnReady, wakeWhenReady } from '../www/startup-ready.mjs';

const fixture = (state = 'running') => {
  const order = [];
  const ctx = { state, destination: 'destination' };
  const node = { port: {}, connect: (destination) => order.push(`connect:${destination}`) };
  let current = true;
  connectOnReady(node, ctx, 'analyser', () => current, (m, sender) => {
    assert.equal(sender, node); order.push(`message:${m.type}`);
  });
  return { ctx, order, send: (type) => node.port.onmessage({ data: { type } }),
    replace: () => { current = false; } };
};

test('initialization messages do not join the live graph before ready', () => {
  const f = fixture();
  assert.deepEqual(f.order, []);
  f.send('state');
  assert.deepEqual(f.order, ['message:state']);
  f.send('ready');
  assert.deepEqual(f.order, ['message:state', 'connect:destination', 'connect:analyser', 'message:ready']);
  f.send('ready'); f.send('screen');
  assert.deepEqual(f.order.slice(4), ['message:ready', 'message:screen']);
});

test('initialization errors reach the page without connecting outputs', () => {
  const f = fixture(); f.send('error');
  assert.deepEqual(f.order, ['message:error']);
});

test('queued ready and state from a replaced node are ignored', () => {
  const f = fixture(); f.replace(); f.send('ready'); f.send('state');
  assert.deepEqual(f.order, []);
});

test('closed context cannot reconnect, while a browser-held context can', () => {
  const closed = fixture('closed'); closed.send('ready');
  assert.deepEqual(closed.order, []);
  const held = fixture('suspended'); held.send('ready');
  assert.deepEqual(held.order, ['connect:destination', 'connect:analyser', 'message:ready']);
});


test('ready connects both outputs before waking and wakes only once', () => {
  const order = [];
  const ctx = { state: 'suspended', destination: 'destination', resume() {
    order.push('resume'); return Promise.resolve();
  } };
  const node = { port: {}, connect: (destination) => order.push(`connect:${destination}`) };
  let ready = false;
  connectOnReady(node, ctx, 'analyser', () => true, (m) => order.push(`message:${m.type}`),
    () => { ready = true; wakeWhenReady(ctx, ready); });
  wakeWhenReady(ctx, ready); // A tap while initialization is pending.
  assert.deepEqual(order, []);
  node.port.onmessage({ data: { type: 'ready' } });
  assert.deepEqual(order, ['connect:destination', 'connect:analyser', 'resume', 'message:ready']);
  node.port.onmessage({ data: { type: 'ready' } });
  assert.equal(order.filter((e) => e === 'resume').length, 1);
});

test('gesture wake only resumes initialized held contexts and handles rejection', async () => {
  let resumes = 0;
  const ctx = { state: 'suspended', resume() {
    resumes++; return Promise.reject(new Error('autoplay held'));
  } };
  wakeWhenReady(null, true); wakeWhenReady(ctx, false);
  assert.equal(resumes, 0);
  wakeWhenReady(ctx, true);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(resumes, 1);
  for (const state of ['running', 'closed']) {
    ctx.state = state; wakeWhenReady(ctx, true);
  }
  assert.equal(resumes, 1);
});

test('stale or closed ready cannot invoke the resume callback', () => {
  for (const current of [false, true]) {
    const ctx = { state: current ? 'closed' : 'suspended', destination: 'destination' };
    const node = { port: {}, connect() { assert.fail('must not connect'); } };
    connectOnReady(node, ctx, 'analyser', () => current,
      () => assert.fail('must not update state'), () => assert.fail('must not resume'));
    node.port.onmessage({ data: { type: 'ready' } });
  }
});
