const BASE = import.meta.env.BASE_URL;

export async function loadMeta() {
  const res = await fetch(`${BASE}data/stations.json`);
  if (!res.ok) throw new Error(`stations.json: ${res.status}`);
  return res.json();
}

export async function loadLines() {
  const res = await fetch(`${BASE}data/lines.geojson`);
  if (!res.ok) throw new Error(`lines.geojson: ${res.status}`);
  return res.json();
}

const networks = new Map();

/** Fare table for one operator, fetched once and cached. */
export function loadNetwork(key) {
  if (!networks.has(key)) networks.set(key, fetchNetwork(key));
  return networks.get(key);
}

async function fetchNetwork(key) {
  const res = await fetch(`${BASE}data/fares/${key}.bin`);
  if (!res.ok) throw new Error(`fares/${key}.bin: ${res.status}`);
  const buf = await res.arrayBuffer();

  const [nStations, nEntries] = new Uint32Array(buf, 0, 2);
  const offsets = new Uint32Array(buf, 8, nStations + 1);
  const toGlobal = new Uint16Array(buf, 8 + (nStations + 1) * 4, nStations);
  const base = 8 + (nStations + 1) * 4 + nStations * 2;

  const localOf = new Map();
  for (let i = 0; i < nStations; i++) localOf.set(toGlobal[i], i);

  return {
    key,
    offsets,
    toGlobal,
    localOf,
    dest: new Uint16Array(buf, base, nEntries),
    ic: new Uint16Array(buf, base + nEntries * 2, nEntries),
    ticket: new Uint16Array(buf, base + nEntries * 4, nEntries),
    childIc: new Uint16Array(buf, base + nEntries * 6, nEntries),
    childTicket: new Uint16Array(buf, base + nEntries * 8, nEntries),
  };
}

const entryAt = (net, i) => ({
  station: net.toGlobal[net.dest[i]],
  ic: net.ic[i],
  ticket: net.ticket[i],
  childIc: net.childIc[i],
  childTicket: net.childTicket[i],
});

/** Every station reachable from `origin` on this operator, with its fares. */
export function destinationsFrom(net, origin) {
  const row = net.localOf.get(origin);
  if (row === undefined) return [];
  const out = [];
  for (let i = net.offsets[row]; i < net.offsets[row + 1]; i++) out.push(entryAt(net, i));
  return out;
}

/** Fares for one pair, or null if this operator doesn't serve it. */
export function fareBetween(net, origin, dest) {
  const row = net.localOf.get(origin);
  const target = net.localOf.get(dest);
  if (row === undefined || target === undefined) return null;

  let lo = net.offsets[row];
  let hi = net.offsets[row + 1] - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const d = net.dest[mid];
    if (d === target) return entryAt(net, mid);
    if (d < target) lo = mid + 1;
    else hi = mid - 1;
  }
  return null;
}
