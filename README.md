# RailSentinel – prognoza zagrożeń infrastruktury kolejowej (72 h)

Prototyp na konkurs PLK „Kolej na bezpieczeństwo” (II edycja), wyzwanie **2: Czy AI może przewidzieć zagrożenie?**

**Aplikacja i strona: https://railsentinel.pl** · kopia na github.io (gdy nowa domena jest blokowana): https://maciejonisiewicz.github.io/railsentinel-app/ · film: https://railsentinel.pl/about.html

RailSentinel łączy prognozę pogody, ukształtowanie terenu, hydrografię i cechy infrastruktury, by codziennie
wskazywać – **dla każdego z 4606 odcinków sieci kolejowej w Polsce** – odcinki, na których w ciągu 72 h rośnie ryzyko:

- **ulewy i podmycia toru** (moduł A – model ML, gradient boosting z ograniczeniami monotoniczności),
- **fali wezbraniowej** na rzece (moduł B – **prognoza ML stanów 814 wodowskazów IMGW na 1–3 dni**),
- **wyboczenia toru bezstykowego** w upale (moduł fizyczny – temperatura szyny),
- **powalonych drzew / uszkodzeń sieci** przy wichurze (progi IMGW),
- **oblodzenia sieci trakcyjnej** (marznący opad).

Wynik jest podzielony na **obiekty i służby**: tor i nasyp (toromistrz), sieć trakcyjna (służba trakcji, tylko odcinki zelektryfikowane) oraz rozjazdy i srk (służba automatyki). Rozjazdy to **wskaźnik ekspozycji** (liczba rozjazdów z OSM razem ze śniegiem, marznącym opadem, mokrym śniegiem i mrozem z opadem oraz upałem), a nie prognoza awarii; progi to założenia robocze do kalibracji na rejestrze usterek srk PLK (`src/features.py`, stałe `SW_*`).

