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

## データの取り方

- 取得する範囲は絞らない。千代田線の全列車・両方向・全曜日区分（平日・土休日）・全時間帯を取る。
- 使うAPIは`odpt:TrainTimetable`（列車ごとの時刻表）。始発駅は`odpt:originStation`、曜日区分は`odpt:calendar`から取る。
- 1回の応答は1000件で打ち切られるので、曜日区分×方向の4回に分けて取る（2026-10-25時点で1回あたり264〜336本）。
- `odpt:StationTimetable`（駅ごとの時刻表）には始発駅が入っていないので使わない。同じAPIの`odpt:isOrigin`は「この駅から出る列車か」を示すだけで、途中駅では始発駅の判定に使えない。
- 曜日区分は`odpt.Calendar:Weekday`（平日）と`odpt.Calendar:SaturdayHoliday`（土休日）の2つ。
- 方向は方面名で書き、「上り・下り」は使わない。ODPTは綾瀬方面を`ascendingRailDirection`（上り）としていて、日常の呼び方と食い違うため。
  - 代々木上原方面: `odpt.RailDirection:TokyoMetro.YoyogiUehara`
  - 綾瀬方面: `odpt.RailDirection:TokyoMetro.KitaAyase`（IDは終点の北綾瀬だが、北綾瀬は支線なので綾瀬方面と呼ぶ）
- 駅IDは`odpt.Station:TokyoMetro.Chiyoda.<駅名>`の形（例: `…Chiyoda.YoyogiUehara`）。
- 始発駅のラベル: 千代田線内の駅から出る列車は「◯◯始発」（綾瀬始発・北綾瀬始発など）。JR常磐線や小田急線から来る列車は「直通」にまとめる。
  - 常磐線から来る列車は、`odpt:originStation`にJRの駅（例: `odpt.Station:JR-East.JobanLocal.Abiko`）が入る。
  - 小田急線から来る列車は、`odpt:originStation`が空で来る。空は直通とみなす。
- `data/trains.csv`の駅の列は代々木上原→北綾瀬の駅順。停まらない・通らない駅と終着駅は空にする。
  - 行のキーは時刻表ID（`odpt:TrainTimetable`の`owl:sameAs`から路線の前置きを除いたもの）。
  - 特急ロマンスカーは途中の停車駅に到着時刻しか無いので、終着駅以外は到着時刻を入れる。
  - 千代田線内のどの駅からも発車しない時刻表（綾瀬に到着するだけのもの。2026-10-25時点で平日5件）は載せない。
- 参考: [ODPTから代々木上原駅始発の便のデータを取得してみた](https://zenn.dev/greenteabiscuit/articles/5613babc3e6648)（2024-07、曜日区分・方向IDの実例）

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
