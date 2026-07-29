"""Build a full-coverage JR East station-distance graph from decoded MARS for
MS-DOS v5.38 data, replacing the 495-station Suica-area-only jreast-graph.json
(which came from a different external source, graph.json) with a graph
covering the entire JR East network.

Background / inputs:
  - The MARS decode (scratchpad mars-findings.md, nn_decoded.tsv) gives, for
    every JR line code, an ordered list of stations with cumulative 営業キロ
    (`km`) and 換算キロ (`fare_km`, 0.0 when it equals 営業キロ i.e. on a
    幹線). nn_decoded.tsv covers ALL of JR (all 6 companies + some
    third-sector), keyed only by an opaque numeric line_code -- there is no
    reliable way to classify a line_code as "JR East" except by checking
    whether its stations' names match JR-East stations in data/stations.json.
  - Two line_codes (中央東, 鹿児島１) pack a branch spur into the same code
    with a large arbitrary km offset, so cumulative km resets partway through
    -- must be split into segments rather than walked naively.
  - Station names in MARS are sometimes prefixed with a disambiguating tag
    like "(中)大久保" or "(陽)大久保" when the same name exists elsewhere in
    the whole JR network. THE PREFIX IS MEANINGFUL AND MUST NOT BE STRIPPED
    BLINDLY. An earlier version of this script stripped the prefix and
    matched on the bare name, then used a "local corroboration" heuristic
    (trust a match only if another match sits within a few rows) to try to
    catch cross-company collisions after the fact. That heuristic missed a
    real one: (常)草野/(常)広野 on line 45 常磐 (JR East, km 220.6/238.2) and
    (福)草野/(福)広野 on line 138 福知山 (JR West, km 39.7/50.5) got merged
    into the same two nodes because line 138 happens to have enough OTHER
    coincidental JR-East name matches nearby to look "corroborated", producing
    a bogus 草野-広野 edge of 10.8km (= the JR West gap, 50.5-39.7) in place of
    the real 常磐線 value of 17.6km (草野-久ノ浜 9.2 + 久ノ浜-広野 8.4). Fixed
    by resolving these specific ambiguous names by PREFIX instead: see
    PREFIX_ACCEPT below, an explicit table of the 17 MARS names whose bare
    form collides with a station already in this graph, built by checking
    every prefixed occurrence's line_code against known JR East railways.
    Corroboration is kept only as a secondary net for names not on that list.
  - Long trunk lines (東海道, 東北) are stored as ONE MARS line_code spanning
    the whole physical route across company boundaries (Tokyo all the way to
    Kobe / Morioka), with only a prefix of their stations actually in JR
    East. A whole-segment "majority of names match JR-East" classifier was
    tried first and rejected these segments outright (their overall match
    ratio is ~0.2-0.4), which silently deleted real JR East stretches
    (Tokyo-Yokohama-Atami, Tokyo-Omiya-Utsunomiya-Kuroiso). The fix, and what
    the task actually specified: keep every individually name-matched row
    with no segment-level gate at all, and let the final "connected component
    containing 東京" filter discard anything that isn't really reachable.
  - Shinkansen line codes (84 新幹線 [Tokaido+Sanyo], 35 東北新幹線,
    4 北陸新幹線, 50 上越新幹線) are EXCLUDED entirely. Ordinary JR fares in
    this app are priced on 在来線 (conventional line) distance, and a
    Shinkansen station is often a genuinely different physical station from
    its parallel 在来線 counterpart at a different point along the route
    (e.g. 新横浜 sits at km 28.8 on the Tokaido Shinkansen's own axis but
    km 6.1 on the 横浜線's), so merging them by name creates real shortcuts:
    品川-新横浜 came out 22.0km (real 在来線 distance 26.3) and
    新横浜-小田原 came out 55.1km (real 63.0) before this exclusion.
    Shinkansen-only stations with no 在来線 station of the same name
    (上毛高原, 安中榛名, 本庄早稲田, ...) become unreachable as a result --
    that is expected and reported, not a bug.

Run: python3 scripts/jr-east/build-graph-from-mars.py
"""
import json
import re
import unicodedata
from collections import defaultdict, deque

