import json
import math
import re
import time
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
CACHE = RAW / "osm_milestones.json"
UA = {"User-Agent": "RailSentinel/0.2 (student research prototype)"}
Q = """[out:json][timeout:1500];
area["ISO3166-1"="PL"][admin_level=2]->.pl;
rel(area.pl)[route=railway][ref]->.rs;
foreach.rs->.r(
  .r out tags;
  way(r.r)->.w;
  node(around.w:25)[railway=milestone]["railway:position"];
  out;
);"""


def fetch():
    if CACHE.exists():
        return json.load(open(CACHE))
    for url in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        for _ in range(3):
            try:
                r = requests.post(url, data={"data": Q}, headers=UA, timeout=1800)
                if r.status_code == 200:
                    d = r.json()
                    json.dump(d, open(CACHE, "w"))
                    return d
                print(url, r.status_code, r.text[:200])
            except requests.RequestException as e:
                print(url, type(e).__name__)
            time.sleep(60)
    raise RuntimeError("Overpass niedostępny")


def pos(v):
    v = v.strip().replace(",", ".")
    if v.startswith("mi:"):
        return None
    m = re.match(r"^-?\d+(\.\d+)?", v)
    return float(m.group(0)) if m else None


def places():
    pl = [(e["lat"], e["lon"], e["tags"]["name"], e["tags"]["place"])
          for e in json.load(open(RAW / "pl" / "places_pl.json"))["elements"]
          if e["tags"].get("place") in ("city", "town", "village") and e["tags"].get("name")]
    A = np.array([(a, b) for a, b, _, _ in pl])
    return A, [n for _, _, n, _ in pl], [t for _, _, _, t in pl]


def nearest_place(A, names, types, la, lo):
    k = math.cos(math.radians(la))
    d = np.hypot((A[:, 0] - la) * 110.57, (A[:, 1] - lo) * 111.32 * k)
    d = d - np.where(np.array(types) == "village", 0.0, 1.5)
    i = int(np.argmin(d))
    return names[i] if d[i] < 6 else None


def main():
    d = fetch()
    PA, PN, PT = places()
    lines, cur = {}, None
    for e in d["elements"]:
        if e["type"] == "relation":
            cur = e["tags"].get("ref", "").strip()
            continue
        p = pos(e["tags"].get("railway:position", ""))
        if cur and p is not None:
            lines.setdefault(cur, {})[e["id"]] = (e["lat"], e["lon"], p)
    print(f"słupki: {sum(len(v) for v in lines.values())} na {len(lines)} liniach")
    segs = json.load(open(P / "segments_static.json"))
    out, miss = {}, 0
    for s in segs:
        pts = [pt for part in s["geometry"] for pt in part]
        G = np.array(pts)
        kk = math.cos(math.radians(s["lat"]))
        GX = np.c_[G[:, 1] * kk * 111.32, G[:, 0] * 110.57]
        D2 = ((GX[:, None, :] - GX[None, :, :]) ** 2).sum(-1)
        ia, ib = np.unravel_index(np.argmax(D2), D2.shape)
        rec = {"km": None, "od": nearest_place(PA, PN, PT, *pts[ia]), "do": nearest_place(PA, PN, PT, *pts[ib])}
        out[s["id"]] = rec
        km = kilometraz(s, lines.get(str(s["line"])), pts, (ia, ib))
        if km is None:
            miss += 1
            continue
        rec["km"], (va, vb) = km
        rec["od"], rec["do"] = nearest_place(PA, PN, PT, *pts[va]), nearest_place(PA, PN, PT, *pts[vb])
    json.dump(out, open(P / "kilometraz.json", "w"), ensure_ascii=False)
    n = sum(1 for r in out.values() if r["km"])
    print(f"kilometraż: {n} / {len(segs)} odcinków ({n / len(segs):.0%}), bez danych: {miss}")


def kilometraz(s, ms, pts, ends):
    if not ms or len(ms) < 2:
        return None
    if True:
        M = np.array(list(ms.values()))
        k = math.cos(math.radians(s["lat"]))
        X = np.c_[M[:, 1] * k * 111.32, M[:, 0] * 110.57]
        kms, at = [], {}
        for vi, (la, lo) in enumerate(pts):
            q = np.array([lo * k * 111.32, la * 110.57])
            dist = np.hypot(*(X - q).T)
            o = np.argsort(dist)
            if dist[o[0]] > 2.0:
                continue
            i = o[0]
            j = next((j for j in o[1:6] if abs(M[j, 2] - M[i, 2]) > 1e-6 and dist[j] < 3.0), None)
            if j is None:
                kms.append(M[i, 2]); at[vi] = M[i, 2]; continue
            a, b = X[i], X[j]
            t = float(np.dot(q - a, b - a) / max(1e-9, np.dot(b - a, b - a)))
            t = max(-1.5, min(2.5, t))
            kms.append(M[i, 2] + t * (M[j, 2] - M[i, 2])); at[vi] = kms[-1]
        if len(kms) < max(2, len(pts) // 3):
            return None
        med = float(np.median(kms))
        good = {vi: v for vi, v in at.items() if abs(v - med) <= s["length_km"] + 1.0}
        kms = np.array(list(good.values()))
        if len(kms) < 2:
            return None
        lo_, hi_ = float(np.percentile(kms, 2)), float(np.percentile(kms, 98))
        span = hi_ - lo_
        if span > 3 * s["length_km"] + 1.0 or span < 0.25 * s["length_km"] - 0.5:
            return None
        va, vb = min(good, key=good.get), max(good, key=good.get)
        return [round(max(0.0, lo_), 1), round(hi_, 1)], (va, vb)


if __name__ == "__main__":
    main()
