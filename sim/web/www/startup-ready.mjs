// Initialize while suspended, then join the live graph before waking it.
// MIT licence, like the rest of this repository.
export function wakeWhenReady(ctx, ready) {
  if (ready && ctx && ctx.state !== 'running' && ctx.state !== 'closed') {
    ctx.resume().catch(() => {});
  }
}

export function connectOnReady(node, ctx, analyser, isCurrent, onMessage, onReady = () => {}) {
  let connected = false;
  node.port.onmessage = ({ data }) => {
    // A ready already queued during power-off must not reconnect an old node
    // or update the replacement page state. Suspended contexts may connect;
    // the existing gesture handlers wake them when the browser permits it.
    if (!isCurrent() || ctx.state === 'closed') return;
    if (data.type === 'ready' && !connected) {
      connected = true;
      node.connect(ctx.destination);
      node.connect(analyser);
      onReady();
    }
    onMessage(data, node);
  };
}
