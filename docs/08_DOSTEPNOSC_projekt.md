# Projekt: ekran „Dostępność trenerów" (v2)

Data: 03.08.2026 · Status: **zaimplementowane w tej wersji (leady_app_v3-v2)**

## Skąd się bierze ta funkcja

W zeszłorocznym pliku (`DT 2025-2026 NOWY PIĘKNY PLIK.xlsx`) dostępność trenera
to była **połowa treści kalendarza DT i jedyne wejście do umawiania**:

- `Kalendarz DT LG!B4 = 'DOSTĘPNA 8 - 12:00'`, `D8 = 'DOSTĘPNA CAŁY DZIEŃ'`,
  `F4 = 'XXX'` (tło w kolorze trenera = niedostępny),
- zakładka `DOSTĘPNOŚĆ NA DT - TRENERZY` (258 wierszy) — ta sama siatka,
  już prawie wyłącznie dostępnościowa. Sami doszli do tego, że dostępność
  trzeba oddzielić od rezerwacji,
- w bieżącym `PH Nowy` ta funkcja **zniknęła całkiem** — regres, przez który
  handlowiec nie wie, komu może wstawić DT.

Przepływ pracy, który odtwarzamy: **trener/koordynator wpisuje okna dostępności
→ handlowiec patrzy, kto i kiedy ma wolne → umawia DT w wolnym oknie**.

## Semantyka komórki (trener × dzień)

W arkuszu jedna komórka mieszała trzy rzeczy. Tu każdy stan jest jawny:

| Stan | W arkuszu było | W systemie |
|---|---|---|
| **brak wpisu** | pusta komórka | „?" — dostępność **nieznana** (to nie to samo co niedostępny!) |
| **niedostępny** | `XXX` na kolorze trenera | czerwona komórka „niedostępny" |
| **okno godzin** | `DOSTĘPNA 8 - 12:00` | zielona komórka z oknem `08:00–12:00` |
| **cały dzień** | `DOSTĘPNA CAŁY DZIEŃ` | zielona komórka „cały dzień" (przyjmujemy 8:00–18:00) |

Tabela istniała w bazie od v3: `dostepnosc(trener, data, godz_od, godz_do,
niedostepny, uwagi)`, `UNIQUE(trener, data)` — jeden wpis na trenera na dzień.

## Rzecz, której arkusz nie umiał: WOLNE OKNA

Komórka nie pokazuje tylko deklaracji — pokazuje **dostępność minus to, co już
zaplanowane** (DT + rozwinięte cykle z kalendarza, z wyjątkami i zastępstwami):

```
deklaracja:  08:00–16:00
zajęte:      09:40–11:55 (DT SP 16), 14:00–15:00 (cykl SP 34)
wolne okna:  08:00–09:40 · 11:55–14:00 · 15:00–16:00
```

Okna krótsze niż **45 min** pomijamy (nie da się w nich zrobić ani DT, ani cyklu).
To jest odpowiedź na realny sposób pracy: w `DOSTĘPNOŚĆ NA DT` trenerki ręcznie
dopisywały `(mam cykliczne 14:00 - 15:00 Sp. 34 Chorzów)` — tu system dopisuje
to sam, z kalendarza, więc nie może się rozjechać.

## Ekran `/dostepnosc`

- **Macierz trener × dzień, bloki tygodniowe pod sobą** — dokładnie ten sam układ
  co Kalendarz DT (macierz), więc zero nauki. Pon–pt, opcja weekendu, wybór miesiąca.
- Wiersz trenera: kropka w jego kolorze + licznik dni z deklaracją.
- Komórka: stan (kolor tła) + okno + zajęte bloki + wyliczone wolne okna + uwagi.
- **Klik w komórkę = edycja** (mini-formularz w komórce): od–do / cały dzień /
  niedostępny / wyczyść + uwagi. Zapis bez przeładowania, jak edycja inline leadów.
- **Wypełnianie zakresu** (panel nad siatką): trener + od–do daty + dni tygodnia
  + godziny albo „niedostępny" → jeden POST wypełnia cały okres. To odpowiada
  temu, jak realnie wpisywali: całe tygodnie na raz.
  Wypełnianie zakresu **nie nadpisuje** istniejących wpisów (chroni ręczne korekty);
  edycja pojedynczej komórki nadpisuje zawsze.

## Ostrzeżenie przy umawianiu

Przy dodaniu/zmianie spotkania (API eventów) sprawdzamy dostępność trenera:

- trener oznaczony **niedostępny** w tym dniu → ostrzeżenie,
- spotkanie **poza zadeklarowanym oknem** → ostrzeżenie,
- brak deklaracji → cisza (nieznana ≠ zabroniona).

Tak samo jak przy kolizjach: **ostrzegamy, nigdy nie blokujemy** — decyzja
zawsze należy do człowieka (ustalenie z analizy, do potwierdzenia z klientką).

## API

| Metoda i ścieżka | Co robi |
|---|---|
| `POST /api/dostepnosc` | upsert jednej komórki `{trener, data, godz_od, godz_do, niedostepny, uwagi}` |
| `DELETE /api/dostepnosc` | czyści komórkę `{trener, data}` |
| `POST /api/dostepnosc/zakres` | wypełnia zakres `{trener, od, do, dni:[0..6], ...}` — bez nadpisywania |
| `POST /api/dostepnosc/demo` | przykładowe deklaracje na wybrany miesiąc (do pokazania działania) |

Trener zawsze walidowany słownikiem — literówka nie przejdzie, jak wszędzie.

## Poza zakresem tej iteracji (świadomie)

- Dostępność **cykliczna** („każdy wtorek 8–12") — na razie wpis per dzień
  + wypełnianie zakresu; reguła tygodniowa to naturalny krok 2, jeśli klientka potwierdzi.
- Samoobsługa trenera (osobny widok „moja dostępność" z logowaniem) — wymaga ról.
- Rejon trenera przy sugerowaniu (pytanie 17 z analizy zeszłorocznego pliku).
