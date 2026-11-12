import importlib
import json
import pickle
import re
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import features as F

P = ROOT / "data" / "processed"
lg = importlib.import_module("17_log")
vf = importlib.import_module("18_verify")
api = importlib.import_module("19_api")


def load_js(name):
    t = (ROOT / "web" / "data" / f"{name}.js").read_text(encoding="utf-8")
    return json.loads(re.search(r"\]=([\[{].*[\]}]);\s*$", t, re.S).group(1))


def run(day, t_obs, gauges, thr=None):
    return {"issued": day, "generated": day + " 04:15", "t_obs": t_obs, "status": {"gauges": len(gauges), "cells_ok": 562},
            "thr_model": thr or {"1": 1.5, "2": 1.5, "3": 1.5}, "gauges": gauges, "risk": {day: {"alarm": 0, "warn": 0, "km_alarm": 0.0}},
            "weather": {}, "imgw": {"meteo": [], "hydro": [], "ok": True}, "overlap": {}}


def write_runs(d, runs):
    (d / "runs").mkdir(parents=True, exist_ok=True)
    for r in runs:
        json.dump(r, open(d / "runs" / f"{r['generated'].replace(' ', '_').replace(':', '')}.json", "w"))


class FeatureTests(unittest.TestCase):
    def test_heat_risk_monotonic_in_temperature(self):
        r = F.heat_risk(np.linspace(15, 40, 30), np.full(30, 20.0))
        self.assertTrue(np.all(np.diff(r) >= 0))

    def test_wind_risk_is_half_at_85_kmh(self):
        self.assertAlmostEqual(float(F.wind_risk(np.array([85.0]))[0]), 0.5, places=6)

    def test_river_risk_needs_exposure_and_grows_with_level(self):
        self.assertEqual(float(F.river_risk(np.array([3.0]), np.array([0.0]))[0]), 0.0)
        r = F.river_risk(np.linspace(0, 4, 20), np.ones(20))
        self.assertTrue(np.all(np.diff(r) >= 0))
        self.assertAlmostEqual(float(F.river_risk(np.array([2.0]), np.array([1.0]))[0]), 0.5, places=6)

    def test_combine_is_probabilistic_or(self):
        self.assertAlmostEqual(float(F.combine(np.array([0.3]), np.array([0.5]))[0]), 0.65, places=9)
        self.assertEqual(float(F.combine(np.array([0.0]), np.array([0.0]))[0]), 0.0)

    def test_freezing_rain_code_dominates_ice_proxy(self):
        args = (np.array([5.0]), np.array([0.5]), np.array([-1.0]), np.array([1.0]))
        frz = F.ice_risk(*args, wcode=np.array([67.0]))[0]
        none = F.ice_risk(*args, wcode=np.array([61.0]))[0]
        self.assertGreater(frz, 0.5)
        self.assertLessEqual(none, 0.15)

    def test_rail_temperature(self):
        self.assertAlmostEqual(float(F.rail_temp(np.array([30.0]), np.array([20.0]))[0]), 45.0)


class ModelTests(unittest.TestCase):
    def test_flood_model_is_monotone_in_rain(self):
        M = pickle.load(open(P / "flood_model.pkl", "rb"))
        ST = F.static_frame(json.load(open(P / "segments_static.json")))
        rows = ST.sample(120, random_state=1).reset_index(drop=True)
        prev = None
        for x in np.linspace(0, 300, 25):
            X = rows.copy()
            X["p3"], X["p1"], X["p7"] = x, x * 0.45, x + 6
            X["p_ante30"], X["p3_extreme"] = 80.0, x / 80.0
            pr = M["model"].predict_proba(X[M["features"]].astype(float))[:, 1]
            if prev is not None:
                self.assertTrue(np.all(pr >= prev - 1e-9), f"ryzyko spadło przy opadzie {x}")
            prev = pr


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.segs = load_js("segments")
        cls.live = load_js("live")
        cls.pw = load_js("powiaty")

    def test_segment_ids_unique_and_have_powiats(self):
        ids = [s["id"] for s in self.segs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(s.get("pw") for s in self.segs))
        codes = set(self.pw["c"])
        self.assertEqual(len(codes), 380)
        self.assertTrue(all(c in codes for s in self.segs for c in s["pw"]))

    def test_live_forecast_schema_and_ranges(self):
        n = len(self.segs)
        days = self.live["days"]
        self.assertEqual(days, sorted(days))
        self.assertEqual(len(days), 3)
        for d in days:
            r = self.live["risk"][d]
            for key in ("total", "flood", "heat", "wind", "ice", "p1", "p3", "gust", "trail", "q", "why"):
                self.assertEqual(len(r[key]), n, key)
            self.assertTrue(0 <= min(r["total"]) and max(r["total"]) <= 1)
            self.assertTrue(set(r["q"]) <= {0, 1, 2})
        self.assertIn("generated", self.live["meta"])

    def test_powiat_polygons_are_closed_enough(self):
        for g in self.pw["g"]:
            self.assertTrue(all(len(ring) >= 4 for ring in g))

    def test_events_validation_has_all_storms(self):
        ev = json.load(open(P / "events_validation.json", encoding="utf-8"))
        self.assertEqual(len(ev["wind_storms"]), 7)
        self.assertTrue(all(w["rank"] == 1 for w in ev["wind_storms"]))


