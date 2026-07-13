# Farechart

A fare map for the Tokyo metropolitan area's railway network. Select a station and the map colors every other station by the fare to get there from it.

Supported operators: Tobu, Tokyu, Seibu, Keikyu, Keio, Sotetsu, Tokyo Metro, Toei Subway, Yokohama Municipal Subway, Tsukuba Express, Tama Toshi Monorail, Yurikamome, Rinkai Line

## Setup

```
npm install
npm run dev
```

App data (station groups, per-operator fare tables, and line shapes) is generated automatically before `dev`/`build` via `npm run data`. It reads the raw ODPT data in `data/` and outputs browser-ready data to `public/data/`.

## Data sources

- `data/RailwayFares.Challenge2026.json`, `data/RailwayFares.ODPT.json` — fare data, provided by [ODPT](https://www.odpt.org/)
- `data/railway-lines.json`, `data/station-groups.json`, `data/stations.json` — line, station, and interchange-group data, from [nagix/mini-tokyo-3d](https://github.com/nagix/mini-tokyo-3d)
- `data/polygons` — line shape data for the map, from [uedayou/jrslod-geojson-downloader](https://github.com/uedayou/jrslod-geojson-downloader)

## Tech stack

Svelte 5 + Vite, with MapLibre GL for map rendering.
