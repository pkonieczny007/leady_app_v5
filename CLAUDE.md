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

Repozytorium: `github.com/pkonieczny007/leady_app_v5` — **publiczne**. Decyzja
z 20.08: na czas rundy poprawek zostaje otwarte, bo tak sprawniej się pracuje;
prywatne będzie później. Ma to skutek techniczny, o którym łatwo zapomnieć: VPS
nie ma żadnych poświadczeń do GitHuba, więc `git pull` działa tam **wyłącznie
dlatego, że repo jest otwarte**. Przełączenie na prywatne położy `wdroz.sh`
w obu katalogach na serwerze, dopóki nie założymy klucza wdrożeniowego
(read-only) i nie przestawimy remote na SSH.
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
- `trenerzy.py` — rejony z zakładki „Trenerzy regiony" → tabela `rejony` (v5, 09.08)

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

**Skrypt `.ps1` bez BOM-u nie parsuje się w PowerShellu 5.1.** Plik zapisany
jako UTF-8 bez znacznika kolejności bajtów jest czytany jako ANSI, polskie znaki
w komentarzach rozpadają się na sekwencje, a te potrafią rozwalić parsowanie
łańcuchów **kilkadziesiąt linii dalej** — komunikat wskazuje wtedy zdrową linię
(u nas: „token '&&' nie jest poprawnym separatorem" przy linii, w której `&&`
siedziało w środku stringa). Po zapisaniu `.ps1` narzędziem Write trzeba dodać
BOM:
```powershell
$t = [IO.File]::ReadAllText($p, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText($p, $t, [Text.UTF8Encoding]::new($true))
```
Uwaga: ponowny zapis narzędziem Write znów usunie BOM — do poprawek w takim
pliku używać Edit, nie Write.

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

### Zrobione w niedzielę 09.08 wieczorem (testy: 649 sprawdzeń, komplet OK)
- **formularz v3** (`/formularz/v3`) — status wybranego trenera, cztery
  kategorie, wolne okna, „co się dzieje tego dnia"; v1 i v2 nietknięte
- **dostępność: tryb zaznaczania dni** — tap w komórki albo nagłówek tygodnia,
  pasek z gotowymi godzinami, jedno żądanie na paczkę; trener widzi w wyborze
  tylko siebie, znikł przycisk demo (i tak kończył się odmową)
- **„Plan na dziś"** w v1/v2/v3 ze wspólnego `_plan_dnia.html` + `fx_plan.js`:
  szkoły od koordynatora z terminem, zadania oddzielone od reszty (jeden
  handlowiec ma 159 przypisanych szkół), gwiazdka na cudzej szkole z jawnym
  ostrzeżeniem „przypisana do…" (autora gwiazdki czytamy z historii zmian)
- **poprawki z testów**: rok „0002" w polu daty nie porywa już kalendarza,
  miesiąc pamiętany między kalendarzem a dostępnością, „godz. nieustalona"
  zamiast pustki (w danych klienta 48 z 66 DT nie ma godziny)
- **rejony trenerów** (`narzedzia/trenerzy.py`): tabela `rejony` była PUSTA,
  choć klient ma dane w zakładce „Trenerzy regiony" — przeniesione do profilu
  `test` (21 trenerów, 44 miasta), więc podpowiedź „jeździ tu" wreszcie działa.
  **Na wtorek dla Kasi:** 6 osób z rejonem spoza słownika trenerów (Legierski,
  Rudek, Jeleń, Borszcz, Wąsek, Nerushenko) i „Pyrzowice" spoza słownika miast.
  Telefonów/maili trenerów NIE przenosimy — trener to pozycja słownika, nie ma
  gdzie ich zapisać bez zmiany schematu

### Przygotowanie wdrożenia — zrobione 09.08 wieczorem (etapy 11 i 10)
`docs/15_DOMENA_I_WDROZENIE.md` — instrukcja do wykonania z palca: DNS → `nslookup`
→ kontener → nginx bez SSL → certbot → `HTTPS=1` → restart, plus checklista.
**Ta kolejność nie jest estetyczna, tylko wymuszona**: certbot nie wystawi
certyfikatu, zanim domena nie wskaże serwera, a `HTTPS=1` przed certyfikatem
daje logowanie w pętli (flaga `Secure` na ciastku).

Serwer: `ubuntu@57.128.241.52` (OVH), domena w OVH DNS (`ns10.ovh.net`).
Dwie subdomeny: `demo-ph.silesia3d.site` (port 5302, `PROFIL=test`)
i `ph.silesia3d.site` (5301, `prod`). Demo idzie pierwsze — na nim wolno się
pomylić. Na tym samym serwerze stoi `librus.silesia3d.site` z ważnym
certyfikatem Let's Encrypt, czyli **nginx 1.26.3 + certbot są skonfigurowane** —
nasze subdomeny to powtórzenie tej ścieżki, nie stawianie jej od zera.

Aplikacje mieszkają w `/home/ubuntu/apps/<subdomena>/` — nasza w
`apps/ph.silesia3d.site`, jeden katalog na obie subdomeny (jedno compose,
dwie usługi).

**Porty publikowane jako `127.0.0.1:5301` / `127.0.0.1:5302`, nie gołe `5301`.**
Docker wpisuje reguły wprost do iptables, z pominięciem `ufw` — bez adresu
z przodu aplikacja byłaby dostępna pod `http://IP:5301` bez HTTPS, a firewall
pokazywałby, że wszystko zamknięte. **To nie teoria:** librus na tym samym
serwerze ma `0.0.0.0:5100->5000`, więc `http://57.128.241.52:5100` odpowiada
gunicornem po czystym HTTP, choć jego `https://` działa poprawnie. Poprawka
u nich to jedna linia, ale to ich aplikacja — nie ruszamy przy okazji.

Trzy pułapki znalezione przy pisaniu instrukcji, wszystkie naprawione:
- **`narzedzia/baza.py` nie widział bazy w kontenerze.** Szukał w `data/<profil>`,
  a compose ustawia `DATA_DIR=/data`. Nocny cron kopii co rano meldowałby „nie ma
  bazy profilu 'prod'" do logu, którego nikt nie czyta — brak kopii wyszedłby
  dopiero przy awarii. Teraz czyta `DATA_DIR`, kopie idą do `DATA_DIR/kopie`
  (**na wolumen**, bo `/app/kopie` znika przy `docker compose build`), a komenda
  na inny profil niż `PROFIL` **odmawia**, zamiast po cichu ruszyć nie tę bazę.
- **`DATA_DIR` wygrywa z `PROFIL`** — dlatego demo i prod mają OSOBNE wolumeny.
  Wspólny oznaczałby jedną bazę pod dwiema nazwami, a kolorowy pasek u góry
  kłamałby, że to różne dane.
- **`.env` nie było w `.gitignore`.** Na VPS repozytorium jest klonem gita; jeden
  `git add .` wypchnąłby `SECRET_KEY` i PIN koordynatora na GitHuba. Wzór bez
  wartości: `.env.example`.

`wdroz.sh [demo|prod]` — kopia PRZED aktualizacją (po starcie nowej wersji jest
za późno), `git pull`, przebudowa, sprawdzenie, że aplikacja odpowiada.
Próba backup → przywracanie przeszła lokalnie na `test` (545 leadów po odtworzeniu).

## 8b. Stan na 10.08.2026 (poniedziałek) — PRODUKCJA DZIAŁA

`https://ph.silesia3d.site` — 545 placówek, 545 leadów, 65 DT, 21 trenerów
z rejonami, **49 kont z PIN-ami**. Certyfikat Let's Encrypt do 08.11.2026.
`https://demo-ph.silesia3d.site` — poligon na profilu `test`.
Katalog na serwerze: `/home/ubuntu/apps/ph.silesia3d.site`.

