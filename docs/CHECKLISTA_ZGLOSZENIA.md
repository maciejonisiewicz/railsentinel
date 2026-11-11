# Checklista zgłoszenia – „Kolej na bezpieczeństwo” (termin: 22.11.2026, do końca dnia)

## Do zrobienia przez Ciebie

- [x] Imię i nazwisko w PDF (Maciej Onisiewicz)
- [x] Strona i aplikacja online: https://railsentinel.pl
- [x] Film: `video/RailSentinel_film.mp4` (też na railsentinel.pl/about.html)
- [x] Kod: https://github.com/maciejonisiewicz/railsentinel
- [ ] **Przeczytaj całą pracę** (`docs/RailSentinel_praca_konkursowa.pdf`). Musisz umieć obronić każde zdanie, bo Komisja może zaprosić do prezentacji (§7 ust. 2).
- [ ] **Załącznik nr 1 – formularz zgłoszeniowy:** pobierz ze strony konkursu i wypełnij.
- [ ] **Załącznik nr 2 – oświadczenia uczestnika:** podpisz. Dopuszczalne podpisy: kwalifikowany, zaufany (profil zaufany – najprościej) albo odręczny w formie skanu. **Przy odręcznym skanie trzeba też wysłać oryginały pocztą** na adres: IPR7 Biuro Spraw Pracowniczych, ul. Targowa 74, 03-734 Warszawa.
- [ ] **Obejrzyj film** (`video/RailSentinel_film.mp4`) – jest gotowy, nagrywać nic nie trzeba.
- [x] Kod spakowany: `RailSentinel_kod.zip` na Pulpicie (oraz publiczne repozytorium). Film i kod podajesz w mailu jako linki.
- [ ] **Wyślij** (gotowa treść: `docs/MAIL_DO_WYSLANIA.md`) na **konkurs-studenci@plk-sa.pl** z tematem dokładnie:
  `Kolej na bezpieczeństwo – zgłoszenie konkursowe`
- [ ] Zachowaj potwierdzenie otrzymania (§6 ust. 5). Organizator może wezwać do uzupełnień w ciągu 3 dni roboczych.

## Odświeżenie prognozy „na żywo” przed wysłaniem / prezentacją

```bash
.venv/bin/python src/05_predict.py live
```

## Spakowanie kodu

```bash
cd ~/Desktop && zip -r RailSentinel_kod.zip RailSentinel -x "RailSentinel/.venv/*" "RailSentinel/data/raw/*"
```
