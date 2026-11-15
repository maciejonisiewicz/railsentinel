import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "switches"
P = ROOT / "data" / "processed"
OUT = P / "switches.json"
UA = {"User-Agent": "RailSentinel/0.3 (student research prototype; non-commercial; github.com/maciejonisiewicz/railsentinel)"}
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
BBOX = (49.0, 14.1, 54.9, 24.2)
TILE = 1.0
SNAP_M = 120.0
KINDS = {"switch": "n", "derail": "d"}


def tiles():
    s0, w0, n0, e0 = BBOX
    out = []
    la = s0
    while la < n0:
        lo = w0
        while lo < e0:
            out.append((round(la, 2), round(lo, 2), round(min(la + TILE, n0), 2), round(min(lo + TILE, e0), 2)))
            lo += TILE
        la += TILE
    return out


def query(s, w, n, e):
    return (f'[out:json][timeout:120];(node["railway"="switch"]({s},{w},{n},{e});'
            f'node["railway"="derail"]({s},{w},{n},{e}););out;')


DEAD = {}


def fetch_tile(t, tries=40):
    f = RAW / f"t_{t[0]}_{t[1]}.json"
    if f.exists():
        return json.load(open(f))
    wait = 10
    for k in range(tries):
        live = [m for m in MIRRORS if DEAD.get(m, 0) < time.time()]
        url = live[k % len(live)] if live else MIRRORS[0]
        host = url.split("/")[2]
        try:
            r = requests.post(url, data={"data": query(*t)}, headers=UA, timeout=(8, 100))
        except requests.exceptions.RequestException as ex:
            print(f"  {t}: {host} {type(ex).__name__}", flush=True)
            DEAD[url] = time.time() + 600 if url != MIRRORS[0] else 0
            time.sleep(3)
            continue
        if r.status_code == 200:
            try:
                d = r.json()
            except ValueError:
                d = None
            if d and "elements" in d and "remark" not in d:
                f.write_text(json.dumps(d, separators=(",", ":")))
                return d
            print(f"  {t}: {host} odpowiedź niepełna ({str(d.get('remark', ''))[:80] if d else 'nie JSON'})", flush=True)
        else:
            print(f"  {t}: {host} http {r.status_code}", flush=True)
        time.sleep(wait)
        wait = min(wait * 1.4, 90)
    raise RuntimeError(f"Overpass niedostępny dla kafelka {t}")


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    nodes = {}
    ts = tiles()
    for i, t in enumerate(ts):
        d = fetch_tile(t)
        for el in d["elements"]:
            if el.get("type") == "node":
                nodes[el["id"]] = (el["lat"], el["lon"], el.get("tags", {}).get("railway"))
        print(f"kafelek {i + 1}/{len(ts)} {t}: razem {len(nodes)} węzłów", flush=True)
    return nodes


def hav_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def build_index(segs, step_m=40.0):
    grid = defaultdict(list)
    cell = 0.003
    for si, s in enumerate(segs):
        for line in s["geometry"]:
            for (a, b), (c, d) in zip(line[:-1], line[1:]):
                n = max(1, int(hav_m(a, b, c, d) / step_m))
                for k in range(n + 1):
                    la, lo = a + (c - a) * k / n, b + (d - b) * k / n
                    grid[(int(la / cell), int(lo / cell))].append((si, la, lo))
    return grid, cell


def nearest(grid, cell, lat, lon, max_m):
    r = int(max_m / 111000 / cell) + 1
    ci, cj = int(lat / cell), int(lon / cell)
    best, bi = 1e18, None
    for i in range(ci - r, ci + r + 1):
        for j in range(cj - r, cj + r + 1):
            for si, la, lo in grid.get((i, j), ()):
                d = hav_m(lat, lon, la, lo)
                if d < best:
                    best, bi = d, si
    return (bi, best) if best <= max_m else (None, best)


def assign(nodes, segs):
    grid, cell = build_index(segs)
    cnt = defaultdict(lambda: {"n": 0, "d": 0})
    dists, matched = [], 0
    for lat, lon, kind in nodes.values():
        si, dist = nearest(grid, cell, lat, lon, SNAP_M)
        dists.append(dist)
        if si is not None:
            matched += 1
            cnt[segs[si]["id"]][KINDS.get(kind, "n")] += 1
    return cnt, dists, matched


def main():
    segs = json.load(open(P / "segments_static.json"))
    nodes = download()
    cnt, dists, matched = assign(nodes, segs)
    dists.sort()
    q = lambda p: round(dists[min(len(dists) - 1, int(p * len(dists)))], 1)
    out = {"meta": {"zrodlo": "OpenStreetMap (Overpass API), węzły railway=switch i railway=derail",
                    "licencja": "ODbL 1.0", "snap_m": SNAP_M, "wezlow": len(nodes), "przypisanych": matched,
                    "odcinkow_z_rozjazdami": len(cnt),
                    "uwaga": "Liczba rozjazdów z OSM jest wskaźnikiem ekspozycji, nie ewidencją PLK."},
           "seg": {sid: [v["n"], v["d"]] for sid, v in sorted(cnt.items())}}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"węzłów OSM: {len(nodes)}, przypisanych do odcinków (<= {SNAP_M:.0f} m): {matched}, "
          f"odcinków z rozjazdami: {len(cnt)} z {len(segs)}")
    print("odległość do najbliższego odcinka [m], kwantyle 10/25/50/75/90%:", [q(p) for p in (0.1, 0.25, 0.5, 0.75, 0.9)])


if __name__ == "__main__":
    if "--tylko-kafelki" in sys.argv:
        download()
    else:
        main()
