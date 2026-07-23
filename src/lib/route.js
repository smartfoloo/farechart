import { fareBetween } from './data.js';
import { fareOf } from './fare.js';

// A transfer between two different railways at the same station. Weight is
// deliberately much larger than a single ride hop (1) so the search prefers
// staying on one line/operator over hopping around for marginal savings.
export const TRANSFER = 8;

const operatorOf = (railway) => railway.split('.')[0];

// ---------------------------------------------------------------------------
// Graph: node = (stationIdx, railwayId). Built once per meta object.
// ---------------------------------------------------------------------------

const graphCache = new WeakMap();

function nodeKey(station, railway) {
  return `${station}|${railway}`;
}

function buildGraph(meta) {
  if (graphCache.has(meta)) return graphCache.get(meta);

  const nodes = new Map(); // key -> { station, railway }
  const adj = new Map(); // key -> [{ to, weight }]
  const byStation = new Map(); // stationIdx -> [key]

  function ensureNode(station, railway) {
    const key = nodeKey(station, railway);
    if (!nodes.has(key)) {
      nodes.set(key, { station, railway });
      adj.set(key, []);
      if (!byStation.has(station)) byStation.set(station, []);
      byStation.get(station).push(key);
    }
    return key;
  }

  function addEdge(a, b, weight) {
    adj.get(a).push({ to: b, weight });
  }

  for (const [railwayId, line] of Object.entries(meta.lines)) {
    const stops = line.stops;
    for (const s of stops) ensureNode(s, railwayId);
    for (let i = 0; i < stops.length - 1; i++) {
      const a = nodeKey(stops[i], railwayId);
      const b = nodeKey(stops[i + 1], railwayId);
      addEdge(a, b, 1);
      addEdge(b, a, 1);
    }
  }

  for (const keys of byStation.values()) {
    for (let i = 0; i < keys.length; i++) {
      for (let j = 0; j < keys.length; j++) {
        if (i === j) continue;
        if (nodes.get(keys[i]).railway === nodes.get(keys[j]).railway) continue;
        addEdge(keys[i], keys[j], TRANSFER);
      }
    }
  }

  const discounts = buildDiscountIndex(meta.discounts);

  const graph = { nodes, adj, byStation, discounts };
  graphCache.set(meta, graph);
  return graph;
}

// ---------------------------------------------------------------------------
// Dijkstra
// ---------------------------------------------------------------------------

class MinHeap {
  constructor() {
    this.a = [];
  }
  get size() {
    return this.a.length;
  }
  push(key, dist) {
    this.a.push({ key, dist });
    let i = this.a.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this.a[p].dist <= this.a[i].dist) break;
      [this.a[p], this.a[i]] = [this.a[i], this.a[p]];
      i = p;
    }
  }
  pop() {
    const top = this.a[0];
    const last = this.a.pop();
    if (this.a.length) {
      this.a[0] = last;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1;
        const r = 2 * i + 2;
        let smallest = i;
        if (l < this.a.length && this.a[l].dist < this.a[smallest].dist) smallest = l;
        if (r < this.a.length && this.a[r].dist < this.a[smallest].dist) smallest = r;
        if (smallest === i) break;
        [this.a[smallest], this.a[i]] = [this.a[i], this.a[smallest]];
        i = smallest;
      }
    }
    return top;
  }
}

function reconstructPath(destKey, prev, nodes) {
  const seq = [destKey];
  let cur = destKey;
  while (prev.has(cur)) {
    cur = prev.get(cur);
    seq.push(cur);
  }
  seq.reverse();
  return seq.map((k) => nodes.get(k));
}

/**
 * Dijkstra from every railway-node at `origin` station to any railway-node
 * at `dest` station. `operatorPrefix` (e.g. "TokyoMetro.") restricts the
 * search to railways of one operator. `bannedEdge` excludes a single
 * directed edge, keyed "aNodeKey>bNodeKey".
 */
