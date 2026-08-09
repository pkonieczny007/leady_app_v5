# CLAUDE.md — kontekst projektu

Plik dla asystenta AI pracującego nad tym repozytorium. Zawiera to, czego **nie
widać z samego kodu**: dlaczego rzeczy są takie, jakie są, i o co się już
potknęliśmy. Wszystko, co da się odczytać z plików (lista funkcji, struktura
katalogów), świadomie pomijamy.

---

## 1. Co to jest

Aplikacja Flask zastępująca arkusz Excela, w którym firma **SILESIA 3D** (zajęcia
druku 3D dla szkół i przedszkoli na Śląsku) prowadzi leady sprzedażowe, grafik
trenerów i rozliczenia dokumentów.

**DT = dzień technologiczny** — pokazowy dzień w szkole, po którym otwierają się
grupy zajęć cyklicznych. To centralne pojęcie całej domeny.

**Wersja v5.** Poprzednia (v4, tag `v4.0-spotkanie`) została zaprezentowana
klientowi 06.08.2026 i zaakceptowana — funkcje i wygląd się spodobały. v5 dokłada
to, co ustalono na tamtym spotkaniu.

**Termin twardy: wtorek 11.08.2026** — handlowcy mają wtedy zacząć realnie
pracować na aplikacji. Poprawki dokładamy w biegu.

Repozytorium: `github.com/pkonieczny007/leady_app_v5` (prywatne).
Repo `leady_app_v4` zawiera przez pomyłkę także pracę z v5 — użytkownik świadomie
zdecydował to zostawić. Punktem odniesienia dla „wersji ze spotkania" jest tag
`v4.0-spotkanie` w repo v5.

---

## 2. Uruchomienie

```powershell
$env:PROFIL="test"; python app.py     # http://127.0.0.1:5301
```

**Port 5301, nie 5000.** Na 5000 startuje domyślnie każda apka Flaska i połowa
narzędzi deweloperskich; użytkownik ma ich kilka naraz. Aplikacja **odmawia
startu, gdy port jest zajęty** — patrz „grabie" niżej.

Tryb serwisowy (wejście bez wyboru osoby, uprawnienia koordynatora):
```powershell
$env:PIN_SERWISOWY="7777"; $env:PROFIL="test"; python app.py
```

Testy — 9 plików, ~470 sprawdzeń, wszystkie muszą przechodzić:
```powershell
python test_parsers.py; python test_scenariusze.py; python test_dostepnosc.py
python test_przydzial.py; python test_filtr_osob.py; python test_formularz.py
python test_logowanie.py; python test_serwis.py; python test_trener.py
```

---

## 3. Profile baz — jeden kod, trzy zestawy danych

Zmienna `PROFIL` wybiera katalog: `data/prod`, `data/test`, `data/pusta`.

**Bazy świadomie NIE są gałęziami gita.** `.db` to binarium, którego git nie
scali; trzy gałęzie „per baza" znaczyłyby trzy merge'e przy każdej poprawce
i gwarantowane rozjechanie się wersji. To była pierwsza rzecz, o którą pytał
użytkownik, i odpowiedź brzmi: baza to konfiguracja uruchomienia, nie wersja kodu.

Na profilu innym niż `prod` u góry każdego ekranu wisi kolorowy pasek — chroni
przed importem w trybie „replace" do złej bazy.

Narzędzia (`narzedzia/`):
- `baza.py` — zakładanie profili, kopiowanie między nimi, kopie `.db` + `.xlsx`
  z retencją, przywracanie
- `konto.py` — konta z linii poleceń; **wyjście awaryjne**, gdy nie da się
  zalogować (świeży profil, zapomniany PIN koordynatora)
- `karta_dostepu.py` — PDF do wydruku z PIN-ami i tabelą uprawnień
- `rspo.py` — wykaz szkół z pliku CSV rejestru RSPO (v5, 09.08)

**Czym są `narzedzia/` i czym nie są.** To część TEGO repozytorium i tej samej
bazy (czytają `PROFIL`, importują `db.py`) — nie osobny program. Ale uruchamia
się je z linii poleceń, więc w praktyce są **dla nas, nie dla klienta**: Kasia
nie kliknie `python narzedzia/rspo.py`. Kolejność jest celowa — najpierw skrypt
(tani, do sprawdzenia pomysłu na realnych danych), a to, co się sprawdzi
i będzie potrzebne klientowi regularnie, przenosimy do aplikacji jako ekran.
`rspo.py` jest właśnie na tym etapie: działa, ma być używany co miesiąc przez
koordynatorkę — czyli po wtorku powinien zostać ekranem w panelu koordynatora.

---

## 4. Role i uprawnienia

