"""Generate JR East pairwise fares in the compact format build-data.mjs consumes.

Distances come from the MARS538-derived graph (data/jr-east/jreast-graph.json).
It carries both 営業キロ (km) and 換算キロ (fkm) per edge, so routes touching a
地方交通線 are priced correctly rather than dropped.

Output shape: a node table plus one row per UNDIRECTED pair. The fare is
symmetric, `op`/`iss` are constant across every row, and both child fares are
exact functions of the adult ones, so none of that is stored. build-data.mjs
expands it back to directed per-ODPT-id records.

The data/jr-east/*.json inputs carry no provenance blocks -- they are data only.
Their sources, which none of them can be re-derived without:

  jreast-graph.json
      MARS for MS-DOS v5.38 (SWA / 葛西隆也), 2026-03-14 revision, decoded by
      build-graph-from-mars.py. Distances in tenths of a km. `zones` came from
      the external graph.json and are carried forward from the file's own
      previous run -- there is no other source, so never strip them.
  jreast-graph-idmap.json
      Same MARS decode; graph slug -> the ODPT ids of that station's complex.
  jreast-fare-tables.json
      Transcribed by hand from https://jr-group.jp/higashinihon-fare/ (幹線
      221km and above, plus the full 地方交通線 table), cross-checked against
      https://ja.wikipedia.org/wiki/電車特定区間 and
      https://jikokuhyo.train-times.net/news/jreast20260314 . Effective
      2026-03-14. from_km/to_km are inclusive whole 営業キロ. The 地方交通線
      bands are NOT uniform steps and carry an extra ¥1,980 band -- transcribed,
      never computed. An earlier version derived them from a rate formula and
      got both the boundaries and the amounts wrong above 10 km.
  jreast-special-section-fares.json
      special.json (external), JR East 2026-03-14 revision, via import-graph.py.

Child-fare rounding (JR floors the IC fare to ¥1 and the ticket fare to ¥10) is
applied in build-data.mjs, not here. Sources for that rule:
https://jreastfaq.jreast.co.jp/faq/show/1177 , https://jr-group.jp/child-fare/ .
"""
import json, heapq, math, os
from collections import defaultdict

REPO = '/Users/rios/farechart/'

graph = json.load(open(REPO + 'data/jr-east/jreast-graph.json'))
idmap = json.load(open(REPO + 'data/jr-east/jreast-graph-idmap.json'))['map']
special = json.load(open(REPO + 'data/jr-east/jreast-special-section-fares.json'))['fares']
tables = json.load(open(REPO + 'data/jr-east/jreast-fare-tables.json'))
stations = json.load(open(REPO + 'data/stations.json'))
groups = json.load(open(REPO + 'data/station-groups.json'))

# ---- exclude the 15 coord-less JR-East stations.json entries ----
# build-data.mjs averages member coordinates to place a node and crashes on a
# member with no `coord`. 7 of the 15 fall inside this graph; the other 8
# (Sendai, Nagano, Matsumoto, Kobuchizawa, Hakuba, Aizu-Wakamatsu, Kitakata,
# Haranomachi) are simply outside the 640-station MARS538 coverage already,
# so they never show up in idmap and need no special handling.
NO_COORD = {s['id'] for s in stations if 'coord' not in s}

odpt_to_graph = {}
for gid, v in idmap.items():
    for o in v['odpt']:
        odpt_to_graph[o] = gid

nocoord_graph_ids = {odpt_to_graph[o] for o in NO_COORD if o in odpt_to_graph}
print("no-coord graph nodes excluded: %s" % sorted(nocoord_graph_ids))

# station-groups.json encodes cross-operator complexes; confirm it agrees with
# the graph's own JR-East-internal merges (e.g. 浦和 already spans 4 lines in
# one graph node) so a separate union-find pass here would be redundant -- the
# graph's node identity already IS the logical-station identity for JR-East
# fare purposes.
mismatches = 0
for grp in groups:
    ids = [i for sub in grp for i in sub if i.startswith('JR-East')]
    gids = {odpt_to_graph.get(i) for i in ids} - {None}
    if len(gids) > 1:
        mismatches += 1
