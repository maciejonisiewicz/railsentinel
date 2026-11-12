import importlib
import json
import pickle
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
m12 = importlib.import_module("12_river_forecast")
WINDOWS = {"powodz_2024": ("2024-09-08", "2024-09-25"), "rok_2024": ("2024-01-01", "2024-12-31")}


def flat(te):
    te = te.copy()
    te["h1"], te["h2"], te["hmax7"] = te["h0"], te["h0"], te["h0"]
    te["dh1"], te["dh2"] = 0.0, 0.0
    for j in range(3):
        if f"du{j}" in te:
            te[f"du{j}"] = 0.0
    return te


def main():
    RF = pickle.load(open(P / "river_model.pkl", "rb"))
    wide = pickle.load(open(P / "station_hidx.pkl", "rb"))
    F = m12.features(wide, RF["ups"], m12.station_rain())
    F = F[F.date.dt.month.between(3, 10)]
    out = {}
    for name, (a, b) in WINDOWS.items():
        out[name] = {}
        for k in (1, 2, 3):
            te = F[F.date.between(a, b)].dropna(subset=[f"y{k}", "h0"])
            true = te.h0.values + te[f"y{k}"].values
            row = {}
            for variant, t2 in (("pelna", te), ("plaska", flat(te))):
                pred = te.h0.values + RF["models"][k].predict(t2[RF["cols"][k]])
                s = m12.scores(true, pred, te.h0.values)
                s.update(m12.system_scores(te.h0.values, true, pred, RF["thr_model"][k]))
                row[variant] = {x: round(float(s[x]), 4) for x in ("mae_model", "pod_system", "far_system", "csi_system")}
                row["persystencja"] = {x: round(float(s[x]), 4) for x in ("mae_persist", "pod_persist", "csi_persist")}
            out[name][str(k)] = row
    json.dump(out, open(P / "live_skew.json", "w"), indent=1)
    for k, r in out["powodz_2024"].items():
        print(k, r)


if __name__ == "__main__":
    main()
