# System Leadów v4

**Punkt startowy: `leady_app_v3-v2`** (v3 + ekran „Dostępność trenerów").

**Nowość v4: przydzielanie trenerów** — panel „Kogo wysłać?" przy każdym
spotkaniu (ranking: dostępność + kolizje + rejon + obciążenie, klik = przydzielenie)
oraz ekran `/rejony` z podpowiedzią rejonu z historii zajęć.
Projekt: `docs/09_PRZYDZIAL_projekt.md`, testy: `python test_przydzial.py` (30 sprawdzeń).

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
cd leady_app_v4
pip install -r requirements.txt
python app.py                       # http://127.0.0.1:5000
```

Przy pierwszym starcie tworzy się baza SQLite (`data/leady_v3.db`) i wypełniają
słowniki. Baza jest pusta — dane wczytujesz na jeden z trzech sposobów:

1. **Ekran „Import" → „Wczytaj dane demo"** — bierze realny plik klienta
   (`PH Nowy  Nad którym pracuję jako główny  .xlsx`) i planszę STARTY z zeszłego roku.
   Ścieżkę do pliku można zmienić zmienną `PLIK_PH_NOWY`.
2. **Ekran „Import" → wgraj `.xlsx`**, źródło `ph_nowy` albo `rspo`.
3. Z kodu: `python -c "import db,importer; c=db.get_conn(); print(importer.wczytaj_demo(c))"`

### Docker

```bash
docker compose up -d --build         # http://<host>:5058
```

Port 5058, żeby nie kolidować z v1 (5057). Baza w wolumenie `leady_v3_data`.

### Zmienne środowiskowe

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `DATA_DIR` | `./data` | katalog bazy SQLite |
| `PORT` | `5000` | port (tylko `python app.py`) |
| `CEL_TYGODNIOWY` | `5` | „minimum na tydzień" — ile DT ma umówić handlowiec |
| `NA_STRONE` | `150` | ile wierszy na stronę listy |
| `PLIK_PH_NOWY` | ścieżka do pliku klienta | źródło danych demo |
| `SECRET_KEY` | `leady-v3-demo` | klucz sesji Flask |

---

## Ekrany

| Ścieżka | Odpowiada zakładce klienta | Co robi |
|---|---|---|
| `/pulpit` | — | liczby, kolizje trenerów, po terminie, realizacja minimum tygodniowego, obciążenie trenerów |
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
- **Crona pilnującego terminów** — po terminie widać na pulpicie, decyzję
  o odebraniu leada podejmuje człowiek.
