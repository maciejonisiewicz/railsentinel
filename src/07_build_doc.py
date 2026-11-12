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
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg.goto(f"{INDEX}#theme=dark&mode=line&line=276"); pg.wait_for_timeout(4000)
        pg.screenshot(path=str(FIG / "screen_phone.png")); b.close()
    print("zrzut screen_phone.png")
    shot("screen_heat", "mode=heat&day=1&hz=heat", 1500, 950)
    from PIL import Image
    im = Image.open(FIG / "screen_popup.png")
    W, H = im.size
    im.crop((int(W * 0.455), int(H * 0.195), int(W * 0.74), int(H * 0.855))).save(FIG / "popup_crop.png")

    m = json.load(open(ROOT / "data" / "processed" / "metrics.json"))
    rp = load_js("replay2024")
    segs = json.load(open(ROOT / "data" / "processed" / "segments_static.json"))
    heat = load_js("heat")
    s = rp["summary"]
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
        "w_n": mv["wind_2022-02-19"]["of_days"], "w_rank": int(mv["wind_2022-02-19"]["rank"]), "w_pct": pc(mv["wind_2022-02-19"]["network_alarm_pct"]),
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
    vals.update(new_tests(rp, segs))
    vals.update(extra_vals(m))
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
    set_pdf_author(pdf, author)
    ann = (DOCS / "zalacznik_template.html").read_text(encoding="utf-8")
    for k, v in vals.items():
        ann = ann.replace("{{" + k + "}}", str(v))
    if re.findall(r"\{\{\w+\}\}", ann):
        print("UWAGA - załącznik, niewypełnione:", set(re.findall(r"\{\{\w+\}\}", ann)))
    ann_html = DOCS / "zalacznik.html"
    ann_html.write_text(ann, encoding="utf-8")
    ann_pdf = DOCS / "RailSentinel_zalacznik_techniczny.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=10000", f"--print-to-pdf={ann_pdf}", ann_html.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    set_pdf_author(ann_pdf, author)
    print("PDF:", pdf, json.dumps(vals, ensure_ascii=False))


def fetch_status():
    snap = DOCS / "status_snapshot.json"
    try:
        import requests
        r = requests.get("https://raw.githubusercontent.com/maciejonisiewicz/railsentinel/gh-pages/data/status.json", timeout=30)
        r.raise_for_status()
        d = r.json()
        snap.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return d
    except Exception as e:
        print("status.json niedostępny, używam zapisanej kopii:", type(e).__name__)
        return json.load(open(snap)) if snap.exists() else None