Dodatkowo aplikacja pobiera **oficjalne ostrzeżenia IMGW** (meteorologiczne i hydrologiczne) i zawęża je do konkretnych odcinków:
pokazuje, ile odcinków leży w powiatach objętych ostrzeżeniem i ile z nich RailSentinel wskazuje do sprawdzenia.
Każdy przebieg prognozy trafia do **publicznego dziennika** (gałąź `logs`), z którego powstaje weryfikacja prospektywna na stronie
`status.html`.

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
.venv/bin/python src/12_river_forecast.py      # ML: prognoza stanów rzek na 1-3 dni (cała Polska)
.venv/bin/python src/13_station_rain.py        # opad przy wodowskazach (posterunki IMGW), potem ponownie krok 12
.venv/bin/python src/04_train.py               # trening, walidacja 2024, niezależny test 1997 -> metrics.json
.venv/bin/python src/05_predict.py             # backtest 2024, upał, 1997, prognoza na żywo -> web/data
.venv/bin/python src/10_validate_modules.py    # walidacja modułów upału/wiatru (Eunice 2022, upał 2025)
.venv/bin/python -I src/16_powiaty.py          # granice powiatów (TERYT) i przypisanie odcinków – ostrzeżenia IMGW
.venv/bin/python src/11_export_model.py        # model ML do przeglądarki (symulator)
.venv/bin/python -I src/21_switches.py         # rozjazdy i wykolejnice z OSM (Overpass, kafelki 1°) -> data/processed/switches.json
.venv/bin/python -I src/22_places.py           # współrzędne miejscowości dla „Mojego rejonu” -> web/data/places.js
.venv/bin/python src/06_figures.py && .venv/bin/python src/07_build_doc.py "Imię Nazwisko"   # wykresy + PDF
open web/index.html                            # aplikacja (działa też bez serwera)
.venv/bin/python video/build_video.py          # film (wymaga: python3 -m http.server 8765 w katalogu projektu)
./deploy_site.sh                               # publikacja na GitHub Pages (railsentinel.pl)
```

Odświeżenie prognozy na żywo: `.venv/bin/python src/05_predict.py live`
(z dziennikiem: `RS_LOG_DIR=data/log`, potem `src/18_verify.py data/log/status.json` i `src/19_api.py <katalog>`).

Testy: `python -m unittest discover -s tests` (potok, dziennik, API, dokumenty) oraz
`python -m http.server 8765 &` i `python tests/e2e.py` (aplikacja w przeglądarce, 121 sprawdzeń, w tym filtr obiektów i „Mój rejon” na komputerze oraz telefonach 390×844 i 360×640). Oba zestawy działają w GitHub Actions
(`.github/workflows/ci.yml`). Szczegóły API: `docs/API.md`.

## Aplikacja (PWA) i strona

`web/` to jednocześnie strona internetowa i aplikacja instalowana na telefonie (manifest + Service Worker):
tryb **„Moja linia”** i **„Mój rejon”** dla kolejarzy (status linii albo wszystkich odcinków w promieniu 5, 10 lub 20 km od stacji, schemat liniowy, odcinki robocze do obchodu, karta obchodu do druku z kolumną „kto sprawdza”, „Gdzie jestem”, udostępnianie komunikatu, eksport CSV/GeoJSON), filtr obiektów (tor i nasyp, sieć trakcyjna, rozjazdy i srk) obok filtra zagrożeń,
praca bez zasięgu (ostatnia prognoza), szybki start na telefonie (wyszukiwarka linii, stacji i miejscowości, zapisane linie, kafelki 3 dni, „Gdzie jestem”), mapa całej Polski, ostrzeżenia IMGW, backtest 2024, test 1997, symulator, opis modelu, przewodnik dla nowych użytkowników, paleta dla daltonistów.
`web/status.html` – stan systemu i weryfikacja prospektywna; `railsentinel.pl/api/v1/` – statyczne API (JSON, GeoJSON, CSV).
`web/about.html` – strona projektu z filmem. Hosting: GitHub Pages (gałąź `gh-pages`), domena railsentinel.pl.

## Struktura

| Ścieżka | Zawartość |
|---|---|
| `src/` | potok danych, model, predykcje |
| `data/labels_flood_2024.json` | etykiety zniszczeń 09.2024 ze źródłami (trening) |
| `data/labels_flood_1997.json` | etykiety zniszczeń 07.1997 ze źródłami (niezależny test) |
| `data/processed/metrics.json` | wyniki walidacji |
| `web/` | dashboard (Leaflet, statyczny) + `sim.js` – model ML w przeglądarce (symulator) |
| `docs/` | praca konkursowa, załącznik techniczny, opis API, odpowiedzi dla jury |
| `video/` | film: `build_video.py` (montaż), `transkrypcja.py` (Whisper lokalnie), `redact.py` (rozmycie logo w tle nagrań); surowe nagrania z twarzą i modele są poza repozytorium (`.gitignore`) |
| `tests/` | testy jednostkowe i testy aplikacji w przeglądarce |
| `web/vendor/leaflet/` | biblioteka mapy Leaflet 1.9.4 (BSD-2, kopia lokalna, suma SHA-512 zgodna z cdnjs) |
| `mirror/` | zestaw kopii lustrzanej strony na github.io (workflow, skrypt `setup_mirror.sh`); kopia działa: https://maciejonisiewicz.github.io/railsentinel-app/ |
| gałąź `logs` | dziennik przebiegów prognozy (JSON), źródło weryfikacji prospektywnej |

## Źródła danych i licencje (§10 ust. 9 Regulaminu)

| Źródło | Zastosowanie | Licencja |
|---|---|---|
| OpenStreetMap (Overpass API) | geometria linii, mosty/nasypy/przekopy, rzeki, miejscowości, rozjazdy i wykolejnice (`railway=switch`, `railway=derail`) | ODbL 1.0 |
| IMGW-PIB – dane publiczne (danepubliczne.imgw.pl) | dobowe opady z posterunków, dobowe stany wód, API hydro na żywo | dane publiczne IMGW-PIB, wymagane wskazanie źródła |
| Open-Meteo Archive API (ERA5, ECMWF/Copernicus) | historia pogody 2021–2024, 1997 | CC BY 4.0 |
| Open-Meteo Previous Runs API (ECMWF IFS 0.25°) | archiwalne prognozy do backtestu | CC BY 4.0 |
| Open-Meteo Forecast API | prognoza bieżąca | CC BY 4.0 |
| AWS Terrain Tiles (Mapzen; SRTM, EU-DEM i in.) | model wysokościowy | licencje otwarte źródeł, wymagana atrybucja |
| IMGW-PIB – API ostrzeżeń (`warningsmeteo`, `warningshydro`) | oficjalne ostrzeżenia w aplikacji i w dzienniku | dane publiczne IMGW-PIB, wymagane wskazanie źródła |
| polska-geojson (ppatrzyk) | granice 380 powiatów (przypisanie ostrzeżeń do odcinków) | MIT |
| Wikidata | kody TERYT powiatów | CC0 |
| Natural Earth | granica Polski | domena publiczna |
| Esri World Gray Canvas | podkład mapy w dashboardzie | atrybucja Esri/OSM |
| PAP, PLK, gov.pl, „Z Biegiem Szyn” nr 133 | komunikaty o zniszczeniach 2024 i 1997 (etykiety) | cytowane jako źródła faktów |
| Polsat News, Sejm RP (interpelacja) | zdarzenia do walidacji modułów (Eunice 2022, upał 2025) | cytowane jako źródła faktów |

Biblioteki: scikit-learn (BSD-3), pandas (BSD-3), NumPy (BSD-3), requests (Apache-2.0), Pillow (HPND),
matplotlib (PSF-like), Leaflet (BSD-2).

Prototyp studencki – nie jest systemem operacyjnym PKP PLK S.A.
