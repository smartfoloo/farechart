// Single source of truth for the mobile breakpoint. The map needs it too (camera
// padding, control placement), so it can't live inside the panel's CSS alone.
const query = window.matchMedia('(max-width: 768px)');

let matches = $state(query.matches);
query.addEventListener('change', (e) => (matches = e.matches));

export const isMobile = {
  get current() {
    return matches;
  },
};

// The layout viewport doesn't move when a mobile keyboard opens — only the visual
// one shrinks. Anything pinned to the bottom has to follow that, or the keyboard
// covers it. innerHeight alone can't see any of this.
const vv = window.visualViewport;

// Below this, the inset is browser chrome or pinch-zoom drift, not a keyboard.
const KEYBOARD_MIN = 80;

let height = $state(vv?.height ?? window.innerHeight);
let keyboard = $state(0);

function sync() {
  if (!vv) {
    height = window.innerHeight;
    return;
  }
  height = vv.height;
  const covered = window.innerHeight - vv.height - vv.offsetTop;
  keyboard = covered > KEYBOARD_MIN ? Math.round(covered) : 0;
}

vv?.addEventListener('resize', sync);
vv?.addEventListener('scroll', sync);
window.addEventListener('resize', sync);

export const viewport = {
  get height() {
    return height;
  },
  get keyboard() {
    return keyboard;
  },
};