REPO = '/Users/rios/farechart/'
SCRATCH = ('/private/tmp/claude-501/-Users-rios-farechart/'
           'c7659244-04d0-4433-8981-87c32fb2fe7f/scratchpad/')
NN_TSV = SCRATCH + 'nn_decoded.tsv'

STATIONS_PATH = REPO + 'data/stations.json'
GROUPS_PATH = REPO + 'data/station-groups.json'
OLD_GRAPH_PATH = REPO + 'data/jr-east/jreast-graph.json'
OLD_IDMAP_PATH = REPO + 'data/jr-east/jreast-graph-idmap.json'
OUT_GRAPH_PATH = REPO + 'data/jr-east/jreast-graph.json'
OUT_IDMAP_PATH = REPO + 'data/jr-east/jreast-graph-idmap.json'

TOKYO_ROOT_NAME = '東京'

# Railways with no station inside the Suica 首都圏エリア, per JR East's
# published route map (2026-03-14 現在). 烏山線 and 久留里線 are drawn only as
# a stub off 宝積寺 / 木更津; 吾妻線 is drawn dashed off 渋川 with 中之条,
# 長野原草津口 and 万座・鹿沢口 marked ◆ Suica一部対応駅, which this repo does
# not count as being in the area.
OUTSIDE_RAILWAYS = {
    'JR-East.Karasuyama',
    'JR-East.Kururi',
    'JR-East.Agatsuma',
}

PREFIX_RE = re.compile(r'^[\(（]([^\)）]{1,6})[\)）]')

# Shinkansen line codes: excluded entirely (see module docstring, BUG 2).
EXCLUDED_LINE_CODES = {
    84: '新幹線 (Tokaido/Sanyo Shinkansen)',
    35: '東北新幹線',
    4: '北陸新幹線',
    50: '上越新幹線',
}

