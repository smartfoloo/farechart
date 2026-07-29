# Farechart

東京都市圏の鉄道運賃マップ。駅を1つ選ぶと、そこからの運賃で他のすべての駅を色分け表示する。

対応事業者: JR東日本、東武鉄道、東急電鉄、西武鉄道、京急電鉄、京王電鉄、相鉄、東京メトロ、都営地下鉄、横浜市営地下鉄、つくばエクスプレス、多摩都市モノレール、ゆりかもめ、りんかい線

## セットアップ

```
npm install
npm run dev
```

アプリが使うデータ(駅グループ、事業者ごとの運賃表、路線形状)は `dev`/`build` の前に `npm run data` で自動生成される。`data/` にある元データ(ODPTなど)を読み込み、`public/data/` にブラウザ用のデータを出力する。

## データソース

- `data/RailwayFares.Challenge2026.json`、`data/RailwayFares.ODPT.json` — 運賃データ。[ODPT](https://www.odpt.org/) 提供
- `data/railway-lines.json`、`data/station-groups.json`、`data/stations.json` — 路線・駅・乗換グループのデータ。[nagix/mini-tokyo-3d](https://github.com/nagix/mini-tokyo-3d) より
- `data/polygons` — 地図に描く路線形状データ。[uedayou/jrslod-geojson-downloader](https://github.com/uedayou/jrslod-geojson-downloader) より
- `data/RailwayFares.JREast.slim.json` — JR東日本の運賃データ。ODPTは公開していないため**独自に算出**したもの。`scripts/jr-east/jreast-gen-fares.py` が、MARSから復元した営業キロ・換算キロ両方を持つ距離グラフをもとに、公表されている幹線・地方交通線の運賃表と特定都区市内・特定区間運賃のルールを当てはめて生成する。対象範囲はSuica首都圏エリアのみ。

### JR東日本の路線形状データについて

`data/polygons` の元データ(uedayou/jrslod-geojson-downloader によるスクレイピング)は、JR東日本の一部路線で不正確だった。具体的には、1本の連続した線ではなく、駅付近だけの短い線分が多数バラバラに散らばった形で入っており、地図上で線が途切れ途切れになっていた(山手線・横須賀線・根岸線・総武本線などが該当)。

この問題があった路線は、`data/polygons/JR-East.geojson` から削除し、代わりに1本の連続した線として描き直したものを `data/polygons/JR-East-special.geojson` に分けて格納している。ビルド時(`scripts/build-data.mjs`)はこの special ファイルも読み込み、そこに含まれる路線には `special: true` のフラグを付けて出力するため、通常のスクレイピングデータとは区別できる。現在 special ファイルに入っているのは以下の7路線: 山手線、中央線快速、中央・総武線各駅停車、埼京・川越線、京浜東北・根岸線、横須賀線、総武線快速。

また、`data/polygons/JR-East.geojson` にはもともと東北・上越・信越エリアなど、このアプリの運賃計算対象(Suica首都圏エリア)外にある路線(五能線、男鹿線、津軽線など)の形状データも含まれていたが、運賃データが存在せず地図上でも使われないため削除した。

**この結果、JR東日本の一部路線は地図上に形状データがない状態になっている。** 運賃データを持つJR東日本の路線は54あるが、そのうち地図に形状を描けるのは(通常データ28+special 7路線の重複を除き)一部にとどまり、高崎線・宇都宮線・東海道線本線・総武本線・中央本線・鶴見線・相模線・青梅線・篠ノ井線などの主要路線を含め、形状データが欠けている路線が複数ある。これらの路線でも運賃計算・経路探索自体は正常に動作するが、地図上には線が表示されない。

## 技術スタック

Svelte 5 + Vite、地図描画に MapLibre GL を使用。
