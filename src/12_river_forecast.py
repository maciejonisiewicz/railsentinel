import json
import pickle
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
hydro = import_module("09_hydro")
H = (1, 2, 3)


def hav(a, b, c, d):
    p1, p2 = np.radians(a), np.radians(c)
    x = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(d - b) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(x))


def station_table():
    df = hydro.load()
    api = {x["id_stacji"]: x for x in json.load(open(RAW / "pl" / "imgw_hydro_api.json"))}
    meta = {}
    for code, g in df.groupby("code"):
        a = api.get(code)
        if not a or not a.get("lat"):
            continue
        tr = g[g.date.dt.year.between(2021, 2024)].h
        if len(tr) < 300:
            continue
        q50, q99 = float(tr.median()), float(tr.quantile(0.99))
        if q99 - q50 < 20:
            continue
        meta[code] = {"lat": float(a["lat"]), "lon": float(a["lon"]), "name": a["stacja"],
                      "river": hydro.river_key(a["rzeka"] or ""), "q50": q50, "q99": q99,
                      "alarm": float(a["stan_alarmowy"]) if a.get("stan_alarmowy") else None}
    df = df[df.code.isin(meta)].copy()
    df["h_idx"] = ((df.h - df.code.map(lambda c: meta[c]["q50"])) /
                   (df.code.map(lambda c: meta[c]["q99"]) - df.code.map(lambda c: meta[c]["q50"]))).clip(-1.5, 6)
    wide = df.pivot_table(index="date", columns="code", values="h_idx", aggfunc="mean").sort_index()
    wide = wide.reindex(pd.date_range(wide.index.min(), wide.index.max()))
    return wide, meta


def pick_upstream(wide, meta):
    tr = wide[(wide.index.year >= 2021) & (wide.index.year <= 2023)]
    d = tr.diff()
    ups = {}
    by_river = {}
    for c, m in meta.items():
        by_river.setdefault(m["river"], []).append(c)
    for s, m in meta.items():
        cands = []
        for c in by_river.get(m["river"], []):
            if c == s or hav(m["lat"], m["lon"], meta[c]["lat"], meta[c]["lon"]) > 200:
                continue
            best = (0, 0)
            for L in (1, 2):
                r = d[s].corr(d[c].shift(L))
                if np.isfinite(r) and r > best[0]:
                    best = (r, L)
            if best[0] > 0.25:
                cands.append((best[0], c, best[1]))
        ups[s] = [(c, L, round(r, 3)) for r, c, L in sorted(cands, reverse=True)[:3]]
    return ups


def station_rain():
    f = P / "station_rain.pkl"
    return pickle.load(open(f, "rb")) if f.exists() else None


def features(wide, ups, rain, t_idx=None, rain_future=None):
    rows = []
    W = wide
    for s, up in ups.items():
        h = W[s]
        f = pd.DataFrame({"h0": h, "h1": h.shift(1), "h2": h.shift(2)})
        f["dh1"] = f.h0 - f.h1
        f["dh2"] = f.h0 - f.h2
        f["hmax7"] = h.rolling(7, min_periods=1).max()
        for j in range(3):
            if j < len(up):
                c, L, r = up[j]
                f[f"u{j}"] = W[c]
                f[f"du{j}"] = W[c] - W[c].shift(1)
                f[f"lag{j}"] = L
            else:
                f[f"u{j}"] = np.nan
                f[f"du{j}"] = np.nan
                f[f"lag{j}"] = np.nan
        if rain is not None and s in rain:
            r = rain[s].reindex(W.index)
            f["r_past3"] = r.rolling(3, min_periods=1).sum()
            for k in H:
                if rain_future is not None:
                    f[f"r_fut{k}"] = rain_future[k][s].reindex(W.index) if s in rain_future[k] else np.nan
                else:
                    f[f"r_fut{k}"] = sum(r.shift(-i) for i in range(1, k + 1))
        else:
            f["r_past3"] = np.nan
            for k in H:
                f[f"r_fut{k}"] = np.nan
        f["month"] = W.index.month
        f["code"] = s
        f["date"] = W.index
        for k in H:
            f[f"y{k}"] = h.shift(-k) - h
        rows.append(f)
    return pd.concat(rows, ignore_index=True)


def feat_cols(k):
    return (["h0", "h1", "h2", "dh1", "dh2", "hmax7"] +
            [f"{a}{j}" for j in range(3) for a in ("u", "du", "lag")] + ["r_past3", f"r_fut{k}", "month"])


