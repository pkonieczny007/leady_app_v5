# Projekt: system zarządzania leadami (szkoły) — kontekst i plan

> Dokument przekazania kontekstu do nowego okna. Stan na 16.07.2026.

---

## 1. Sytuacja

Znajomi/klient poprosili o pomoc w uporządkowaniu arkusza, w którym firma szkoleniowa
(zajęcia dla szkół i przedszkoli: DT = dni testowe/pokazowe + zajęcia cykliczne)
zarządza leadami, handlowcami i grafikiem trenerów.

- To **prośba o pomoc**, nie zlecenie → rozwiązanie doraźne **w Google Sheets**.
- Docelowo rozważana własna aplikacja Flask (jest VPS `opxen.xyz`, działa już jedna
  aplikacja Flask do rozliczeń — więc infrastruktura i precedens adopcji istnieją).
- Materiały wejściowe: plik `DT_2025-2026_NOWY_PIEKNY_PLIK.xlsx` (stan obecny)
  + opis wymagań w `.odt` (lista życzeń, napisana językiem użytkownika arkusza).

### Role w firmie

| Rola | Kto (wg opisu / wg pliku) | Co robi |
|---|---|---|
| Koordynator | (autorka opisu) | wgrywa bazę RSPO, przydziela szkoły handlowcom, pilnuje terminów |
| Handlowcy | opis: Sacawa, Olszewska, Małolepsza, Chytry, Młynarczyk<br>plik: Kasia, Zuza, Majka, Chytry, Dominika, Zuzanna | dzwonią do szkół, umawiają DT |
| Julka | — | prowadzi arkusz zbiorczy, ma własne kolumny do ręcznego uzupełniania |
| Trenerzy | Weronika, Maja, Klaudia, Zuzanna, Adam M, Paulina, Natalia M, Mateusz L, Kinga K… | prowadzą DT i zajęcia cykliczne, potrzebują grafiku |

**Uwaga:** role handlowca i trenera są w pliku splątane (te same imiona w obu listach).
Do rozstrzygnięcia przed startem.

---

## 2. Czego chcą (oryginalny opis, streszczony)

### Cykl życia leada
1. **Przypisanie** — koordynator wybiera handlowca z listy rozwijanej w bazie głównej.
   Jedna baza na cały region, filtrowanie po mieście i handlowcu.
2. **Transfer** — lead automatycznie znika z bazy głównej i trafia do arkusza handlowca.
   Filtrowanie po mieście i statusach (umówione DT / brak ruchu).
3. **Sukces** — handlowiec zmienia status na „DT umówione", dane trafiają jednocześnie do:
   arkusza zbiorczego Julki, kalendarza DT, kalendarza zajęć cyklicznych.
4. **Brak efektu** — jeśli nie umówi w terminie, koordynator „odbiera dostęp",
   rekord ląduje w zakładce „niewykorzystane rekordy" i może iść do innego handlowca.

### Moduł RSPO
- Wgranie czystej bazy szkół z rejestru RSPO, przefiltrowanej po miastach regionu.
- Koordynator przypisuje szkołę + wpisuje „ostateczny termin" (datę) na wykonanie ruchu.
- System kontroluje aktywność przed terminem *(sami oznaczyli jako najmniej ważne —
  mogą robić ręcznie)*.
- Brak aktywności po terminie → wiersz znika z widoku handlowca → „niewykorzystane rekordy".

