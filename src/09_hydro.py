"""Krok 9: moduł hydrologiczny - stany wód z wodowskazów IMGW.

Powódź to dwa mechanizmy: (1) lokalna ulewa (spływ, podmycie) i (2) fala wezbraniowa,
która przychodzi z górnego biegu rzeki, często bez lokalnego deszczu (1997: mosty na Odrze).
Model oparty tylko na lokalnym opadzie nie widzi (2). Dodajemy indeks stanu wody:
    h_idx = (H - mediana_H) / (Q99_H - mediana_H)    [0 = typowo, 1 = poziom 1% najwyższych dni]
dla odcinków leżących < 2 km od rzeki, z wodowskazu NA TEJ SAMEJ RZECE (najbliższy, < 60 km).
Lokalizacja wodowskazów: kod IMGW koduje stopnie szer./dł., nazwa -> miejscowość w OSM.
Wynik: data/processed/hydro_daily.pkl (id, date, h_idx, h3 = maks. z 3 dni)
"""
import io
import json
import pickle
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from importlib import import_module

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
P = ROOT / "data" / "processed"
norm = import_module("08_gauges").norm


def hav(a, b, c, d):
    p1, p2 = np.radians(a), np.radians(c)
    x = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(d - b) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(x))


def river_key(s):
    return norm(re.sub(r"\(.*?\)", "", str(s)))


def load():
    frames = []
    for f in sorted((RAW / "imgw_hydro").glob("codz_*.zip")):
        with zipfile.ZipFile(f) as z:
            for n in z.namelist():
                b = z.read(n)
                try:
                    txt = b.decode("utf-8-sig")
                except UnicodeDecodeError:
                    txt = b.decode("cp1250")
                # formaty IMGW różnią się między latami (';' / ',' / całe wiersze w cudzysłowie)
                rows = []
                for line in txt.splitlines():
                    line = line.replace('"', "").strip()
                    if not line:
                        continue
                    parts = line.split(";") if ";" in line else line.split(",")
                    if len(parts) >= 10:
                        rows.append([p.strip() for p in parts[:10]])
                t = pd.DataFrame(rows, columns=["code", "name", "river", "hy", "hm", "d", "h", "q", "t", "m"])
                frames.append(t)
    df = pd.concat(frames, ignore_index=True)
    df["code"] = df.code.str.strip()
    hy, m = df.hy.astype(int), df.m.astype(int)
    df["date"] = pd.to_datetime(dict(year=np.where(m >= 11, hy - 1, hy), month=m, day=df.d.astype(int)),
                                errors="coerce")
    df["h"] = pd.to_numeric(df.h, errors="coerce")
    df.loc[df.h >= 9999, "h"] = np.nan
    return df.dropna(subset=["date", "h"])


def locate(df):
    places = defaultdict(list)
    for e in json.load(open(RAW / "osm_places_all.json"))["elements"]:
        nm = e.get("tags", {}).get("name")
        if nm:
            places[(norm(nm), int(e["lat"]), int(e["lon"]))].append((e["lat"], e["lon"]))
    st = df.groupby("code").agg(name=("name", "first"), river=("river", "first")).reset_index()
    out = {}
    # cała Polska: współrzędne wodowskazów z API IMGW; dla stacji spoza API - geokodowanie po nazwie
    api_f = RAW / "pl" / "imgw_hydro_api.json"
    api = {x["id_stacji"]: x for x in json.load(open(api_f))} if api_f.exists() else {}
    for _, r in st.iterrows():
        a = api.get(r.code)
        if a and a.get("lat"):
            out[r.code] = {"lat": float(a["lat"]), "lon": float(a["lon"]), "name": r["name"],
                           "river": river_key(r.river)}
            continue
        latd, lond = int(r.code[1:3]), int(r.code[3:5])
        if not (49 <= latd <= 54 and 14 <= lond <= 24):
            continue
        n = norm(r["name"])
        c = places.get((n, latd, lond)) or places.get((n.split(" ")[0], latd, lond), [])
        if c and np.ptp([x[0] for x in c]) < 0.05 and np.ptp([x[1] for x in c]) < 0.08:
            out[r.code] = {"lat": float(np.mean([x[0] for x in c])), "lon": float(np.mean([x[1] for x in c])),
                           "name": r["name"], "river": river_key(r.river)}
    return out


