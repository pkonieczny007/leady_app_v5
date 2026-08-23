# PLAN — „PH bazy": zakładki widoku handlowca + problem telefonu

Rozpracowanie uwagi Kasi z 23.08 (`POPRAWKA_FORMULARZA/poprawka_dzialania_filtrow`).
Analiza i projekt — bez zmian w kodzie. Liczby policzone na bazie **prod**
(tylko odczyt, stan 23.08.2026): 545 leadów, 398 przypisanych, 147 w puli.

**Najważniejsze odkrycie na wstępie:** większość zakładek, o które prosi Kasia,
JUŻ ISTNIEJE na ekranie `/leady` (`templates/leady.html`, wiersze 26–35):
„W pracy" / „DT umówione" / „Po terminie" / „Z cyklami" jako segmenty `zakres=`.
Uwaga Kasi to więc w połowie prośba o **doprecyzowanie znaczeń** (co dokładnie
znaczy „w pracy", żeby „po terminie" nie znikało), a w połowie o **dwie nowe
zakładki** (cała moja baza, jednorazówki/VR). To dobra wiadomość: wzorzec
(`zakres` w `repo._warunki`, segmenty w szablonie, filtr „mój" przypięty przez
obecność parametru `handlowiec` w URL) jest gotowy i przetestowany — dokładamy
gałęzie, nie budujemy ekranu.

---

## 1. Mapowanie: zakładka Kasi → warunek SQL

Wszystkie warunki działają w `repo._warunki()` jako nowe/zmienione gałęzie
`zakres`, W POŁĄCZENIU z filtrem `l.handlowiec = :ja` (przypiętym, zdejmowalnym
— sekcja „Filtr mój" w CLAUDE.md). Prefiksy statusów wg słownika w prod:
`00, 00b, 01, 02, 02b, 03, 03b, 03c, 04` (trzy warianty 04).

### 1a. „W pracy" — DOPRECYZOWANIE istniejącego

Dziś zakładka „W pracy" to `zakres=przydzielone`:
`handlowiec niepusty AND status NOT LIKE '04%'` — czyli **łącznie z 03. DT
umówione** (383 leady na prod). Kasia wymienia: „umówione spotkanie, zaplanowane
spotkanie, rozmowy w toku, doprecyzuj szczegóły" — i osobno zakładkę „DT
umówione". Wniosek: „w pracy" = *jest u mnie i jeszcze nie ma efektu*.

Proponowany nowy zakres `w_pracy`:
```sql
l.handlowiec IS NOT NULL AND l.handlowiec <> ''
AND (l.status_realizacji IS NULL
     OR (l.status_realizacji NOT LIKE '03.%'      -- sukces ma swoją zakładkę
         AND l.status_realizacji NOT LIKE '04%')) -- odpadłe mają Niewykorzystane
```
Na prod dziś: **325** (305 × `01.`, 20 × `02.`; statusy `00b./02b.` istnieją
w słowniku, ale mają 0 leadów).

Mapowanie słów Kasi na słownik:
- „rozmowy w toku" → `01. Próba kontaktu (Brak konkretów)` + `02. …(czekam na termin)`
- „doprecyzuj szczegóły" → `02b. DT w trakcie umawiania`
- „umówione/zaplanowane spotkanie" → najbliżej `02b.` — w słowniku NIE MA statusu
  „spotkanie handlowca umówione" (pytanie P2). Nowy status, gdyby zapadł, wchodzi
  przez `narzedzia/statusy.py`, bez zmian w tym filtrze (prefiks `02` łapie go sam).

Rozstrzygnięcie w zawieszeniu: czy `03c. Grupa się nie otworzyła` wraca do
„w pracy" (szkoła znów do obdzwonienia?) — pytanie P1. Warunek powyżej
zostawia ją w „w pracy" tylko, jeśli zapiszemy `NOT LIKE '03.%'` (łapie wyłącznie
`03. DT umówione` — `03b./03c.` mają inny prefiks, `'03b.' NOT LIKE '03.%'`).

### 1b. „Cała moja baza" — NOWA zakładka (jedyna naprawdę prosta)