def extra_vals(m):
    pl = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")
    out = {}
    sk = json.load(open(ROOT / "data" / "processed" / "live_skew.json"))["powodz_2024"]
    rows = []
    for k in "123":
        r = sk[k]
        pf, pp, pq = r["pelna"], r["plaska"], r["persystencja"]
        rows.append(f"<tr><td>{k} {'dzień' if k == '1' else 'dni'}</td>"
                    f"<td>{pf['pod_system'] * 100:.0f}% / {pp['pod_system'] * 100:.0f}% / {pq['pod_persist'] * 100:.0f}%</td>"
                    f"<td>{pl(pf['csi_system'], 2)} / {pl(pp['csi_system'], 2)} / {pl(pq['csi_persist'], 2)}</td>"
                    f"<td>{pl(pf['mae_model'], 3)} / {pl(pp['mae_model'], 3)} / {pl(pq['mae_persist'], 3)}</td></tr>")
    out["skew_rows"] = "".join(rows)
    r2 = sk["2"]
    out["skew_gain_full"] = f"+{(r2['pelna']['pod_system'] / r2['persystencja']['pod_persist'] - 1) * 100:.0f}%"
    out["skew_gain_flat"] = f"+{(r2['plaska']['pod_system'] / r2['persystencja']['pod_persist'] - 1) * 100:.0f}%"
    n_reg = round(m["rows"] / 856)
    rate = m["sys_normal_alarms_per_1000_system"]
    out["normal_n"], out["normal_rate"] = n_reg, pl(rate, 2)
    out["normal_every"] = pl(1 / (rate / 1000 * n_reg), 1)
    st = fetch_status()
    rows, note = [], ""
    if st and st.get("daily"):
        for k in "123":
            x = st["river"].get(k)
            lbl = f"{k} {'dzień' if k == '1' else 'dni'}"
            if x:
                g = x["gain_pct"]
                rows.append(f"<tr><td>{lbl}</td><td>{x['n']}</td><td>{pl(x['mae_model'], 3)} / {pl(x['mae_persist'], 3)}</td>"
                            f"<td>{'+' if g and g > 0 else ''}{pl(g)}%</td><td>{x['events']}</td></tr>")
            else:
                rows.append(f"<tr><td>{lbl}</td><td colspan='4'>za mało danych (dziennik ma {st['days']} dni)</td></tr>")
        al = sorted(d["alarm"] for d in st["daily"])
        wa = sorted(d["warn"] for d in st["daily"])
        ev = sum((st["river"].get(k) or {}).get("events", 0) for k in "123")
        note = (("W okresie weryfikacji nie było przekroczeń progu alarmu fali, więc wykrywalność będzie widoczna dopiero przy pierwszym wezbraniu. "
                 if ev == 0 else f"W okresie weryfikacji było {ev} przekroczeń progu; wykrywalność w tabeli na stronie statusu. ") +
                f"W {st['days']} dniach dziennika mediana odcinków w stanie ALARM wynosiła {al[len(al) // 2]} dziennie, a w stanie UWAGA {wa[len(wa) // 2]}. "
                f"Narastająco {st['imgw_overlap']['rs_in']} wskazań RailSentinel mieściło się w powiatach z ostrzeżeniem IMGW, a {st['imgw_overlap']['rs_out']} poza nimi.")
        out["prosp_date"] = f"{st['updated'][8:10]}.{st['updated'][5:7]}.{st['updated'][:4]}"
        out["prosp_days"], out["prosp_gauges"] = st["days"], st["daily"][-1].get("gauges") or 780
    else:
        rows.append("<tr><td colspan='5'>Dziennik zbiera dane od 12.11.2026, pierwsze wyniki pojawią się po kilku dniach.</td></tr>")
        out.update({"prosp_date": "dzień złożenia pracy", "prosp_days": 0, "prosp_gauges": 780})
    out["prosp_rows"], out["prosp_note"] = "".join(rows), note
    cand = [d for d in (st or {}).get("daily", []) if d.get("imgw_segments")]
    if cand:
        e = max(cand, key=lambda d: d["imgw_segments"])
        d = e["date"]
        out["imgw_example"] = (f"Przykład z {d[8:10]}.{d[5:7]}.{d[:4]}: ostrzeżenia IMGW obejmowały {e['imgw_powiats']} powiatów, czyli "
                               f"{e['imgw_segments']} odcinków, a RailSentinel wskazał z nich do sprawdzenia {e['rs_in']}"
                               + (f", a dodatkowo {e['rs_out']} poza obszarem ostrzeżeń" if e["rs_out"] else ""))
    else:
        out["imgw_example"] = ("Przykład z 12.11.2026: ostrzeżenie 1° przed intensywnym deszczem obejmowało 9 powiatów, czyli 71 odcinków "
                               "(256 km toru), a RailSentinel wskazał z nich do sprawdzenia 0")
    return out


