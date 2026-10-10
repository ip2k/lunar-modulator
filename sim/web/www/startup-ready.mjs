// Initialize before joining the live graph. The context still wakes in the
// owner's power-on gesture; waiting for ready does not suspend it.
// MIT licence, like the rest of this repository.
export function connectOnReady(node, ctx, analyser, isCurrent, onMessage) {
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
    }
    onMessage(data, node);
  };
}