def main():
    df = load()
    loc = locate(df)
    df = df[df.code.isin(loc)]
    train = df[df.date.dt.year.between(2021, 2024)]
    q50 = train.groupby("code").h.median()
    q99 = train.groupby("code").h.quantile(0.99)
    ok = (q99 - q50) > 20  # wodowskazy z sensowną amplitudą (cm)
    df = df[df.code.map(ok).fillna(False)]
    df["h_idx"] = ((df.h - df.code.map(q50)) / (df.code.map(q99) - df.code.map(q50))).clip(-1, 4)
    print(f"wodowskazy zlokalizowane: {len(loc)}, z danymi 2021-24: {int(ok.sum())}")

    segs = json.load(open(P / "segments_static.json"))
    # wszystkie rzeki w promieniu 1.5 km od toru (nie tylko najbliższa) - tor przecinający Odrę
    # mostem może mieć bliżej mały dopływ; liczy się NAJWIĘKSZA rzeka z wodowskazem
    from sklearn.neighbors import BallTree
    rpts, rnames = [], []
    size = defaultdict(int)
    rivers, seen = [], set()
    for f in (sorted((RAW / "pl").glob("rivers_*.json")) or [RAW / "osm_rivers.json"]):
        for w in json.load(open(f))["elements"]:
            if w["id"] not in seen:
                seen.add(w["id"])
                rivers.append(w)
    for w in rivers:
        nm = w.get("tags", {}).get("name")
        if not nm or "geometry" not in w:
            continue
        size[river_key(nm)] += len(w["geometry"])
        for g in w["geometry"]:
            rpts.append((g["lat"], g["lon"]))
            rnames.append(river_key(nm))
    tree = BallTree(np.radians(np.array(rpts)), metric="haversine")
    loclen = import_module("02_static_features").LocalRiverLength(rpts, rnames)
    gauged = defaultdict(list)
    for code, g in loc.items():
        if ok.get(code, False):
            gauged[g["river"]].append(code)
    mapping, exposure = {}, {}
    for s in segs:
        pts = np.radians(np.array([p for line in s["geometry"] for p in line]))
        idx = tree.query_radius(pts, r=1.5 / 6371)
        rivers = {rnames[j] for arr in idx for j in arr}
        best = None
        for rk in sorted(rivers, key=lambda r: -loclen(r, s["lat"], s["lon"])):
            for code in gauged.get(rk, []):
                g = loc[code]
                d = float(hav(s["lat"], s["lon"], g["lat"], g["lon"]))
                if d < 60 and (best is None or d < best[1]):
                    best = (code, d)
            if best:
                break
        if best:
            mapping[s["id"]] = best[0]
            # ekspozycja: tor przecina rzekę (most) lub biegnie < 300 m od niej -> 1.0, dalej -> 0.6
            rk = loc[best[0]]["river"]
            dmin = min((float(hav(np.degrees(pts[i][0]), np.degrees(pts[i][1]),
                                  rpts[j][0], rpts[j][1]))
                        for i, arr in enumerate(idx) for j in arr if rnames[j] == rk), default=9.9)
            exposure[s["id"]] = 1.0 if (dmin <= 0.3 or s["bridge_km"] > 0) else 0.6
    print(f"odcinki przypisane do wodowskazu: {len(mapping)}/{len(segs)}")
    wide = df.pivot_table(index="date", columns="code", values="h_idx", aggfunc="max")
    rows = []
    for sid, code in mapping.items():
        s = wide[code]
        rows.append(pd.DataFrame({"id": sid, "date": s.index, "h_idx": s.values,
                                  "h3": s.rolling(3, min_periods=1).max().values}))
    h = pd.concat(rows, ignore_index=True)
    pickle.dump(h, open(P / "hydro_daily.pkl", "wb"))
    json.dump({"stations": {c: loc[c] for c in set(mapping.values())}, "segment_station": mapping,
               "exposure": exposure, "q50": {c: float(q50[c]) for c in set(mapping.values())},
               "q99": {c: float(q99[c]) for c in set(mapping.values())}},
              open(P / "hydro_mapping.json", "w"), ensure_ascii=False)
    for name in ("Odra", "Nysa Kłodzka", "Biała Głuchołaska"):
        rk = river_key(name)
        print(name, "wodowskazy:", sorted({loc[c]["name"] for c in loc if loc[c]["river"] == rk})[:8])


if __name__ == "__main__":
    main()
