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

Operator-specific tariff quirks live there too: `FLAT_CHILD_IC` overrides Keikyu and Seibu, whose IC
child fare is flat at any distance even though ODPT still derives a distance curve for it.

## JR East (wired in; fares are computed, not sourced)

ODPT publishes no JR fare data, so JR East fares are **computed** by
`scripts/jreast-gen-fares.py` and written to `data/RailwayFares.JREast.slim.json` in the same slim
format as the ODPT dumps, which `build-data.mjs` then treats like any other operator. Regenerate that
file by hand (`python3 scripts/jreast-gen-fares.py`) — it is NOT part of `npm run data`.

The pipeline is: shortest path over a 558-node graph built from 営業キロ, then the 幹線 fare band
table, then 特定都区市内 zone overrides. **幹線 only** — the 10 地方交通線 are excluded because
pricing a route touching one needs 換算キロ, which is not collected; using 営業キロ against the 幹線
table would silently under-price every such pair.

Two rules that look like they need code but do not: **経路特定区間 needs no override pass**, because
inside 東京近郊区間 the fare is the shortest route, so shortest-path selects the fare route by itself
(東京-大宮 comes out 30.3 via 田端, not the 30.5 physical route via 尾久). And **特定区間運賃 is not
applied** — the 12 surviving pairs are known but their fares are not published anywhere accessible,
so those pairs currently get the ordinary distance fare (新宿-八王子 yields 715; the real special
fare is reportedly 616).

The `data/jreast-*.json` files hold the rules and distances behind this.

- `jreast-fare-tables.json` — 幹線 fare bands (verified) and 地方交通線 (derived, unverified)
- `jreast-fare-zones.json` — 特定都区市内 zone rules; these override shortest-path distance
- `jreast-tokyo-kinko-kukan.json` — 東京近郊区間 line inventory and 幹線/地方交通線 classification
- `jreast-keiro-tokutei.json` — 経路特定区間 shorter-route fare distances
- `jreast-special-section-fares.json` — the 12 surviving 特定区間運賃 pairs; **fares are null**
- `jreast-child-fares.json` — JR rounds child fares **down**; Toei rounds up, so don't share a helper
- `jreast-station-km.json` — 営業キロ per station, keyed by `data/stations.json` line ids

`jreast-station-km.json` covers 825/851 stations across 46/58 lines. 山手線 is a **loop**: its km
comes from 駅間キロ (adjacent-pair distances), not a cumulative column, because a loop wraps to 0.0 at
its origin and has no monotonic cumulative. Its `closing_edge` (品川-大崎, 2.0 km) is **not** a
consecutive pair in the station list — anything walking consecutive pairs must add it explicitly or
central Tokyo routes come out wrong.

The Python scrapers (`scripts/wikitable-grid.py`, `scrape-jreast-km.py`, `fill-jreast-km.py`) pull
営業キロ from ja.wikipedia raw wikitext. Two lessons are encoded in them and worth keeping: coverage
percentages hide corruption (a line hit 47/47 stations while being 15 km wrong across an unrebased
seam), and a single bad km silently creates a phantom shortcut that corrupts every fare routed
through it. Validate with the monotonicity gate and the known station-pair distances listed in the
data file's `_meta.validation`, not with coverage counts.

JR East's 2026-03-14 revision abolished the 電車特定区間 and 山手線内 fare tables and merged them into
幹線. Pre-2026 Tokyo-area fare tables are wrong; don't carry them forward.

## Conventions

Svelte 5 runes (`$state`, `$derived`, `$props`, `$effect`) — not the older store/`export let` style.

Comments in this codebase explain *why*, especially where a rule looks arbitrary but encodes a real
tariff quirk. Match that when touching `build-data.mjs` or `route.js`.

UI strings are Japanese-first with English alongside in `src/lib/i18n.js` (`LABELS[lang]`).
