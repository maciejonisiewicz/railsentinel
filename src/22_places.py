import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "pl" / "places_pl.json"
OUT = ROOT / "web" / "data" / "places.js"
MERGE_KM = 4.0
MAX_POINTS = 3


def hav_km(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def main():
    segs = json.load(open(P / "segments_static.json"))
    km = json.load(open(P / "kilometraz.json"))
    nodes = defaultdict(list)
    for e in json.load(open(RAW))["elements"]:
        t = e.get("tags", {})
        if t.get("place") in ("city", "town", "village") and t.get("name"):
            nodes[t["name"]].append((e["id"], e["lat"], e["lon"]))
    refs = defaultdict(list)
    for s in segs:
        k = km.get(s["id"], {})
        for n in {s.get("place"), k.get("od"), k.get("do")}:
            if n:
                refs[n].append((s["lat"], s["lon"]))
    out = {}
    for name, pts in refs.items():
        cand = nodes.get(name)
        if not cand:
            continue
        votes = Counter()
        for la, lo in pts:
            best = min(cand, key=lambda c: hav_km(la, lo, c[1], c[2]))
            votes[best[0]] += 1
        info = {c[0]: c for c in cand}
        chosen = []
        for nid, _ in votes.most_common():
            c = info[nid]
            if all(hav_km(c[1], c[2], o[1], o[2]) > MERGE_KM for o in chosen):
                chosen.append(c)
            if len(chosen) >= MAX_POINTS:
                break
        out[name] = [[round(c[1], 3), round(c[2], 3)] for c in chosen]
    OUT.write_text("window.RS_DATA=window.RS_DATA||{};window.RS_DATA[\"places\"]=" +
                   json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    multi = sum(1 for v in out.values() if len(v) > 1)
    print(f"miejscowości: {len(out)} z {len(refs)}, z kilkoma punktami: {multi}, plik {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
