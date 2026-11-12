import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/web/index.html"
CHANNEL = os.environ.get("RS_BROWSER", "chrome")
res = []


def ok(name, cond):
    res.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def load_js(name):
    t = (ROOT / "web" / "data" / f"{name}.js").read_text(encoding="utf-8")
    return json.loads(re.search(r"\]=([\[{].*[\]}]);\s*$", t, re.S).group(1))


LIVE = load_js("live")
SEGS = load_js("segments")
GEN = datetime.strptime(LIVE["meta"]["generated"], "%Y-%m-%d %H:%M")
NOW = (GEN + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
DAY = LIVE["days"][0]
CODES = sorted({c for s in SEGS if s["line"] == "276" for c in s.get("pw", [])})
METEO = [{"id": "T1", "nazwa_zdarzenia": "Intensywne opady deszczu", "stopien": "2", "prawdopodobienstwo": "80",
          "obowiazuje_od": f"{DAY} 00:00:00", "obowiazuje_do": f"{LIVE['days'][-1]} 23:00:00", "opublikowano": f"{DAY} 01:00:00",
          "tresc": "test", "komentarz": "Brak.", "biuro": "test", "teryt": CODES}]
HYDRO = [{"opublikowano": f"{DAY} 01:00:00", "stopień": "1", "data_od": f"{DAY} 00:00:00", "data_do": f"{LIVE['days'][-1]} 23:00:00",
          "prawdopodobienstwo": "80", "numer": "1", "biuro": "test", "zdarzenie": "Gwałtowne wzrosty stanów wody", "przebieg": "test",
          "komentarz": "", "obszary": [{"wojewodztwo": "dolnośląskie", "opis": "test", "kod_zlewni": []}]}]
STATUS = {"updated": "x", "runs": 4, "days": 4, "first": "2026-11-09", "last": GEN.strftime("%Y-%m-%d %H:%M"),
          "runs_per_day": {"2026-11-09": 1}, "imgw_overlap": {"rs_in": 3, "rs_out": 1},
          "river": {"1": {"n": 100, "days": 3, "mae_model": 0.03, "mae_persist": 0.04, "gain_pct": 25.0, "events": 2, "pod_system": 1.0,
                          "pod_persist": 0.5, "far_system": 0.2, "far_persist": 0.1}, "2": None, "3": None},
          "daily": [{"date": "2026-11-09", "generated": "2026-11-09 04:15", "alarm": 1, "warn": 2, "km_alarm": 5.0, "imgw_powiats": 3,
                     "imgw_segments": 30, "rs_in": 3, "rs_out": 1, "p1_max": 10, "gust_max": 70, "tmin_min": -2, "gauges": 780, "cells_ok": 562}]}


def route_all(ctx):
    ctx.route("**/api/data/warningsmeteo", lambda r: r.fulfill(json=METEO, headers={"access-control-allow-origin": "*"}))
    ctx.route("**/api/data/warningshydro", lambda r: r.fulfill(json=HYDRO, headers={"access-control-allow-origin": "*"}))
    ctx.route("**/data/status.json", lambda r: r.fulfill(json=STATUS))


with sync_playwright() as p:
    b = p.chromium.launch(channel=CHANNEL)
    ctx = b.new_context(viewport={"width": 1600, "height": 950}, accept_downloads=True, color_scheme="dark")
    route_all(ctx)
    pg = ctx.new_page()
    pg.clock.set_fixed_time(NOW)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE)
    pg.wait_for_timeout(3000)
    ok("start: tryb Na żywo", pg.locator("#modes button.on").inner_text().strip().endswith("Na żywo"))
    ok("start: licznik alarmów", pg.locator("#kAlarm").inner_text().strip() != "–")
    ok("start: lista do sprawdzenia", pg.locator("#top li").count() >= 1)
    ok("start: chip daty prognozy", "Prognoza wydana" in pg.locator("#updChip").inner_text())
    ok("dni: Dziś/Jutro/Pojutrze", pg.locator("#days button").count() == 3)
    has_wx = pg.evaluate("!!RS_DATA.live.risk[RS_DATA.live.days[0]].tmin")
    ok("pogoda w liczbach w opisie widoku", (not has_wx) or "Pogoda w prognozie" in pg.locator("#story").inner_text())
    ok("przewodnik: nie wyświetla się automatycznie w teście", not pg.locator("#tour").is_visible())
    ok("szybki start: ciężkie dane widoków historycznych ładują się dopiero na żądanie", pg.evaluate("!window.RS_DATA.replay2024 && !window.RS_DATA.heat && !window.RS_DATA.y1997 && !window.RS_DATA.model"))

    ok("IMGW: karta ostrzeżeń widoczna", pg.locator("#warnCard").is_visible())
    ok("IMGW: nazwa ostrzeżenia i stopień", "Intensywne opady deszczu" in pg.locator("#warnCard").inner_text() and "2°" in pg.locator("#warnCard").inner_text())
    ok("IMGW: ostrzeżenie hydrologiczne", "Gwałtowne wzrosty stanów wody" in pg.locator("#warnCard").inner_text())
    ok("IMGW: porównanie obszaru z odcinkami", "RailSentinel wskazuje z nich do sprawdzenia" in pg.locator("#warnCard").inner_text())
    pg.check("#wOverlay")
    pg.wait_for_timeout(500)
    ok("IMGW: nakładka powiatów włącza się", pg.locator("#wOverlay").is_checked())
    pg.uncheck("#wOverlay")

    for m in ["line", "replay2024", "sim", "heat", "y1997", "live"]:
        pg.click(f"#modes button[data-mode='{m}']")
        pg.wait_for_timeout(900)
        ok(f"tryb {m}: nagłówek", len(pg.locator("#story h2").inner_text()) > 3)
    pg.click("#modes button[data-mode='heat']")
    pg.wait_for_timeout(800)
    n = pg.evaluate("(() => { const r = RS_DATA.heat.risk[RS_DATA.heat.days[1]]; return RS_DATA.segments.filter((s,i)=>r.heat[i]>=0.3 && s.g[0][0][0]>52.3).length })()")
    ok(f"upał obejmuje północ Polski ({n} odc. > 52.3°N z uwagą)", n > 0)
    ok("karta IMGW ukryta poza trybem na żywo", not pg.locator("#warnCard").is_visible())
    ok("komputer: przycisk „Więcej” (tylko dla telefonu) jest ukryty", not pg.locator("#moreBtn").is_visible() and pg.locator("#modes button:visible").count() == 6)
    pg.click("#hazards button[data-h='wind']")
    pg.wait_for_timeout(300)
    ok("filtr zagrożeń", pg.locator("#hazards button.on").get_attribute("data-h") == "wind")
    pg.click("#hazards button[data-h='total']")
    pg.click("#modes button[data-mode='replay2024']")
    pg.wait_for_timeout(800)
    ok("backtest: oś czasu widoczna", pg.locator("#issueCtrl").is_visible())
    pg.click("#play")
    pg.wait_for_timeout(1400 * 7 + 800)
    ok("backtest: animacja dochodzi do końca", pg.locator("#issue").input_value() == "6")
    ok("backtest: statystyka zniszczeń", "/37" in pg.locator("#tlStat").inner_text())
    ok("backtest: komentarz do daty prognozy", "Alarm:" in pg.locator("#tlCap").inner_text())
    pg.locator("#top li[data-i]").first.click()
    pg.wait_for_timeout(1200)
    ok("okno szczegółów odcinka", pg.locator(".leaflet-popup .pp").count() == 1)
    ok("okno: wyjaśnienie 'Dlaczego'", "Dlaczego" in pg.locator(".leaflet-popup").inner_text())
    pg.click("#briefBtn")
    pg.wait_for_timeout(300)
    ok("raport dla dyżurnego otwiera się", pg.locator("#briefDlg").is_visible() and "ALARM" in pg.locator("#brief").inner_text())
    with pg.expect_download() as dl:
        pg.click("#csvNet")
    f = ROOT / "build" / "e2e_net.csv"
    f.parent.mkdir(exist_ok=True)
    dl.value.save_as(f)
    rows = f.read_text(encoding="utf-8-sig").splitlines()
    ok(f"eksport CSV sieci ({len(rows) - 1} odcinków)", len(rows) > 5 and rows[0].startswith("priorytet;dzien;linia"))
    with pg.expect_download() as dl:
        pg.click("#geoNet")
    dl.value.save_as(f.with_suffix(".geojson"))
    g = json.loads(f.with_suffix(".geojson").read_text(encoding="utf-8"))
    c0 = g["features"][0]["geometry"]["coordinates"][0][0]
    ok("eksport GeoJSON (współrzędne lon, lat w Polsce)", g["type"] == "FeatureCollection" and 14 < c0[0] < 25 and 48 < c0[1] < 55)
    pg.click("#closeDlg")
    pg.click("#modes button[data-mode='sim']")
    pg.wait_for_timeout(600)
    pg.click("#presets button[data-p='storm']")
    pg.wait_for_timeout(500)
    a1 = int(pg.locator("#kAlarm").inner_text().replace("\xa0", ""))
    pg.evaluate("(()=>{const e=document.querySelector('#sClim'); e.value=20; e.dispatchEvent(new Event('input'));})()")
    pg.wait_for_timeout(400)
    a2 = int(pg.locator("#kAlarm").inner_text().replace("\xa0", ""))
    ok(f"symulator: klimat +20% zwiększa alarmy ({a1}→{a2})", a2 > a1)
    ok("symulator: komunikat klimatyczny", "mocniejszych" in pg.locator("#climDelta").inner_text())
    pg.click("#modes button[data-mode='line']")
    pg.wait_for_timeout(500)
    pg.fill("#lineInput", "276")
    pg.press("#lineInput", "Enter")
    pg.locator("#lineInput").dispatch_event("change")
    pg.wait_for_timeout(800)
    ok("Moja linia: status", "Linia 276" in pg.locator("#lineStatus").inner_text())
    ok("Moja linia: tabela odcinków", pg.locator(".ltab tr").count() > 5)
    ok("Moja linia: kafelki trzech dni", pg.locator("#dayTiles .dt").count() == 3)
    pg.fill("#lineInput", "Kłodz")
    pg.wait_for_timeout(400)
    ok("Moja linia: podpowiedzi po nazwie stacji", pg.locator("#sugg button").count() >= 1 and "Kłodzko" in pg.locator("#sugg").inner_text())
    pg.fill("#lineInput", "276")
    pg.press("#lineInput", "Enter")
    pg.wait_for_timeout(600)
    ok("Moja linia: schemat liniowy (3 dni)", pg.locator("#lineStrip svg rect").count() >= 3 * 10)
    ok("Moja linia: sekcja obchodu", "odcinki do sprawdzenia" in pg.locator("#lineRounds").inner_text().lower())
    ok("Moja linia: ostrzeżenia IMGW wzdłuż linii", "Intensywne opady deszczu 2°" in pg.locator("#lineWarn").inner_text())
    with pg.expect_download() as dl:
        pg.click("#csvLine")
    f2 = ROOT / "build" / "e2e_line.csv"
    dl.value.save_as(f2)
    rows = f2.read_text(encoding="utf-8-sig").splitlines()
    ok(f"eksport CSV linii ({len(rows) - 1} wierszy)", len(rows) > 30 and ";276;" in rows[1])
    pg.evaluate("window.print = () => { window.__printed = true; }")
    pg.click("#cardBtn")
    ok("karta obchodu do druku", pg.evaluate("window.__printed") and "Karta obchodu" in pg.evaluate("document.querySelector('#printArea').innerText"))
    pg.locator(".ltab tr[data-i]").first.click()
    pg.wait_for_timeout(1200)
    ok("okno odcinka: ostrzeżenie IMGW dla powiatu", "IMGW" in pg.locator(".leaflet-popup").inner_text())
    pg.click("#theme")
    pg.wait_for_timeout(400)
    ok("przełączanie motywu", pg.evaluate("document.documentElement.dataset.theme") == "light")
    pg.click("#theme")
    pg.click("#helpBtn")
    ok("przycisk ? otwiera przewodnik", pg.locator("#tour").is_visible())
    pg.click("#tour [data-go='close']")
    ok("przewodnik zamyka się i zapamiętuje wybór", not pg.locator("#tour").is_visible() and pg.evaluate("localStorage.getItem('rs_tour')") == "1")
    ok("brak błędów JS (desktop)", not errs)
    if errs:
        print(errs[:5])
    ctx.close()

    ctx = b.new_context(viewport={"width": 1100, "height": 800})
    route_all(ctx)
    pg = ctx.new_page()
    pg.clock.set_fixed_time(NOW)
    pg.goto(BASE.replace("index.html", "") + "status.html")
    pg.wait_for_timeout(1200)
    t = pg.locator("#out").inner_text()
    ok("status.html: stan systemu i tabele", "przebiegów w dzienniku" in t and "Weryfikacja prospektywna" in t and "+25,0%" in t)
    ctx.close()

    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    route_all(ctx)
    pg = ctx.new_page()
    pg.clock.set_fixed_time(NOW)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "#mode=line&line=276")
    pg.wait_for_timeout(3000)
    ok("telefon: panel u dołu", pg.evaluate("document.getElementById('side').getBoundingClientRect().top") > 250)
    ok("telefon: brak poziomego przewijania", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    ok("telefon: status linii", "Linia 276" in pg.locator("#lineStatus").inner_text())
    ctx.close()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    route_all(ctx)
    pg = ctx.new_page()
    pg.clock.set_fixed_time(NOW)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "#tour=1")
    pg.wait_for_timeout(2500)
    box = pg.locator("#tour").bounding_box()
    ok("telefon: przewodnik mieści się na ekranie", box and box["x"] >= 0 and box["x"] + box["width"] <= 391 and box["y"] >= 40)
    ok("brak błędów JS (telefon)", not errs)
    ctx.close()

    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, color_scheme="dark")
    route_all(ctx)
    pg = ctx.new_page()
    pg.clock.set_fixed_time(NOW)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE)
    pg.wait_for_timeout(3000)
    ok("telefon: pierwsza wizyta zaczyna od mapy z przyciskiem „Sprawdź moją linię”", pg.evaluate("document.querySelector('#app').dataset.mode") == "live" and pg.locator(".cta").is_visible())
    ok("telefon: w pasku tylko 3 duże przyciski (Moja linia, Na żywo, Więcej)", pg.locator("#modes button:visible").count() == 3)
    ok("telefon: okno startowe nie zasłania ekranu", not pg.locator("#tour").is_visible())
    pg.click(".cta")
    pg.wait_for_timeout(900)
    ok("telefon: przycisk prowadzi do wyszukiwarki linii", pg.evaluate("document.querySelector('#app').dataset.mode") == "line" and pg.locator("#lineInput").is_visible())
    pg.fill("#lineInput", "Kłodz")
    pg.wait_for_timeout(500)
    ok("telefon: podpowiedzi po nazwie miejscowości", pg.locator("#sugg button").count() >= 1)
    pg.locator("#sugg button").first.click()
    pg.wait_for_timeout(1500)
    ok("telefon: wybór podpowiedzi pokazuje status linii", "Linia" in pg.locator("#lineStatus").inner_text() and pg.locator("#dayTiles .dt").count() == 3)
    box = pg.locator("#dayTiles").bounding_box()
    ok("telefon: kafelki trzech dni widać bez przewijania", box is not None and box["y"] + box["height"] <= 844)
    h = lambda q: pg.locator(q).first.bounding_box()["height"]
    ok("telefon: duże pola dotyku (wyszukiwarka, lokalizacja, kafelki ≥ 44 px)", h("#lineInput") >= 44 and h("#geoBtn") >= 44 and h("#dayTiles .dt") >= 44)
    ok("telefon: ostatnio używana linia jako przycisk", pg.locator("#recent button").count() >= 1)
    ok("telefon: brak poziomego przewijania po wyborze linii", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    pg.click("#moreBtn")
    pg.wait_for_timeout(300)
    ok("telefon: menu „Więcej” pokazuje pozostałe widoki", pg.locator("#moreMenu").is_visible() and "Symulator" in pg.locator("#moreMenu").inner_text())
    pg.locator("#moreMenu button[data-mode='sim']").click()
    pg.wait_for_timeout(900)
    ok("telefon: widok z menu „Więcej” otwiera się i jest oznaczony", pg.evaluate("document.querySelector('#app').dataset.mode") == "sim" and "Symulator" in pg.locator("#moreBtn").inner_text())
    pg.reload()
    pg.wait_for_timeout(3000)
    ok("telefon: kolejne wejście od razu w „Moja linia” z zapisaną linią", pg.evaluate("document.querySelector('#app').dataset.mode") == "line" and "Linia" in pg.locator("#lineStatus").inner_text())
    ok("brak błędów JS (telefon, wyszukiwarka)", not errs)
    ctx.close()

    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, color_scheme="dark",
                        geolocation={"latitude": 50.4345, "longitude": 16.6615}, permissions=["geolocation"])
    route_all(ctx)
    pg = ctx.new_page()
    pg.clock.set_fixed_time(NOW)
    pg.goto(BASE + "#mode=line")
    pg.wait_for_timeout(2500)
    pg.click("#geoBtn")
    pg.wait_for_timeout(2500)
    ok("telefon: „Gdzie jestem” wskazuje najbliższe linie", pg.locator("#near button").count() >= 1 and "Linia" in pg.locator("#lineStatus").inner_text())
    ctx.close()

    ctx = b.new_context(viewport={"width": 1280, "height": 800}, color_scheme="dark")
    pg = ctx.new_page()
    pg.goto(BASE)
    pg.wait_for_timeout(2500)
    pg.evaluate("navigator.serviceWorker.ready.then(() => 1)")
    cached = False
    for _ in range(40):
        cached = pg.evaluate("Promise.all(['about.html','status.html','offline.html'].map(u => caches.match(u))).then(r => r.every(Boolean))")
        if cached:
            break
        pg.wait_for_timeout(500)
    ok("offline: „O projekcie”, status i strona zastępcza są w pamięci aplikacji", cached)
    ctx.set_offline(True)
    pg.click("a.btn[href='about.html']")
    pg.wait_for_timeout(1500)
    ok("offline: „O projekcie” otwiera się z pamięci zamiast błędu przeglądarki", "o projekcie" in pg.title().lower())
    pg.goto(BASE.replace("index.html", "") + "nie-ma-takiej-strony.html", wait_until="domcontentloaded")
    pg.wait_for_timeout(800)
    ok("offline: nieznana strona pokazuje komunikat zamiast błędu", "Brak połączenia" in pg.inner_text("body"))
    pg.goto(BASE, wait_until="domcontentloaded")
    pg.wait_for_timeout(2500)
    ok("offline: aplikacja działa na zapisanej prognozie", pg.locator("#kAlarm").inner_text().strip() != "–")
    ctx.close()
    b.close()
print(f"\n{sum(r for _, r in res)}/{len(res)} testów OK")
sys.exit(0 if all(r for _, r in res) else 1)