print("station-groups.json JR-East unions vs graph node identity: %d mismatch(es)" % mismatches)

NODES = set(graph['stations']) - nocoord_graph_ids

# ---- adjacency: km/fkm are already integers in tenths of a km ----
adj = defaultdict(dict)  # adj[a][b] = (km, fkm, chihou)
for e in graph['edges']:
    a, b = e['a'], e['b']
    if a not in NODES or b not in NODES: continue
    w = (e['km'], e['fkm'], e['chihou'])
    adj[a][b] = w
    adj[b][a] = w

nodes = sorted(NODES)
print("graph: %d nodes, %d edges" % (len(nodes), sum(len(v) for v in adj.values()) // 2))

# connectivity sanity check: excluding 大津港 is expected to sever anything
# further up the 常磐線, but every station further up (原ノ町, 仙台, ...) was
# already outside the 640-node graph, so nothing NEW should go unreachable.
_seen = {nodes[0]}; _q = [nodes[0]]
while _q:
    u = _q.pop()
    for v2 in adj[u]:
        if v2 not in _seen: _seen.add(v2); _q.append(v2)
_unreachable = NODES - _seen
print("connectivity: %d/%d nodes reachable from an arbitrary node; unreachable: %s"
      % (len(_seen), len(NODES), sorted(_unreachable) or "none"))

ids_of = {gid: sorted(idmap[gid]['odpt']) for gid in nodes}  # graphId -> ODPT ids

# ---- railway <2-stop check (build-data.mjs throws on this) ----
def rail_of(odpt_id): return '.'.join(odpt_id.split('.')[:2])
by_rail = defaultdict(set)
for s in stations:
    if not s['id'].startswith('JR-East'): continue
    gid = odpt_to_graph.get(s['id'])
    if gid in NODES: by_rail[rail_of(s['id'])].add(gid)
THIN_RAILWAYS = {r for r, v in by_rail.items() if len(v) < 2}
print("railways with <2 connected stops (their ids are stripped from output): %s"
      % (sorted(THIN_RAILWAYS) or "none"))
ZERO_RAILWAYS = sorted({rail_of(s['id']) for s in stations
                         if s['id'].startswith('JR-East')} - set(by_rail))
print("railways with 0 nodes in this graph (never referenced, nothing to strip): %s" % ZERO_RAILWAYS)

# Railways with no station inside the Suica 首都圏エリア. Their own stations are
# already dropped by the SUICA filter below, but 宝積寺, 木更津 and 渋川 sit on
# one of these AND on a line inside the area, so their outside-area platform id
# has to be stripped too -- it names a railway build-data.mjs no longer knows.
OUTSIDE_RAILWAYS = {'JR-East.Karasuyama', 'JR-East.Kururi', 'JR-East.Agatsuma'}

def strip_thin(ids):
    return [i for i in ids
            if rail_of(i) not in THIN_RAILWAYS and rail_of(i) not in OUTSIDE_RAILWAYS]

# ---- Dijkstra over either edge weight (km index 0, fkm index 1) ----
def dijkstra(src, weight_idx):
    dist = {src: 0}; prev = {}
    pq = [(0, src)]; done = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in done: continue
        done.add(u)
        for v2, w in adj[u].items():
            nd = d + w[weight_idx]
            if nd < dist.get(v2, 1 << 30):
                dist[v2] = nd; prev[v2] = u
                heapq.heappush(pq, (nd, v2))
    return dist, prev

def path_edges(prev, src, dest):
    """Edge list (km, fkm, chihou) from src to dest, reconstructed via prev."""
    out_edges = []
    node = dest
    while node != src:
        p = prev[node]
        out_edges.append(adj[p][node])
        node = p
    return out_edges

# ---- fare tables (whole-km bands; graph units are tenths, so /10 to compare) ----
KANSEN = tables['kansen']
CHIHOU = tables['chihou_kotsusen']

def band_lookup(table, km_whole):
    for b in table:
        if b['from_km'] <= km_whole <= b['to_km']: return b
    return None

def kansen_fare(km_tenths):
    k = math.ceil(km_tenths / 10)
    b = band_lookup(KANSEN, k)
    return (b['ic'], b['ticket']) if b else None

CHIHOU_IC_FALLBACK = {'count': 0}
def chihou_fare(km_tenths):
    k = math.ceil(km_tenths / 10)
    b = band_lookup(CHIHOU, k)
    if not b: return None
    # The 1-10km chihou_kotsusen bands carry no verified IC figure (ic: None);
    # falling back to the ticket amount is the closest available number, not
    # a confirmed published fare.
    if b['ic'] is None:
        CHIHOU_IC_FALLBACK['count'] += 1
        return (b['ticket'], b['ticket'])
    return (b['ic'], b['ticket'])

def price_path(edges):
    """Composition-dependent pricing (the real JR rule, not an approximation):
    a route entirely on 幹線 is priced on 営業キロ against the 幹線 table; entirely
    on 地方交通線, on 営業キロ against the 地方交通線 table; mixed, on 運賃計算キロ
    (幹線 区間の営業キロ + 地方交通線 区間の換算キロ, summed) against the 幹線 table --
    except that if the WHOLE journey is <=10km, it is priced on 営業キロ against
    the 地方交通線 table regardless of composition (this is the one case where a
    mixed route can be cheaper priced as if it were pure 地方交通線)."""
    total_km = sum(e[0] for e in edges)
    all_kansen = all(not e[2] for e in edges)
    all_chihou = all(e[2] for e in edges)
    if all_kansen:
        return kansen_fare(total_km), 'kansen'
    if all_chihou:
        return chihou_fare(total_km), 'chihou'
    if total_km <= 100:  # <=10.0km in tenths
        return chihou_fare(total_km), 'mixed-le10km'
    calc_km = sum(e[1] if e[2] else e[0] for e in edges)
    return kansen_fare(calc_km), 'mixed'

# ---- zone hubs: eligibility distance is plain 営業キロ shortest path ----
# The fare distance, once a zone override fires, is NOT this plain 営業キロ --
# 特定都区市内 only relocates which station the fare is computed FROM (the zone
# hub); it does not change HOW the fare from there is computed. So we also
# need km- and fkm-shortest paths (with parents, to reconstruct) from each hub,
# to re-price hub->destination with the same composition-aware price_path used
# for ordinary pairs. Eligibility thresholds stay on plain 営業キロ from the hub.
TOKYO = next(gid for gid, v in graph['stations'].items() if v['ja'] == '東京' and gid in NODES)
YOKO = next(gid for gid, v in graph['stations'].items() if v['ja'] == '横浜' and gid in NODES)
d_tokyo_km, prev_tokyo_km = dijkstra(TOKYO, 0)
d_tokyo_fkm, prev_tokyo_fkm = dijkstra(TOKYO, 1)
d_yoko_km, prev_yoko_km = dijkstra(YOKO, 0)
d_yoko_fkm, prev_yoko_fkm = dijkstra(YOKO, 1)

HUB_KM = {TOKYO: (d_tokyo_km, prev_tokyo_km), YOKO: (d_yoko_km, prev_yoko_km)}
HUB_FKM = {TOKYO: (d_tokyo_fkm, prev_tokyo_fkm), YOKO: (d_yoko_fkm, prev_yoko_fkm)}

YAMANOTE = {gid for gid, v in graph['stations'].items() if 'yamanote' in v.get('zones', []) and gid in NODES}
TOKUNAI = {gid for gid, v in graph['stations'].items() if 'tokunai' in v.get('zones', []) and gid in NODES}
YOKOHAMA = {gid for gid, v in graph['stations'].items() if 'yokohama' in v.get('zones', []) and gid in NODES}
print("zones: 山手線内=%d 都区内=%d 横浜市内=%d" % (len(YAMANOTE), len(TOKUNAI), len(YOKOHAMA)))

def zone_override(a, b):
    """特定都区市内: the origin sits in a zone, the destination is OUTSIDE that
    zone and beyond its distance threshold from the zone's hub station -> the
    fare is computed from the zone's hub station instead of the point-to-point
    route. Checked symmetrically since either side of a pair can be the zone
    member. Returns (hub, destination) so the caller re-prices hub->destination
    with the normal composition-aware rule, or (None, None) if no zone fires."""
    for x, y in ((a, b), (b, a)):
        if x in YAMANOTE and y not in YAMANOTE:
            dt = d_tokyo_km.get(y)
            if dt is not None and 1000 < dt <= 2000: return TOKYO, y, 'yamanote'
        if x in TOKUNAI and y not in TOKUNAI:
            dt = d_tokyo_km.get(y)
            if dt is not None and dt > 2000: return TOKYO, y, 'tokunai'
        if x in YOKOHAMA and y not in YOKOHAMA:
            dyk = d_yoko_km.get(y)
            if dyk is not None and dyk > 2000: return YOKO, y, 'yokohama'
    return None, None, None

# ---- special-section fares (特定区間運賃), already keyed by graphId ----
SPECIAL = {}
for f in special:
    a, b = f['a'], f['b']
    if a not in NODES or b not in NODES: continue
    SPECIAL[(a, b)] = (f['ic'], f['ticket'])
    SPECIAL[(b, a)] = (f['ic'], f['ticket'])

# ---- Suica 首都圏エリア: only these stations are priced ----
# Everything else stays in the graph as a routing waypoint (the 吾妻線 chain is
# the only place a shortest path actually needs one), but never gets a fare
# record, so build-data.mjs -- which derives its whole station list from the
# fare records -- drops it from the app.
SUICA = {gid for gid, v in graph['stations'].items() if v.get('suica')}
print("Suica 首都圏エリア: %d of %d graph nodes priced" % (len(SUICA & NODES), len(NODES)))

ISSUED = '2026-03-14'

# The complexes that actually get priced, in graph-node order. ids[0] is the
# canonical destination id; build-data.mjs uses every id as an origin (so each
# ODPT platform joins the logical node) but only ids[0] as a destination.
priced = []
for gid in nodes:
    if gid not in SUICA: continue
    ids = strip_thin(ids_of[gid])
    if ids: priced.append((gid, ids))
print("priced complexes: %d (%d ODPT ids)" % (len(priced), sum(len(i) for _, i in priced)))

pairs = []
stat_kansen = stat_chihou = stat_mixed = 0
stat_zone = {'yamanote': 0, 'tokunai': 0, 'yokohama': 0}
stat_special = 0
max_fare = 0

# i < j only: the fare is symmetric (same shortest paths, symmetric zone check,
# symmetric SPECIAL table), so half the matrix is enough and half the Dijkstras.
for i, (a, _) in enumerate(priced):
    dist_km, prev_km = dijkstra(a, 0)
    dist_fkm, prev_fkm = dijkstra(a, 1)
    for j in range(i + 1, len(priced)):
        b = priced[j][0]

        # Composition-dependent pricing: evaluate the plain-営業キロ-shortest
        # path AND the plain-換算キロ-shortest path, price each by its own
        # composition, and take the cheaper. Inside 東京近郊区間 the passenger
        # is always charged the cheapest available route, so this min is the
        # correct fare rule, not a heuristic shortcut.
        candidates = []
        if b in dist_km:
            edges = path_edges(prev_km, a, b)
            f, comp = price_path(edges)
            if f: candidates.append((f, comp))
        if b in dist_fkm:
            edges = path_edges(prev_fkm, a, b)
            f, comp = price_path(edges)
            if f: candidates.append((f, comp))
        if not candidates: continue
        (ic, tk), comp = min(candidates, key=lambda c: c[0][1])

        if comp == 'kansen': stat_kansen += 1
        elif comp == 'chihou': stat_chihou += 1
        else: stat_mixed += 1

        hub, y, which = zone_override(a, b)
        if hub is not None:
            dkm, pkm = HUB_KM[hub]
            dfkm, pfkm = HUB_FKM[hub]
            zone_candidates = []
            if y in dkm:
                edges = path_edges(pkm, hub, y)
                f, _ = price_path(edges)
                if f: zone_candidates.append(f)
            if y in dfkm:
                edges = path_edges(pfkm, hub, y)
                f, _ = price_path(edges)
                if f: zone_candidates.append(f)
            if zone_candidates:
                zic, ztk = min(zone_candidates, key=lambda c: c[1])
                if ztk < tk:
                    ic, tk = zic, ztk
                    stat_zone[which] += 1

        sp = SPECIAL.get((a, b))
        if sp:
            sic, stk = sp
            if sic < ic or stk < tk:
                stat_special += 1
            ic, tk = min(ic, sic), min(tk, stk)

        max_fare = max(max_fare, ic, tk)
        pairs.append([i, j, ic, tk])

print("undirected pairs: %d" % len(pairs))
print("pairs by composition: 幹線=%d 地方交通線=%d mixed=%d" % (stat_kansen, stat_chihou, stat_mixed))
print("pairs changed by zone override: %s" % stat_zone)
print("pairs changed by special-section fare: %d" % stat_special)
print("chihou_kotsusen band lookups that fell back to ic=ticket (unverified short bands): %d"
      % CHIHOU_IC_FALLBACK['count'])

assert max_fare <= 0xffff, "fare %d overflows uint16" % max_fare
print("max fare: %d (uint16 OK)" % max_fare)

SLIM_PATH = REPO + 'data/RailwayFares.JREast.slim.json'
# `cic`/`ctk` are absent by design: JR floors the child IC fare to ¥1 and the
# child ticket fare to ¥10, so both are exact functions of the adult fare and
# build-data.mjs recomputes them. Toei rounds its child ticket fare UP instead
# (see RailwayFares.ODPT.slim.json), which is why that derivation lives in the
# JR-East branch of the reader and is not a shared helper.
blob = {
    'op': 'JR-East',
    'iss': ISSUED,
    'nodes': [ids for _, ids in priced],
    'pairs': pairs,
}
with open(SLIM_PATH, 'w') as fh:
    json.dump(blob, fh, ensure_ascii=False, separators=(',', ':'))
# Read it straight back so a short or interleaved write is caught here rather
# than as a JSON syntax error inside `npm run data`.
with open(SLIM_PATH) as fh:
    assert len(json.load(fh)['pairs']) == len(pairs), 'slim.json did not round-trip'
print("size: %.2f MB" % (os.path.getsize(SLIM_PATH) / 1e6))

# ---- validation ----
index_of = {gid: i for i, (gid, _) in enumerate(priced)}
fare_of = {(p[0], p[1]): (p[2], p[3]) for p in pairs}

def fare_between(a_ja, b_ja):
    a = next(g for g, v in graph['stations'].items() if v['ja'] == a_ja and g in NODES)
    b = next(g for g, v in graph['stations'].items() if v['ja'] == b_ja and g in NODES)
    i, j = index_of.get(a), index_of.get(b)
    if i is None or j is None: return None
    return fare_of.get((i, j)) or fare_of.get((j, i))

checks = [
    ('東京', '大宮', 620, 616),
    ('東京', '横浜', 530, 528),
    ('東京', '高尾', 1040, 1034),
    ('東京', '熱海', 2090, None),
    ('新宿', '八王子', 620, 616),
    ('綾瀬', '北千住', 150, 146),
]
for a_ja, b_ja, tk, ic in checks:
    r = fare_between(a_ja, b_ja)
    print("%s-%s: tk=%s ic=%s (expect tk=%s ic=%s)" % (a_ja, b_ja, r and r[1], r and r[0], tk, ic))
    assert r is not None, "%s-%s: no record found" % (a_ja, b_ja)
    assert r[1] == tk, "%s-%s: tk %s != expected %s" % (a_ja, b_ja, r[1], tk)
    if ic is not None:
        assert r[0] == ic, "%s-%s: ic %s != expected %s" % (a_ja, b_ja, r[0], ic)

# 東京-大宮 distance assertion: 経路特定区間 needs no override pass because
# shortest-path selects the fare route (田端 routing) by itself.
omiya = next(g for g, v in graph['stations'].items() if v['ja'] == '大宮' and g in NODES)
best = min(dijkstra(TOKYO, 0)[0].get(omiya, 1 << 30), dijkstra(TOKYO, 1)[0].get(omiya, 1 << 30))
print("東京-大宮 shortest distance: %.1f km (expect 30.3, not 30.5)" % (best / 10))
assert best == 303, "東京-大宮 distance %.1f != 30.3" % (best / 10)

print("ALL CHECKS PASSED")
