# Checklista zgłoszenia – „Kolej na bezpieczeństwo” (termin: 22.11.2026, do końca dnia)

## Do zrobienia przez Ciebie

- [ ] **Wpisz imię i nazwisko** i przebuduj PDF:
  `.venv/bin/python src/07_build_doc.py "Imię Nazwisko"`
- [ ] **Przeczytaj całą pracę** (`docs/RailSentinel_praca_konkursowa.pdf`). Musisz umieć obronić każde zdanie, bo Komisja może zaprosić do prezentacji (§7 ust. 2).
- [ ] **Załącznik nr 1 – formularz zgłoszeniowy:** pobierz ze strony konkursu i wypełnij.
- [ ] **Załącznik nr 2 – oświadczenia uczestnika:** podpisz. Dopuszczalne podpisy: kwalifikowany, zaufany (profil zaufany – najprościej) albo odręczny w formie skanu. **Przy odręcznym skanie trzeba też wysłać oryginały pocztą** na adres: IPR7 Biuro Spraw Pracowniczych, ul. Targowa 74, 03-734 Warszawa.
- [ ] **Nagraj wideo (MP4, max 5 min):** scenariusz w `docs/scenariusz_wideo.md`. Nagranie ekranu macOS: Cmd+Shift+5.
- [ ] **Spakuj kod:** ZIP bez `.venv/` i bez `data/raw/` (dane da się odtworzyć skryptami). Jeśli ZIP z PDF i wideo przekroczy 50 MB, wrzuć wideo na Google Drive lub OneDrive z dostępem bez logowania.
- [ ] **Wyślij** na **konkurs-studenci@plk-sa.pl** z tematem dokładnie:
  `Kolej na bezpieczeństwo – zgłoszenie konkursowe`
- [ ] Zachowaj potwierdzenie otrzymania (§6 ust. 5). Organizator może wezwać do uzupełnień w ciągu 3 dni roboczych.

## Odświeżenie prognozy „na żywo” przed wysłaniem / prezentacją

```bash
.venv/bin/python src/05_predict.py live
```

## Spakowanie kodu

```bash
cd ~/Desktop && zip -r RailSentinel_kod.zip RailSentinel -x "RailSentinel/.venv/*" "RailSentinel/data/raw/*" "RailSentinel/.claude/*"
```