| | trener | handlowiec | koordynator |
|---|---|---|---|
| Własna dostępność — podgląd i edycja | ✅ | podgląd | ✅ |
| Cudza dostępność — zmiana | ❌ | ❌ | ✅ |
| Kalendarz DT | ✅ | ✅ | ✅ |
| Formularz, moje szkoły, plan tygodnia | ❌ | ✅ | ✅ |
| Baza, zbiorczy, słowniki, import, konta | ❌ | ❌ | ✅ |

Blokady działają **na trzech poziomach**, nie tylko w wyglądzie menu:
kontrola w `before_request`, sprawdzenie właściciela w każdym endpoincie zapisu,
i elementy interfejsu, które nie otwierają edytora. Testy sprawdzają wszystkie
trzy — nie wystarczy ukryć przycisku.

### Filtr „mój" — przypięty, ale zdejmowalny

Wzorzec używany w dwóch miejscach: handlowiec → własne szkoły, trener → własny
wiersz grafiku (chip przypięty kłódką).

**Rozstrzyga OBECNOŚĆ parametru w adresie, nie jego wartość:**
- brak `handlowiec` / `osoby` w URL → wchodzi filtr domyślny
- `handlowiec=` (puste) → człowiek świadomie go zdjął, szanujemy to

Dzięki temu „Wyczyść" i przejście na inny ekran **same wracają do domyślnego**,
a podejrzenie cudzych danych wymaga świadomego kliknięcia. Filtr jest zawsze
**jawny** — plakietka mówi, że działa, i jak go zdjąć. Ukryty filtr wygląda jak
brakujące dane i po dwóch dniach ktoś zgłasza, że aplikacja pogubiła rekordy.

### PIN, nie hasło

Handlowiec loguje się na telefonie, na stojąco, w szkolnym korytarzu. Hasło
z wielką literą wpisywane kciukiem to gwarancja, że po tygodniu wszyscy będą je
mieli w notatniku. Cztery cyfry + sesja 30 dni to kompromis, który ludzie
utrzymają. PIN-y jako PBKDF2 z solą per konto; **nie da się ich odczytać** —
dlatego `karta_dostepu.py` nadaje nowe zamiast wypisywać stare.

---

## 5. Decyzje projektowe, których nie widać z kodu

**Ostrzegamy, nigdy nie blokujemy.** Kolizja godzin trenera, DT w przeszłości,
trener spoza rejonu — wszystko to daje ostrzeżenie, ale zapis przechodzi. Klient
wprost chciał *widzieć*, że coś się nakłada, a nie mieć zablokowany zapis.
Jedyne twarde blokady: wartości spoza słownika i uprawnienia.

**Jedno źródło, ekrany to filtry.** W ich arkuszu wiersz kopiował się do trzech
zakładek i zawsze się rozjeżdżał. Tutaj `placowki` + `leady` + `eventy`, a każdy
ekran to widok. „Transfer leada" to zmiana statusu, nie przeniesienie wiersza.

**Prefiksy `01. `, `02. ` zostają w wartościach słowników** — klient po nich
sortuje. Ale nie są identyfikatorem: w jego dwóch listach ten sam numer bywa
inną osobą. Tożsamość niesie część nazwowa.

**Auto-zwrot szkół po terminie ma karencję i ostrzega.** Automat, który po cichu
zabiera pracę, zostanie znienawidzony i obejdą go, wpisując byle co dla
„odświeżenia" rekordu. Wraca **wyłącznie przypisanie** — notatki, kontakty
i historia zostają przy placówce.

**Automat wisi na ruchu w aplikacji, nie na cronie.** Cron na VPS potrafi cicho
umrzeć i nikt nie zauważy przez tydzień; wątek w tle ginie przy restarcie
gunicorna. `zwrot.przeglad()` przelatuje najwyżej raz na godzinę przy zwykłym
żądaniu.

**Formularz zapisuje JEDNYM żądaniem.** W terenie połączenie zrywa się w połowie.
Albo całość, albo nic — inaczej powstaje lead bez DT i handlowiec nie wie, co
poprawić. Każda próba niesie `klucz_zapisu`, więc ponowienie po zerwanym
połączeniu **nie tworzy drugiego leada** (tabela `zapisy_formularza`).

**Dwa warianty formularza istnieją celowo.** Klient przysłał makietę jednego
długiego formularza; my uważamy, że w terenie lepszy jest podział na kroki.
Zamiast się spierać — pokazujemy oba na jego danych. **Oba zapisują przez to samo
API i tę samą walidację**; gdyby się rozjechały, klient wybierałby między
funkcjami, a nie między układem, i porównanie nic by nie znaczyło.

**Właściciel wpisu zawsze z sesji, nigdy z ciała żądania.** Inaczej każdy
zalogowany mógłby podpisać się cudzym nazwiskiem, a `kto` w historii zmian jest
podstawą kontroli „czy handlowiec ruszył lead przed terminem".

