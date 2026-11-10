"""Krok 4: zbiór uczący + model ML ryzyka podmycia/zalania odcinka + walidacja.

Model: HistGradientBoostingClassifier z ograniczeniami monotoniczności (physics-informed ML).
Walidacja:
  (a) GroupKFold po numerze linii na latach 2021-2024 (etykiety: powódź 09.2024),
  (b) NIEZALEŻNY test czasowy: powódź 07.1997 (inne zdarzenie, inne etykiety, model jej nie widział),
  (c) porównanie zestawów cech na teście 1997 (wybór cech nie był na nim dostrajany).
Źródła opadu: "era5" (reanaliza 0.25°; zgodna z prognozami - model operacyjny)
              "gauge" (posterunki IMGW, IDW ~ kilka km, braki uzupełnione ERA5 - model obserwacyjny)
Baseline: reguła progowa "opad 3-dniowy > X mm".
"""
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from features import (DYNAMIC, FLOOD_FEATURES, HYDRO, MONOTONIC, cell_daily, combine, dist_to_polyline_km,
                      river_risk, static_frame)

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
W = ROOT / "data" / "raw" / "weather"
TRAIN_YEARS = [y for y in [2021, 2022, 2023, 2024] if (W / f"{y}.json").exists()]
FULL_STATIC = ["elev", "tpi", "relief", "river_dist_km", "river_size", "bridge_share", "embankment_share",
               "cutting_share", "tunnel_share", "electrified", "maxspeed", "main_line"]


def label_segments(st, fname):
    lab = json.load(open(ROOT / "data" / fname))
    pos = {}
    for c in lab["corridors"]:
        buf = c.get("buffer_km", lab["buffer_km"])
        for _, r in st.iterrows():
            if c.get("line") and str(r.line) != c["line"]:
                continue
            if dist_to_polyline_km(r.lat, r.lon, c["points"]) <= buf:
                pos[r.id] = c["name"]
    return pos, pd.to_datetime(lab["event_days"])


def rolling(df, key):
    df = df.sort_values([key, "date"])
    g = df.groupby(key)["p1"]
    df["p3"] = g.transform(lambda s: s.rolling(3, min_periods=1).sum())
    df["p7"] = g.transform(lambda s: s.rolling(7, min_periods=1).sum())
    df["p_ante30"] = g.transform(lambda s: s.shift(3).rolling(27, min_periods=1).sum())
    return df


def frame(years, source, st, clim=None):
    """Odcinko-dni z cechami. source='era5' lub 'gauge'."""
    w = pd.concat([cell_daily(json.load(open(W / f"{y}.json"))) for y in years], ignore_index=True)
    df = st.merge(w.drop(columns=["p3", "p7", "p_ante30"]), on="cell")
    if source == "gauge":
        g = pickle.load(open(P / "gauge_daily.pkl", "rb"))
        df = df.merge(g[["id", "date", "p1g"]], on=["id", "date"], how="left")
        df["p1_era5"] = df["p1"]
        df["p1"] = df["p1g"].fillna(df["p1"])
    df = rolling(df, "id")
    h = pickle.load(open(P / "hydro_daily.pkl", "rb"))
    df = df.merge(h, on=["id", "date"], how="left")
    key = "cell" if source == "era5" else "id"
    if clim is None:
        clim = df.groupby(key)["p3"].quantile(0.99).to_dict()
    df["p3_extreme"] = df["p3"] / df[key].map(clim).fillna(df["p3"].quantile(0.99))
    return df, clim


def make_model(feats):
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_depth=4, min_samples_leaf=40, l2_regularization=1.0,
        monotonic_cst=[MONOTONIC.get(f, 0) for f in feats], class_weight="balanced", random_state=42)


