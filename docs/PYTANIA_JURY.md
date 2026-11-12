# Pytania, które może zadać jury (i krótkie, uczciwe odpowiedzi)

Komisja może zaprosić do prezentacji (§7 ust. 2 Regulaminu). Poniżej pytania, których można się spodziewać, wraz z odpowiedziami opartymi na pracy. Każdą liczbę można znaleźć w pracy (numer rozdziału w nawiasie).

## Liczby do zapamiętania

| Co | Wartość |
|---|---|
| Sieć w systemie | 4606 odcinków, 27 293 km torów, 647 linii, 814 wodowskazów IMGW |
| Powódź 2024, prognoza z wieczora 11.09 | alarm na 3,3% sieci, w tym **31 z 37** zniszczonych odcinków, **52 h** przed zniszczeniami; pozostałe 6 w prognozach z 12 i 13.09 (rozdz. 05, 08) |
| Wszystkie 37 zniszczonych odcinków | z alarmem w prognozie z 13.09, ok. 4 h przed (rozdz. 08) |
| Cena skuteczności (próg 0,5, prognoza z 11.09) | 119 alarmów bez potwierdzonego zniszczenia, 4,8 odcinka do sprawdzenia na 1 trafny (rozdz. 08) |
| Powódź 1997 (bez douczania) | 3 z 3 miejsc zniszczeń, ale dopiero z modułem fali; sam model ML: 0 z 3 (rozdz. 06) |
| Zwykłe dni (IV–X 2021–2023) | ok. 0,31 alarmu na 1000 odcinko-dni, czyli jeden odcinek co 3,5 dnia w całym regionie (rozdz. 08) |
| Prognoza rzek, 2 dni, test 2024 | wykrywa o 46% więcej przekroczeń niż „bez zmian”, ale przy idealnym opadzie i pełnej historii (Załącznik A2, A3) |

## Pytania

**1. Czym to się różni od ostrzeżeń IMGW?**
IMGW mówi, gdzie i ile spadnie (powiat, rzeka). RailSentinel korzysta z tych samych prognoz i mówi, który odcinek toru, dlaczego i w jakiej kolejności sprawdzić. Przykład na żywo (12.11.2026): ostrzeżenie 1° dla 9 powiatów obejmowało 71 odcinków, RailSentinel wskazał z nich 0. W 2024 r. IMGW ostrzegało całe województwo, a system wskazał 3,3% sieci, z czego 31 z 37 odcinków faktycznie zniszczonych (26 razy lepiej niż losowo). Nie zastępuje ostrzeżeń, tylko je uzupełnia.

**2. Skąd wiadomo, że to działa, a nie tylko pasuje do jednej powodzi?**
Backtest 2024 używa wyłącznie archiwalnych prognoz ECMWF, a odcinek ocenia model, który nie widział jego linii (GroupKFold). Do tego test na powodzi 1997 i trzech zdarzeniach 2010 bez douczania oraz 7 orkanów. Uczciwie: etykiety są tylko z jednej powodzi (2024), a zdarzenia 1997 i 2010 to testy na reanalizie, nie na prawdziwych prognozach. Dlatego od 12.11.2026 prowadzę publiczny dziennik prognoz i weryfikuję je na bieżąco (status.html).

**3. „37 z 37” i „52 godziny” to ta sama liczba?**
Nie. Z prognozą z wieczora 11.09 (52 h przed) alarm miało 31 z 37 odcinków. Pozostałe 6 dostało alarm w prognozie z 12–13.09, czyli później. Wszystkie 37 miało alarm przed zniszczeniem, ale nie wszystkie 52 godziny wcześniej.

**4. Ile jest fałszywych alarmów?**
Zależy od progu (rozdz. 08). Przy domyślnym progu 0,5 i prognozie z 11.09: 31 trafnych alarmów, 119 odcinków bez potwierdzonego zniszczenia, czyli 4,8 odcinka do sprawdzenia na jeden trafny. Część z tych „fałszywych” mogła być zalana lub zamknięta, ale liczę je jako fałszywe, żeby nie zawyżać wyniku. W zwykłe dni system alarmuje rzadko: ok. 0,31 alarmu na 1000 odcinko-dni.

