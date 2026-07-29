export const ACCENT = '#3182CE';

// Green (cheapest) through to red (dearest), across the fares actually on screen.
const HUE_MIN = 0;
const HUE_MAX = 145;

// t runs 0 (cheapest) to 1 (dearest).
const ramp = (t) => `hsl(${(HUE_MAX - (HUE_MAX - HUE_MIN) * t).toFixed(0)} 66% 43%)`;

export function fareColor(fare, min, max) {
  if (max <= min) return ramp(0);
  return ramp(Math.max(0, Math.min(1, (fare - min) / (max - min))));
}

const GRADIENT_STOPS = 6;

export function fareGradient() {
  const parts = [];
  for (let i = 0; i < GRADIENT_STOPS; i++) parts.push(ramp(i / (GRADIENT_STOPS - 1)));
  return `linear-gradient(90deg, ${parts.join(', ')})`;
}

export const yen = (n) => `¥${n}`;

// Resolve a raw fare entry to a single number. Adult and child fares both ship
// in the ODPT data, so neither is derived.
export function fareOf(entry, mode, passenger) {
  if (passenger === 'child') return mode === 'ic' ? entry.childIc : entry.childTicket;
  return mode === 'ic' ? entry.ic : entry.ticket;
}
