"""Krok 8: gęsta sieć posterunków opadowych IMGW -> opad dobowy dla każdego odcinka.

Wykaz stacji IMGW nie zawiera współrzędnych, ale 9-cyfrowy kod stacji koduje stopień
szerokości i długości (np. 250180460 -> 50°N, 18°E). Stację lokalizujemy dopasowując jej nazwę
do miejscowości z OpenStreetMap wewnątrz tego kwadratu 1°x1° (jednoznaczne dopasowania).

Opad dla odcinka = IDW (waga 1/d²) z posterunków w promieniu 20 km (min. 2), inaczej brak (-> ERA5).
Wynik: data/processed/gauge_daily.pkl  (DataFrame: id, date, p1g)
"""
import io
import json
import pickle
import re
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
P = ROOT / "data" / "processed"


def norm(s):
    s = s.upper().replace("Ł", "L")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def locate_stations():
    st = pd.read_csv(RAW / "imgw_wykaz_stacji.csv", header=None, encoding="cp1250", dtype=str,
                     names=["code", "name", "code2"])
    st["latd"] = st.code.str[1:3].astype(int)
    st["lond"] = st.code.str[3:5].astype(int)
    st = st[(st.latd.between(49, 52)) & (st.lond.between(14, 18))]
    places = defaultdict(list)
    for e in json.load(open(RAW / "osm_places_all.json"))["elements"]:
        nm = e.get("tags", {}).get("name")
        if nm:
            places[(norm(nm), int(e["lat"]), int(e["lon"]))].append((e["lat"], e["lon"]))
    out = {}
    for _, r in st.iterrows():
        n = norm(r["name"])
        cands = places.get((n, r.latd, r.lond), [])
        if not cands:  # np. "KLODZKO 2" / "BARDO SLASKIE" -> spróbuj pierwszego członu
            first = n.split(" ")[0]
            cands = places.get((first, r.latd, r.lond), []) if len(first) > 3 else []
        if len(cands) == 1 or (len(cands) > 1 and np.ptp([c[0] for c in cands]) < 0.03
                               and np.ptp([c[1] for c in cands]) < 0.05):
            out[r.code] = (float(np.mean([c[0] for c in cands])), float(np.mean([c[1] for c in cands])), r["name"])
    print(f"stacje w kwadratach regionu: {len(st)}, zlokalizowane: {len(out)}")
    return out


def read_zip(f):
    with zipfile.ZipFile(f) as z:
        for n in z.namelist():
            raw = z.read(n).decode("cp1250")
            df = pd.read_csv(io.StringIO(raw), header=None, dtype=str)
            df = df.iloc[:, :7]
            df.columns = ["code", "name", "y", "m", "d", "p", "status"]
            yield df


def main():
    loc = locate_stations()
    frames = []
    for f in sorted((RAW / "imgw").glob("*.zip")):
        for df in read_zip(f):
            df = df[df.code.isin(loc)]
            df["date"] = pd.to_datetime(df.y + "-" + df.m + "-" + df.d, errors="coerce")
            p = pd.to_numeric(df.p, errors="coerce")
            p[df.status == "9"] = 0.0          # brak zjawiska = 0 mm
            p[df.status == "8"] = -1.0         # brak pomiaru (znacznik, później NaN)
            p[df.status == "Z"] = -1.0         # opad zbiorczy - nie wiadomo kiedy
            df["p"] = p.fillna(0.0)
            frames.append(df[["code", "date", "p"]])
    obs = pd.concat(frames).dropna(subset=["date"])
    obs = obs[obs.date.dt.month.between(3, 10)]
    print(f"pomiary: {len(obs):,}, stacje z danymi: {obs.code.nunique()}")

    segs = json.load(open(P / "segments_static.json"))
    seg_xy = np.radians([[s["lat"], s["lon"]] for s in segs])
    codes = sorted(obs.code.unique())
    st_xy = np.radians([[loc[c][0], loc[c][1]] for c in codes])
    tree = BallTree(st_xy, metric="haversine")
    ind, dist = tree.query_radius(seg_xy, r=20 / 6371, return_distance=True)

    wide = obs.pivot_table(index="date", columns="code", values="p", aggfunc="max").reindex(columns=codes)
    full = pd.date_range(wide.index.min(), wide.index.max())
    full = full[full.month.isin(range(3, 11)) & full.year.isin(obs.date.dt.year.unique())]
    wide = wide.reindex(full)
    # "brak zjawiska to również brak dnia w istniejącym miesiącu": jeśli stacja raportowała
    # w danym miesiącu, brakujące dni = 0 mm
    month = wide.index.to_period("M")
    reported = wide.notna().groupby(month).transform("any")
    wide = wide.where(~(wide.isna() & reported), 0.0)
    wide = wide.where(wide >= 0)  # znaczniki -1 -> NaN
    A = wide.values  # dni x stacje
    rows = []
    for si, s in enumerate(segs):
        if len(ind[si]) < 2:
            continue
        w = 1 / np.maximum(dist[si] * 6371, 1.0) ** 2
        sub = A[:, ind[si]]
        m = ~np.isnan(sub)
        num = np.nansum(sub * w, axis=1)
        den = (m * w).sum(axis=1)
        ok = m.sum(axis=1) >= 2
        val = np.where(ok, num / np.where(den > 0, den, 1), np.nan)
        rows.append(pd.DataFrame({"id": s["id"], "date": wide.index, "p1g": val,
                                  "n_gauges": m.sum(axis=1)}))
    g = pd.concat(rows, ignore_index=True)
    pickle.dump(g, open(P / "gauge_daily.pkl", "wb"))
    json.dump({c: loc[c] for c in codes}, open(P / "gauges.json", "w"), ensure_ascii=False)
    cov = g.dropna().groupby("id").size().shape[0]
    print(f"odcinki z opadem z posterunków: {cov}/{len(segs)}, "
          f"średnio posterunków/odcinek: {g.n_gauges.mean():.1f}")


if __name__ == "__main__":
    main()
