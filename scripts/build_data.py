#!/usr/bin/env python3
"""data/trains.csv から、ページに埋め込む時刻表 data/timetable.json を作る。

- 駅・方面・曜日区分ごとに、[発車時刻（分）, 始発駅の番号, 終着駅の番号] を並べる。
  始発駅・終着駅の名前は origins・terminals に1回だけ持つ。
- 特急ロマンスカー（座席指定の有料特急）は載せない。
- fetched はODPTから取得した日（JST）。ODPTの開発者ガイドラインが取得日時の表示を求めている。
  中身が前回と同じなら前回の日付を引き継ぐ（毎週の取得のたびに差分を出さないように）。

使い方:
    python3 scripts/build_data.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
CSV_PATH = DATA_DIR / "trains.csv"
STATIONS_CSV_PATH = DATA_DIR / "stations.csv"
OUT_PATH = DATA_DIR / "timetable.json"
JST = timezone(timedelta(hours=9))
CHIYODA_STATION_PREFIX = "odpt.Station:TokyoMetro.Chiyoda."


def service_minutes(hhmm: str) -> int:
    """深夜0〜2時台は前日の続きとして24時以降に並べる。"""
    h, m = (int(x) for x in hhmm.split(":"))
    return (h + 24 if h < 3 else h) * 60 + m


def build(rows: list[dict], stations: list[dict]) -> dict:
    rows = [r for r in rows if r["train_type"] != "LimitedExpress"]
    names = {s["station"]: s["station_name"] for s in stations}
    order = {s["station"]: int(s["order"]) for s in stations}

    origins: list[str] = []
    origin_station: dict[str, str] = {}
    for r in rows:
        if r["origin"] not in origins:
            origins.append(r["origin"])
        if r["origin"] != "直通":
            origin_station[r["origin"]] = r["origin_station"].rsplit(".", 1)[-1]
    # 始発駅は駅順に並べ、直通は最後に置く
    origins.sort(key=lambda o: (o == "直通", order.get(origin_station.get(o, ""), 0)))
    index = {o: i for i, o in enumerate(origins)}

    # 終着駅は千代田線内なら駅（◯◯行）、JR常磐線・小田急線へ抜ける列車は直通にまとめる
    def terminal(r: dict) -> str | None:
        d = r["destination_station"]
        return d[len(CHIYODA_STATION_PREFIX):] if d.startswith(CHIYODA_STATION_PREFIX) else None

    terminals = sorted({terminal(r) for r in rows}, key=lambda t: (t is None, order.get(t, 0)))
    t_index = {t: i for i, t in enumerate(terminals)}

    timetable: dict[str, dict[str, dict[str, list]]] = {}
    for r in rows:
        by_station = timetable.setdefault(r["calendar"], {}).setdefault(r["direction"], {})
        for s in stations:
            t = r.get(s["station"])
            if t:
                by_station.setdefault(s["station"], []).append(
                    [service_minutes(t), index[r["origin"]], t_index[terminal(r)]]
                )
    for by_dir in timetable.values():
        for by_station in by_dir.values():
            for deps in by_station.values():
                deps.sort()

    return {
        "issued": max((r["issued"] for r in rows if r["issued"]), default=""),
        "stations": [
            {"id": s["station"], "name": s["station_name"], "order": int(s["order"])} for s in stations
        ],
        "origins": [{"label": o, "station": origin_station.get(o)} for o in origins],
        "terminals": [
            {"label": f"{names[t]}行" if t else "直通", "station": t} for t in terminals
        ],
        "timetable": timetable,
    }


def with_fetched(new: dict, old: dict | None, today: str) -> dict:
    """取得日を付ける。中身が前回と同じなら、前回の取得日を引き継ぐ。"""
    same = old is not None and {k: v for k, v in old.items() if k != "fetched"} == new
    return {**new, "fetched": (old.get("fetched") or today) if same else today}


def main() -> int:
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    with STATIONS_CSV_PATH.open(encoding="utf-8", newline="") as f:
        stations = list(csv.DictReader(f))
    old = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else None
    today = datetime.now(JST).strftime("%Y-%m-%d")
    data = with_fetched(build(rows, stations), old, today)
    OUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT_PATH.relative_to(REPO)} ({OUT_PATH.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
