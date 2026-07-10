// Precompute browser-ready data from the raw ODPT dumps in /data.
//
// RailwayFares.json is 38 MB of per-line station pairs. Stations that share a
// platform complex (station-groups.json) are collapsed into one logical node,
// which is what the UI treats as "a station". Fares are emitted per operator as
// a CSR adjacency in a binary blob so the app only fetches the network it needs.

import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(ROOT, 'data');
const OUT = join(ROOT, 'public', 'data');

const STATION_PREFIX = 'odpt.Station:';
const OPERATOR_PREFIX = 'odpt.Operator:';

// Only these operators have fare data; everything else in /data/polygons is omitted.
const OPERATORS = [
  { key: 'Tobu', ja: '東武鉄道', en: 'Tobu', fallback: '#1E90FF' },
  { key: 'Tokyu', ja: '東急電鉄', en: 'Tokyu', fallback: '#DA0442' },
  { key: 'Seibu', ja: '西武鉄道', en: 'Seibu', fallback: '#00CC00' },
  { key: 'Keikyu', ja: '京急電鉄', en: 'Keikyu', fallback: '#00BFFF' },
  { key: 'Keio', ja: '京王電鉄', en: 'Keio', fallback: '#DD0077' },
  { key: 'Sotetsu', ja: '相鉄', en: 'Sotetsu', fallback: '#0080C6' },
];

const json = (p) => JSON.parse(readFileSync(p, 'utf8'));
const round5 = (n) => Math.round(n * 1e5) / 1e5;

const stations = json(join(SRC, 'stations.json'));
const groups = json(join(SRC, 'station-groups.json'));
const fares = json(join(SRC, 'RailwayFares.json'));

const byId = new Map(stations.map((s) => [s.id, s]));

// A station in a group belongs to that interchange complex; otherwise it stands alone.
const groupOf = new Map();
groups.forEach((group, gi) => {
  for (const cluster of group) for (const id of cluster) groupOf.set(id, gi);
});
const nodeKey = (id) => (groupOf.has(id) ? `g${groupOf.get(id)}` : `s${id}`);

// ---- logical stations -------------------------------------------------------

const members = new Map(); // nodeKey -> station ids that carry fares
for (const rec of fares) {
  for (const field of ['odpt:fromStation', 'odpt:toStation']) {
    const id = rec[field].slice(STATION_PREFIX.length);
    const key = nodeKey(id);
    if (!members.has(key)) members.set(key, new Set());
    members.get(key).add(id);
  }
}

const nodeKeys = [...members.keys()].sort();
const indexOf = new Map(nodeKeys.map((k, i) => [k, i]));

const nodes = nodeKeys.map((key) => {
  const ids = [...members.get(key)].sort();
  const rep = byId.get(ids[0]);
  const lng = ids.reduce((a, id) => a + byId.get(id).coord[0], 0) / ids.length;
  const lat = ids.reduce((a, id) => a + byId.get(id).coord[1], 0) / ids.length;
  return {
    ja: rep.title.ja,
    en: rep.title.en,
    coord: [round5(lng), round5(lat)],
    ops: [...new Set(ids.map((id) => id.split('.')[0]))].sort(),
  };
});

// ---- fares: operator -> directed pair -> fares -------------------------------

const perOp = new Map(OPERATORS.map((o) => [o.key, new Map()]));
let maxFare = 0;
for (const rec of fares) {
  const op = rec['odpt:operator'].slice(OPERATOR_PREFIX.length);
  const table = perOp.get(op);
  if (!table) continue;
  const a = indexOf.get(nodeKey(rec['odpt:fromStation'].slice(STATION_PREFIX.length)));
  const b = indexOf.get(nodeKey(rec['odpt:toStation'].slice(STATION_PREFIX.length)));
  if (a === b) continue; // same complex, different platform
  table.set(a * 100000 + b, [
    rec['odpt:icCardFare'],
    rec['odpt:ticketFare'],
    rec['odpt:childIcCardFare'],
    rec['odpt:childTicketFare'],
  ]);
  maxFare = Math.max(maxFare, rec['odpt:ticketFare'], rec['odpt:icCardFare']);
}
if (maxFare > 0xffff) throw new Error(`fare ${maxFare} overflows uint16`);

