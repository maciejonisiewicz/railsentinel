import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "powiaty"
P = ROOT / "data" / "processed"
WEB = ROOT / "web" / "data"
UA = {"User-Agent": "RailSentinel/0.3 (student research prototype)"}
GH = "https://raw.githubusercontent.com/ppatrzyk/polska-geojson/master"
WD = "https://query.wikidata.org/sparql"
VOIV = {"dolnośląskie": "02", "kujawsko-pomorskie": "04", "lubelskie": "06", "lubuskie": "08", "łódzkie": "10",
        "małopolskie": "12", "mazowieckie": "14", "opolskie": "16", "podkarpackie": "18", "podlaskie": "20",
        "pomorskie": "22", "śląskie": "24", "świętokrzyskie": "26", "warmińsko-mazurskie": "28",
        "wielkopolskie": "30", "zachodniopomorskie": "32"}
CITY_FALLBACK = {"jaworzno": "2468", "żory": "2479"}
RENAMED = {"jeleniogórski": "karkonoski"}


def fetch(name, url):
    f = RAW / name
    if not f.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, headers=UA, timeout=180)
        r.raise_for_status()
        f.write_bytes(r.content)
    return f


def sparql(name, query):
    f = RAW / name
    if not f.exists():
        r = requests.get(WD, params={"query": query}, headers={**UA, "Accept": "application/sparql-results+json"}, timeout=180)
        r.raise_for_status()
        f.write_bytes(r.content)
    return json.load(open(f))["results"]["bindings"]


def norm(s):
    s = s.lower().strip()
    s = re.sub(r"^(powiat|miasto)\s+", "", s)
    return unicodedata.normalize("NFC", s)