**Baza produkcyjna powstała LOKALNIE i pojechała gotowym plikiem** — nie przez
ekran „Import" na serwerze. Powód: ten importer już raz zaskoczył (165 placówek
zamiast 545, zmieniona nazwa zakładki). Poprawianie kodu na produkcji przy
czekających ludziach to nie jest plan. Ta kolejność ma zostać.

**Konta wielorolowe.** Osoba bywa jednocześnie handlowcem, trenerem
i koordynatorem — wtedy dostaje osobne konto z dopiskiem roli w nazwie
(`03. Małolepsza (koordynator)`). Decyzja Przemka 10.08. Koordynatorzy na
produkcji: `01. Sacawa (koordynator)` (to jest Kasia), `03. Małolepsza`,
`05. Młynarczyk`, `Przemek`, plus awaryjne konto `Koordynator`.

### Naprawione 10.08 — wszystko wyszło z pytań, nie z testów
- **układ na telefonie** — arkusz nie miał ŻADNEGO progu `@media`; `.brand` nie
  daje się ścisnąć, więc `.nav` zawijał się w pionie w kilkanaście wierszy
  i wypychał stronę w bok. Nawigacja ma teraz własny wiersz i przewija się
  poziomo; tabele przewijają się same
- ⚠️ **zajęcia cykliczne były NIEWIDOCZNE w kalendarzu** — openpyxl oddaje datę
  jako `datetime`, więc wyliczona data pierwszych zajęć szła do bazy jako
  `2026-09-22T00:00:00`; `date.fromisoformat` to odrzuca, a kalendarz robił
  `continue` i pomijał wpis BEZ ŚLADU. Naprawione z obu stron (importer + odporny
  kalendarz), dane w `prod` i `test` poprawione. Test S16
- ⚠️ **zajęcia bez prowadzącego znikały z macierzy, a licznik je liczył** —
  wiersze to trenerzy, więc event bez osoby nie miał gdzie trafić: 56 pokazanych
  z 61 zapowiedzianych. Doszedł bursztynowy wiersz „— bez prowadzącego —" (zawsze
  pierwszy) i liczniki braków w nagłówku. Test S17
- kalendarzyk przeglądarki otwierał się na dziś zamiast na oglądanym miesiącu

### Kopie zapasowe — trzy warstwy
1. **VPS, cron 6:00** — `.db` + `.xlsx` do `/data/kopie` w wolumenie, retencja 30 dni
2. **Mac mini (Debian!)** — ciągnie codziennie timerem systemd z `Persistent=true`.
   Ciągnie, a nie serwer pcha: przy przejęciu VPS-a pchanie skasowałoby też kopie
3. **Z ręki** — `narzedzia/kopia_z_serwera.ps1` (Windows) i
   `narzedzia/kopia_na_maca.sh --cel …` (Debian)

Oba skrypty **sprawdzają pobrane bazy** (`integrity_check` + liczba placówek) —
plik o poprawnej nazwie i rozmiarze to jeszcze nie kopia. Instrukcja odtwarzania:
`docs/17_KOPIE_NA_MACU.md`; ścieżka przećwiczona na demo (545 → 0 → 545).
**Kopii bazy NIE wkładamy na GitHub** — dane osobowe w historii, której git nie
zapomina. Kod tak, dane nie.

### Zostało do wtorku
- **8** — ręczny test z telefonu **po LTE, na produkcji**: logowanie PIN-em,
  ikona na ekranie początkowym (PWA — teraz zadziała, HTTPS jest),
  formularz → kalendarz (nacisk Kasi)
- wydruk kart dostępu (`dostepy/karta_dostepu_prod_*.pdf`) i kartki A5
  (`docs/16_KARTKA_HANDLOWCA.html`, Ctrl+P) — **wpisać numer telefonu**
- RSPO: rozmowa z Wojtkiem, warianty zakresu z `docs/12_RSPO.md`

### ⚠️ Bez tego NIE wolno wystawiać na VPS
Wszystkie trzy siedzą w `.env` na serwerze (wzór: `.env.example`, plik jest
w `.gitignore` i ma tam zostać):
1. `SECRET_KEY` — domyślny `leady-v3-demo` leży w repozytorium, więc każdy mógłby
   podrobić sesję koordynatora
2. `PIN_KOORDYNATORA` — domyślnie `0000`
3. **`PIN_SERWISOWY` musi zniknąć ze środowiska** — to klucz uniwersalny
   (na `prod` kod wymaga jeszcze `PIN_SERWISOWY_PROD=tak`, więc przypadkiem się
   nie włączy — ale świadomie też nie)

### Czeka na odpowiedź klienta
- podpowiedź trenera w formularzu: czy handlowiec może obiecać termin, czy
  wiążąco potwierdza koordynator
- czy w formularzu czegoś brakuje (osoba kontaktowa, zgoda na salę, sprzęt)
- osoba figurująca i jako handlowiec, i jako trener ma dziś **dwa konta** (różne
  prefiksy w słownikach) — czy to ma być jedno

---

## 8c. Runda poprawek 20–23.08.2026 — gałąź `poprawki-2026-08`

Produkcja stoi nietknięta na `main` (`6a3e181`, tag `przed-poprawkami-2026-08-20`
to punkt cofnięcia). **Demo zostało wdrożone i zmigrowane dopiero 24.08
wieczorem** — przez cztery dni klient oglądał wersję sprzed poprawek i zgłaszał
je ponownie. To była najczęstsza przyczyna nieporozumień w tej rundzie
i sprawdzanie, CO klient właściwie widzi, ma być pierwszym ruchem przy każdym
zgłoszeniu.

Testy: **11 plików, 912 sprawdzeń + 93 w `test_parsers` + 17 w node**, komplet
przechodzi. Doszedł `test_obszary.py`.

### Zrobione (P01–P31 + E0)
Blokada pisania po cudzych szkołach · przydział/termin tylko dla koordynatora ·
podstawianie kontaktu · gwiazdka „twoje" zamiast licznika · filtr tekstowy listy
szkół · odwoływanie DT ze śladem (kasowanie tylko koordynator) · sekcja „Wynik
wizyty" · „zrobione" schodzi z planu dnia · filtr „bez prowadzącego" ·
**P27** pola DT nieobowiązkowe poza datą · **P30** znacznik „do uzupełnienia"
w kalendarzu · **P31** lista odwołanych · statusy pośrednie · poprawka mobilna ·
**E0** brakujący typ w słowniku produkcji.

### Sedno listy Zuzi: to nie był jeden błąd, tylko jedna reguła
Formularz żądał kompletu sześciu pól DT. Przez to nie dało się zapisać ani
wizyty bez terminu, ani terminu bez szczegółów — czyli **większości realnej
pracy w terenie**. Praca, której nie da się zapisać, nie znika: dzieje się dalej,
tylko poza aplikacją. Twarda została sama **data**, bo serwer pomija blok DT bez
niej (`if typ == "DT" and not blok["data"]: continue`) i godzina wpisana obok
przepadłaby bez śladu. Reszta braków jest teraz WIDOCZNA (P30), nie blokowana —
bez tego zamienilibyśmy „nie da się zapisać" na gorsze: „zapisane, wygląda na
gotowe, nikt tam nie wróci".

**Punkty 7–10 jej listy nie były błędem kodu.** Te operacje od początku były
zamknięte dla handlowca; Zuzia pracuje na wspólnym koncie `Koordynator` (nie ma
własnego wśród 50). Dopóki go nie dostanie, będzie zgłaszać to samo, a historia
zmian zapisuje konto zamiast człowieka.

