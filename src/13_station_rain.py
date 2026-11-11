import json
import pickle
from collections import defaultdict
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
P = ROOT / "data" / "processed"
g8 = import_module("08_gauges")


def locate_pl():
    st = pd.read_csv(RAW / "imgw_wykaz_stacji.csv", header=None, encoding="cp1250", dtype=str,
                     names=["code", "name", "code2"])
    st["latd"] = st.code.str[1:3].astype(int)
    st["lond"] = st.code.str[3:5].astype(int)
    places = defaultdict(list)
    for f in (RAW / "pl" / "places_pl.json", RAW / "osm_places_all.json"):
        for e in json.load(open(f))["elements"]:
            nm = e.get("tags", {}).get("name")
            if nm:
                places[(g8.norm(nm), int(e["lat"]), int(e["lon"]))].append((e["lat"], e["lon"]))
    out = {}
    for _, r in st.iterrows():
        n = g8.norm(r["name"])
        c = places.get((n, r.latd, r.lond)) or (places.get((n.split(" ")[0], r.latd, r.lond), [])
                                                if len(n.split(" ")[0]) > 3 else [])
        if c and np.ptp([x[0] for x in c]) < 0.03 and np.ptp([x[1] for x in c]) < 0.05:
            out[r.code] = (float(np.mean([x[0] for x in c])), float(np.mean([x[1] for x in c])))
    return out


def main():
    loc = locate_pl()
    frames = []
    for f in sorted((RAW / "imgw").glob("*.zip")):
        for df in g8.read_zip(f):
            df = df[df.code.isin(loc)]
            df["date"] = pd.to_datetime(df.y + "-" + df.m + "-" + df.d, errors="coerce")
            p = pd.to_numeric(df.p, errors="coerce")
            p[df.status == "9"] = 0.0
            p[df.status.isin(["8", "Z"])] = -1.0
            df["p"] = p.fillna(0.0)
            frames.append(df[["code", "date", "p"]])
    obs = pd.concat(frames).dropna(subset=["date"])
    wide = obs.pivot_table(index="date", columns="code", values="p", aggfunc="max")
    full = pd.date_range(wide.index.min(), wide.index.max())
    full = full[full.year.isin(obs.date.dt.year.unique())]
    wide = wide.reindex(full)
    rep = wide.notna().groupby(wide.index.to_period("M")).transform("any")
    wide = wide.where(~(wide.isna() & rep), 0.0).where(lambda x: x >= 0)
    codes = list(wide.columns)
    tree = BallTree(np.radians([[loc[c][0], loc[c][1]] for c in codes]), metric="haversine")
    meta = json.load(open(P / "station_meta.json"))["meta"]
    out = {}
    for s, m in meta.items():
        idx = tree.query_radius(np.radians([[m["lat"], m["lon"]]]), r=25 / 6371)[0]
        if len(idx):
            out[s] = wide.iloc[:, idx].mean(axis=1, skipna=True)
    R = pd.DataFrame(out)
    pickle.dump(R, open(P / "station_rain.pkl", "wb"))
    json.dump({c: loc[c] for c in codes}, open(P / "gauges_pl.json", "w"))
    print(f"posterunki zlokalizowane: {len(loc)}, z danymi: {len(codes)}, wodowskazy z opadem: {R.shape[1]}/{len(meta)}")


if __name__ == "__main__":
    main()
