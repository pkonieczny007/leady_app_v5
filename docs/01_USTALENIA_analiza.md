# Ustalenia z analizy źródeł (baza dla v3)

Stan na 30.07.2026. Zebrane z: `PH Nowy ... .xlsx`, `opis tabelki do zrobionia.docx`,
`DT 2025-2026 NOWY PIĘKNY PLIK.xlsx`, notatek ze spotkania 24.07, `leady_app` (v1/v2).

---

## A. `PH Nowy` — to jest stan AKTUALNY, na tym pracują

16 zakładek. **Ważne: to nie ten sam plik, co opisany w `00_kontekst_v1.md`** — klient
poszedł dalej i sam zbudował część architektury, o którą prosił.

| # | Zakładka | Rola | Zawartość |
|---|---|---|---|
| 0 | `Zbiorczy` | arkusz Julki + **hub kalendarzy** | `VSTACK(FILTER(...))` z 5 zakładek handlowców + kolumny Julki + 3 kolumny techniczne |
| 1 | `BAZA` | baza główna (RSPO) | ~980 szkół, 167 z przypisanym handlowcem, 11 walidacji |
| 2 | `Niewykorzystane rekordy` | pula zwrotna | `QUERY(... WHERE Col3 = '04. BRAK KONTAKTU ZE SZKOŁĄ')` |
| 3 | `Szkoły z DT` | widok | `QUERY(... WHERE Col12 = '01. Tak')` (kolumna L = DT) |
| 4 | `Szkoły z cyklami` | widok | `QUERY(... WHERE Col21 = '01. Tak')` (kolumna U = Cykle) |
| 5–10 | `Kalendarz WRZESIEŃ/PAŹDZIERNIK/LISTOPAD/GRUDZIEŃ/STYCZEŃ/LUTY DT` | kalendarze | siatka trener × dzień, bloki tygodniowe |
| 11–15 | `Sacawa`, `Olszewska`, `Małolepsza`, `Chytry`, `Młynarczyk` | arkusze handlowców | dane wpisywane ręcznie, dane od wiersza 4 |

### Kolumny (identyczne we wszystkich zakładkach operacyjnych, A→AG)

```
A  Handlowiec                    S  Ilość dzieci w klasach
B  Status szkoły                 T  Mail do rodziców na dziennik elektroniczny
C  Status realizacji             U  Cykle
D  death line  (= deadline!)     V  Zajecia cykliczne (dzień tygodnia)
E  Miejscowość                   W  Numer sali cykle
F  Numer placówki                X  Zajecia cykliczne (godzina)
G  Adres placówki                Y  Trener
H  Osoby decyzyjne i kontakt     Z  Mail z wnioskiem o wynajem sali
I  numer telefonu                AA Dane do umowy            WYPEŁNIA JULIA
J  mail                          AB Standardy ochrony małoletnich  WYPEŁNIA JULIA
K  Uwagi                         AC Oświadczenia trenerów    WYPEŁNIA JULIA
L  DT                            AD Zaświadczenie o niekaralności WYPEŁNIA JULIA
M  Data DT                       AE Podanie o wynajem sali    WYPEŁNIA JULIA
N  Godzina DT                    AF Umowa podpisana           WYPEŁNIA JULIA
O  Prowadzący DT                 AG Librus                    WYPEŁNIA JULIA
P  Numer sali DT
Q  mail propozycja lub ustalenie DT      (tylko w Zbiorczym dodatkowo:)
R  Ilość klas 1-4                AG Klucz | AH trener | AI kod do kalendarza
```

Uwaga: w `Zbiorczy` kolumna `Z` = „Dane do umowy WYPEŁNIA JULIA" (przesunięcie o 1
względem BAZY, która ma `Z` = „Mail z wnioskiem o wynajem sali"). Rozjazd kolumn
między zakładkami — realny problem do usunięcia w v3.

### Mechanizm kalendarza — i ŹRÓDŁO ICH BUGA (najważniejsze odkrycie)

W `Zbiorczy` są trzy kolumny techniczne:

```
AG „Klucz"  = MAP(...LAMBDA(...)) → wielolinijkowa KARTA leada:
      Handlowiec: 01. Sacawa
      Status szkoły: 02. Kontynuacja
      Miejscowość: 05. Knurów
      Numer placówki: MSP 2
      Adres placówki: Thomasa Woodrowa Wilsona 22
      Osoby decyzyjne i kontakt: Joanna Kucyniak
      Numer telefonu: 32 235 27 27
      Godzina DT: 08:55
      Numer sali DT:
      Ilość klas 1-4: 12 klas
      Ilość dzieci w klasach: około 240

AH „trener" = M2&"-"&O2                       (data-trener, surowe)
AI „kod do kalendarza" = MAP(M,O, LAMBDA(d,t, TEXT(d,"dd.mm.yyyy") & "||" & t))
```

Komórka kalendarza (np. `Kalendarz WRZESIEŃ DT!B3`):

```
=IFERROR(XLOOKUP(TEXT(B$2,"dd.mm.yyyy") & "||" & $A3,
                 Zbiorczy!$AI$2:$AI$1100, Zbiorczy!$AG$2:$AG$1100), "")
```

**`XLOOKUP` zwraca PIERWSZE trafienie.** Dlatego gdy trener ma 2–3 DT w tym samym dniu,
w kalendarzu widać tylko jedno. To dokładnie bug zgłoszony w `.docx` i powtórzony
w notatkach ze spotkania („żeby nie mógł trener 2× mieć aktywności").

W wierszach 50+ arkusza WRZESIEŃ widać ich **próbę naprawy**, niedokończoną
(zastosowana tylko w części wierszy):

```
=IFERROR(TEXTJOIN(CHAR(10) & "--------------------" & CHAR(10), PRAWDZIWE,
         FILTER(Zbiorczy!$AG:$AG, Zbiorczy!$AI:$AI = TEXT(B$2,"dd.mm.yyyy")&"||"&$A50)), "")
```

→ **v3 musi pokazywać WSZYSTKIE eventy w komórce (dzień × trener) i dodatkowo ostrzegać
o kolizji godzin.** To jest sztandarowa funkcja do pokazania klientowi.

### Layout kalendarza (do odwzorowania w v3)

- Wiersz 1: nazwy dni `Poniedziałek…Piątek` (pon–pt, **bez weekendu**)
- Wiersz 2: daty (pierwsza wpisana, kolejne `=B2+1`)
- Kolumna A: lista trenerów (23 pozycje, numerowane `01. …`)
- Bloki tygodniowe **obok siebie**: `A|B-F` (tyg. 1), `H|I-M` (tyg. 2), `O|P-T` (tyg. 3),
  `V|W-AA` (tyg. 4), `AC|AD-AH` (tyg. 5); kolumny `G, N, U, AB` = separatory
- Kolumna z nazwą trenera powtórzona w każdym bloku (`A`, `H`, `O`, `V`, `AC`)
- Miesiąc zaczyna się od poniedziałku tygodnia, w którym jest 1. dzień miesiąca
  (WRZESIEŃ startuje `2026-08-31`, PAŹDZIERNIK `2026-09-28`)

### Kolory trenerów (formatowanie warunkowe, tylko 4 zdefiniowane)

| Trener | RGB |
|---|---|
| 01. Małolepsza | `FF00FF` (magenta) |
| 02. Olszewska | `FF9900` (pomarańcz) |
| 03. Majewska | `00FF00` (zielony) |
| 04. Zemela | `B7E1CD` (mięta) |

Pozostałych 19 trenerów bez koloru → w v3 kolory generowane deterministycznie
+ edytowalne w słownikach.

### Słowniki (z 11 walidacji) — i ich rozjazdy

| Słownik | Wartości |
|---|---|
| Status szkoły | `01. Nowa szkoła`, `02. Kontynuacja` |
| Status realizacji | `01. Próba kontaktu (Brak konkretów)`, `02. Próba kontaktu (czekam na termin)`, `03. DT umówione`, `04. BRAK KONTAKTU ZE SZKOŁĄ` |
| DT | `01. Tak`, `02. Do ustalenia` |
| Cykle / Tak-Nie | `01. Tak`, `02. Nie` |
| mail propozycja | `01. Podsumowanie DT`, `02. Propozycja DT` |
| Dzień tygodnia | `poniedziałek…sobota` |
| Handlowcy | `01. Sacawa`, `02. Olszewska`, `03. Małolepsza`, `04. Chytry` (+`Bitner` / +`05. Młynarczyk`) |
| Miejscowości | 20–22 pozycje, **trzy różne warianty listy** |
| Trenerzy | **dwie różne listy** — 40-pozycyjna (kol. Y) i 24-pozycyjna (kol. O) |

**Udokumentowane rozjazdy (dowód, że słownik centralny jest konieczny):**

- `Sacawa!A20:A200` i `Olszewska!A29:A340` → literówka **`02. Olaszewska`**
  (zamiast `02. Olszewska`) — psuje filtrowanie po handlowcu
- `Olszewska!Y4:Y340` → własna 3-pozycyjna lista trenerów
  (`01. Olszewska Zuza, 02. Sacawa Dominika, 03. Zemela Paulina`)
- Miejscowości: `BAZA` ma `09. Pszczyna powiat`/`15. Będzin powiat`,
  handlowcy mają `09. Pszczyna`/`15. Będzin`, `Sacawa!E14:E200` ma jeszcze inną
  (`08. Katowice Południe`, `10. Katowice`, `20. Ornontowice`, `21. Wyry`, `22. Gostyń`)
- Dublet w tej samej liście: `14. Dąbrowa Górnicza` i `17. Dąbrowa Górnicza`
- Literówki w kalendarzu vs walidacji: `11. Białass (Pszczyna)` vs `11. Białas (Pszczyna)`,
  `23. Trenner 5` vs `24. Trener 5`, `22. Trene 3` vs `21. Trener 3`
- W liście trenerów puste pozycje `31. , 32., 33. … 40.`
- Zakładka `Kalendarz LUTY DT` jest **pusta** (A1:A1) — dowód, że mechanizm
  „nowy miesiąc sam się tworzy" NIE działa; trzeba go zrobić ręcznie
- Formuła `Zbiorczy!A2` ma literówkę w odwołaniu: `FILTER(Chytry!A2:Y1075, Chytrychi!A2:A1075<>"")`
- `Niewykorzystane rekordy` i `Szkoły z DT` czytają tylko z 4 zakładek
  (`Sacawa; Olszewska; Małolepsza; Chytry`) — **Młynarczyk wypada z tych widoków**
- `Sacawa` ma `max_row = 50500` (rozdmuchany arkusz)

### Zbitki w danych (do rozbicia na kolumny)

| Kolumna | Realne wartości |
|---|---|
| R `Ilość klas 1-4` | `10 klas`, `12 klas`, `8 klas`, `14 klas` → liczba + tekst |
| S `Ilość dzieci` | `około 200`, `około 240`, `330` → raz tekst, raz liczba |
| N `Godzina DT` | `datetime.time(8,0)`, `time(8,55)`, raz `timedelta(31800s)` → niespójny typ |
| I `numer telefonu` | `="601290441"` (formuła-tekst), `32 235 27 15` → dwa formaty |
| X `Zajecia cykliczne (godzina)` | zakres w jednej komórce |
| V `dzień tygodnia` | w v1 pliku były wpisy typu `Poniedziałek i piątek` |

### Skala realnych danych

`BAZA` 980 wierszy szkół (167 przypisanych) · `Sacawa` 42 · `Olszewska` 25 ·
`Zbiorczy` 70 · `Szkoły z DT` 46 · `Niewykorzystane rekordy` 0 wypełnionych.
**Dane zaczynają się w wierszu 4** (handlowcy, BAZA) lub 2 (widoki).

---

## B. Wymagania klienta (`.docx`) — 4 fazy cyklu życia leada

1. **Przypisanie** — koordynator wybiera handlowca z listy w bazie głównej;
   jedna baza na region; filtrowanie po mieście i handlowcu.
2. **Transfer** — lead znika z bazy głównej i trafia do arkusza handlowca;
   filtrowanie po mieście i statusach.
3. **Sukces** — status `DT umówione` → dane lecą do: arkusza Julki, kalendarza DT
   (**„czasem 2-3 eventy dziennie u jednego trenera"**), kalendarza cyklicznych.
4. **Brak efektu** — koordynator odbiera dostęp → `niewykorzystane rekordy` → inny handlowiec.

Dodatkowo:
- **Moduł RSPO**: wgranie czystej bazy szkół, filtrowanie po miastach regionu,
  przypisanie + „ostateczny termin", kontrola aktywności przed terminem
  (*„jeśli się to da zrobić — je­śli nie będę to robiła ręcznie, tu akurat to najmniej ważne"*).
- **Kalendarze miesięczne rozpoznawane z daty, bez sztywnego kodowania.**
- **Plansza trenerów typu `STARTY CZERWIEC`** — każdy trener swoim kolorem,
  „widzimy całą firmę, kto gdzie jest" → zastępstwa, szybka lokalizacja trenera.
  („to już jest Meksyk")
- **Google Calendar per trener** — „to jest przyszłość, chyba że nie zajmie dużo czasu".
- Listy rozwijane identyczne na każdym arkuszu.

---

## C. Notatki ze spotkania 24.07 (SILESIA 3D, kontakt: ZUZA)

**DT = dzień technologiczny** (potwierdzone przez klienta).

1. Filtrowanie **po Handlu** → BAZA SZKÓŁ ŚLĄSKIE
2. **Arkusze po statusie** (np. „DT w trakcie umawiania" — status, którego jeszcze NIE ma
   w liście; dziś jest tylko `02. Próba kontaktu (czekam na termin)`)
3. **Pobrane szkoły z RSPO**: szkoły + **przedszkola** + **instytucje kultury**
   → typ placówki jako pole (dziś nie istnieje)
4. Bazy szkół — Śląskie:
   - **wybrane szkoły na tydzień „do góry"** → przypinanie / plan tygodnia
   - **STATUS — minimum na tydzień** → cel tygodniowy per handlowiec + licznik
5. Kalendarz DT: **Olszewska — DT umówione ⟹ przenosi się do BAZY SZKÓŁ**
6. **żeby nie mógł trener 2× mieć aktywności** → walidacja kolizji trenera
7. Kalendarz ma pokazywać: **NAZWA szkoły · MIEJSCOWOŚĆ · ILOŚĆ KLAS · NR SALI**
   (to jest podzbiór ich „karty" z `Zbiorczy!AG` — potwierdza kierunek)

---

## D. Co już jest w `leady_app` (v1/v2) — punkt startowy

`app.py` (249) · `db.py` (99) · `calendar_view.py` (159) · `importer.py` (145) ·
`exporter.py` (80) · `parsers.py` (103) · `seed.py` (68) + 5 szablonów + `static/`.

Jest: SQLite bez ORM, `LEAD_FIELDS` jako pojedyncze źródło definicji kolumn,
słowniki z wymuszaniem wartości przy PATCH, kalendarz `build_grid`/`build_weeks`,
`find_collisions`, pulpit z overdue + kolizjami, import/eksport XLSX, Docker.

Brakuje (zidentyfikowane luki): brak modelu **eventów** (kalendarz liczony z leadów →
1 lead = max 1 DT), brak typu placówki, brak RSPO/klucza, brak ról i logowania,
brak `niewykorzystane rekordy` jako przepływu, brak planszy STARTY, brak celu
tygodniowego, brak eksportu **wyfiltrowanego** (jawne życzenie z `prompt_v2`),
brak historii aktywności (potrzebnej do kontroli deadline).

---

## E. Rozstrzygnięcia przyjęte dla v3 (o ile klient nie powie inaczej)

1. **Klucz główny**: własne `id` + opcjonalny `nr RSPO` (unikalny, gdy jest).
   Nie zakładamy, że RSPO zawsze jest — w `BAZA` dziś go nie ma.
2. **Jedno źródło prawdy = tabela `leady`**, a osobno **tabela `eventy`**
   (1 wiersz = 1 spotkanie). Kalendarze, plansza i kolizje to widoki z `eventy`.
   To rozwiązuje bug 2–3 eventów bez żadnej sztuczki.
3. **Nic nie jest usuwane ani kopiowane** — przepływ to zmiana `handlowiec` + `status`
   + filtr widoku. „Znika z bazy głównej" = nie pokazuje się na liście do rozdania.
4. **Słownik centralny** — jedna tabela, wymuszanie przy zapisie, koniec
   z `02. Olaszewska`.
5. **Prefiksy `01. `, `02. ` zostają** w wartościach (klient ich używa do sortowania),
   ale sortowanie i wyświetlanie ma je rozumieć, nie traktować jako część nazwy.
6. **Miesiące kalendarza generowane z daty** — zakładka/miesiąc nie jest nigdzie
   zapisywana na sztywno.