### Baza na RSPO — projekt i pierwsze dwa etapy
`docs/poprawki/2026-08-23/PROJEKT_BAZY_RSPO.md` (etapy M0–M9). Zrobione **M1 i M2
na profilu `test`**, oba addytywne i odwracalne `DROP TABLE`:
- `rejestr_rspo.py` — lustro rejestru (`rspo_rejestr` + dziennik zmian), 6 116
  placówek śląskich, wgranie 1,2 s
- `obszary.py` — 17 obszarów z listy Kasi; kontrola wyjścia zgodna co do sztuki:
  **1 259 szkół i przedszkoli**, Knurów 44 przez gminę, rybnicki 0
- `narzedzia/migracja_rspo.py` (`lustro` / `obszary` / `stan`), ekran `/obszary`
  (podgląd, bez klikania)

**Źródło całego zamieszania z miejscowościami**: w pliku klienta dwie wartości
brzmiały `09. Pszczyna powiat` i `15. Będzin powiat` — **import urwał słowo
„powiat"**. Pod Będzinem siedzi 17 miejscowości (w tym Czeladź), pod Pszczyną 27.
Stąd „nie ma szkół z Czeladzi": one są, tylko nazwa przestała o tym mówić.
Ornontowice też nie były naszym wymysłem — u klienta siedziały pod `01. Orzesze`.

**Rejon działania to LISTA OBSZARÓW (powiat albo gmina), nie kolumna.** Zakres
firmy nie pokrywa się z żadnym jednym poziomem administracyjnym: Rybnik bierzemy
jako miasto, ale nie powiat rybnicki; Knurów jako gminę, ale nie resztę powiatu
gliwickiego. Reguła „gmina bije powiat" żyje w jednym zapytaniu w `przelicz()`.

**Lustro jest OSOBNĄ tabelą, nie kolumnami w `placowki`** — bo polityki
nadpisywania są sprzeczne: w lustrze wygrywa rejestr, w bazie roboczej człowiek.
W jednej tabeli jedna z nich musiałaby po cichu przegrywać.

Stan bazy przed migracją: **409 placówek niesie realną pracę, 136 jest
nietkniętych** (granica ostra; pola miękkie nic nie zmieniają). **18 par dubli**
w bloku id 517–545, przy czym w 16 z nich jedyne DT wisi na rekordzie
SKRÓCONYM — scalanie musi przepiąć eventy PRZED czymkolwiek innym.

### Plany czekające na decyzje klienta
`PLAN_FORMULARZA.md` (v5 obok czterech starych — decyzja klienta; kaskada od
placówki, chipy zajęć, etapy E0–E8) i `PLAN_BAZY_PH.md` (6 zakładek Kasi; cztery
już istnieją w backendzie). Razem **28 pytań** do Kasi i Wojtka.

**Nowy formularz to PIĄTY PRZYCISK na `/formularz`, nie podmiana istniejącego.**
Dzięki temu można go budować w dowolnym momencie — rozgrzebany v5 nie blokuje
nikomu pracy, bo handlowiec dalej klika swój v3, a piąty kafelek jest ścieżką,
w którą nikt nie wchodzi przypadkiem (i ma być opisany jako testowy, jak dziś
v4). Warunek: rozszerzenia API muszą być **addytywne** — nowa lista `zajecia`
dochodzi obok bloków `dt`/`cykl`, a stare payloady jadą bez zmian. To ta sama
zasada, dla której cztery warianty w ogóle istnieją: porównanie na żywych
danych zamiast sporu o układ. Wygaszanie starych — osobna decyzja po testach.

### Grabie z tej rundy
**`git add <katalog>` zgarnia pliki klienta.** Dwa razy: raz notatkę roboczą,
raz `Kopia Julia Młynarczyk.xlsx` — miesięczne rozliczenia trenerów ze stawkami,
do PUBLICZNEGO repo. Za drugim razem złapane przed `push`. Arkusze klienta
w katalogach poprawek są teraz w `.gitignore`; **`git status` czytać PRZED
commitem, nie po**.

**`odwolane` w `calendar_view.py` było już zajęte** — znaczy „odwołane
WYSTĄPIENIE cyklu" i `_naloz_wyjatek()` zeruje je przy każdym wpisie bez wyjątku.
Odwołanie całego spotkania musiało dostać własną nazwę (`odwolanie`), inaczej
znacznik znikał po cichu.

**Skrypty Pythona w heredocu Basha mają cudzysłowy w cp1250.** Wzorce z polskimi
znakami przestają pasować i `replace` nie robi nic — bez asercji na liczbę
trafień wygląda to jak wykonana praca. Do zmian w plikach z polskimi znakami
używać narzędzia Edit albo `\uXXXX`.

**`app.py` jest w CRLF, a `calendar_view.py` w LF.** Skrypt podmieniający tekst
działa na jednym, a na drugim cicho nie trafia. Zawsze `assert s.count(wzorzec) == 1`.

**Test pisał wszystkie pliki pod jedną ścieżkę** — „plik pierwotny" miał już
treść drugiego wgrania, więc sprawdzenie przechodziło zależnie od kolejności.
Test, który nie testuje, jest gorszy niż jego brak.

**`typ_eventu` na produkcji nie znał `CYKLICZNE-PRZEDSZKOLE`**, choć v4 pozwala
go zapisać (walidacja idzie po stałej `db.TYPY_CYKLICZNE`, a słownik to DANE
osobne dla każdego profilu). Wpis dawało się utworzyć, ale nie poprawić —
edycja odbija się od twardej blokady słownika. `narzedzia/slowniki_kontrola.py`
+ sprawdzenie w S0. **Każda nowa stała, którą kod zna, musi trafić do słownika
każdego profilu** — i pamiętać, że `odswiez_demo.sh` zasiewa demo kopią produkcji
i takie dopiski zetrze (jak `statusy.py`).

**Telefon: dwie różne przyczyny pod jednym zgłoszeniem.** „Nie da się zmniejszyć"
to tryb standalone PWA (iOS wyłącza zoom systemowo — nasza decyzja z 10.08),
a „widok trzeba przesuwać" to był realny błąd: `.topbar-right` miał w wersji
mobilnej `flex:0 0 auto`, czyli ZAKAZ kurczenia, przy zawartości ~370 px.
Poprawka z 10.08 objęła nawigację i tabele, ale nie ten blok, nie `.seg`
(ucinał zakładki bez możliwości dojechania) i nie kartę szkoły.

---

## 8d. 24.08.2026 — baza przeszła na rejestr RSPO

Stan, liczby i plan: **`docs/poprawki/2026-08-24/STAN_SESJI_2026-08-24.md`**.
Skrót tego, co zmienia sposób myślenia o projekcie:

**Baza `test` ma 1618 placówek i pokrywa rejestr co do wiersza** (0 braków wobec
1589 wierszy rejestru w typach klienta × 17 obszarach). Było 545. Doszły
732 przedszkola i punkty, 34 brakujące szkoły, 29 domów kultury i ognisk,
278 zespołów. `prod` jest NIETKNIĘTY.

**Osią filtrowania jest POWIAT, nie miejscowość.** Filtr „Powiat" stoi przed
„Miejscowością" na `/baza`, `/leady`, `/zbiorczy`, `/niewykorzystane`
i `/tydzien`; miejscowość zawęża się wybranym powiatem. Formularz v5 ma kaskadę
powiat → miejscowość → placówka.

**Import urwał słowo „powiat" — to jest źródło zgłoszenia „nie ma bazy
w Czeladzi".** W pliku klienta były wartości `09. Pszczyna powiat`
i `15. Będzin powiat`. Czeladź nie zniknęła, tylko wpadła do worka razem
z 16 innymi miejscowościami. Po nadaniu numerów RSPO 68 rekordów odzyskało
prawdziwą miejscowość; Czeladź ma dziś 12 placówek.

