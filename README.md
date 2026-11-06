# ChiyoRush

東京メトロ千代田線の列車のうち、小田急線・JR常磐線に直通しない列車（千代田線内で始発・終着になる列車）を見分ける時刻表のページです。
直通運転する列車に比べて、車内が空いていることが期待されます。

- ページ: https://gracom.github.io/chiyorush/

## できること

- 駅と方面を選ぶと、次の発車と1日の時刻表を、列車の区分ごとに色を分けて出します。千代田線内の始発・終着は緑、北綾瀬始発は青、直通は灰色です。
- 「出勤（始発駅特定）」は列車を始発駅で分けます。「退勤（終着駅特定）」は列車を終着駅で分けます。
  開いた時刻で自動に決まり、正午より前は出勤、正午からは退勤になります。出勤はライト、退勤はダークで表示します。
- 曜日（平日・土休日）は、今日の曜日で自動に決まります。
- `#駅.方面`付きのリンクで開くと、その駅・方面で出ます（例: `#Otemachi.YoyogiUehara`）。退勤は末尾に`.terminal`を付けます。
- 選んだ駅と方面は、そのブラウザのCache Storageとクッキーにだけ残ります。ページの外へは通信しません。
- 特急ロマンスカー（座席指定の有料特急）は載せていません。

## 仕組み

```
ODPT API ──(週1回 timetable.yml)──> data/trains.csv ──(build_data.py)──> data/timetable.json
                                                                              │
site/index.html ─────────────────(pages.yml: build_site.py で埋め込み)────────┴──> GitHub Pages
```

| パス | 中身 |
|---|---|
| `site/` | ページ（`index.html`）とアイコン。`index.html`の`<script id="timetable-data">`は空にしてあり、公開するときに時刻表を埋め込む |
| `data/trains.csv` | 1行1列車（ODPTの列車時刻表1件）。駅ごとの列に発車時刻 |
| `data/stations.csv` | 千代田線の駅順と駅名 |
| `data/timetable.json` | ページに埋め込む時刻表。駅・方面・曜日区分ごとに`[発車時刻（分）, 始発駅, 終着駅]`を並べる |
| `scripts/fetch_odpt.py` | ODPTから時刻表を取得し、`data/trains.csv`・`data/stations.csv`を書き出す |
| `scripts/build_data.py` | `data/trains.csv`から`data/timetable.json`を作る |
| `scripts/build_site.py` | `site/`に時刻表を埋め込み、`_site/`に書き出す |
| `tests/` | スクリプトのテスト |
| `.github/workflows/timetable.yml` | 週1回（月曜03:00 JST）ODPTから取得し、差分があればPRを出す |
| `.github/workflows/pages.yml` | `main`が変わったらGitHub Pagesに公開する |

スクリプトはPythonの標準ライブラリだけで動きます。

```sh
python3 -m unittest discover -s tests
ODPT_CONSUMER_KEY=... python3 scripts/fetch_odpt.py
python3 scripts/build_data.py
python3 scripts/build_site.py      # _site/index.html をブラウザで開いて確かめる
```

## 動かすための設定

- Secretsに`ODPT_CONSUMER_KEY`（ODPTのアクセストークン）を登録する。
- Settings → Pages の Source を「GitHub Actions」にする。
- Settings → Actions → General の「Allow GitHub Actions to create and approve pull requests」を有効にする（時刻表の更新をPRで出すため）。

## データの出典

公共交通オープンデータセンター（ODPT）の、東京メトロの列車時刻表をもとにしています。

- 公共交通オープンデータセンター: https://www.odpt.org/
- 内容の正確性・完全性は保証されません。遅延や運転見合わせは反映されません。
- 表示内容について、東京メトロへ直接お問い合わせにならないようお願いします。
- このページへのお問い合わせは、このリポジトリのIssueからお寄せください。