# Every MARS name whose bare (prefix-stripped) form collides with a station
# name already in this JR-East graph, and the ONE prefix that actually
# resolves to that JR-East station. Any OTHER prefix on that same bare name
# is a different, non-JR-East (or JR-East-but-untracked-in-stations.json)
# physical station and must never be matched. Built by cross-referencing
# every occurrence of these 17 names in nn_decoded.tsv against MARS line_code
# and data/stations.json (none of the 17 ever appears without a prefix in the
# source data -- checked explicitly). A couple of names (大久保, 根岸) have a
# SECOND genuine JR-East station behind a different prefix, but stations.json
# has only one ODPT id for that name, so the second one has no id to attach
# to and is reported as "untracked", not merged into the wrong node.
PREFIX_ACCEPT = {
    '三郷':   '武蔵',  # (武蔵)三郷 line 79 武蔵野線 km 53.4 (JR East, between
                       # 新三郷 51.3 and 南流山 55.4) vs (関)三郷 関西線
                       # (JR West/Central). An earlier version of this table
                       # said "MARS has no JR-East 三郷 row" and rejected all
                       # occurrences -- wrong: it does exist, this script's
                       # regex just hadn't been checked against every 三郷
                       # occurrence in the file, only the one on line 114.
    '神代':   '田沢',  # (田沢)神代 田沢湖線 vs (陽)神代 山陽本線 (JR West).
                       # 田沢湖線 isn't in this repo's stations.json (no
                       # "Tazawako" railway id), so this is currently a no-op
                       # -- kept for correctness/documentation in case that
                       # coverage is ever extended.
    '高瀬':   '仙山',  # (仙山)高瀬 仙山線 vs (讃)高瀬 予讃線 (JR Shikoku).
                       # 仙山線 isn't in stations.json either -- same no-op
                       # caveat as 神代.
    '瀬田':   None,    # (東)瀬田 東海道本線 (Shiga, JR Central/West, not JR
                       # East despite the "東" tag) vs (豊肥)瀬田 豊肥本線
                       # (JR Kyushu) -- neither is JR East; always reject.
    '仁井田': '烏',    # 烏山線 (JR East) vs (土)仁井田 土讃線 (JR Shikoku)
    '千歳':   '房',    # 内房線 (JR East) vs (千)千歳 JR Hokkaido
    '大久保': '中',    # 中央東 (JR East, ChuoSobuLocal.Okubo) --
                       # (奥)大久保 is a real JR East Ou-line station but has
                       # no id in stations.json (untracked); (陽)大久保 is
                       # JR West San'yo line.
    '富浦':   '房',    # 内房線 (JR East) vs (室)富浦 JR Hokkaido Muroran line
    '富田':   '両',    # 両毛線 (JR East) vs (関)富田 関西線 (JR West/Central)
    '小林':   '成',    # 成田２ = Narita Abiko branch (JR East) vs
                       # (吉)小林 吉都線 (JR Kyushu)
    '広野':   '常',    # 常磐線 (JR East) vs (福)広野 福知山線 (JR West) --
                       # the concrete bug the coordinator found.
    '戸田':   '北',    # 埼京線 (JR East) vs (陽)戸田 San'yo line (JR West)
    '日進':   '川',    # 川越線 (JR East) vs (宗)日進 宗谷線 (JR Hokkaido)
    '旭':     '総',    # 総武線 (JR East) vs (土)旭 土讃線 (JR Shikoku)
    '根岸':   '岸',    # 根岸線 (JR East, KeihinTohokuNegishi.Negishi) --
                       # (只)根岸 is a real JR East 只見線 station but has no
                       # id in stations.json (untracked).
    '横川':   '信',    # 信越線 (JR East, Yokokawa) vs (陽)横川 San'yo /
                       # 可部線 (both JR West)
    '橋本':   '横',    # both 横浜線 and 相模線 occurrences use prefix 横 and
                       # resolve to the same real JR-East junction station
                       # (already a single union-find root) vs (和)橋本
                       # 和歌山線 (JR West)
    '滝':     '烏',    # 烏山線 (JR East) vs (加)滝 加古川線 (JR West)
    '草野':   '常',    # 常磐線 (JR East) vs (福)草野 福知山線 (JR West)
    '野崎':   '北',    # 東北線 (JR East) vs (片)野崎 片町線 (JR West/Central)
}

# Secondary safety net for names NOT in PREFIX_ACCEPT: a matched row is
# trusted only if another matched row exists within this many rows. Real
# JR-East stretches -- even inside a trunk line shared with another company,
# e.g. 東海道/東北 -- show up as long contiguous runs, so this always keeps
# them; a handful of isolated single-name collisions elsewhere in the whole
# JR network get dropped.
CORROBORATION_WINDOW = 3

# Names exempt from the corroboration net. It assumes a real JR-East stretch
# shows up as a contiguous run of matched rows, which breaks where the Suica
# 首都圏エリア itself is discontinuous: on 大糸線 the area covers 松本-穂高 and
# then jumps to 信濃大町 (8 rows later) and 白馬 (9 rows after that), so both
# sit alone in their window and were silently dropped. Neither name is
# ambiguous -- each occurs exactly once in the whole MARS file, on line 108
# 大糸 -- so there is nothing for corroboration to protect against.
TRUST_UNCORROBORATED = {'信濃大町', '白馬'}

# MARS truncates some names to fit its fixed-width record; this alias table
# maps the abbreviated MARS spelling (after NFKC normalisation) to the real
# station name so it can still be matched against stations.json. Found:
# line 58 両毛線 km 52.4 stores あしかがフラワーパーク (a request stop between
# 足利 46.2 and (両)富田 53.3, confirming the identity) as "あしかがﾌﾗﾜｰP" --
# half-width katakana plus a literal "P" standing in for パーク. NFKC folds
# the half-width kana to full-width but leaves the "P" alone, giving
# "あしかがフラワーP", not the real name -- hence the explicit alias.
MARS_NAME_ALIAS = {
    'あしかがフラワーP': 'あしかがフラワーパーク',
}


