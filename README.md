# RailSentinel – prognoza zagrożeń infrastruktury kolejowej (72 h)

Prototyp na konkurs PLK „Kolej na bezpieczeństwo” (II edycja), wyzwanie **2: Czy AI może przewidzieć zagrożenie?**

RailSentinel łączy prognozę pogody, ukształtowanie terenu, hydrografię i cechy infrastruktury, by codziennie
wskazywać odcinki linii kolejowych, na których w ciągu 72 h rośnie ryzyko:

- **ulewy i podmycia toru** (moduł A – model ML, gradient boosting z ograniczeniami monotoniczności),
- **fali wezbraniowej** na rzece (moduł B – stany wód z ~200 wodowskazów IMGW),
- **wyboczenia toru bezstykowego** w upale (moduł fizyczny – temperatura szyny),
- **powalonych drzew / uszkodzeń sieci** przy wichurze (progi IMGW),
- **oblodzenia sieci trakcyjnej** (marznący opad).

Backtest na powodzi z września 2024 r. z użyciem **archiwalnych prognoz ECMWF** (tych, które były dostępne
przed powodzią) pokazuje, z jakim wyprzedzeniem system wskazałby odcinki, które faktycznie uległy zniszczeniu.

## Uruchomienie

```bash
python3 -m venv .venv && .venv/bin/pip install pandas numpy scikit-learn requests pillow matplotlib
.venv/bin/python src/01_build_segments.py      # odcinki sieci z OSM
.venv/bin/python src/02_static_features.py     # teren (DEM), rzeki, miejscowości
.venv/bin/python src/03_weather.py 2021 2022 2023 2024   # historia pogody ERA5 (+ 1997, zdarzenia)
.venv/bin/python src/08_gauges.py              # posterunki opadowe IMGW -> opad na odcinkach
.venv/bin/python src/09_hydro.py               # wodowskazy IMGW -> indeks stanu wody (moduł B)
.venv/bin/python src/04_train.py               # trening, walidacja 2024, niezależny test 1997 -> metrics.json
.venv/bin/python src/05_predict.py             # backtest 2024, upał, 1997, prognoza na żywo -> web/data
.venv/bin/python src/10_validate_modules.py    # walidacja modułów upału/wiatru (Eunice 2022, upał 2025)
.venv/bin/python src/11_export_model.py        # model ML do przeglądarki (symulator)
.venv/bin/python src/06_figures.py && .venv/bin/python src/07_build_doc.py "Imię Nazwisko"   # wykresy + PDF
open web/index.html                            # dashboard (działa bez serwera)
```

Odświeżenie prognozy na żywo: `.venv/bin/python src/05_predict.py live`

## Struktura

| Ścieżka | Zawartość |
|---|---|
| `src/` | potok danych, model, predykcje |
| `data/labels_flood_2024.json` | etykiety zniszczeń 09.2024 ze źródłami (trening) |
| `data/labels_flood_1997.json` | etykiety zniszczeń 07.1997 ze źródłami (niezależny test) |
| `data/processed/metrics.json` | wyniki walidacji |
| `web/` | dashboard (Leaflet, statyczny) + `sim.js` – model ML w przeglądarce (symulator) |
| `docs/` | praca konkursowa |

## Źródła danych i licencje (§10 ust. 9 Regulaminu)

| Źródło | Zastosowanie | Licencja |
|---|---|---|
| OpenStreetMap (Overpass API) | geometria linii, mosty/nasypy/przekopy, rzeki, miejscowości | ODbL 1.0 |
| IMGW-PIB – dane publiczne (danepubliczne.imgw.pl) | dobowe opady z posterunków, dobowe stany wód, API hydro na żywo | dane publiczne IMGW-PIB, wymagane wskazanie źródła |
| Open-Meteo Archive API (ERA5, ECMWF/Copernicus) | historia pogody 2021–2024, 1997 | CC BY 4.0 |
| Open-Meteo Previous Runs API (ECMWF IFS 0.25°) | archiwalne prognozy do backtestu | CC BY 4.0 |
| Open-Meteo Forecast API | prognoza bieżąca | CC BY 4.0 |
| AWS Terrain Tiles (Mapzen; SRTM, EU-DEM i in.) | model wysokościowy | licencje otwarte źródeł, wymagana atrybucja |
| Natural Earth | granica Polski | domena publiczna |
| Esri World Gray Canvas | podkład mapy w dashboardzie | atrybucja Esri/OSM |
| PAP, PLK, gov.pl, „Z Biegiem Szyn” nr 133 | komunikaty o zniszczeniach 2024 i 1997 (etykiety) | cytowane jako źródła faktów |
| Polsat News, Sejm RP (interpelacja) | zdarzenia do walidacji modułów (Eunice 2022, upał 2025) | cytowane jako źródła faktów |

Biblioteki: scikit-learn (BSD-3), pandas (BSD-3), NumPy (BSD-3), requests (Apache-2.0), Pillow (HPND),
matplotlib (PSF-like), Leaflet (BSD-2).

Prototyp studencki – nie jest systemem operacyjnym PKP PLK S.A.
