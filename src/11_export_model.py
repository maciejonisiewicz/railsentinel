import json
import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd

from features import static_frame

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
WEB = ROOT / "web" / "data"


def export_trees(model):
    trees = []
    for it in model._predictors:
        n = it[0].nodes
        trees.append({
            "f": n["feature_idx"].astype(int).tolist(),
            "t": [float(x) for x in n["num_threshold"]],
            "l": n["left"].astype(int).tolist(),
            "r": n["right"].astype(int).tolist(),
            "v": [float(x) for x in n["value"]],
            "leaf": n["is_leaf"].astype(int).tolist(),
            "m": n["missing_go_to_left"].astype(int).tolist(),
        })
    return {"base": float(np.ravel(model._baseline_prediction)[0]), "trees": trees}


def predict_like_js(exp, X):
    raw = np.full(len(X), exp["base"])
    for t in exp["trees"]:
        for i, x in enumerate(X):
            k = 0
            while not t["leaf"][k]:
                v = x[t["f"][k]]
                go_left = t["m"][k] if np.isnan(v) else v <= t["t"][k]
                k = t["l"][k] if go_left else t["r"][k]
            raw[i] += t["v"][k]
    return 1 / (1 + np.exp(-raw))


def main():
    M = pickle.load(open(P / "flood_model.pkl", "rb"))
    model, feats = M["model"], M["features"]
    exp = export_trees(model)
    rng = np.random.default_rng(1)
    X = rng.uniform(0, 1, (300, len(feats)))
    st = static_frame(json.load(open(P / "segments_static.json")))
    for j, f in enumerate(feats):
        if f in st:
            X[:, j] = rng.choice(st[f].values, 300)
        elif f in ("p1", "p3", "p7"):
            X[:, j] = rng.gamma(0.6, {"p1": 25, "p3": 60, "p7": 90}[f], 300)
        elif f == "p_ante30":
            X[:, j] = rng.uniform(0, 200, 300)
        elif f == "p3_extreme":
            X[:, j] = rng.uniform(0, 4, 300)
    ref = model.predict_proba(pd.DataFrame(X, columns=feats))[:, 1]
    mine = predict_like_js(exp, X)
    err = float(np.abs(ref - mine).max())
    print(f"drzew: {len(exp['trees'])}, maks. różnica vs sklearn: {err:.2e}")
    assert err < 1e-4

    st["q99"] = st["cell"].map(M["clim_q99"]).astype(float)
    hm = json.load(open(P / "hydro_mapping.json"))
    base = {
        "features": feats,
        "static": {f: st[f].round(4).tolist() for f in feats if f in st},
        "q99": st["q99"].round(2).tolist(),
        "exposure": st["id"].map(hm["exposure"]).fillna(0).round(2).tolist(),
        "hriver": [hm["stations"][hm["segment_station"][i]]["river"] if i in hm["segment_station"] else ""
                   for i in st["id"]],
        "threshold": M["threshold"],
        "ids": st["id"].tolist(),
    }
    out = {"model": exp, "base": base}
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "model.js").write_text("window.RS_DATA=window.RS_DATA||{};window.RS_DATA.model=" +
                                  json.dumps(out, separators=(",", ":")) + ";\n")
    print("zapisano web/data/model.js", round((WEB / "model.js").stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