def evaluate(df, feats, pos):
    """GroupKFold po liniach + metryki vs reguła opadowa."""
    X, y, groups = df[feats], df["y"].values, df["line"].values
    oof = np.zeros(len(df))
    fold_models, line_fold = [], {}
    for k, (tr, te) in enumerate(GroupKFold(n_splits=5).split(X, y, groups)):
        m = make_model(feats).fit(X.iloc[tr], y[tr])
        oof[te] = m.predict_proba(X.iloc[te])[:, 1]
        fold_models.append(m)
        for ln in np.unique(groups[te]):
            line_fold[str(ln)] = k
    base = df["p3"].values
    thr = float(np.quantile(oof[y == 1], 0.20))
    thr_b = float(np.quantile(base[y == 1], 0.20))
    ev = df["date"].isin(pd.to_datetime(["2024-09-14", "2024-09-15", "2024-09-16"])).values
    wet = ev & (base > 40)
    other = df["date"].isin(pd.to_datetime(["2024-09-14", "2024-09-15"])).values & (y == 0)
    normal = df["date"].dt.year.values < 2024
    res = {
        "rows": int(len(df)), "positives": int(y.sum()), "positive_segments": len(pos),
        "roc_auc_model": float(roc_auc_score(y, oof)), "pr_auc_model": float(average_precision_score(y, oof)),
        "roc_auc_baseline_p3": float(roc_auc_score(y, base)),
        "pr_auc_baseline_p3": float(average_precision_score(y, base)),
        "alarm_threshold": thr, "baseline_threshold_mm": thr_b,
        "event_auc_model": float(roc_auc_score(y[wet], oof[wet])),
        "event_auc_baseline": float(roc_auc_score(y[wet], base[wet])),
        "other_alarm_pct_model": float((oof[other] >= thr).mean() * 100),
        "other_alarm_pct_baseline": float((base[other] >= thr_b).mean() * 100),
        "precision_event_days_model": float(y[ev & (oof >= thr)].mean()),
        "precision_event_days_baseline": float(y[ev & (base >= thr_b)].mean()),
        "false_alarms_per_1000_segment_days_2021_2023_model": float((oof[normal] >= thr).mean() * 1000),
        "false_alarms_per_1000_segment_days_2021_2023_baseline": float((base[normal] >= thr_b).mean() * 1000),
    }
    res['_oof'] = oof
    return res, fold_models, line_fold, thr, thr_b


def test_1997(model, feats, thr, thr_b, source, st, clim):
    """Niezależny test: maks. ryzyko odcinka w oknie powodzi 1997 vs etykiety 1997."""
    df, _ = frame([1997], source, st, clim)
    df = df[df["date"].dt.month == 7]
    pos, days = label_segments(st, "labels_flood_1997.json")
    ev = df[df["date"].isin(days)].copy()
    ev["r"] = model.predict_proba(ev[feats])[:, 1]
    agg = ev.groupby("id").agg(r=("r", "max"), p3=("p3", "max"))
    yy = agg.index.isin(list(pos)).astype(int)
    return {
        "test1997_positive_segments": int(yy.sum()),
        "test1997_auc_model": float(roc_auc_score(yy, agg["r"])),
        "test1997_auc_baseline": float(roc_auc_score(yy, agg["p3"])),
        "test1997_detected_model": int((agg["r"][yy == 1] >= thr).sum()),
        "test1997_detected_baseline": int((agg["p3"][yy == 1] >= thr_b).sum()),
        "test1997_network_alarm_pct_model": float((agg["r"] >= thr).mean() * 100),
        "test1997_network_alarm_pct_baseline": float((agg["p3"] >= thr_b).mean() * 100),
        "test1997_positive_rank_pct": [float((agg["r"] > v).mean() * 100) for v in agg["r"][yy == 1]],
    }


def flood_scale(r, thr):
    return 1 / (1 + np.exp(-(np.log(np.asarray(r) + 1e-9) - np.log(thr)) * 1.6))


def system_eval(df, oof, thr, pos, final, feats, source, st, clim):
    """Cały system: moduł A (ML, ulewa) + moduł B (fala wezbraniowa). Alarm gdy P >= 0.5."""
    hm = json.load(open(P / "hydro_mapping.json"))
    exp = df["id"].map(hm["exposure"]).astype(float)
    sA = flood_scale(oof, thr)
    sB = river_risk(df["h3"].values, exp.values)
    out = {}
    ev = df["date"].isin(pd.to_datetime(["2024-09-14", "2024-09-15", "2024-09-16"])).values
    pk = df["date"].isin(pd.to_datetime(["2024-09-14", "2024-09-15"])).values
    normal = (df["date"].dt.year.values < 2024)
    for name, s in (("ml", sA), ("system", combine(sA, sB))):
        a = s >= 0.5
        det = df[ev & a]["id"].unique()
        mx = pd.Series(s[pk]).groupby(df["id"].values[pk]).max()
        out[f"sys2024_detected_{name}"] = int(len(set(det) & set(pos)))
        out[f"sys2024_other_alarm_pct_{name}"] = float((mx[~mx.index.isin(list(pos))] >= 0.5).mean() * 100)
        out[f"sys_normal_alarms_per_1000_{name}"] = float(a[normal].mean() * 1000)
    # test 1997
    t, _ = frame([1997], source, st, clim)
    t = t[t["date"].dt.month == 7]
    pos97, days97 = label_segments(st, "labels_flood_1997.json")
    t = t[t["date"].isin(days97)].copy()
    sA97 = flood_scale(final.predict_proba(t[feats])[:, 1], thr)
    sB97 = river_risk(t["h3"].values, t["id"].map(hm["exposure"]).astype(float).values)
    lab = json.load(open(ROOT / "data" / "labels_flood_1997.json"))
    for name, s in (("ml", sA97), ("system", combine(sA97, sB97))):
        mx = pd.Series(s).groupby(t["id"].values).max()
        out[f"test1997_seg_detected_{name}"] = int((mx.reindex(list(pos97)).fillna(0) >= 0.5).sum())
        out[f"test1997_network_alarm_pct_{name}"] = float((mx >= 0.5).mean() * 100)
        sites = 0
        for c in lab["corridors"]:
            ids = [i for i, n in pos97.items() if n == c["name"]]
            sites += int((mx.reindex(ids).fillna(0) >= 0.5).any())
        out[f"test1997_sites_detected_{name}"] = sites
    out["test1997_sites"] = len(lab["corridors"])
    out["test1997_segments"] = len(pos97)
    return out


