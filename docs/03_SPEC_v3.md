# SPEC v3 — `leady_app_v3` (SILESIA 3D)

Wersja 1.1 · 30.07.2026 · dokument implementacyjny
Źródła: `01_USTALENIA_analiza.md`, `WYMAGANIA_klient_docx.md`,
`notatki-spotkanie-2026-07-24-silesia-3d.md`, `00_kontekst_v1.md`, `FAZA2_PH_Nowy.md`,
**`design/05_DESIGN_handoff.md`**, **`design/06_STARTY_aliasy_trenerow.md`**,
**`design/starty_normalized.json`** (286 realnych wpisów STARTY CZERWIEC), kod `leady_app` (v1/v2).

**Zmiany w 1.1 względem 1.0** (po dostarczeniu design handoffu i danych STARTY):
osoby wyjęte ze słowników tekstowych do tabeli `osoby` + aliasy (dowód: 50 zapisów → 29 osób) ·
event dostał `grupa`, `sprzet`, `kod_tinkercad`, `link_tinkercad` · role przy eventzie
(`prowadzący`, `współprowadzący`, `zastępstwo`, `drukarz`) jako tabela łącząca ·
kalendarz zunifikowany do trzech widoków `macierz | agenda | starty` zgodnie z handoffem ·
dodany trzeci importer (STARTY) i trzeci system nazewnictwa placówek ·
dodany rozdz. 5 „warstwa wizualna" · odwrócona decyzja z ryzyka R19.