def rings(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [[np.array(r) for r in poly] for poly in polys]


def inside(lon, lat, polys):
    for poly in polys:
        if not _ring_has(lon, lat, poly[0]):
            continue
        if any(_ring_has(lon, lat, h) for h in poly[1:]):
            continue
        return True
    return False


def _ring_has(lon, lat, ring):
    x, y = ring[:, 0], ring[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    cond = (y > lat) != (y2 > lat)
    with np.errstate(divide="ignore", invalid="ignore"):
        xi = (x2 - x) * (lat - y) / (y2 - y) + x
    return bool(np.sum(cond & (lon < xi)) % 2)


def bbox(polys):
    a = np.concatenate([p[0] for p in polys])
    return a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()


def dp_open(pts, tol):
    n = len(pts)
    if n < 3:
        return pts
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        ab = b - a
        ap = pts[i + 1:j] - a
        d = np.abs(ab[0] * ap[:, 1] - ab[1] * ap[:, 0]) / (np.hypot(*ab) + 1e-12)
        k = int(np.argmax(d))
        if d[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return pts[keep]


def dp(pts, tol):
    pts = np.asarray(pts)
    if len(pts) < 5:
        return pts
    if np.allclose(pts[0], pts[-1]):
        m = int(np.argmax(np.hypot(*(pts - pts[0]).T)))
        return np.vstack([dp_open(pts[:m + 1], tol), dp_open(pts[m:], tol)[1:]])
    return dp_open(pts, tol)


def build_codes(pw, vw):
    four = sparql("wd_teryt4.json", 'SELECT ?itemLabel ?teryt WHERE { ?item wdt:P1653 ?teryt . FILTER(STRLEN(?teryt) = 4) '
                                    'SERVICE wikibase:label { bd:serviceParam wikibase:language "pl". } }')
    seven = sparql("wd_teryt7.json", 'SELECT ?itemLabel ?teryt WHERE { ?item wdt:P1653 ?teryt . FILTER(STRLEN(?teryt) = 7) '
                                     'FILTER(REGEX(?teryt, "^[0-9]{2}6[0-9]011$")) '
                                     'SERVICE wikibase:label { bd:serviceParam wikibase:language "pl". } }')
    by4, by7 = {}, {}
    for r in four:
        by4.setdefault(norm(r["itemLabel"]["value"]), set()).add(r["teryt"]["value"])
    for r in seven:
        by7.setdefault(norm(r["itemLabel"]["value"]), set()).add(r["teryt"]["value"][:4])
    vpoly = [(VOIV[f["properties"]["nazwa"]], rings(f["geometry"])) for f in vw]
    out, notes = [], []
    for f in pw:
        name = f["properties"]["nazwa"]
        n = norm(name)
        n = RENAMED.get(n, n)
        cand = by4.get(n) or by7.get(n) or ({CITY_FALLBACK[n]} if n in CITY_FALLBACK else set())
        polys = rings(f["geometry"])
        c = np.concatenate([p[0] for p in polys]).mean(axis=0)
        if len(cand) > 1:
            v = next((code for code, vp in vpoly if inside(c[0], c[1], vp)), None)
            if v is None:
                d = [(code, np.hypot(*(np.concatenate([p[0] for p in vp]).mean(axis=0) - c))) for code, vp in vpoly]
                v = min(d, key=lambda x: x[1])[0]
            cand = {x for x in cand if x[:2] == v}
        if len(cand) != 1:
            notes.append((name, sorted(cand)))
            continue
        out.append(next(iter(cand)))
    return out, notes, vpoly


def main():
    pw = json.load(open(fetch("powiaty-medium.geojson", f"{GH}/powiaty/powiaty-medium.geojson")))["features"]
    vw = json.load(open(fetch("wojewodztwa-medium.geojson", f"{GH}/wojewodztwa/wojewodztwa-medium.geojson")))["features"]
    codes, notes, vpoly = build_codes(pw, vw)
    if notes:
        sys.exit(f"Nie rozstrzygnięto kodów: {notes}")
    assert len(set(codes)) == len(pw) == 380, (len(set(codes)), len(pw))
    bad = []
    for k, f in enumerate(pw):
        polys = rings(f["geometry"])
        c = np.concatenate([p[0] for p in polys]).mean(axis=0)
        v = next((code for code, vp in vpoly if inside(c[0], c[1], vp)), None)
        if v and v != codes[k][:2]:
            bad.append((f["properties"]["nazwa"], codes[k], v))
    print(f"kody: {len(codes)}, niezgodne z województwem (środek poza): {len(bad)}", bad[:5])

    items = []
    for k, f in enumerate(pw):
        polys = rings(f["geometry"])
        area = sum(abs(np.sum(p[0][:, 0] * np.roll(p[0][:, 1], -1) - np.roll(p[0][:, 0], -1) * p[0][:, 1])) / 2 for p in polys)
        items.append({"code": codes[k], "name": re.sub(r"^powiat\s+", "", f["properties"]["nazwa"]),
                      "polys": polys, "bbox": bbox(polys), "area": float(area)})
    items.sort(key=lambda x: -x["area"])

    segs = json.load(open(P / "segments_static.json"))
    seg_pw = {}
    for s in segs:
        pts = []
        for line in s["geometry"]:
            idx = np.unique(np.linspace(0, len(line) - 1, min(len(line), 9)).round().astype(int))
            pts += [line[i] for i in idx]
        hit = []
        for la, lo in pts:
            for it in reversed(items):
                x0, y0, x1, y1 = it["bbox"]
                if x0 <= lo <= x1 and y0 <= la <= y1 and inside(lo, la, it["polys"]):
                    if it["code"] not in hit:
                        hit.append(it["code"])
                    break
        seg_pw[s["id"]] = hit
    miss = [k for k, v in seg_pw.items() if not v]
    print(f"odcinki z powiatem: {len(seg_pw) - len(miss)}/{len(seg_pw)}; bez: {len(miss)}")
    json.dump(seg_pw, open(P / "seg_powiaty.json", "w"), separators=(",", ":"))
    json.dump({it["code"]: it["name"] for it in items}, open(P / "powiaty_kody.json", "w"), ensure_ascii=False, indent=0)

    out = {"c": [], "n": [], "g": []}
    for it in items:
        out["c"].append(it["code"])
        out["n"].append(it["name"])
        gs = []
        for poly in it["polys"]:
            ring = dp(poly[0][:, ::-1], 0.005)
            if len(ring) >= 4:
                gs.append([[round(float(a), 3), round(float(b), 3)] for a, b in ring])
        out["g"].append(gs)
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "powiaty.js").write_text("window.RS_DATA=window.RS_DATA||{};window.RS_DATA[\"powiaty\"]=" +
                                    json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print("zapisano web/data/powiaty.js", round((WEB / "powiaty.js").stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