rmSync(OUT, { recursive: true, force: true });
mkdirSync(join(OUT, 'fares'), { recursive: true });

const opMeta = [];
for (const op of OPERATORS) {
  const table = perOp.get(op.key);
  if (!table.size) throw new Error(`no fares for ${op.key}`);

  const global = [...new Set([...table.keys()].flatMap((k) => [Math.floor(k / 100000), k % 100000]))].sort(
    (x, y) => x - y,
  );
  const local = new Map(global.map((g, i) => [g, i]));

  // group directed edges by local origin
  const rows = global.map(() => []);
  for (const [k, v] of table) {
    rows[local.get(Math.floor(k / 100000))].push([local.get(k % 100000), ...v]);
  }
  for (const r of rows) r.sort((x, y) => x[0] - y[0]);

  const nStations = global.length;
  const nEntries = rows.reduce((a, r) => a + r.length, 0);

  const headerBytes = 8;
  const offsetBytes = (nStations + 1) * 4;
  const buf = new ArrayBuffer(headerBytes + offsetBytes + nStations * 2 + nEntries * 10);

  new Uint32Array(buf, 0, 2).set([nStations, nEntries]);
  const offsets = new Uint32Array(buf, headerBytes, nStations + 1);
  const toGlobal = new Uint16Array(buf, headerBytes + offsetBytes, nStations);
  const base = headerBytes + offsetBytes + nStations * 2;
  const dest = new Uint16Array(buf, base, nEntries);
  const ic = new Uint16Array(buf, base + nEntries * 2, nEntries);
  const ticket = new Uint16Array(buf, base + nEntries * 4, nEntries);
  const childIc = new Uint16Array(buf, base + nEntries * 6, nEntries);
  const childTicket = new Uint16Array(buf, base + nEntries * 8, nEntries);

  toGlobal.set(global);
  let cursor = 0;
  for (let i = 0; i < nStations; i++) {
    offsets[i] = cursor;
    for (const [d, a, b, c, e] of rows[i]) {
      dest[cursor] = d;
      ic[cursor] = a;
      ticket[cursor] = b;
      childIc[cursor] = c;
      childTicket[cursor] = e;
      cursor++;
    }
  }
  offsets[nStations] = cursor;

  writeFileSync(join(OUT, 'fares', `${op.key}.bin`), Buffer.from(buf));
  opMeta.push({ key: op.key, ja: op.ja, en: op.en, stations: nStations, entries: nEntries });
  console.log(`  ${op.key.padEnd(8)} ${String(nStations).padStart(3)} stations  ${String(nEntries).padStart(5)} fares  ${(buf.byteLength / 1024).toFixed(1)} KB`);
}

// ---- line geometry ----------------------------------------------------------

const features = [];
for (const op of OPERATORS) {
  const fc = json(join(SRC, 'polygons', `${op.key}.geojson`));
  for (const f of fc.features) {
    const color = f.properties.color ? `#${f.properties.color}` : op.fallback;
    features.push({
      type: 'Feature',
      properties: { operator: op.key, name: f.properties.name, color },
      geometry: {
        type: f.geometry.type,
        coordinates: f.geometry.coordinates.map((part) => part.map(([x, y]) => [round5(x), round5(y)])),
      },
    });
  }
}
writeFileSync(join(OUT, 'lines.geojson'), JSON.stringify({ type: 'FeatureCollection', features }));

writeFileSync(
  join(OUT, 'stations.json'),
  JSON.stringify({ operators: opMeta, maxFare, stations: nodes }),
);

console.log(`  ${nodes.length} logical stations, ${features.length} lines`);
