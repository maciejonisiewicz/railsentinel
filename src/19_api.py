import csv
import importlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"
P = ROOT / "data" / "processed"
ALARM, WARN = 0.5, 0.3
HZS = {"flood": "woda", "heat": "upał", "wind": "wiatr", "ice": "oblodzenie"}
LVL = ["wysoka", "średnia", "niższa"]
lg = importlib.import_module("17_log")


def load_js(name):
    t = (WEB / f"{name}.js").read_text(encoding="utf-8")
    return json.loads(re.search(r"\]=([\[{].*[\]}]);\s*$", t, re.S).group(1))


def level(x):
    return "ALARM" if x >= ALARM else "UWAGA" if x >= WARN else "niskie"


def confidence(r, i, k):
    q = r["q"][i] if r.get("q") else 0
    if q == 2:
        return "brak"
    k = min(k, 2)
    if q == 1:
        k = min(k + 1, 2)
    return LVL[k]


def build(out):
    segs = load_js("segments")
    live = load_js("live")
    names = json.load(open(P / "powiaty_kody.json", encoding="utf-8"))
    imgw = lg.imgw_warnings()
    meta = live["meta"]
    issued = meta.get("generated") or meta.get("issued")
    by_pw = {}
    for w in imgw["meteo"]:
        for c in w["c"]:
            by_pw.setdefault(c, []).append(w)

    def record(i, d, k):
        r, s = live["risk"][d], segs[i]
        h = max(HZS, key=lambda z: r[z][i])
        x = r["total"][i]
        ws = [w for c in s.get("pw", []) for w in by_pw.get(c, []) if lg.active(w, d)]
        km = s.get("km")
        return {"dzien": d, "linia": s["line"], "km_od": km[0] if km else None, "km_do": km[1] if km else None,
                "od": s.get("od", ""), "do": s.get("do", ""), "miejscowosc": s.get("place", ""), "rzeka": s.get("river") or "",
                "powiat": ", ".join(names.get(c, "") for c in s.get("pw", []) if names.get(c)), "poziom": level(x),
                "ryzyko_proc": round(x * 100), "zagrozenie": HZS[h], "woda_proc": round(r["flood"][i] * 100),
                "upal_proc": round(r["heat"][i] * 100), "wiatr_proc": round(r["wind"][i] * 100), "lod_proc": round(r["ice"][i] * 100),
                "opad_1d_mm": r["p1"][i], "opad_3d_mm": r["p3"][i], "porywy_kmh": r["gust"][i], "szyna_C": r["trail"][i],
                "pewnosc": confidence(r, i, k), "ostrzezenia_imgw": ", ".join(sorted({f"{w['n']} {w['d']}°" for w in ws})),
                "prognoza_wydana": issued, "id": s["id"]}

    days, rows, lines = [], [], {}
    for k, d in enumerate(live["days"]):
        tot = live["risk"][d]["total"]
        idx = sorted([i for i, x in enumerate(tot) if x >= WARN], key=lambda i: -tot[i])
        recs = [{"priorytet": n + 1, **record(i, d, k)} for n, i in enumerate(idx)]
        rows += recs
        days.append({"date": d, "alarm": sum(1 for x in tot if x >= ALARM), "warn": sum(1 for x in tot if WARN <= x < ALARM),
                     "km_alarm": round(sum(segs[i]["len"] for i, x in enumerate(tot) if x >= ALARM), 1), "segments": recs})
        for i, x in enumerate(tot):
            ln = lines.setdefault(segs[i]["line"], {"km": 0.0, "max": [0.0] * len(live["days"]), "worst": [None] * len(live["days"])})
            if k == 0:
                ln["km"] += segs[i]["len"]
            if x > ln["max"][k]:
                ln["max"][k] = x
                ln["worst"][k] = i
    def worst_txt(i):
        if i is None:
            return None
        g = segs[i]
        km = f"km {g['km'][0]}–{g['km'][1]}" if g.get("km") else "rejon " + (g.get("place") or "?")
        ends = f" ({g['od']} – {g['do']})" if g.get("od") else ""
        return km + ends

    line_out = {}
    for ln, v in lines.items():
        line_out[ln] = {"km_toru": round(v["km"]), "dni": [
            {"date": d, "max_ryzyko_proc": round(v["max"][k] * 100), "poziom": level(v["max"][k]), "najgorszy_odcinek": worst_txt(v["worst"][k])}
            for k, d in enumerate(live["days"])]}
    head = {"wersja": "v1", "wygenerowano": issued, "zrodlo": "RailSentinel, railsentinel.pl",
            "licencja_wynikow": "CC BY 4.0",
            "dane_zrodlowe": "IMGW-PIB (stany wód, ostrzeżenia), Open-Meteo (CC BY 4.0), OpenStreetMap (ODbL)",
            "uwaga": "Prototyp studencki. Wspiera ocenę zagrożenia, nie zastępuje procedur ani ostrzeżeń IMGW; decyzję podejmuje uprawniony pracownik.",
            "progi": {"UWAGA": WARN, "ALARM": ALARM}}
    out.mkdir(parents=True, exist_ok=True)
    json.dump({**head, "dni": days}, open(out / "alarms.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump({**head, "linie": line_out}, open(out / "lines.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    pos = {g["id"]: i for i, g in enumerate(segs)}
    feats = [{"type": "Feature", "properties": r, "geometry": {"type": "MultiLineString",
              "coordinates": [[[lo, la] for la, lo in line] for line in segs[pos[r["id"]]]["g"]]}} for r in rows]
    json.dump({"type": "FeatureCollection", "properties": head, "features": feats}, open(out / "alarms.geojson", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    keys = list(rows[0]) if rows else ["priorytet"] + list(record(0, live["days"][0], 0))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(keys)
    for r in rows:
        w.writerow(["" if r[k] is None else (str(r[k]).replace(".", ",") if isinstance(r[k], float) else r[k]) for k in keys])
    (out / "alarms.csv").write_text("﻿" + buf.getvalue(), encoding="utf-8")
    print(f"api: {len(rows)} wierszy (UWAGA+), {len(line_out)} linii -> {out}")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "api" / "v1")
