export const ACCENT = '#3182CE';

// Green (cheapest) through to red (dearest), across the fares actually on screen.
const HUE_MIN = 0;
const HUE_MAX = 145;

export function fareColor(fare, min, max) {
  if (max <= min) return `hsl(${HUE_MAX} 66% 43%)`;
  const t = Math.max(0, Math.min(1, (fare - min) / (max - min)));
  return `hsl(${(HUE_MAX - (HUE_MAX - HUE_MIN) * t).toFixed(0)} 66% 43%)`;
}

export function fareGradient(stops = 6) {
  const parts = [];
  for (let i = 0; i < stops; i++) {
    const t = i / (stops - 1);
    parts.push(`hsl(${(HUE_MAX - (HUE_MAX - HUE_MIN) * t).toFixed(0)} 66% 43%)`);
  }
  return `linear-gradient(90deg, ${parts.join(', ')})`;
}

export const yen = (n) => `¥${n}`;
