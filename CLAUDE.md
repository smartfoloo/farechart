# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```
npm install
npm run dev        # runs `npm run data` first via predev, then vite
npm run build      # runs `npm run data` first via prebuild
npm run data       # regenerate public/data/ from data/
npm run slim       # re-derive data/*.slim.json from the raw ODPT dumps
```

There is **no test suite and no linter**. Don't invent commands for them; verify changes by running the app.

`npm run slim` is a one-off preprocessing step, not part of dev/build. It reads the ~67 MB raw
`data/RailwayFares.*.json` dumps and writes the committed `*.slim.json` files that `build-data.mjs`
actually consumes. Only rerun it when the raw dumps change.

Node 22 (`.node-version`).

## Architecture

Two stages with a hard boundary: a Node build script precomputes everything, and the browser app
only reads its output. No fare logic runs at request time.

```
data/ (raw, committed)  ->  scripts/build-data.mjs  ->  public/data/  ->  src/ (Svelte 5 + MapLibre)
```

`public/data/` is deleted and rewritten on every `npm run data`. Never edit it by hand.

### Logical stations are the core abstraction

Almost everything else follows from this. A "station" in the UI is not an ODPT station id — it is a
**complex** of ids merged by union-find in `build-data.mjs`, and its integer index into
`meta.stations` is the identity used by fares, routing, and the map.

Two signals feed the merge: `data/station-groups.json`, and Tokyo Metro's ¥0 fare records (which mark
out-of-station transfers). The ¥0 records are deliberately **not** all unioned — only pairs where one
station's name is a prefix of the other. The comment in `build-data.mjs` explains why: unioning them
transitively chains Otemachi to Yurakucho via Tokyo and understates real fares. Preserve that
restriction.

Where a complex bills as several fare origins (Toei charges more from Shinjuku-nishiguchi than from
Shinjuku), the node **quotes the cheapest**. A complex spanning differently-named stations
(虎ノ門 / 虎ノ門ヒルズ) stays one fare node but gets a `members` array so the map can draw each
physical station.

Station ids are `Operator.Line.Station`; the first two segments are the railway id.

### The binary fare format is written and read in two places

`build-data.mjs` emits one `public/data/fares/<Operator>.bin` per operator as a CSR adjacency, and
`src/lib/data.js` parses it back. **The layout is duplicated, not shared** — header, offsets,
toGlobal, then five parallel `Uint16Array`s (dest, ic, ticket, childIc, childTicket). Changing either
side requires changing the other in lockstep.

Constraints baked into the format: fares and node indices are `uint16` (the build throws if a fare
exceeds 0xffff), and pairs are keyed as `a * 100000 + b`, capping the network at 100000 nodes.

Fare rows within an origin are sorted by destination so `fareBetween` can binary-search. Each
operator's blob is fetched lazily and cached in `src/lib/data.js`, so the app only downloads networks
the user actually touches.

### Routing

`src/lib/route.js` builds a graph where a node is **(stationIdx, railwayId)**, not a station — that's
what makes transfers explicit. Same-station edges between different railways cost `TRANSFER = 8`
against a ride hop of 1, so the search prefers staying on one line over hopping for marginal savings.
The graph is cached in a `WeakMap` keyed on the meta object.

Per-line stop order (`meta.lines[id].stops`) is recovered in `build-data.mjs` by walking
`data/stations.json` in file order, because records for a railway appear consecutively in geographic
order there. That ordering is load-bearing.

### Adding an operator

The `OPERATORS` array at the top of `build-data.mjs` gates everything — fare tables, line geometry,
and the operator picker. An operator needs fare records in the dumps, an entry in
`data/railway-lines.json` for every railway its nodes reference (the build throws otherwise), and a
`data/polygons/<key>.geojson`.

Keikyu (from 2023-10) and Seibu (from 2026-03) charge one flat child IC fare at any distance instead
of a distance curve — Seibu ¥50 system-wide, Keikyu ¥75 except a separate flat ¥100 on the Haneda
Airport line. ODPT's dumps used to still derive these as a distance curve, which needed a
`FLAT_CHILD_IC` override in `build-data.mjs`; ODPT now emits the flat fares (and the airport
exception) directly per record, so the override was removed — don't reintroduce it.

### `<key>-special.geojson`: hand-drawn overrides for bad scraped lines

`data/polygons/<key>.geojson` comes from uedayou/jrslod-geojson-downloader, and some of its JR East
lines are wrong: instead of one continuous path, the line is many short disconnected segments (mostly
just the stretch near each station), so it renders as a gapped, broken line on the map. 山手線,
横須賀線, 根岸線, and 総武本線 were all affected this way.

The fix for an affected line is a hand-drawn replacement — a single continuous `LineString` — kept in
an optional `data/polygons/<key>-special.geojson` sibling file, loaded in `build-data.mjs` alongside
the base file. Its properties schema differs from the scraped file's (`{ id, ja, en, color }`, color
already `#`-prefixed, vs. the scraped `{ name, uri, color }` with an unprefixed color) — `build-data.mjs`
normalizes both. Features from the special file are tagged `special: true` in the emitted
`lines.geojson` so the frontend can tell them apart from the scraped set.

