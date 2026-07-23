// Precompute browser-ready data from the raw ODPT dumps in /data.
//
// Two fare dumps, ~67 MB of per-line station pairs between them: the Challenge
// 2026 release covers the six private operators, the public ODPT release covers
// the subways and monorails. Their operator sets are disjoint, so they concat.
// Stations that share a platform complex (station-groups.json) are collapsed
// into one logical node, which is what the UI treats as "a station". Fares are
// emitted per operator as a CSR adjacency in a binary blob so the app only
// fetches the network it needs.

import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(ROOT, 'data');
const OUT = join(ROOT, 'public', 'data');

// Only these operators have fare data; everything else in /data/polygons is omitted.
// `fallback` colors a line whose geojson feature carries no color of its own.
const OPERATORS = [
  { key: 'Tobu', ja: '東武鉄道', en: 'Tobu', fallback: '#1E90FF' },
  { key: 'Tokyu', ja: '東急電鉄', en: 'Tokyu', fallback: '#DA0442' },
  { key: 'Seibu', ja: '西武鉄道', en: 'Seibu', fallback: '#00CC00' },
  { key: 'Keikyu', ja: '京急電鉄', en: 'Keikyu', fallback: '#00BFFF' },
  { key: 'Keio', ja: '京王電鉄', en: 'Keio', fallback: '#DD0077' },
  { key: 'Sotetsu', ja: '相鉄', en: 'Sotetsu', fallback: '#0080C6' },
  { key: 'TokyoMetro', ja: '東京メトロ', en: 'Tokyo Metro', fallback: '#00A7DB' },
  { key: 'Toei', ja: '都営地下鉄', en: 'Toei Subway', fallback: '#009944' },
  { key: 'YokohamaMunicipal', ja: '横浜市営地下鉄', en: 'Yokohama Municipal', fallback: '#0070B9' },
  { key: 'MIR', ja: 'つくばエクスプレス', en: 'Tsukuba Express', fallback: '#0F55A0' },
  { key: 'TamaMonorail', ja: '多摩都市モノレール', en: 'Tama Monorail', fallback: '#E60012' },
  { key: 'Yurikamome', ja: 'ゆりかもめ', en: 'Yurikamome', fallback: '#0075C2' },
  { key: 'TWR', ja: 'りんかい線', en: 'Rinkai Line', fallback: '#00639C' },
];

// Keikyu (from 2023-10) and Seibu (from 2026-03) charge one flat child fare on IC at
// any distance. ODPT still derives their child fares as half the adult one, so the
// dumps carry a distance curve that no longer exists. Paper tickets keep the half fare.
const FLAT_CHILD_IC = { Keikyu: 75, Seibu: 50 };

const json = (p) => JSON.parse(readFileSync(p, 'utf8'));
const round5 = (n) => Math.round(n * 1e5) / 1e5;

const stations = json(join(SRC, 'stations.json'));
const groups = json(join(SRC, 'station-groups.json'));
const railwayLines = json(join(SRC, 'railway-lines.json'));
const fares = [
  ...json(join(SRC, 'RailwayFares.Challenge2026.slim.json')),
  ...json(join(SRC, 'RailwayFares.ODPT.slim.json')),
];

const opOrder = new Map(OPERATORS.map((o, i) => [o.key, i]));
// A station id is operator.line.station, so its first two segments name the railway line.
const lineOf = (id) => id.split('.').slice(0, 2).join('.');

const byId = new Map(stations.map((s) => [s.id, s]));

// A station in a group belongs to that interchange complex; otherwise it stands alone.
// Union-find rather than a flat group id, because two separate signals have to merge:
// station-groups.json, and Metro's own ¥0 fares below.
const parent = new Map();
const find = (id) => {
  let root = id;
  while (parent.get(root) !== undefined && parent.get(root) !== root) root = parent.get(root);
  while (parent.get(id) !== undefined && parent.get(id) !== id) {
    const next = parent.get(id);
    parent.set(id, root);
    id = next;
  }
  return root;
};
const union = (a, b) => {
  const [ra, rb] = [find(a), find(b)];
  if (ra === rb) return;
  // Lowest id wins so the key is stable regardless of input order.
  if (ra < rb) parent.set(rb, ra);
  else parent.set(ra, rb);
};
const seed = (id) => {
  if (!parent.has(id)) parent.set(id, id);
};

for (const group of groups) {
  for (const cluster of group) for (const id of cluster) seed(id);
  const flat = group.flat();
  for (let i = 1; i < flat.length; i++) union(flat[0], flat[i]);
}

