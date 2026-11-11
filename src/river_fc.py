import pickle
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
RF = pickle.load(open(P / "river_model.pkl", "rb"))
_m12 = import_module("12_river_forecast")


def forecast(wide_hist, rain_hist, rain_fut, t):
    t = pd.Timestamp(t)
    W = wide_hist.loc[:t].iloc[-10:].reindex(columns=sorted(set(wide_hist.columns) | set(RF["meta"])))
    R = rain_hist.reindex(W.index) if rain_hist is not None else None
    ups = {s: u for s, u in RF["ups"].items() if s in W.columns}
    fut = {k: pd.DataFrame([rain_fut.get(k, pd.Series(dtype=float))], index=[t]) for k in (1, 2, 3)}
    F = _m12.features(W, ups, R, rain_future=fut)
    F = F[F.date == t]
    out = []
    for k, m in RF["models"].items():
        cols = RF["cols"][k]
        X = F[cols]
        ok = F.h0.notna().values
        pred = np.full(len(F), np.nan)
        if ok.any():
            pred[ok] = F.h0.values[ok] + m.predict(X[ok])
        eff = np.fmax(F.h0.values, pred * 2.0 / RF["thr_model"][k])
        out.append(pd.DataFrame({"code": F.code.values, "k": k, "h_eff": eff, "h_pred": pred}))
    return pd.concat(out, ignore_index=True)


def segments_h3(fc, seg_station, t, h_past_seg=None):
    rows = []
    piv = fc.pivot_table(index="code", columns="k", values="h_eff")
    for sid, code in seg_station.items():
        if code not in piv.index:
            continue
        hk = piv.loc[code]
        prev = [h_past_seg.get(sid, np.nan)] if h_past_seg is not None else []
        series = prev + [hk.get(1, np.nan), hk.get(2, np.nan), hk.get(3, np.nan)]
        for k in (1, 2, 3):
            win = [x for x in series[max(0, k + len(prev) - 3):k + len(prev)] if np.isfinite(x)]
            rows.append({"id": sid, "date": pd.Timestamp(t) + pd.Timedelta(days=k),
                         "h3": max(win) if win else np.nan})
    return pd.DataFrame(rows, columns=["id", "date", "h3"])
