# Dlaczego railsentinel.pl nie otwiera się w niektórych sieciach i co z tym zrobić

## Co się dzieje

Z sieci PWr strona nie otwiera się, a przeglądarka pisze, że nie jest bezpieczna albo zrywa połączenie. Sprawdziłem to z Twojego komputera: serwer GitHub Pages jest w porządku (certyfikat ważny do 02.2027, HTTPS wymuszony, DNS poprawny), ale filtr sieci PWr odpowiada stroną „Web Page Blocked … Category: **high-risk**” i zrywa połączenie HTTPS. To nie jest błąd strony.

Filtry firmowe i szkolne oceniają domeny osobno i **nowe domeny (młodsze niż ok. 30 dni, często do 90) z założenia traktują jako ryzykowne**. Domena railsentinel.pl powstała kilka dni temu. Sieć PLK, w której jury będzie oceniać pracę, może działać tak samo. Dlatego **ocena pracy nie może zależeć od jednej nowej domeny**.

Adres `maciejonisiewicz.github.io/railsentinel` nie jest zapasowym: GitHub przekierowuje go na railsentinel.pl, bo domena własna jest ustawiona dla tego repozytorium.

## Co zostało zrobione w kodzie

- Naprawiony błąd „Safari nie może otworzyć strony … Returned response is null” po kliknięciu „O projekcie”: Service Worker zwracał pustą odpowiedź, gdy sieć blokowała domenę. Teraz „O projekcie” i „Status” są zapisane w pamięci aplikacji, a strona, której nie ma w pamięci, pokazuje komunikat „Brak połączenia” zamiast błędu przeglądarki.
- Mniej zależności zewnętrznych: biblioteka mapy (Leaflet) jest teraz na tej samej domenie, a czcionki nie blokują wyświetlenia strony. Zewnętrzne zostały tylko kafelki mapy i ostrzeżenia IMGW; bez nich aplikacja nadal pokazuje linie i prognozę.
- Aplikacja startuje szybciej na słabym zasięgu (pierwsza treść po ok. 4,5 s zamiast 8,4 s na łączu 4G).

Jeśli przeglądarka na Twoim komputerze nadal pokazuje błąd po kliknięciu „O projekcie”, to zostaje w niej stary Service Worker, którego z zablokowanej sieci nie da się zaktualizować. W Safari: Ustawienia → Prywatność → Zarządzaj danymi witryn → railsentinel.pl → Usuń. Albo otwórz stronę w oknie prywatnym lub przez dane komórkowe.

## Co zrobić, żeby jury na pewno wszystko otworzyło

1. **Film i pliki na Google Drive lub OneDrive.** Regulamin (§ 5 ust. 5) wprost przewiduje taki sposób: link dostępny bez logowania i z możliwością pobrania przez cały okres oceny. Wrzuć film (MP4), a najlepiej też pracę (PDF), ustaw udostępnianie „Każda osoba mająca link” i wstaw link do maila (`docs/MAIL_DO_WYSLANIA.md`). Praca w PDF dołączona do maila i tak zawiera wszystkie najważniejsze ekrany aplikacji i wyniki.
2. **Zgłoś domenę do rekategoryzacji** u dostawców filtrów. To zwykłe formularze (kilka minut każdy), a po zatwierdzeniu domena przestaje być „high-risk” w sieciach, które z nich korzystają. Najczęściej używane w firmach: Palo Alto Networks (urlfiltering.paloaltonetworks.com), Fortinet FortiGuard (fortiguard.com/faq/wfratingsubmit), Cisco Talos (talosintelligence.com/reputation_center/support), Zscaler (sitereview.zscaler.com), Broadcom/Symantec (sitereview.broadcom.com), Forcepoint (csi.forcepoint.com), Trellix (trustedsource.org). Adresy formularzy mogą się zmieniać. Wpisz domenę `railsentinel.pl`, a w polu uwag:

   > railsentinel.pl is a static, non-commercial website of a student project submitted to the PKP PLK competition "Kolej na bezpieczeństwo" (weather-risk forecast for railway infrastructure). It is hosted on GitHub Pages, collects no personal data, has no login or ads. Suggested category: Education / Science and Technology (not newly registered / not high-risk).

3. **Kopia strony na znanej domenie (github.io).** Przygotowałem gotowy zestaw w katalogu `mirror/`: nowe publiczne repozytorium `railsentinel-app` z automatyczną synchronizacją co kilka godzin, bez żadnych tokenów. Utworzenie publicznego repozytorium wymaga Twojej wyraźnej zgody. Gdy ją dasz (lub uruchomisz sam `./mirror/setup_mirror.sh`), kopia pojawi się pod `https://maciejonisiewicz.github.io/railsentinel-app/`, a ja dopiszę ten adres do maila, pracy i strony.
4. **Odblokowanie w PWr (opcjonalnie).** Możesz napisać do działu IT uczelni: „Proszę o odblokowanie strony railsentinel.pl (kategoria high-risk), to mój projekt konkursowy na GitHub Pages, termin zgłoszenia 22.11.”.
5. **Przed wysyłką sprawdź stronę z telefonu na danych komórkowych** (Wi-Fi wyłączone).