function shortestPath(graph, origin, dest, { operatorPrefix, bannedEdge } = {}) {
  const { nodes, adj, byStation } = graph;
  const railwayOk = (r) => !operatorPrefix || r.startsWith(operatorPrefix);

  const startKeys = (byStation.get(origin) || []).filter((k) => railwayOk(nodes.get(k).railway));
  if (!startKeys.length) return null;
  const destKeys = new Set((byStation.get(dest) || []).filter((k) => railwayOk(nodes.get(k).railway)));
  if (!destKeys.size) return null;

  const dist = new Map();
  const prev = new Map();
  const visited = new Set();
  const heap = new MinHeap();

  for (const k of startKeys) {
    dist.set(k, 0);
    heap.push(k, 0);
  }

  while (heap.size > 0) {
    const { key, dist: d } = heap.pop();
    if (visited.has(key)) continue;
    if (d > (dist.get(key) ?? Infinity)) continue;
    visited.add(key);

    if (destKeys.has(key)) return reconstructPath(key, prev, nodes);

    for (const edge of adj.get(key)) {
      if (!railwayOk(nodes.get(edge.to).railway)) continue;
      if (bannedEdge && `${key}>${edge.to}` === bannedEdge) continue;
      const nd = d + edge.weight;
      if (nd < (dist.get(edge.to) ?? Infinity)) {
        dist.set(edge.to, nd);
        prev.set(edge.to, key);
        heap.push(edge.to, nd);
      }
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Path -> legs -> operatorLegs
// ---------------------------------------------------------------------------

function pathToLegs(path) {
  const legs = [];
  let current = null;
  for (const node of path) {
    if (!current || node.railway !== current.railway) {
      if (current) legs.push(current);
      current = { railway: node.railway, from: node.station, to: node.station, hops: 0 };
    } else {
      current.to = node.station;
      current.hops += 1;
    }
  }
  if (current) legs.push(current);
  return legs;
}

function nameOf(meta, railway, stationIdx) {
  const names = meta.lines[railway].names;
  const override = names && names[String(stationIdx)];
  return override ?? meta.stations[stationIdx].ja;
}

function attachNames(meta, legs) {
  return legs.map((l) => ({
    ...l,
    fromName: nameOf(meta, l.railway, l.from),
    toName: nameOf(meta, l.railway, l.to),
  }));
}

// Consecutive legs sharing an operator merge: within one operator a line
// change is free, since that operator's fare table already prices
// origin -> destination including in-operator transfers.
function buildOperatorLegs(legs) {
  const out = [];
  for (const leg of legs) {
    const op = operatorOf(leg.railway);
    const last = out[out.length - 1];
    if (last && last.operator === op) {
      last.to = leg.to;
    } else {
      out.push({ operator: op, from: leg.from, to: leg.to });
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Candidate generation
// ---------------------------------------------------------------------------

/**
 * Raw path candidates between two stations, no fares attached (fares need
 * networks loaded asynchronously). Returns at most ~10, deduped by railway
 * sequence.
 */
export function candidateRoutes(meta, origin, dest) {
  if (origin === dest) return [];
  const graph = buildGraph(meta);

  const rawPaths = [];

  const originOps = meta.stations[origin].ops;
  const destOps = meta.stations[dest].ops;
  const sharedOps = originOps.filter((op) => destOps.includes(op));

  for (const op of sharedOps) {
    const path = shortestPath(graph, origin, dest, { operatorPrefix: `${op}.` });
    if (path) rawPaths.push(path);
  }

  const best = shortestPath(graph, origin, dest);
  if (best) {
    rawPaths.push(best);
    for (let i = 0; i < best.length - 1; i++) {
      const bannedEdge = `${nodeKey(best[i].station, best[i].railway)}>${nodeKey(best[i + 1].station, best[i + 1].railway)}`;
      const alt = shortestPath(graph, origin, dest, { bannedEdge });
      if (alt) rawPaths.push(alt);
    }
  }

  const seen = new Set();
  const candidates = [];
  for (const path of rawPaths) {
    const legs = attachNames(meta, pathToLegs(path));
    const sig = legs.map((l) => `${l.railway}:${l.from}:${l.to}`).join('|');
    if (seen.has(sig)) continue;
    seen.add(sig);
    candidates.push({ legs, operatorLegs: buildOperatorLegs(legs) });
    if (candidates.length >= 10) break;
  }

  return candidates;
}

/** Every operator key any candidate touches — tells the caller what to load. */
export function operatorsFor(candidates) {
  const set = new Set();
  for (const c of candidates) {
    for (const leg of c.legs) set.add(operatorOf(leg.railway));
  }
  return set;
}

// ---------------------------------------------------------------------------
// Discounts
// ---------------------------------------------------------------------------

function buildDiscountIndex(discounts) {
  const conditional = (discounts?.conditional || []).map((row) => ({
    via: row.via,
    aOp: row.a.op,
    aStations: new Set(row.a.stations),
    bOp: row.b.op,
    bStations: new Set(row.b.stations),
    adult: row.adult,
    child: row.child,
  }));

  const flatExact = new Map(); // "OpA|OpB" (sorted) -> { adult, child }
  const flatWildcard = new Map(); // namedOp -> { adult, child }

  for (const row of discounts?.flat || []) {
    const [x, y] = row.ops;
    if (x === '*' || y === '*') {
      const named = x === '*' ? y : x;
      flatWildcard.set(named, { adult: row.adult, child: row.child });
    } else {
      flatExact.set([x, y].sort().join('|'), { adult: row.adult, child: row.child });
    }
  }

  return { conditional, flatExact, flatWildcard };
}

function matchConditional(row, opA, opB, via, endpointA, endpointB) {
  if (row.via !== via) return false;
  if (row.aOp === opA && row.bOp === opB) {
    return row.aStations.has(endpointA) && row.bStations.has(endpointB);
  }
  if (row.aOp === opB && row.bOp === opA) {
    return row.aStations.has(endpointB) && row.bStations.has(endpointA);
  }
  return false;
}

// Resolves the discount for one operator boundary, applying at most one rule
// (conditional > flat exact > flat wildcard).
function resolveDiscount(index, opA, opB, via, endpointA, endpointB, passenger) {
  for (const row of index.conditional) {
    if (matchConditional(row, opA, opB, via, endpointA, endpointB)) {
      return { amount: passenger === 'adult' ? row.adult : row.child, assumed: false };
    }
  }

  const exact = index.flatExact.get([opA, opB].sort().join('|'));
  if (exact) return { amount: passenger === 'adult' ? exact.adult : exact.child, assumed: false };

  const wa = index.flatWildcard.get(opA);
  if (wa) return { amount: passenger === 'adult' ? wa.adult : wa.child, assumed: true };

  const wb = index.flatWildcard.get(opB);
  if (wb) return { amount: passenger === 'adult' ? wb.adult : wb.child, assumed: true };

  return null;
}

// ---------------------------------------------------------------------------
// Pricing
// ---------------------------------------------------------------------------

/**
 * Prices each candidate against loaded fare networks. `nets` is
 * `{ [operatorKey]: network }`. Candidates whose operator legs aren't sold
 * by the loaded network for that pair are discarded.
 */
export function priceRoutes(meta, candidates, nets, fareMode, passenger) {
  const graph = buildGraph(meta);
  const discountIndex = graph.discounts;

  const priced = [];
  for (const c of candidates) {
    const { legs, operatorLegs } = c;

    let gross = 0;
    let ok = true;
    for (const oleg of operatorLegs) {
      const net = nets[oleg.operator];
      const entry = net ? fareBetween(net, oleg.from, oleg.to) : null;
      if (!entry) {
        ok = false;
        break;
      }
      gross += fareOf(entry, fareMode, passenger);
    }
    if (!ok) continue;

    let discount = 0;
    let discountAssumed = false;
    // A same-pair transfer discount (e.g. Toei<->Metro) isn't granted again
    // when you immediately re-cross back into a network you just left. For a
    // maximal run of consecutive boundaries sharing the same unordered
    // operator pair, only every other boundary within the run (index 0, 2, 4,
    // ...) actually applies the discount, giving ceil(k/2) for a run of
    // length k. A boundary whose pair differs from the previous one starts a
    // new run.
    let prevPairKey = null;
    let runIndex = 0;
    for (let i = 0; i < operatorLegs.length - 1; i++) {
      const a = operatorLegs[i];
      const b = operatorLegs[i + 1];
      const pairKey = [a.operator, b.operator].sort().join('|');
      if (pairKey === prevPairKey) {
        runIndex++;
      } else {
        runIndex = 0;
        prevPairKey = pairKey;
      }
      if (runIndex % 2 !== 0) continue;
      const res = resolveDiscount(discountIndex, a.operator, b.operator, a.to, a.from, b.to, passenger);
      if (res) {
        discount += res.amount;
        if (res.assumed) discountAssumed = true;
      }
    }

    const fare = Math.max(0, gross - discount);
    const transfers = legs.length - 1;
    const hops = legs.reduce((s, l) => s + l.hops, 0);
    const operators = [...new Set(legs.map((l) => operatorOf(l.railway)))];

    priced.push({ legs, operators, gross, discount, fare, transfers, hops, discountAssumed });
  }

  return priced;
}

// ---------------------------------------------------------------------------
// Ranking
// ---------------------------------------------------------------------------

// Route y dominates x if it's no worse on fare/transfers/hops and strictly
// better on at least one. Deliberately not a weighted score.
function dominates(y, x) {
  const noWorse = y.fare <= x.fare && y.transfers <= x.transfers && y.hops <= x.hops;
  const better = y.fare < x.fare || y.transfers < x.transfers || y.hops < x.hops;
  return noWorse && better;
}

/** Drops Pareto-dominated routes, sorts by fare/transfers/hops, keeps top 3. */
export function rankRoutes(routes) {
  const survivors = routes.filter((x) => !routes.some((y) => y !== x && dominates(y, x)));
  survivors.sort((a, b) => a.fare - b.fare || a.transfers - b.transfers || a.hops - b.hops);

  // Routes that tie on every axis and use the same operators differ only in which
  // parallel line they ride. Showing both spends two of three slots on one choice.
  const seen = new Set();
  return survivors
    .filter((r) => {
      const sig = `${r.fare}|${r.transfers}|${r.hops}|${r.operators.join(',')}`;
      return !seen.has(sig) && seen.add(sig);
    })
    .slice(0, 3);
}