### Wymogi poprzeczne
- **Identyczne listy rozwijane na każdym arkuszu** („generalnie całe tabele są powielone").
- Filtrowanie po mieście / handlowcu / statusie wszędzie („filtrowanie w każdej komórce").
- Kalendarze miesięczne rozpoznawane **automatycznie z daty** („kalendarz wrzesień",
  „kalendarz październik"…), **bez sztywnego kodowania** — muszą działać dla kolejnych miesięcy.

### Zgłoszony bug (ich największy ból)
> „Jeśli trener ma 2 lub więcej spotkań w danym dniu, to nie widzę 2 wpisów w tej dacie
> w kalendarzu DT, a powinnam, bo z tego kalendarza będą korzystali trenerzy."

### Nice-to-have
- Push eventów do Google Calendar każdego trenera („to jest przyszłość — chyba że
  nie zajmie to dużo czasu").
- Plansza „STARTY" — grafik całej firmy, każdy trener swoim kolorem, do zastępstw
  i szybkiej lokalizacji trenera („to już jest Meksyk").

---

## 3. Co realnie jest w pliku (zweryfikowane)

Plik to **eksport z Google Sheets** (sygnatura walidacji `DATEVALUE(...)`, brak nazwanych
zakresów, arkusze „Arkusz31/37/52"). To kluczowe: cała żądana automatyka
to **Apps Script**, nie formuły.

**Skala:** 40 zakładek, ~20 tys. wypełnionych komórek.

**Zero formuł w arkuszach operacyjnych:**

| Zakładka | Wypełnione komórki | Formuły | Walidacje |
|---|---:|---:|---:|
| DT 2025-2026 dograne (główna) | 2457 | **0** | 25 |
| Majka | 1791 | 0 | 0 |
| Chytry BRUDNOPIS | 1577 | 0 | 1 |
| JEDNORAZÓWKI | 3270 | 3006 | 0 |
| PRZEDSZKOLA FAKTURY | 1777 | 519 | 1 |

Wszystko operacyjne jest wklepywane ręcznie. Formuły istnieją tylko w modułach
rozliczeniowych.

### Kolumny arkusza głównego (`DT 2025-2026 dograne`, A1:AU1062)

```
A  (handlowiec — nagłówek pusty, w BRUDNOPISACH: "HANDLOWIEC")
B  TRENER DT
C  KALENDARZ DT (status) → lista: "Komplet wpisany / Zaklepany termin i trener DT- wpisana - do uzupełnienia"
D  KALENDARZ CYKLICZNE → lista: "wpisane / do wpisania"
E  DATA DT
F  NUMER szkoły/przedszkola (SP1, PP30, PM2...)
G  MIASTO
H  ULICA
I  Mail
J  Numer kontaktowy
K  DT ilość klas/dzieci        WZÓR: 10/186          ← ZBITKA
L  GODZINA rozpoczęcia i zakończenia  WZÓR: 08:00-12:30   ← ZBITKA
M  CYKLICZNE data 1 zajęć
N  CYKLICZNE dzień tygodnia   (lista zawiera "Poniedziałek i piątek", "Wtorek i środa")  ← ZBITKA
O  CYKLICZNE godzina  WZÓR: 12:30-14:30, 14:40-15:40   ← ZBITKA
P  CYKLICZNE sala komputerowa/chromebooki
Q  Numer sali
R  UMOWA: czy bez podpisanej umowy możemy rozpocząć zajęcia?
S  Cena wynajmu
T  Czy szkoła wyśle wiadomość przez dziennik
U  BRELOKI (info czy dowiezione)
V  Kto zawiózł breloki
W  CZY JEST WYWIESZONY PLAKAT
X  Mail z inform. o DT
Y  Mail z inform. o cyklicznych
Z  Mail do rodziców na dziennik elektroniczny
AA Mail o jednorazówkach
AB BIURO
AC DRUKARZ / AD PŁYTKARZ / AE TRENER cykliczne
AF Dane do umowy / AG Standardy ochrony małoletnich / AH Oświadczenia trenerów
AI Zaświadczenie o niekaralności / AJ Podanie o wynajem sali / AK Umowa podpisana / AL Librus
```

**Brakuje:** statusu „DT umówione", kolumny „ostateczny termin", kolumny „ostatnia aktywność",
klucza RSPO. Nie ma też zakładek: baza główna RSPO, „niewykorzystane rekordy",
„kalendarz wrzesień/październik". **~60% opisu to greenfield.**

---

## 4. Trzy blokery strukturalne

### 4.1. Brak klucza głównego szkoły

Ta sama szkoła zapisana na cztery sposoby w czterech zakładkach:

| Zakładka | Zapis |
|---|---|
| DT 2025-2026 dograne | `SP11` + `Będzin` (kol. F + G) |
| Chytry BRUDNOPIS | `Sp3 Będzin` — wolny tekst w jednej komórce |
| JEDNORAZÓWKI | `33` (liczba) + `katowice` (małe litery) |
| Katowice PH | `ZSP1 Katowice ul.Sportowa 29` — nazwa+miasto+ulica w jednej komórce |

Bez wspólnego klucza **żaden automatyczny transfer nie zadziała niezawodnie**.
Skoro i tak wchodzi RSPO — **numer RSPO musi zostać kluczem głównym**.

### 4.2. Listy rozwijane wpisane na sztywno i wzajemnie sprzeczne

25 reguł walidacji, każda z listą wklejoną jako **tekst**, w porozrywanych zakresach —
i o **różnej treści w tym samym słupku**:

| Zakres | Lista handlowców |
|---|---|
| `A3:A44` | Dominika, Chytry, Zuzanna |
| `A45:A49` | **Kasia**, Chytry, Zuzanna |
| `A50:A80` | Dominika, Chytry, Zuzanna |
| `A81:A90` | **Kasia**, Chytry, Zuzanna |

To samo w kolumnie trenerów (`B150:B156` zawiera Kingę K, `B3:B30` już nie).
Ich wymóg „listy takie same wszędzie" jest dziś **strukturalnie niemożliwy** do utrzymania.
Lekarstwo: zakładka `SŁOWNIKI` + nazwane zakresy, walidacja przez odwołanie.

### 4.3. Kalendarz jest macierzą, nie zbiorem zdarzeń — źródło ich buga

- `ARCHIWUM -Kalendarz DT LG`: siatka **trener × dzień tygodnia**.
  Jedna komórka = jeden dzień = fizycznie mieści jeden wpis.
- `STARTY CZERWIEC`: kolumny = dni tygodnia, w komórkach bloby tekstu,
  **trener zakodowany kolorem** (nieczytelny maszynowo, brak kolumny z trenerem).

Dopóki kalendarz jest ręcznie malowaną planszą, dubli nie da się zobaczyć — to nie usterka,
to konsekwencja układu danych.

---

## 5. Tłumaczenie ich słów na intencje

Opis jest pisany językiem użytkownika arkusza — opisuje **obecne nawyki**, nie potrzeby.
Trzeba czytać intencje:

| Piszą | Naprawdę znaczy | Rozwiązanie |
|---|---|---|
| „wiersz kopiuje się do 3 miejsc" | 3 osoby muszą widzieć te dane u siebie | jedno źródło + widoki |
| „lead znika z bazy głównej" | koordynator nie chce widzieć obsłużonych na liście do rozdania | status + filtr, **nie** usuwanie |
| „koordynator odbiera dostęp" | lead ma zniknąć z listy roboczej handlowca i wrócić do puli | zmiana statusu, nie uprawnienia |
| „filtrowanie w każdej komórce" | chcą normalnie filtrować | zwykły autofiltr — dostają za darmo |
| „tabele są powielone" | frustracja rozjeżdżającymi się listami | `SŁOWNIKI` + nazwane zakresy |

**Nie wysyłać im opisu rozwiązania — pokazać działającą próbkę** na 15–20 wierszach
i zapytać „czy o to chodziło?". Ich „tak" na czymś, co widzą, jest warte więcej
niż dziesięć rund opisów.

---

## 6. Architektura docelowa (Sheets)

### Filar 1 — dane rozbite na kolumny, sklejanie przez formułę

Ich główny grzech (i zgłoszony problem): pakowanie kilku informacji w jedną komórkę
(`10/186`, `08:00-12:30`, `12:30-14:30, 14:40-15:40`, `Poniedziałek i piątek`).
Z posklejanej komórki nie da się filtrować ani liczyć.

**Kierunek jest nienegocjowalny: wpisują w osobne kolumny, skleja formuła.**

```
Kolumny źródłowe:        data | trener | szkoła | miasto | godz_od | godz_do
Komórka „ładna":         =TEXTJOIN(" | "; PRAWDA; TEKST(A2;"dd.MM"); B2; C2&" "&D2; E2&"-"&F2)
Wynik:                   16.09 | Weronika | SP11 Będzin | 8:00-9:35
```

Zamiast `10/186` → `ilość_klas` (10) i `ilość_dzieci` (186), a wyświetlanie: `=K2&"/"&L2`.
Zamiast `08:00-12:30` → `godz_od` i `godz_do` (typ czas — pozwala liczyć długość, sortować,
wykrywać kolizje trenera).

*(Uwaga: w polskiej lokalizacji Sheets separator argumentów to średnik, `TRUE`→`PRAWDA`,
`TEXT`→`TEKST`. W lokalizacji EN — przecinki.)*

### Filar 2 — trzy pliki zamiast jednego

Ich intuicja „wszystko w jednym pliku to problem" jest słuszna.

| Plik | Kto | Zawartość |
|---|---|---|
| **BAZA** | koordynator (+ Ty) | import RSPO, przypisania, „niewykorzystane rekordy", SŁOWNIKI |
| **PRACA** | handlowcy + Julka | zakładki handlowców, arkusz Julki, `EVENTY` |
| **KALENDARZE** | trenerzy — **tylko odczyt** | generowane kalendarze miesięczne, plansza STARTY |

Zyski: trenerzy nic nie zepsują, plik roboczy przestaje ważyć 2 MB i mulić,
uprawnienia per plik dają namiastkę „odbierania dostępu".
**Granica:** pełnej izolacji handlowca od handlowca w Sheets nie zrobisz — trzeba im to
powiedzieć wprost.

### Filar 3 — jedno źródło prawdy, reszta to widoki

`EVENTY` (1 wiersz = 1 spotkanie) jest źródłem. Kalendarze miesięczne i plansza STARTY
są **generowane** z tej tabeli. Julka dostaje append (jej kolumny nietknięte przez skrypt).
Nic się nie „kopiuje w trzy miejsca" — trzy kopie zawsze się rozjadą.

### Filar 4 — statusy i filtry zamiast „usuwania" i „dostępu"

Klucz rekordu = **nr RSPO**. Statusy: `nowy / przydzielone / DT umówione / brak ruchu`.
Listy z jednej zakładki `SŁOWNIKI`.

---

## 7. Proponowana struktura zakładek

### `SŁOWNIKI`
```
handlowcy | trenerzy | miasta | statusy | dni_tygodnia | trener_kolor
```
Wszystkie walidacje w obu plikach wskazują tutaj (nazwane zakresy).

### `BAZA` (plik BAZA)
```
rspo | nazwa | typ | miasto | ulica | mail | telefon |
handlowiec | deadline | status | ostatnia_aktywnosc | notatka
```

### zakładka handlowca (plik PRACA)
```
rspo | nazwa | miasto | ulica | mail | telefon |
status | data_dt | godz_od | godz_do | trener_dt | ilosc_klas | ilosc_dzieci |
cykl_dzien | cykl_godz_od | cykl_godz_do | cykl_sala | uwagi
```

### `EVENTY` (plik PRACA) — źródło prawdy dla kalendarzy
```
id | rspo | szkola | miasto | typ (DT|CYKLICZNE) | data | godz_od | godz_do |
trener | handlowiec | status | gcal_event_id
```
`gcal_event_id` od razu — bez tego push do Google Calendar będzie duplikował eventy
przy każdej edycji.

### `kalendarz <miesiąc>` (plik KALENDARZE) — **generowana**, nie edytowana
```
data | dzien_tyg | trener | szkola | miasto | godziny | typ
```

---

## 8. Plan etapami

### Etap 0 — porządek (warunek konieczny każdego kolejnego)
- `SŁOWNIKI` + nazwane zakresy, przepięcie 25 walidacji.
- `BAZA` z kluczem RSPO (import CSV/API z rejestru).
- Rozbicie zbitek na kolumny.
- `EVENTY` jako tabela zdarzeń.

> Automatyzacja na obecnym bałaganie będzie kopiować śmieci szybciej, niż oni to robią ręcznie.

### Etap 1 — dwa automaty (Apps Script)
- Edycja `handlowiec` + `deadline` w BAZIE → wiersz ląduje u handlowca,
  w BAZIE status `przydzielone` (**nie usuwać** — ukryć filtrem).
- Status `DT umówione` u handlowca → append u Julki + wpis do `EVENTY`.

### Etap 2 — kalendarze jako widoki
- Generator: `EVENTY` → `kalendarz <miesiąc>`, miesiąc z daty (`getMonth()`),
  zakładka tworzy się sama jeśli nie istnieje (spełnia „bez sztywnego kodowania").
- **Bug z 2–3 eventami znika sam z siebie** — to po prostu 2–3 wiersze pod tą samą datą.

### Etap 3 — opcjonalne
- Trigger dzienny: `deadline < dziś` && brak aktywności → kandydaci do „niewykorzystanych".
  **Półautomat** (skrypt oznacza, koordynator zatwierdza) — bezpieczniejszy niż ciche znikanie.
  Sami napisali, że mogą robić ręcznie → można pominąć w v1.
- Push do Google Calendar: `CalendarApp.createEvent()` + zapis `gcal_event_id`.
- Plansza STARTY generowana, kolor z mapy `trener → kolor` w SŁOWNIKACH
  (nie malowany ręką — malowany ręką jest właśnie tym, co czyni to „Meksykiem").

### Świadomie odpuszczone w v1
Izolacja handlowca od handlowca · plansza STARTY · Google Calendar
(chyba że zostanie czas — to kilka linijek).

---

## 9. Scenariusze do zatwierdzenia (język ich, nie techniczny)

**S1 — przydzielenie.** Koordynator otwiera BAZĘ, przy `SP11 Będzin` wybiera z listy
„Chytry" i wpisuje termin `30.09`. Po chwili szkoła jest w pliku roboczym w zakładce
Chytrego, a w BAZIE ma status „przydzielone" i nie widać jej na liście do rozdania.

**S2 — sukces.** Chytry umawia DT na `16.09`, wpisuje godziny `8:00`–`9:35`, trenera
Weronikę i zmienia status na „DT umówione". Po chwili: wiersz jest u Julki
(z pustymi jej kolumnami do uzupełnienia), a w zakładce „kalendarz wrzesień" pod `16.09`
pojawia się wpis `Weronika | SP11 Będzin | 8:00-9:35`.

**S3 — dwa eventy jednego dnia** ⭐ *(wprost odpowiedź na ich bug — wyróżnić)*.
Zuza umawia drugie DT z Weroniką na ten sam `16.09`, godz. `11:00`–`12:30` w `SP8 Będzin`.
W kalendarzu pod `16.09` są **dwa** wiersze Weroniki:
```
16.09 | czwartek | Weronika | SP11 Będzin | 8:00-9:35   | DT
16.09 | czwartek | Weronika | SP8 Będzin  | 11:00-12:30 | DT
```
Oba widoczne, trener planuje dzień z jednego ekranu.

**S4 — niewykorzystany rekord.** Mija `30.09`, Chytry nie ruszył `SP20 Sosnowiec`.
Rano szkoła znika z jego zakładki i jest w „niewykorzystane rekordy" w BAZIE.
Koordynator wybiera z listy „Zuzanna" — szkoła pojawia się u niej.

**S5 — nowy miesiąc sam z siebie.** Handlowiec umawia DT na `3.11`. Zakładki
„kalendarz listopad" jeszcze nie ma — tworzy się sama, wpis od razu w niej ląduje.
Nikt niczego nie konfiguruje.

**S6 — poprawka bez rozjazdu** ⭐ *(test akceptacji architektury)*.
Szkoła przekłada DT z `16.09` na `23.09`. Handlowiec poprawia datę w swoim wierszu —
wpis w kalendarzu przeskakuje pod `23.09`, u Julki data się aktualizuje.
Nie trzeba poprawiać w trzech miejscach.

> S6 pokazuje różnicę między „kopiowaniem", o które prosili, a widokami.
> Jak go zaakceptują — zaakceptowali architekturę, nie wiedząc o tym.

**S7 — kolizja trenera** *(bonus, sprzedaje rozbijanie zbitek)*.
Handlowiec wpisuje DT z Weroniką `16.09` na `9:00`, a ona ma już wtedy zajęcia do `9:35`.
Komórka podświetla się na czerwono. Możliwe **tylko** dlatego, że godziny są w osobnych
kolumnach jako czas, a nie tekst `08:00-12:30`.

---

## 10. Do rozstrzygnięcia z nimi (przed dotknięciem pliku)

1. **Kto jest handlowcem, a kto trenerem?**
   Opis (Sacawa, Olszewska, Małolepsza, Chytry, Młynarczyk) ≠ plik (Kasia, Zuza, Majka,
   Chytry, Dominika), a role są splątane w walidacjach. Bez czystych list automat
   przydzielania nie ruszy.
2. **Izolacja handlowców — twardy wymóg czy wygoda?**
   Rozstrzyga, czy Sheets długoterminowo wystarczy, czy to kandydat na Flask.
3. **Ile wierszy po filtrze RSPO** (setki czy tysiące) i ilu równoczesnych edytorów?
   Rozstrzyga, czy Sheets to udźwignie.
4. **Cykliczne — osobna tabela czy typ w `EVENTY`?**
   Zależy, jak spójna ma być plansza trenerów z kalendarzem DT.
5. **Czy w `.odt` było coś poza tekstem** (tabele, komentarze, obrazki)?
   Dostałem tylko warstwę tekstową.

---

## 11. Notatki techniczne (Apps Script)

- **Czym jest:** JavaScript wykonywany przez Google, edytor w arkuszu
  (*Rozszerzenia → Apps Script*). Odpowiednik makr VBA. Kod siedzi w pliku arkusza —
  **nic nie hostujesz**. Oni w opisie **nie wspominają o Apps Script** — to wniosek,
  nie ich wymaganie; najpewniej nie wiedzą, że coś takiego istnieje.
  Warto uprzedzić: to, o co proszą, wymaga kodu, nie da się wyklikać.
- **`onEdit` z zapisem do innego pliku wymaga installable trigger** — simple trigger
  nie ma uprawnień. To pierwsza rzecz, o którą się rozbijesz przy modelu 3-plikowym.
- **Blokowo, nie komórka po komórce:** `getValues()` / `setValues()` na zakresach.
  Inaczej skrypt muli. Limit: 6 min na wykonanie.
- **`clasp`** — CLI trzymające kod Apps Script lokalnie w git i pushujące do arkusza.
  Naturalny setup przy Claude Code zamiast klepania w edytorze przeglądarkowym.
- **API Sheets** ma limity zapisu — przy generowaniu kalendarzy budować całą tablicę
  w pamięci i zapisywać jednym `setValues()`.

---

## 12. Ścieżka długoterminowa (Flask)

Jest VPS `opxen.xyz` + działająca aplikacja Flask do rozliczeń → największe wady
własnej aplikacji (hosting, utrzymanie, adopcja) w dużej mierze odpadają.
Ci ludzie **już raz** przeszli z arkusza do webowej apki.

Druga aplikacja: osobny kontener/port, nginx reverse proxy (`leady.opxen.xyz`),
SQLite wystarczy przy tej skali.

Co daje, czego Sheets nie da:
- logowanie i role → **izolacja handlowców znika jako problem**,
- transfer = zmiana pola `przypisany_do`, zero kopiowania wierszy,
- kalendarz jako widok z tabeli eventów → 2–3 eventy dziennie naturalnie,
  kolory per trener w CSS,
- deadline'y cronem, historia zmian w logu,
- push do Google Calendar przez API (jedna integracja OAuth).

**Ryzyko:** oni myślą arkuszem („Julka ma swoje kolumny", „filtrowanie w każdej komórce").
Trzeba dać widok tabelaryczny z filtrami i edycją inline + eksport do XLSX,
inaczej wrócą do Excela bokiem.

**Migracja Sheets → Flask:** jeśli Etap 0 zrobiony porządnie, `BAZA` i `EVENTY`
z kluczem RSPO to **dokładnie schemat przyszłej bazy**. Migracja = eksport dwóch
zakładek do CSV, nie archeologia.
