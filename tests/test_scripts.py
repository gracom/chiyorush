"""scripts/ のテスト。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_data  # noqa: E402
import build_site  # noqa: E402
import fetch_odpt as f  # noqa: E402

P = f.CHIYODA_STATION_PREFIX
STATIONS = [
    {"order": 15, "station": "Sendagi", "station_name": "千駄木"},
    {"order": 19, "station": "Ayase", "station_name": "綾瀬"},
    {"order": 20, "station": "KitaAyase", "station_name": "北綾瀬"},
]


def train(number: str, origin: str, stops: list[tuple[str, str]], calendar: str = "Weekday") -> dict:
    return {
        "owl:sameAs": f"{f.TIMETABLE_PREFIX}{number}.{calendar}",
        "odpt:calendar": f"odpt.Calendar:{calendar}",
        "odpt:railDirection": "odpt.RailDirection:TokyoMetro.YoyogiUehara",
        "odpt:trainNumber": number,
        "odpt:trainType": "odpt.TrainType:TokyoMetro.Local",
        "odpt:originStation": [origin],
        "odpt:destinationStation": [P + "YoyogiUehara"],
        "odpt:trainTimetableObject": [{"odpt:departureTime": t, "odpt:departureStation": P + s} for s, t in stops]
        + [{"odpt:arrivalTime": "09:00", "odpt:arrivalStation": P + "YoyogiUehara"}],
    }


class OriginLabelTest(unittest.TestCase):
    def test_chiyoda_origin(self):
        names = {"Ayase": "綾瀬"}
        self.assertEqual(f.origin_label([P + "Ayase"], names), "綾瀬始発")

    def test_through(self):
        self.assertEqual(f.origin_label(["odpt.Station:JR-East.Joban.Toride"], {}), "直通")

    def test_missing_is_odakyu_through(self):
        self.assertEqual(f.origin_label([], {}), "直通")


class ServiceMinutesTest(unittest.TestCase):
    def test_after_midnight_sorts_last(self):
        self.assertGreater(f.service_minutes("00:12"), f.service_minutes("23:58"))


class RowsTest(unittest.TestCase):
    def test_one_row_per_train_with_station_columns(self):
        rows = f.to_rows([train("A0701", P + "Ayase", [("Ayase", "07:04"), ("Sendagi", "07:10")])], STATIONS)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["Ayase"], r["Sendagi"], r["KitaAyase"]), ("07:04", "07:10", ""))
        self.assertEqual(r["timetable_id"], "A0701.Weekday")
        self.assertEqual(r["origin"], "綾瀬始発")

    def test_romancecar_intermediate_arrival_counts(self):
        t = train("B607E", "", [])
        t["odpt:trainTimetableObject"] = [
            {"odpt:departureStation": P + "YoyogiUehara"},
            {"odpt:arrivalTime": "07:37", "odpt:arrivalStation": P + "Sendagi"},
            {"odpt:arrivalTime": "07:53", "odpt:arrivalStation": P + "Ayase"},
        ]
        r = f.to_rows([t], STATIONS)[0]
        self.assertEqual((r["Sendagi"], r["Ayase"]), ("07:37", ""))

    def test_arrival_only_train_is_dropped(self):
        t = train("B509K", P + "Ayase", [])
        t["odpt:trainTimetableObject"] = [{"odpt:arrivalTime": "05:45", "odpt:arrivalStation": P + "Ayase"}]
        self.assertEqual(f.to_rows([t], STATIONS), [])

    def test_sorted_by_first_departure(self):
        rows = f.to_rows(
            [train("B", P + "Ayase", [("Sendagi", "08:00")]), train("A", P + "Ayase", [("Sendagi", "07:00")])], STATIONS
        )
        self.assertEqual([r["train_number"] for r in rows], ["A", "B"])


class FetchedDateTest(unittest.TestCase):
    NEW = {"issued": "2026-03-14", "timetable": {}}

    def test_first_time_is_today(self):
        self.assertEqual(build_data.with_fetched(self.NEW, None, "2026-10-26")["fetched"], "2026-10-26")

    def test_unchanged_keeps_previous_date(self):
        old = {**self.NEW, "fetched": "2026-10-19"}
        self.assertEqual(build_data.with_fetched(self.NEW, old, "2026-10-26")["fetched"], "2026-10-19")

    def test_changed_is_today(self):
        old = {"issued": "2025-03-15", "timetable": {}, "fetched": "2026-10-19"}
        self.assertEqual(build_data.with_fetched(self.NEW, old, "2026-10-26")["fetched"], "2026-10-26")


class EmbedTest(unittest.TestCase):
    def test_fills_empty_placeholder(self):
        page = '<p>x</p><script type="application/json" id="timetable-data"></script>'
        self.assertIn('id="timetable-data">{"a":1}</script>', build_site.embed(page, '{"a":1}'))


if __name__ == "__main__":
    unittest.main()