# Obszar etykiet: komunikaty o zniszczeniach (2024, 1997) zebrano dla Dolnego Śląska i Opolszczyzny.
# Odcinki spoza tego obszaru nie mają zweryfikowanych etykiet, więc nie biorą udziału w treningu/walidacji
# (inaczej trafiłyby do zbioru jako "niezniszczone" bez sprawdzenia). Prognoza działa dla całej Polski.
LABEL_BBOX = (50.0, 51.9, 14.8, 18.7)


def main():
    st = static_frame(json.load(open(P / "segments_static.json")))
    a, b, c, d = LABEL_BBOX
    st = st[st.lat.between(a, b) & st.lon.between(c, d)].reset_index(drop=True)
    print("odcinki w obszarze etykiet:", len(st))
    pos, days = label_segments(st, "labels_flood_2024.json")
    report = {}
    keep = {}
    for source in ("era5", "gauge"):
        df, clim = frame(TRAIN_YEARS, source, st)
        df = df[df["date"].dt.month >= 4].reset_index(drop=True)
        df["y"] = (df["id"].isin(pos) & df["date"].isin(days)).astype(int)
        variants = (("fizyczne", FLOOD_FEATURES), ("wszystkie", DYNAMIC + FULL_STATIC),
                    ("fizyczne+hydroML", FLOOD_FEATURES + HYDRO)) if source == "era5" else (("fizyczne", FLOOD_FEATURES),)
        for fs_name, feats in variants:
            res, folds, line_fold, thr, thr_b = evaluate(df, feats, pos)
            oof = res.pop("_oof")
            final = make_model(feats).fit(df[feats], df["y"].values)
            res.update(test_1997(final, feats, thr, thr_b, source, st, clim))
            if fs_name == "fizyczne":
                res.update(system_eval(df, oof, thr, pos, final, feats, source, st, clim))
                print("   SYSTEM:", {k: round(v, 2) for k, v in res.items() if k.startswith(("sys", "test1997_s", "test1997_n"))})
            report[f"{source}/{fs_name}"] = res
            print(f"{source:5s} {fs_name:9s} PR={res['pr_auc_model']:.3f} (reg {res['pr_auc_baseline_p3']:.3f}) "
                  f"evAUC={res['event_auc_model']:.3f} (reg {res['event_auc_baseline']:.3f}) "
                  f"inne%={res['other_alarm_pct_model']:.1f} (reg {res['other_alarm_pct_baseline']:.1f}) | "
                  f"1997 AUC={res['test1997_auc_model']:.3f} (reg {res['test1997_auc_baseline']:.3f}) "
                  f"wykryte {res['test1997_detected_model']}/{res['test1997_positive_segments']} "
                  f"(reg {res['test1997_detected_baseline']}) sieć%={res['test1997_network_alarm_pct_model']:.0f}",
                  flush=True)
            keep[(source, fs_name)] = (final, feats, thr, clim, folds, line_fold, df)

    # model operacyjny (prognozy): ERA5 + cechy fizyczne; obserwacyjny: posterunki IMGW
    for source, fname in (("era5", "flood_model.pkl"), ("gauge", "flood_model_gauge.pkl")):
        final, feats, thr, clim, folds, line_fold, df = keep[(source, "fizyczne")]
        pickle.dump({"model": final, "features": feats, "threshold": thr, "clim_q99": clim,
                     "fold_models": folds, "line_fold": line_fold, "source": source}, open(P / fname, "wb"))

    from sklearn.inspection import permutation_importance
    final, feats, thr, clim, folds, line_fold, df = keep[("era5", "fizyczne")]
    y = df["y"].values
    rng = np.random.default_rng(0)
    sel = np.unique(np.concatenate([np.where((y == 1) | (df["p3"].values > 30))[0],
                                    rng.choice(len(df), 20000, replace=False)]))
    pi = permutation_importance(final, df[feats].iloc[sel], y[sel], scoring="average_precision",
                                n_repeats=5, random_state=0, n_jobs=-1)
    json.dump({f: float(v) for f, v in zip(feats, pi.importances_mean)}, open(P / "importance.json", "w"), indent=1)

    metrics = dict(report["era5/fizyczne"])
    metrics["variants"] = report
    json.dump(metrics, open(P / "metrics.json", "w"), indent=2)
    json.dump(pos, open(P / "positive_segments.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