**Powiat da się nadać BEZ numerów RSPO** — po nazwie miejscowości przez lustro
rejestru. To był warunek, żeby przełączenie filtrów nie musiało czekać na
decyzje koordynatorki przy kilkudziesięciu wierszach.

**`miejscowosc` przestała być pozycją słownika** (`text` w `PLACOWKA_FIELDS`).
Musiała: miejscowości w zakresie jest ~150, w tym wsie, których słownik nigdy
nie zawierał — twarda blokada zamieniłaby każdą nową wieś z rejestru w rekord
NIE DO POPRAWIENIA w karcie. Słownik `miasto` ZOSTAJE, bo używa go `aliasy`
przy imporcie arkuszy klienta.

**Listy filtrów idą z DANYCH, listy formularza z REJESTRU.** Filtr po
miejscowości bez placówek daje pustą tabelę; formularz służy do ZAKŁADANIA
placówki, więc musi mieć nazwę, w której nas jeszcze nie ma.

**Formularz v5 istnieje** — piąty przycisk na `/formularz`, kaskada od placówki,
chipy „co ustaliłeś" (kilka rodzajów naraz), zapis samej wizyty bez żadnego
chipa. API rozszerzone ADDYTYWNIE o listę `zajecia`; jest test-zapora, że
v1–v4 wysyłają dokładnie to co dotąd.

### Zakładanie placówek wypadło z formularza (Kasia, 24.08)

„Usuń tę możliwość, bo to powoduje, że PH wpisują coś z ręki sami i będą się
dublować rzeczy, a wpisują nazwy jak popadnie". Przycisk „dodaj nową placówkę"
zniknął z **wszystkich pięciu** wariantów — gdyby został w jednym, handlowiec
zakładałby placówki tamtym, a porównanie wariantów przestałoby dotyczyć układu.

Wolno było tak zrobić dopiero teraz: argument, dla którego ta furtka w ogóle
powstała („brak szkoły w bazie = ustalenia na kartce"), zniknął razem
z przejściem bazy na rejestr RSPO. Dlatego podpowiedź w miejscu przycisku
kieruje **najpierw do filtra powiatu**, a dopiero potem do koordynatorki —
„nie ma jej na liście" znaczy dziś prawie zawsze „szukam nie w tym powiecie".

Blokada siedzi przy **zapisie**, nie w wyglądzie: `/api/formularz` odmawia
handlowcowi bloku `placowka`, a `api_lead_create` doszedł do
`TYLKO_KOORDYNATOR`. Sam brak przycisku nie zamyka niczego — to ta sama lekcja
co przy K01 z 20.08. Koordynator zakłada dalej, na ekranie „Baza".

⚠️ **Na `prod` ta zmiana ma sens dopiero razem z bazą RSPO.** Produkcja ma 545
placówek i zero powiatów; sam zakaz zakładania zabrałby handlowcowi możliwość
zapisania wizyty w przedszkolu, którego w tych 545 nie ma. Obie rzeczy jadą tą
samą gałęzią, więc wystarczy ich nie rozdzielać przy wdrożeniu.

### Cztery usterki z 24.08 wieczorem — wszystkie z KLIKANIA, nie z testów
Wyszły, gdy klient zaczął używać aplikacji, mimo blisko tysiąca zielonych
sprawdzeń. Łączy je jedno i warto to zapamiętać: **siedziały na styku „nowa
baza ↔ stary ekran"**, a testy chodzą po świeżej bazie, gdzie tego styku
nie ma. Po każdej migracji danych trzeba przejść ekrany ręcznie.

- **„Zapis się zacina".** `pilnujWyjscia` wiesza `beforeunload`, a udany zapis
  robi `location.reload()` — czyli wychodzi ze strony. Bez flagi „już zapisane"
  przeglądarka blokuje przeładowanie własnym okienkiem. **Zapis dochodził do
  bazy, zacinał się powrót** — usterka wyglądająca jak utrata pracy i kusząca
  do ponowienia. v1–v4 mają tę flagę od czerwca.
- **Lista miejscowości w formularzach przestała trafiać w bazę.** Warianty 2–4
  brały je ze słownika `miasto` (`01. Orzesze`), a M8 wyczyścił nazwy w bazie
  (`Orzesze`) — część wspólna PUSTA, wybór dawał zero szkół. Zdanie klienta
  „lista jest widoczna na demo" było kluczem: demo nie było zmigrowane, więc
  usterka **czekała na moment migracji**, czyli na handlowców.
- **Cykl bez prowadzącego** — sekcja cykliczna v5 rysowała sam harmonogram,
  więc definicje jej pól były martwym kodem, choć wyglądały na kompletne.
- **Po zapisie pusty formularz zamiast potwierdzenia** — ostatnie miejsce,
  w którym v5 różnił się od v1–v4 funkcją, a nie układem.

### Grabie z tej rundy
- **Kontakt należy do placówki — v5 popełnił od nowa błąd naprawiony w v2–v4.**
  Reguła „podstawiaj tylko w puste pole" (P04) chroni to, co wpisał człowiek,
  i jest słuszna WEWNĄTRZ jednej placówki. Przy zmianie placówki ta sama reguła
  przenosi dyrektorkę jednego przedszkola do karty drugiego. Nie ma tu czego
  chronić: sekcja kontaktu jest zakryta, dopóki placówka nie jest wybrana, więc
  każda wartość w niej dotyczy POPRZEDNIEJ szkoły. Nadpisujemy zawsze, także
  pustą wartością, i mówimy o tym.
- **v5 robił dubla placówki sam z siebie.** Przy placówce bez leada wysyłał blok
  `placowka` z nazwą przepisaną z rekordu, w przekonaniu, że serwer rozpozna ją
  po nazwie. Nie rozpoznawał — `/api/formularz` bez `lead_id` po prostu wstawia
  wiersz. Komentarz w kodzie twierdził coś przeciwnego przez dwa dni. Teraz
  jedzie `placowka_id`, a serwer zakłada lead do ISTNIEJĄCEGO rekordu.
- **Reguła wykrywania dubli musi znać numer szkoły.** Bez niego „miejska szkoła
  podstawowa" to same słowa puste i wszystko skleja się ze wszystkim (289
  fałszywych trafień w pierwszym podejściu, SP nr 9 jako nasza SP nr 7).
- **`RSPO podmiotu nadrzędnego` bywa w rejestrze puste** — w całym Orzeszu nie
  ma go ani jedna placówka. Do wiązania zespołu ze składowymi trzeba też adresu.
- **504 z 536 rekordów klienta ma w adresie samą ulicę, bez numeru budynku** —
  porównanie adresów musi umieć obie postaci.
- **Sprawdzać ZAWARTOŚĆ, nie tylko liczbę.** 93 zespoły „brakujące w bazie"
  okazały się technikami i liceami, gdy policzyłem, co zawierają.
- **Podgląd musi liczyć tym samym kodem co zapis** — `przygotuj()` jest wspólnym
  jądrem obu.

### ✅ PRODUKCJA ZMIGROWANA 24.08 o 16:22
`https://ph.silesia3d.site` stoi na rejestrze RSPO: **557 placówek → 1614,
leady 556 → 1613, EVENTY 90 → 90**, 1587 z numerem RSPO (27 do decyzji Kasi),
jeden rekord bez powiatu (znane P28). Kopia do cofnięcia:
`/data/kopie/prod_2026-08-24_1622.db` + `.xlsx`.

