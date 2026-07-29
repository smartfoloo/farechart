# Farechart

東京都市圏の鉄道運賃マップ。

対応事業者: JR東日本、東武鉄道、東急電鉄、西武鉄道、京急電鉄、京王電鉄、相鉄、東京メトロ、都営地下鉄、横浜市営地下鉄、つくばエクスプレス、多摩都市モノレール、ゆりかもめ、りんかい線

## セットアップ

```
npm install
npm run dev
```

アプリが使うデータ(駅グループ、事業者ごとの運賃表、路線形状)は `dev`/`build` の前に `npm run data` で自動生成されます。`data/` にある元データ(ODPTなど)を読み込み、`public/data/` にブラウザ用のデータを出力する。

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
