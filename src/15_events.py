import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib

pr = importlib.import_module("05_predict")
from features import wind_risk

RAW, P = pr.RAW, pr.P
ARCH = "https://archive-api.open-meteo.com/v1/archive"
VARS = "precipitation_sum,temperature_2m_max,temperature_2m_min,wind_gusts_10m_max,shortwave_radiation_sum"
ALARM, WARN = 0.5, 0.3

FLOOD = [
    {"name": "Ulewy i fala na Odrze, maj 2010 – linia 273 Głogów–Krzepów zamknięta",
     "src": "Rzeczpospolita (rp.pl), relacja z powodzi 2010",
     "window": ("2010-04-10", "2010-06-15"), "test": ("2010-05-15", "2010-06-10"),
     "seg": ["L273_1033_321", "L273_1033_320", "L273_1033_322"]},
    {"name": "Ulewy na Śląsku, maj 2010 – osunięcie nasypu linii 149 (Zabrze – Leszczyny)",
     "src": "Transport Problems / PWr, artykuł o stateczności nasypu linii 149",
     "window": ("2010-04-10", "2010-06-15"), "test": ("2010-05-15", "2010-06-10"),
     "seg": ["L149_1002_372", "L149_1003_372", "L149_1003_373", "L149_1004_373", "L149_1004_374",
             "L149_1005_374", "L149_1005_375"]},
    {"name": "Powódź błyskawiczna, 7.08.2010 – Bogatynia, linia wzdłuż Miedzianki i Nysy Łużyckiej zniszczona",
     "src": "RMF24: zniszczona linia Görlitz–Zittau przez Bogatynię",
     "window": ("2010-07-01", "2010-08-12"), "test": ("2010-08-06", "2010-08-09"),
     "seg": ["L786_1018_297", "L786_1018_298", "L786_1019_297", "L290_1019_298"]},
]

WIND = [
    ("Kyrill", "2007-01-18"), ("Xaver", "2013-12-06"), ("Ksawery", "2017-10-05"), ("Grzegorz", "2017-10-29"),
    ("Friederike", "2018-01-18"), ("Sabina (Ciara)", "2020-02-10"), ("Eunice", "2022-02-19"),
]


def archive(tag, start, end, daily):
    f = RAW / "weather" / f"ev_{tag}.json"
    if f.exists():
        return json.load(open(f))
    raw = pr.fetch_cells(ARCH, {"start_date": start, "end_date": end, "timezone": "Europe/Warsaw", "daily": daily},
                         chunk=10, pause=8)
    raw = {c: x["daily"] for c, x in raw.items()}
    json.dump(raw, open(f, "w"))
    return raw


def hydro_2010():
    m09 = importlib.import_module("09_hydro")
    m09.RAW = RAW / "ev2010"
    df = m09.load()
    HM = pr.HM
    q50, q99 = pd.Series(HM["q50"]), pd.Series(HM["q99"])
    df = df[df.code.isin(q50.index)]
    df["h_idx"] = ((df.h - df.code.map(q50)) / (df.code.map(q99) - df.code.map(q50))).clip(-1, 4)
    wide = df.pivot_table(index="date", columns="code", values="h_idx", aggfunc="max")
    rows = []
    for sid, code in HM["segment_station"].items():
        if code in wide:
            x = wide[code]
            rows.append(pd.DataFrame({"id": sid, "date": x.index, "h3": x.rolling(3, min_periods=1).max().values}))
    h = pd.concat(rows, ignore_index=True)
    print(f"stany wód 2010: {wide.shape[1]} wodowskazów, {h.id.nunique()} odcinków")
    return h


def flood_tests():
    out, cache = [], {}
    H10 = hydro_2010()
    for ev in FLOOD:
        key = ev["window"]
        if key not in cache:
            raw = archive(f"{key[0]}_{key[1]}", key[0], key[1], VARS)
            cache[key] = pr.score(pr.frame_from_daily(raw, hydro=H10))
        df = cache[key]
        t = df[(df["date"] >= ev["test"][0]) & (df["date"] <= ev["test"][1])]
        mx = t.groupby("id")["s_water"].max()
        seg = [s for s in ev["seg"] if s in mx.index]
        best = float(mx[seg].max())
        rank = float((mx >= best).mean())
        alarm_share = float((mx >= ALARM).mean())
        day = t[t["id"].isin(seg)].sort_values("s_water").iloc[-1]["date"]
        r = {"name": ev["name"], "src": ev["src"], "risk": round(best, 3), "alarm": best >= ALARM, "warn": best >= WARN,
             "top_pct": round(rank * 100, 1), "net_alarm_pct": round(alarm_share * 100, 1), "day": str(day.date())}
        print(f"{'ALARM' if r['alarm'] else 'uwaga' if r['warn'] else 'BRAK '} {best:.2f}  top {r['top_pct']}% sieci  "
              f"(w alarmie {r['net_alarm_pct']}% sieci)  {ev['name']}")
        out.append(r)
    return out