**5. Czy model nie jest przeuczony?**
Walidacja po liniach, test 1997 bez douczania i porównanie z regułą opadową. Sam model ML nie wykrył powodzi 1997, bo uczył się mechanizmu podgórskiego (ulewa), a w 1997 zniszczyła mosty fala na nizinnej Odrze. Dlatego jest drugi moduł (fala wezbraniowa) z progiem ustalonym z góry. Nie ukrywam tego w pracy.

**6. Dlaczego nie głębokie sieci neuronowe?**
Mało etykiet (jedna powódź), a w bezpieczeństwie liczy się wyjaśnialność. Gradient boosting z wymuszoną monotonicznością jest przejrzysty (ryzyko nie spada, gdy rośnie opad), a każdy alarm ma listę przyczyn. Komunikaty są z szablonów, bez generatywnego modelu językowego, więc bez „halucynacji”.

**7. Kto podejmuje decyzję? Czy system czymś steruje?**
Decyzję podejmuje uprawniony pracownik. System niczym nie steruje, nie jest połączony z urządzeniami srk, tylko odczytuje dane publiczne. Proponuję pilotaż „w cieniu” (30 dni, bez wpływu na ruch), a dopiero po ocenie szerszy test.

**8. Dane z OpenStreetMap to nie ewidencja PLK. Czy kilometraż jest wiarygodny?**
Kilometraż pochodzi ze słupków OSM dla 92% odcinków i jest orientacyjny (tak jest opisany w aplikacji i na wydruku). Wdrożenie wymaga ewidencji PLK (kilometraż, obiekty, przepusty); architektura jest na to gotowa.

**9. Co z bezpieczeństwem cybernetycznym?**
Aplikacja to statyczna strona i pliki. Nie ma kont, haseł ani zapisu danych użytkownika; lokalizacja „Gdzie jestem” jest używana tylko w przeglądarce. W środowisku PLK system działałby w osobnej strefie, tylko z odczytem danych.

**10. A burze lokalne, mniejsze niż siatka 25 km?**
To ograniczenie (rozdz. 14). Częściowo pokrywa je moduł fali na wodowskazach i ostrzeżenia IMGW pokazane przy odcinku. Następny krok: nowcasting radarowy IMGW (0–6 h) i prognozy o rozdzielczości ok. 2 km.

**11. Co się dzieje, gdy brakuje danych lub prognoza jest stara?**
Aplikacja pokazuje czerwony komunikat „prognoza nieaktualna” (po 30 godzinach), odcinki bez danych są szare i nigdy nie są pokazane jako niskie ryzyko, a raport dla dyżurnego zaczyna się od stanu danych.

**12. Dlaczego upał, wiatr i oblodzenie to reguły, a nie ML?**
Brak etykiet. Moduły oparte są na progach IMGW i fizyce szyny, zweryfikowane na 7 orkanach i upale 2025. Po podłączeniu rejestru zdarzeń PLK można je skalibrować (rozdz. 14). Ostrzeżenia IMGW o śniegu i mrozie pokazuję jako informację oficjalną, bo własnej prognozy dla nich nie mam.

**13. Jaki jest model biznesowy i ile to kosztuje?**
Koszt uruchomienia prototypu to domena (hosting 0 zł). System zwraca się, jeśli rocznie pozwoli uniknąć 0,1–0,3% strat jednej powodzi na skalę 2024 (rozdz. 13; ceny subskrypcji to założenie, oznaczone w pracy).

**14. Czy kod napisał asystent AI?**
Tak, korzystałem z asystenta AI (Claude, Anthropic) jako narzędzia programistycznego i wprost to deklaruję w rozdz. 16 (§10 ust. 9 Regulaminu). Całość zintegrowałem sam i potrafię wyjaśnić każdy element: dane, model, walidację i aplikację.

**15. Kim byli rozmówcy z filmu i co zmieniłeś po rozmowach?**
(Uzupełnić po wywiadach: stanowisko i staż każdego rozmówcy oraz zmiany w aplikacji lub pracy wynikające z uwag. W filmie rozmówcy są opisani tylko stanowiskiem i stażem.)

**16. Co dalej?**
Pilotaż na jednej linii (np. 276), dostęp do ewidencji i rejestru zdarzeń PLK, kalibracja progów z zespołami utrzymania, nowcasting radarowy i mapa zadrzewień (rozdz. 11, 14).