JR East's special file currently holds 7 lines: 山手線, 中央線快速, 中央・総武線各駅停車, 埼京・川越線,
京浜東北・根岸線, 横須賀線, 総武線快速. Their now-redundant, broken counterparts (old 山手線, 中央線,
根岸線, 横須賀線, 総武本線 features) were deleted from `JR-East.geojson` outright rather than left in
as dead duplicates.

`JR-East.geojson` also no longer carries lines with no fare data — the app only prices the Suica
首都圏エリア, so Tohoku/Niigata/Nagano-area lines like 五能線, 男鹿線, and 津軽線 were dropped along with
about two dozen others in the same situation.

**As a result, several JR East lines currently have no polygon coverage at all.** 54 JR East railways
carry fare/routing data (`data/railway-lines.json`), but only 28 distinct line names have a matching
polygon feature (scraped + special combined) — among the missing are trunk lines that do carry fare
data and should eventually get coverage: 総武本線, 中央本線, 高崎線, 宇都宮線, 東海道線, 鶴見線, 相模線,
青梅線, 篠ノ井線. Fares and routing work fine for these; they just don't draw on the map.

## JR East (wired in; fares are computed, not sourced)

ODPT publishes no JR fare data, so JR East fares are **computed** by
`scripts/jr-east/jreast-gen-fares.py` and written to `data/RailwayFares.JREast.slim.json`. Regenerate
that file by hand (`python3 scripts/jr-east/jreast-gen-fares.py`) — it is NOT part of `npm run data`.

Unlike the ODPT dumps it does **not** ship one record per directed pair. That form was 96 MB of
almost entirely redundant text, so it ships as a node table plus one row per *undirected* pair:

```
{ op, iss, nodes: [[odptId, ...], ...], pairs: [[i, j, ic, tk], ...] }
```

`op` and `iss` are constant across every row; the fare is symmetric (0 asymmetric pairs out of
221,445); and both child fares are exact functions of the adult ones — JR floors the child IC fare to
¥1 and the child ticket fare to ¥10. `expandJREast` in `build-data.mjs` expands this back to the flat
record shape the rest of that script reads, re-deriving the child fares. **That expansion is agreed
with the generator, not shared with it** — like the binary fare format, changing either side requires
changing the other. The rounding must not become a shared helper: Toei rounds its child fare *up*.
The reformat is lossless — it reproduces all 577,885 records and byte-identical `public/data/`.

Distances come from `data/jr-east/jreast-graph.json`: 703 stations, 733 undirected edges, one
connected component, carrying **both** 営業キロ (`km`) and 換算キロ (`fkm`) per edge in tenths of a km,
plus a `chihou` flag, the 特定都区市内 zone membership, and a `suica` flag. Because 換算キロ is now
present, 地方交通線 are priced rather than dropped.

**Only the Suica 首都圏エリア is priced.** `suica` marks the 666 stations inside it, per JR East's
published route map (2026-03-14 現在); the other 37 are 烏山線, 久留里線 and 吾妻線, the only lines the
graph carries that the map omits. That set lives in `OUTSIDE_RAILWAYS`, duplicated in
`build-graph-from-mars.py` (which writes the flag) and `jreast-gen-fares.py` (which also strips those
railway ids off 宝積寺, 木更津 and 渋川, each of which stays inside on its other line). Excluded
stations keep their distances — a route may still pass through one — they just never get a fare
record, and `build-data.mjs` derives its whole station list from fare records, so they vanish from
the app. ◆ Suica一部対応駅 (吾妻線's three, 水郡線, 小海線's 清里・野辺山) count as outside.

**The fare depends on the route's composition, not just its length:**

- entirely 幹線 → 営業キロ against the 幹線 table
- entirely 地方交通線 → 営業キロ against the 地方交通線 table
- mixed → 換算キロ against the 幹線 table

So the generator runs Dijkstra twice per origin (minimising `km`, then `fkm`), reconstructs both
paths, prices each under the rule above and charges the cheaper. Taking the min is correct, not a
shortcut: inside 東京近郊区間 the passenger is charged the cheapest available route. 東京-銚子 is the
case that exercises it — 119.5 km via 京葉→外房→東金→総武 (touching the 東金線, so priced on 換算 120.9)
against 120.5 km all-幹線 via 総武本線.

**経路特定区間 still needs no override pass** — inside 東京近郊区間 the fare is the shortest route, so
shortest-path selects the fare route by itself (東京-大宮 comes out 30.3 via 田端, not the 30.5
physical route via 尾久).

**特定区間運賃 IS now applied** — all 29 pairs, with real published fares, as
`min(ordinary, special)` and **after** the zone override (新宿-八王子 is ¥620 / IC 616, not the ¥720 /
715 the distance alone gives).

Every priced pair is inside the Suica area by construction, so IC fares always exist; the `ic` field
only equals `ticket` where the band itself carries no separate IC figure (¥220 and ¥1,980 on
地方交通線, which have no 幹線 counterpart to borrow one from).

