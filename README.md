# System Leadów v5

**Punkt startowy: `leady_app_v4`** — wersja zaprezentowana klientowi 06.08.2026
(tag `v4.0-spotkanie`). Plan v5: `docs/11_PLAN_v5.md`.

**Nowość v5: profile baz** — ten sam kod, trzy zestawy danych. Zmienna `PROFIL`
wybiera katalog: `data/prod`, `data/test`, `data/pusta`. Bazy świadomie NIE są
gałęziami gita (`.db` to binarium, którego git nie scali; trzy gałęzie znaczyłyby
trzy merge'e przy każdej poprawce). Zarządza tym `narzedzia/baza.py` — zakładanie,
kopiowanie między profilami, kopie zapasowe `.db` + `.xlsx` z retencją, przywracanie.
Na profilu innym niż produkcja u góry każdego ekranu wisi kolorowy pasek.

**Nowość v5: formularz terenowy w DWÓCH wariantach** (`/formularz` → wybór) —
do pokazania klientowi na jego danych, żeby wybrał sam. Oba zapisują przez to samo
API i tę samą walidację; różni je wyłącznie sposób podania.

| | `/formularz/kroki` (typ 1) | `/formularz/ciagly` (typ 2) |
|---|---|---|
| Układ | cztery kroki, jedna kolumna | jeden ciągły, przewijany w dół |
| Wzór | nasza propozycja | **makieta klienta z 06.08** |
| Szkoła | wyszukiwarka (wpisujesz fragment) | para list miejscowość → placówka |
| Walidacja | blokuje przejście dalej | zbiorczo przy zapisie |
| Lepszy na | telefonie, przy rozmowie na stojąco | komputerze i tablecie, przy biurku |

Oba zajmują **całe okno** — pasek aplikacji i stopka znikają, wyjście jest jedno
i jawne („Zakończ”), bo na telefonie nawigacja z logo i dziesięcioma zakładkami
zjadała pół ekranu i się zawijała.

**Awaria w trakcie wypełniania** (`static/formularz_awaria.js`) — cztery przypadki:
szkic leci do pamięci telefonu po każdej zmianie pola; przy zamknięciu karty
z niezapisanymi danymi wyskakuje ostrzeżenie; gdy zapis nie dojdzie, treść
formularza ląduje w kolejce „niewysłane” i wraca czerwoną ramką z przyciskiem
**Ponów wysyłkę**; a gdy zapis dojdzie, lecz odpowiedź nie wróci — każda próba
niesie `klucz_zapisu`, więc ponowienie **nie tworzy drugiego leada** (serwer
zwraca poprzedni wynik z tabeli `zapisy_formularza`).

Wspólne dla obu: pola ≥46 px i font 16 px (poniżej tego Safari sam przybliża widok),
**własne szkoły na górze listy**, przy dacie DT podpowiedź **kto jest wolny i jeździ
po tym mieście** (ranking z `przydzial.py`), szkic w telefonie (localStorage) —
utrata zasięgu w połowie nie kasuje wpisanego tekstu — i zapis JEDNYM żądaniem,
więc nie powstaje lead bez DT.
Projekt: `docs/11_PLAN_v5.md`, testy: `python test_formularz.py`.

**Nowość v5: logowanie PIN-em i role** (`uzytkownicy.py`) — wybór osoby z listy
plus czterocyfrowy PIN na własnej klawiaturze ekranowej, sesja 30 dni. **Trzy role:**

| | trener | handlowiec | koordynator |
|---|---|---|---|
| Własna dostępność — podgląd i edycja | ✅ | podgląd | ✅ |
| Cudza dostępność — zmiana | ❌ | ❌ | ✅ |
| Kalendarz DT | ✅ | ✅ | ✅ |
| Formularz, moje szkoły, plan tygodnia | ❌ | ✅ | ✅ |
| Baza, zbiorczy, słowniki, import, konta | ❌ | ❌ | ✅ |

Trener wchodzi na grafik **z własnym nazwiskiem już przypiętym** (kłódka na
chipie filtra) — otwiera go po to, żeby zobaczyć siebie, a nie szukać się wśród
39 osób. Filtr jest jawny: „Pokazuję tylko Twój grafik — Pokaż wszystkich →",
a po odpięciu widzi cały zespół. Ta sama zasada co przy „moich szkołach"
handlowca: rozstrzyga obecność parametru w adresie, więc zwykłe wejście na ekran
wraca do stanu domyślnego.

**Trener** edytuje wyłącznie swój wiersz grafiku — w ich zeszłorocznym pliku każdy
mógł nadpisać każdemu deklarację i nikt potem nie wiedział, czyja wersja jest
aktualna. **Handlowiec** grafik widzi (bez tego nie umówi DT), ale go nie zmienia.
Konta zakładają się same ze słowników `handlowiec` i `trener`; osoba figurująca
w obu zachowuje szerszą rolę. Handlowiec ma **filtr własnych szkół przypięty
domyślnie, ale jawny i zdejmowalny** — po przejściu na inny ekran wraca sam.
PIN-y trzymane jako PBKDF2 z solą per konto; po 5 błędnych próbach konto blokuje
się, a nadanie nowego PIN-u je odblokowuje. Panel `/uzytkownicy` pokazuje PIN
raz, przy nadaniu. Do tego token CSRF na wszystkich zapisach i `kto` w historii
zmian brany z sesji zamiast dotychczasowego „demo".
Testy: `python test_logowanie.py` (75 sprawdzeń).

**Tryb serwisowy** (`PIN_SERWISOWY=7777`) — jeden PIN wpuszcza **bez wyboru osoby**
na uprawnienia koordynatora. Wygodne przy pracy nad aplikacją; to jednak klucz
uniwersalny, więc obwarowany trzema rzeczami: żyje wyłącznie w zmiennej
środowiskowej (restart bez niej i tryb znika, sesje przestają działać), na profilu
`prod` wymaga dodatkowo `PIN_SERWISOWY_PROD=tak`, a gdy działa — na każdym ekranie
wisi czerwony pasek w pasy i każde wejście ląduje w historii jako
„logowanie serwisowe". Testy: `python test_serwis.py` (30 sprawdzeń).

**Nowość v5: auto-zwrot po terminie** (`zwrot.py`) — szkoły po terminie wracają
do puli nieprzydzielonych SAME. Z karencją (`KARENCJA_DNI`, domyślnie 2),
z ostrzeżeniem „wraca do puli za N dni" u handlowca i na pulpicie, i **bez kasowania
pracy** — wraca wyłącznie przypisanie, notatki i kontakty zostają przy placówce.
Automat wisi na zwykłym ruchu w aplikacji (najwyżej raz na godzinę), nie na cronie,
który na VPS potrafi cicho umrzeć.

---

## Wersja v4 (zaprezentowana 06.08)

**Punkt startowy: `leady_app_v3-v2`** (v3 + ekran „Dostępność trenerów").

**Nowość v4: przydzielanie trenerów** — panel „Kogo wysłać?" przy każdym
spotkaniu (ranking: dostępność + kolizje + rejon + obciążenie, klik = przydzielenie)
oraz ekran `/rejony` z podpowiedzią rejonu z historii zajęć.
Projekt: `docs/09_PRZYDZIAL_projekt.md`, testy: `python test_przydzial.py` (30 sprawdzeń).

**Nowość v4: filtr wpisywany** — druga linia paska filtrów, w której **wpisuje się**
fragment tekstu zamiast wybierać z listy. Wpisów może być kilka (LUB / ORAZ), każdy
da się wyłączyć bez kasowania i przypiąć kłódką (przeżywa „Wyczyść", zmianę zakładki,
miesiąca i widoku). Na listach leadów zakresy to `◇` dowolna osoba / `H` handlowiec /
`T` prowadzący; na **kalendarzu i dostępności** — `∗` wszystko / `N` nazwisko
(„nazwisko" na grafiku to kto TAM BĘDZIE — bez handlowca, bo on nie jedzie
na zajęcia; kilka osób figuruje u nich i jako handlowiec, i jako trener).
Po prowadzących nie dało się wcześniej filtrować w ogóle, a lista „— wszyscy
trenerzy —" na kalendarzu działała tylko w widoku Agenda (zdjęta, stare linki
`?trener=` dalej działają). Przy okazji rozdzielone dwa języki pola:
**zimny błękit = filtr**, **ciepły krem = wypełnij (zapis do bazy)**.
Projekt: `docs/10_FILTR_OSOB_projekt.md`, testy: `python test_filtr_osob.py` (88 sprawdzeń).

Odziedziczone z v2: ekran `/dostepnosc` — deklaracje dostępności per dzień
i wyliczone wolne okna (deklaracja minus kalendarz). Projekt:
`docs/08_DOSTEPNOSC_projekt.md`, testy: `python test_dostepnosc.py` (24 sprawdzenia).

Aplikacja Flask zastępująca arkusz, w którym firma szkoleniowa (zajęcia druku 3D
dla szkół i przedszkoli) prowadzi leady, grafik trenerów i rozliczenia dokumentów.
**DT = dzień technologiczny** — pokazowy dzień w szkole, po którym otwierają się
grupy zajęć cyklicznych.

To **prototyp do pokazania klientowi**, uruchomiony na jego realnych danych,
nie system produkcyjny. Świadomie nie ma logowania ani ról — patrz „Czego tu nie ma".

---

## Co to rozwiązuje

Cztery bóle wynikające wprost z ich pliku i z rozmowy:

| Ból | Jak było w arkuszu | Jak jest tutaj |
|---|---|---|
| **Trener ma 2–3 DT w jednym dniu, a w kalendarzu widać jedno** | Komórka kalendarza to `XLOOKUP(data & "\|\|" & trener; …)`, a `XLOOKUP` zwraca **pierwsze** trafienie. Drugie DT istniało w danych, ale formuła nie umiała go pokazać. | Kalendarz jest widokiem z tabeli spotkań. W komórce jest **lista** — widać wszystkie. Dodatkowo ostrzegamy, gdy godziny się nakładają (bo godziny to osobne pola czasu, a nie tekst `08:00-12:30`). |
| **Listy rozwijane rozjeżdżają się między zakładkami** | 25 reguł walidacji z listami wklejonymi jako tekst; `02. Olaszewska` obok `02. Olszewska`, trzy różne listy miejscowości, dwie listy trenerów. W planszy STARTY **50 zapisów nazwiska dla 29 osób**. | Jeden słownik + tabela aliasów. Zapis wartości spoza listy jest odrzucany. Aliasy scalają literówki przy imporcie. |
| **„Wiersz kopiuje się do trzech miejsc"** | Trzy kopie danych, które zawsze się rozjadą. | Jedno źródło, ekrany to filtry. Poprawka daty w jednym miejscu aktualizuje wszystko. |
| **„Koordynator odbiera dostęp i przenosi rekord"** | Ręczne wycinanie wierszy do zakładki „niewykorzystane rekordy". | Zmiana statusu. Nic się nie usuwa, nic nie przenosi — zmienia się to, na których ekranach lead widać. |

---

## Uruchomienie

```bash
cd leady_app_v5
pip install -r requirements.txt

# PowerShell — profil wybiera bazę, kod jest ten sam
$env:PROFIL="test";  python app.py    # http://127.0.0.1:5301/formularz
$env:PROFIL="pusta"; python app.py

python narzedzia/baza.py lista        # jakie profile istnieją i ile mają danych

# karta dostępu do wydruku (PIN-y + uprawnienia) — wymaga `pip install reportlab`
python narzedzia/karta_dostepu.py --profil test
```

Karta ląduje w `dostepy/` — katalogu poza gitem, bo zawiera PIN-y. PIN-u nie da
się odczytać z bazy (leży tam tylko skrót), więc narzędzie **nadaje nowe** i od
razu wpisuje je do PDF-a; papier i baza nie mają jak się rozjechać. Wydrukuj,
rozetnij dolne paski, rozdaj i skasuj plik.

Przy pierwszym starcie tworzy się baza SQLite (`data/leady_v3.db`) i wypełniają
słowniki. Baza jest pusta — dane wczytujesz na jeden z trzech sposobów:

1. **Ekran „Import" → „Wczytaj dane demo"** — bierze realny plik klienta
   (`PH Nowy  Nad którym pracuję jako główny  .xlsx`) i planszę STARTY z zeszłego roku.
   Ścieżkę do pliku można zmienić zmienną `PLIK_PH_NOWY`.
2. **Ekran „Import" → wgraj `.xlsx`**, źródło `ph_nowy` albo `rspo`.
3. Z kodu: `python -c "import db,importer; c=db.get_conn(); print(importer.wczytaj_demo(c))"`

### Docker

```bash
docker compose up -d --build         # http://<host>:5301
```

Port 5301, żeby nie kolidować z v1 (5057) ani v4 (5058). Baza w wolumenie `leady_v5_data`, kontener `leady_app_v5` — v4 na tym samym serwerze działa dalej nietknięta.

### Zmienne środowiskowe

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `DATA_DIR` | `./data/<PROFIL>` | katalog bazy SQLite; ustawiony wprost ma pierwszeństwo przed `PROFIL` (tak działa docker-compose) |
| `PORT` | `5301` | port (tylko `python app.py`); własny, bo na 5000 startuje domyślnie każda apka Flaska i nowy proces cicho nie zajmuje portu |
| `CEL_TYGODNIOWY` | `5` | „minimum na tydzień" — ile DT ma umówić handlowiec |
| `NA_STRONE` | `150` | ile wierszy na stronę listy |
| `PLIK_PH_NOWY` | ścieżka do pliku klienta | źródło danych demo |
| `SECRET_KEY` | `leady-v3-demo` | klucz sesji Flask — **na produkcji ustaw wlasny**, inaczej da się podrobić sesję |
| `PIN_KOORDYNATORA` | `0000` | PIN startowy konta `Koordynator` przy pierwszym uruchomieniu (v5) |
| `PIN_SERWISOWY` | — | 4 cyfry: **tryb serwisowy** — wejście bez wyboru osoby, na uprawnienia koordynatora. Do pracy nad aplikacją; **wyłącz przed wdrożeniem** (v5) |
| `PIN_SERWISOWY_PROD` | — | `tak` — dopiero to włącza tryb serwisowy na profilu `prod`. Sam `PIN_SERWISOWY` na produkcji nie wystarcza (v5) |
| `HTTPS` | — | ustaw cokolwiek za reverse proxy z HTTPS — włącza `Secure` na ciastku sesji (v5) |
| `PROFIL` | `test` | która baza: `prod` / `test` / `pusta` (v5) |
| `KARENCJA_DNI` | `2` | ile dni po terminie zanim lead wróci do puli (v5) |
| `OSTRZEZENIE_DNI` | `3` | z ilodniowym wyprzedzeniem ostrzegać handlowca (v5) |

---

## Ekrany

| Ścieżka | Odpowiada zakładce klienta | Co robi |
|---|---|---|
| `/logowanie` | — | **NOWE v5** — wybór osoby + PIN na klawiaturze ekranowej |
| `/uzytkownicy` | — | **NOWE v5** — panel koordynatora: konta, role, nadawanie i reset PIN-ów |
| `/formularz` | — | **NOWE v5** — wybór wariantu formularza: dwa linki |
| `/formularz/kroki` | — | **wariant 1** — cztery kroki, jedna kolumna, wyszukiwarka szkół; pod telefon |
| `/formularz/ciagly` | — | **wariant 2** — jeden ciągły formularz wg makiety klienta z 06.08, para list miejscowość→placówka; pod komputer i tablet |
| `/pulpit` | — | liczby, kolizje trenerów, **co wraca do puli (v5)**, po terminie, realizacja minimum tygodniowego, obciążenie trenerów |
| `/baza` | `BAZA` | baza placówek do rozdania; zaznaczasz wiele wierszy, wybierasz handlowca i termin ostateczny, „Przypisz" |
| `/leady` | zakładki handlowców | leady w pracy; edycja inline, przypięcie na tydzień, „odbierz handlowcowi" |
| `/zbiorczy` | `Zbiorczy` | widok Julii — jej kolumny (umowa, standardy, niekaralność, Librus…) jako listy Tak/Nie |
| `/niewykorzystane` | `Niewykorzystane rekordy` | pula zwrotna; przypisanie innemu handlowcowi |
| `/tydzien` | — (z notatek: „wybrane szkoły na tydzień do góry") | plan tygodnia, pogrupowany po handlowcu |
| `/kalendarz?widok=macierz` | `Kalendarz <MIESIĄC> DT` | siatka trener × dzień, bloki tygodniowe; **wiele wpisów w komórce** |
| `/kalendarz?widok=agenda` | — | dzień po dniu, posortowane po godzinie (czytelne przy ~30 zajęciach dziennie) |
| `/kalendarz?widok=starty` | `STARTY <MIESIĄC>` | plansza całej firmy w kartach: godziny, szkoła, grupa, sprzęt, trener, zastępstwo, drukarz, kod Tinkercad |
| `/dostepnosc` | `DOSTĘPNOŚĆ NA DT - TRENERZY` (plik zeszłoroczny) | **NOWE w v2** — kiedy kto może: deklaracje per dzień, arkuszowe „XXX" jako stan „niedostępny", a w komórce wyliczone **wolne okna** (deklaracja minus kalendarz) |
| `/rejony` | — (w arkuszu nie było wcale) | **NOWE w v4** — kto po jakich miastach jeździ; rejon podpowiadany z historii zajęć, „Przyjmij jako rejon" jednym klikiem |
| `/lead/<id>` | — | karta leada: dane placówki, pola, kolumny Julii, spotkania, historia zmian; przy spotkaniu **„Kogo wysłać?"** — ranking trenerów (dostępność + kolizje + rejon + obciążenie), klik = przydzielenie |
| `/slowniki` | — | jedno źródło list + aliasy („zapis w arkuszu → wartość kanoniczna") |
| `/import` | — | import xlsx / RSPO / dane demo, z raportem |
| `/export.xlsx?<filtry>` | — | eksport **dokładnie tego, co widać po filtrach** |

Eksport ma cztery arkusze: `Leady` (układ kolumn jak u nich), `Spotkania`
(1 wiersz = 1 spotkanie), `Kolizje` i `Filtr` (co było ustawione przy eksporcie).

---

## Model danych

```
placowki   1 wiersz = 1 szkoła / przedszkole / instytucja kultury
leady      przypisanie placówki handlowcowi + proces sprzedażowy + kolumny Julii
eventy     1 wiersz = 1 SPOTKANIE (DT | START | CYKLICZNE | JEDNORAZÓWKA | FESTYN | VR)
wyjatki_cyklu   zastępstwo albo odwołanie na KONKRETNĄ datę cyklu
dostepnosc      dostępność trenera per dzień (ekran /dostepnosc — nowość v2)
rejony          miasta, po których jeździ trener (ekran /rejony — nowość v4)
slowniki   wszystkie listy rozwijane + kolor trenera
aliasy     literówki i warianty zapisu → wartość kanoniczna
log        ślad zmian (podstawa kontroli „czy handlowiec ruszył lead przed terminem")
```

Dwie decyzje warte uwagi:

- **Zajęcia cykliczne to jeden rekord z regułą** (dzień tygodnia, godziny,
  co ile tygodni), a wystąpienia liczymy dopiero na potrzeby widoku miesiąca.
  W arkuszu tydzień 2 był w 149 z 155 komórek kopią tygodnia 1 — tutaj zmiana
  godziny to jedna edycja, a zastępstwo to jeden wyjątek na jednej dacie.
- **Prefiksy `01. `, `02. ` zostają w wartościach**, bo klient sortuje po nich,
  ale nie są identyfikatorem: w jego dwóch listach ten sam numer to dwie różne
  osoby (`18. Bitner` vs `18. Młynarczyk Adam`). Tożsamość niesie część nazwowa.

---

## Pliki

| Plik | Za co odpowiada |
|---|---|
| `app.py` | route'y, API, walidacja zapisu, przepływ leada |
| `db.py` | schemat, definicje pól (jedno źródło dla UI, importu i eksportu), migracje |
| `repo.py` | wszystkie zapytania o leady — **jedna** funkcja filtrująca dla ekranu i eksportu |
| `calendar_view.py` | trzy widoki kalendarza, rozwijanie cykli, wykrywanie kolizji |
| `dostepnosc_view.py` | dostępność trenerów: stany komórki, wolne okna, ostrzeżenia (v2) |
| `przydzial.py` | ranking kandydatów na spotkanie + rejony trenerów (v4) |
| `uzytkownicy.py` | konta, PIN-y (PBKDF2), role, sesja, blokada po błędnych próbach (v5) |
| `zwrot.py` | auto-zwrot przeterminowanych leadów do puli: karencja, ostrzeżenia, przebieg (v5) |
| `static/formularz_awaria.js` | co się dzieje przy awarii w trakcie wypełniania: szkic, ostrzeżenie przy wyjściu, kolejka „niewysłane” z ponowieniem (v5) |
| `narzedzia/baza.py` | profile baz, kopie zapasowe i przywracanie (v5) |
| `narzedzia/konto.py` | konta z linii poleceń — wyjście awaryjne, gdy nie da się zalogować (v5) |
| `narzedzia/karta_dostepu.py` | PDF do wydruku: PIN-y, tabela uprawnień i paski do rozcięcia (v5) |
| `parsers.py` | parsowanie brudnych danych z arkusza (daty, godziny, „10 klas", „około 200", telefony) |
| `importer.py` | import `PH Nowy`, RSPO i planszy STARTY, z deduplikacją placówek |
| `exporter.py` | eksport XLSX w układzie kolumn klienta |
| `seed.py` | słowniki, aliasy i kolory trenerów odtworzone z jego plików |
| `templates/`, `static/` | warstwa prezentacji — język wizualny pierwszej wersji (granatowy pasek, białe panele, niebieski akcent, Segoe UI), odświeżony |

## Testy

```bash
python test_parsers.py        # 93 przypadki — parsowanie realnych, brudnych wartości
python test_scenariusze.py    # 67 sprawdzeń — przejście scenariuszy klienta przez API
python test_dostepnosc.py     # 24 sprawdzenia — dostępność i wolne okna (v2)
python test_przydzial.py      # 30 sprawdzeń — ranking kandydatów, rejony (v4)
python test_filtr_osob.py     # 88 sprawdzeń — filtr wpisywany, listy + grafik (v4)
python test_trener.py         # 61 sprawdzeń — rola trenera, dostępność tylko własna (v5)
python test_serwis.py         # 30 sprawdzeń — tryb serwisowy i jego ograniczenia (v5)
python test_logowanie.py      # 75 sprawdzeń — logowanie, role, filtr „moje”, CSRF (v5)
python test_formularz.py      # 93 sprawdzenia — oba warianty, awaria przy zapisie, auto-zwrot (v5)
```

`test_scenariusze.py` przechodzi przez to, o co klient poprosił: przypisanie,
umówienie DT, **dwa DT jednego trenera w jednym dniu**, ostrzeżenie o nakładających
się godzinach, przesunięcie terminu, nowy miesiąc tworzący się sam, odebranie leada,
odrzucenie wartości spoza słownika, plan tygodnia, cykl z zastępstwem i odwołaniem,
eksport wyfiltrowanego widoku. Oba testy działają na własnej, tymczasowej bazie.

## Dokumentacja analizy

W `docs/`:

| Plik | Co zawiera |
|---|---|
| `01_USTALENIA_analiza.md` | ustalenia z ich aktualnego pliku + wymagania + notatki ze spotkania |
| `02_RAPORT_DT_2025-2026.md` | analiza zeszłorocznego pliku: plansze STARTY, mapa kolor→trener, rozliczenia, 8 zgubionych modułów |
| `03_SPEC_v3.md` | specyfikacja: model danych, moduły, route'y, scenariusze, ryzyka |
| `04_AUDYT_v1_i_dane.md` | audyt poprzedniej wersji + inwentarz realnych wartości w każdej kolumnie |
| `07_PYTANIA_do_klienta.md` | **do wysłania klientowi** — pytania z dowodami z pliku |
| `08_DOSTEPNOSC_projekt.md` | projekt ekranu dostępności trenerów (v2) |
| `09_PRZYDZIAL_projekt.md` | projekt przydzielania trenerów i rejonów (v4) |
| `design/` | design handoff, makieta, dane STARTY, mapa aliasów trenerów |

---

## Czego tu nie ma (świadomie)

- **Logowania i ról** — każdy widzi wszystko. Do decyzji, czy izolacja handlowców
  jest twardym wymogiem, czy wygodą.
- ~~Dostępności trenerów jako ekranu~~ — **jest w tej wersji** (`/dostepnosc`).
  Poza zakresem została dostępność cykliczna („każdy wtorek 8–12") i samoobsługa
  trenera (wymaga logowania) — patrz `docs/08_DOSTEPNOSC_projekt.md`.
- **Push do Google Calendar** — klient sam napisał, że to przyszłość.
- **Rozliczeń** (`JEDNORAZÓWKI`, `PRZEDSZKOLA FAKTURY`) — logika jest prosta
  (30% trener, 30% handlowiec, 5% Julia, reszta firma), ale to osobny moduł.
- ~~Rejonu trenera~~ — **jest w tej wersji** (`/rejony`). Poza zakresem zostały:
  masowa obsada spotkań bez trenera, zastępstwa (trener wypada na tydzień)
  i liczenie dojazdu między szkołami — patrz `docs/09_PRZYDZIAL_projekt.md`.
- **RSPO przez API** — import jest z pliku.
- ~~Crona pilnującego terminów~~ — **jest w v5**: `zwrot.py` oddaje przeterminowane
  leady do puli sam, bez crona. Ręczne „Zwróć teraz" zostaje na pulpicie.
- ~~Logowania i ról~~ — **jest w v5**: PIN, dwie role, filtr własnych szkół.
  Poza zakresem zostało logowanie trenerów (oni nie mają jeszcze kont) i pełny
  dziennik audytu — historia notuje autora, ale nie każdy odczyt.
- **Pracy offline** — formularz działa online, szkic trzyma się w telefonie.
  Kolejka wysyłkowa po odzyskaniu zasięgu to etap po wdrożeniu.
