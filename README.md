# Farechart

東京都市圏の鉄道運賃マップ。

対応事業者: JR東日本、東武鉄道、東急電鉄、西武鉄道、京急電鉄、京王電鉄、相鉄、東京メトロ、都営地下鉄、横浜市営地下鉄、つくばエクスプレス、多摩都市モノレール、ゆりかもめ、りんかい線

## セットアップ

```
npm install
npm run dev
```

アプリが使うデータ(駅グループ、事業者ごとの運賃表、路線形状)は `dev`/`build` の前に `npm run data` で自動生成されます。

## ファイル構成

運賃の計算はすべてビルド時に済ませ、ブラウザはその結果を読むだけ。

### 生成スクリプト (`scripts/`)

- `build-data.mjs` — `data/` を読んで `public/data/` を出力する。駅の統合、運賃表のバイナリ化、路線形状の整形、乗継割引の駅名解決まで担当する。
- `slim-fares.mjs` — ODPTの生ダンプから必要な8項目だけを抜き出して `*.slim.json` を作る。元データが更新されたときだけ実行する。
- `jr-east/jreast-gen-fares.py` — JR東日本の運賃を算出する。手動実行で、`npm run data` には含まれない。
- `jr-east/build-graph-from-mars.py` — MARSの解析結果から距離グラフを作る。
- `jr-east/import-graph.py` — 特定区間運賃の一覧を変換する。

### 元データ (`data/`)

- `RailwayFares.ODPT.json`、`RailwayFares.Challenge2026.json` — ODPTの運賃ダンプ。`npm run slim` の入力で、ビルドは直接読まない。
- `RailwayFares.*.slim.json` — 上を絞り込んだもの。ビルドが実際に読む運賃データ。
- `stations.json` — 駅の座標と駅名。運賃データに出てくる駅はここに無いと扱えない。
- `station-groups.json` — 同一駅として扱う駅IDのまとまり。乗換駅の統合に使う。
- `railway-lines.json` — 路線IDごとの路線名と色。運賃データが参照する路線が欠けているとビルドが止まる。
- `transfer-discounts.json` — 乗継割引。事業者間で一律のものと、乗換駅と両端の駅で決まる条件付きのものがある。
- `polygons/<事業者>.geojson` — 地図に描く路線形状。`<事業者>-special.geojson` があれば、手描きの直通路線として重ねて読み込む。
- `jr-east/` — JR東日本の運賃算出に使う距離グラフと運賃表。

### 生成物 (`public/data/`)

`npm run data` のたびに作り直すので、直接編集しない。

- `stations.json` — 駅一覧、路線・事業者の情報、乗継割引。アプリが最初に読む。
- `lines.geojson` — 地図に描く路線形状。
- `fares/<事業者>.bin` — 事業者ごとの運賃表。触った事業者の分だけ読み込む。

## データソース

- `data/RailwayFares.Challenge2026.json`、`data/RailwayFares.ODPT.json` — 運賃データ。[ODPT](https://www.odpt.org/) 提供
- `data/railway-lines.json`、`data/station-groups.json`、`data/stations.json` — 路線・駅・乗換グループのデータ。[nagix/mini-tokyo-3d](https://github.com/nagix/mini-tokyo-3d) より
- `data/polygons` — 地図に描く路線形状データ。[uedayou/jrslod-geojson-downloader](https://github.com/uedayou/jrslod-geojson-downloader) より
- `data/RailwayFares.JREast.slim.json` — JR東日本の運賃データ。ODPTは公開していないため独自に算出したものです。`scripts/jr-east/jreast-gen-fares.py` が、MARSから復元した営業キロ・換算キロ両方を持つ距離グラフをもとに、公表されている幹線・地方交通線の運賃表と特定都区市内・特定区間運賃のルールを当てはめて生成しています。対象範囲はSuica首都圏エリアのみです。

### JR東日本の路線形状データについて

`data/polygons` の元データ(uedayou/jrslod-geojson-downloader)は、JR東日本の正式路線名ごとのものであったため、一部路線では運行形態と異なる路線形状データが見られました。

この問題があった路線は、`data/polygons/JR-East.geojson` から削除し、代わりに1本の連続した線として描き直したものを `data/polygons/JR-East-special.geojson` に分けて格納しています。

また、`data/polygons/JR-East.geojson` にはもともと東北・上越・信越エリアなど、このアプリの運賃計算対象(Suica首都圏エリア)外にある路線(五能線、男鹿線、津軽線など)の形状データも含まれていましたが、運賃データが存在せず地図上でも使われないため削除しました。

そのため、形状データがない路線がいくつかあります。この路線に関してはアップデートで順次修正を加えていく予定です。

## 技術スタック

Svelte 5 + Vite、地図に MapLibre GL を使用。