**Charakter dokumentu:** spec prototypu do pokazania klientowi („czy o to chodziło?"),
działającego na ich realnych danych. Nie system produkcyjny. Każda decyzja o odpuszczeniu
czegoś jest tu jawna i uzasadniona — żeby nikt jej później nie „naprawiał".

---

## 0. Cel prototypu — kryterium sukcesu

Prototyp jest udany, jeśli klientka po 15 minutach klikania powie „tak, o to chodziło",
bo zobaczy rozwiązane **cztery swoje bóle**:

| # | Ból (jej słowami) | Co to naprawia w v3 | Gdzie to widać |
|---|---|---|---|
| B1 | „listy rozwijane muszą być takie same na każdym arkuszu" | `osoby` + `osoby_alias` + `slowniki`, wymuszanie przy zapisie, autonaprawa przy imporcie | Osoby, Słowniki, Raport importu, każdy select |
| B2 | „jeśli trener ma 2–3 spotkania w dniu, widzę tylko jedno" | `eventy` (1 wiersz = 1 spotkanie); komórka kalendarza to LISTA, nie `XLOOKUP` | Kalendarz → Macierz ⭐ |
| B3 | „wiersz kopiuje się do trzech miejsc" | jedno źródło + widoki; poprawka w jednym miejscu zmienia wszystkie ekrany | Zbiorczy + Kalendarz + widok handlowca |
| B4 | „niewykorzystane rekordy — chcę je przydzielić komu innemu" | `leady.aktywny` + pula zwrotna + masowe przypisanie | Niewykorzystane rekordy |

**Piąty ból, którego klientka nie nazwała, ale który jest w jej danych najgłębszy:**
w zakładce STARTY CZERWIEC jest **50 różnych zapisów nazwy trenera na 29 osób**
(`ZUZA` / `ZUZANNA` / `ZUZANNA OLSZEWSKA` / `ZUZIA OLSZEWSKA` = jedna osoba;
`NATALIA STARZOMSKA` / `NATALIA STARZOSMKA`; `PATRYK PALUS` / `PATRYK PALSU`;
`WERONIKA MAŁOLEPSZA + kornelia gawron (1)` = dwie osoby w jednym polu; `:` jako trener).
Skutek: **dziś nie da się policzyć, ile kto ma zajęć, ani wyfiltrować grafiku jednej osoby.**
To jest B1 w najostrzejszej postaci i osobny scenariusz demo (S12).

Wszystko, co nie służy B1–B5, jest kandydatem do fazy 2 (rozdz. 6).

**Twarda zasada demo:** nic nie jest usuwane i nic nie jest kopiowane. „Znika z bazy głównej"
= przestaje spełniać warunek filtra. Trzeba to powiedzieć wprost, zanim klientka zacznie
szukać zniknięć.

---

## 1. Model danych

### 1.1. Rozstrzygnięcie kluczowego napięcia

Klient myśli **„jeden wiersz = jedna szkoła"**. Realnie trzeba **„jeden wiersz = jedno spotkanie"**.
Oba są prawdziwe — na różnych ekranach. Dlatego:

> **Reguła UI (nienegocjowalna):** ekrany listowe (BAZA, widok handlowca, Zbiorczy,
> Niewykorzystane) pokazują **zawsze jeden wiersz na placówkę**, z odznaką liczby spotkań
> (`DT ×2`, `cykl ×34`). Rozbicie na spotkania widać **tylko** w kalendarzach i w karcie leada.

Gdyby BAZA pokazała 3 wiersze dla jednej szkoły, klientka powie „zepsuliście mi plik" —
i będzie miała rację, bo to jej podstawowa jednostka myślenia. Model danych jest znormalizowany,
prezentacja jest „arkuszowa".

### 1.2. Drugie napięcie — klient sam sobie zaprzeczył

W `.docx`: *„jeśli trener ma 2 lub więcej spotkań w danym dniu to nie widzę 2 wpisów,
a powinnam"*. W notatkach ze spotkania: *„żeby nie mógł trener 2× mieć aktywności"*.
Rozstrzygnięcie:

- **dwa spotkania tego samego dnia = NORMA** → muszą być widoczne oba (to bug do naprawy).
  Dane to potwierdzają: Kinga Król ma 22 zajęcia w 10 dni roboczych, czyli średnio 2,2 dziennie.
- **dwa spotkania o nakładających się godzinach = KOLIZJA** → ostrzeżenie, ale zapis dozwolony.

Zapis dozwolony, nie blokowany — bo w prototypie blokada, której klientka nie rozumie,
to droga do „ta apka mi nie pozwala pracować". Ostrzeżenie + czerwona (magenta) ramka
+ licznik na Pulpicie sprzedaje tę samą wartość bez ryzyka.

### 1.3. Ile tabel — decyzja i cena

Rdzeń: **`placowki` / `leady` / `eventy`**, plus **`osoby` + `osoby_alias` + `event_osoby`**,
plus `cykle`, `slowniki` (+ aliasy), tabele pomocnicze.

Rozważone warianty rdzenia:

| Wariant | Za | Przeciw | Werdykt |
|---|---|---|---|
| **1 tabela** (jak v1: `leady` = wszystko) | najprostszy, działa dziś | 1 lead = max 1 DT → **bug B2 nie do naprawienia**; reimport RSPO nadpisuje pracę handlowca | odrzucony |
| **2 tabele** (`leady` = szkoła+przypisanie, `eventy`) | naprawia B2, mało joinów | reimport RSPO musi wiedzieć, których kolumn nie ruszać; zwrot leada gubi historię; 980 szkół z RSPO i proces sprzedaży w jednym worku | odrzucony, ale to była realna alternatywa |
| **3 tabele** (`placowki` / `leady` / `eventy` + `cykle`) | reimport RSPO idempotentny; dedup „MSP 2" vs oficjalna nazwa RSPO jest jawny; zwrot do puli = zamknięcie leada i otwarcie nowego → historia gratis | każdy widok listowy to JOIN; edycja inline musi wiedzieć, do której tabeli trafia pole | **wybrany** |

Rozstrzygający argument: w ich danych **ta sama szkoła ma TRZY różne nazewnictwa**:

| Źródło | Zapis tej samej szkoły |
|---|---|
| `BAZA` (z RSPO) | `SZKOŁA PODSTAWOWA NR 11 IM. … W BĘDZINIE` + `15. Będzin powiat` |
| arkusze handlowców (`PH Nowy`) | `SP 11` + `15. Będzin` |
| `STARTY CZERWIEC` | `SP.11 BĘDZIN` (miasto, kod i grupa w jednej komórce) |

Bez osobnej tabeli placówek dedup jest niemożliwy do zrobienia tak, żeby dał się obejrzeć
i poprawić.

**Cena, którą płacimy (świadomie):**
1. Każda lista to JOIN → neutralizujemy widokiem SQL `v_leady`, który spłaszcza wszystko
   do „jednego wiersza jak w Excelu". Cały kod czytający używa widoków, nie joinów ręcznie.
2. Edycja inline musi routować pole do właściwej tabeli → jedna funkcja `repo.zapisz_pole()`
   + jedna mapa w `fields.py`. Koszt: ~30 linii, raz.
3. Invariant „jedna placówka = jeden aktywny lead" trzeba wymusić, bo inaczej model kłamie
   → `CREATE UNIQUE INDEX … WHERE aktywny=1`.

### 1.4. Osoby: jedna tabela z aliasami, nie dwie listy tekstowe

**To jest odwrócenie wcześniejszej decyzji** (w wersji 1.0 spec mówił: „dwa osobne słowniki
handlowiec/trener, zero aliasowania między rodzajami"). Nowe dane wymuszają zmianę i warto
wiedzieć dlaczego.

Dowody z realnych danych:

1. **Ta sama osoba występuje w 3–4 rolach pod różnymi zapisami.**
   Dominika Sacawa: handlowiec `01. Sacawa` (PH), trener `20. Sacawa` (PH),
   trener `DOMINIKA SACAWA` (STARTY), drukarz `DOMINIKA` (STARTY). Cztery teksty, jedna osoba.
   Przy modelu „słownik per rola" trzeba by pilnować spójności czterech list — czyli dokładnie
   tego, co dziś nie działa.
2. **50 zapisów → 29 osób** w jednej zakładce (`06_STARTY_aliasy_trenerow.md`).
   Cztery zapisy jednej Zuzanny. Literówki w nazwiskach (`STARZOSMKA`, `PALSU`, `WESOŁOWKSA`).
   Formy skrócone (`MATI`, `ZUZIA`, `JULA`, `kinga`, `MAJKA`).
3. **Dwa równoległe systemy nazewnictwa:** `PH Nowy` = `prefiks + nazwisko` (`04. Zemela`),
   STARTY = `IMIĘ NAZWISKO` (`PAULINA ZEMELA`). Bez wspólnego identyfikatora te dwa zbiory
   danych nigdy się nie spotkają, a to znaczy: kalendarz DT i plansza STARTY nigdy nie pokażą
   spójnego obrazu jednego trenera.
4. **Pole trenera zawiera czasem dwie osoby** (`WERONIKA MAŁOLEPSZA + kornelia gawron (1)`).
5. **`zastepstwo` i `drukarz` to też osoby** — dwie kolejne role.

Decyzja:

```
osoby        (id, nazwa kanoniczna „Paulina Zemela", etykieta_ph „04. Zemela",
              role: handlowiec/trener/koordynator, kolor, sort_order, aktywny)
osoby_alias  (alias_norm → osoba_id)      ← 50 aliasów z STARTY + 64 z PH w SEEDZIE
event_osoby  (event_id, osoba_id, rola)   ← prowadzący | współprowadzący | zastępstwo | drukarz
```

`slowniki` **zostaje** — dla wszystkiego, co nie jest osobą (miasta, statusy, typy placówek,
dni tygodnia, sprzęt, grupa, status eventu).

Co to daje natychmiast:
- „ile zajęć ma Kinga Król" = `COUNT` (dziś: niemożliwe, bo `KINGA KRÓL` i `kinga` to dwa różne teksty),
- kolizje liczone **per osoba**, nie per tekst,
- dropdown „Handlowiec" pokazuje osoby z `rola_handlowiec=1`, „Trener" z `rola_trener=1` —
  jedna prawda, dwa filtry,
- zastępstwo i drukarz bez dodawania kolumn (to tylko inna `rola`).

**Reguła bezpieczeństwa przy scalaniu (ważna):** alias **jednotokenowy** (samo nazwisko,
np. `norm('03. Małolepsza') = 'malolepsza'`) **nigdy nie scala się automatycznie** z osobą
o pełnym imieniu i nazwisku — idzie do raportu jako DECYZJA. Powód: `03. Małolepsza`
(handlowiec) i `WERONIKA MAŁOLEPSZA` (trener) mogą być tą samą osobą albo dwiema.
Automatyczne scalanie po nazwisku zrobiłoby z nich jeden byt i pomieszało przypisania
z grafikiem. Aliasy jednotokenowe z `PH Nowy` **wchodzą do seeda z ręki** (mamy je wypisane),
a nie zgadywane przy imporcie.

**Kolumna `etykieta_ph` zostaje**, bo klientka rozpoznaje swoje listy po `04. Zemela`.
Na ekranach pokazujemy `nazwa` (pełne imię i nazwisko), w podpowiedzi (tooltip)
i w eksporcie XLSX dodatkowo `etykieta_ph` — żeby wyeksportowany plik dał się porównać
z jej starym arkuszem.

### 1.5. Zajęcia cykliczne: reguła + materializacja (wariant hybrydowy)

Warianty:

- **(a) tylko reguła, rozwijana przy renderowaniu** — zero rekordów do rozjechania, ale:
  nie da się odwołać jednych zajęć ani wpisać zastępstwa na jednym terminie, a kolizje
  DT × cykliczne trzeba liczyć osobnym kodem.
- **(b) tylko wygenerowane eventy** — jednolity kod, ale edycja serii to 34 wiersze,
  a klient nie wpisuje „terminów", wpisuje „wtorek 12:25, grupa 1".
- **(c) reguła (`cykle`) + wygenerowane `eventy` z `cykl_id`** ← **wybrane**

Dlaczego (c): klientka wpisuje dokładnie to, co dziś ma w kolumnach V/W/X/Y
(dzień tygodnia + godzina + sala + trener) — czyli regułę. Ale **kalendarz, plansza STARTY
i detekcja kolizji mają wtedy JEDNO źródło (`eventy`) i JEDEN kod**. To największa oszczędność
w projekcie. Dane STARTY dowodzą, że (a) by nie wystarczyło: 18 z 286 wpisów ma wypełnione
`zastepstwo`, czyli **co szesnaste zajęcia odbiegają od reguły**. Bez zmaterializowanych
terminów nie ma gdzie zapisać zastępstwa.

Materializacja jest jawna: zapis reguły regeneruje przyszłe terminy `wygenerowany=1
AND zmodyfikowany_recznie=0`; terminy ruszone ręcznie i terminy z przeszłości zostają nietknięte.

Zbitka `„Poniedziałek i piątek"` → **dwa wiersze w `cykle`** dla jednego leada.
Grupa 1 i grupa 2 tej samej szkoły (`SP. Strzyżowice (gr.1)` 12:25–13:25 i `(gr2)` 13:35–14:35)
→ **też dwa wiersze w `cykle`**, różniące się polem `grupa` i godzinami. To jest jedyny sposób,
żeby nie wyglądały jak duplikat.

### 1.6. Historia aktywności — nie przeinwestować

Klientka sama: *„jeśli się to da zrobić — jeśli nie, będę to robiła ręcznie,
tu akurat to najmniej ważne"*. Więc:

- **`leady.ostatnia_aktywnosc`** (data) — to, czego potrzebuje kontrola deadline'u. Jedno pole,
  jedno tanie zapytanie na Pulpicie.
- **`log_aktywnosci`** — cienka tabela append-only, zapisywana **wyłącznie** przez
  `activity.dotknij()` (ta sama funkcja ustawia pole powyżej). Bez UI poza panelem w karcie leada.

Dlaczego jednak log: koordynatorka na demo zapyta „a skąd wiem, że on tego nie ruszył?".
Odpowiedź „bo tu jest lista: 14.09 zmienił status, potem nic" kosztuje 15 linii i wygrywa
rozmowę. To jedyne miejsce, gdzie świadomie robimy pół kroku więcej niż klient prosił.

**Czego NIE robimy:** pełnego audytu z cofaniem zmian, wersjonowania, diffów.

### 1.7. Słowniki, prefiksy i aliasy (rzeczy niebędące osobami)

**Jedna tabela `slowniki`** (`rodzaj`, `wartosc`, `sort_order`, `kolor`, `aktywny`) +
**`slowniki_alias`** (`rodzaj`, `alias_norm` → `wartosc`).

Prefiksy `01. `, `02. ` **zostają w wartości** — klientka używa ich do sortowania i rozpoznaje
po nich swoje listy. Ale:

- sortowanie idzie po **`sort_order`** (INTEGER), nie po tekście prefiksu,
- w ciasnych komórkach kalendarza wyświetlamy `etykieta` (wartość bez prefiksu),
- `norm(v)` (usuń prefiks → lower → usuń polskie znaki → zbij spacje) jest kluczem dopasowania.

**Dowód, że to właściwa decyzja:** z notatek klientka chce nowy status „DT w trakcie umawiania",
który logicznie należy **przed** `03. DT umówione`. Gdyby prefiks był kluczem sortowania,
trzeba by przenumerować listę i unieważnić dane historyczne. U nas: `05. DT w trakcie umawiania`
z `sort_order=25` — wyświetla się w dobrym miejscu, stary prefiks zostaje, dane historyczne
dalej walidują się.

**Usuwanie wartości słownikowych jest zabronione** — tylko `aktywny=0`. (W v1
`DELETE FROM slowniki` mógł osierocić dane — to poprawiamy.)

**Kolory trenerów:** 4 zdefiniowane u nich (`01. Małolepsza` `#FF00FF`, `02. Olszewska` `#FF9900`,
`03. Majewska` `#00FF00`, `04. Zemela` `#B7E1CD`) idą do seeda — ale **przepuszczone przez
paletę Broadsheet** (patrz rozdz. 5.3), bo czysta magenta `#FF00FF` na papierowym tle wygląda
jak błąd. Pozostałe 25 osób: kolor deterministyczny z hasza nazwy (stabilny między restartami),
edytowalny na ekranie Osoby.

### 1.8. Migracja — trzy importery, jeden raport

Zasada: **importer nigdy nie przerywa pracy na błędnym wierszu.** Koeruje, aliasuje, flaguje
i produkuje **Raport importu** (`importy` + `importy_pozycje`) jako osobny ekran.
Raport jest jednocześnie argumentem sprzedażowym (scenariusz S8).

Trzy źródła:

| Importer | Źródło | Co tworzy | Czego NIE tworzy |
|---|---|---|---|
| `import_ph.py` | `PH Nowy` — 5 arkuszy handlowców + `BAZA` | placówki, leady, eventy DT (z `Data DT` + `Prowadzący DT`), reguły cykli (z V/W/X/Y) | nie czyta `Zbiorczy` (patrz R1) |
| `import_rspo.py` | plik RSPO (xlsx/csv) przefiltrowany przez koordynatorkę | placówki (upsert regułą „wypełniaj puste") | leadów |
| `import_starty.py` | `STARTY CZERWIEC` (xlsx lub gotowy `starty_normalized.json`) | eventy cykliczne + role (prowadzący/zastępstwo/drukarz) + `grupa`, `sprzet`, `kod_tinkercad`, `link_tinkercad`; dopina do istniejących placówek | nowych leadów, jeśli placówka ma już aktywny lead |

Konkretne rozjazdy i ich obsługa:

| Problem w danych | Obsługa |
|---|---|
| `02. Olaszewska` (`Sacawa!A20:A200`, `Olszewska!A29:A340`) | odległość Levenshteina 1 do istniejącego aliasu → alias **automatyczny**, INFO w raporcie |
| `11. Białass (Pszczyna)`, `23. Trenner 5`, `22. Trene 3`, `NATALIA STARZOSMKA`, `PATRYK PALSU`, `ANIEL CEBULA`, `JULA WESOŁOWKSA` | jak wyżej (odległość ≤ 2, **ta sama liczba tokenów**) → alias automatyczny, INFO |
| `19. Chorzow` vs `16. Chorzów`; `noemi białas` vs `NOEMI BIAŁAS` | `norm()` zdejmuje diakrytyki i wielkość liter → dopasowanie dokładne |
| `ZUZA`, `ZUZANNA`, `ZUZIA OLSZEWSKA`, `MATI PUSTELNIK`, `kinga`, `MAJKA` | **z mapy w `06_STARTY_aliasy_trenerow.md`, wpisanej do seeda 1:1** — nie zgadywane przez algorytm |
| `WERONIKA MAŁOLEPSZA + kornelia gawron (1)`, `MATEUSZ PUSTELNIK + SARA` | rozbicie na `+` → **dwa wpisy w `event_osoby`**: `prowadzacy` + `wspolprowadzacy` |
| `:` jako trener (4 wpisy), `?? MAJA`, `?? NATALIA M` jako drukarz (38 wpisów) | event powstaje **bez** tej roli, pozycja `DECYZJA` w raporcie |
| trzy listy miejscowości (LISTA 5 / 11 / 12) | kanoniczna = **LISTA 5 z `BAZA`**. `09. Pszczyna` → alias `09. Pszczyna powiat`, `15. Będzin` → `15. Będzin powiat` (**jawne aliasy w seedzie** — `norm()` ich nie połączy). `20. Ornontowice`, `21. Wyry`, `22. Gostyń`, `21. Strzyzowice`, `08. Katowice Południe` → nowe wartości z `do_przegladu=1` |
| dublet w jednej liście: `14. Dąbrowa Górnicza` i `17. Dąbrowa Górnicza` | kanoniczna `14.`, `17.` → alias, INFO |
| dwie listy trenerów w PH: 40-poz. (kol. Y) i 24-poz. (kol. O) | oba mapowane na `osoby` przez `osoby_alias`; puste pozycje `31.`…`40.` i placeholdery `20. Trener 1`…`24. Trener 5` → **pomijane** (nie są osobami) |
| `Bitner` bez prefiksu w handlowcach, `18. Bitner` w trenerach, `AGATA BITTNER` w STARTY (dwa „t"!) | jedna osoba `Agata Bittner`, trzy aliasy; `rola_handlowiec` i `rola_trener` = 1; `do_przegladu=1` + pytanie do klienta |
| `Sacawa` ma `max_row = 50500` | `read_only=True`, stop po 200 pustych wierszach z rzędu |
| dane od wiersza 4 (handlowcy, BAZA) albo 2 (widoki) | **autodetekcja** pierwszego wiersza danych; bez zakładania numeru |
| `="601290441"` (telefon jako formuła-tekst) | zdejmij `="` i `"` |
| `Godzina DT` raz `time(8,55)`, raz `0.3715277…`, raz `timedelta(31800s)` | `parsers.to_hhmm()` obsługuje wszystkie trzy + serial |
| `death line` = `46206.0` (serial Excela) | `parse_date()` z epoką `1899-12-30` |
| `10 klas`, `około 240`, `330` | `parse_int_leading()` (jest w v1) |
| `12:25–13:25` z **półpauzą** (nie minusem) | `parse_time_range()` musi znać `-`, `–`, `—` |
| `AI4 = 30.12.1899\|\|04. Zemela` (pusta data DT) | żaden event nie powstaje, lead zostaje |
| STARTY nie ma dat — tylko `tydzien` + `dzien_nr` (1–5, 8–12) | import STARTY **wymaga parametru miesiąc/rok** w formularzu; `dzien_nr` to dzień miesiąca |
| `"Piekary Śląskie SP 13, gr 2"`, `"SP. Strzyżowice (gr.1)"`, `"SP. 30 Dabrowa Górnicza (gr.2)"`, `"SP.11 BĘDZIN"` — miasto + kod + grupa w jednej komórce, w trzech różnych kolejnościach | algorytm: (1) wytnij grupę regexem `gr\.?\s*(\d)` / `\((\d)\)`, (2) **znajdź w tekście dowolną znaną miejscowość ze słownika po `norm()`** i wytnij ją, (3) resztę znormalizuj jako `kod` (`SP.11` → `SP 11`). Miejscowość rozpoznawana przez słownik, nie przez pozycję w tekście — to jedyna metoda odporna na trzy kolejności |
| `Zbiorczy` = same formuły `VSTACK/FILTER/QUERY` | **nie importujemy** (R1) |
| `BAZA` nazwy oficjalne UPPER vs `MSP 2` u handlowców vs `SP.11 BĘDZIN` w STARTY | dopasowanie placówki 4-stopniowe + `placowki_alias` + ekran scalania |
| brak `typ placówki`, brak `nr RSPO` w `BAZA` | `typ` domyślnie `01. Szkoła podstawowa` z `do_przegladu=1`; `rspo` NULL |

**Dopasowanie placówki (dedup), kolejność prób:**
1. `rspo` — dokładnie (gdy jest w obu),
2. `placowki_alias.alias_norm` — dokładnie,
3. `norm(kod)` **w tej samej miejscowości** (`SP 11` + `Będzin`),
4. podobieństwo `nazwa` ≥ 0.85 (`difflib.SequenceMatcher`) w tej samej miejscowości
   → **propozycja scalenia w raporcie, nie automat**,
5. brak trafienia → nowa placówka z `zrodlo` i `do_przegladu=1`.

Kroki 1–3 automatyczne, krok 4 wymaga kliknięcia. Bez kroku 4 demo pokaże ~1 100 rekordów
z widocznymi duplikatami tej samej szkoły — to zabija wiarygodność szybciej niż każdy inny błąd.

### 1.9. DDL (SQLite, gotowy do wklejenia jako `schema.sql`)

```sql
-- =====================================================================
-- leady_app_v3 — schemat bazy. Jedno źródło prawdy, widoki generowane.
-- Uruchamiane przez db.init_db(); idempotentne.
-- =====================================================================
PRAGMA journal_mode = WAL;      -- kilku edytujących naraz, krótkie transakcje
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- OSOBY — jedna tabela ludzi. Handlowiec, trener, drukarz i osoba
-- wchodząca na zastępstwo to TE SAME byty w różnych rolach.
-- Dowód konieczności: 50 zapisów nazwy trenera na 29 osób w STARTY.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS osoby (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  nazwa            TEXT    NOT NULL UNIQUE,   -- kanoniczna: 'Paulina Zemela'
  imie             TEXT,
  nazwisko         TEXT,
  etykieta_ph      TEXT,                      -- '04. Zemela' — jak w PH Nowy (rozpoznawalność)
  rola_handlowiec  INTEGER NOT NULL DEFAULT 0,
  rola_trener      INTEGER NOT NULL DEFAULT 0,
  rola_koordynator INTEGER NOT NULL DEFAULT 0,
  kolor            TEXT,                      -- #RRGGBB, paleta Broadsheet
  sort_order       INTEGER NOT NULL DEFAULT 0,
  aktywny          INTEGER NOT NULL DEFAULT 1,
  do_przegladu     INTEGER NOT NULL DEFAULT 0,
  uwagi            TEXT
);
CREATE INDEX IF NOT EXISTS ix_osoby_role ON osoby(rola_trener, rola_handlowiec, aktywny);

-- Aliasy globalne (jedna przestrzeń nazw): 'zuza', 'zuzia olszewska',
-- '02. olszewska', 'zuzanna olszewska' → ta sama osoba.
CREATE TABLE IF NOT EXISTS osoby_alias (
  alias_norm TEXT PRIMARY KEY,                -- norm() z wariantu z pliku
  osoba_id   INTEGER NOT NULL REFERENCES osoby(id) ON DELETE CASCADE,
  zrodlo     TEXT                             -- 'seed' | 'PH' | 'STARTY' | 'reczny'
);
CREATE INDEX IF NOT EXISTS ix_osoby_alias_os ON osoby_alias(osoba_id);

-- ---------------------------------------------------------------------
-- SŁOWNIKI — wszystko, co NIE jest osobą.
-- rodzaj ∈ miasto | typ_placowki | status_szkoly | status_realizacji |
--          dt | tak_nie | mail_propozycja | dzien_tyg | status_eventu |
--          sprzet | grupa
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS slowniki (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  rodzaj       TEXT    NOT NULL,
  wartosc      TEXT    NOT NULL,            -- kanoniczna, Z prefiksem '01. '
  etykieta     TEXT,                         -- bez prefiksu, do ciasnych komórek
  kolor        TEXT,
  sort_order   INTEGER NOT NULL DEFAULT 0,   -- PRAWDZIWY klucz sortowania
  aktywny      INTEGER NOT NULL DEFAULT 1,
  do_przegladu INTEGER NOT NULL DEFAULT 0,
  UNIQUE (rodzaj, wartosc)
);
CREATE INDEX IF NOT EXISTS ix_slow_rodzaj ON slowniki(rodzaj, sort_order);

CREATE TABLE IF NOT EXISTS slowniki_alias (
  rodzaj     TEXT NOT NULL,
  alias_norm TEXT NOT NULL,
  wartosc    TEXT NOT NULL,
  zrodlo     TEXT,
  PRIMARY KEY (rodzaj, alias_norm)
);

-- ---------------------------------------------------------------------
-- PLACÓWKI — obiekty świata (szkoła / przedszkole / instytucja kultury).
-- Reguła reimportu RSPO: WYPEŁNIAJ PUSTE, NIGDY NIE NADPISUJ niepustego.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS placowki (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  rspo          TEXT,
  typ           TEXT NOT NULL DEFAULT '01. Szkoła podstawowa',
  nazwa         TEXT NOT NULL,               -- oficjalna (RSPO) albo robocza
  kod           TEXT,                        -- ich kod roboczy: 'SP 11', 'MSP 2'
  miejscowosc   TEXT,
  adres         TEXT,
  kontakt       TEXT,
  telefon       TEXT,
  mail          TEXT,
  ilosc_klas    INTEGER,                     -- rozbite z '10 klas'
  ilosc_dzieci  INTEGER,                     -- rozbite z 'około 240'
  mail_rodzice  TEXT,
  klucz_norm    TEXT NOT NULL,               -- norm(miejscowosc)|norm(kod||nazwa)
  zrodlo        TEXT,                        -- 'RSPO' | 'PH' | 'STARTY' | 'RECZNIE'
  scalona_z     INTEGER REFERENCES placowki(id),
  do_przegladu  INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT DEFAULT (datetime('now')),
  updated_at    TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_plac_rspo   ON placowki(rspo) WHERE rspo IS NOT NULL;
CREATE INDEX        IF NOT EXISTS ix_plac_klucz  ON placowki(klucz_norm);
CREATE INDEX        IF NOT EXISTS ix_plac_miasto ON placowki(miejscowosc, typ);

CREATE TABLE IF NOT EXISTS placowki_alias (
  alias_norm  TEXT PRIMARY KEY,
  placowka_id INTEGER NOT NULL REFERENCES placowki(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- LEADY — przypisanie placówki handlowcowi + proces sprzedaży
-- + kolumny Julki. aktywny=0 → lead zamknięty (zwrot do puli / archiwum).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leady (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  placowka_id        INTEGER NOT NULL REFERENCES placowki(id) ON DELETE CASCADE,
  handlowiec_id      INTEGER REFERENCES osoby(id),   -- NULL = w puli, nierozdany
  status_szkoly      TEXT,
  status_realizacji  TEXT,
  deadline           TEXT,                  -- ich 'death line', ISO
  dt                 TEXT,                  -- 01. Tak / 02. Do ustalenia
  cykle              TEXT,                  -- 01. Tak / 02. Nie
  mail_propozycja    TEXT,
  mail_wynajem       TEXT,                  -- kol. Z w BAZA
  uwagi              TEXT,
  pin_tydzien        TEXT,                  -- '2026-W36' = 'szkoły na tydzień do góry'
  aktywny            INTEGER NOT NULL DEFAULT 1,
  ostatnia_aktywnosc TEXT,
  powod_zwrotu       TEXT,
  -- kolumny Julki (u nich AA..AG / Z..AF; wartości 01. Tak / 02. Nie)
  jul_dane_umowy     TEXT,
  jul_standardy      TEXT,
  jul_oswiadczenia   TEXT,
  jul_niekaralnosc   TEXT,
  jul_podanie_sala   TEXT,
  jul_umowa          TEXT,
  jul_librus         TEXT,
  created_at         TEXT DEFAULT (datetime('now')),
  updated_at         TEXT DEFAULT (datetime('now'))
);
-- INVARIANT: jedna placówka = najwyżej jeden AKTYWNY lead
CREATE UNIQUE INDEX IF NOT EXISTS ux_lead_aktywny ON leady(placowka_id) WHERE aktywny = 1;
CREATE INDEX IF NOT EXISTS ix_lead_handl ON leady(handlowiec_id, status_realizacji);
CREATE INDEX IF NOT EXISTS ix_lead_dl    ON leady(deadline)    WHERE aktywny = 1;
CREATE INDEX IF NOT EXISTS ix_lead_pin   ON leady(pin_tydzien) WHERE pin_tydzien IS NOT NULL;

-- ---------------------------------------------------------------------
-- CYKLE — REGUŁA zajęć cyklicznych (to, co klient realnie wpisuje).
-- 'Poniedziałek i piątek' = DWA wiersze. Grupa 1 i grupa 2 = DWA wiersze.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cykle (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id         INTEGER NOT NULL REFERENCES leady(id) ON DELETE CASCADE,
  dzien_tyg       TEXT    NOT NULL,          -- 'poniedziałek'…'sobota'
  godz_od         TEXT,                      -- HH:MM
  godz_do         TEXT,
  trener_id       INTEGER REFERENCES osoby(id),
  drukarz_id      INTEGER REFERENCES osoby(id),
  grupa           TEXT,                      -- '1' | '2' | '3' | '4'
  sprzet          TEXT,                      -- 'Sala komputerowa' | 'Nasze laptopy'
  sala            TEXT,
  kod_tinkercad   TEXT,
  link_tinkercad  TEXT,
  data_start      TEXT    NOT NULL,
  data_koniec     TEXT    NOT NULL,          -- WYMAGANE (ogranicza generowanie)
  co_ile_tyg      INTEGER NOT NULL DEFAULT 1,
  aktywny         INTEGER NOT NULL DEFAULT 1,
  wygenerowano_do TEXT,
  created_at      TEXT DEFAULT (datetime('now')),
  updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_cykle_lead ON cykle(lead_id, aktywny);

-- ---------------------------------------------------------------------
-- EVENTY — 1 WIERSZ = 1 SPOTKANIE. Jedyne źródło kalendarzy, planszy
-- STARTY i detekcji kolizji. TO ROZWIĄZUJE ZGŁOSZONY BUG.
-- Pola grupa/sprzet/kod_tinkercad/link_tinkercad pochodzą z realnej
-- zakładki STARTY CZERWIEC — bez nich karta zajęć jest atrapą.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eventy (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id               INTEGER NOT NULL REFERENCES leady(id) ON DELETE CASCADE,
  typ                   TEXT    NOT NULL CHECK (typ IN ('DT','CYKL','START','INNE')),
  data                  TEXT    NOT NULL,    -- ISO YYYY-MM-DD
  godz_od               TEXT,                -- HH:MM (osobno! inaczej brak kolizji)
  godz_do               TEXT,
  grupa                 TEXT,                -- '1'..'4' — gr.1 i gr.2 to DWA eventy
  sprzet                TEXT,                -- 'Sala komputerowa' | 'Nasze laptopy'
  sala                  TEXT,
  kod_tinkercad         TEXT,                -- 'BMR DKP QHW' — kod klasy dla dzieci
  link_tinkercad        TEXT,
  uwagi                 TEXT,
  status                TEXT    NOT NULL DEFAULT '01. Zaplanowany',
  cykl_id               INTEGER REFERENCES cykle(id) ON DELETE SET NULL,
  wygenerowany          INTEGER NOT NULL DEFAULT 0,  -- 1 = z reguły cyklu
  zmodyfikowany_recznie INTEGER NOT NULL DEFAULT 0,  -- 1 = regeneracja go nie tknie
  gcal_event_id         TEXT,                -- pusty w MVP; kolumna od dnia 1, patrz 6.2
  created_at            TEXT DEFAULT (datetime('now')),
  updated_at            TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_ev_lead ON eventy(lead_id, typ);
CREATE INDEX IF NOT EXISTS ix_ev_data ON eventy(data, typ);
CREATE INDEX IF NOT EXISTS ix_ev_mies ON eventy(substr(data,1,7));

-- ---------------------------------------------------------------------
-- EVENT_OSOBY — kto jest przy tym spotkaniu i w jakiej roli.
-- Zamiast czterech kolumn FK: pozwala na DWÓCH prowadzących
-- ('… + kornelia gawron (1)') i daje kolizje liczone per OSOBA.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_osoby (
  event_id INTEGER NOT NULL REFERENCES eventy(id) ON DELETE CASCADE,
  osoba_id INTEGER NOT NULL REFERENCES osoby(id),
  rola     TEXT    NOT NULL CHECK (rola IN
             ('prowadzacy','wspolprowadzacy','zastepstwo','drukarz')),
  PRIMARY KEY (event_id, osoba_id, rola)
);
CREATE INDEX IF NOT EXISTS ix_eo_osoba ON event_osoby(osoba_id, rola);
CREATE INDEX IF NOT EXISTS ix_eo_event ON event_osoby(event_id);

-- ---------------------------------------------------------------------
-- LOG AKTYWNOŚCI — cienki, append-only. Pisze TYLKO activity.dotknij().
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_aktywnosci (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id INTEGER REFERENCES leady(id) ON DELETE CASCADE,
  kiedy   TEXT NOT NULL DEFAULT (datetime('now')),
  kto     TEXT,                              -- z selektora 'kim jesteś'
  co      TEXT NOT NULL,                     -- 'edycja'|'przypisanie'|'zwrot'|'event+'…
  pole    TEXT, przed TEXT, po TEXT
);
CREATE INDEX IF NOT EXISTS ix_log_lead ON log_aktywnosci(lead_id, kiedy DESC);

-- ---------------------------------------------------------------------
-- CELE — 'STATUS minimum na tydzień' per handlowiec (notatki 24.07)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cele (
  handlowiec_id INTEGER PRIMARY KEY REFERENCES osoby(id) ON DELETE CASCADE,
  cel_tyg       INTEGER NOT NULL DEFAULT 5   -- WARTOŚĆ DO POTWIERDZENIA U KLIENTA
);

CREATE TABLE IF NOT EXISTS ustawienia (
  klucz   TEXT PRIMARY KEY,
  wartosc TEXT
);  -- rok_szkolny_od/do, domyslny_miesiac, kto_jestem_domyslnie, domyslny_widok_kalendarza

-- ---------------------------------------------------------------------
-- IMPORTY — bez raportu import 'bez czyszczenia ręcznie' nie ma sensu
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS importy (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  plik      TEXT,
  zrodlo    TEXT,                            -- 'PH' | 'RSPO' | 'STARTY'
  kiedy     TEXT DEFAULT (datetime('now')),
  tryb      TEXT,                            -- 'scal' | 'zastap'
  n_wierszy INTEGER, n_nowych INTEGER, n_zaktualizowanych INTEGER,
  n_info INTEGER, n_ostrzezen INTEGER, n_do_decyzji INTEGER
);
CREATE TABLE IF NOT EXISTS importy_pozycje (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  import_id      INTEGER NOT NULL REFERENCES importy(id) ON DELETE CASCADE,
  poziom         TEXT NOT NULL,              -- 'INFO' | 'OSTRZEZENIE' | 'DECYZJA'
  arkusz         TEXT, wiersz INTEGER, kolumna TEXT,
  komunikat      TEXT NOT NULL,
  przed          TEXT, po TEXT,
  placowka_id    INTEGER, lead_id INTEGER, osoba_id INTEGER,
  rozstrzygniete INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_imp_poz ON importy_pozycje(import_id, poziom);

-- =====================================================================
-- WIDOKI — 'jeden wiersz jak w Excelu'. Cały kod czytający używa ICH.
-- =====================================================================

-- Płaski lead: to jest 'wiersz szkoły', którego oczekuje klient.
CREATE VIEW IF NOT EXISTS v_leady AS
SELECT
  l.id AS lead_id, p.id AS placowka_id,
  p.rspo, p.typ, p.nazwa, p.kod, p.miejscowosc, p.adres,
  p.kontakt, p.telefon, p.mail, p.ilosc_klas, p.ilosc_dzieci, p.mail_rodzice,
  l.handlowiec_id, h.nazwa AS handlowiec, h.etykieta_ph AS handlowiec_ph,
  l.status_szkoly, l.status_realizacji, l.deadline,
  l.dt, l.cykle, l.mail_propozycja, l.mail_wynajem, l.uwagi,
  l.pin_tydzien, l.aktywny, l.ostatnia_aktywnosc, l.powod_zwrotu,
  l.jul_dane_umowy, l.jul_standardy, l.jul_oswiadczenia, l.jul_niekaralnosc,
  l.jul_podanie_sala, l.jul_umowa, l.jul_librus,
  l.created_at, l.updated_at,
  (SELECT COUNT(*) FROM eventy e WHERE e.lead_id=l.id AND e.typ IN ('DT','START')) AS n_dt,
  (SELECT COUNT(*) FROM eventy e WHERE e.lead_id=l.id AND e.typ='CYKL')            AS n_cykl,
  (SELECT MIN(e.data) FROM eventy e WHERE e.lead_id=l.id AND e.typ IN ('DT','START')) AS pierwsze_dt
FROM leady l
JOIN placowki p ON p.id = l.placowka_id
LEFT JOIN osoby h ON h.id = l.handlowiec_id
WHERE p.scalona_z IS NULL;

-- BAZA do rozdawania: placówki z ewentualnym aktywnym leadem.
CREATE VIEW IF NOT EXISTS v_baza AS
SELECT p.*, l.id AS lead_id, l.handlowiec_id, h.nazwa AS handlowiec,
       l.status_realizacji, l.deadline, l.ostatnia_aktywnosc
FROM placowki p
LEFT JOIN leady l  ON l.placowka_id = p.id AND l.aktywny = 1
LEFT JOIN osoby h  ON h.id = l.handlowiec_id
WHERE p.scalona_z IS NULL;

-- Event z kontekstem — dokładnie to, co ma być na karcie/kaflu.
-- (Notatki 24.07: NAZWA szkoły · MIEJSCOWOŚĆ · ILOŚĆ KLAS · NR SALI.
--  STARTY dodaje: grupa · sprzęt · drukarz · kod Tinkercad.)
CREATE VIEW IF NOT EXISTS v_eventy AS
SELECT e.id, e.lead_id, e.typ, e.data, substr(e.data,1,7) AS miesiac,
       e.godz_od, e.godz_do, e.grupa, e.sprzet, e.sala,
       e.kod_tinkercad, e.link_tinkercad, e.status, e.uwagi,
       e.cykl_id, e.wygenerowany,
       COALESCE(p.kod, p.nazwa) AS szkola, p.nazwa AS szkola_pelna,
       p.miejscowosc, p.adres, p.ilosc_klas, p.ilosc_dzieci, p.telefon, p.kontakt,
       hl.nazwa AS handlowiec, l.status_realizacji,
       (SELECT GROUP_CONCAT(o.nazwa, ' + ') FROM event_osoby eo
          JOIN osoby o ON o.id=eo.osoba_id
         WHERE eo.event_id=e.id AND eo.rola IN ('prowadzacy','wspolprowadzacy')) AS prowadzacy,
       (SELECT GROUP_CONCAT(o.nazwa, ', ') FROM event_osoby eo
          JOIN osoby o ON o.id=eo.osoba_id
         WHERE eo.event_id=e.id AND eo.rola='zastepstwo')                        AS zastepstwo,
       (SELECT GROUP_CONCAT(o.nazwa, ', ') FROM event_osoby eo
          JOIN osoby o ON o.id=eo.osoba_id
         WHERE eo.event_id=e.id AND eo.rola='drukarz')                           AS drukarz
FROM eventy e
JOIN leady l     ON l.id = e.lead_id
JOIN placowki p  ON p.id = l.placowka_id
LEFT JOIN osoby hl ON hl.id = l.handlowiec_id;

-- Event × osoba prowadząca — źródło MACIERZY (wiersz = osoba) i licznika obciążenia.
-- Event z dwoma prowadzącymi pojawia się w DWÓCH wierszach macierzy. Tak ma być.
CREATE VIEW IF NOT EXISTS v_eventy_osoby AS
SELECT ev.*, eo.osoba_id, eo.rola, o.nazwa AS osoba, o.kolor AS osoba_kolor,
       o.sort_order AS osoba_sort
FROM v_eventy ev
JOIN event_osoby eo ON eo.event_id = ev.id
JOIN osoby o        ON o.id = eo.osoba_id;

-- KOLIZJE: ta sama OSOBA, ten sam dzień, NAKŁADAJĄCE SIĘ godziny.
-- Dwa eventy tego samego dnia BEZ nakładania to NIE kolizja — to norma.
-- Rola 'drukarz' nie liczy się do kolizji (nie prowadzi zajęć).
CREATE VIEW IF NOT EXISTS v_kolizje AS
SELECT ea.event_id AS event_id, eb.event_id AS event_id_2,
       ea.osoba_id, o.nazwa AS osoba, a.data,
       a.godz_od AS a_od, a.godz_do AS a_do, b.godz_od AS b_od, b.godz_do AS b_do
FROM event_osoby ea
JOIN event_osoby eb ON eb.osoba_id = ea.osoba_id AND eb.event_id <> ea.event_id
JOIN eventy a ON a.id = ea.event_id
JOIN eventy b ON b.id = eb.event_id
JOIN osoby  o ON o.id = ea.osoba_id
WHERE ea.rola IN ('prowadzacy','wspolprowadzacy','zastepstwo')
  AND eb.rola IN ('prowadzacy','wspolprowadzacy','zastepstwo')
  AND a.data = b.data AND a.id < b.id
  AND a.godz_od IS NOT NULL AND a.godz_do IS NOT NULL
  AND b.godz_od IS NOT NULL AND b.godz_do IS NOT NULL
  AND a.godz_od < b.godz_do AND b.godz_od < a.godz_do;

-- Obciążenie osoby (Pulpit + ekran Osoby) — dziś niemożliwe do policzenia.
CREATE VIEW IF NOT EXISTS v_obciazenie AS
SELECT eo.osoba_id, o.nazwa AS osoba, substr(e.data,1,7) AS miesiac,
       COUNT(*) AS n_zajec,
       SUM(CASE WHEN e.typ='CYKL' THEN 1 ELSE 0 END) AS n_cykl,
       SUM(CASE WHEN e.typ IN ('DT','START') THEN 1 ELSE 0 END) AS n_dt
FROM event_osoby eo
JOIN eventy e ON e.id = eo.event_id
JOIN osoby  o ON o.id = eo.osoba_id
WHERE eo.rola IN ('prowadzacy','wspolprowadzacy','zastepstwo')
GROUP BY eo.osoba_id, substr(e.data,1,7);
```

### 1.10. Dane startowe (seed)

**Osoby (29 kanonicznych)** — z `06_STARTY_aliasy_trenerow.md`, sekcja „Obciążenie per osoba".
**Aliasy (~120)** wpisane do seeda **z ręki, nie zgadywane**:
- 50 aliasów STARTY z tabeli „zapis w arkuszu → osoba kanoniczna",
- 40 + 24 etykiety trenerów z PH (`LISTA 6`, `LISTA 8`) zmapowane na osoby
  (`04. Zemela` → Paulina Zemela, `11. Białas (Pszczyna)` → Noemi Białas, …),
- 6 etykiet handlowców (`01. Sacawa` → Dominika Sacawa, `02. Olszewska` → Zuzanna Olszewska, …)
  + literówka `02. Olaszewska`,
- placeholdery `20. Trener 1`…`24. Trener 5` i puste `31.`…`40.` **pomijane**.

Role: `rola_handlowiec=1` dla Sacawa, Olszewska, Małolepsza, Chytry, Młynarczyk, Bittner;
`rola_trener=1` dla wszystkich 29 z STARTY. Osoby w obu rolach (Sacawa, Olszewska, Małolepsza,
Bittner) mają oba flagi — i to jest poprawne odwzorowanie rzeczywistości.

**Słowniki:**

| rodzaj | wartości |
|---|---|
| `miasto` | LISTA 5 z `BAZA` (kanoniczna) + `20. Ornontowice`, `21. Wyry`, `22. Gostyń`, `23. Strzyżowice`, `24. Katowice Południe` (`do_przegladu=1`) |
| `typ_placowki` | `01. Szkoła podstawowa`, `02. Przedszkole`, `03. Instytucja kultury`, `04. Zespół szkolno-przedszkolny`, `05. Inne` *(do potwierdzenia)* |
| `status_szkoly` | `01. Nowa szkoła`, `02. Kontynuacja` |
| `status_realizacji` | `01. Próba kontaktu (Brak konkretów)` (10), `02. Próba kontaktu (czekam na termin)` (20), **`05. DT w trakcie umawiania` (25 — nowy, z notatek)**, `03. DT umówione` (30), `04. BRAK KONTAKTU ZE SZKOŁĄ` (40), **`06. Zwrócony do puli` (50 — techniczny)** |
| `dt` | `01. Tak`, `02. Do ustalenia` |
| `tak_nie` | `01. Tak`, `02. Nie` |
| `mail_propozycja` | `01. Podsumowanie DT`, `02. Propozycja DT` |
| `dzien_tyg` | `poniedziałek`…`sobota` (bez niedzieli — tak mają) |
| `status_eventu` | `01. Zaplanowany`, `02. Zrealizowany`, `03. Odwołany` |
| `sprzet` | `01. Sala komputerowa`, `02. Nasze laptopy` *(z STARTY: 88 / 196 wpisów)* |
| `grupa` | `1`, `2`, `3`, `4` *(z STARTY: 180 / 86 / 18 / 2)* |

Liczba w nawiasie = `sort_order`. `05.` wyświetla się między `02.` i `03.` — to funkcjonalność z 1.7.

Aliasy słownikowe w seedzie: `09. pszczyna` → `09. Pszczyna powiat` ·
`15. bedzin` → `15. Będzin powiat` · `17. dabrowa gornicza` → `14. Dąbrowa Górnicza` ·
`10. katowice` → `08. Katowice` · `chorzow` → `16. Chorzów`.

---

## 2. Moduły i pliki

### 2.1. Drzewo

```
leady_app_v3/
├── app.py                  # fabryka Flask, rejestracja blueprintów. NIC WIĘCEJ.
├── schema.sql              # DDL z rozdz. 1.9
├── core/
│   ├── db.py               # połączenie (WAL, FK), init_db(schema.sql), helpery odczytu
│   ├── fields.py           # JEDNO ŹRÓDŁO definicji pól: tabela, etykieta, typ, słownik, widoki
│   ├── repo.py             # cały dostęp do danych: filtry, zapisz_pole (router tabel), operacje
│   ├── osoby.py            # osoby + aliasy + role + kolory + dopasowanie zapisu → osoba
│   ├── slowniki.py         # CRUD słowników nieosobowych, norm(), aliasy, fuzzy
│   ├── parsers.py          # ← z v1 + serial Excela, ="tel", timedelta, półpauza, blob placówki
│   └── activity.py         # dotknij(lead_id, kto, co, pole, przed, po) → pole + log
├── logika/
│   ├── kalendarz.py        # trzy buildery: macierz / agenda / starty (jedno źródło v_eventy*)
│   ├── cykle.py            # rozwijanie reguły → eventy, regeneracja
│   ├── kolizje.py          # odczyt v_kolizje + sprawdz_przed_zapisem()
│   ├── metryki.py          # Pulpit: po terminie, kolizje, lejek, cel tygodniowy, obciążenie
│   ├── import_ph.py        # import PH Nowy (5 arkuszy handlowców + BAZA)
│   ├── import_rspo.py      # import pliku RSPO (upsert placówek)
│   ├── import_starty.py    # import STARTY CZERWIEC (+ role, grupa, sprzęt, Tinkercad)
│   └── eksport.py          # ← z v1 + EKSPORT WYFILTROWANEGO WIDOKU
├── widoki/                 # blueprinty — jeden plik = jeden obszar, bez importów między nimi
│   ├── baza.py             # /baza + przypisanie + pula zwrotna
│   ├── handlowiec.py       # /handlowiec/<id> + pin tygodnia + cel
│   ├── zbiorczy.py         # /zbiorczy (widok Julki)
│   ├── lead.py             # /lead/<id> (karta+drawer) + PATCH pól + create
│   ├── eventy.py           # API eventów, cykli, ról + /api/kolizje
│   ├── kalendarz.py        # /kalendarz?widok=macierz|agenda|starty
│   ├── pulpit.py           # /pulpit
│   ├── osoby.py            # /osoby (ludzie, role, kolory, aliasy)
│   ├── slowniki.py         # /slowniki + API
│   └── io.py               # /import*, /export.xlsx
├── templates/
│   ├── base.html           # shell Broadsheet + nawigacja + selektor „kim jesteś"
│   ├── _filtry.html        # partial: pasek filtrów
│   ├── _tabela.html        # partial: tabela leadów z edycją inline (4 ekrany listowe)
│   ├── _drawer_lead.html   # partial: karta leada + eventy + log
│   ├── _kafel.html         # partial: kafel eventu w MACIERZY
│   ├── _karta_zajec.html   # partial: karta zajęć w widoku STARTY (kod, link, sprzęt, drukarz)
│   ├── baza.html · handlowiec.html · zbiorczy.html · niewykorzystane.html
│   ├── kalendarz.html      # + _widok_macierz.html · _widok_agenda.html · _widok_starty.html
│   ├── pulpit.html · osoby.html · slowniki.html · import.html · import_raport.html
├── static/
│   ├── style.css           # tokeny Broadsheet + klasy komponentów (rozdz. 5)
│   ├── app.js              # ← z v1: PATCH na change, toast, rollback + przełącznik widoku
│   └── fonts/              # Source Serif 4 hostowany lokalnie (patrz R21)
├── seed.py                 # osoby + 120 aliasów + słowniki + bootstrap na realnym pliku
├── smoke.py                # jedyny test: import realnych danych → każdy ekran zwraca 200
└── requirements.txt · Dockerfile · docker-compose.yml   ← z v1
```

### 2.2. Zakres odpowiedzialności (jedno zdanie na plik)

| Plik | Odpowiada za |
|---|---|
| `app.py` | Fabryka aplikacji: rejestruje blueprinty i nic poza tym (żeby nie był plikiem konfliktowym). |
| `schema.sql` | Cały DDL — jedyne miejsce, gdzie definiuje się strukturę bazy. |
| `core/db.py` | Otwarcie połączenia (WAL, `row_factory`, FK ON), `init_db()`, proste odczyty słownikowe. |
| `core/fields.py` | Lista pól `(etykieta, klucz, tabela, typ, słownik, widoki)` — kontrakt czytany przez szablony i eksport. |
| `core/repo.py` | Jedyne miejsce z SQL-em dla widoków: zapytania filtrowane, `zapisz_pole()` z routingiem tabel, `przypisz()`, `zwroc_do_puli()`, `scal_placowki()`. |
| `core/osoby.py` | Rozpoznanie „ten tekst = ta osoba" (alias → fuzzy → nowa/`DECYZJA`), role, kolory, CRUD osób i aliasów. |
| `core/slowniki.py` | `norm()`, dopasowanie aliasowe i rozmyte, CRUD słowników nieosobowych. |
| `core/parsers.py` | Zamiana brudnych wartości na typy: daty (w tym serial), godziny (time/float/timedelta/półpauza), liczby ze zbitek, telefon-formuła, rozbicie blobu `„Piekary Śląskie SP 13, gr 2"`. |
| `core/activity.py` | Jedna funkcja `dotknij()` — ustawia `ostatnia_aktywnosc` i pisze `log_aktywnosci`. |
| `logika/kalendarz.py` | Trzy buildery danych dla widoków macierz / agenda / starty — wszystkie z `v_eventy*`, żadnego własnego SQL-a poza nimi. |
| `logika/cykle.py` | Rozwinięcie reguły cyklu na daty i regeneracja eventów bez niszczenia ręcznych zmian. |
| `logika/kolizje.py` | Odczyt `v_kolizje` i sprawdzenie „czy ta osoba już coś ma w tych godzinach" przed zapisem. |
| `logika/metryki.py` | Liczby na Pulpit: po terminie, kolizje, lejek statusów, cel tygodniowy, obciążenie osób. |
| `logika/import_ph.py` | Wczytanie `PH Nowy`, dedup placówek, mapowanie osób, eventy DT, reguły cykli, raport. |
| `logika/import_rspo.py` | Upsert `placowki` z pliku RSPO regułą „wypełniaj puste", bez tworzenia leadów. |
| `logika/import_starty.py` | Wczytanie STARTY (miesiąc/rok z formularza), rozbicie blobu placówki, role osób, `grupa`/`sprzet`/Tinkercad, raport. |
| `logika/eksport.py` | XLSX **z dokładnie tych wierszy i kolumn, które użytkownik widzi po filtrze** + arkusz „Filtr". |
| `widoki/baza.py` | Ekran BAZA, masowe przypisanie z deadline'em, akcja puli zwrotnej. |
| `widoki/handlowiec.py` | Ekran „tylko moje leady", przypinanie na tydzień, pasek celu. |
| `widoki/zbiorczy.py` | Ekran Julki: leady z umówionym DT + jej 7 kolumn do odhaczania. |
| `widoki/lead.py` | Karta/drawer leada, `PATCH` pojedynczego pola, tworzenie leada ręcznie. |
| `widoki/eventy.py` | API eventu, cyklu i ról osób + `GET /api/kolizje` do ostrzeżenia na żywo. |
| `widoki/kalendarz.py` | Jeden ekran, trzy widoki (`?widok=`), filtr typu i zakresu. |
| `widoki/pulpit.py` | Ekran metryk + akcja „przenieś przeterminowane do puli". |
| `widoki/osoby.py` | Ekran ludzi: role, kolory, aliasy, scalanie dwóch osób w jedną, obciążenie. |
| `widoki/slowniki.py` | Ekran edycji list nieosobowych + aliasy. |
| `widoki/io.py` | Formularze trzech importów, uruchomienie, ekran raportu, pobranie eksportu. |
| `seed.py` | Osoby, ~120 aliasów, słowniki i jednorazowy import realnego pliku przy pierwszym starcie. |
| `smoke.py` | Jeden test end-to-end: import realnych danych → wszystkie ekrany 200 → liczby się zgadzają. |

### 2.3. Granice do pracy równoległej

Cztery strumienie, które nie wchodzą sobie w pliki:

| Strumień | Pliki | Wchodzi po |
|---|---|---|
| **A — fundament** | `schema.sql`, `core/*`, `seed.py`, `logika/import_*.py` | od razu |
| **B — ekrany listowe** | `widoki/{baza,handlowiec,zbiorczy,lead}.py`, `templates/_filtry.html`, `_tabela.html`, `_drawer_lead.html`, `baza.html`, `handlowiec.html`, `zbiorczy.html`, `niewykorzystane.html` | po zamrożeniu `fields.py` + `repo.py` |
| **C — kalendarze** | `logika/{kalendarz,cykle,kolizje}.py`, `widoki/{kalendarz,eventy}.py`, `templates/kalendarz.html`, `_widok_*.html`, `_kafel.html`, `_karta_zajec.html` | po zamrożeniu `schema.sql` (potrzebuje `v_eventy`, `v_eventy_osoby`, `v_kolizje`) |
| **D — pulpit / osoby / słowniki / IO / skóra** | `logika/{metryki,eksport}.py`, `widoki/{pulpit,osoby,slowniki,io}.py`, `static/*`, `base.html` | po zamrożeniu `schema.sql` |

**Reguły, żeby to nie eksplodowało:**
1. `schema.sql` i `core/fields.py` zamraża strumień A **w dniu 1**. Potem zmiana tylko przez
   uzgodnienie — to jedyne dwa pliki, których dotyka każdy.
2. **Żaden plik w `widoki/` nie pisze SQL-a.** Wszystko przez `core/repo.py`
   (dopisanie funkcji na końcu pliku ≈ brak konfliktu).
3. Blueprinty nie importują się wzajemnie. Wspólny HTML tylko w `templates/_*.html`,
   właścicielem partiali jest strumień B (`_kafel`, `_karta_zajec` — strumień C).
4. Każdy blueprint ma własny prefiks URL → brak kolizji route'ów.
5. `static/style.css` jest **tylko dodawany** (tokeny z rozdz. 5 na górze, klasy komponentów
   w środku, sekcje per-ekran na dole z komentarzem `/* --- ekran: kalendarz --- */`)
   — to jedyny plik dzielony przez wszystkich, więc podział na sekcje jest obowiązkowy.
6. `activity.dotknij()` wywołuje **każda** operacja zapisu — jedna linia, ale bez niej
   kontrola deadline'u kłamie.

### 2.4. Co bierzemy z v1/v2 i z design handoffu

| Źródło | Werdykt |
|---|---|
| v1 `parsers.py` | **przenieść prawie 1:1** → `core/parsers.py`; dodać serial Excela, `="601290441"`, `timedelta`, półpauzę, blob placówki |
| v1 `calendar_view.py` | **przenieść logikę, przepiąć źródło** — `build_grid`/`build_weeks` są dobre, ale czytają z `leady`; w v3 czytają `v_eventy_osoby`, a `find_collisions` zastępuje `v_kolizje` |
| v1 `exporter.py` | **rozbudować** — struktura arkuszy OK, brakuje eksportu wyfiltrowanego (`prompt_v2`) |
| v1 `importer.py` | **przepisać** — wybiera `Zbiorczy` (nieczytelny, R1), brak dedupu, raportu, eventów, osób |
| v1 `db.py` | **rozbić** na `core/db.py` + `core/fields.py`; `LEAD_FIELDS` to dobry pomysł, rozszerzamy o „tabela" i „widoki" |
| v1 `app.py` | **rozbić na blueprinty** — 250 linii dziś, w v3 byłoby 1500 i plik konfliktowy |
| v1 `templates/*`, `static/*` | **zachować MECHANIKĘ** (edycja inline `PATCH` na `change`, toast, rollback), **wymienić WYGLĄD** na Broadsheet |
| v1 `Dockerfile`, `docker-compose.yml` | **bez zmian** |
| `design/05_DESIGN_handoff.md` | **wiążące** dla tokenów, komponentów i trzech widoków kalendarza (rozdz. 5) |
| `design/makieta.dc.html` | **referencja wyglądu, NIE kod do skopiowania** — działa na innym runtime |
| `design/starty_normalized.json` | **dane do seeda demo** (286 realnych wpisów) + kontrakt pól karty zajęć |
| `design/06_STARTY_aliasy_trenerow.md` | **mapa aliasów do seeda 1:1** (50 pozycji) |

---

## 3. Ekrany i route'y

Legenda: **MVP** = w prototypie na demo · **F2** = faza druga, jawnie odłożone.

### 3.1. Ekrany (GET)

| Metoda | Ścieżka | Ekran / co robi | Dane dla szablonu | Faza |
|---|---|---|---|---|
| GET | `/` | redirect → `/baza` | — | MVP |
| GET | `/baza` | **BAZA** — baza główna do rozdawania. Filtry: `miasto`, `handlowiec` (w tym „— nieprzypisane —"), `typ` placówki, `status`, `q`. Zaznaczanie checkboxami → pasek akcji „Przypisz". Domyślnie **nieprzypisane** (to jest „lead znika z bazy głównej"). | `rows` (`v_baza`), `fields`, `slowniki`, `osoby_handlowcy`, `f`, `total`, `n_nieprzypisane` | MVP |
| GET | `/handlowiec/<osoba_id>` | **Widok handlowca** — tylko jego aktywne leady. Filtry: `miasto`, `status`, `q`, `tylko_po_terminie`. Przypięte na dany tydzień **na samej górze**. Edycja inline. Pasek celu: „umówione w tym tygodniu 3 / 5". | `rows`, `fields`, `slowniki`, `f`, `pinned`, `cel`, `zrobione_tydz`, `osoba` | MVP |
| GET | `/moje` | redirect na `/handlowiec/<kto_jestem z ciasteczka>` | — | MVP |
| GET | `/zbiorczy` | **Zbiorczy (widok Julki)** — leady ze `status_realizacji='03. DT umówione'`. Kolumny placówki do odczytu + **7 kolumn Julki edytowalnych** (Tak/Nie). Filtr po mieście, handlowcu, trenerze i „czego brakuje". | `rows`, `fields_jul`, `slowniki`, `f`, `braki` | MVP |
| GET | `/niewykorzystane` | **Niewykorzystane rekordy** — leady `aktywny=0` z `powod_zwrotu` **+** aktywne ze statusem `04. BRAK KONTAKTU ZE SZKOŁĄ` (bo tak dziś filtrują). Filtry `miasto`, `status`, `poprzedni handlowiec`. Zaznacz → „Przydziel innemu handlowcowi". | `rows`, `fields`, `slowniki`, `osoby_handlowcy`, `f`, `total` | MVP |
| GET | `/lead/<id>` | **Karta leada** (pełny ekran lub drawer `?frag=1`) — wszystkie pola, lista eventów DT i cyklicznych, reguły cykli, role osób, log aktywności. Odpowiednik ich „Klucza" z `Zbiorczy!AG`. | `lead`, `eventy`, `cykle`, `log`, `slowniki`, `osoby`, `kolizje_ids` | MVP |
| GET | `/kalendarz?widok=macierz&m=YYYY-MM&typ=DT&zakres=miesiac&tylko_z_wpisami=1` | **Kalendarz → MACIERZ** — siatka osoba × dzień, sticky pierwsza kolumna i nagłówek. Komórka = **stos kafli**, każdy kafel = jedno spotkanie (`szkoła · miejscowość · klasy · sala · godz`), lewy border w kolorze osoby. Kolizja = tło magenta + tag „kolizja". Miesiąc z daty — luty powstaje sam. | `cal` (dni × wiersze osób × komórki-listy), `month`, `months`, `n_events`, `n_kolizji`, `f` | MVP |
| GET | `/kalendarz?widok=agenda&m=&typ=` | **Kalendarz → AGENDA** — dzień po dniu: wielki numer dnia po lewej, po prawej lista spotkań sortowana po godzinie (kropka koloru osoby, godziny, placówka, miejscowość, prowadzący). Widok ratunkowy przy gęstych dniach i widok domyślny dla trenera na telefonie. | `dni` (lista dni z listami eventów), `n_events`, `f` | MVP |
| GET | `/kalendarz?widok=starty&m=&tydz=` | **Kalendarz → STARTY** — odwzorowanie ich zakładki: tygodnie jeden pod drugim, każdy tydzień = 5 kolumn (pon–pt), w kolumnie **stos kart zajęć**: badge typu (START magenta / CYKLICZNE cyan), godziny, placówka, adres, `Gr. N · sprzęt`, `TRENER …` + `Zastępstwo: …`, `Drukarz: …`, stopka z **kodem Tinkercad** i linkiem. To operacyjny dokument trenera. | `tygodnie` → `dni` → `karty`, `legenda`, `n_zajec` | MVP |
| GET | `/kalendarz/dt`, `/kalendarz/cykle`, `/starty` | Skróty (redirect z ustawionym `?widok=`/`?typ=`) — bo klientka myśli zakładkami, a nie parametrami. | — | MVP |
| GET | `/pulpit` | **Pulpit** — pasek wskaźników (leady / DT umówione / z datą / po terminie / kolizje); **po terminie** (lista + akcja); **kolizje** (lista); podział wg handlowca z paskiem postępu; **cel tygodniowy**; **obciążenie osób** (`v_obciazenie`); placówki i osoby `do_przegladu`. | `metryki`, `overdue`, `kolizje`, `per_h`, `cele`, `obciazenie`, `do_przegladu` | MVP |
| GET | `/osoby` | **Osoby** — 29 ludzi: rola (handlowiec / trener / oba), kolor, liczba zajęć, lista aliasów („znane zapisy: `ZUZA`, `ZUZIA OLSZEWSKA`, `02. Olszewska`…"), scalanie dwóch osób. Wartości `do_przegladu` na górze. | `osoby`, `aliasy`, `obciazenie`, `do_przegladu` | MVP |
| GET | `/slowniki` | **Słowniki** — karty per rodzaj (grid `auto-fill minmax(230px,1fr)`), dodawanie pozycji, dezaktywacja, zakładka aliasów. | `data`, `rodzaje`, `aliasy` | MVP |
| GET | `/import` | **Import** — trzy formularze (PH Nowy · RSPO · STARTY + pole miesiąc/rok) i lista ostatnich importów. | `importy`, `ostatni` | MVP |
| GET | `/import/raport/<id>` | **Raport importu** — INFO / OSTRZEŻENIE / DECYZJA; przy DECYZJI przyciski „ta sama szkoła / inna", „ta sama osoba / inna". | `imp`, `pozycje`, `n_per_poziom` | MVP |
| GET | `/export.xlsx?<filtry>&widok=baza\|handlowiec\|zbiorczy\|niewykorzystane\|kalendarz` | **Eksport wyfiltrowanego widoku** — te same wiersze i kolumny, co na ekranie, + arkusz „Filtr" z opisem. Nie jest ekranem, ale jest jawnym życzeniem klienta (`prompt_v2`). | — (plik) | MVP |
| GET | `/plan-tygodnia?tydz=` | Ekran planu tygodnia (przypięte leady wszystkich handlowców + postęp celów). Funkcja „do góry" jest już w `/handlowiec`. | `pinned`, `cele`, `tydz` | **F2** |
| GET | `/osoba/<id>/grafik?m=` | Agenda jednej osoby (do wysłania trenerowi). | `eventy`, `osoba` | **F2** |
| GET | `/osoba/<id>.ics` | Plik `.ics` z zajęciami osoby — tani zamiennik Google Calendar (~30 linii). | — (plik) | **F2 (tanie)** |
| GET | `/placowki/duplikaty` | Ekran scalania kandydatów na duplikaty poza raportem importu. | `pary` | **F2** |

### 3.2. API (zapisy)

| Metoda | Ścieżka | Co robi | Faza |
|---|---|---|---|
| PATCH | `/api/lead/<id>` | `{field, value}` — edycja jednego pola. Wymusza słownik/osobę (`400`), rzutuje typ, **routuje do `placowki` albo `leady`** wg `fields.py`, wywołuje `activity.dotknij()`. Zwraca `{ok, overdue, n_dt}`. | MVP |
| POST | `/api/lead` | Utworzenie leada ręcznie („stare szkoły"); tworzy placówkę, jeśli nie istnieje. | MVP |
| POST | `/api/przypisz` | `{placowka_ids[] \| lead_ids[], handlowiec_id, deadline}` — masowe przypisanie; tworzy lead, jeśli brak; status `01.`; log. Obsługuje też przydzielenie z puli. | MVP |
| POST | `/api/zwrot` | `{lead_ids[], powod}` — `aktywny=0`, `powod_zwrotu`, log. Lead trafia do „Niewykorzystanych". | MVP |
| POST | `/api/lead/<id>/pin` | `{tydzien}` / `{tydzien: null}` — „szkoły na tydzień do góry". | MVP |
| POST | `/api/event` | `{lead_id, typ, data, godz_od, godz_do, grupa, sprzet, sala, kod_tinkercad, link_tinkercad, osoby:[{osoba_id, rola}]}`. Zwraca `{ok:true, kolizje:[…]}` — kolizja to **ostrzeżenie, nie odmowa**. | MVP |
| PATCH | `/api/event/<id>` | Edycja pola eventu; ustawia `zmodyfikowany_recznie=1`, gdy event pochodzi z cyklu. | MVP |
| DELETE | `/api/event/<id>` | Usuwa event (nie leada). | MVP |
| POST/DELETE | `/api/event/<id>/osoba` | `{osoba_id, rola}` — dodanie/usunięcie prowadzącego, współprowadzącego, **zastępstwa** lub **drukarza**. | MVP |
| GET | `/api/kolizje?osoba_id=&data=&od=&do=&pomin=<event_id>` | Sprawdzenie na żywo, zanim użytkownik zapisze — do ostrzeżenia w formularzu. | MVP |
| POST | `/api/cykl` | Zapis reguły **i od razu materializacja** eventów (z `grupa`, `sprzet`, Tinkercad). | MVP |
| PATCH | `/api/cykl/<id>` | Edycja reguły → regeneracja przyszłych eventów `wygenerowany=1 AND zmodyfikowany_recznie=0`. | MVP |
| DELETE | `/api/cykl/<id>` | `aktywny=0` + usunięcie przyszłych wygenerowanych eventów. | MVP |
| POST | `/api/osoba` | Nowa osoba (`nazwa`, role, kolor). | MVP |
| PATCH | `/api/osoba/<id>` | Rola / kolor / `sort_order` / `aktywny` / `etykieta_ph` / `do_przegladu=0`. **Bez DELETE.** | MVP |
| POST | `/api/osoba/alias` | `{alias, osoba_id}` — ręczne dodanie aliasu (np. rozstrzygnięcie `MAJKA`). | MVP |
| POST | `/api/osoba/scal` | `{z_id, do_id}` — scalenie dwóch osób (aliasy i `event_osoby` przepisane). | MVP |
| POST | `/api/slownik` | Dodanie wartości. | MVP |
| PATCH | `/api/slownik/<id>` | Kolor / etykieta / `sort_order` / `aktywny`. **Bez DELETE** — tylko dezaktywacja. | MVP |
| POST | `/api/slownik/alias` | `{rodzaj, alias, wartosc}`. | MVP |
| POST | `/api/placowka/scal` | `{z_id, do_id}` — scalenie duplikatów. | MVP |
| POST | `/api/cel` | `{handlowiec_id, cel_tyg}`. | MVP |
| POST | `/api/kto-jestem` | `{osoba_id}` — ciasteczko dla `/moje` i pola `kto` w logu. Zamiast logowania. | MVP |
| POST | `/import/ph` · `/import/rspo` · `/import/starty` | Wgranie pliku (STARTY dodatkowo `{miesiac, rok}`), tryb `scal`/`zastap` → redirect na raport. | MVP |
| POST | `/api/import/<id>/decyzja` | `{pozycja_id, decyzja}` — rozstrzygnięcie z raportu. | MVP |
| POST | `/api/pulpit/przenies-przeterminowane` | Masowy zwrot do puli — **ręcznie, nie cronem**. | MVP |
| POST | `/api/gcal/push` · `/login` | — | **nie wchodzi** |

**Razem MVP: 20 ekranów GET + 27 endpointów zapisu.** Do zrobienia, bo połowa to warianty
tego samego: trzy widoki kalendarza z jednego źródła, cztery ekrany listowe z jednego partiala.

### 3.3. Który widok kalendarza dla kogo (rozstrzygnięcie skali)

Realny wolumen z STARTY: **286 wpisów w 2 tygodniach = ~29 zajęć na dzień roboczy przy 29 osobach.**
Rozkład jest nierówny: Kinga Król 22 zajęcia / 10 dni (2,2 dziennie), Ewa Łaczak 2.

Co to znaczy dla widoków:

| Widok | Gęstość przy realnych danych | Domyślny dla | Domyślny zakres |
|---|---|---|---|
| **Macierz** (osoba × dzień) | 29 wierszy × 20 dni ≈ 580 komórek, ~1–3 kafle w komórce. Czytelne per komórka, **za szerokie na miesiąc cyklicznych** | **koordynator** — bo tylko tu widać „całą firmę" i puste okna na zastępstwo | `typ=DT` → **miesiąc** (48 eventów, luźno) · `typ=CYKL` lub `wszystko` → **tydzień** |
| **Agenda** (dzień → lista) | ~29 wierszy na dzień, zawsze czytelne, jedna kolumna | ratunek przy gęstym dniu; telefon | tydzień |
| **Starty** (karty w kolumnach dni) | 5 kolumn × ~6 kart = duże, czytelne bloki z kodem i linkiem | **trener** — to jego dokument roboczy (co, gdzie, jaki sprzęt, jaki kod dla dzieci) | tydzień |

Rozstrzygnięcia:
1. **`tylko_z_wpisami=1` domyślnie włączone** w macierzy — inaczej klientka zobaczy 29 wierszy,
   z których 8 jest pustych, i powie „nieczytelne".
2. **Macierz z `typ=CYKL` na cały miesiąc jest zablokowana do zakresu tygodnia** (przełącznik
   `zakres=tydzien|miesiac`, przy `CYKL`+`miesiac` ostrzeżenie „580 kafli — pokazać mimo to?").
3. **Zakres domyślny liczony z danych, nie z kalendarza** — patrz R6.
4. Domyślny widok zapisywany w `ustawienia` per „kim jesteś" — koordynator wchodzi w macierz,
   trener w starty. Bez logowania, na ciasteczku.

---

## 4. Co pokazuje który ekran — mapowanie na wymagania

| Wymaganie klienta | Ekran w v3 | Źródło |
|---|---|---|
| przypisanie handlowca z listy + filtr miasto/handlowiec | `/baza` | `.docx` p.1, notatki k.1 p.1 |
| „ostateczny termin" na ruch | `/baza` (pasek przypisania) | `.docx` moduł RSPO |
| transfer: znika z bazy głównej | `/baza`, filtr „nieprzypisane" (domyślny) | `.docx` p.2 |
| widok handlowca, filtr miasto + status | `/handlowiec/<id>` | `.docx` p.2 |
| arkusze po statusie („DT w trakcie umawiania") | filtr statusu + nowa wartość `05.` | notatki k.1 p.2 |
| DT umówione → do Julki | `/zbiorczy` (filtr, nie kopiowanie) | `.docx` p.3 |
| DT umówione → kalendarz DT | `/kalendarz?widok=macierz&typ=DT` | `.docx` p.3 |
| **2–3 eventy dziennie u trenera** | komórka macierzy = stos kafli | `.docx` p.2 (bug) ⭐ |
| trener nie może mieć 2× aktywności | `v_kolizje` → ostrzeżenie w `/api/event` + licznik na `/pulpit` | notatki k.2 |
| kalendarz: nazwa · miejscowość · klasy · nr sali | `_kafel.html` | notatki k.2 |
| kalendarz zajęć cyklicznych | `/kalendarz?typ=CYKL` | `.docx` p.3 |
| plansza STARTY, trener = kolor | `/kalendarz?widok=starty` | `.docx` p.3 „Meksyk" |
| zastępstwa i szybka lokalizacja trenera | rola `zastepstwo` + karta zajęć + macierz z pustymi oknami | `.docx` p.3 |
| logistyka drukarek | rola `drukarz` na karcie zajęć | `starty-czerwiec.js` |
| kod klasy dla dzieci / Tinkercad | `kod_tinkercad`, `link_tinkercad` na karcie | `starty-czerwiec.js` |
| grupa 1 / grupa 2 tej samej szkoły | `eventy.grupa` + osobne reguły cyklu | `starty-czerwiec.js` |
| sala komputerowa vs nasze laptopy | `eventy.sprzet` | `starty-czerwiec.js` |
| miesiące z daty, bez sztywnego kodowania | `?m=YYYY-MM`, lista miesięcy z `v_eventy` | `.docx` p.2 |
| brak efektu → niewykorzystane → inny handlowiec | `/niewykorzystane` + `/api/przypisz` | `.docx` p.4 |
| kontrola aktywności przed terminem | `ostatnia_aktywnosc` + `/pulpit` | `.docx` moduł RSPO |
| RSPO: szkoły + przedszkola + instytucje kultury | `placowki.typ` + `/import/rspo` | notatki k.1 p.3 |
| listy rozwijane identyczne wszędzie | `osoby`+`slowniki` + wymuszanie w `PATCH` | `.docx`, wszędzie |
| **jedna osoba = jeden zapis** (50 → 29) | `/osoby` + aliasy + `v_obciazenie` | `06_STARTY_aliasy_trenerow.md` |
| wybrane szkoły na tydzień „do góry" | `pin_tydzien` + sort na `/handlowiec` | notatki k.1 p.4 |
| STATUS — minimum na tydzień | `cele` + pasek na `/handlowiec` i `/pulpit` | notatki k.1 p.4 |
| pobranie wyfiltrowanego do Excela | `/export.xlsx?<filtry>` | `prompt_v2` |
| Google Calendar per trener | — (`.ics` w F2) | `.docx`, „to jest przyszłość" |

---

## 5. Warstwa wizualna — ustalenia wiążące

`design/05_DESIGN_handoff.md` jest **wiążący** dla wyglądu. Ten rozdział mówi tylko, jak go
pogodzić z v3, która ma więcej ekranów, niż handoff opisuje.

### 5.1. Co bierzemy z handoffu bez dyskusji

- **Tokeny CSS** (`:root`) 1:1: papierowe tło `#f3f2f2`, tekst `#201e1d`, cyan `#0088b0`
  (interaktywne + cykliczne), magenta `#d6006c` (alerty + STARTy + kolizje), skala odstępów
  5/10/15/20/30/40, promienie 1–4 px, dwa cienie.
- **Typografia:** Source Serif 4, jeden krój, 15 px baza, nagłówki 600 + `letter-spacing:-0.015em`,
  kickery 11 px UPPERCASE `letter-spacing .08–.14em` w `--color-accent-700`.
- **Zasada „światło i cienka linia, nie ramki"**; `.card` tylko dla dyskretnych elementów
  (pozycje słowników, karty zajęć), nigdy do budowy layoutu.
- **Klasy komponentów** `.btn/.btn-primary/.btn-secondary/.tag*/.input/.card/.table` — dokładnie
  jak w handoffie, wklejone do `style.css` **przed** sekcjami per-ekran.
- **Liczby:** `font-variant-numeric: tabular-nums`, kolumny liczbowe do prawej.
- **Trzy widoki kalendarza** z przełącznikiem segmentowym i parametrem `?widok=macierz|agenda|starty`.
- **Struktura karty zajęć** w widoku Starty: badge typu → godziny → placówka → adres →
  `Gr. N · sprzęt` → `TRENER …` (+ `Zastępstwo:`) → stopka `kod` (mono, tło `--color-neutral-100`)
  + `Tinkercad ↗`.
- Desktop, treść max ~1360 px, wyśrodkowana.

### 5.2. Czego handoff nie obejmuje — i jak to domykamy

Handoff opisuje 4 ekrany (Pulpit, Tabela, Kalendarz, Słowniki). v3 ma 20. Reguła:

| Ekran v3 | Wzorzec z handoffu |
|---|---|
| `/baza`, `/handlowiec`, `/zbiorczy`, `/niewykorzystane` | **„Tabela"** — ten sam nagłówek (kicker + h1), ten sam pasek filtrów, ta sama `.table` z edycją inline. Cztery ekrany, jeden partial `_tabela.html`. Różnią się tylko zestawem kolumn (z `fields.py`) i domyślnym filtrem. |
| `/lead/<id>` | **karta** — układ jak karta zajęć ze Startów, ale pionowo; sekcje rozdzielone linią. |
| `/osoby` | **„Słowniki"** — grid kart, próbka koloru, lista aliasów jako tagi (`.tag-accent`). |
| `/import`, `/import/raport` | **„Pulpit"** — pasek wielkich liczb (wierszy / poprawionych / do decyzji) + dwie kolumny tabel. Poziom `DECYZJA` na magenta, `INFO` neutralnie. |
| `/kalendarz` | dokładnie handoff (trzy widoki) |

**Kolizja koncepcji, którą rozstrzygamy tutaj:** wersja 1.0 tego spec postulowała odtworzenie
kolorów nagłówków z ich Excela (zielony `#93C47D`, różowy `#F4CCCC`) „dla rozpoznawalności".
To jest **sprzeczne** z systemem Broadsheet (papier + dwa oszczędne akcenty).
**Wygrywa handoff.** Rozpoznawalność budujemy inacz:
- **kolejnością kolumn** identyczną z ich `BAZA` (A→AG),
- **nazwami kolumn** dosłownie ich („death line", „Prowadzący DT", „WYPEŁNIA JULIA"),
- kolumny Julki wyróżnione **kickerem `WYPEŁNIA JULIA` i cienką linią**, nie różowym tłem.

Ryzyko tej decyzji jest realne (R22) i trzeba je świadomie ponieść: ładniejszy ekran,
o pół sekundy dłuższe rozpoznanie „to mój plik".

### 5.3. Kolory osób

23 kolory z ich Excela istnieją tylko dla 4 osób i są to czyste RGB (`#FF00FF`, `#00FF00`),
które na papierowym tle wyglądają jak błąd. Rozstrzygnięcie:

- zachowujemy **tożsamość** kolorów (Małolepsza = magenta-różowy, Olszewska = pomarańcz,
  Majewska = zielony, Zemela = mięta), ale **stonowane do palety Broadsheet**
  (obniżona jaskrawość, kontrast tekstu ≥ 4.5:1 na `--color-bg`),
- pozostałe 25 osób: kolor deterministyczny z hasza `nazwa` w ograniczonej palecie
  (stabilny między restartami — inaczej po każdym deployu trener zmienia kolor i klientka traci zaufanie),
- kolor każdej osoby edytowalny na `/osoby` (`<input type="color">` → `PATCH /api/osoba/<id>`),
- kafel/karta używa koloru osoby **tylko na lewym borderze i jako 12 % tło** — nigdy jako
  tło tekstu, żeby przy 29 kolorach ekran nie stał się plakatem.

### 5.4. Zależności zewnętrzne

Source Serif 4 z Google Fonts to **jedyna** zewnętrzna zależność frontu — i **hostujemy ją
lokalnie** w `static/fonts/` (patrz R21). Zero bibliotek JS. Ikony jako znaki tekstowe
(`↓ ↑ ▦ ☰ ▤ ✕ ↗`).

---

## 6. Zakres prototypu — twarde decyzje

### 6.1. Wchodzi

BAZA + przypisanie · widok handlowca + pin + cel · Zbiorczy · Niewykorzystane · karta leada ·
eventy DT (CRUD) · cykle (reguła + materializacja) · **role przy eventzie: prowadzący,
współprowadzący, zastępstwo, drukarz** · **pola `grupa`, `sprzet`, `kod_tinkercad`,
`link_tinkercad`** · kalendarz w trzech widokach (macierz / agenda / starty) · osoby + aliasy
+ scalanie + obciążenie · pulpit z kolizjami i po terminie · słowniki + aliasy · trzy importy
+ raport + scalanie duplikatów · eksport wyfiltrowanego widoku · `ostatnia_aktywnosc` + cienki log.

**Rozstrzygnięcie nowych pól z STARTY** (żadnego nie pomijamy milcząco):

| Pole | Decyzja | Dlaczego |
|---|---|---|
| `grupa` (1–4) | **MVP** | Bez tego gr.1 12:25 i gr.2 13:35 w tej samej szkole wyglądają jak duplikat. 286 wpisów, wszystkie mają grupę. |
| `sprzet` (sala komputerowa / nasze laptopy) | **MVP** | Trener musi wiedzieć, czy pakować laptopy. Jeden słownik, jedno pole, widoczne na karcie w handoffie. |
| `zastepstwo` (rola) | **MVP** | 18 z 286 wpisów. To powód istnienia planszy STARTY („zastępstwa i szybka lokalizacja trenera"). |
| `drukarz` (rola) | **MVP** | 256 z 286 wpisów. Logistyka drukarek jest realną operacją; pominięcie zrobiłoby z karty atrapę. |
| `kod_tinkercad`, `link_tinkercad` | **MVP** | To, czym trener faktycznie prowadzi zajęcia. Zero logiki: tekst + URL. |
| `wspolprowadzacy` (drugi trener) | **MVP** | 4 wpisy („`… + kornelia gawron (1)`"). Bez tego dane się gubią przy imporcie — a cichy ubytek danych jest najgorszym możliwym błędem demo. |
| zarządzanie klasami Tinkercad przez API | **NIE** | Integracja z zewnętrznym serwisem; klient nie prosił. |
| ewidencja sprzętu (który egzemplarz drukarki, numer seryjny) | **NIE** | `drukarz` = kto dowozi, nie co dowozi. Inwentarz to inny produkt. |
| workflow zastępstw (zgłoszenie → akceptacja → powiadomienie) | **NIE** | W MVP zastępstwo to wpis, nie proces. |

### 6.2. Nie wchodzi — i dlaczego

| Kandydat | Decyzja | Uzasadnienie | Co dajemy zamiast |
|---|---|---|---|
| **Logowanie i role** | **NIE** | Żaden z bólów B1–B5 nie jest bólem dostępu. Klientka pisze „koordynator odbiera dostęp", ale z kontekstu wynika, że chodzi o *zniknięcie leada z listy roboczej*, nie o uprawnienia (`00_kontekst_v1.md` §5). Auth = tabela użytkowników, sesje, reset hasła, guardy w każdym widoku ≈ 1/3 budżetu prototypu za zero wartości na demo. | Selektor „kim jesteś" w pasku górnym (ciasteczko) → `/moje`, domyślny widok kalendarza per rola, `kto` w logu. Na demo wygląda identycznie. **Do powiedzenia wprost:** w prototypie Sacawa widzi Chytrego; docelowo to jeden dekorator. |
| **Google Calendar (push)** | **NIE** | OAuth + zgoda per trener + obsługa aktualizacji i usunięć = dni pracy z zależnością, która może padnąć **w trakcie demo**. Klientka: „to jest przyszłość". | Kolumna `gcal_event_id` od dnia 1 (bez niej późniejszy push zduplikuje eventy przy każdej edycji — ostrzeżenie z `00_kontekst_v1.md` §7). Eksport `.ics` per osoba w F2 (~30 linii) pokrywa 80 % potrzeby. |
| **Moduł rozliczeń** | **NIE** | Nikt nie poprosił w tej rundzie. Istnieje w starym pliku (`JEDNORAZÓWKI`, `PRZEDSZKOLA FAKTURY`, 3 000 formuł), ale to osobny produkt. | Nic. Świadomie milczymy. |
| **RSPO przez API** | **NIE** | Koordynatorka **i tak filtruje RSPO ręcznie po miastach regionu** przed wgraniem (`.docx`) — plik jest jej realnym procesem. API to zależność od zewnętrznego kontraktu dla funkcji używanej raz na rok. | Import pliku `.xlsx`/`.csv` z regułą „wypełniaj puste". |
| **Cron / automatyczne wygaszanie deadline'ów** | **NIE** | Klientka wprost: *„jeśli się to da zrobić — jeśli nie, będę to robiła ręcznie, tu akurat to najmniej ważne"*. Rekord, który sam znika w trakcie demo, buduje nieufność. | Flaga „po terminie" liczona przy odczycie + lista na Pulpicie + **przycisk** „Przenieś do puli". Półautomat, człowiek zatwierdza. |
| **Pełny audyt / historia wersji** | **NIE** | „Najmniej ważne" wg klientki. | `ostatnia_aktywnosc` + cienki log w karcie leada. |
| **Załączniki, wysyłka maili, generowanie umów** | **NIE** | Kolumny Julki to *checklisty* („Umowa podpisana: Tak/Nie"), nie repozytorium plików. | Kolumny Tak/Nie dokładnie jak u niej. |
| **Frontend framework / build step (npm)** | **NIE** | Prototyp musi wstać na ich VPS jednym `docker compose up`. Toolchain = ryzyko przed demo, zero wartości dla użytkownika arkusza. Handoff wymaga wyłącznie czystego CSS. | Jinja + vanilla JS + `PATCH` na `change` (mechanika z v1 działa i wygląda jak arkusz). |
| **Widok mobilny / responsywny** | **NIE** | Handoff mówi wprost „cały layout na desktop". | Widok Agenda jest jednokolumnowy i przypadkowo używalny na telefonie — to wystarczy jako odpowiedź na pytanie „a na telefonie?". |
| **Wielo-region / wiele województw** | **NIE** | Dziś jeden region (Śląskie). | Filtr po miejscowości. |
| **Testy automatyczne poza smoke** | **NIE** | Prototyp weryfikuje klient klikaniem (rozdz. 7). | `smoke.py`: import realnych danych → każdy ekran 200 → liczby się zgadzają. Jedyny test, ale obowiązkowy. |

### 6.3. Dwie rzeczy, które robimy PONAD zakres — i dlaczego

1. **Raport importu + scalanie duplikatów.** Formalnie nikt nie prosił. Ale wymóg brzmiał
   „import musi zadziałać **bez czyszczenia danych ręcznie**", a ich dane mają **trzy**
   nazewnictwa tych samych szkół. Bez tego demo pokaże duplikaty i klientka powie
   „to nie są moje dane". Raport zamienia najbrzydszą część migracji w argument sprzedażowy (S8).
2. **Ekran Osoby + licznik obciążenia.** Klientka nie prosiła — bo nie wie, że to możliwe.
   Ale „ile zajęć ma Kinga Król" to pytanie, które zadaje sobie przy każdym zastępstwie,
   a dziś jest bez odpowiedzi (dwa zapisy: `KINGA KRÓL` i `kinga`). To jedno z najtańszych
   „wow" w całym projekcie: jeden widok SQL i jedna tabela (S12).

---

## 7. Scenariusze akceptacyjne (do przeklikania z klientką)

Język klienta. Każdy: *co robisz → co widzisz*. Na ich realnych danych po imporcie.

---

### S1. Rozdanie szkół handlowcowi
**Robisz:** wchodzisz w **BAZA**, ustawiasz *Miejscowość = 08. Katowice* i
*Typ = Szkoła podstawowa*. Zaznaczasz 6 szkół, u góry wybierasz *Emil Chytry*, wpisujesz
ostateczny termin `30.09.2026`, klikasz **Przypisz**.
**Widzisz:** te 6 szkół zniknęło z listy (BAZA pokazuje domyślnie nierozdane — licznik spadł
z 312 na 306). Klikasz filtr *handlowiec = Emil Chytry* i one są, każda z terminem `30.09`.
Nic nie zostało skopiowane ani usunięte — to ta sama szkoła, tylko z przypisaniem.

---

### S2. Handlowiec umawia dzień technologiczny
**Robisz:** wchodzisz w widok **Chytry**. Przy `SP 11 Będzin` wpisujesz kontakt i telefon,
zmieniasz status na *05. DT w trakcie umawiania*, a po telefonie na *03. DT umówione*.
Klikasz **+ DT**: data `16.09.2026`, godziny `08:00–09:35`, prowadzący *Paulina Zemela*,
sala `12`, sprzęt *Nasze laptopy*.
**Widzisz:** wiersz ma odznakę `DT ×1`. W **Zbiorczy** (u Julki) ta szkoła jest już na liście,
z pustymi kolumnami Julki do odhaczenia. W **Kalendarzu → Macierz** we wrześniu, w wierszu
*Paulina Zemela*, pod `16.09` jest kafel: `SP 11 · Będzin · 12 klas · sala 12 · 8:00–9:35`.
Nigdzie nie wpisywałaś tego drugi raz.

---

### S3. ⭐ DWA I TRZY DNI TECHNOLOGICZNE JEDNEGO DNIA U JEDNEGO TRENERA
> *Scenariusz dowodzący naprawy zgłoszonego błędu. Pokazać pierwszy, jeśli mało czasu.*

**Robisz:** przy `SP 8 Będzin` klikasz **+ DT**: `16.09.2026`, `11:00–12:30`, *Paulina Zemela*.
Potem przy `SP 3 Mikołów` jeszcze raz: `16.09.2026`, `13:00–14:30`, *Paulina Zemela*.
**Widzisz:** w **Macierzy**, w wierszu *Paulina Zemela*, w komórce `16.09` są **TRZY** kafle
jeden pod drugim:
```
8:00–9:35    SP 11 · Będzin  · 12 klas · sala 12
11:00–12:30  SP 8  · Będzin  ·  8 klas · sala 4
13:00–14:30  SP 3  · Mikołów · 14 klas · sala 7
```
Wszystkie trzy widoczne, żadnego nie trzeba szukać. Trener planuje cały dzień z jednego ekranu.
U góry licznik: *„48 spotkań w miesiącu"*.

**Dlaczego wcześniej się nie dało:** komórka kalendarza w arkuszu pobierała dane funkcją
`XLOOKUP`, która zwraca **pierwsze** trafienie. Drugi i trzeci wpis istniał w danych,
ale komórka fizycznie umiała pokazać jeden. Tu komórka to lista, więc problem nie istnieje.

---

### S4. Kiedy trener naprawdę nie może być w dwóch miejscach
**Robisz:** przy `SP 21 Katowice` wpisujesz DT na `16.09.2026`, `9:00–10:30`,
*Paulina Zemela* — a ona ma już wtedy zajęcia do `9:35`.
**Widzisz:** zanim zapiszesz, czerwone (magenta) ostrzeżenie:
*„Paulina Zemela ma już 16.09 spotkanie 8:00–9:35 w SP 11 Będzin — godziny się nakładają"*.
Możesz zapisać świadomie (bywa, że trzeba) — wtedy oba kafle mają magenta tło i tag „kolizja",
a na **Pulpicie** widnieje *„Kolizje trenerów: 1"* z linkiem do obu wpisów.

> Różnica względem S3 jest zamierzona: **trzy spotkania w dniu = normalna praca**,
> **nakładające się godziny = ostrzeżenie**. Wcześniej nie było widać ani jednego, ani drugiego.

---

### S5. Szkoła przekłada termin — poprawiasz w JEDNYM miejscu
**Robisz:** `SP 11 Będzin` przenosi DT z `16.09` na `23.09`. Wchodzisz w kartę leada
i zmieniasz datę.
**Widzisz:** kafel przeskoczył z `16.09` pod `23.09` — w Macierzy, w Agendzie i na Startach.
U Julki data się zaktualizowała. Nie poprawiałaś w trzech miejscach — bo nie ma trzech miejsc.

---

### S6. Zajęcia cykliczne: dwie grupy, cały semestr, jeden wpis na grupę
**Robisz:** przy `SP Strzyżowice` klikasz **+ Zajęcia cykliczne**: `poniedziałek`,
`12:25–13:25`, **grupa 1**, *Zuzanna Olszewska*, sprzęt *Sala komputerowa*,
kod `BMR DKP QHW`, od `07.09.2026` do `25.01.2027`. Zapisujesz. Potem to samo dla
**grupy 2**, `13:35–14:35`.
**Widzisz:** *„Utworzono 20 terminów"* i drugie *„Utworzono 20 terminów"*.
**Kalendarz → Starty** ma w każdy poniedziałek **dwie osobne karty** dla tej szkoły —
grupa 1 i grupa 2, każda ze swoją godziną i swoim kodem dla dzieci. Nie wyglądają
jak podwójny wpis, bo nim nie są.
Gdy jedne zajęcia wypadną (ferie), otwierasz ten jeden termin i zmieniasz go albo usuwasz —
reszta serii zostaje. Gdy zmienisz godzinę w regule, wszystkie przyszłe terminy się przestawiają,
a ten poprawiony ręcznie zostaje nietknięty.

> A jeśli zajęcia są dwa razy w tygodniu („poniedziałek i piątek") — to **dwie** reguły,
> nie jedna komórka z tekstem. Dopiero wtedy da się je zobaczyć w kalendarzu.

---

### S7. Handlowiec nie ruszył szkoły — wraca do puli
**Robisz:** mija `30.09`. Na **Pulpicie**, sekcja *Po terminie bez umówionego DT* — 4 szkoły
Chytrego, przy każdej data ostatniego ruchu (albo „nic nie ruszał"). Zaznaczasz je,
klikasz **Przenieś do puli**, powód „brak kontaktu".
**Widzisz:** zniknęły z widoku Chytrego i są w **Niewykorzystanych rekordach** z adnotacją
„wcześniej: Emil Chytry, powód: brak kontaktu". Zaznaczasz jedną, wybierasz *Zuzanna Olszewska*
i nowy termin — szkoła pojawia się u niej, z zachowaną historią wcześniejszych prób.

---

### S8. Import waszego pliku sam go sprząta
**Robisz:** w **Imporcie** wgrywasz `PH Nowy`, potem `STARTY CZERWIEC` (podając miesiąc: czerwiec 2026).
**Widzisz:** raport:
```
PH Nowy — wczytano 1 043 wiersze z 6 zakładek
Poprawione automatycznie (34):
  „02. Olaszewska"        → Zuzanna Olszewska            28 wierszy
  „11. Białass (Pszczyna)" → Noemi Białas                 3 wiersze
  „22. Trene 3"           → (placeholder, pominięty)      2 wiersze
  „19. Chorzow"           → „16. Chorzów"                 1 wiersz
Ujednolicone miejscowości (2 listy → 1):
  „09. Pszczyna" = „09. Pszczyna powiat" · „17. Dąbrowa Górnicza" = „14. Dąbrowa Górnicza"

STARTY CZERWIEC — wczytano 286 wpisów
Rozpoznane osoby: 50 różnych zapisów → 29 osób
  „ZUZA", „ZUZANNA", „ZUZIA OLSZEWSKA", „ZUZANNA OLSZEWSKA" → Zuzanna Olszewska   (20 zajęć)
  „NATALIA STARZOSMKA" → Natalia Starzomska · „PATRYK PALSU" → Patryk Palus
  „WERONIKA MAŁOLEPSZA + kornelia gawron (1)" → dwie osoby na jednych zajęciach
Do decyzji (12):
  kto to „MAJKA"?  [Maja Majewska] [Weronika Małolepsza] [nowa osoba]
  kto to „SARA"?   [nowa osoba] [pomiń]
  „?? MAJA" jako drukarz (20 wpisów)                     [wskaż osobę] [pomiń]
  czy „MSP 2" i „MIEJSKA SZKOŁA PODSTAWOWA NR 2 W KNUROWIE" to ta sama szkoła?  [ta sama] [inna]
```
Potem próbujesz gdziekolwiek wpisać handlowca „Olaszewska" — **nie da się**, lista pozwala
wybrać tylko istniejące osoby. Ta literówka nie może już wrócić.

---

### S9. Filtrujesz i pobierasz dokładnie to, co widzisz
**Robisz:** w **Zbiorczy** ustawiasz *Miejscowość = 05. Knurów*, *Trener = Paulina Zemela*,
*brakuje: Umowa podpisana*. Zostaje 7 wierszy. Klikasz **Pobierz Excel**.
**Widzisz:** plik z **tymi siedmioma wierszami** i tymi kolumnami, które widzisz na ekranie —
nie z całą bazą. W pliku dodatkowa zakładka „Filtr" z opisem, co dokładnie pobrałaś,
żeby po tygodniu wiedzieć, czym jest ten plik na pulpicie.

---

### S10. Plansza STARTY: cała firma i wszystko, co trener musi wiedzieć
**Robisz:** wchodzisz w **Kalendarz → Starty**, tydzień `01–05.06`.
**Widzisz:** pięć kolumn (pon–pt), w każdej stos kart zajęć. Na jednej karcie:
```
[CYKLICZNE]                                   12:25–13:25
SP Strzyżowice
Strzyżowice, ul. 1 Maja 17
Gr. 1 · Sala komputerowa
TRENER  Zuzanna Olszewska
DRUKARZ Zuzanna Olszewska
BMR DKP QHW                          Tinkercad ↗
```
STARTy są magenta, cykliczne cyan. Na jedno spojrzenie widać, kto gdzie jest w piątek,
kto ma okno i może wziąć zastępstwo, i kto wiezie drukarkę. Klikasz **Macierz** —
te same dane w siatce osoba × dzień, każda osoba w swoim kolorze.

**Potem:** wpisujesz DT na `10.02.2027`. Wybierasz *luty 2027* — **jest, z wpisem**.
Nikt tego miesiąca nie tworzył, nikt nie kopiował formuł. (W arkuszu zakładka
`Kalendarz LUTY DT` jest pusta, bo trzeba ją zrobić ręcznie.)

---

### S11 *(bonus)*. Plan tygodnia i minimum
**Robisz:** w widoku **Olszewska** zaznaczasz 5 szkół gwiazdką „na ten tydzień".
**Widzisz:** wskoczyły na samą górę listy. Nad nimi pasek: *„Umówione w tym tygodniu: 2 z 5"*.
Ten sam pasek dla wszystkich handlowców jest na Pulpicie — widzisz, kto realizuje minimum,
bez pytania.

> **Do ustalenia:** ile ma wynosić „minimum na tydzień" (dziś 5, ustawiane per handlowiec).

---

### S12 *(bonus, mocny)*. Ile kto ma zajęć — pytanie, na które dziś nie ma odpowiedzi
**Robisz:** wchodzisz w **Osoby**.
**Widzisz:** listę 29 osób z liczbą zajęć w wybranym okresie:
```
Kinga Król          22        Zuzanna Olszewska   20        Damian Paziewski  20
Mateusz Pustelnik   17        Monika Swoboda      16        …
Ewa Łaczak           2
```
Przy każdej osobie rozwijasz „znane zapisy" i widzisz, z czego to policzono:
*Kinga Król ← `KINGA KRÓL`, `kinga`* · *Mateusz Pustelnik ← `MATEUSZ PUSTELNIK`,
`MATI PUSTELNIK`, `mateusz pustelnik`*.

**Dlaczego to jest ważne:** w arkuszu ta sama osoba ma do czterech różnych zapisów, więc
`COUNTIF` liczy każdy zapis osobno. Nie da się powiedzieć, kto jest przeciążony, ani kto
ma miejsce na kolejną szkołę. Tu jest to jedna liczba — i to ona ma decydować, komu
handlowiec dogra następną szkołę.

---

## 8. Ryzyka i pułapki

### Wysadzą prototyp technicznie

**R1. Import z zakładki `Zbiorczy` zwróci puste dane.** `Zbiorczy` to w 100 % formuły
`VSTACK/FILTER`, zapisane jako `=IFERROR(__xludf.DUMMYFUNCTION("…"), <wartość>)`.
`openpyxl` z `data_only=True` na pliku z Google Sheets **może nie mieć zbuforowanych wartości**
dla nieobsługiwanych funkcji. **Importer v1 wybiera właśnie `Zbiorczy` jako pierwszy**
(`importer._pick_sheet`) — v3 odziedziczyłaby ten błąd z marszu.
→ czytamy **5 arkuszy handlowców + `BAZA`** (literalne wartości). `Zbiorczy` ignorujemy.

**R2. `Sacawa` ma `max_row = 50500`.** Naiwna pętla po `ws.max_row` na 6 arkuszach = minuty
i setki MB. → `read_only=True`, `values_only=True`, stop po 200 pustych wierszach.

**R3. Dane nie zaczynają się w tym samym wierszu wszędzie** (handlowcy i `BAZA` od 4,
widoki od 2, wiersze 2–3 to kolorowane śmieci). Zahardkodowanie numeru = import gubi
lub duplikuje dane. → autodetekcja pierwszego wiersza danych.

**R4. Macierz utonie w HTML-u.** 29 osób × 20 dni roboczych ≈ 580 komórek i ~570 kafli
przy cyklicznych. → `tylko_z_wpisami=1` domyślnie, pon–pt domyślnie, `zakres=tydzien`
wymuszony dla `typ=CYKL`, `position: sticky` na kolumnie osoby i nagłówku (jak w handoffie).

**R5. Cykliczne zatopią kalendarz DT.** 70 leadów × ~35 terminów = 2 500 eventów.
Dla SQLite to nic, dla oka wszystko. → filtr `typ` z domyślnym `DT` w macierzy,
`data_koniec` w regule **wymagana**, na Startach domyślnie tydzień.

**R6. Demo otworzy się na pustym miesiącu.** Dziś lipiec 2026; dane DT to wrzesień 2026 –
styczeń 2027, a STARTY to czerwiec. Domyślne `m = dzisiaj[:7]` (jak w v1) pokaże pusty ekran
w pierwszej sekundzie demo. → domyślny miesiąc = **miesiąc z największą liczbą eventów**,
zapisany w `ustawienia`.

**R7. Serial daty `46206.0` i godzina `0.3715277`.** Wynikają z tego, że wartość przychodzi
jako fallback `IFERROR`, a nie sformatowana data. Bez obsługi serialu deadline'y wyjdą jako
`1899-12-30` (widać to wprost w ich `AI4 = 30.12.1899||04. Zemela`). → parser z epoką `1899-12-30`.

**R8. Duplikaty placówek po imporcie z TRZECH źródeł.** `BAZA` (980 nazw UPPER) +
arkusze handlowców (~120 kodów) + STARTY (~60 blobów `SP.11 BĘDZIN`) → bez dopasowania
będzie ~1 160 rekordów, w których jedna szkoła występuje trzy razy. Klientka zauważy
w pierwszej minucie. → dopasowanie 4-stopniowe + ekran decyzji (1.8).

**R9. Godziny z półpauzą.** W STARTY jest `12:25–13:25` z `–` (U+2013), nie `-`.
Regex na `-` przepuści połowę danych jako „brak godziny", a wtedy **detekcja kolizji przestaje
działać w milczeniu** (warunek `godz_od IS NOT NULL` po prostu nie łapie). → `[-–—]` w parserze
+ asercja w `smoke.py`: „liczba eventów bez godziny = 0".

**R10. STARTY nie ma dat, tylko `dzien_nr` 1–5 i 8–12.** Import bez parametru miesiąc/rok
wstawi eventy w losowy miesiąc albo padnie. → pole miesiąc/rok w formularzu importu,
walidacja „czy `dzien_nr` z podanym miesiącem daje dzień roboczy".

**R11. SQLite i kilku edytujących naraz.** Inline edit generuje dużo krótkich zapisów.
Bez WAL trafi się `database is locked` w środku demo. → `PRAGMA journal_mode=WAL`,
transakcja na jedno pole, brak długich odczytów w transakcji. Konflikt: „ostatni wygrywa
**na poziomie pola**" — wystarcza, bo dwie osoby rzadko edytują to samo pole.

**R12. `event_osoby` to o jeden JOIN więcej w najgorętszym zapytaniu.** Macierz czyta
`v_eventy_osoby`, który sam jest widokiem na widok — przy 2 500 eventach SQLite policzy to bez
problemu, ale przy `GROUP_CONCAT` w `v_eventy` łatwo zrobić zapytanie N+1 z szablonu.
→ builder pobiera **wszystkie** eventy miesiąca jednym zapytaniem i grupuje w Pythonie;
szablon nie wykonuje żadnych zapytań (zakaz w code review).

**R13. Polskie znaki i nazwy plików.** Nazwa ich pliku ma podwójne spacje i polskie znaki,
system to Windows → Linux (Docker). → jawne `encoding='utf-8'`, sanityzacja `download_name`,
brak polskich znaków w nazwach plików wynikowych.

**R14. Osoby scalone za agresywnie = katastrofa cicha.** Gdyby `norm('03. Małolepsza')`
automatycznie trafił w `Weronika Małolepsza`, przypisania handlowca zmieszałyby się z grafikiem
trenera i nikt by tego nie zauważył, bo dane dalej wyglądałyby sensownie.
→ **reguła z 1.4: alias jednotokenowy nigdy nie scala się automatycznie**; wszystkie aliasy
jednotokenowe wchodzą z seeda, z ręki. `smoke.py` sprawdza liczbę osób = 29 po imporcie.

### Zniechęcą klienta produktowo

**R15. „To nie wygląda jak mój arkusz".** Klientka myśli komórkami i filtrami. → zostaje
tabela z gęstymi wierszami, edycja w komórce, filtry nad kolumnami, **kolejność i nazwy
kolumn dokładnie jej** (A→AG, „death line", „WYPEŁNIA JULIA").

**R16. Jedna szkoła w kilku wierszach.** Gdyby ekran listowy pokazał 3 wiersze dla szkoły
z 3 DT, klientka uzna to za regres. → reguła z 1.1: listy zawsze jeden wiersz + odznaka `DT ×3`.

**R17. Pytanie „a czy Sacawa widzi leady Chytrego?"** padnie, bo w Sheets to był ich problem.
→ przygotowana odpowiedź: *w prototypie tak, docelowo to jedna linia przy logowaniu*.
Nie improwizować.

**R18. „Minimum na tydzień" jest wymyślone.** Notatki mówią, że licznik ma być, ale nie ile.
→ wartość edytowalna + **jawne pytanie** na demo.

**R19. Scope creep w trakcie demo.** Po S3 klientka będzie mieć 10 nowych pomysłów.
→ lista „faza 2" widoczna w aplikacji (stopka/`README`), żeby każde życzenie miało gdzie
wylądować zamiast wchodzić do prototypu na żywo.

**R20. „Niewykorzystane rekordy" znaczą u nich dwie rzeczy.** W pliku to
`QUERY(… WHERE Col3='04. BRAK KONTAKTU ZE SZKOŁĄ')`, w `.docx` to „rekordy odebrane po terminie".
→ ekran pokazuje **oba zbiory** (z etykietą, skąd rekord się wziął) i pytamy, czy tak zostaje.

**R21. Font z Google Fonts nie wczyta się na demo.** Handoff wymaga Source Serif 4 z CDN.
Jeśli demo idzie przez ich VPS z filtrowaniem wyjścia albo z laptopa bez internetu, cały
system wizualny spada do Georgii — i „hifi" przestaje być hifi w najgorszym momencie.
→ **font hostowany lokalnie** w `static/fonts/` (woff2, 2 wagi + italic ≈ 120 kB),
`font-display: swap`, Georgia jako fallback.

**R22. Konflikt „ładne" vs „rozpoznawalne".** Broadsheet zabiera jej excelowe kolory nagłówków
(zielony/różowy), po których nawigowała wzrokiem. Ryzyko: ekran ładniejszy, rozpoznanie
„to mój plik" o sekundę dłuższe. → rekompensata kolejnością i nazwami kolumn (5.2).
**Jeśli na demo klientka powie „gdzie moje kolory" — dodać cienki pasek koloru nad grupą kolumn.
Nie kłócić się.**

**R23. 29 kolorów osób zamieni ekran w plakat.** Przy 4 osobach kolor jest informacją,
przy 29 — szumem. → kolor tylko na lewym borderze i jako 12 % tło (5.3), nigdy jako tło tekstu;
w Agendzie tylko kropka.

**R24. Zniknięcie danych bez śladu = utrata zaufania.** Każda operacja „usuwająca"
(zwrot do puli, dezaktywacja słownika, scalenie placówek/osób) musi pokazywać „gdzie to teraz
jest" i być odwracalna jednym kliknięciem. Nie kasujemy nic fizycznie.

**R25. Ryzyko odwrotne — przeinwestowanie.** Największym ryzykiem projektu jest to, że zamiast
prototypu na demo powstanie system produkcyjny bez klienta. Wszystko z 6.2 jest zablokowane
do momentu, w którym klientka powie „tak, o to chodziło".

### Pytania do klientki (zabrać na demo)

1. **Kto to `MAJKA`?** (4 zajęcia) — Maja Majewska, Weronika Małolepsza, czy ktoś inny?
2. **Kto to `SARA`** z wpisu `MATEUSZ PUSTELNIK + SARA`? (brak nazwiska w danych)
3. **`?? MAJA` i `?? NATALIA M`** jako drukarz (38 wpisów) — kto to?
4. Czy `03. Małolepsza` (handlowiec) i `WERONIKA MAŁOLEPSZA` (trener) to **ta sama osoba**?
   To samo dla `Bitner` / `18. Bitner` / `AGATA BITTNER` (dwa „t").
5. Jakie dokładnie **typy placówek** ma RSPO w Waszym imporcie? (proponujemy 5 wartości)
6. Ile wynosi **„minimum na tydzień"** i czy jest jednakowe dla wszystkich?
7. `09. Pszczyna` vs `09. Pszczyna powiat`, `15. Będzin` vs `15. Będzin powiat` — to samo,
   czy dwa różne obszary?
8. Status `05. DT w trakcie umawiania` — tak go nazywamy i ma być między „czekam na termin"
   a „DT umówione"?
9. „Niewykorzystane rekordy" = brak kontaktu, przekroczony termin, czy oba?
10. Czy zajęcia cykliczne mają **datę końca** (koniec semestru), czy trwają bezterminowo?
11. Co znaczy **grupa 3 i 4** (18 i 2 wpisy) — trzecia grupa w tej samej szkole, czy coś innego?
12. Czy **`zastepstwo` to zawsze osoba**, czy czasem notatka („odwołane", „do ustalenia")?
13. Kto ma widzieć czyje leady — izolacja handlowców to wymóg, czy wygoda?
14. Czy trenerom wystarczy plik `.ics` w telefonie, czy naprawdę potrzebny push do Google Calendar?

---

## 9. Kolejność implementacji (dla planowania, nie deadline)

| Krok | Zawartość | Bez tego nie ruszy |
|---|---|---|
| 1 | `schema.sql`, `core/db.py`, `fields.py`, `osoby.py`, `slowniki.py`, `seed.py` (29 osób + 120 aliasów) | wszystko |
| 2 | `core/parsers.py`, `logika/import_ph.py`, raport importu | demo na realnych danych |
| 3 | `core/repo.py`, `_tabela.html`, `_filtry.html`, `/baza`, `/handlowiec` + tokeny Broadsheet w `style.css` | S1, S2 |
| 4 | `widoki/eventy.py`, `logika/kolizje.py`, `logika/kalendarz.py` (macierz), `/kalendarz` | **S3 ⭐**, S4 |
| 5 | `/zbiorczy`, `/niewykorzystane`, `/lead/<id>` | S5, S7 |
| 6 | `logika/cykle.py`, `logika/import_starty.py`, widoki agenda + starty, `_karta_zajec.html` | S6, S10 |
| 7 | `logika/metryki.py`, `/pulpit`, `/osoby`, `cele`, pin tygodnia | S7, S11, **S12** |
| 8 | `logika/eksport.py` (wyfiltrowany), `/slowniki`, `import_rspo` | S8, S9 |
| 9 | `smoke.py`, Docker, przejście S1–S12 po kolei | demo |

Krok 4 jest punktem, w którym prototyp zaczyna mieć sens sprzedażowy — gdyby zabrakło czasu,
na nim można pokazywać. Krok 6 dodaje drugą połowę wartości (STARTY to ich „Meksyk").
