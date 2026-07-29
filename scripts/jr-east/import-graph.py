#!/usr/bin/env python3
"""Convert the externally-sourced 特定区間運賃 list into this repo's format.

This script used to also write data/jr-east/jreast-graph.json from the external
graph.json. It no longer does, and must not: that graph carries 495 stations,
while the live one is the 703-station MARS538 decode written by
build-graph-from-mars.py. Re-emitting it here would silently delete fare
coverage. graph.json is still read, but only as the id namespace the
special-fare slugs are validated against.

Inputs (read-only):
  - GRAPH_SRC: station/adjacency graph -- used ONLY to validate station slugs
  - SPECIAL_SRC: 特定区間運賃 (specified-section fare) list

Output:
  - SPECIAL_OUT: data/jr-east/jreast-special-section-fares.json
"""
import json
from pathlib import Path

GRAPH_SRC = Path("/Users/rios/Downloads/graph.json")
SPECIAL_SRC = Path("/Users/rios/Downloads/special.json")

SPECIAL_OUT = Path("/Users/rios/farechart/data/jr-east/jreast-special-section-fares.json")

# special.json uses two ids that don't exist in graph.json under those names.
ID_FIXUPS = {
    "okubo": "okubo-chuo",   # 大久保 (Chuo line), vs. graph's other okubo-* ids
    "shinbashi": "shimbashi",  # 新橋 — graph.json spells it "shimbashi"
}


def resolve_id(raw_id, stations):
    fixed = ID_FIXUPS.get(raw_id, raw_id)
    if fixed not in stations:
        raise SystemExit(f"STOP: special-fare id '{raw_id}' (fixed: '{fixed}') not found in graph.json stations")
    return fixed


def build_special(special_src, stations):
    out = []
    for rec in special_src:
        a = resolve_id(rec["from"], stations)
        b = resolve_id(rec["to"], stations)
        if a > b:
            a, b = b, a
        # Station names are deliberately not stored -- jreast-gen-fares.py keys
        # on the slugs alone and resolves names off jreast-graph.json.
        out.append({"a": a, "b": b, "ticket": rec["fare"], "ic": rec["icFare"]})
    out.sort(key=lambda r: (r["a"], r["b"]))
    return out


def main():
    stations_src = json.loads(GRAPH_SRC.read_text())["stations"]
    special_src = json.loads(SPECIAL_SRC.read_text())["specialFares"]

    special_fares = build_special(special_src, stations_src)
    print(f"[validate] special fares resolved: {len(special_fares)}/{len(special_src)}")

    # Data only -- no provenance block. Source: special.json (external), JR East
    # 2026-03-14 fare revision. These are 特定区間運賃, applied by the generator as
    # min(ordinary, special) AFTER the 特定都区市内 zone override.
    SPECIAL_OUT.write_text(json.dumps({"fares": special_fares}, ensure_ascii=False, indent=2) + "\n")
    print(f"[write] {SPECIAL_OUT}")


if __name__ == "__main__":
    main()
