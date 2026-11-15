# RailSentinel: statyczne API (v1)

Po każdym przebiegu prognozy (dwa razy na dobę, ok. 4:15 i 16:15) na stronie pojawiają się pliki z listą odcinków zagrożonych w ciągu 72 godzin. To zwykłe pliki, więc czytają je Excel, QGIS, skrypty i dowolne systemy bez logowania i bez serwera po stronie odbiorcy. Nagłówek `Access-Control-Allow-Origin: *` pozwala pobierać je także z przeglądarki.

| Plik | Zawartość |
|---|---|
| `https://railsentinel.pl/api/v1/alarms.json` | odcinki UWAGA i ALARM na 3 dni, z kilometrażem, przyczyną, pewnością i ostrzeżeniami IMGW |
| `https://railsentinel.pl/api/v1/alarms.geojson` | ta sama lista z geometrią (MultiLineString, WGS 84, kolejność lon, lat) |
| `https://railsentinel.pl/api/v1/alarms.csv` | ta sama lista dla Excela (UTF-8 z BOM, separator „;”, przecinek dziesiętny) |
| `https://railsentinel.pl/api/v1/lines.json` | status każdej z 647 linii na 3 dni: najwyższe ryzyko i najgorszy odcinek |
| `https://railsentinel.pl/data/status.json` | stan systemu i weryfikacja prospektywna (strona `status.html`) |

## Pola rekordu odcinka

| Pole | Znaczenie |
|---|---|
| `priorytet` | kolejność weryfikacji w danym dniu (1 = najpierw) |
| `dzien` | data, której dotyczy prognoza |
| `linia`, `km_od`, `km_do`, `od`, `do`, `miejscowosc`, `rzeka`, `powiat` | lokalizacja odcinka (kilometraż orientacyjny, z OpenStreetMap) |
| `poziom` | `ALARM` (ryzyko ≥ 0,5), `UWAGA` (≥ 0,3) lub `niskie` |
| `ryzyko_proc` | ryzyko łączne w procentach |
| `zagrozenie` | dominujące zagrożenie: woda, upał, wiatr, oblodzenie |
| `woda_proc`, `upal_proc`, `wiatr_proc`, `lod_proc` | ryzyko wg mechanizmu |
| `opad_1d_mm`, `opad_3d_mm`, `porywy_kmh`, `szyna_C` | prognozowane wartości pogodowe |
| `pewnosc` | wysoka, średnia, niższa (maleje z wyprzedzeniem; niższa przy braku stanu wody) lub brak oceny |
| `ostrzezenia_imgw` | oficjalne ostrzeżenia IMGW obowiązujące w powiecie odcinka tego dnia |
| `prognoza_wydana` | data i godzina przebiegu |
| `id` | stały identyfikator odcinka |
| `obiekt` | obiekt o najwyższym ryzyku (≥ 15%): tor i nasyp, sieć trakcyjna albo rozjazdy i srk; puste, gdy żaden nie przekracza progu |
| `sluzba` | służba, która sprawdza ten obiekt: toromistrz, służba trakcji lub służba automatyki (srk) |
| `tor_proc` | ryzyko dla toru i nasypu (woda, upał, wiatr) w procentach |
| `trakcja_proc` | ryzyko dla sieci trakcyjnej (wiatr, oblodzenie) w procentach; 0 na odcinkach bez sieci |
| `rozjazdy_wskaznik_proc` | **wskaźnik ekspozycji** rozjazdów i srk w procentach (liczba rozjazdów z OSM razem z pogodą: śnieg, marznący opad, mokry śnieg i mróz z opadem, upał). To heurystyka, nie prognoza awarii; progi to założenia robocze do kalibracji na rejestrze usterek srk PLK |
| `rozjazdy_liczba` | liczba rozjazdów i wykolejnic z OpenStreetMap przypisanych do odcinka (niepełna) |
| `elektryfikacja_proc` | udział długości odcinka z siecią trakcyjną w procentach |

Pola od `obiekt` do `elektryfikacja_proc` zostały dodane po rozmowach z kolejarzami; dotychczasowe pola i ich kolejność nie zmieniły się. Wskaźnik rozjazdów nie wchodzi do `ryzyko_proc` ani do `poziom`, więc lista UWAGA i ALARM jest taka jak wcześniej.

## Przykłady

Excel: Dane → Z tekstu/CSV → wskaż `alarms.csv` (separator: średnik).

QGIS: Warstwa → Dodaj warstwę → Dodaj warstwę wektorową → `alarms.geojson`.

Python:

```python
import requests
d = requests.get("https://railsentinel.pl/api/v1/alarms.json", timeout=30).json()
for dzien in d["dni"]:
    print(dzien["date"], dzien["alarm"], "ALARM,", dzien["warn"], "UWAGA")
```

## Zasady

- API nie wymaga rejestracji i niczym nie steruje: tylko udostępnia wyniki.
- Wersja `v1` zachowuje nazwy pól. Zmiany niekompatybilne pojawią się pod `v2`.
- Wyniki: licencja CC BY 4.0 (wskazanie źródła: RailSentinel, railsentinel.pl). Dane źródłowe: IMGW-PIB, Open-Meteo (CC BY 4.0), OpenStreetMap (ODbL).
- Prototyp studencki. Wspiera ocenę zagrożenia i nie zastępuje procedur ani ostrzeżeń IMGW. Decyzję podejmuje uprawniony pracownik.
- Brak pliku lub nieaktualna data `prognoza_wydana` oznacza brak aktualnej prognozy: brak alarmu nie oznacza wtedy braku zagrożenia.