def system_scores(h0, true, pred, thr_m, thr=2.0):
    m = np.isfinite(true) & np.isfinite(pred) & np.isfinite(h0)
    h0, t, p = h0[m], true[m], pred[m]
    ev = t >= thr
    al_p = h0 >= thr
    al_s = al_p | (p >= thr_m)
    def pfc(al):
        hit = (ev & al).sum()
        return (float(hit / max(ev.sum(), 1)), float((al & ~ev).sum() / max(al.sum(), 1)),
                float(hit / max((ev | al).sum(), 1)))
    on = (h0 < thr) & ev
    on_al = (h0 < thr) & (p >= thr_m)
    return {"events": int(ev.sum()), "onset_events": int(on.sum()),
            "onset_pod_model": float((on & on_al).sum() / max(on.sum(), 1)),
            "onset_far_model": float((on_al & ~ev).sum() / max(on_al.sum(), 1)),
            "pod_persist": pfc(al_p)[0], "far_persist": pfc(al_p)[1], "csi_persist": pfc(al_p)[2],
            "pod_system": pfc(al_s)[0], "far_system": pfc(al_s)[1], "csi_system": pfc(al_s)[2]}


def scores(true, pred, base, thr=2.0):
    m = np.isfinite(true) & np.isfinite(pred) & np.isfinite(base)
    t, p, b = true[m], pred[m], base[m]
    hi = t >= 1.0

    def det(x):
        ev, al = t >= thr, x >= thr
        pod = (ev & al).sum() / max(ev.sum(), 1)
        far = (al & ~ev).sum() / max(al.sum(), 1)
        csi = (ev & al).sum() / max((ev | al).sum(), 1)
        return float(pod), float(far), float(csi)
    return {"n": int(m.sum()), "mae_model": float(np.abs(t - p).mean()), "mae_persist": float(np.abs(t - b).mean()),
            "mae_high_model": float(np.abs(t[hi] - p[hi]).mean()), "mae_high_persist": float(np.abs(t[hi] - b[hi]).mean()),
            "pod_model": det(p)[0], "far_model": det(p)[1], "csi_model": det(p)[2],
            "pod_persist": det(b)[0], "far_persist": det(b)[1], "csi_persist": det(b)[2]}


def main():
    wide, meta = station_table()
    ups = pick_upstream(wide, meta)
    rain = station_rain()
    F = features(wide, ups, rain)
    F = F[F.date.dt.month.between(3, 10)]
    yr = F.date.dt.year
    used_cols, thr_model = {}, {}
    models, metrics = {}, {"stations": len(meta), "with_upstream": int(sum(1 for u in ups.values() if u)),
                           "with_rain": int(F.groupby("code").r_past3.apply(lambda s: s.notna().any()).sum())}
    for k in H:
        tr = F[yr.between(2021, 2023)].dropna(subset=[f"y{k}", "h0"])
        cols = [c for c in feat_cols(k) if tr[c].notna().any()]
        used_cols[k] = cols
        m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_depth=6, min_samples_leaf=50,
                                          l2_regularization=1.0, random_state=0)
        m.fit(tr[cols], tr[f"y{k}"])
        models[k] = m
        ptr = tr.h0.values + m.predict(tr[cols])
        ttr = tr.h0.values + tr[f"y{k}"].values
        best = max(((system_scores(tr.h0.values, ttr, ptr, th)["csi_system"], th)
                    for th in np.arange(1.0, 2.31, 0.1)))
        thr_model[k] = float(round(best[1], 2))
        for name, sel in (("test2024", yr == 2024),
                          ("test2024_flood", F.date.between("2024-09-08", "2024-09-25")),
                          ("test1997_flood", F.date.between("1997-07-01", "1997-07-25"))):
            te = F[sel].dropna(subset=[f"y{k}", "h0"])
            if not len(te):
                continue
            pred = te.h0.values + m.predict(te[cols])
            true = te.h0.values + te[f"y{k}"].values
            metrics[f"{name}_k{k}"] = scores(true, pred, te.h0.values)
            metrics[f"{name}_k{k}"].update(system_scores(te.h0.values, true, pred, thr_model[k]))
        for n in ("test2024_flood", "test1997_flood"):
            x = metrics[f"{n}_k{k}"]
            print(f"k={k} {n}: MAE {x['mae_model']:.3f} vs {x['mae_persist']:.3f} | wysokie {x['mae_high_model']:.3f} vs {x['mae_high_persist']:.3f} | "
                  f"onset POD {x['onset_pod_model']:.2f} FAR {x['onset_far_model']:.2f} ({x['onset_events']}) | "
                  f"CSI system {x['csi_system']:.3f} vs persyst {x['csi_persist']:.3f} | POD {x['pod_system']:.2f} vs {x['pod_persist']:.2f} | thr {thr_model[k]}", flush=True)
    pickle.dump(wide, open(P / "station_hidx.pkl", "wb"))
    pickle.dump({"models": models, "ups": ups, "meta": meta, "cols": used_cols, "thr_model": thr_model},
                open(P / "river_model.pkl", "wb"))
    metrics["thr_model"] = thr_model
    json.dump(metrics, open(P / "river_metrics.json", "w"), indent=1)
    json.dump({"meta": meta, "ups": ups}, open(P / "station_meta.json", "w"), ensure_ascii=False)
    print("stacje:", metrics["stations"], "ze zwiastunami:", metrics["with_upstream"], "z opadem:", metrics["with_rain"])


if __name__ == "__main__":
    main()
