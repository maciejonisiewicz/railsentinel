import importlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

lg = importlib.import_module("17_log")
THR = 2.0


def pairs(by, k):
    obs, pred, pers, eff, thr, n_days = [], [], [], [], [], 0
    for day, a in by.items():
        later = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=k)).strftime("%Y-%m-%d")
        b = by.get(later)
        if not b:
            continue
        n_days += 1
        for code, ga in a["gauges"].items():
            gb = b["gauges"].get(code)
            if not gb or gb[0] is None or ga[0] is None or ga[3 + k] is None or ga[k] is None:
                continue
            obs.append(gb[0]); pred.append(ga[3 + k]); pers.append(ga[0]); eff.append(ga[k])
            thr.append(a["thr_model"].get(str(k), 1.5))
    return np.array(obs), np.array(pred), np.array(pers), np.array(eff), np.array(thr), n_days


def river_stats(by, k):
    obs, pred, pers, eff, thr, n_days = pairs(by, k)
    if not len(obs):
        return None
    mm, mp = float(np.abs(obs - pred).mean()), float(np.abs(obs - pers).mean())
    ev = obs >= THR
    al_p = pers >= THR
    al_s = al_p | (pred >= thr)
    def pod(al):
        return float((ev & al).sum() / ev.sum()) if ev.sum() else None
    def far(al):
        return float((al & ~ev).sum() / al.sum()) if al.sum() else None
    return {"n": int(len(obs)), "days": n_days, "mae_model": round(mm, 4), "mae_persist": round(mp, 4),
            "gain_pct": round((1 - mm / mp) * 100, 1) if mp > 0 else None, "events": int(ev.sum()),
            "pod_system": pod(al_s), "pod_persist": pod(al_p), "far_system": far(al_s), "far_persist": far(al_p)}


def main(d, out):
    by = lg.first_per_day(lg.runs(d))
    allruns = lg.runs(d)
    days = sorted(by)
    daily = []
    for day in days:
        r = by[day]
        k = r["risk"].get(day) or next(iter(r["risk"].values()))
        o = r["overlap"].get(day, {})
        w = r["weather"].get(day, {})
        daily.append({"date": day, "generated": r["generated"], "alarm": k["alarm"], "warn": k["warn"], "km_alarm": k["km_alarm"],
                      "imgw_powiats": o.get("powiats"), "imgw_segments": o.get("segments"), "rs_in": o.get("rs_in"),
                      "rs_out": o.get("rs_out"), "p1_max": w.get("p1_max"), "gust_max": w.get("gust_max"),
                      "tmin_min": w.get("tmin_min"), "snow_max": w.get("snow_max"), "gauges": r["status"].get("gauges"),
                      "cells_ok": r["status"].get("cells_ok")})
    per_day = {}
    for r in allruns:
        per_day[r["issued"]] = per_day.get(r["issued"], 0) + 1
    res = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "runs": len(allruns), "days": len(days),
           "first": days[0] if days else None, "last": allruns[-1]["generated"] if allruns else None,
           "runs_per_day": per_day, "river": {str(k): river_stats(by, k) for k in (1, 2, 3)}, "daily": daily}
    ins = sum(x["rs_in"] or 0 for x in daily)
    outs = sum(x["rs_out"] or 0 for x in daily)
    res["imgw_overlap"] = {"rs_in": ins, "rs_out": outs}
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"status: {len(allruns)} przebiegów, {len(days)} dni, para k=1: {res['river']['1']}")
    return res


if __name__ == "__main__":
    d = lg.logdir()
    if not d:
        sys.exit("Ustaw RS_LOG_DIR")
    main(d, Path(sys.argv[1]) if len(sys.argv) > 1 else d / "status.json")
