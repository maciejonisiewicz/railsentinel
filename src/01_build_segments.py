import json
import math
from collections import defaultdict
from pathlib import Path

from matplotlib.path import Path as MplPath

ROOT = Path(__file__).resolve().parents[1]
RAW_FILES = sorted((ROOT / "data" / "raw" / "pl").glob("rail_*.json")) or [ROOT / "data" / "raw" / "osm_rail.json"]
OUT = ROOT / "data" / "processed" / "segments.json"

TILE = 0.05
POLISH_OPERATORS = {"PKP Polskie Linie Kolejowe", "Dolnośląska Służba Dróg i Kolei we Wrocławiu",
                    "PMT Linie Kolejowe", "SKPL Infrastruktura i Linie Kolejowe"}


def hav(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_polish(tags):
    op = tags.get("operator")
    ref = tags.get("ref", "")
    if op in POLISH_OPERATORS:
        return True
    if op is None and ref.isdigit() and len(ref) <= 3 and not ref.startswith("0"):
        return True
    return False


def num(v, default=None):
    try:
        return float(str(v).split(";")[0])
    except (TypeError, ValueError):
        return default


def main():
    border = json.load(open(ROOT / "data" / "raw" / "poland_border.geojson"))["coordinates"][0]
    poland = MplPath([(lat, lon) for lon, lat in border])
    seen, els = set(), []
    for f in RAW_FILES:
        for w in json.load(open(f))["elements"]:
            if w["id"] not in seen:
                seen.add(w["id"])
                els.append(w)
    groups = defaultdict(list)
    for w in els:
        t = w.get("tags", {})
        if not is_polish(t) or "geometry" not in w:
            continue
        pts = [(g["lat"], g["lon"]) for g in w["geometry"]]
        mid = pts[len(pts) // 2]
        if not poland.contains_point(mid):
            continue
        ref = t.get("ref", "bn")
        key = (ref.split(";")[0], int(mid[0] // TILE), int(mid[1] // TILE))
        groups[key].append((t, pts))

    segs = []
    for (ref, ty, tx), ways in groups.items():
        length = bridge = tunnel = emb = cut = 0.0
        speeds, elec, lines = [], 0.0, []
        for t, pts in ways:
            L = sum(hav(*pts[i], *pts[i + 1]) for i in range(len(pts) - 1))
            length += L
            if t.get("bridge") in ("yes", "viaduct"):
                bridge += L
            if t.get("tunnel") == "yes":
                tunnel += L
            if t.get("embankment") == "yes":
                emb += L
            if t.get("cutting") == "yes":
                cut += L
            if t.get("electrified") == "contact_line":
                elec += L
            s = num(t.get("maxspeed"))
            if s:
                speeds.append((s, L))
            lines.append([[round(a, 5), round(b, 5)] for a, b in pts])
        if length < 0.3:
            continue
        allpts = [p for _, pts in ways for p in pts]
        clat = sum(p[0] for p in allpts) / len(allpts)
        clon = sum(p[1] for p in allpts) / len(allpts)
        vmax = (sum(s * L for s, L in speeds) / sum(L for _, L in speeds)) if speeds else 80.0
        main_usage = any(t.get("usage") == "main" for t, _ in ways)
        segs.append({
            "id": f"L{ref}_{ty}_{tx}",
            "line": ref,
            "lat": round(clat, 5), "lon": round(clon, 5),
            "length_km": round(length, 3),
            "bridge_km": round(bridge, 3),
            "tunnel_km": round(tunnel, 3),
            "embankment_km": round(emb, 3),
            "cutting_km": round(cut, 3),
            "electrified": round(elec / length, 2),
            "maxspeed": round(vmax, 1),
            "main_line": int(main_usage),
            "geometry": lines,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(segs, open(OUT, "w"))
    print(f"odcinki: {len(segs)}, linie: {len({s['line'] for s in segs})}, "
          f"km toru: {sum(s['length_km'] for s in segs):.0f}")


if __name__ == "__main__":
    main()