def norm(s):
    s = unicodedata.normalize('NFKC', s)
    return s.replace('ヶ', 'ケ')


def strip_prefix(name):
    return PREFIX_RE.sub('', name)


def slugify(en):
    return re.sub(r'[^a-z0-9]', '', en.lower())


def camel_first_word(seg):
    # "SaikyoKawagoe" -> "Saikyo", "ChuoSobuLocal" -> "Chuo"
    m = re.match(r'[A-Z][a-z0-9]*', seg)
    return m.group(0).lower() if m else seg.lower()


def main():
    stations = json.load(open(STATIONS_PATH))
    groups = json.load(open(GROUPS_PATH))
    old_graph = json.load(open(OLD_GRAPH_PATH))
    old_idmap = json.load(open(OLD_IDMAP_PATH))

    id_by_id = {s['id']: s for s in stations}
    jr = [s for s in stations if s['id'].startswith('JR-East')]

    # ---- union-find, replicated from jreast-gen-fares.py / build-idmap.py ----
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[min(ra, rb)] = parent[max(ra, rb)] = min(ra, rb)

    for g in groups:
        ids = [i for sub in g for i in sub if i.startswith('JR-East')]
        for i in ids[1:]:
            union(ids[0], i)

    name_to_ids = defaultdict(list)
    for s in jr:
        name_to_ids[norm(s['title']['ja'])].append(s['id'])

    root_to_ids = defaultdict(list)
    for s in jr:
        root_to_ids[find(s['id'])].append(s['id'])

    for name, ids in name_to_ids.items():
        roots = {find(i) for i in ids}
        if len(roots) > 1:
            raise SystemExit(f'name {name!r} spans multiple complexes: {roots}')

    name_to_root = {name: find(ids[0]) for name, ids in name_to_ids.items()}

    def canonical_id(root):
        return sorted(root_to_ids[root])[0]

    # ---- load MARS rows ----
    rows = []
    with open(NN_TSV, encoding='utf-8') as f:
        header = f.readline()
        for line in f:
            parts = line.rstrip('\n').split('\t')
            nn_row, line_code, line_name, km, fare_km, sd_idx, sd_row, name = parts
            rows.append({
                'nn_row': int(nn_row),
                'line_code': int(line_code),
                'line_name': line_name,
                'km': float(km),
                'fare_km': float(fare_km),
                'name': name,
            })
    rows = [r for r in rows if r['nn_row'] != 0]  # drop sentinel

    excluded_rows = [r for r in rows if r['line_code'] in EXCLUDED_LINE_CODES]
    rows = [r for r in rows if r['line_code'] not in EXCLUDED_LINE_CODES]

    by_line = defaultdict(list)
    for r in rows:
        by_line[r['line_code']].append(r)
    for v in by_line.values():
        v.sort(key=lambda r: r['nn_row'])

    # ---- split into segments on km decrease (branch-restart quirk) ----
    segments = []  # list of dict(line_code, line_name, rows)
    restart_report = []
    for line_code, line_rows in by_line.items():
        cur = [line_rows[0]]
        for prev, r in zip(line_rows, line_rows[1:]):
            if r['km'] < prev['km']:
                segments.append({'line_code': line_code,
                                  'line_name': line_rows[0]['line_name'],
                                  'rows': cur})
                restart_report.append({
                    'line_code': line_code, 'line_name': line_rows[0]['line_name'],
                    'at_row': r['nn_row'], 'from_km': prev['km'], 'to_km': r['km'],
                    'from_station': prev['name'], 'to_station': r['name'],
                })
                cur = [r]
            else:
                cur.append(r)
        segments.append({'line_code': line_code,
                          'line_name': line_rows[0]['line_name'],
                          'rows': cur})

    # ---- resolve each row to a JR-East root (or None), prefix-aware ----
    def effective(r):
        return r['fare_km'] if r['fare_km'] != 0.0 else r['km']

    def resolve(r):
        """Return (root_or_None, reason) for a single MARS row."""
        m = PREFIX_RE.match(r['name'])
        if not m:
            base = norm(r['name'])
            base = MARS_NAME_ALIAS.get(base, base)
            root = name_to_root.get(base)
            return (root, 'unprefixed-match' if root else 'unprefixed-nomatch')
        prefix, base = m.group(1), norm(PREFIX_RE.sub('', r['name']))
        base = MARS_NAME_ALIAS.get(base, base)
        if base in PREFIX_ACCEPT:
            accept_prefix = PREFIX_ACCEPT[base]
            if accept_prefix is not None and prefix == accept_prefix:
                return (name_to_root.get(base), 'prefix-accept')
            return (None, 'prefix-reject')
        root = name_to_root.get(base)
        return (root, 'prefixed-match' if root else 'prefixed-nomatch')

    prefix_rejected = []   # rows whose base name is ambiguous and this prefix lost
    isolated_dropped = []  # rows dropped by the secondary corroboration net

    edges = {}   # (min_root, max_root) -> dict(km, fkm, chihou, line)
    conflicts = []
    jr_segments = 0
    total_segments = len(segments)

    for seg in segments:
        matched = []
        for r in seg['rows']:
            root, reason = resolve(r)
            matched.append(root)
            if reason == 'prefix-reject':
                prefix_rejected.append({
                    'line_code': seg['line_code'], 'line_name': seg['line_name'],
                    'row': r['nn_row'], 'name': r['name'],
                })

        # Secondary net: for names NOT in PREFIX_ACCEPT (i.e. matched via the
        # generic unprefixed/prefixed-match path), still require corroboration.
        corroborated = []
        for i, root in enumerate(matched):
            if root is None:
                corroborated.append(None)
                continue
            base = norm(PREFIX_RE.sub('', seg['rows'][i]['name']))
            if base in PREFIX_ACCEPT or base in TRUST_UNCORROBORATED:
                # resolved by explicit prefix rule -- trust it outright.
                corroborated.append(root)
                continue
            lo = max(0, i - CORROBORATION_WINDOW)
            hi = min(len(matched), i + CORROBORATION_WINDOW + 1)
            has_neighbor = any(matched[j] is not None for j in range(lo, hi) if j != i)
            if has_neighbor:
                corroborated.append(root)
            else:
                corroborated.append(None)
                isolated_dropped.append({
                    'line_code': seg['line_code'], 'line_name': seg['line_name'],
                    'row': seg['rows'][i]['nn_row'], 'name': seg['rows'][i]['name'],
                })
        matched = corroborated

        n_matched = sum(1 for x in matched if x is not None)
        if n_matched == 0:
            continue
        jr_segments += 1
        kept = [(root, r) for root, r in zip(matched, seg['rows']) if root is not None]
        for (root_a, ra), (root_b, rb) in zip(kept, kept[1:]):
            if root_a == root_b:
                continue
            km = round((rb['km'] - ra['km']) * 10)
            fkm = round((effective(rb) - effective(ra)) * 10)
            # chihou is derived per edge (fkm != km for this specific hop),
            # not per line/segment: a segment-level "any row in this line has
            # fare_km != km" flag was tried first and produced false positives
            # on lines whose fare_km surcharge lives entirely outside the JR
            # East portion of the same MARS line code.
            chihou = fkm != km
            if km < 0 or fkm < 0:
                # shouldn't happen: segments are monotonic by construction
                conflicts.append(('negative-diff', seg['line_code'], root_a, root_b, km, fkm))
                continue
            key = (root_a, root_b) if root_a < root_b else (root_b, root_a)
            if key in edges:
                if edges[key]['km'] != km or edges[key]['fkm'] != fkm:
                    conflicts.append(('distance-mismatch', key, edges[key], (km, fkm, seg['line_code'])))
                continue
            edges[key] = {'km': km, 'fkm': fkm, 'chihou': chihou, 'src': seg['line_code']}

    # ---- 山手線 loop closing edge: 代々木-新宿 ----
    # MARS packs the Yamanote loop into two chains under different line codes
    # (山手１ line 197 ends at 代々木; 山手２ line 82 starts at 新宿) with no
    # row anywhere in nn_decoded.tsv linking them directly -- confirmed by
    # grepping the source tsv for a bare or prefixed 代々木/新宿 pair on any
    # single line_code; none exists. So this hop cannot be sourced from MARS
    # at all. 0.7km is HARDCODED here as an external constant: it is JR East's
    # own published 駅間キロ for 代々木-新宿 (not derived from "loop total
    # minus the other four legs" -- that would make the loop-total assertion
    # below circular and unable to fail).
    root_yoyogi = name_to_root['代々木']
    root_shinjuku = name_to_root['新宿']
    key = tuple(sorted((root_yoyogi, root_shinjuku)))
    closed_loop_edge_added = key not in edges
    if closed_loop_edge_added:
        edges[key] = {'km': 7, 'fkm': 7, 'chihou': False, 'src': 'external-constant-yoyogi-shinjuku-0.7km'}

    # ---- connected component containing 東京 ----
    adj = defaultdict(list)
    for (a, b) in edges:
        adj[a].append(b)
        adj[b].append(a)
    root_tokyo = name_to_root[TOKYO_ROOT_NAME]
    seen = {root_tokyo}
    q = deque([root_tokyo])
    while q:
        x = q.popleft()
        for y in adj[x]:
            if y not in seen:
                seen.add(y)
                q.append(y)

    comp_edges = {k: v for k, v in edges.items() if k[0] in seen and k[1] in seen}
    comp_roots = seen

    # ---- slugs: reuse old idmap slugs where the root already existed there ----
    old_root_for_slug = {}
    for slug, rec in old_idmap['map'].items():
        old_root_for_slug[slug] = find(rec['odpt'][0])
    root_to_old_slug = {r: slug for slug, r in old_root_for_slug.items()}

    used_slugs = set()
    root_to_slug = {}
    for root in comp_roots:
        if root in root_to_old_slug:
            slug = root_to_old_slug[root]
            root_to_slug[root] = slug
            used_slugs.add(slug)

    unresolved = [r for r in comp_roots if r not in root_to_slug]
    for root in sorted(unresolved):
        cid = canonical_id(root)
        en = id_by_id[cid]['title'].get('en', cid.split('.')[-1])
        base = slugify(en)
        slug = base
        if slug in used_slugs:
            suffix = camel_first_word(cid.split('.')[1])
            slug = f'{base}-{suffix}'
        n = 2
        while slug in used_slugs:
            slug = f'{base}-{suffix}{n}'
            n += 1
        root_to_slug[root] = slug
        used_slugs.add(slug)

    # ---- zones from old graph, Suica area from the published route map ----
    zone_counts = defaultdict(int)
    for rec in old_graph['stations'].values():
        for z in rec.get('zones', []):
            zone_counts[z] += 1

    stations_out = {}
    for root in comp_roots:
        cid = canonical_id(root)
        ja = id_by_id[cid]['title']['ja']
        slug = root_to_slug[root]
        rec = {'ja': ja}
        old_slug = root_to_old_slug.get(root)
        if old_slug and old_slug in old_graph['stations']:
            old_rec = old_graph['stations'][old_slug]
            if 'zones' in old_rec:
                rec['zones'] = old_rec['zones']
        railways = {i.rsplit('.', 1)[0] for i in root_to_ids[root]}
        rec['suica'] = not railways <= OUTSIDE_RAILWAYS
        stations_out[slug] = rec

    new_zone_counts = defaultdict(int)
    for rec in stations_out.values():
        for z in rec.get('zones', []):
            new_zone_counts[z] += 1

    missing_zone_stations = []
    for old_slug, old_rec in old_graph['stations'].items():
        if 'zones' not in old_rec:
            continue
        root = old_root_for_slug.get(old_slug)
        if root is None or root not in comp_roots:
            missing_zone_stations.append(old_slug)

    edges_out = []
    for (a, b), rec in comp_edges.items():
        edges_out.append({
            'a': root_to_slug[a], 'b': root_to_slug[b],
            'km': rec['km'], 'fkm': rec['fkm'], 'chihou': rec['chihou'],
            'src': rec['src'],
        })

    suica_true = sum(1 for r in stations_out.values() if r.get('suica'))

    # Data only -- no provenance block. Source: MARS for MS-DOS v5.38 (SWA /
    # 葛西隆也), 2026-03-14 revision; zones carried forward from the external
    # graph.json; Suica area from JR East's published 「Suicaご利用可能エリア
    # 首都圏エリア」route map, 2026-03-14 現在. Distances are in tenths of a km.
    out = {
        'stations': stations_out,
        'edges': edges_out,
    }
    json.dump(out, open(OUT_GRAPH_PATH, 'w'), ensure_ascii=False, indent=2)

    # ---- idmap ----
    # Only `odpt` is ever read. The station's name is not stored here -- the
    # generator resolves names off jreast-graph.json's `stations[*].ja`.
    idmap = {}
    for root in comp_roots:
        idmap[root_to_slug[root]] = {'odpt': sorted(root_to_ids[root])}
    idmap_out = {'map': idmap}
    json.dump(idmap_out, open(OUT_IDMAP_PATH, 'w'), ensure_ascii=False, indent=2)

    # ================= REPORT =================
    print(f'MARS rows total (excl sentinel): {len(rows)}')
    print(f'line codes total: {len(by_line)}')
    print(f'segments total: {total_segments}, classified JR-East: {jr_segments}')
    print(f'branch restarts detected: {len(restart_report)}')
    for rr in restart_report:
        print('  ', rr)
    print(f'excluded Shinkansen rows: {len(excluded_rows)} across line codes {sorted(EXCLUDED_LINE_CODES)}')
    print(f'prefix-rejected rows (ambiguous name, wrong company for this prefix): {len(prefix_rejected)}')
    for d in prefix_rejected:
        print('  ', d)
    print(f'isolated (non-corroborated) name matches dropped: {len(isolated_dropped)}')
    for d in isolated_dropped:
        print('  ', d)
    print(f'edges before component filter: {len(edges)}')
    print(f'yamanote loop closer added: {closed_loop_edge_added}')
    print(f'conflicts: {len(conflicts)}')
    for c in conflicts[:20]:
        print('  ', c)
    print(f'connected component (from 東京) size: {len(comp_roots)} stations, {len(comp_edges)} edges')
    long_edges = sorted(comp_edges.items(), key=lambda kv: -kv[1]['km'])[:15]
    print('longest single-hop edges in component (sanity check for phantom bridges):')
    for (a, b), rec in long_edges:
        an = id_by_id[canonical_id(a)]['title']['ja']
        bn = id_by_id[canonical_id(b)]['title']['ja']
        print(f'   {an} - {bn}: {rec["km"]/10}km (src {rec["src"]})')
    print(f'suica=true count: {suica_true}')
    print('zone counts (old graph):', dict(zone_counts))
    print('zone counts (new graph):', dict(new_zone_counts))
    print('missing zone stations (in old graph, absent from new component):', missing_zone_stations)

    # station coverage check: JR-East stations.json entries absent from the
    # FINAL graph (informational) -- this is presence in comp_roots, i.e.
    # after resolution, corroboration, AND the connected-component filter,
    # not merely "some MARS row's name matched at some point" (a name can
    # resolve via resolve() and still get dropped later by corroboration).
    never_matched = [s for s in jr if find(s['id']) not in comp_roots]
    never_matched_names = sorted({s['title']['ja'] for s in never_matched})
    print(f'JR-East stations.json entries absent from the final graph: {len(never_matched)}')
    for s in never_matched[:30]:
        print('  ', s['id'], s['title']['ja'])

    # All four sit beyond the Suica 首都圏エリア on lines this repo does not
    # carry, so MARS never links them to the 東京 component.
    expected_missing = {'原ノ町', '仙台', '会津若松', '喜多方'}
    if set(never_matched_names) == expected_missing:
        print(f'missing-name set matches expected 4: {sorted(expected_missing)}')
    else:
        print('MISMATCH: missing-name set differs from the expected 4')
        print('  expected:', sorted(expected_missing))
        print('  actual:  ', never_matched_names)

    # coord-less stations.json entries that ARE present in this graph (for
    # auditing the downstream fare generator's own coord-less exclusion list)
    coordless_in_graph = sorted(
        id_by_id[canonical_id(root)]['title']['ja']
        for root in comp_roots
        if 'coord' not in id_by_id[canonical_id(root)]
    )
    print(f'coord-less stations.json entries present in this graph: {len(coordless_in_graph)}')
    for n in coordless_in_graph:
        print('  ', n)

    # validation distances
    def dist(a_name, b_name):
        import heapq
        ra, rb = name_to_root[a_name], name_to_root[b_name]
        adj2 = defaultdict(list)
        for (x, y), rec in comp_edges.items():
            adj2[x].append((y, rec['km']))
            adj2[y].append((x, rec['km']))
        dd = {ra: 0}
        pq = [(0, ra)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dd.get(u, float('inf')):
                continue
            if u == rb:
                return d / 10
            for v, w in adj2[u]:
                nd = d + w
                if nd < dd.get(v, float('inf')):
                    dd[v] = nd
                    heapq.heappush(pq, (nd, v))
        return None

    print('東京-大宮:', dist('東京', '大宮'))
    print('東京-横浜:', dist('東京', '横浜'))
    print('東京-高尾:', dist('東京', '高尾'))
    print('東京-熱海:', dist('東京', '熱海'))
    print('東京-宇都宮:', dist('東京', '宇都宮'))
    print('東京-黒磯:', dist('東京', '黒磯'))
    print('品川-新横浜 (Shinkansen removed, should be 26.3):', dist('品川', '新横浜'))
    print('新横浜-小田原 (Shinkansen removed, should be 63.0):', dist('新横浜', '小田原'))
    print('草野-広野 (prefix fix, should be 17.6):', dist('草野', '広野'))

    def loop_len():
        # Sum the specific pairwise shortest-path legs that make up the
        # physical loop (not a single shortest-path query, which could in
        # principle hop through an unrelated shorter connection instead of
        # actually tracing the loop).
        legs = [('品川', '代々木'), ('代々木', '新宿'), ('新宿', '田端'),
                ('田端', '東京'), ('東京', '品川')]
        total = 0
        for a, b in legs:
            d = dist(a, b)
            if d is None:
                return None
            total += d
        return total

    print('山手線 loop (sum of 品川-代々木-新宿-田端-東京-品川 legs):', loop_len())

    for name in ['館山', '銚子', '日立', '黒磯', '水上', '横川', '猿橋', '安房鴨川']:
        root = name_to_root.get(name)
        present = root in comp_roots if root else False
        d = dist('東京', name) if present else None
        print(f'{name}: present={present} dist_from_tokyo={d}')

    print('Shinkansen-only stations (expected unreachable now):')
    for name in ['上毛高原', '安中榛名', '本庄早稲田']:
        root = name_to_root.get(name)
        present = root in comp_roots if root else False
        print(f'  {name}: present={present} (in stations.json: {root is not None})')

    # ---- diff vs the previous (pre-fix) run, saved to scratchpad ----
    try:
        prev = json.load(open(SCRATCH + 'jreast-graph-prev-run.json'))
        prev_names = {v['ja'] for v in prev['stations'].values()}
        new_names = {v['ja'] for v in stations_out.values()}
        dropped = sorted(prev_names - new_names)
        added = sorted(new_names - prev_names)
        print(f'stations dropped vs previous run: {len(dropped)}')
        for n in dropped:
            print('  ', n)
        print(f'stations added vs previous run: {len(added)}')
        for n in added:
            print('  ', n)
        print(f'previous run: {len(prev["stations"])} stations, {len(prev["edges"])} edges')
        print(f'this run: {len(stations_out)} stations, {len(edges_out)} edges')
    except FileNotFoundError:
        print('no previous-run snapshot found to diff against')


if __name__ == '__main__':
    main()