Różnica wobec próby na kopii z 08:24 (555 → 1614, eventy 87) to praca z tego
dnia: 2 placówki i 3 DT dopisane między rankiem a wieczorem. **Zgodność co do
tej różnicy jest lepszym dowodem niż zgodność co do liczby** — pokazuje, że
migracja wzięła bazę taką, jaka była.

✅ **Scalone do `main`** (`4d8355f`, `--no-ff`), tag **`v5.1-rspo`**. `main` znów
znaczy „to, co działa u klienta". Zostaje jedno: na serwerze produkcyjnym
`git checkout main` — katalog stoi jeszcze na gałęzi, treść jest identyczna,
więc bez przebudowy.

⚠️ **Cofnięcie kodu do wersji sprzed migracji NIE wystarczy.** Baza ma po M8
czyste nazwy miejscowości (`Orzesze`), których starszy kod szuka w słowniku
(`01. Orzesze`) — wybór szkoły w formularzach przestałby działać. Cofać kod
i bazę naraz.

### Otwarte zadania są w GitHub Issues
Kamień milowy **„Po migracji RSPO"**, etykiety `migracja` / `formularz` /
`dane` / `zgloszenie-klienta`. Tam planujemy dalsze rundy — nie w plikach.
⚠️ Repo jest PUBLICZNE: w zgłoszeniach role zamiast nazwisk, żadnych nazw
szkół ani numerów.

