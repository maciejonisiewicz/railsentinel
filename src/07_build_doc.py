"""Krok 7: zrzuty ekranu dashboardu (Chrome headless) + praca konkursowa PDF z szablonu HTML.

Użycie: python src/07_build_doc.py "Imię Nazwisko"
"""
import json
import pickle
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FIG = DOCS / "fig"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
INDEX = (ROOT / "web" / "index.html").as_uri()


def chrome(*args):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--virtual-time-budget=15000", "--force-device-scale-factor=2", *args],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)


def shot(name, hash_, w=1500, h=900):
    out = FIG / f"{name}.png"
    chrome(f"--screenshot={out}", f"--window-size={w},{h}", f"{INDEX}#theme=dark&{hash_}")
    print("zrzut", out.name)


def load_js(name):
    t = (ROOT / "web" / "data" / f"{name}.js").read_text(encoding="utf-8")
    return json.loads(re.search(r"\]=([\[{].*[\]}]);\s*$", t, re.S).group(1))


def main():
    author = sys.argv[1] if len(sys.argv) > 1 else "[Imię i nazwisko autora]"
    FIG.mkdir(parents=True, exist_ok=True)
    shot("screen_replay", "mode=replay2024&issue=4&day=1")
    shot("screen_popup", "mode=replay2024&issue=4&day=1&lat=50.40&lon=16.75&z=11&popup=1", 1500, 820)
    shot("screen_1997", "mode=y1997&day=2", 1500, 900)
    shot("screen_sim", "mode=sim&preset=storm&clim=20", 1500, 900)
    shot("screen_live_pl", "mode=live", 1500, 950)
    # telefon: Playwright (Chrome headless nie zwęża okna poniżej ~500 px)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg.goto(f"{INDEX}#theme=dark&mode=line&line=276"); pg.wait_for_timeout(4000)
        pg.screenshot(path=str(FIG / "screen_phone.png")); b.close()
    print("zrzut screen_phone.png")
    shot("screen_heat", "mode=heat&day=1&hz=heat", 1500, 950)
    # wycinek mapy z dymkiem szczegółów (czytelny w druku)
    from PIL import Image
    im = Image.open(FIG / "screen_popup.png")
    W, H = im.size
    im.crop((int(W * 0.455), int(H * 0.195), int(W * 0.74), int(H * 0.855))).save(FIG / "popup_crop.png")

    m = json.load(open(ROOT / "data" / "processed" / "metrics.json"))
    rp = load_js("replay2024")
    segs = json.load(open(ROOT / "data" / "processed" / "segments_static.json"))
    heat = load_js("heat")
    s = rp["summary"]
    # udział sieci w alarmie w dniu szczytu (15.09) wg prognozy z wieczora 14.09
    share = None
    for it in rp["issues"]:
        if it["issued"] == "2024-09-15":
            share = float(np.mean(np.array(it["risk"]["2024-09-15"]["flood"]) >= 0.5) * 100)
    f3 = lambda x: f"{x:.3f}".replace(".", ",")
    f2 = lambda x: f"{x:.2f}".replace(".", ",")
    V = m["variants"]
    mv = json.load(open(ROOT / "data" / "processed" / "module_validation.json"))
    pc = lambda x: f"{x:.0f}"
    vals = {
        "author": author, "n_segments": len(segs), "km": f"{sum(x['length_km'] for x in segs):,.0f}".replace(",", " "),
        "detected": s["detected"], "damaged": s["damaged_segments"], "det_ml": s["detected_ml_only"],
        "median_lead": f"{s['median_lead_hours']:.0f}", "other_pct": pc(s["other_in_alarm_pct"]),
        "event_auc_model": f3(m["event_auc_model"]), "event_auc_baseline": f3(m["event_auc_baseline"]),
        "pr_auc_baseline": f3(m["pr_auc_baseline_p3"]), "oa_baseline": pc(m["other_alarm_pct_baseline"]),
        "prec_model": f"{m['precision_event_days_model'] * 100:.0f}%", "prec_baseline": f"{m['precision_event_days_baseline'] * 100:.0f}%",
        "rows": f"{m['rows']:,}".replace(",", " "), "n_pos": m["positive_segments"],
        "s97": m["test1997_sites_detected_system"], "s97ml": m["test1997_sites_detected_ml"],
        "seg97": m["test1997_seg_detected_system"], "seg97ml": m["test1997_seg_detected_ml"],
        "net97": pc(m["test1997_network_alarm_pct_system"]), "net97ml": pc(m["test1997_network_alarm_pct_ml"]),
        "b97_seg": m["test1997_detected_baseline"], "b97_net": pc(m["test1997_network_alarm_pct_baseline"]),
        "sys_oa": pc(m["sys2024_other_alarm_pct_system"]),
        "w_n": mv["wind_2022-02-19"]["of_days"], "w_pct": pc(mv["wind_2022-02-19"]["network_alarm_pct"]),
        "h_rank": int(mv["heat_2025_07_03"]["rank"]), "h_n": mv["heat_2025_07_03"]["of_days"],
        "h_t": pc(mv["heat_2025_07_03"]["rail_temp_max"]),
        "h_pct": f"{mv['heat_2025_07_03']['network_alarm_pct']:.1f}".replace(".", ","),
        "v_97_b": f3(V["era5/fizyczne"]["test1997_auc_baseline"]),
    }
    rm = json.load(open(ROOT / "data" / "processed" / "river_metrics.json"))
    hm = json.load(open(ROOT / "data" / "processed" / "hydro_mapping.json"))
    for yy, tag in (("test2024_flood", "24"), ("test1997_flood", "97")):
        for k in (1, 2, 3):
            x = rm[f"{yy}_k{k}"]
            vals[f"r{tag}_{k}p"] = f"{x['pod_system'] * 100:.0f}% / {x['pod_persist'] * 100:.0f}%"
            vals[f"r{tag}_{k}c"] = f"{x['csi_system']:.2f} / {x['csi_persist']:.2f}".replace(".", ",")
            vals[f"r{tag}_{k}m"] = f"{x['mae_high_model']:.2f} / {x['mae_high_persist']:.2f}".replace(".", ",")
    k2 = rm["test2024_flood_k2"]
    vals["rgain"] = f"{(k2['pod_system'] / k2['pod_persist'] - 1) * 100:.0f}"
    vals["rmae"] = f"{(1 - k2['mae_high_model'] / k2['mae_high_persist']) * 100:.0f}"
    vals["n_gauges_rf"] = rm["stations"]
    vals["n_ups"] = rm["with_upstream"]
    vals["n_gauges"] = len({c for c in json.load(open(ROOT / "data" / "processed" / "station_meta.json"))["meta"]})
    vals["n_mapped"] = len(hm["segment_station"])
    vals["n_trees"] = len(pickle.load(open(ROOT / "data" / "processed" / "flood_model.pkl", "rb"))["model"]._predictors)
    vals["n_lines"] = len({x["line"] for x in segs})
    vals["n_cells"] = len({(round(x["lat"] * 4) / 4, round(x["lon"] * 4) / 4) for x in segs})
    for key, tag in (("era5/fizyczne", "e"), ("era5/wszystkie", "a"), ("gauge/fizyczne", "g")):
        vals[f"v_pr_{tag}"] = f3(V[key]["pr_auc_model"])
        vals[f"v_ev_{tag}"] = f3(V[key]["event_auc_model"])
        vals[f"v_oa_{tag}"] = pc(V[key]["other_alarm_pct_model"])
        vals[f"v_97_{tag}"] = f3(V[key]["test1997_auc_model"])
    html = (DOCS / "praca_template.html").read_text(encoding="utf-8")
    for k, v in vals.items():
        html = html.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{\w+\}\}", html)
    if left:
        print("UWAGA - niewypełnione pola:", set(left))
    out_html = DOCS / "praca.html"
    out_html.write_text(html, encoding="utf-8")
    pdf = DOCS / "RailSentinel_praca_konkursowa.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=10000", f"--print-to-pdf={pdf}", out_html.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    print("PDF:", pdf, json.dumps(vals, ensure_ascii=False))


if __name__ == "__main__":
    main()
