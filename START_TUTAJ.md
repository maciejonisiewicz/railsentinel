# RailSentinel – START TUTAJ

Wszystko jest gotowe do wysłania na konkurs PKP PLK „Kolej na bezpieczeństwo” (termin: **22.11.2026, do końca dnia**).

## 1. Co sprawdzić (ok. 15 minut)

| Co | Gdzie | Na co patrzeć |
|---|---|---|
| **Strona i aplikacja** | https://railsentinel.pl (zapasowo: https://maciejonisiewicz.github.io/railsentinel/) | Zakładki: Na żywo, Moja linia, Powódź 2024 (przycisk ▶ na osi czasu), Symulator, Upał (cała Polska), Powódź 1997; kliknij odcinek na liście lub mapie |
| **Na telefonie** | ten sam adres w Chrome / Safari | „Moja linia” → wpisz np. `276` albo „📍 Gdzie jestem”; zainstaluj: menu → „Dodaj do ekranu głównego” |
| **Strona projektu z filmem** | https://railsentinel.pl/about.html | Odtwarza się film, linki do PDF i kodu |
| **Film** | `video/RailSentinel_film.mp4` | Lektor, muzyka, przejścia, ok. 3,5 min |
| **Praca konkursowa** | `docs/RailSentinel_praca_konkursowa.pdf` | 14 stron (limit 15); przeczytaj całość – Komisja może zaprosić na prezentację |
| **Kod** | https://github.com/maciejonisiewicz/railsentinel | Publiczne repozytorium |

> **Ważne:** sprawdziłem, że strona działa w internecie (HTTPS, certyfikat wystawiony), ale **sieć, z której korzysta Twój
> komputer (prawdopodobnie akademik), blokuje świeżo zarejestrowane domeny** – na tym komputerze railsentinel.pl może
> się nie otwierać („Web Page Blocked” / zerwane połączenie). **Sprawdź na telefonie przez dane komórkowe (wyłącz Wi-Fi).**
> Jury otworzy stronę normalnie. Kopia lokalna: `web/index.html` (otwiera się z dysku).

## 2. Co musisz zrobić Ty (ok. 20 minut)

1. **Pobierz załączniki** ze strony konkursu (https://www.plk-sa.pl/konkurs-dla-studentow-kolej-na-bezpieczenstwo):
   **Załącznik nr 1** (formularz zgłoszeniowy) i **Załącznik nr 2** (oświadczenia).
2. **Wypełnij i podpisz** – najprościej **profilem zaufanym** (gov.pl → „Podpisz dokument elektronicznie”).
   Przy podpisie odręcznym (skan) trzeba też wysłać **oryginały pocztą**: IPR7 Biuro Spraw Pracowniczych, ul. Targowa 74, 03-734 Warszawa.
3. **Wyślij maila** – gotowa treść: `docs/MAIL_DO_WYSLANIA.md`. Adres: **konkurs-studenci@plk-sa.pl**,
   temat dokładnie: **Kolej na bezpieczeństwo – zgłoszenie konkursowe**.
   Załączniki: PDF pracy + 2 podpisane załączniki. Film i kod przez link (mail max 50 MB).
4. Zachowaj potwierdzenie otrzymania zgłoszenia.

## 3. Co zrobiłem podczas Twojej nieobecności

- **Nowy model ML – prognoza stanów rzek na 1–3 dni** dla 814 wodowskazów IMGW w całej Polsce. Model sam wybiera
  „zwiastuny” fali w górnym biegu rzeki. W powodzi 2024 z 2-dniowym wyprzedzeniem wykrywa **o 46% więcej**
  przekroczeń stanu wody niż założenie „rzeka się nie zmieni” (i podobnie w 1997 r.).
- **Cała Polska**: 4606 odcinków, 27 293 km torów, 647 linii, 845 wodowskazów; prognoza na żywo dla całego kraju
  (pogoda Open-Meteo + bieżące stany wód z API IMGW + prognoza rzek ML).
- **Aplikacja (PWA)** – strona, która instaluje się jak aplikacja na Androidzie, iPhonie i komputerze, działa bez zasięgu.
  Nowy tryb **„Moja linia”** dla kolejarzy: status linii, każdy odcinek na 3 dni, „Gdzie jestem”, „Udostępnij komunikat”.
- **Wdrożenie**: repozytorium GitHub + GitHub Pages (0 zł) pod Twoją domeną **railsentinel.pl** (rekordy DNS ustawiłeś w OVH).
- **Film** (MP4, 1920×1080): animowane plansze, nagrania prawdziwej aplikacji, lektor (neuronowy polski głos Microsoft „Marek”),
  muzyka skomponowana algorytmicznie (bez problemów z prawami autorskimi), płynne przejścia.
- **Praca konkursowa** zaktualizowana: nowe rozdziały 08 (prognoza rzek) i 09 (cała Polska i aplikacja), aktualne wyniki.
- **Poprawki jakości** wychwycone przy sprawdzaniu: moduł oblodzenia dawał fałszywe alarmy przy każdej mżawce
  (teraz alarm tylko przy prognozowanym marznącym deszczu), kontrola jakości odczytów wodowskazów na żywo
  (np. Głuchołazy po odbudowie mają nowe zero), trening tylko na obszarze ze zweryfikowanymi etykietami.

## 4. Najważniejsze wyniki (do zapamiętania na ewentualną prezentację)

| | Wynik |
|---|---|
| Powódź 2024, backtest na archiwalnych prognozach ECMWF | **37/37** zniszczonych odcinków z alarmem, mediana **52 h** wcześniej |
| Powódź 1997 – niezależny test (model jej nie widział) | **3/3** miejsca zniszczeń wykryte |
| Trafność w strefie ulewy (AUC) | **0,948** vs 0,864 dla reguły „dużo deszczu” |
| Zbędne alarmy w dniach powodzi | **6,5%** sieci vs 27% dla reguły (4× mniej) |
| Prognoza rzek, 2 dni wcześniej | **66%** vs 45% wykrytych przekroczeń (+46%) |
| Orkan Eunice 19.02.2022 | moduł wiatru: 2. najgorszy dzień z 1096 |

**Uczciwie o ograniczeniach** (są opisane w pracy): etykiety tylko z dwóch powodzi; model ML zna mechanizm podgórski
(na nizinach pracuje moduł fali); w teście prognozy rzek opad przyszły jest „idealny”; moduł upału jest ostrożny.

## 5. Jak to działa – w skrócie

`src/` – potok danych i modele (kroki 01–13), `web/` – aplikacja i strona, `docs/` – praca konkursowa,
`video/` – skrypty filmu. Szczegóły i polecenia: `README.md`.

**Odświeżenie prognozy na żywo na stronie** (np. przed prezentacją):

```bash
cd ~/Desktop/RailSentinel && .venv/bin/python src/05_predict.py live && ./deploy_site.sh
```
