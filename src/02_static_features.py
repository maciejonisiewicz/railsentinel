"""Krok 2: cechy statyczne odcinków - teren i hydrografia.

- wysokość n.p.m. (Copernicus DEM 90 m przez Open-Meteo Elevation API)
- TPI (topographic position index): wysokość odcinka minus średnia otoczenia 2-3 km.
  Ujemny = dno doliny (strefa zalewowa), dodatni = grzbiet/nasyp na stoku.
- deniwelacja otoczenia (relief) - proxy stromości zboczy i spływu powierzchniowego
- odległość do najbliższej rzeki (OSM) i "wielkość" tej rzeki (łączna długość w regionie)
"""
import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parents[1]
SEG = ROOT / "data" / "processed" / "segments.json"
RIV = ROOT / "data" / "raw" / "osm_rivers.json"
OUT = ROOT / "data" / "processed" / "segments_static.json"
UA = {"User-Agent": "RailSentinel/0.1 (student research prototype)"}

RING = [(0, 0)] + [(r * math.cos(a), r * math.sin(a))
                   for r in (1.5, 3.0) for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)]


ZOOM = 11  # ~50 m/piksel na szerokości 51°N
TILE_CACHE = ROOT / "data" / "raw" / "dem_tiles"
_tiles = {}


def _tile(x, y):
    """Kafel DEM (AWS Terrain Tiles, kodowanie terrarium; źródła: SRTM/Copernicus/EU-DEM)."""
    if (x, y) not in _tiles:
        TILE_CACHE.mkdir(parents=True, exist_ok=True)
        f = TILE_CACHE / f"{ZOOM}_{x}_{y}.png"
        if not f.exists():
            url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{ZOOM}/{x}/{y}.png"
            f.write_bytes(requests.get(url, headers=UA, timeout=60).content)
        a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float64)
        _tiles[(x, y)] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    return _tiles[(x, y)]


def elevations(points):
    n = 2 ** ZOOM
    out = []
    for lat, lon in points:
        fx = (lon + 180) / 360 * n
        fy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        tx, ty = int(fx), int(fy)
        px, py = min(int((fx - tx) * 256), 255), min(int((fy - ty) * 256), 255)
        out.append(float(_tile(tx, ty)[py, px]))
    return out


class LocalRiverLength:
    """Długość [km] rzeki o danej nazwie w promieniu R km od punktu (suma długości odcinków geometrii OSM).
    Długość w km, nie liczba punktów - gęstość punktów zależy od sposobu mapowania rzeki."""
    def __init__(self, rpts, rnames, radius_km=60.0):
        self.r = radius_km / 6371.0
        idx = defaultdict(list)
        for i, n in enumerate(rnames):
            idx[n].append(i)
        self.pts, self.w = {}, {}
        for n, ii in idx.items():
            a = np.radians(np.array([rpts[i] for i in ii]))
            # długość do następnego punktu (kolejne punkty tej samej rzeki leżą obok siebie w liście)
            d = np.zeros(len(ii))
            if len(ii) > 1:
                dl = a[1:] - a[:-1]
                h = np.sin(dl[:, 0] / 2) ** 2 + np.cos(a[:-1, 0]) * np.cos(a[1:, 0]) * np.sin(dl[:, 1] / 2) ** 2
                seg = 2 * 6371 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))
                d[:-1] = np.where(seg < 2.0, seg, 0.0)   # skoki między różnymi drogami OSM pomijamy
            self.pts[n], self.w[n] = a, d
        self.trees = {}

    def __call__(self, name, lat, lon):
        if name not in self.pts:
            return 0.0
        if name not in self.trees:
            self.trees[name] = BallTree(self.pts[name], metric="haversine")
        ii = self.trees[name].query_radius(np.radians([[lat, lon]]), r=self.r)[0]
        return float(self.w[name][ii].sum())


def main():
    segs = json.load(open(SEG))

    # --- teren ---
    pts = []
    for s in segs:
        k_lat = 1 / 111.0
        k_lon = 1 / (111.0 * math.cos(math.radians(s["lat"])))
        for dx, dy in RING:
            pts.append((s["lat"] + dy * k_lat, s["lon"] + dx * k_lon))
    elev = np.array(elevations(pts)).reshape(len(segs), len(RING))
    for s, e in zip(segs, elev):
        s["elev"] = float(e[0])
        s["tpi"] = float(e[0] - e[1:].mean())
        s["relief"] = float(e.max() - e.min())

    # --- rzeki ---
    rivers, seen = [], set()
    for f in (sorted((ROOT / "data" / "raw" / "pl").glob("rivers_*.json")) or [RIV]):
        for w in json.load(open(f))["elements"]:
            if w["id"] not in seen:
                seen.add(w["id"])
                rivers.append(w)
    name_len = defaultdict(float)
    rpts, rnames = [], []
    for w in rivers:
        if "geometry" not in w:
            continue
        name = w.get("tags", {}).get("name", f"bn_{w['id']}")
        g = w["geometry"]
        name_len[name] += len(g)
        for p in g:
            rpts.append((p["lat"], p["lon"]))
            rnames.append(name)
    tree = BallTree(np.radians(np.array(rpts)), metric="haversine")
    loclen = LocalRiverLength(rpts, rnames)
    for s in segs:
        flat = np.array([p for line in s["geometry"] for p in line])
        d, idx = tree.query(np.radians(flat), k=1)
        j = int(np.argmin(d[:, 0]))
        s["river_dist_km"] = float(d[j, 0] * 6371.0)
        nm = rnames[idx[j, 0]]
        s["river_name"] = nm if not nm.startswith("bn_") else ""
        # "wielkość" rzeki = długość [km] rzeki o tej nazwie w promieniu 60 km (lokalnie, bo w Polsce
        # jest wiele różnych rzek o tej samej nazwie - Biała, Czarna...; globalna suma zawyżałaby małe rzeki)
        s["river_size"] = float(math.log1p(loclen(nm, s["lat"], s["lon"])))
    # --- najbliższa miejscowość (miasto) - do czytelnych komunikatów ---
    pf = ROOT / "data" / "raw" / "pl" / "places_pl.json"
    if not pf.exists():
        pf = ROOT / "data" / "raw" / "osm_places.json"
    if pf.exists():
        places = [(e["lat"], e["lon"], e["tags"].get("name", "")) for e in json.load(open(pf))["elements"]
                  if e.get("tags", {}).get("name") and e["tags"].get("place") in ("city", "town")]
        ptree = BallTree(np.radians(np.array([(a, b) for a, b, _ in places])), metric="haversine")
        d, idx = ptree.query(np.radians(np.array([(s["lat"], s["lon"]) for s in segs])), k=1)
        for s, dd, ii in zip(segs, d[:, 0], idx[:, 0]):
            s["place"] = places[ii][2]
            s["place_km"] = round(float(dd * 6371), 1)
    json.dump(segs, open(OUT, "w"))
    print("ok", len(segs), "przykład:", {k: segs[0][k] for k in
          ("id", "elev", "tpi", "relief", "river_dist_km", "river_name", "river_size")})


if __name__ == "__main__":
    main()
