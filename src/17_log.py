import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "RailSentinel/0.3 (student research prototype)"}
IMGW = "https://danepubliczne.imgw.pl/api/data/"
ALARM, WARN = 0.5, 0.3
HAZ = {"s_water": "w", "s_heat": "h", "s_wind": "v", "s_ice": "i"}


def logdir():
    d = os.environ.get("RS_LOG_DIR")
    return Path(d) if d else None


def runs(d):
    out = []
    if d and (d / "runs").exists():
        for f in sorted((d / "runs").glob("*.json")):
            try:
                out.append(json.load(open(f)))
            except ValueError:
                continue
    return out


def first_per_day(rs):
    by = {}
    for r in sorted(rs, key=lambda x: x["generated"]):
        by.setdefault(r["issued"], r)
    return by


def history(d, t, cur, days=10):
    idx = pd.date_range(pd.Timestamp(t) - pd.Timedelta(days=days - 1), pd.Timestamp(t))
    W = pd.DataFrame(np.nan, index=idx, columns=list(cur))
    for iss, r in first_per_day(runs(d)).items():
        day = pd.Timestamp(r["t_obs"])
        if day in W.index and day != pd.Timestamp(t):
            for code, g in r["gauges"].items():
                if code in W.columns and g[0] is not None:
                    W.at[day, code] = g[0]
    W.loc[pd.Timestamp(t)] = pd.Series(cur)
    return W.ffill().bfill()


def imgw_warnings():
    out = {"meteo": [], "hydro": [], "ok": False}
    try:
        m = requests.get(IMGW + "warningsmeteo", headers=UA, timeout=60).json()
        h = requests.get(IMGW + "warningshydro", headers=UA, timeout=60).json()
        out["meteo"] = [{"n": w["nazwa_zdarzenia"], "d": int(w["stopien"]), "f": w["obowiazuje_od"], "t": w["obowiazuje_do"],
                         "c": w.get("teryt", [])} for w in m]
        out["hydro"] = [{"n": w["zdarzenie"], "d": int(w["stopień"]), "f": w["data_od"], "t": w["data_do"],
                         "w": sorted({o["wojewodztwo"] for o in w.get("obszary", [])})} for w in h if int(w["stopień"]) >= 1]
        out["ok"] = True
    except Exception as e:
        print("ostrzeżenia IMGW niedostępne:", e)
    return out


def active(w, day):
    a, b = w["f"], w["t"]
    if a[:10] > day or b[:10] < day:
        return False
    return not (b[:10] == day and b[11:19] == "00:00:00")


def record(d, ctx):
    if not d:
        return None
    ST, df, days, fcst, cur, thr = ctx["ST"], ctx["df"], ctx["days"], ctx["fcst"], ctx["cur"], ctx["thr"]
    seg_pw = json.load(open(ROOT / "data" / "processed" / "seg_powiaty.json"))
    ids = ST["id"].tolist()
    line = dict(zip(ST["id"], ST["line"]))
    gauges = {}
    if fcst is not None:
        piv = fcst.pivot_table(index="code", columns="k", values="h_eff")
        pp = fcst.pivot_table(index="code", columns="k", values="h_pred")
        for code, h in cur.items():
            row = [h] + [piv.loc[code].get(k) if code in piv.index else None for k in (1, 2, 3)] + \
                  [pp.loc[code].get(k) if code in pp.index else None for k in (1, 2, 3)]
            gauges[code] = [None if (x is None or not np.isfinite(x)) else round(float(x), 3) for x in row]
    imgw = imgw_warnings()
    risk, weather, overlap = {}, {}, {}
    for day in days:
        ds = str(day)[:10]
        sub = df[df["date"] == pd.Timestamp(day)].set_index("id").reindex(ids)
        tot = sub["s_total"].fillna(0)
        dom = sub[list(HAZ)].fillna(0).idxmax(axis=1).map(HAZ)
        top = tot.nlargest(25)
        lines = {}
        for sid, x in tot[tot >= 0.15].items():
            lines[line[sid]] = max(lines.get(line[sid], 0), round(float(x), 3))
        risk[ds] = {"alarm": int((tot >= ALARM).sum()), "warn": int(((tot >= WARN) & (tot < ALARM)).sum()),
                    "km_alarm": round(float(sub.loc[tot >= ALARM, "length_km"].sum()), 1),
                    "top": [[sid, round(float(x), 3), dom[sid]] for sid, x in top.items() if x >= 0.15],
                    "lines": lines}
        w = {"p1_max": sub["p1"].max(), "p3_max": sub["p3"].max(), "gust_max": sub["gust"].max(),
             "trail_max": sub["t_rail"].max(), "tmin_min": sub["tmin"].min()}
        if "snowfall_sum" in sub:
            w["snow_max"] = sub["snowfall_sum"].max()
        weather[ds] = {k: (None if not np.isfinite(v) else round(float(v), 1)) for k, v in w.items()}
        if imgw["ok"]:
            warned = {c for x in imgw["meteo"] if active(x, ds) for c in x["c"]}
            inw = pd.Series([bool(set(seg_pw.get(i, [])) & warned) for i in ids], index=ids)
            overlap[ds] = {"powiats": len(warned), "segments": int(inw.sum()), "rs_in": int(((tot >= WARN) & inw).sum()),
                           "rs_out": int(((tot >= WARN) & ~inw).sum())}
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = {"issued": ctx["issued"], "generated": ctx["generated"], "t_obs": ctx["t_obs"], "status": ctx["status"],
           "thr_model": {str(k): v for k, v in thr.items()}, "gauges": gauges, "risk": risk, "weather": weather,
           "imgw": imgw, "overlap": overlap}
    (d / "runs").mkdir(parents=True, exist_ok=True)
    f = d / "runs" / f"{stamp}.json"
    json.dump(out, open(f, "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"dziennik: {f.name}, {round(f.stat().st_size / 1024)} KB, {len(gauges)} wodowskazów")
    return f
