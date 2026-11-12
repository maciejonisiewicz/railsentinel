# Checklista zgłoszenia – „Kolej na bezpieczeństwo” (termin: 22.11.2026, do końca dnia)

## Do zrobienia przez Ciebie

- [x] Imię i nazwisko w PDF (Maciej Onisiewicz)
- [x] Strona i aplikacja online: https://railsentinel.pl
- [x] Film: `video/RailSentinel_film.mp4` (też na railsentinel.pl/about.html)
- [x] Kod: https://github.com/maciejonisiewicz/railsentinel
- [x] Praca: 15 stron (limit regulaminu: 15 stron dokumentu); załącznik techniczny jako materiał uzupełniający
- [ ] **Film ≤ 5 minut** – sprawdź długość po wmontowaniu wywiadów
- [ ] **Załączniki w mailu ≤ 50 MB** (PDF ok. 5 MB + załącznik ok. 2 MB + podpisane dokumenty) – film tylko jako link
- [ ] **Zgody osób z wywiadów** – zdjęcia podpisanych kartek zachowaj u siebie; w filmie tylko wariant, na który się zgodzili
- [ ] **Licencje i źródła** – rozdz. 16 pracy (wymóg §10 ust. 9); zdanie o autorstwie kodu w rozdz. 16 – zdecyduj o brzmieniu
- [ ] **Prototyp bez logowania** – otwórz railsentinel.pl na telefonie (dane komórkowe) i sprawdź datę prognozy (aktualizuje się dwa razy na dobę, ok. 4:15 i 16:15)
- [ ] **Zajrzyj na railsentinel.pl/status.html** (od 13.11): dziennik powinien rosnąć o 1–2 przebiegi na dobę. Jeśli długo nie ma nowych wpisów, uruchom ręcznie workflow „Codzienna prognoza”.
- [ ] **19.11: przebuduj PDF z aktualnym dziennikiem** (tabela weryfikacji prospektywnej w rozdz. 15 i w załączniku A3 zasila się z `status.json`).
- [ ] **Przeczytaj całą pracę** (`docs/RailSentinel_praca_konkursowa.pdf`). Musisz umieć obronić każde zdanie, bo Komisja może zaprosić do prezentacji (§7 ust. 2).
- [ ] **Załącznik nr 1 – formularz zgłoszeniowy:** pobierz ze strony konkursu i wypełnij.
- [ ] **Załącznik nr 2 – oświadczenia uczestnika:** podpisz. Dopuszczalne podpisy: kwalifikowany, zaufany (profil zaufany – najprościej) albo odręczny w formie skanu. **Przy odręcznym skanie trzeba też wysłać oryginały pocztą** na adres: IPR7 Biuro Spraw Pracowniczych, ul. Targowa 74, 03-734 Warszawa.
- [ ] **Obejrzyj film** (`video/RailSentinel_film.mp4`) – jest gotowy, nagrywać nic nie trzeba.
- [x] Kod spakowany: `RailSentinel_kod.zip` na Pulpicie (oraz publiczne repozytorium). Film i kod podajesz w mailu jako linki.
- [ ] **Wyślij** (gotowa treść: `docs/MAIL_DO_WYSLANIA.md`) na **konkurs-studenci@plk-sa.pl** z tematem dokładnie:
  `Kolej na bezpieczeństwo – zgłoszenie konkursowe`
- [ ] Zachowaj potwierdzenie otrzymania (§6 ust. 5). Organizator może wezwać do uzupełnień w ciągu 3 dni roboczych.

## Prognoza „na żywo”

Odświeża się sama dwa razy na dobę, ok. 4:15 i 16:15 (GitHub Actions). Ręcznie: zakładka Actions w repozytorium → „Codzienna prognoza” → Run workflow.

## Spakowanie kodu

```bash
cd ~/Desktop && zip -r RailSentinel_kod.zip RailSentinel -x "RailSentinel/.venv/*" "RailSentinel/data/raw/*"
```
