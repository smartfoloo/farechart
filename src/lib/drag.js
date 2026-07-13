// Vertical pointer drag for the bottom sheets. Pointer capture keeps the gesture
// on the handle even when the finger slides off it, and `touch-action: none` on
// the node stops the browser scrolling the page underneath mid-drag.
export function dragY(node, params) {
  let opts = params;
  let active = false;
  let startY = 0;
  let lastY = 0;
  let lastAt = 0;
  let velocity = 0; // px per ms, positive downwards

  function down(e) {
    if (e.button > 0) return;
    active = true;
    startY = lastY = e.clientY;
    lastAt = e.timeStamp;
    velocity = 0;
    node.setPointerCapture(e.pointerId);
    opts.onStart?.();
  }

  function move(e) {
    if (!active) return;
    const dt = e.timeStamp - lastAt;
    if (dt > 0) velocity = (e.clientY - lastY) / dt;
    lastY = e.clientY;
    lastAt = e.timeStamp;
    opts.onMove?.(e.clientY - startY);
  }

  function up(e) {
    if (!active) return;
    active = false;
    node.releasePointerCapture(e.pointerId);
    // A flick that ends after a pause is a drag, not a flick.
    if (e.timeStamp - lastAt > 80) velocity = 0;
    opts.onEnd?.(lastY - startY, velocity);
  }

  node.addEventListener('pointerdown', down);
  node.addEventListener('pointermove', move);
  node.addEventListener('pointerup', up);
  node.addEventListener('pointercancel', up);

  return {
    update: (next) => (opts = next),
    destroy() {
      node.removeEventListener('pointerdown', down);
      node.removeEventListener('pointermove', move);
      node.removeEventListener('pointerup', up);
      node.removeEventListener('pointercancel', up);
    },
  };
}