// Tokyo Metro bills some out-of-station transfers as ¥0 to mean "one fare station"
// (Ginza/Ginza-itchome), and station-groups.json misses several of those. But those
// markers are pairwise permissions, not an equivalence: unioning all of them chains
// Otemachi to Yurakucho via Tokyo, and since a node quotes its cheapest origin that
// understates 10 of Otemachi's 139 fares (Shibuya ¥209 -> ¥178). So only merge a pair
// that is one station wearing two names -- one title a prefix of the other.
const sameStationTwoNames = (a, b) => {
  const na = byId.get(a)?.title.ja;
  const nb = byId.get(b)?.title.ja;
  return !!na && !!nb && (na.startsWith(nb) || nb.startsWith(na));
};

for (const rec of fares) {
  if (rec.ic !== 0 && rec.tk !== 0) continue;
  const a = rec.from;
  const b = rec.to;
  if (!sameStationTwoNames(a, b)) continue;
  seed(a);
  seed(b);
  union(a, b);
}

const nodeKey = (id) => (parent.has(id) ? `g${find(id)}` : `s${id}`);

// ---- logical stations -------------------------------------------------------

const members = new Map(); // nodeKey -> station ids that carry fares
for (const rec of fares) {
  for (const id of [rec.from, rec.to]) {
    const key = nodeKey(id);
    if (!members.has(key)) members.set(key, new Set());
    members.get(key).add(id);
  }
}

const nodeKeys = [...members.keys()].sort();
const indexOf = new Map(nodeKeys.map((k, i) => [k, i]));

const usedLines = new Set(); // railway ids referenced by at least one node
const nodes = nodeKeys.map((key) => {
  const ids = [...members.get(key)].sort();
  const rep = byId.get(ids[0]);
  const lng = ids.reduce((a, id) => a + byId.get(id).coord[0], 0) / ids.length;
  const lat = ids.reduce((a, id) => a + byId.get(id).coord[1], 0) / ids.length;

  // Railways serving this complex, sorted by operator order then name, so the
  // details popup lists them predictably.
  const lines = [...new Set(ids.map(lineOf))].sort((a, b) => {
    const d = opOrder.get(a.split('.')[0]) - opOrder.get(b.split('.')[0]);
    return d || a.localeCompare(b);
  });
  for (const id of lines) {
    if (!railwayLines[id]) throw new Error(`no name/color for railway ${id} in railway-lines.json`);
    usedLines.add(id);
  }

  // A complex can span differently-named stations (虎ノ門 / 虎ノ門ヒルズ). Fares are
  // keyed to the complex, so it stays one node, but the map needs each physical
  // station's own name and position to draw them all. Only emitted when the names
  // actually differ -- 98% of nodes are a single name and carry nothing extra.
  const byName = new Map();
  for (const id of ids) {
    const rec = byId.get(id);
    let m = byName.get(rec.title.ja);
    if (!m) byName.set(rec.title.ja, (m = { ja: rec.title.ja, en: rec.title.en, ids: [] }));
    m.ids.push(id);
  }

  const node = {
    ja: rep.title.ja,
    en: rep.title.en,
    coord: [round5(lng), round5(lat)],
    ops: [...new Set(ids.map((id) => id.split('.')[0]))].sort(),
    lines,
  };

  if (byName.size > 1) {
    node.members = [...byName.values()]
      .map((m) => ({
        ja: m.ja,
        en: m.en,
        coord: [
          round5(m.ids.reduce((a, id) => a + byId.get(id).coord[0], 0) / m.ids.length),
          round5(m.ids.reduce((a, id) => a + byId.get(id).coord[1], 0) / m.ids.length),
        ],
        lines: [...new Set(m.ids.map(lineOf))].sort((a, b) => {
          const d = opOrder.get(a.split('.')[0]) - opOrder.get(b.split('.')[0]);
          return d || a.localeCompare(b);
        }),
      }))
      // The node's own name first; the rest are the ones you have to walk to.
      .sort((a, b) => (a.ja === node.ja ? -1 : b.ja === node.ja ? 1 : a.ja.localeCompare(b.ja)));
  }

  return node;
});

// ---- fares: operator -> directed pair -> fares -------------------------------

