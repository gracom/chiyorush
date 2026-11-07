#!/usr/bin/env python3
"""ODPT（公共交通オープンデータセンター）から千代田線の列車時刻表を取得し、1行1列車のCSVに書き出す。

- 1行は ODPT の列車時刻表1件。駅ごとの列に、その駅の発車時刻を入れる（停まらない・通らない駅と終着駅は空）。
- 特急ロマンスカーは途中の停車駅に到着時刻しか無いので、終着駅以外は到着時刻を入れる。
- 千代田線内のどの駅からも発車しない時刻表（綾瀬に到着するだけのもの）は載せない。

- 取得範囲は絞らない。千代田線の全列車・両方向・全曜日区分・全時間帯。
- 始発駅のラベルは、千代田線内の駅から出る列車なら「◯◯始発」、JR常磐線・小田急線から来る列車は「直通」。
- 出力は毎回まるごと書き直す。並びを固定しているので、差分が出るのはダイヤが変わったときだけ。

取得は GitHub Actions（.github/workflows/timetable.yml）で週1回行う。

使い方:
    ODPT_CONSUMER_KEY=... python3 scripts/fetch_odpt.py
    ODPT_CONSUMER_KEY=... python3 scripts/fetch_odpt.py --dump raw/   # 生のJSONも保存する

標準ライブラリのみで動く。API仕様: https://developer.odpt.org/documents
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://api.odpt.org/api/v4/"
RAILWAY = "odpt.Railway:TokyoMetro.Chiyoda"
CHIYODA_STATION_PREFIX = "odpt.Station:TokyoMetro.Chiyoda."
REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
CSV_PATH = DATA_DIR / "trains.csv"
TIMETABLE_PREFIX = "odpt.TrainTimetable:TokyoMetro.Chiyoda."
STATIONS_CSV_PATH = DATA_DIR / "stations.csv"
THROUGH_LABEL = "直通"
RESPONSE_LIMIT = 1000
CALENDARS = ["odpt.Calendar:Weekday", "odpt.Calendar:SaturdayHoliday"]
DIRECTIONS = ["odpt.RailDirection:TokyoMetro.YoyogiUehara", "odpt.RailDirection:TokyoMetro.KitaAyase"]

# この後ろに駅の列（代々木上原→北綾瀬の駅順）が続く
FIELDS = [
    "calendar",
    "direction",
    "timetable_id",
    "train_number",
    "train_type",
    "origin",
    "origin_station",
    "destination_station",
    "issued",
]

STATION_FIELDS = ["order", "station", "station_name"]


def get(resource: str, params: dict, key: str) -> list[dict]:
    query = urllib.parse.urlencode({**params, "acl:consumerKey": key})
    req = urllib.request.Request(f"{API_BASE}{resource}?{query}", headers={"User-Agent": "chiyorush"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                return json.load(res)
        except urllib.error.HTTPError as e:
            # 鍵がURLに入るので、エラーメッセージには resource だけを出す
            if e.code < 500 or attempt == 2:
                raise SystemExit(f"{resource}: HTTP {e.code}") from None
        except urllib.error.URLError as e:
            if attempt == 2:
                raise SystemExit(f"{resource}: {e.reason}") from None
        time.sleep(10 * (attempt + 1))
    raise AssertionError("unreachable")


def tail(odpt_id: str) -> str:
    """'odpt.Station:TokyoMetro.Chiyoda.Otemachi' → 'Otemachi'、'odpt.Calendar:Weekday' → 'Weekday'。"""
    return odpt_id.rsplit(":", 1)[-1].rsplit(".", 1)[-1] if odpt_id else ""


def service_minutes(hhmm: str) -> int:
    """深夜0〜2時台は前日の続きとして24時以降に並べる。"""
    h, m = (int(x) for x in hhmm.split(":"))
    return (h + 24 if h < 3 else h) * 60 + m


def station_table(railway: dict, stations: list[dict]) -> list[dict]:
    names = {s["owl:sameAs"]: (s.get("odpt:stationTitle") or {}).get("ja") or s.get("dc:title", "") for s in stations}
    rows = []
    for o in railway.get("odpt:stationOrder", []):
        sid = o["odpt:station"]
        name = (o.get("odpt:stationTitle") or {}).get("ja") or names.get(sid, tail(sid))
        rows.append({"order": o["odpt:index"], "station": tail(sid), "station_name": name})
    return sorted(rows, key=lambda r: r["order"])


def origin_label(origin_ids: list[str], names: dict[str, str]) -> str:
    """千代田線内の駅から出る列車は「◯◯始発」、ほかの路線から来る列車は「直通」。

    常磐線から来る列車は originStation にJRの駅が入る。小田急線から来る列車は originStation が空で来る
    （2026-10-25の取得で、空の90本はすべて代々木上原から北綾瀬方面へ出る列車だった）ので、空も直通とみなす。
    """
    if not origin_ids:
        return THROUGH_LABEL
    sid = origin_ids[0]
    if sid.startswith(CHIYODA_STATION_PREFIX):
        return f"{names.get(tail(sid), tail(sid))}始発"
    return THROUGH_LABEL


def first_departure(row: dict, stations: list[str]) -> int:
    times = [service_minutes(row[s]) for s in stations if row.get(s)]
    return min(times) if times else 0


def to_rows(trains: list[dict], station_rows: list[dict]) -> list[dict]:
    names = {s["station"]: s["station_name"] for s in station_rows}
    stations = [s["station"] for s in station_rows]
    rows = []
    for t in trains:
        origins = t.get("odpt:originStation") or []
        dests = t.get("odpt:destinationStation") or []
        row = {
            "calendar": tail(t.get("odpt:calendar", "")),
            "direction": tail(t.get("odpt:railDirection", "")),
            "timetable_id": t.get("owl:sameAs", "").removeprefix(TIMETABLE_PREFIX),
            "train_number": t.get("odpt:trainNumber", ""),
            "train_type": tail(t.get("odpt:trainType", "")),
            "origin": origin_label(origins, names),
            "origin_station": origins[0] if origins else "",
            "destination_station": dests[0] if dests else "",
            "issued": t.get("dct:issued", ""),
            **{s: "" for s in stations},
        }
        stops = t.get("odpt:trainTimetableObject", [])
        for i, stop in enumerate(stops):
            st = tail(stop.get("odpt:departureStation") or stop.get("odpt:arrivalStation", ""))
            # 終着駅は到着だけで発車しないので入れない
            time_ = stop.get("odpt:departureTime") or (stop.get("odpt:arrivalTime") if i < len(stops) - 1 else "")
            if time_ and st in row:
                row[st] = time_
        if any(row[s] for s in stations):
            rows.append(row)
    rows.sort(key=lambda r: (r["calendar"], r["direction"], first_departure(r, stations), r["timetable_id"]))
    return rows


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", type=Path, help="生のJSONを保存するディレクトリ（要確認点を確かめるとき用）")
    args = ap.parse_args()

    key = os.environ.get("ODPT_CONSUMER_KEY", "")
    if not key:
        print("ODPT_CONSUMER_KEY が未設定", file=sys.stderr)
        return 1

    railways = get("odpt:Railway", {"owl:sameAs": RAILWAY}, key)
    stations = get("odpt:Station", {"odpt:railway": RAILWAY}, key)
    if not railways:
        print("取得結果が空: Railway", file=sys.stderr)
        return 1
    # 1回の応答は1000件で打ち切られる（2026-10-25に確認）ので、曜日区分×方向に分けて取る
    trains = []
    for cal in CALENDARS:
        for d in DIRECTIONS:
            part = get("odpt:TrainTimetable", {"odpt:railway": RAILWAY, "odpt:calendar": cal, "odpt:railDirection": d}, key)
            if not part or len(part) >= RESPONSE_LIMIT:
                print(f"{tail(cal)} / {tail(d)}: {len(part)}件。空か上限に達している", file=sys.stderr)
                return 1
            trains += part

    if args.dump:
        args.dump.mkdir(parents=True, exist_ok=True)
        dumps = {"railway": railways, "stations": stations, "train_timetable": trains}
        for name, data in dumps.items():
            (args.dump / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    station_rows = station_table(railways[0], stations)
    rows = to_rows(trains, station_rows)
    write_csv(STATIONS_CSV_PATH, STATION_FIELDS, station_rows)
    write_csv(CSV_PATH, FIELDS + [s["station"] for s in station_rows], rows)

    counts: dict[tuple[str, str], int] = {}
    for t in trains:
        k = (tail(t.get("odpt:calendar", "")), tail(t.get("odpt:railDirection", "")))
        counts[k] = counts.get(k, 0) + 1
    print(f"列車 {len(rows)}本")
    seen: dict[tuple[str, str, str], list[str]] = {}
    for r in rows:
        seen.setdefault((r["calendar"], r["direction"], r["train_number"]), []).append(r["timetable_id"])
    for k, ids in seen.items():
        if len(ids) > 1:
            print(f"  同じ列車番号の時刻表が複数: {' / '.join(k)}: {', '.join(ids)}")
    for (cal, d), n in sorted(counts.items()):
        print(f"  {cal} / {d}: {n}本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