def new_tests(rp, segs):
    out = {}
    ids = [x["id"] for x in load_js("segments")]
    dam = np.array([i in set(rp["damaged"]) for i in ids])
    nd = int(dam.sum())
    rng = np.random.default_rng(0)
    def top(v, k, n=300):
        return float(np.mean([dam[np.lexsort((rng.random(len(v)), -v))[:k]].sum() for _ in range(n)]))
    ISS = {it["issued"]: it for it in rp["issues"]}
    mx = lambda it, key: np.max([it["risk"][d][key] for d in it["days"]], axis=0)
    it = ISS["2024-09-12"]
    W, FL, P3 = mx(it, "flood"), mx(it, "flash"), mx(it, "p3")
    al = W >= 0.5
    out.update({"rk_alarm": int(al.sum()), "rk_alarm_pct": f"{al.mean() * 100:.1f}".replace(".", ","),
                "rk_dmg": int(dam[al].sum()), "rk_lift": f"{(dam[al].mean()) / (nd / len(ids)):.0f}"})
    S = load_js("segments")
    Ln = np.array([x["len"] for x in S])
    reg = np.array([any(c[:2] in ("02", "16") for c in x.get("pw", [])) for x in S])
    out["rg_km"] = f"{Ln[reg].sum() / 1000:.1f}".replace(".", ",") + " tys."
    out["rg_alarm_km"] = f"{Ln[al & reg].sum():.0f}"
    out["rg_pct"] = f"{Ln[al & reg].sum() / Ln[reg].sum() * 100:.0f}"
    for k in (10, 50, 100):
        out[f"rk_m{k}"] = f"{top(FL, k):.0f}"
        out[f"rk_b{k}"] = f"{top(P3, k):.0f}"
        out[f"rk_r{k}"] = f"{k * nd / len(ids):.1f}".replace(".", ",")
    rows = []
    for key, lbl in (("2024-09-12", "11.09, 20:00 (52 h)"), ("2024-09-14", "13.09, 20:00 (4 h)")):
        Wk = mx(ISS[key], "flood")
        for thr in (0.3, 0.5, 0.7):
            a = Wk >= thr
            tp, fp, fn = int((a & dam).sum()), int((a & ~dam).sum()), int((~a & dam).sum())
            b = "<b>" if thr == 0.5 else ""
            e = "</b>" if thr == 0.5 else ""
            rows.append(f"<tr><td>{lbl}</td>" + f"<td>{b}{thr:.1f}{e}".replace(".", ",") +
                        f"</td><td>{b}{tp}{e}</td><td>{fn}</td><td>{fp}</td><td>{b}{(tp + fp) / max(tp, 1):.1f}{e}</td>".replace(".", ",") +
                        f"<td>{a.mean() * 100:.1f}%</td></tr>".replace(".", ","))
    out["err_rows"] = "".join(rows)
    ci = ids.index("L309_1008_332")
    rank = lambda it: int((mx(it, "flood") > mx(it, "flood")[ci]).sum()) + 1
    out["cs_p3_10"] = f"{mx(ISS['2024-09-10'], 'p3')[ci]:.0f}"
    out["cs_p3_11"] = f"{mx(ISS['2024-09-11'], 'p3')[ci]:.0f}"
    out["cs_p3_12"] = f"{mx(ISS['2024-09-12'], 'p3')[ci]:.0f}"
    out["cs_r12"] = f"{mx(ISS['2024-09-12'], 'flood')[ci] * 100:.0f}"
    out["cs_rank12"] = rank(ISS["2024-09-12"])
    out["cs_r13"] = f"{mx(ISS['2024-09-13'], 'flood')[ci] * 100:.0f}"
    out["cs_h13"] = f"{mx(ISS['2024-09-13'], 'h3')[ci]:.1f}".replace(".", ",")
    out["cs_rv14"] = f"{mx(ISS['2024-09-14'], 'river')[ci] * 100:.0f}"
    out["cs_h14"] = f"{mx(ISS['2024-09-14'], 'h3')[ci]:.1f}".replace(".", ",")
    out["rk_nd"] = nd
    ev = json.load(open(ROOT / "data" / "processed" / "events_validation.json"))
    pl = lambda x: f"{x:.1f}".replace(".", ",")
    rows = []
    for r in ev["flood_2010"]:
        verdict = "<b>ALARM</b>" if r["alarm"] else ("UWAGA" if r["warn"] else "<b>brak</b> – nie wykryto")
        rows.append(f"<tr><td>{r['name']}</td><td>{verdict} ({r['risk'] * 100:.0f}%)</td><td>{pl(r['top_pct'])}%</td></tr>")
    out["ev_flood_rows"] = "".join(rows)
    rows, hit = [], 0
    for r in ev.get("wind_storms", []):
        hit += r["rank"] == 1
        rows.append(f"<tr><td>{r['name']}</td><td>{r['storm_day'][8:10]}.{r['storm_day'][5:7]}.{r['storm_day'][:4]}</td>"
                    f"<td><b>{pl(r['share_warn'])}%</b></td><td>{pl(r['rest_median'])}% / {pl(r['rest_max'])}%</td>"
                    f"<td>{r['rank']}/{r['days']}</td><td>{r['max_gust']} km/h</td></tr>")
    out["ev_wind_rows"] = "".join(rows)
    out["ev_wind_hit"], out["ev_wind_n"] = hit, len(ev.get("wind_storms", []))
    km = json.load(open(ROOT / "data" / "processed" / "kilometraz.json"))
    out["km_pct"] = f"{sum(1 for v in km.values() if v['km']) / len(segs) * 100:.0f}"
    return out


def set_pdf_author(path, author):
    import pypdf
    r = pypdf.PdfReader(str(path)); w = pypdf.PdfWriter()
    for pg in r.pages:
        w.add_page(pg)
    w.add_metadata({"/Title": "RailSentinel – praca konkursowa", "/Author": author, "/Creator": author, "/Producer": "RailSentinel"})
    with open(path, "wb") as f:
        w.write(f)


if __name__ == "__main__":
    main()