const perOp = new Map(OPERATORS.map((o) => [o.key, new Map()]));
// The tariff each operator's records are drawn from (dct:issued), not the dump's own
// date. Several are years old, so the app shows it rather than implying fares are current.
const issuedOf = new Map();
let maxFare = 0;
for (const rec of fares) {
  const op = rec.op;
  const table = perOp.get(op);
  if (!table) continue;

  const issued = rec.iss;
  if (!issuedOf.has(op) || issuedOf.get(op) < issued) issuedOf.set(op, issued);

  // Tokyo Metro bills out-of-station transfers (Otemachi/Tokyo, Ginza/Ginza-itchome)
  // as ¥0 to mean "one fare station". Those are transfer markers, not fares.
  if (rec.ic === 0 || rec.tk === 0) continue;

  const a = indexOf.get(nodeKey(rec.from));
  const b = indexOf.get(nodeKey(rec.to));
  if (a === b) continue; // same complex, different platform

  // A complex can bill as several fare origins (Toei charges more from Shinjuku-nishiguchi
  // than from Shinjuku). The node is one station to the user, so quote the cheapest.
  const key = a * 100000 + b;
  const prev = table.get(key);
  if (prev && prev[0] <= rec.ic) continue;

  table.set(key, [rec.ic, rec.tk, FLAT_CHILD_IC[op] ?? rec.cic, rec.ctk]);
  maxFare = Math.max(maxFare, rec.tk, rec.ic);
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
  opMeta.push({
    key: op.key,
    ja: op.ja,
    en: op.en,
    issued: issuedOf.get(op.key),
    stations: nStations,
    entries: nEntries,
  });
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

// Only the railways actually referenced by a node, keyed by id for the popup to resolve.
const lineMeta = Object.fromEntries([...usedLines].sort().map((id) => [id, railwayLines[id]]));

// ---- ordered stops per line --------------------------------------------------

// Records for a given railway appear consecutively, in geographic order, in the
// source dump. That order is otherwise thrown away, so walk it once per line.
for (const railwayId of usedLines) {
  const stops = [];
  const names = {};
  let prevIdx;
  for (const rec of stations) {
    if (rec.railway !== railwayId) continue;
    const idx = indexOf.get(nodeKey(rec.id));
    if (idx === undefined) continue; // no fare records -> not a node
    if (idx !== prevIdx) stops.push(idx); // collapse consecutive dupes only (Oedo loops through 都庁前 twice)
    if (rec.title.ja !== nodes[idx].ja) names[String(idx)] = rec.title.ja;
    prevIdx = idx;
  }
  if (stops.length < 2) throw new Error(`railway ${railwayId} has fewer than 2 stops (${stops.length})`);
  lineMeta[railwayId].stops = stops;
  if (Object.keys(names).length) lineMeta[railwayId].names = names;
}

// ---- transfer discounts -------------------------------------------------------

const norm = (s) => s.normalize('NFKC');

// `operator` narrows the raw-station search to that operator's ids; omit it (as for
// `via`) to search across all operators.
function resolveStationName(name, operator, context) {
  const target = norm(name);
  for (const rec of stations) {
    if (operator && rec.id.split('.')[0] !== operator) continue;
    if (norm(rec.title.ja) === target) {
      const idx = indexOf.get(nodeKey(rec.id));
      if (idx !== undefined) return idx;
    }
  }
  throw new Error(`${context}: station "${name}"${operator ? ` (${operator})` : ''} did not resolve to a fare node`);
}

const discountsSrc = json(join(SRC, 'transfer-discounts.json'));

const discountsFlat = discountsSrc.flat.map((f) => ({ ops: f.operators, adult: f.adult, child: f.child }));

const discountsConditional = [];
for (const row of discountsSrc.conditional) {
  if ('_skip' in row) continue;
  const via = resolveStationName(row.via, undefined, `discount via "${row.via}"`);
  const aStations = [...new Set(
    row.a.stations.map((name) => resolveStationName(name, row.a.operator, `discount via "${row.via}" a:${row.a.operator}`)),
  )].sort((x, y) => x - y);
  const bStations = [...new Set(
    row.b.stations.map((name) => resolveStationName(name, row.b.operator, `discount via "${row.via}" b:${row.b.operator}`)),
  )].sort((x, y) => x - y);
  discountsConditional.push({
    via,
    a: { op: row.a.operator, stations: aStations },
    b: { op: row.b.operator, stations: bStations },
    adult: row.adult,
    child: row.child,
  });
}

writeFileSync(
  join(OUT, 'stations.json'),
  JSON.stringify({
    operators: opMeta,
    maxFare,
    lines: lineMeta,
    stations: nodes,
    discounts: { flat: discountsFlat, conditional: discountsConditional },
  }),
);

console.log(`  ${nodes.length} logical stations, ${features.length} lines, ${usedLines.size} named railways`);
