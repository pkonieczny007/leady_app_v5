# Projekt migracji bazy na rejestr RSPO

**Data:** 23.08.2026. **Status na 24.08:** WYKONANE na profilu `test` — etapy
M1, M2, M3 (514 z 545 numerów), M5, M6, M7 i M8. Zostało **M4** (scalanie 25 par,
narzędzia jeszcze nie ma) i **M9** (ekran rejestru dla koordynatorki).
Profil `prod` NIETKNIĘTY. Liczby i odstępstwa od tego projektu:
`docs/poprawka 24.08.2026/STAN_SESJI_2026-08-24.md`.

Dwa świadome odstępstwa od tego, co niżej: (1) `miejscowosc` czyszczona jest
RAZEM z przejściem na powiat, a nie tydzień później — bo filtr i tak się
przełącza w tym samym commicie; (2) zespoły szkolno-przedszkolne wchodzą do bazy
WSZYSTKIE (decyzja Pawła: „wolę mieć za dużo niż za mało"), choć pkt 1.4 tego
projektu zakładał rekord tylko dla składowych. **Zastępuje** plan z `docs/12_RSPO.md` w części dotyczącej
modelu danych (tamten dokument zakładał „dosypanie" rejestru do istniejącej
tabeli; ten projekt rozdziela lustro rejestru od bazy roboczej — powody niżej).

**Czego chce klient (rozmowa 23.08, plik `baza_aktualizacja`):** numery RSPO do
tego, co jest → zero dubli → powiaty zgodne z rejestrem zamiast naszych
„miejscowości" → dołożenie brakujących placówek z obecnych powiatów → możliwość
rozszerzania terenu w przyszłości. I nadrzędnie: **nic z obecnej pracy
handlowców nie ginie**.

Stan wyjściowy (zweryfikowany na `data/prod/leady_v3.db` 23.08):
545 placówek, 545 leadów, 65 eventów, `placowki.rspo` puste w 545/545,
13 wpisów w `log` (11 od automatu zwrotu), 409 placówek z realną pracą,
136 nietkniętych, 18 par dubli w bloku id 517–545.

---

## 1. Model docelowy

### 1.1. Rozstrzygnięcie: lustro rejestru to OSOBNA tabela, nie kolumny w `placowki`

Dwie populacje o różnym cyklu życia:

| | lustro rejestru | baza robocza `placowki` |
|---|---|---|
| wierszy | 6 116 (całe śląskie) | 545 → ~1 300 |
| kto pisze | wyłącznie import z CSV | ludzie + formularz terenowy |
| polityka nadpisywania | **rejestr wygrywa zawsze** | **człowiek wygrywa** (import uzupełnia tylko puste) |
| kasowanie / odtworzenie | wolno w całości (odtwarzalne z pliku) | nigdy (wisi na tym historia) |

Gdyby to była jedna tabela, te dwie polityki nadpisywania musiałyby żyć w jednej
procedurze importu z regułami per kolumna — dokładnie tam rodzą się ciche utraty
danych („dlaczego zniknął telefon, który handlowiec poprawił?"). Osobna tabela
daje jeszcze dwie rzeczy za darmo: comiesięczne odświeżenie rejestru **nie
dotyka ani jednego wiersza roboczego** (odwracalność), a 134 użycia `placowki`
w kodzie (ekrany, formularze, filtry) nie widzą 4 800 placówek spoza naszego
terenu, więc żaden ekran nie wymaga natychmiastowej przeróbki.

### 1.2. Tabele nowe (schemat przejmowany z `rspo_app`, sprawdzony w działaniu)

```sql
-- LUSTRO REJESTRU. Jeden wiersz = jeden wiersz rejestru RSPO. 34 kolumny
-- z POLA_RSPO z rspo_app/db.py (rspo, nazwa, typ, regon, nip, wojewodztwo,
-- powiat, gmina, miejscowosc, rodzaj_miejscowosci, teryt_gmina, ulica,
-- nr_budynku, nr_lokalu, kod_pocztowy, poczta, telefon, faks, email, www,
-- dyrektor, publicznosc, kategoria_uczniow, specyfika, liczba_uczniow, jezyki,
-- organ_typ, organ_nazwa, organ_regon, miejsce_w_strukturze, rspo_nadrzedny,
-- nazwa_nadrzedna, data_zalozenia, data_likwidacji) + ślad importów.
CREATE TABLE rspo_rejestr (
  rspo INTEGER PRIMARY KEY,          -- tożsamość niesie numer, nie nazwa
  ...,                               -- 33 kolumny rejestru j.w.
  pierwszy_import TEXT,
  ostatni_import TEXT,               -- kiedy ostatnio potwierdził go plik
  ostatnia_zmiana TEXT,
  nieobecna_od TEXT                  -- zniknęła z pliku — OZNACZAMY, nie kasujemy
);
CREATE INDEX ix_rr_powiat ON rspo_rejestr(powiat);
CREATE INDEX ix_rr_gmina  ON rspo_rejestr(gmina);
CREATE INDEX ix_rr_nadrz  ON rspo_rejestr(rspo_nadrzedny);

-- Dziennik wgrań i zmian pole-po-polu — przejęte z rspo_app/magazyn.py razem
-- z bezpiecznikiem wycinka (PROG_ZNIKNIEC=0.20, MIN_ZNIKNIEC=25): plik, w którym
-- zniknęło >20% placówek, to prawie na pewno eksport jednego powiatu, nie rejestr.
CREATE TABLE rspo_importy (...);     -- jak `importy` w rspo_app
CREATE TABLE rspo_zmiany  (...);     -- jak `zmiany` w rspo_app

-- OBSZARY DZIAŁANIA FIRMY — to jest odpowiedź na „rejony muszą być powiatami
-- z RSPO". Jedna pozycja = jeden powiat albo jedna gmina, nazwa DOKŁADNIE jak
-- w rejestrze (miasta na prawach powiatu gołą nazwą: 'Katowice', 'Rybnik';
-- powiaty ziemskie małą literą: 'mikołowski'). Gmina po to, żeby dało się wziąć
-- Knurów bez reszty powiatu gliwickiego — uwaga klienta o Rybniku pokazuje,
-- że ta granulacja jest potrzebna od pierwszego dnia.
CREATE TABLE obszary_dzialania (
  id        INTEGER PRIMARY KEY,
  rodzaj    TEXT NOT NULL,           -- 'powiat' | 'gmina'
  wartosc   TEXT NOT NULL,           -- nazwa 1:1 z kolumny Powiat/Gmina rejestru
  kolejnosc INTEGER NOT NULL DEFAULT 100,  -- kolejność Kasi; ZAMIAST prefiksów '01. '
  aktywny   INTEGER NOT NULL DEFAULT 1,
  UNIQUE(rodzaj, wartosc)
);
```

Zawartość startowa `obszary_dzialania` = lista koordynatorki, 17 pozycji:
16 × powiat (`Katowice`, `Sosnowiec`, `Zabrze`, `Rybnik`, `Tychy`,
`Dąbrowa Górnicza`, `Ruda Śląska`, `Chorzów`, `Jaworzno`, `Żory`,
`Siemianowice Śląskie`, `Piekary Śląskie`, `Świętochłowice`, `pszczyński`,
`będziński`, `mikołowski`) + 1 × gmina (`Knurów`). Przecięcie z lustrem
i typami klienta = **1 259 placówek** (549 SP + 710 przedszkoli; +23 punkty
przedszkolne, jeśli klient potwierdzi — pkt 9).

### 1.3. Zmiany w `placowki` (tabela robocza — zostaje, dostaje geografię)

```
rspo             — już jest, z częściowym UNIQUE; staje się łącznikiem do lustra
powiat, gmina    — kopiowane z lustra po nadaniu rspo; dla rekordów bez rspo
                   wpisuje je człowiek. NIE wchodzą do PLACOWKA_FIELDS (formularz
                   edycji ich nie pokazuje) — wzorzec EVENT_KOLUMNY_TECHNICZNE:
                   pole, które ma własną drogę zapisu, nie jest zwykłym polem karty
obszar           — WYLICZANE: obszar działania, który łapie placówkę
                   (gmina bije powiat — reguła z rspo_app/rejony.py, jedyna,
                   której nie trzeba pamiętać). Dla Knurowa 'Knurów', dla
                   Orzesza 'mikołowski'. Przeliczane funkcją obszary.przelicz()
                   po każdym imporcie i każdej zmianie obszarów
nazwa_potoczna   — skrót handlowca ('MSP 1', 'korczakowska'). Po scaleniu dubli
                   i przyjęciu nazw rejestrowych to jedyne miejsce, gdzie skrót
                   przeżywa; wyszukiwarka formularza przeszukuje nazwę I skrót,
                   bo handlowiec w terenie wpisze 'msp 1', nie 'MIEJSKA SZKOŁA…'
```

`miejscowosc` **zostaje** (134 użycia w 30+ plikach — patrz pkt 3), ale zmienia
źródło: docelowo czysta nazwa z rejestru, bez prefiksu.

Kolumny `powiat`/`gmina` trzymamy **zdenormalizowane na placówce**, nie tylko
w lustrze, z dwóch powodów: (a) rekordy lokalne bez numeru RSPO (EduHub itp.)
też muszą mieć geografię, inaczej wypadają z każdego filtra; (b) filtry i eksport
nie robią JOIN-a z tabelą, którą raz w miesiącu przepisuje import.

### 1.4. Zespoły szkolno-przedszkolne

Rejestr rozbija ZSP na wiersze: zespół (`jednostka złożona`) + składowe
(SP, przedszkola) z `RSPO podmiotu nadrzędnego`. W śląskim 510 z 1 464 SP ma
podmiot nadrzędny; w zakresie klienta 341 z 1 259 placówek należy do zespołu.

**Rozstrzygnięcie: rekord roboczy powstaje dla JEDNOSTKI SKŁADOWEJ (SP,
przedszkole, punkt), NIE dla zespołu.** Wiersze `jednostka złożona` zostają
tylko w lustrze. Powody:
- proces sprzedażowy klienta rozróżnia szkołę od przedszkola (typ eventu
  `CYKLICZNE-PRZEDSZKOLE` istnieje od sierpnia); jeden rekord „ZSP 23" nie
  pomieściłby DT w podstawówce i osobnych cykli w dwóch przedszkolach zespołu,
- to jednostka składowa ma typ i liczbę uczniów — czyli to, po czym handlowiec
  wybiera, do kogo dzwoni.

Rekord klienta, który dziś dopasowuje się do numeru ZESPOŁU, dostaje numer
jednostki składowej typu SP (deterministycznie: wiersz lustra z tym
`rspo_nadrzedny` i typem `Szkoła podstawowa`; gdy składowych SP jest ≠1 —
do decyzji człowieka w pliku z etapu M3).

Żeby lista nie wyglądała na zdublowaną („SP nr 11" i „Przedszkole nr 15" pod
tym samym adresem), karta placówki i wyniki wyszukiwania pokazują dopisek
z lustra: „w zespole: ZSP nr 23 w Katowicach" (JOIN po `rspo_nadrzedny` —
w locie, bez kolumny; to informacja, nie oś filtrowania).

---

## 2. Kolizja nazw „rejony"

Dziś `rejony` = `(trener, miasto)` — „kto po czym jeździ" (`przydzial.py`,
trasa `/rejony`, `templates/rejony.html`). Klient słowem „rejony" nazywa obszar
działania firmy. Dwa pojęcia nie mogą dzielić nazwy, bo za miesiąc ktoś
naprawi „rejony" nie te, co trzeba.