The `data/jr-east/*.json` files hold the rules and distances behind this.

- `jreast-graph.json` — the distance graph described above. Each edge carries `src`, the source line
  code it came from; keep it, both bugs found while building this file were diagnosed from it.
- `jreast-graph-idmap.json` — graph id → the ODPT ids of that station's logical complex
- `jreast-fare-tables.json` — 幹線 bands 1–640 km and the full 地方交通線 table, both transcribed
  from jr-group.jp. The 地方交通線 bands are **not** uniform 5/10 km steps — they widen (47–55,
  56–64, …) and carry an extra ¥1,980 band the 幹線 table has no equivalent of. An earlier version
  derived them from a rate formula and got both the boundaries and the amounts wrong above 10 km.
  Don't compute these.
- `jreast-special-section-fares.json` — the 29 特定区間運賃 pairs, **fares populated**

JR rounds child fares **down**; Toei rounds up, so don't share a helper. That rule is implemented in
`build-data.mjs` (`expandJREast`); `jreast-child-fares.json`, which only documented it, is gone.

**No JSON file in `data/` carries provenance.** Every `_meta` / `_source` / `_note` / `_section`
block was stripped, and the writers were changed to stop emitting them — so were station names
sitting alongside ids, and `verified` / `base` flags. Don't reintroduce any of it. The citations for
data that cannot be re-derived (the hand-transcribed fare tables, the MARS decode, the 乗継割引
table) live in the header of the script that reads the file: `jreast-gen-fares.py` for
`data/jr-east/*`, `build-data.mjs` for `transfer-discounts.json`. Keep them there and in sync.

`jreast-fare-zones.json`, `jreast-tokyo-kinko-kukan.json`, `jreast-keiro-tokutei.json` and
`jreast-station-km.json` were deleted: nothing read them (zone logic is reimplemented in
`zone_override`, 経路特定区間 falls out of shortest-path), and `jreast-station-km.json` had no
producer either. The wikipedia scrapers that built it (`wikitable-grid.py`, `scrape-jreast-km.py`,
`fill-jreast-km.py`, `jreast-pair-km.py`) are gone too — they could not even run, importing a
`grid`/`join` module that does not exist.

**`build-idmap.py` was deleted and `import-graph.py` no longer writes the graph.** Both regenerated
their outputs from the external 495-station `graph.json`, which would silently delete coverage
against the live 703-station MARS decode. `import-graph.py` survives because it is the only producer
of `jreast-special-section-fares.json`; it now writes nothing else.

Two lessons from the superseded scraper era still apply to any distance data: coverage percentages
hide corruption (a line once hit 47/47 stations while being 15 km wrong across an unrebased seam),
and **a single bad km silently creates a phantom shortcut that corrupts every fare routed through
it**. Validate against known station-pair distances, never against coverage counts. Two real
instances found while building the current graph: same-named stations merged across JR companies
(a bogus 草野-広野 edge of 10.8 km, the JR West 福知山線 distance, against the true 常磐線 17.6 km),
and 東海道新幹線 edges leaking in (新横浜 exists at km 6.1 on the 横浜線 and km 28.8 on the Shinkansen,
which produced a 品川-新横浜 of 22.0 against the true 26.3). Shinkansen line codes are excluded
outright: ordinary fares are computed on 在来線 distance and this app prices no supplements.

All three 特定都区市内 rules fire now (山手線内 1048 pairs, 都区内 856, 横浜市内 1026). 都区内 and
横浜市内 need a destination >200 km from the hub and used to have none, because every candidate was a
coord-less `stations.json` entry the build had to exclude; those coordinates now exist.

**`data/stations.json` is the coverage ceiling, not MARS.** The graph builder matches MARS rows by
name against JR-East entries in `stations.json`, so a station missing there is missing from the fare
data no matter what MARS knows. 63 stations were added by hand for exactly this reason (常磐線
高萩〜浪江, 中央本線 竜王〜塩尻, 篠ノ井線, 大糸線 松本〜白馬, 信越本線 篠ノ井〜長野). Their
coordinates come from `Seo-4d696b75/station_database` (駅データ.jp + 国土数値情報), 6 decimal places;
nothing in the fare path reads them, they only place a dot on the map.
`build-graph-from-mars.py` also needs `TRUST_UNCORROBORATED` for 信濃大町 and
白馬: its corroboration net assumes a real stretch is a contiguous run of matched rows, which is false
where the Suica area itself skips 8 stations at a time.

JR East's 2026-03-14 revision abolished the 電車特定区間 and 山手線内 fare tables and merged them into
幹線. Pre-2026 Tokyo-area fare tables are wrong; don't carry them forward.

## Conventions

Svelte 5 runes (`$state`, `$derived`, `$props`, `$effect`) — not the older store/`export let` style.

Comments in this codebase explain *why*, especially where a rule looks arbitrary but encodes a real
tariff quirk. Match that when touching `build-data.mjs` or `route.js`.

UI strings are Japanese-first with English alongside in `src/lib/i18n.js` (`LABELS[lang]`).
