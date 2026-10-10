import { test } from 'node:test';
import assert from 'node:assert/strict';
import { connectOnReady } from '../www/startup-ready.mjs';

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