| pojęcie | tabela | moduł | trasa | szablon | etykieta w menu |
|---|---|---|---|---|---|
| obszar działania firmy (powiaty/gminy z RSPO) | `obszary_dzialania` | `obszary.py` | `/obszary` | `obszary.html` | „Obszary działania" |
| teren trenera | `rejony_trenerow` (rename z `rejony`) | zostaje w `przydzial.py` | `/rejony-trenerow` | `rejony_trenerow.html` | „Rejony trenerów" (bez zmian merytorycznych) |

Zasada nazewnicza na przyszłość: **„obszar" = geografia firmy, „rejon" = zawsze
z dopełniaczem czyim** („rejon trenera"). Rename tabeli to
`ALTER TABLE rejony RENAME TO rejony_trenerow` + poprawka nazw w `przydzial.py`
(5 miejsc) i trasie — pół godziny, a oszczędza tygodni mylenia pojęć.

Docelowo (etap M8) `rejony_trenerow` przechodzi z kolumny `miasto`
(wartości z prefiksami ze słownika `miasto`) na pary `(rodzaj, wartosc)` jak
w `obszary_dzialania` — trener może mieć cały powiat albo jedną gminę, a
podpowiedź „jeździ tu" w przydziale porównuje geografię placówki z geografią
trenera tą samą regułą gmina-bije-powiat. Do etapu M8 zostaje po staremu.

---

## 3. `miejscowosc` i słownik `miasto` — przejście bez łamania 134 użyć

### Diagnoza (dlaczego dzisiejsza oś jest nie do utrzymania)

Słownik `miasto` (33 pozycje, 11 pustych) miesza trzy skale: miasta
(`08. Katowice`), wsie dopisane ręcznie (`23. Strzyżowice`, `27. Wola`,
`28. Frydek`) i worki powiatowe po urwanym przy imporcie słowie „powiat"
(`09. Pszczyna` = 27 różnych miejscowości, `15. Będzin` = 17). Ornontowice
(powiat mikołowski) siedzą pod `01. Orzesze`. `Psary` występują w śląskim
dwa razy (będziński i lubliniecki) — sama nazwa miejscowości nie identyfikuje.
Klient żąda wprost: filtry mają iść po powiatach zgodnych z RSPO.

### Rozstrzygnięcie: trzy osie zamiast jednej, przełączane etapami

- **`obszar`** — nowa oś FILTROWANIA (17 wartości = lista koordynatorki).
  To po niej idzie formularz i `/baza`. Nie jest pozycją słownika `slowniki` —
  jej źródłem jest tabela `obszary_dzialania` (jedno źródło; drugi słownik
  z tymi samymi wartościami zaraz by się rozjechał). Nie jest edytowana
  ręcznie, więc twarda blokada „wartość spoza słownika" jej nie dotyczy.
- **`powiat`, `gmina`** — surowa geografia z rejestru, do raportów i przeliczeń.
- **`miejscowosc`** — zostaje jako INFORMACJA na karcie i w wynikach
  wyszukiwania („SP w Woli, gm. Miedźna"), docelowo czysta nazwa z rejestru.
  Przestaje być typu `slownik:miasto`, staje się `text` — bo miejscowości
  w zakresie będzie ~150 (wsie powiatów ziemskich) i lista rozwijana traci sens.

### Kolejność przełączania (szczegóły etapów w pkt 4)

1. Dochodzą kolumny `powiat`/`gmina`/`obszar` — **`miejscowosc` nietknięta**,
   wszystkie 134 użycia działają jak wczoraj.
2. Formularz i `/baza` dostają filtr „Obszar" (formularz: wybór obszaru →
   szkoła, zamiast miasto → szkoła); `miejscowosc` w `PLACOWKA_FIELDS`
   zmienia typ ze `slownik:miasto` na `text`. To JEDYNY moment dotykania kodu
   filtrów i jest odwracalny gitem, bo nie zmienia danych.
3. Dopiero po przełączeniu ekranów: `UPDATE placowki SET miejscowosc = (czysta
   nazwa z lustra)` po `rspo`. Robione na końcu, bo rekord z miejscowością
   `Wojkowice Kościelne` przy filtrze działającym jeszcze po słowniku
   `15. Będzin` **zniknąłby handlowcowi z oczu** — a ukryty filtr wygląda jak
   zgubione dane (zasada projektu).

### Słownik `miasto` i prefiksy

- Słownik `miasto` dostaje `aktywny=0` w etapie M8 — **nie kasujemy**: tabela
  `aliasy` (21 wpisów rodzaju `miasto`) musi dalej normalizować stare pliki
  przy imporcie arkuszy klienta, a historyczne eksporty mają się zgadzać.
- **Prefiksy `01. `–`33. ` NIE przechodzą** na `powiat`/`gmina`/`obszar`.
  Wymóg klienta „musi być takie same jak w RSPO" bije nawyk sortowania,
  a kolejność Kasi niesie kolumna `obszary_dzialania.kolejnosc` — listy
  i eksporty sortują po niej, więc porządek na ekranie zostaje ten sam.
  (Do potwierdzenia z Kasią — pkt 9.)

---

## 4. Kolejność migracji — etapy M0–M9, każdy odwracalny

Zasady wspólne: każdy etap zaczyna się od `narzedzia/baza.py kopia` (kopia
PRZED, jak w `wdroz.sh`); każdy etap najpierw w całości na profilu `test`
(i demo na VPS), na `prod` dopiero po obejrzeniu wyniku; etapy wymagające
decyzji człowieka kończą się PLIKIEM do zatwierdzenia, nie automatem; każdy
zapis do danych roboczych zostawia ślad w `log` (`co='migracja-rspo'`,
`przed`/`po`). Narzędzia migracji to skrypty w `narzedzia/` (konwencja:
najpierw skrypt, ekranem zostaje to, co ma być używane co miesiąc).

### M0. Kopie i inwentaryzacja
- Wejście: brak.
- Robi: kopia `.db` + `.xlsx` prod, weryfikacja (`integrity_check` + licznik
  545 — plik o dobrej nazwie to jeszcze nie kopia); zrzut liczb kontrolnych
  (placówki/leady/eventy/log) do pliku w `docs/poprawka 23.08.2026/`.
- Wyjście: kopia odtwarzalna, liczby spisane. Odwracalność: n/d (nic nie zmienia).

### M1. Lustro rejestru
- Wejście: M0. Robi: nowe tabele `rspo_rejestr`/`rspo_importy`/`rspo_zmiany`
  (kod przejęty z `rspo_app`: `db.py` POLA_RSPO, `magazyn.wgraj()`, `plik.py`
  z „pancerzem Excela" `="…"`), wgranie `rspo_2026_08_08.csv` zawężonego do
  `ŚLĄSKIE`. **Nie dotyka żadnej istniejącej tabeli.**
- Wyjście (sprawdzenie): 6 116 wierszy; liczniki per powiat zgodne z analizą
  (Katowice 225 w typach klienta itd.); `Numer RSPO` unikalny.
- Odwracalność: `DROP TABLE` × 3 — zero skutków ubocznych.

### M2. Obszary działania
- Wejście: M1. Robi: tabela `obszary_dzialania` + 17 pozycji startowych,
  moduł `obszary.py` z `przelicz()`.
- Wyjście: przecięcie lustro × obszary × typy (SP, przedszkole, punkt) =
  **1 259** — jeśli inna liczba, najpierw wyjaśnić, potem iść dalej.
- Odwracalność: `DROP TABLE obszary_dzialania`.

### M3. Nadanie numerów RSPO istniejącym 545 — plik decyzyjny
- Wejście: M1 (lustro do porównań). Robi skrypt `narzedzia/migracja_rspo.py
  dopasuj`: zestawia TRZY źródła — raport `rspo.py dopasuj` (466 pewnych + 10
  po numerze), plik klienta `POPRAWKA BAZY - RSPO dopasowane.xlsx` (457
  wpisanych) i lustro. Wynik: xlsx z kolumnami *nasz rekord / numer wg raportu /
  numer wg klienta / werdykt*.
  - **automat wpisze wyłącznie zgodne**: oba źródła wskazują ten sam numer,
  - rozjazd, tylko jedno źródło, brak — wiersz do ręcznej decyzji Kasi/Przemka,
  - numer wskazywany przez DWA nasze rekordy (18 przypadków) → NIE wpisujemy
    żadnemu, para idzie do M4 (częściowy UNIQUE na `rspo` i tak by drugiego
    nie przyjął — ale świadome „to jest dubel" jest lepsze niż wyjątek SQL).
- Po zatwierdzeniu: `migracja_rspo.py wpisz plik.xlsx` — każdy UPDATE z wpisem
  do `log` (`pole='rspo'`, `przed=NULL`, `po=numer`).
- Wyjście: raport ile z 545 ma numer (cel: wszystkie poza lokalnymi bez
  odpowiednika w rejestrze i parami z M4). Odwracalność: `UPDATE rspo=NULL`
  po liście z loga.

### M4. Scalenie dubli — plik decyzyjny (reguła w pkt 5)
- Wejście: M3 (duble ujawnione numerami). PRZED startem sprawdzić grepem, że
  kod nigdzie nie zakłada `leady.id == placowka_id` (dziś równość jest
  przypadkiem importu; sprawdzenie 23.08 nie znalazło takiego założenia —
  powtórzyć na aktualnym kodzie).
- Wyjście: 0 par wskazujących ten sam numer; wszystkie eventy z par widoczne
  w kalendarzu (licznik eventów PRZED == PO — scalanie niczego nie kasuje
  z `eventy`).
- Odwracalność: kopia z początku etapu + pełny zrzut JSON kasowanego wiersza
  w `log.przed`.

### M5. Geografia dla istniejących
- Wejście: M2 + M3. Robi: `UPDATE placowki SET powiat, gmina` z lustra po
  `rspo`; `obszary.przelicz()` wypełnia `obszar`. Rekordy bez `rspo` (lokalne)
  dostają geografię z pliku decyzyjnego M3 (kolumna uzupełniana ręcznie).
- Wyjście: lista placówek bez `obszar` — akceptowalna tylko, gdy każda pozycja
  ma wyjaśnienie (np. Książenice — pkt 9). `miejscowosc` NIETKNIĘTA.
- Odwracalność: kolumny są nowe — wyzerowanie nic nie psuje.

### M6. Przełączenie filtrów na obszar (kod, nie dane)
- Wejście: M5 (każda placówka ma obszar). Robi: formularz (v1–v4: endpoint listy
  szkół + `formularz*.js` — wybór obszaru zamiast miasta), `/baza` (filtr
  „Obszar" wchodzi obok „Miejscowość"; „Miejscowość" znika ekran po ekranie,
  nie jednym cięciem), `miejscowosc` w `PLACOWKA_FIELDS` → `text`.
  Testy: `test_formularz.py` i `test_scenariusze.py` rozszerzone o `sprawdz()`
  na filtr obszaru.
- Wyjście: komplet testów zielony; handlowiec na `test` znajduje te same szkoły
  co wczoraj. Odwracalność: revert gałęzi — dane nieruszone.

### M7. Dołożenie brakujących ~714 placówek
- Wejście: M6 na produkcji (inaczej nowe rekordy z czystą miejscowością nie
  wpadną w stare filtry słownikowe). Robi skrypt `migracja_rspo.py doloz`:
  dla każdego wiersza lustra w obszarach, w typach klienta, bez rekordu
  roboczego o tym `rspo` → INSERT do `placowki` (nazwa, miejscowość CZYSTA,
  adres `ulica + nr_budynku` — lepszy niż 504 obecne „sama nazwa ulicy",
  telefon, mail, powiat, gmina, obszar, `zrodlo='rspo'`) + lead ze statusem
  `00. Nieprzydzielony`. Typ z mapowania rejestr→słownik `typ_placowki`
  (`Szkoła podstawowa`→`01.`, `Przedszkole` publiczne→`02.`, niepubliczne→`03.`,
  `Punkt przedszkolny`→`03.` lub nowa pozycja — pkt 9); przy okazji naprawić
  rozjazd `04. Inna` (6 rekordów) z wartościami słownika.
  Najpierw `--podglad` (liczby per obszar i typ, zero zapisu), potem zapis.
- Wyjście: liczba placówek = lokalne + zakres (kontrola: per obszar zgodna
  z rozkładem z analizy — Katowice 225 itd.). Formularz niezalany: domyślny
  widok to obszar + wyszukiwarka (nazwa i `nazwa_potoczna`), a lista „moje
  szkoły" handlowca w ogóle nie rośnie (nowe leady są nieprzydzielone).
- Odwracalność: `DELETE` placówek `zrodlo='rspo'` bez żadnego ruchu
  (bez handlowca, bez eventu, bez loga poza wpisem importu) — to samo ostre
  kryterium, którym policzono 136 nietkniętych.

### M8. Domknięcie geografii
- Wejście: M7 przeżył tydzień na produkcji bez zgłoszeń.
- Robi: `UPDATE placowki SET miejscowosc=` czysta nazwa z lustra (po `rspo`);
  słownik `miasto` → `aktywny=0` (aliasy zostają); rename `rejony` →
  `rejony_trenerow` + przejście na `(rodzaj, wartosc)` z mapowaniem obecnych
  44 wierszy (`01. Orzesze`→gmina `Orzesze`, `08. Katowice`→powiat `Katowice`…)
  — mapowanie jednoznaczne, ale wynik pokazać Kasi (przy okazji: 19 pozycji
  bez trenera i 6 osób spoza słownika ze stanu 09.08).
- Wyjście: zero wartości z prefiksem w `placowki.miejscowosc`; podpowiedź
  „jeździ tu" działa po nowej geografii. Odwracalność: kopia + `log`.

### M9. Ekran koordynatora „Rejestr RSPO" (comiesięczny rytm)
- Wejście: M1–M8 zamknięte. Robi: przeniesienie toru `magazyn.wgraj()` do
  aplikacji jako ekran (wgraj plik → raport nowe/zmienione/zniknęły →
  zatwierdź), zgodnie z planem z `12_RSPO.md` („po sprawdzeniu skrypt staje
  się ekranem"). Zniknięte z rejestru: `nieobecna_od` w lustrze + plakietka
  na powiązanej placówce roboczej — **ostrzeżenie, nie blokada** (placówka
  mogła się przekształcić, wisi na niej historia). Nowe w obszarach: sekcja
  „w rejestrze doszło N placówek z Twoich obszarów" z przyciskiem „dołóż" —
  ten sam kod co M7.
- To zamyka pytanie „czy da się wgrać całe RSPO śląskie": tak, całe śląskie
  siedzi w lustrze od M1, a do bazy roboczej wchodzi tylko przecięcie
  z obszarami — resztę widać jako rezerwę do rozszerzeń.

---

## 5. Scalanie 18 par dubli

### Reguła

**Zostaje rekord, który dostaje numer RSPO** (w praktyce: pełnonazwowy — to on
dopasowuje się do rejestru). Z rekordu kasowanego przenosi się WSZYSTKO:

| co | jak |
|---|---|
| eventy | `UPDATE eventy SET lead_id = <docelowy>` — **przed czymkolwiek innym**: `ON DELETE CASCADE` na łańcuchu placówka→lead→event skasowałby DT bez śladu. W 16 z 18 par jedyne DT wisi właśnie na rekordzie skróconym |
| log | `UPDATE log SET lead_id = <docelowy>` (analogicznie `event_id` zostaje — eventy przeżywają) |
| pola leada (status, dt, cykle, deadline, do_zrobienia, pola Julii…) | per pole: niepuste wygrywa nad pustym; **dwa niepuste różne → decyzja człowieka w pliku** (kolumna „konflikt"). Reguła jest symetryczna, więc para 419/537 (DT na pełnym, odwrotnie niż reszta) nie wymaga wyjątku |
| uwagi / do_zrobienia przy dwóch niepustych | sklejenie z separatorem `— [scalone z: MSP 1] —`, nie wybór |
| telefon/mail/kontakt placówki | niepuste wygrywa; konflikt → człowiek (zdarzy się rzadko: w tych parach kontakty siedzą na rekordzie pełnym) |
| nazwa skrócona | do `nazwa_potoczna` rekordu docelowego — skrót handlowca nie ginie z wyszukiwarki |
| rekord skrócony po przeniesieniu | `DELETE` — ale dopiero po wpisie do `log` na rekordzie docelowym: `co='scalenie'`, `przed`=pełny JSON kasowanego wiersza placówki i leada. Razem z kopią z M0/M4 to daje odtwarzalność w praktyce |

### Automat czy ekran — rozstrzygnięcie: skrypt + plik do zatwierdzenia

Skrypt `narzedzia/migracja_rspo.py scal --plik pary.xlsx` działający wyłącznie
na parach zatwierdzonych w pliku (kolumna „zatwierdzone: TAK" wypełnia Kasia;
konflikty pól rozstrzygnięte w osobnych kolumnach). NIE budujemy ekranu:
operacja jest jednorazowa na 18 par + drugi przebieg po M8, a ekran to dzień
pracy z walidacją i uprawnieniami. Konwencja projektu mówi wprost: ekranem
zostaje to, co ma być używane regularnie — scalanie regularne nie będzie,
bo UNIQUE na `rspo` i dopasowywanie po numerze nie pozwolą dubli tworzyć.

### Drugi przebieg — duble „geograficzne"

Po M5 rekordy `541 Sp`/Strzyżowice, `542 Zsp`/Psary, `543 Sp 1`/Wola (dziś
osobne „miasta" w słowniku) dostaną numery RSPO i część z nich wskaże szkoły,
które M7 i tak by dołożył — czyli dubli nie będzie, bo M7 pomija zajęte numery.
Ale jeśli któryś z nich NIE dostanie numeru w M3 (nazwa zbyt skąpa — `Sp`),
a M7 doda pełny rekord z rejestru, powstanie para stary-lokalny / nowy-z-rejestru.
Dlatego po M7 skrypt `dopasuj` przechodzi jeszcze raz po rekordach bez `rspo`
i raportuje kandydatów — ten sam plik decyzyjny, ta sama reguła scalenia.

---

## 6. Dołożenie brakujących placówek — rozstrzygnięcia szczegółowe

- **Przedszkola (710 + ewentualnie 23 punkty): wchodzą.** Firma prowadzi
  zajęcia przedszkolne (typ eventu `CYKLICZNE-PRZEDSZKOLE`, słownik
  `typ_placowki` ma pozycje 02/03 od początku — puste do dziś, bo plik klienta
  ich nie zawierał, nie dlatego, że są niepotrzebne). To podwaja bazę, ale
  handlowca chroni domyślny filtr obszaru + jawny chip typu placówki na
  `/baza` (wzorzec „przypięty, ale zdejmowalny" — plakietka mówi, że filtr
  działa). Lista „moje szkoły" i „plan na dziś" nie rosną ani o wiersz.
- **Zespoły**: bez rekordów roboczych dla `jednostka złożona` (pkt 1.4).
- **Dane przy dokładaniu**: telefon/mail z rejestru (1 258 z 1 259 je ma),
  `liczba_uczniow` i `organ_nazwa` zostają w lustrze — karta placówki pokaże
  je JOIN-em, bez poszerzania tabeli roboczej (podpowiedź „ten sam organ
  prowadzi szkołę, którą już mamy" to przyszły ekran, nie kolumna).
- **Kolejność**: najpierw `test` → demo-ph → tydzień obserwacji → prod.
  Baza produkcyjna zmienia się gotowym, sprawdzonym skryptem — nie ekranem
  Import na serwerze (lekcja z 10.08 zostaje w mocy).

---

## 7. Rozszerzalność — „wchodzimy do Bytomia" / „cały powiat gliwicki"

Rozszerzenie NIE wymaga zmiany kodu ani nowego pliku rejestru — całe śląskie
już siedzi w lustrze:

1. **Bytom**: koordynatorka na `/obszary` dodaje powiat `Bytom` →
   `obszary.przelicz()` → ekran pokazuje „w lustrze jest N placówek Bytomia
   w Twoich typach" → przycisk „dołóż do bazy" (kod M7) tworzy rekordy robocze
   + nieprzydzielone leady. Odwracalne tak samo jak M7.
2. **Cały powiat gliwicki**: dodanie powiatu `gliwicki`. Knurów (gmina) już
   jest — reguła gmina-bije-powiat sprawia, że placówki Knurowa zachowują
   `obszar='Knurów'` (etykieta, do której zespół przywykł), a reszta powiatu
   dostaje `obszar='gliwicki'`. Dubli nie będzie: „dołóż" pomija numery RSPO
   już obecne w `placowki` (UNIQUE pilnuje tego także na poziomie bazy).
3. **Nowe województwo** (kiedyś): jedyna zmiana to zdjęcie zawężenia do
   `ŚLĄSKIE` przy wgrywaniu lustra — model obszarów nie zna pojęcia
   „województwo domyślne" poza importem.

---

## 8. Ryzyka i czego NIE WOLNO

Miejsca, gdzie praca handlowców ginie nieodwracalnie, i zapory:

1. **`ON DELETE CASCADE`** placówka→lead→event: skasowanie placówki „dubla"
   przed przepięciem eventów kasuje DT bez śladu. Zapora: kolejność w skrypcie
   scalania (eventy → log → pola → dopiero DELETE) + test `sprawdz()` na
   licznik eventów PRZED==PO.
2. **`UPDATE miejscowosc` przed przełączeniem filtrów** (M8 przed M6): szkoła
   znika handlowcowi z formularza — „aplikacja pogubiła rekordy". Zapora:
   twarda kolejność etapów; skrypt M8 odmawia, gdy w kodzie nadal jest
   `slownik:miasto` w `PLACOWKA_FIELDS` (ten sam wzorzec co odmowa
   `baza.py` przy nie tej bazie).
3. **Import lustra w tryb roboczy**: NIE WOLNO wgrywać pliku RSPO ekranem
   „Import" aplikacji (trafiłby do `placowki` z polityką „człowiek wygrywa"
   i osieroconą geografią). Lustro ma własny, osobny tor.
4. **Nadpisanie ręcznych poprawek rejestrem**: w `placowki` rejestr NIGDY nie
   nadpisuje niepustego telefonu/maila/kontaktu (uzupełnia puste). W lustrze
   odwrotnie — i właśnie dlatego to są dwie tabele.
5. **Automatyczne wpisywanie numerów przy rozjeździe źródeł** (raport mówi X,
   plik klienta Y): NIE WOLNO — złe powiązanie znaczy, że comiesięczne
   odświeżenie będzie latami „poprawiać" nie tę szkołę. Rozjazd zawsze do
   człowieka (w M3 to maks. kilkadziesiąt wierszy).
6. **Kasowanie „nadmiarowych" rekordów lokalnych** (EduHub, `29.0`, sieroty
   bloku 517–545): NIE WOLNO kasować niczego, co ma event albo wpis człowieka
   w logu. Sierota bez odpowiednika w rejestrze zostaje rekordem lokalnym
   z `rspo=NULL` — model tego nie zabrania (częściowy UNIQUE).
7. **Zniknięcia z rejestru**: eksport RSPO nie ma dat likwidacji (kolumna
   pusta w 56 190 wierszach) — zamknięcie szkoły widać TYLKO porównaniem
   zbiorów między wgraniami. Dlatego bezpiecznik wycinka z `magazyn.py` jest
   obowiązkowy: plik „tylko Katowice" wyglądałby jak likwidacja 96% placówek.
8. **Prod w godzinach pracy**: M4–M8 wyłącznie poza godzinami pracy handlowców,
   każdy z kopią PRZED (po starcie nowej wersji jest za późno — lekcja
   z `wdroz.sh`).
9. **Kopie z danymi osobowymi**: pliki decyzyjne M3/M4 zawierają telefony
   i nazwiska — trzymać w `SIERPIEN2026\_KOPIE_PLIKOW_KLIENTA` /
   `docs/poprawka …` tylko lokalnie; NIE commitować do publicznego repo
   (repo jest publiczne do końca rundy poprawek!).

---

## 9. Otwarte decyzje dla klienta

| # | pytanie | do kogo | rekomendacja |
|---|---|---|---|
| 1 | Zespoły: rekord roboczy na każdą jednostkę składową (SP + każde przedszkole osobno), czy jeden na zespół? | Kasia | składowe osobno — przedszkole w zespole to osobna sprzedaż i osobne cykle; przynależność do zespołu widać na karcie |
| 2 | Punkty przedszkolne (23 w zakresie) — dokładać? | Kasia | tak — ten sam produkt co przedszkola; to 23 wiersze, nie zalew |
| 3 | Książenice (id 528, u nas pod „Rybnik") leżą w powiecie **rybnickim** (gmina Czerwionka-Leszczyny), którego wg deklaracji NIE obsługujecie. Dołożyć gminę Czerwionka-Leszczyny do obszarów, czy oznaczyć szkołę „poza obszarem"? | Kasia | skoro szkoła jest w bazie z pracą — dodać gminę (samą gminę, nie powiat; dokładnie po to model ma poziom gminy) |
| 4 | Nazwy placówek po nadaniu numerów: przyjąć pełne nazwy z rejestru (skróty handlowców zostają w `nazwa_potoczna` i w wyszukiwarce)? | Kasia | tak — to rozwiązuje jej własne zgłoszenie z 09.08 o rozjeździe nazw; skrót nie ginie |
| 5 | Prefiksy `01. `: obszary bez prefiksów (kolejność trzyma `kolejnosc`, listy sortują się jak dotąd) — czy sortowanie w eksportach Excela bez prefiksu wystarczy? | Kasia | bez prefiksów — wymóg „takie same jak w RSPO" jest ważniejszy; w razie potrzeby eksport może dokładać prefiks w locie |
| 6 | Sieroty bloku 517–545 bez odpowiednika w rejestrze (`SP 5` bez miejscowości, `29.0`, `Zając Poziomka`, `EduHub`): dopasować ręcznie / zostawić jako lokalne / skasować (tylko te bez ruchu)? | Kasia | jednorazowa przejrzenie z Kasią przy pliku M3 — na części wiszą DT, więc kasowanie tylko dla ewidentnych pomyłek bez ruchu (`29.0` wygląda na błąd wiersza) |
| 7 | Czy handlowiec w `/baza` domyślnie widzi też przedszkola (podwaja listę), czy domyślny chip „szkoły" (zdejmowalny, jawny)? | Kasia + handlowcy | domyślnie wszystko z obszaru, jawny chip typu — ukryty filtr to zgłoszenie „zniknęły rekordy" |
| 8 | Zakres lustra: całe śląskie (6 116) — potwierdzenie decyzji z `12_RSPO.md` pkt 4 (Wojtek chciał „całą bazę") | Wojtek | tak — lustro nic nie kosztuje, a rozszerzenia (pkt 7) działają bez nowych plików |
| 9 | Termin okna na M4–M8 na produkcji (wieczór/weekend) + kto zatwierdza pliki M3/M4 | Kasia + Przemek | pliki zatwierdza Kasia (zna teren), wykonanie poza godzinami pracy handlowców |

---

## Aneks: mapa zmian w kodzie (do wyceny, nie do wykonania teraz)

| plik | zmiana | etap |
|---|---|---|
| `db.py` | tabele `rspo_rejestr`/`rspo_importy`/`rspo_zmiany`/`obszary_dzialania`; kolumny `powiat`,`gmina`,`obszar`,`nazwa_potoczna` w `migruj()`; `PLACOWKA_KOLUMNY_GEOGRAFIA` poza `PLACOWKA_FIELDS`; `miejscowosc` → `text` | M1/M2/M6 |
| nowy `obszary.py` | `przelicz()`, `lista()`, `dodaj/usun` — logika przejęta z `rspo_app/rejony.py` | M2 |
| nowy `rejestr_rspo.py` (albo rozbudowa `narzedzia/rspo.py` → moduł) | `wgraj()` z dziennikiem i bezpiecznikiem — z `rspo_app/magazyn.py` + `plik.py` | M1/M9 |
| nowy `narzedzia/migracja_rspo.py` | `dopasuj` / `wpisz` / `scal` / `doloz` (+`--podglad`) | M3–M7 |
| `przydzial.py` | rename `rejony`→`rejony_trenerow`, przejście na `(rodzaj, wartosc)` | M8 |
| `app.py` | trasy `/obszary`, `/rejony-trenerow`, `/rejestr-rspo`; filtr obszaru w `/baza` i endpointach formularza | M6/M8/M9 |
| `filtry.py`, `repo.py` | oś `obszar` obok (potem zamiast) `miejscowosc` | M6 |
| `static/formularz*.js` (4 warianty) | wybór obszaru zamiast miasta; wyszukiwarka po `nazwa_potoczna`; nowa placówka: miejscowość tekstem + podpowiedź obszaru z lustra | M6 |
| szablony: `obszary.html`, `rejony_trenerow.html` (rename), `baza.html`, `lead.html` (dopisek „w zespole: …") | j.w. | M6–M9 |
| testy | nowy `test_obszary.py` + `test_migracja_rspo.py` (konwencja `sprawdz()`, własna tymczasowa baza); rozszerzenia `test_formularz.py`, `test_scenariusze.py` | każdy etap |