---

## 6. Grabie, na które już nadepnęliśmy

Każda z tych rzeczy kosztowała czas. Nie powtarzać.

**`[hidden]` przegrywa z `display`.** Przeglądarka ukrywa atrybut `hidden` przez
`display:none` w arkuszu domyślnym, a ten przegrywa z każdą naszą regułą
`display`. Objaw: okno modalne widoczne od wejścia na ekran, „nie da się
zamknąć". W projekcie było **11 takich elementów**; w v4 łatano to punktowo dwa
razy. Naprawione globalnie regułą `[hidden]{display:none !important}` na początku
`style.css` — **nie usuwać jej**, jest test regresji.

**Windows pozwala DWÓM procesom nasłuchiwać na tym samym porcie** (Werkzeug
ustawia `SO_REUSEADDR`). Stary i nowy serwer odpowiadają na przemian, a zmiany
w kodzie „raz działają, raz nie". Kosztowało pół godziny szukania błędu, którego
nie było. `app.py` sprawdza port przed startem — **z pominięciem procesu
potomnego reloadera** (`WERKZEUG_RUN_MAIN`), inaczej blokuje każde przeładowanie.
Zabijanie serwera: znaleźć PID przez `netstat -ano | Select-String ":5301"`,
bo `Get-NetTCPConnection` bywa zwraca puste wiersze dla martwych gniazd.

**`pip` na tym komputerze celuje w innego Pythona niż `python`** (3.9.5 vs 3.13
ze Store). Instalować przez `python -m pip install …`.

**Konsola Windows to cp1250.** Skrypty CLI muszą robić
`sys.stdout.reconfigure(encoding="utf-8")`, inaczej wywalają się na własnym
komunikacie zawierającym „→".

**Polskie cudzysłowy „…” w stringach Pythona.** Zamykający `"` kończy string
i psuje składnię. Używać `„…”` (oba typograficzne) albo apostrofów.

**Heredoc w Bashu psuje się na cudzysłowach w SVG.** Do dłuższych plików używać
narzędzia Write, nie `cat << EOF`.

**Bash vs PowerShell.** Narzędzie Bash to Git Bash (składnia POSIX), PowerShell to
osobne narzędzie z własną składnią. Nie mieszać — `-m @'…'@` to PowerShell i w
Bashu wyląduje dosłownie w treści commita.

**Klasyfikator blokuje polecenia z PIN-ami w linii komend.** Operacje na kontach
robić przez `narzedzia/konto.py`, nie przez `python -c` z PIN-em w argumencie.

---

## 7. Konwencje

**Komentarze po polsku i wyjaśniają DLACZEGO, nie CO.** Kod mówi, co robi;
komentarz ma powiedzieć, jakiego realnego problemu klienta dotyczy i dlaczego
wybrano to rozwiązanie, a nie inne. Odwołania do konkretów z ich plików
(„w planszy STARTY 50 zapisów nazwiska dla 29 osób") są cenne — to dowód, a nie
ozdoba.

**Testy to zwykłe skrypty `.py`**, nie pytest. Każdy ma funkcję `sprawdz(nazwa,
warunek, opis)` i wypisuje `[OK] / [BLAD]` plus podsumowanie `N/N`. Działają na
własnej, tymczasowej bazie (`DATA_DIR` w `tempfile.mkdtemp()`). Od v5 logują się
przez wspólny helper `_zaloguj_testowo()`.

**Nazwy funkcji, zmiennych i tras po polsku** — projekt ma przejąć ktoś
z zespołu klienta.

**Git:** `main` zawsze działa. Gałęzie funkcji żyją 1–2 dni, merge przez
`--no-ff`, potem kasowane. Commity opisują **problem i decyzję**, nie listę
plików.

**Bez bibliotek frontendowych i bez buildu.** Cały JS to delegowane nasłuchy na
dokumencie. `reportlab` jest tylko dla `karta_dostepu.py` i **celowo nie ma go
w `requirements.txt`** — obraz dockera ma zostać lekki.

---

## 8. Stan na 08.08.2026 (sobota wieczór)

### Zrobione
Profile baz · formularz terenowy w dwóch wariantach + obsługa awarii · auto-zwrot
szkół po terminie · logowanie PIN-em, trzy role, CSRF · karta dostępu w PDF ·
tryb serwisowy · nowe repo.

### Odpowiedzi Kasi z 08.08 (szczegóły i skutki: `docs/11_PLAN_v5.md`)
- świeży plik JEST: `C:\XEN\AI-szkolenie\SIERPIEN2026\8.08.2026-home\PH PRÓBA
  Nowy dla handlowców.xlsx` — blokada etapu 5 zdjęta
- przypisuje **wyłącznie koordynator** → ścieżka „chcę wziąć tę szkołę" WYPADA z 3b
- auto-zwrot automatyczny; zwrócona szkoła ma się „świecić, że wróciła"
- trener może mieć 4–5 zajęć dziennie (nie zakładać limitu 2)
- konta: koordynatorki Kasia + Weronika Małolepsza, admini Julia Młynarczyk
  + Przemek (admin = uprawnienia koordynatora, osobnej roli nie robimy)
- RSPO (pełna baza szkół, rejony wg listy Kasi) — etap po wtorku, projekt
  w sekcji F planu; klucz = numer RSPO, żeby zmiana nazwy nie rozwalała bazy

### Zrobione dodatkowo 08.08 wieczorem (testy: 585 sprawdzeń, komplet OK)
- **6** — Konta ↔ Słowniki: dodanie do słownika handlowiec/trener tworzy konto
  (bez PIN-u), „bez konta" w `/uzytkownicy` czyta oba słowniki i niesie rolę
- **3b** — „Przedłuż termin" masowo: licznik dni (domyślnie 14, ±, wpisanie),
  po terminie liczy od dziś; termin przy „Przypisz" z góry dziś+14
- **7** — plakietka „wróciła do puli" na `/baza` (gaśnie przy pierwszym ruchu
  na leadzie) + skok do daty w kalendarzu (podświetlony tydzień, 3 widoki)