### Do zrobienia w pierwszej kolejności
1. ✅ **Demo wdrożone i zmigrowane 24.08 po południu.** Migrowaliśmy W MIEJSCU,
   nie wgrywając gotowego `.db` — odwrotnie niż produkcję w sierpniu, bo tamta
   reguła („baza powstaje lokalnie i jedzie plikiem") straciła podstawę:
   produkcja od 11.08 ŻYJE, więc jej bazy nie da się podmienić, trzeba ją
   migrować w miejscu — a demo było jedynym miejscem, gdzie dało się to
   przećwiczyć. ⚠️ **Od teraz NIE uruchamiać `odswiez_demo.sh`** — zasiewa demo
   kopią produkcji i skasowałby migrację. Znów będzie miał sens po migracji
   produkcji.
2. ✅ **Produkcja zmigrowana** — `WDROZENIE_NA_PRODUKCJE.md` +
   `narzedzia/migracja_na_produkcje.sh`. Trzy rzeczy odróżniły ją od demo
   i każda kosztowała osobny krok: kopia z eksportem `.xlsx` (plik do otwarcia
   bez tej aplikacji), **zatrzymanie usługi** na czas migracji (~2 min), oraz
   sprawdzenie liczby eventów przed i po — skrypt sam kończy się błędem, gdy
   się rozjedzie. Osobny plik skryptu, nie `--profil prod` w skrypcie demo:
   inaczej produkcję dałoby się ruszyć poleceniem wklejonym z pamięci
3. **Po migracji, bez pośpiechu:** 27 placówek bez numeru RSPO → plik decyzyjny
   dla Kasi (`dopasuj --decyzje <plik> --zapisz`) · **M4 scalanie 18 par dubli**
   (narzędzia NIE MA; eventy i log przepiąć PRZED skasowaniem rekordu, bo
   `ON DELETE CASCADE` zabiera DT bez śladu) · P28 „SP 5" bez miejscowości ·
   konto handlowca dla Zuzi · **12 placówek dopisanych ręcznie przez handlowców
   między 10.08 a 24.08** (557 wobec 545) — to jest materiał dowodowy do prośby
   Kasi o zamknięcie zakładania placówek z formularza
2. Plik `do_sprawdzenia_recznego/BEZ_RSPO_2026-08-24.xlsx` do Kasi (25 placówek)
3. **M4 — scalanie par** (narzędzia jeszcze nie ma; po wypełnionym pliku)
4. Konto handlowca dla Zuzi
5. P29 „zgłoś do usunięcia" · P28 placówka 532 „SP 5" bez miejscowości

---

## 8e. Runda poprawek 30.08.2026 — ✅ WDROŻONA NA PRODUKCJI

**Stan: `main` = `5ad3196`, tag `v5.2-poprawki-30-08` (punkt cofnięcia kodu),
produkcja zaktualizowana 30.08 wieczorem.** Zrobione **18 z 21** punktów listy.

Lista 21+2 punktów od Kasi: `docs/poprawki/2026-08-30/` (katalog w `.gitignore`
— są tam JPG-i i nazwiska, repo jest publiczne). W środku:
**`PODSUMOWANIE_DLA_WOJTKA_2026-08-30.md`** (punkt po punkcie, językiem klienta
— to jest plik do wysłania) i **`STAN_SESJI_2026-08-30.md`** (kroki wdrożeniowe,
stan kont, checklisty). Testy: 11 plików, **1120 sprawdzeń + 93 parsers**, komplet OK.

⚠️ **Katalog produkcyjny na VPS stał na gałęzi `poprawki-2026-08`, nie na `main`**
— ktoś przełączył go w poprzedniej rundzie, a `wdroz.sh` robi `git pull --ff-only`
na BIEŻĄCEJ gałęzi, więc bez `git checkout main` pociągnąłby poprzednią rundę.
Sprawdzać to przed każdym wdrożeniem: `git branch --show-current` w katalogu apki.

⚠️ **Migracja przy kilku workerach gunicorna to wyścig.** Przy wdrożeniu demo
wyszło `duplicate column name` — każdy worker startuje osobno, każdy widzi brak
kolumny, każdy robi `ALTER TABLE`. Worker padał, kontener podnosił go po
sekundzie, więc wdrożenie „działało", ale w logu zostawał wpis wyglądający jak
awaria. `db.migruj()` łyka teraz `duplicate column` (commit `2090303`,
test S6 odpala cztery równoległe migracje). **Każda przyszła zmiana schematu
musi to zachować.**

Zrobione: eksport XLSX dla PH (przybity do własnych szkół) · chip „H handlowiec"
w kalendarzu · raport lejka per handlowiec na pulpicie · v5 jedynym widocznym
formularzem (v1–v4 pod `<details>`) · „Zapisz" bez sticky · notatki DOPISYWANE
ze stemplem serwera (bug utraty danych!) · „Oddaj lead" z powodem + czerwona
plakietka u koordynatora · flaga/filtr „szkoły z brakami" · sortowanie listy PH
wg lejka · liczniki umówione/zrealizowane · wystąpienia cyklu w karcie ·
„Zdejmij prowadzącego" w panelu przydziału.

**Sedno zgłoszenia „moja baza koordynatora jest pusta" (pkt 17):** domyślna
zakładka `/baza` „Do rozdania" + filtr handlowca dawały sprzeczny SQL
(`handlowiec=X AND handlowiec IS NULL`) → zawsze 0 rekordów. Naprawione
w `repo.domknij_zakres()` — zakres ustępuje filtrowi osoby. Ten sam bug
tłumaczy „dodać SP 1 Zabrze" — szkoła BYŁA w bazie (id 1313).

**Drugi znaleziony bug utraty danych (pkt 10):** `/api/formularz` NADPISYWAŁ
`uwagi` — druga wizyta kasowała notatkę pierwszej, choć UI v5 obiecywał
dopisywanie. Teraz serwer dopisuje (najświeższa na górze) i stempluje
`[data · kto]` z sesji dla WSZYSTKICH wariantów; wizyta bez zajęć zostawia
wpis w logu (wcześniej zero śladu — `zapisz_log` siedział w pętli po spotkaniach).

Decyzje klienta z tej rundy: **nie robimy roli „biuro"** · braki = dane ZAJĘĆ,
nie kontaktowe · oddawanie leada z powodem zamiast twardego kasowania ·
standalone PWA zostaje (zoom na iOS blokuje system, nie my).

⏸️ **Konta Małolepskiej NIE ruszaliśmy przy wdrożeniu (decyzja 30.08).** Miały
zostać zmienione, ale kontrola stanu pokazała **trzy konta**, w tym
`03. Małolepsza (koordynator)` z logowaniem **27.08** — ktoś na nim pracuje.
Najpierw potwierdzenie u Kasi, kto to był. Gdy będzie jasne: `konto.py wylacz`,
**nie** `usun` — efekt dla klienta ten sam (brak wejścia do panelu), ale wpisy
„kto zmienił" w historii zostają czytelne i decyzja jest odwracalna. To ta sama
zasada, dla której odwołanie spotkania nie kasuje wpisu.

**Cykle przestały być nietykalne (pkt 18 i 21).** Do 30.08 pojedynczych zajęć
nie dało się ani odwołać, ani przesunąć — i to nie był brak przycisku, tylko
skutek modelu: kafel cyklu w grafiku to WYSTĄPIENIE reguły, a nie wiersz
w bazie, więc każda operacja „po `e.id`" dotyczyła całego pakietu. Obie
brakujące operacje dostały więc własne drogi:
- **odwołanie jednych zajęć** → wyjątek na datę w `wyjatki_cyklu` (tabela
  istniała od początku, pisał do niej tylko importer); ślad jak przy DT
- **przesunięcie jednych zajęć** → `materializuj_terminy()` rozwija regułę na
  listę konkretnych dat w `terminy_cyklu` przy PIERWSZEJ edycji, potem
  poprawiamy jeden wiersz. Dla ekranów niewidoczne (kalendarz zawsze wolał
  listę od reguły), ale trzeba o tym wiedzieć czytając bazę: po edycji cykl
  ma ~41 wierszy terminów zamiast samej reguły
- przesunięcie PIERWSZYCH zajęć aktualizuje kolumnę `eventy.data` — niesie ją
  pół aplikacji (sortowania, statystyki, `WHERE e.data`)
- „Odwołaj" w karcie przy cyklu nazywa się teraz **„Odwołaj cały cykl"**; do
  30.08 mówił „Odwołaj" i zdejmował z grafiku wszystkie wystąpienia naraz

⚠️ **Po wdrożeniu pkt 18 zostaje robota z Kasią:** skasować DT, które PH
powpisywali jako obejście braku edycji dat cykli („jak zrobisz możliwość
edycji, wykasujemy DT z tej placówki") — które to, wie ona.

### Zostało po tej rundzie (stan na koniec 30.08)
1. **Most Zuzi** — czeka na jedną decyzję zakresu: dane pchane automatycznie czy
   pobierane na żądanie. Punkt startu: eksport XLSX istnieje (`exporter.py`),
   `drukarz` jest już polem eventu, więc kolumny, o które prosiły, mamy skąd wziąć.
2. **Pkt 7 — „inna placówka" dla PH** (biblioteka/dom kultury/seniorzy, ~pół dnia).
   Odwraca częściowo zakaz z 24.08, więc musi być wąskie: dozwolone TYLKO typy
   pozaszkolne, blokada po typie **w API, nie w UI**, wymagany adres, anty-duble
   wobec bazy i lustra RSPO. Typu „biblioteka" nie ma w słowniku — dopisać do
   KAŻDEGO profilu (grabie ze `statusy.py`).
3. **Konto Małolepskiej** — jw., czeka na potwierdzenie.
4. **Z Kasią:** skasować DT wpisane przez PH jako obejście braku edycji dat cykli
   („jak zrobisz możliwość edycji, wykasujemy DT z tej placówki") — pkt 18 jest
   wdrożony, więc obejście straciło powód; które to placówki, wie ona.
5. **Dopisywanie placówki po nr RSPO** — odłożone świadomie (backend gotowy:
   `dokladanie.zapisz` ustawia typ, adres, powiat, gminę i obszar).

### Czego ta runda uczy o zgłoszeniach
Trzy z najgłośniejszych punktów listy **nie były tym, czym wyglądały**:
„baza koordynatora pusta" i „brakuje SP 1 Zabrze" to jeden błąd filtra (szkoła
była w bazie), a „kalendarz się nie zaktualizował" to luka KARTY, nie kalendarza.
Dwa najpoważniejsze znaleziska — nadpisywane notatki z wizyt i wyścig migracji —
**nie były w ogóle zgłoszone**; wyszły przy sprawdzaniu, jak działa to, co
klient opisał. Warto trzymać ten nawyk: sprawdzać mechanizm, nie tylko objaw.

---

## 8f. Most do Akademii Silesia3D — ✅ WDROŻONY 01.09.2026

Pakiet `most/` wystawia grafik naszych zajęć do katalogu na serwerze, skąd czyta go
aplikacja partnerska (`akademia.silesia3d.site` — React SPA + Supabase, stoi na TYM
SAMYM VPS, konto `zuzia`). Opis formatu i obsługi: `most/README.md`.
Projekt dla ich strony + wzorcowy importer: `docs/poprawki/2026-08-31/dla_akademii/`
(poza repozytorium — niesie namiary na ich bazę).

⚠️ **Ich aplikacja NIE MA czym przeczytać pliku.** To było założenie zlecenia i jest
nieprawdziwe: w całym buildzie nie ma ani jednego `fetch()` po dane z własnego origin,
nie ma tabeli „przychodzące", importu ani ekranu do wgrywania. Podłożenie katalogu
samo z siebie nie uruchamia niczego — ktoś po ich stronie musi napisać import.
Dlatego robimy **plik + specyfikację**, a nie zapis do ich bazy (do której zresztą
nie mamy konta ani potwierdzenia polityk RLS).

**Cel po ich stronie: `recurring_classes`** dla cykli i `one_off_activities` dla DT.
„Lead dla lidera liderów" z prośby Kasi to rola `head_leader` — u nich nie istnieje
żaden inny byt, który by tak działał. Zalecamy im **osobną tabelę-skrzynkę**, a nie
wpychanie wprost do grafiku: `trainer_id` jest u nich wymagany, a to jest dokładnie
to pole, które ma przypisać Weronika.

### Decyzje, których nie widać z kodu

**Nazwy pól w wystawianym pliku są ICH, nie nasze** (`school`, `weekday`, `start_time`).
Import ma być przepisaniem pola w pole; gdybyśmy wysłali `placowka`/`godz_od`, po
drugiej stronie powstałby tłumacz do utrzymywania w nieskończoność.

**Wysyłamy policzone daty, nie regułę** — i liczy je `calendar_view`, ten sam kod, co
nasz kalendarz. Dwa niezależne liczenia rozjeżdżają się na pierwszym odwołanym
terminie, a wychodzi to przy awanturze o nieodbyte zajęcia.

**`ends_on` tylko dla pakietu z uzgodnioną listą dat.** Cykl z reguły nie ma końca,
a ostatnia policzona data to `CYKL_HORYZONT_TYGODNI` — miejsce, w którym przestaliśmy
liczyć. Stąd pola `occurrences_agreed` i `occurrences_horizon_weeks`.

**Dane kontaktowe NIE wychodzą** — telefon, mail, osoba kontaktowa, notatki. Most
przekracza granicę zespołu PH, a pytanie z 20.08 („czy w pliku mają być telefony do
szkół") nie doczekało się odpowiedzi; brak odpowiedzi znaczy „nie". Notatek nie
wysyłamy w całości, bo to wolny tekst, a w wolnym tekście lądują nazwiska i numery.
Pilnuje tego test szukający po **wartościach**, nie po nazwach pól.

**Znacznik „coś się zmieniło" stawia `db.zapisz_log()`** — jedyne miejsce, przez które
przechodzi każdy zapis eventu i leada. Endpointów piszących po kalendarzu jest osiem
i dziewiąty powstanie bez przypomnienia. Stała `db.MOST_BRUDNY` mieszka w `db.py`, żeby
`db` nie musiało importować `most` (byłby cykl).

**Dwa zegary:** zmiana → zapis po 20 s (dławik chroni przed przepisywaniem pliku kilka
razy w trakcie jednego zapisu formularza), cisza → zapis co godzinę (bicie serca —
bez niego zamarły znacznik wygląda jak „nic się nie zmieniło").

**Katalog wymiany to `/home/ubuntu/apps/most/{prod,demo}`, ścieżka BEZWZGLĘDNA
w compose.** Katalog aplikacji na VPS jest klonem gita, w którym leży pakiet `most/`
— `./most` przykryłby kod katalogiem danych; `apps/most` jest jego **rodzeństwem**,
więc kolizji nie ma. Osobno na profil z tego samego powodu, co osobne wolumeny.
To **jedyny bind mount** w `docker-compose.yml` i jest nim z konieczności: wolumen
dockera ma prawa `root:root drwx--x---`, więc partner by tam nie zajrzał.

⚠️ **Było `/srv/most`, przeniesione 01.09 — z powodu ludzkiego, nie technicznego.**
Obie strony pracują w `/home/ubuntu/apps` (my z konta `ubuntu`, partnerka przez skrót
do tego katalogu), a rzecz, do której trzeba skakać po systemie plików, przestaje być
sprawdzana. Kosztem jest `chmod o+x /home/ubuntu` — każde konto na serwerze może
wtedy PRZEJŚĆ przez ten katalog (wylistować już nie). Świadomy wybór; powrót to jedna
linia w compose.

**Pliki dostają prawa JAWNIE** (`most/pliki.py`, `nadaj_prawa`, przed `os.replace`).
`tempfile.mkstemp()` tworzy plik z prawami 600 i robi to celowo, a `os.replace()`
przenosi go bez zmiany praw — bez tego `zajecia.json` wychodził `-rw------- root`,
czyli nieczytelny dla partnera. Wyszło dopiero na serwerze, bo testy sprawdzały
zawartość, a nie jedyną własność, od której zależy działanie całej funkcji. Serwerem
się tego nie obejdzie: `chmod` przeżyje do następnego przepisania, czyli ~20 sekund.

**Pierwszy przebieg daje JEDNĄ linię `pierwsza_migawka`,** a nie tyle wpisów „dodane",
ile jest rekordów (na produkcji byłyby 124). Odbiorca musi odróżnić „wystawiliśmy
most" od „handlowcy wpisali dziś 124 spotkania". Ten sam warunek łapie odtworzenie
katalogu po awarii: nie mamy skrótów, więc nie WIEMY, co się zmieniło.

**Most jest dodatkiem i łapie własne wyjątki.** Handlowiec ma zapisać wizytę także
wtedy, gdy katalog wymiany zniknął. Wyłącznik: `MOST=0` w środowisku.

### Co z tego wyszło o danych — do rozmowy z Kasią
- **43 z 66 rekordów nie ma godziny rozpoczęcia**, a u partnera `start_time` jest
  wymagany. To nie błąd: termin ustala się wcześniej niż godzinę i nasza aplikacja
  świadomie tego nie blokuje. Każdy rekord jedzie z listą `missing`.
- **Na profilu `test` są tylko 2 cykle** (64 DT), na produkcji 17 cykli i 107 DT.
  Skoro most ma wozić „cykle wpisane przez PH", to dziś jest tego mało — warto to
  powiedzieć, zanim ktoś uzna, że most nie działa.
- ⚠️ Lokalny `data/prod` to STARA kopia sprzed migracji `odwolane` — `calendar_view`
  się na niej wywraca. Produkcja na VPS jest zmigrowana; lokalnej kopii nie ruszamy.

### ✅ Stan wdrożenia (01.09)
Demo i produkcja stoją na `4db3a0a`. Katalogi wymiany:
`/home/ubuntu/apps/most/{prod,demo}`, komplet plików z prawami 644, konto partnerki
czyta. Produkcja: **17 cykli, 107 DT**; demo: 3 cykle, 72 DT. Dane aplikacji
nietknięte (1614 placówek). Paczka dla partnerki idzie do
`/home/ubuntu/apps/most/dla-akademii/` — kanałem dostawy jest sam katalog mostu,
bo partnerka ma konto na tym samym serwerze.

### ⚠️ Dwa błędy wyszły PRZY WDROŻENIU, nie z testów
Oba dotyczyły rzeczy, których testy nie sprawdzały, choć sprawdzały wszystko dookoła.

**Pliki wychodziły z prawami 600.** `tempfile.mkstemp()` tworzy plik z prawami 600
celowo, a `os.replace()` przenosi go bez ich zmiany — więc `zajecia.json` wychodził
`-rw------- root` i partnerka nie mogła go otworzyć. Testy sprawdzały ZAWARTOŚĆ,
a nie jedyną własność, od której zależy działanie całej funkcji. Zamydlało obraz to,
że dzienniki `.jsonl` były przypadkiem czytelne (idą przez `open(…, "a")` respektujące
umask), więc katalog wyglądał na sprawny. Nowy test M6b sprawdza INTENCJĘ (czy kod
nadaje prawa) niezależnie od systemu — inaczej regresja przechodziłaby na Windowsie,
czyli tam, gdzie się ją pisze.

**Pierwsza migawka wyglądała jak 124 zmiany w grafiku.** Nie błąd kodu, tylko
komunikatu: odbiorca nie miał jak odróżnić „wystawiliśmy most" od „handlowcy wpisali
dziś 124 spotkania". To zgłosił drugi agent z serwera, patrząc na działający system —
nie wyszłoby z żadnego testu, bo wszystko działało zgodnie ze specyfikacją.

**Wniosek na przyszłość:** przy funkcji, której sensem jest, że KTOŚ INNY czyta wynik,
trzeba testować także to, co widzi ten ktoś — prawa, nazwy, komunikaty — a nie tylko
poprawność danych.

---

## 8g. Runda poprawek 31.08–01.09.2026 — cztery punkty Kasi

Materiał rundy: `docs/poprawki/2026-08-31/` (poza repo). Testy po rundzie:
**11 plików, 1143 sprawdzenia + 93 `parsers` + 17 node**, komplet OK.
Kod na `main` (`4db3a0a`), **wdrożone razem z mostem**.

**Pkt 3 (pilny) — przycisk „Zapisz" w karcie placówki.** Zgłoszenie brzmiało „nie
zapisuje się w kalendarzu", ale przyczyna nie była w zapisie: `+ Dodaj spotkanie`
**robił jedno i drugie** — zapisywał i przeładowywał stronę z pustym formularzem.
Nazwa mówiła tylko o pierwszej połowie, więc ludzie wypełniali dwadzieścia pól
i szukali „Zapisz", którego nie było. **Nic się nie gubiło — wpis nigdy nie
powstawał.** Nie zmieniliśmy nazwy przycisku, tylko jego działanie na to, w co
ludzie i tak wierzyli („to dodaje kolejne spotkania"): dokłada blok pól, a zapisuje
osobny „Zapisz", jednym kliknięciem dla wszystkich bloków.
Walidacja idzie PRZED wysłaniem czegokolwiek — API przyjmuje jedno spotkanie, więc
zapis leci po kolei; walidacja po drodze zostawiłaby dwa pierwsze w bazie, trzecie
odbite, a człowiek nie wiedziałby, czego nie dublować.

**Pkt 1 — DT kontra cykliczne w kalendarzu.** Kolor kafla JEST ZAJĘTY: niesie trenera
i to jego jedyne znaczenie od czerwca. Typ dostał więc własny nośnik — obwódkę
(nie wypełnienie) plus **nazwę wersalikami** (`skrot_typu`). Czerwień DT jest inna niż
`--warn` (kolizja): kolizja ma czerwone TŁO, DT samą obwódkę; gdyby alarm i typ mówiły
tym samym czerwonym, kolizja przestałaby się rzucać w oczy.
⚠️ **Do obejrzenia u klienta:** DT to ~95% wpisów, więc ramka wyjdzie prawie wszędzie.
Jeśli to szum, odwrócenie na rzadsze cykle to jedna linia CSS — opisana przy regule.

**Pkt 4 — miasto jako osobny zakres filtra kalendarza (`M`).** Miasto DAŁO SIĘ
filtrować zakresem „wszystko", ale razem ze szkołą, salą i uwagami: „Zabrze" trafiało
też w szkołę z Zabrzem w nazwie i w notatkę „dojazd przez Zabrze". Ta sama zasada,
dla której 30.08 powstał chip „H handlowiec".

**Pkt 2 — rola i konto BIURO** (widok koordynatora bez prawa zapisu).
⚠️ Odwraca decyzję z 30.08 („nie robimy roli biuro") — świadomie, na prośbę Kasi.
**Blokada stoi na METODZIE HTTP, nie na liście endpointów.** Lista wymagałaby
dopisywania każdego nowego zapisu, a pierwszy pominięty byłby dziurą — dokładnie jak
„Usuń lead", który przez trzy tygodnie renderował się handlowcowi. Test sprawdza to
na `api_zwrot_podglad`: POST, który niczego nie zmienia, a i tak jest zamknięty.
Import zostaje samemu koordynatorowi **nawet do podglądu** — samo wejście nic nie
zapisuje, ale PO TO się tam wchodzi. Konto WIDZI swoje ograniczenie (plakietka
„tylko podgląd"), żeby nikt nie zgłaszał uprawnień jako błędu.
`narzedzia/konto.py` bierze listę ról z `uzytkownicy.ROLE` zamiast kopii — inaczej
konta nowej roli nie dałoby się założyć jedynym narzędziem działającym, gdy nie da
się zalogować.

⚠️ **Konto `BIURO` to DANE, nie kod** — zakłada się je na serwerze poleceniem
`narzedzia/konto.py nowe --osoba BIURO --rola biuro --pin …`.

### Co zostało otwarte po tej rundzie (stan 01.09)

**Na serwerze, do domknięcia:**
1. Założyć konto `BIURO` (jw.) i sprawdzić z niego, że `/baza` się otwiera,
   a w pasku jest plakietka „tylko podgląd".
2. Wgrać paczkę dla partnerki do `/home/ubuntu/apps/most/dla-akademii/` —
   nigdy tam nie trafiła, więc nie ma czego podmieniać, to pierwsze wgranie.
3. Potwierdzić `namei -l`, że konto partnerki ma prawo przejścia przez
   `/home/ubuntu` i `/home/ubuntu/apps`.
4. Skasować stary `/srv/most` po sprawdzeniu, że nowy katalog ma świeższe pliki.

**Czeka na klienta:**
- **Kasia:** czy czerwona ramka na DT to nie za dużo (95% wpisów) · świadome
  potwierdzenie, że rola BIURO odwraca jej własną decyzję z 30.08.
- **Zuzia:** co znaczyło „automatycznie" (plik u nas czy zapis u niej) · czy RLS
  jest włączony i kto ma prawo `insert` na `recurring_classes` · konto testowe ·
  czy dokłada kolumnę `external_id`.
  ⚠️ **Wygląd `skrzynka.html` to prototyp, nie produkt** — jeden plik bez
  zależności, świadomie tani do wyrzucenia. Docelowo jej programista przepisuje
  go na komponent i wtedy wygląda jak reszta ICH aplikacji, nie naszej.

**Z poprzednich rund, dalej otwarte:** pkt 7 „inna placówka" dla PH · konto
Małolepskiej (czeka na potwierdzenie u Kasi) · skasowanie z Kasią DT wpisanych
przez PH jako obejście braku edycji dat cykli · dopisywanie placówki po nr RSPO.

---

## 9. Dokumentacja w `docs/`

`11_PLAN_v5.md` to żywy plan v5 ze stanem etapów — aktualizować przy każdym
domknięciu etapu. Starsze pliki (`01`–`10`) to analiza plików klienta i projekty
modułów v2–v4; są punktem odniesienia dla decyzji, nie do zmieniania.

### ⚠️ `docs/poprawki/` — cały katalog jest POZA repozytorium (31.08)

Cztery katalogi rund (`poprawka 20.08`, `23.08`, `24.08`, `poprawki 30.08`)
zeszły się w jeden `docs/poprawki/` z podkatalogami po datach w formacie ISO
(`2026-08-20` … `2026-08-30`) i **cały ten katalog jest w `.gitignore`**.

Powód nie jest porządkowy. Poprzednio każda runda miała własną regułę wpuszczającą
notatki i blokującą arkusze klienta — czyli przy każdym nowym pliku trzeba było
trafić wzorcem. Nie trafiliśmy: `git add <katalog>` dwa razy zgarnął arkusz
z nazwiskami i stawkami (raz złapany przed `push`), a `dopasowanie_prod_2026-08-23.xlsx`
naprawdę wjechał do PUBLICZNEGO repo i **siedzi w historii, której git nie
zapomina** — usunięcie z indeksu tego nie cofa. Reguła na cały katalog wymaga
zera trafnych wzorców.

Skutek do zapamiętania: **materiał rund żyje tylko lokalnie i na dysku firmowym.**
To, co ma być publiczne, wędruje świadomie do `docs/` albo do GitHub Issues —
nie trafia tam samo przez commit. Ścieżki w komentarzach kodu (`PROJEKT_BAZY_RSPO.md`
w `rejestr_rspo.py`, `dopasowanie.py`, `geografia.py`, `dokladanie.py`,
`narzedzia/migracja_rspo.py`, `templates/obszary.html`) wskazują więc pliki,
których **nie ma w klonie z GitHuba** — to celowe, ale nie zdziw się przy
świeżym `git clone` ani czytając to na VPS.

Zawartość (lokalnie): `2026-08-31` — **`PODSUMOWANIE_RUNDY.md`** (co zrobione, co
zostało — czytać najpierw), `STAN_SESJI_2026-08-31.md` (rozpoznanie sprzed rundy),
`WDROZENIE_MOSTU.md`, `ROZPOZNANIE_AKADEMIA.md` (schemat cudzej bazy) ·
`2026-08-20` — `REJESTR_POPRAWEK_2026-08.md` (P01–P31),
`STAN_SESJI_2026-08-20.md`, listy zgłoszeń od Zuzi · `2026-08-23` —
`PROJEKT_BAZY_RSPO.md` (M0–M9), `PLAN_FORMULARZA.md` (v5, E0–E8),
`PLAN_BAZY_PH.md` · `2026-08-24` — `STAN_SESJI_2026-08-24.md`,
`WDROZENIE_NA_DEMO.md`, `WDROZENIE_NA_PRODUKCJE.md` · `2026-08-30` —
`PODSUMOWANIE_DLA_WOJTKA_2026-08-30.md` (do wysłania klientowi),
`STAN_SESJI_2026-08-30.md` (kroki wdrożeniowe, stan kont, checklisty).

**Czytać w tej kolejności przy wznowieniu pracy: sekcja 8g (ostatnia runda) →
8f (most, stan produkcji) → 8e → 8d (baza RSPO) → właściwy plan.**
Szczegóły ostatniej rundy i lista otwartych zadań:
`docs/poprawki/2026-08-31/PODSUMOWANIE_RUNDY.md` (poza repo).