def wind_archive(d, s, e):
    f = RAW / "weather" / f"ev_wind_{d}.json"
    if f.exists():
        return json.load(open(f))
    sub = [c for c in pr.CELLS if all(abs(float(v) * 2 - round(float(v) * 2)) < 1e-6 for v in c.split(","))]
    raw = {}
    for i in range(0, len(sub), 20):
        ch = sub[i:i + 20]
        q = {"start_date": s, "end_date": e, "timezone": "Europe/Warsaw", "daily": "wind_gusts_10m_max",
             "latitude": ",".join(c.split(",")[0] for c in ch), "longitude": ",".join(c.split(",")[1] for c in ch)}
        dd = pr.get(ARCH, q)
        dd = dd if isinstance(dd, list) else [dd]
        for c, x in zip(ch, dd):
            raw[c] = x["daily"]
        pr.time.sleep(4)
    S = np.array([[float(v) for v in c.split(",")] for c in sub])
    full = {}
    for c in pr.CELLS:
        la, lo = (float(v) for v in c.split(","))
        j = int(np.argmin((S[:, 0] - la) ** 2 + ((S[:, 1] - lo) * 0.63) ** 2))
        full[c] = raw[sub[j]]
    json.dump(full, open(f, "w"))
    print(f"  {d}: {len(sub)} węzłów siatki 0,5°")
    return full


def wind_tests():
    out = []
    seg_cells = pr.ST[["id", "cell"]]
    for name, d in WIND:
        d0 = pd.Timestamp(d)
        s, e = (d0 - pd.Timedelta(days=10)).strftime("%Y-%m-%d"), (d0 + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        raw = wind_archive(d, s, e)
        w = pd.concat([pd.DataFrame({"date": pd.to_datetime(x["time"]), "gust": x["wind_gusts_10m_max"], "cell": c})
                       for c, x in raw.items()])
        df = seg_cells.merge(w, on="cell")
        df["r"] = wind_risk(df["gust"].astype(float).values)
        share = df.groupby("date")["r"].apply(lambda x: float((x >= WARN).mean()))
        storm = share[(share.index >= d0 - pd.Timedelta(days=1)) & (share.index <= d0 + pd.Timedelta(days=1))]
        sd = storm.idxmax()
        rest = share.drop(storm.index)
        rank = int((share >= share[sd]).sum())
        g = df[df["date"] == sd].groupby("cell")["gust"].first()
        top = g.idxmax()
        r = {"name": name, "date": d, "storm_day": str(sd.date()), "share_warn": round(share[sd] * 100, 1),
             "rest_median": round(float(rest.median()) * 100, 1), "rest_max": round(float(rest.max()) * 100, 1),
             "rank": rank, "days": len(share), "max_gust": round(float(g.max())), "max_cell": top}
        print(f"{name:<15} {d}: dzień orkanu {r['share_warn']:5.1f}% sieci ≥ UWAGA, zwykłe dni mediana {r['rest_median']}% "
              f"(maks. {r['rest_max']}%), miejsce {rank}/{len(share)}, porywy do {r['max_gust']} km/h")
        out.append(r)
    return out


if __name__ == "__main__":
    f = P / "events_validation.json"
    res = json.load(open(f)) if f.exists() else {}
    if "flood" in sys.argv[1:] or len(sys.argv) == 1:
        res["flood_2010"] = flood_tests()
    if "wind" in sys.argv[1:] or len(sys.argv) == 1:
        res["wind_storms"] = wind_tests()
    json.dump(res, open(P / "events_validation.json", "w"), ensure_ascii=False, indent=1)
    print("zapisano events_validation.json")