### Zrobione w niedzielę 09.08
- **3c** — zwrot bez karencji po terminie (`KARENCJA_DNI=0`), 2 dni jako
  ostrzeżenie PRZED terminem (`OSTRZEZENIE_DNI=2`)
- **import** — ⚠️ importer brał 165 placówek zamiast 545, bo zakładka bazy
  w nowym pliku nazywa się „Baza szkół Śląskie", a nie „BAZA"; rozpoznajemy
  ją teraz po początku nazwy. Nowe statusy klienta („04. Brak zgody na DT",
  „04. Odpuścić") i alias „Julia" → 05. Młynarczyk
- **profil `test` ma świeże dane** z `PH PRÓBA Nowy dla handlowców.xlsx`
  (545 placówek, 523 z telefonem, 529 z mailem)
- **`narzedzia/rspo.py`** — wykaz z CSV rejestru + raport dopasowania nazw;
  szczegóły i liczby w `docs/12_RSPO.md`
- **kopia plików klienta** w `SIERPIEN2026\_KOPIE_PLIKOW_KLIENTA\2026-08-09`
  — Kasia nie ma własnej kopii pliku, o czym powiedziała wprost

### Zostało do wtorku (plan dzienny w `docs/11_PLAN_v5.md` sekcja B)
- **8** — ręczny test z telefonu: trener ustawia dostępność, handlowiec
  formularz→kalendarz (praca formularz→kalendarz musi być sprawna — nacisk Kasi)
- **2b** — PWA: manifest i ikona (wymaga HTTPS, więc razem z etapem 4)
- **4** — VPS: najpierw **demo** na subdomenie (profile pusta/test), potem prod;
  `certbot`, cron kopii o 6:00, skrypt wdrożenia (git pull + compose build)
- **9** — próba pełnej ścieżki backup → przywracanie zanim ruszy prod
- **5** — import realnych danych do profilu `prod`, próba na sucho z telefonu po LTE
- RSPO: wniosek o API w poniedziałek + CSV z wyszukiwarki (eksport potwierdzony);
  propozycja w `docs/12_RSPO.md`, szczegóły z klientem we wtorek

### ⚠️ Bez tego NIE wolno wystawiać na VPS
1. `SECRET_KEY` — domyślny `leady-v3-demo` leży w repozytorium, więc każdy mógłby
   podrobić sesję koordynatora
2. `PIN_KOORDYNATORA` — domyślnie `0000`
3. **`PIN_SERWISOWY` musi zniknąć ze środowiska** — to klucz uniwersalny

### Czeka na odpowiedź klienta
- podpowiedź trenera w formularzu: czy handlowiec może obiecać termin, czy
  wiążąco potwierdza koordynator
- czy w formularzu czegoś brakuje (osoba kontaktowa, zgoda na salę, sprzęt)
- osoba figurująca i jako handlowiec, i jako trener ma dziś **dwa konta** (różne
  prefiksy w słownikach) — czy to ma być jedno

---

## 9. Dokumentacja w `docs/`

`11_PLAN_v5.md` to żywy plan v5 ze stanem etapów — aktualizować przy każdym
domknięciu etapu. Starsze pliki (`01`–`10`) to analiza plików klienta i projekty
modułów v2–v4; są punktem odniesienia dla decyzji, nie do zmieniania.