„Wszystko co przydzielił koordynator". To po prostu `handlowiec = :ja`
**bez żadnego warunku na status**:
```sql
l.handlowiec IS NOT NULL AND l.handlowiec <> ''   -- zakres 'moja_baza'
```
(z przypiętym `handlowiec=ja` daje „moje wszystko"). Nie trzeba nawet nowego
zakresu — `zakres=wszystkie` + filtr handlowca robi to samo — ale osobna nazwa
`moja_baza` jest czytelniejsza w URL i pozwala na własną etykietę segmentu.
Na prod: Sacawa 170, Olszewska 97, Chytry 71, Małolepsza 43, Młynarczyk 17.

Uwaga spójności: po auto-zwrocie lead znika z tej listy (handlowiec = NULL) —
dokładnie tak, jak chce Kasia („po terminie spadają z listy cała moja baza").
To już działa samo z siebie.

### 1c. „DT umówione" — ISTNIEJE, jedno rozstrzygnięcie

Dziś `zakres=umowione` = `status_realizacji LIKE '03.%'` → **58** na prod.
Alternatywa „po faktach": istnieje nieodwołany event DT z datą → **63** eventy DT.
Rozbieżność 58 vs 63 jest prawdziwa (leady z wpisem DT w kalendarzu, ale statusem
innym niż 03 — m.in. po odwołaniach i imporcie; w danych klienta status bywał
nieaktualny, patrz komentarz w `zwrot.py`).

**Rozstrzygnięcie: zostawić definicję STATUSOWĄ.** Kasia steruje procesem przez
status (to jej słownik, ona po nim sortuje), a auto-zwrot już dziś traktuje status
i „fakty z kalendarza" jako dwa osobne bezpieczniki. Zakładka ma pokazywać to,
co handlowiec zadeklarował; rozjazd status↔kalendarz to temat na osobną plakietkę
ostrzegawczą (poza zakresem tej poprawki).

### 1d. „Jednorazówki/VR umówione" — NOWA zakładka, słownik JEST, danych brak

Słownik `typ_eventu` w prod: `CYKLICZNE, DT, FESTYN, JEDNORAZÓWKA, START, VR` —
czyli typy **istnieją** i formularz może je zapisywać. W kodzie jest tylko stała
`TYPY_CYKLICZNE = ("CYKLICZNE", "CYKLICZNE-PRZEDSZKOLE")` (`db.py:190`);
odpowiednika dla jednorazówek nie ma. W prod dziś **0 eventów** typu
JEDNORAZÓWKA/VR/FESTYN/START (są tylko 63 DT + 2 CYKLICZNE) — zakładka na start
będzie pusta, co się zgadza z „może się przydać".

Proponowany zakres `jednorazowki` + stała w `db.py` (jedno miejsce, jak przy
cyklach — ta sama lekcja z 10.08):
```python
TYPY_JEDNORAZOWE = ("JEDNORAZÓWKA", "VR", "FESTYN")   # START = start cyklu, nie tu
```
```sql
EXISTS (SELECT 1 FROM eventy e WHERE e.lead_id = l.id
        AND e.typ IN ('JEDNORAZÓWKA','VR','FESTYN')
        AND (e.odwolane IS NULL OR e.odwolane = ''))
```
Skład listy do potwierdzenia (P5). Przy okazji dwa znaleziska poboczne:
- zakres `cykle` w `repo.py:217-219` NIE wyklucza eventów odwołanych (licznik
  `n_cykl` w `BAZOWY_SELECT` wyklucza) — ta sama klasa usterki co P08, poprawić
  przy okazji;
- w słowniku `typ_eventu` na **prod nie ma** `CYKLICZNE-PRZEDSZKOLE`, choć stała
  w kodzie już je zna (P26 doszedł na gałęzi) — sprawdzić przy wdrożeniu rundy.

### 1e. „Po terminie" — ISTNIEJE, ale dla handlowca jest MARTWE (pułapka)

Dziś `zakres=po_terminie` = `deadline < dziś AND status NOT LIKE '03.%'`.
Problem: auto-zwrot (`zwrot.py`, KARENCJA_DNI=0, przebieg co ≤60 min ruchu)
czyści **i handlowca, i deadline**. Czyli lead „po terminie" jest widoczny
najwyżej ~godzinę–dzień, a po zwrocie filtr nie ma na czym stanąć: ani
`handlowiec`, ani `deadline` już nie istnieją. Na prod „po terminie" pokazuje
dziś 4 leady — to wyjątki, których automat nie rusza (mają DT w kalendarzu).
Rozstrzygnięcie „historia zostaje" — cała sekcja 2.

### 1f. „Z cyklami — to zostaje" — ISTNIEJE

`zakres=cykle` zostaje bez zmian znaczenia (plus poprawka `odwolane` z 1d).
Auto-zwrot i tak nie rusza leadów z DT w kalendarzu, a status `03.` chroni przed
zwrotem — szkoły z cyklami nie „spadają", zgodnie z życzeniem.

### Proponowany komplet segmentów na `/leady`

| Segment | zakres | Warunek (skrót) | Dziś na prod |
|---|---|---|---|
| W pracy | `w_pracy` (nowy) | przydzielone − 03. − 04 | 325 |
| Cała moja baza | `moja_baza` (nowy) | handlowiec niepusty | 398 |
| DT umówione | `umowione` (jest) | status LIKE '03.%' | 58 |
| Jednorazówki/VR | `jednorazowki` (nowy) | event typu jednorazowego | 0 |
| Po terminie | `po_terminie` (przerobiony) | sekcja 2 | 4 + 11 z historii |
| Z cyklami | `cykle` (jest) | event cykliczny | ~2 |

Linki segmentów przenoszą `f.handlowiec` tak jak dziś (`href_zakres(...,
f.handlowiec)`) — wzorzec „obecność parametru rozstrzyga" zostaje nietknięty.

---

## 2. „Po terminie z historią" — rozstrzygnięcie

### Co dokładnie zapisuje zwrot

`zwrot.wykonaj()` (`zwrot.py:139-159`) przy każdym zwrocie robi wpis do `log`:
```
co='auto-zwrot po terminie', pole='handlowiec',
przed=<dotychczasowy handlowiec>, po=NULL, kto='automat'
```
Czyli **informacja „czyj był" JUŻ JEST zapisywana** — w `log.przed`. Na prod
jest 11 takich wpisów (wszystkie z 10.08, wszystkie `przed='02. Olszewska'`).
Analogicznie ręczne odebranie (`/api/odbierz`, `app.py:983`) pisze
`co='odebranie leada'` z `przed=<handlowiec>`.

### Decyzja: czytać z `log`, BEZ nowej kolumny

Rozważane trzy warianty:

1. **Odczyt z `log` w filtrze** (WYBRANY):
   ```sql
   -- zakres 'po_terminie' dla handlowca :ja — suma dwóch przypadków:
   (   l.handlowiec = :ja                      -- jeszcze mój, termin już minął
       AND l.deadline IS NOT NULL AND l.deadline <> '' AND l.deadline < :dzis
       AND (l.status_realizacji IS NULL OR l.status_realizacji NOT LIKE '03.%'))
   OR EXISTS (SELECT 1 FROM log g               -- był mój, automat zabrał
              WHERE g.lead_id = l.id
                AND g.co = 'auto-zwrot po terminie'
                AND g.przed = :ja)
   ```
2. Nowa kolumna `byl_handlowiec` zapisywana w momencie zwrotu — odrzucona:
   wymaga migracji schematu i backfillu… właśnie z `log`, czyli log i tak jest
   źródłem; trzecia kopia tej samej informacji to prosta droga do rozjazdu
   (dokładnie problem „wiersz w trzech zakładkach" z arkusza klienta).
3. Nie czyścić `handlowiec` przy zwrocie, tylko flagować — odrzucona: rozbiłaby
   całą semantykę puli (`nieprzydzielone` = pusty handlowiec) i auto-zwrot,
   które działają i są przetestowane.

Uzasadnienie wyboru 1: zero zmian schematu, dane historyczne od 10.08 już
istnieją, jedna prawda. Koszt wydajnościowy pomijalny — `log` ma dziś 13 wpisów,
a podzapytanie działa per lead na stronie (150). Gdyby log urósł do dziesiątek
tysięcy, wystarczy indeks `log(lead_id, co)` — odnotować, nie robić na zapas.

### Pułapka implementacyjna (ważna!)

Warunek `l.handlowiec = :ja` z filtra „mój" jest dziś dokładany NIEZALEŻNIE od
zakresu (`repo._warunki`, linia 175-176) i łączony przez `AND`. Dla zwróconego
leada `handlowiec IS NULL`, więc **zwykłe dołożenie gałęzi `EXISTS(log…)` do
zakresu nic nie da — filtr handlowca i tak go zetnie**. Implementacja musi przy
`zakres='po_terminie'` + niepustym `f["handlowiec"]` zbudować jeden wspólny
nawias (jak w SQL wyżej), zamiast dwóch niezależnych warunków. To jedyne
miejsce, gdzie zakres i filtr osoby muszą się widzieć — zasługuje na komentarz
w kodzie i osobny test.

### Prezentacja

Wiersz „z historii" nie jest zwykłym leadem handlowca: pokazać plakietkę
w stylu istniejącej „wróciła do puli" z `/baza` (`app.py:538-552` — mechanizm
odczytu ostatniego wpisu logu już jest!): *„wróciła do puli 10.08 · teraz:
nieprzydzielona / u 03. Małolepsza"*. Edycja takiego wiersza przez byłego
właściciela ma zostać zablokowana tak, jak dziś dla cudzych leadów (kontrola
właściciela w endpointach zapisu istnieje — nic nowego do napisania, tylko test,
że działa też tutaj).

Kasia mówi też „tyle miał przyznanych, a nie dał rady" — to zapowiedź metryki
dla koordynatora. Tanio: licznik `auto-zwroty` per handlowiec w `per_handlowiec()`
na pulpicie (z tego samego loga). Zaproponować, nie rozbudowywać na zapas.

---

## 3. „Szkoły pozaznaczane do PH" w pliku klienta — co znalazłem

Plik: `_KOPIE_PLIKOW_KLIENTA\2026-08-09\PH PRÓBA Nowy dla handlowców.xlsx`.

**Zaznaczenia siedzą w zakładce `Baza szkół Śląskie`, w kolumnie A `Handlowiec`**
— 544 wiersze placówek, z czego **360 ma wpisanego handlowca**:
157 × `01. Sacawa`, 105 × `02. Olszewska`, 43 × `03. Małolepsza`,
39 × `04. Chytry`, 15 × `Julia` (alias → `05. Młynarczyk`), 1 × `Bitner` (?!).
Zakładki per-handlowiec (`Sacawa` 81, `Olszewska` 53, `Chytry` 48, `Małolepsza` 0,
`Młynarczyk` 240 wierszy) to widoki/formuły z tej samej kolumny — „odpowiednim
arkuszem" z uwagi Kasi jest kolumna Handlowiec w bazie, nie osobna lista.

**Porównanie z prod (dopasowanie po mieście+nazwie, z aliasami Julia→Młynarczyk
i Olaszewska→Olszewska):** z 360 zaznaczeń —

- **345 już jest w bazie prod, zgodnie z plikiem** — bo importer przeniósł
  kolumnę Handlowiec przy budowie bazy 09–10.08. **„Zaczytanie" w ~96% już się
  wydarzyło. Nie robić drugiego importu** (tryb „replace" na prod to ryzyko,
  a nic nowego by nie wniósł);
- **9 różnic**: 8 szkół (7 × Olszewska, 1 × Chytry) jest dziś w puli
  nieprzydzielonych — to skutek **auto-zwrotu z 10.08** (11 wpisów w logu), nie
  błąd importu; 1 szkoła (SP 32 Katowice) ma w pliku `Bitner` — to nazwisko ze
  słownika TRENERÓW, w prod przypisana `05. Młynarczyk`;
- **5 placówek z pliku nie ma w prod w ogóle** (m.in. SP 1 Katowice,
  Prywatna SP 1 Sosnowiec, SP 1 Mikołów, 2 szkoły z powiatu pszczyńskiego);
- 1 nazwa niejednoznaczna (ta sama nazwa w dwóch miastach) — do ręcznego rzutu okiem.

Do zrobienia jest więc nie import, tylko **krótka lista decyzji dla Kasi**
(sekcja 6, P6-P7): czy 8 zwróconych szkół przydzielić ponownie (przycisk
„Przypisz" na `/baza` — istnieje), kto naprawdę prowadzi SP 32 Katowice,
i czy dopisywać 5 brakujących placówek teraz, czy razem z migracją RSPO
(rekomendacja: z RSPO — tam klucz to numer RSPO i dopisanie ręczne teraz
stworzyłoby kandydatów na duble).

---

## 4. Telefon: „nie da się zmniejszyć obrazu" — diagnoza i poprawka

### Diagnoza

**Meta viewport jest NIEWINNA** — `templates/base.html:5`:
`width=device-width,initial-scale=1,viewport-fit=cover`. Nie ma ani
`user-scalable=no`, ani `maximum-scale=1`, więc jednolinijkowa poprawka
„odblokować zoom w meta" tu **nie istnieje — nie ma czego odblokować**.
Przybliżanie (pinch-in) działa.

Prawdziwa przyczyna to skutek uboczny naprawy z 10.08. Wtedy tabele dostały
własne przewijanie (`.table-scroll{overflow:auto}` — `style.css:479` — oraz
`@media (max-width:700px){.table{display:block;overflow-x:auto}}` —
`style.css:292-293`), żeby szeroka tabela nie wypychała całego `body` w bok.
Zrobiono: nawigacja w jednym przewijanym wierszu + tabele przewijane w sobie.
**NIE zrobiono: żadnej redukcji samej tabeli** — tabela leadów na `/leady` ma
16 kolumn i ~1560 px szerokości, czyli na ekranie 375 px ~4 „ekrany" w poziomie.

A przeglądarka mobilna **nie pozwala oddalić strony poniżej jej szerokości
układu**: skoro strona (po poprawce z 10.08) jest szeroka dokładnie na ekran,
minimalny zoom = 100% i pinch-out nie robi nic — szerokość siedzi ukryta
WEWNĄTRZ kontenera przewijania, gdzie zoom nie sięga. Przed 10.08 dało się
oddalić właśnie dlatego, że strona była zepsuta (szeroki body). Kasia opisuje
ten stan bezbłędnie: „nie da się zmniejszyć, widok trzeba przesuwać".

### Proponowana poprawka (dwustopniowa)

1. **S — przełącznik „Pomniejsz" nad tabelą** (dosłownie to, o co prosi Kasia):
   przycisk przełącza na kontenerze klasę z `zoom: 0.7` (+ ciaśniejszy padding);
   stan w `localStorage`. CSS `zoom` działa w Chrome/Safari/Firefox (od 2024)
   — bez bibliotek, zgodnie z konwencją projektu. Kilka linii CSS + delegowany
   nasłuch. To NIE jest pinch-zoom, ale daje ten sam efekt: więcej kolumn na oku.
2. **M — mobilny zestaw kolumn**: na <700 px domyślnie ukryć kolumny
   niskiej wartości w terenie (uwagi, klasy, dzieci, kolumny Julii), zostawić
   placówka / miejscowość / status / termin / data DT; przełącznik „wszystkie
   kolumny" dla nieufnych. Tu jest 80% zysku, ale wymaga decyzji, które kolumny
   są „terenowe" (P8).

Świadomie odrzucone: powrót do szerokiego `body` (przywróciłby błąd z 10.08 —
w bok jeździłby cały ekran z nagłówkiem); pełny widok kart (L, po sezonie —
najpierw sprawdzić, czy 1+2 wystarczą).

---

## 5. Zadania w kolejności

| # | Zadanie | Rozmiar | Zależy od |
|---|---|---|---|
| Z1 | Zakładka „Cała moja baza" (`zakres=moja_baza`) + segment | **S** | nic |
| Z2 | Zakres `w_pracy` + podmiana segmentu „W pracy" | **S** | P1/P2 (definicja) |
| Z3 | „Po terminie z historią": wspólny nawias zakres+handlowiec, odczyt z `log`, plakietka „wróciła … teraz u …", test na pułapkę z 2. | **M** | P3/P4 |
| Z4 | Zakres `jednorazowki` + stała `TYPY_JEDNORAZOWE` w `db.py`; przy okazji poprawić `cykle` o `odwolane` i sprawdzić brak `CYKLICZNE-PRZEDSZKOLE` w słowniku prod | **S** | P5 |
| Z5 | Telefon 1: przycisk „Pomniejsz" (CSS zoom + localStorage) | **S** | nic |
| Z6 | Telefon 2: mobilny zestaw kolumn + „wszystkie kolumny" | **M** | P8, po Z5 |
| Z7 | Lista decyzyjna dla Kasi: 8 zwróconych szkół, SP 32 Katowice (Bitner), 1 niejednoznaczna nazwa — do klików na `/baza`, bez kodu | **S** | P6 |
| Z8 | Dopisanie 5 placówek brakujących w prod | **S** | **migracja RSPO** (P7) — jedyne zadanie, które na nią czeka |
| Z9 | (opcja) licznik auto-zwrotów per handlowiec na pulpicie | **S** | Z3 |

Nic z Z1–Z7 nie czeka na RSPO. Kolejność Z1→Z5 daje Kasi widoczny efekt przy
minimalnym ryzyku; Z3 jest najdelikatniejsze (jedyne miejsce, gdzie zakres musi
zobaczyć filtr osoby) i powinno iść osobnym commitem z własnym testem.

---

## 6. Pytania do Kasi (z rekomendacjami)

- **P1 — „W pracy":** czy to statusy 00b/01/02/02b (bez „03. DT umówione",
  które ma własną zakładkę)? I czy `03c. Grupa się nie otworzyła` ma wracać do
  „w pracy" jako szkoła do ponownego obdzwonienia? *Rekomendacja: tak jak
  w pytaniu; 03c zostaje poza „w pracy" (widać ją w „Cała moja baza").*
- **P2 — „umówione/zaplanowane spotkanie":** w słowniku nie ma takiego statusu —
  czy `02b. DT w trakcie umawiania` to pokrywa, czy dodać nowy status (przez
  `narzedzia/statusy.py`)? *Rekomendacja: bez nowego statusu; 02b wystarcza,
  a filtr po prefiksie `02` i tak go załapie, gdyby doszedł.*
- **P3 — „Po terminie":** liczyć tylko szkoły zabrane przez automat, czy też
  odebrane ręcznie przez koordynatora („odebranie leada" → Niewykorzystane)?
  *Rekomendacja: tylko automat — ręczne odebranie to decyzja koordynatora,
  nie „nie zdążył".*
- **P4 — historia po ponownym przydziale:** gdy zwrócona szkoła trafi do innego
  handlowca, czy u poprzedniego dalej wisi w „Po terminie" (z dopiskiem „teraz
  u X")? *Rekomendacja: tak — historia to historia; wiersz jest tylko do
  odczytu.*
- **P5 — jednorazówki:** czy `FESTYN` liczy się do zakładki „Jednorazówki/VR"?
  (`START` proponujemy wyłączyć — to start cyklu.) *Rekomendacja:
  JEDNORAZÓWKA + VR + FESTYN.*
- **P6 — rozbieżności przydziałów:** 8 szkół z Twojego pliku (7 Olszewska,
  1 Chytry) automat zwrócił do puli 10.08 — przydzielić ponownie tym samym
  osobom? I kto prowadzi SP 32 Katowice — w pliku stoi „Bitner", a to trener,
  nie handlowiec (w bazie: 05. Młynarczyk). *Rekomendacja: decyzja na ekranie
  Baza, przyciskiem „Przypisz" — nie automatem.*
- **P7 — 5 szkół z pliku, których nie ma w bazie:** dopisać teraz ręcznie, czy
  poczekać na bazę RSPO (klucz = numer RSPO, brak ryzyka dubli)? *Rekomendacja:
  z RSPO.*
- **P8 — telefon:** czy przycisk „Pomniejsz" wystarczy na początek, a jeśli
  chować kolumny — które są potrzebne w terenie? *Rekomendacja: start od
  „Pomniejsz"; do schowania proponujemy kolumny Julii, uwagi, klasy, dzieci.*
