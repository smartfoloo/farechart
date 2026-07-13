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