class LogTests(unittest.TestCase):
    def test_history_forward_and_back_fill(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            write_runs(d, [run("2026-10-31", "2026-10-30", {"A": [0.2, None, None, None, None, None, None]}),
                           run("2026-11-01", "2026-10-31", {"A": [0.4, None, None, None, None, None, None]})])
            W = lg.history(d, "2026-11-01", {"A": 0.9}, days=4)
            self.assertEqual(list(W["A"].round(2)), [0.2, 0.2, 0.4, 0.9])

    def test_first_run_of_day_is_used(self):
        r1, r2 = run("2026-11-01", "2026-10-31", {}), run("2026-11-01", "2026-10-31", {})
        r2["generated"] = "2026-11-01 16:15"
        self.assertEqual(lg.first_per_day([r2, r1])["2026-11-01"]["generated"], "2026-11-01 04:15")

    def test_verification_matches_hand_computation(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            a = run("2026-11-01", "2026-10-31", {"A": [0.5, 0.6, 0.7, 0.8, 0.55, 0.65, 0.75], "B": [1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.3],
                                                  "C": [1.0, 1.8, 1.8, 1.8, 2.2, 2.2, 2.2]})
            b = run("2026-11-02", "2026-11-01", {"A": [0.57, 0, 0, 0, 0, 0, 0], "B": [1.15, 0, 0, 0, 0, 0, 0], "C": [2.5, 0, 0, 0, 0, 0, 0]})
            write_runs(d, [a, b])
            s = vf.river_stats(lg.first_per_day(lg.runs(d)), 1)
            self.assertEqual(s["n"], 3)
            self.assertAlmostEqual(s["mae_model"], round((0.02 + 0.05 + 0.3) / 3, 4), places=4)
            self.assertAlmostEqual(s["mae_persist"], round((0.07 + 0.15 + 1.5) / 3, 4), places=4)
            self.assertEqual(s["events"], 1)
            self.assertEqual(s["pod_system"], 1.0)
            self.assertEqual(s["pod_persist"], 0.0)
            self.assertIsNone(vf.river_stats(lg.first_per_day(lg.runs(d)), 3))

    def test_imgw_activity_window(self):
        w = {"f": "2026-11-12 22:00:00", "t": "2026-11-13 00:00:00"}
        self.assertTrue(lg.active(w, "2026-11-12"))
        self.assertFalse(lg.active(w, "2026-11-13"))
        self.assertFalse(lg.active(w, "2026-11-11"))


class ApiTests(unittest.TestCase):
    def test_static_api_files(self):
        lg_orig = api.lg.imgw_warnings
        api.lg.imgw_warnings = lambda: {"meteo": [], "hydro": [], "ok": True}
        try:
            with tempfile.TemporaryDirectory() as t:
                out = Path(t)
                api.build(out)
                a = json.load(open(out / "alarms.json", encoding="utf-8"))
                n = sum(len(x["segments"]) for x in a["dni"])
                g = json.load(open(out / "alarms.geojson", encoding="utf-8"))
                rows = (out / "alarms.csv").read_text(encoding="utf-8-sig").strip().splitlines()
                lines = json.load(open(out / "lines.json", encoding="utf-8"))
                self.assertEqual(len(g["features"]), n)
                self.assertEqual(len(rows) - 1, n)
                self.assertEqual(a["wersja"], "v1")
                self.assertGreater(len(lines["linie"]), 600)
                for f in g["features"][:5]:
                    lon, lat = f["geometry"]["coordinates"][0][0]
                    self.assertTrue(14 < lon < 25 and 48 < lat < 55)
        finally:
            api.lg.imgw_warnings = lg_orig


class DocTests(unittest.TestCase):
    def test_paper_has_no_unresolved_placeholders(self):
        html = (ROOT / "docs" / "praca.html").read_text(encoding="utf-8")
        self.assertNotIn("{{", html)

    def test_paper_page_limit(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("brak pypdf")
        n = len(PdfReader(str(ROOT / "docs" / "RailSentinel_praca_konkursowa.pdf")).pages)
        self.assertLessEqual(n, 15)

    def test_eunice_rank_in_text_matches_data(self):
        html = (ROOT / "docs" / "praca.html").read_text(encoding="utf-8")
        m = re.search(r"Eunice \(19\.02\.2022[^)]*\)</b> to (\d+)\. najgorszy", html)
        rank = int(json.load(open(P / "module_validation.json"))["wind_2022-02-19"]["rank"])
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), rank)


if __name__ == "__main__":
    unittest.main()
