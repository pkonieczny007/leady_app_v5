# Pytania do klienta — zebrane z analizy trzech plików

Stan na 30.07.2026. Kolejność = od najbardziej blokujących.
Każde pytanie ma **dowód z pliku**, żeby nie brzmiało jak czepianie się.

---

## A. Blokujące (bez odpowiedzi prototyp zgaduje)

### A1. Kto jest kim wśród trenerów o tym samym imieniu?

W planszy STARTY jedna osoba ma do 6 zapisów, a niektóre zapisy są niejednoznaczne.
Automat scalił **50 zapisów w 29 osób**, ale trzech nie umiał rozstrzygnąć:

| zapis w arkuszu | wystąpień | problem |
|---|---:|---|
| `MATEUSZ` / `METEUSZ` | 4 | dwóch Mateuszów: **Leśniak** i **Pustelnik** — którego dotyczy? |
| `Natalia Jasińska` | 2 | nazwisko wskazuje Jasińską, ale ona ma na imię **Nina**. Literówka czy trzecia osoba? |
| `MAJKA` / `MAJA` | 58 | przyjęliśmy **Maja Majewska** (legenda kolorów: `MAJA` = `#93C47D`, a `#B6D7A8` = Majewska Maja). Potwierdzić. |
| `SARA` | 10 | przyjęliśmy **Sara Bąk-Kopaniarz**. Potwierdzić. |
| `NATALIA M` | 18 | przyjęliśmy **Natalia Miękina** (druga Natalia — Starzomska — pisana pełnym nazwiskiem). Potwierdzić. |

Dodatkowo: czy `03. Małolepsza` (z listy w `PH Nowy`) i `WERONIKA MAŁOLEPSZA`
(z planszy STARTY) to ta sama osoba? Zakładamy, że tak.

**Dlaczego to blokuje:** bez tego nie da się policzyć, ile kto ma zajęć, ani
wykryć, że komuś nakładają się terminy.

### A2. Czy „02. Olaszewska" to literówka?

`Sacawa!A20:A200` i `Olszewska!A29:A340` mają na liście rozwijanej
**`02. Olaszewska`**, a pozostałe zakładki `02. Olszewska`.
Przyjęliśmy, że to literówka i scaliliśmy. Potwierdzić.

### A3. Trzy zakładki handlowców są puste — czy tak ma być?

`Małolepsza`, `Chytry`, `Młynarczyk` mają w pliku **same nagłówki, zero danych**
(sprawdzone komórka po komórce). Wypełnione są tylko `Sacawa` (42 wiersze)
i `Olszewska` (25). Czy oni jeszcze nie zaczęli, czy pracują gdzie indziej?

### A4. Ile realnie ma być „minimum na tydzień"?

Z notatek ze spotkania: „STATUS — minimum na tydzień". Prototyp przyjmuje
**5 umówionych DT na tydzień na handlowca** (parametr `CEL_TYGODNIOWY`).
Jaka jest prawdziwa liczba? Czy jest jedna dla wszystkich?

### A5. Zajęcia cykliczne nie mają w pliku daty pierwszych zajęć

W `PH Nowy` jest dzień tygodnia i godzina, ale nie ma daty startu.
Prototyp wylicza pierwsze wystąpienie po dacie DT (albo po 1 września) i oznacza
taki wpis jako „do potwierdzenia". Czy jest gdzieś data startu grupy?

---

## B. Ważne (zmieniają zakres, nie blokują)

### B1. Dwie sprzeczne prośby dotyczące trenera w jednym dniu

W `.docx`: *„jeśli dany trener ma 2 lub więcej takich spotkań w danym dniu,
to nie widzę 2 wpisów w tej dacie w kalendarzu DT, a powinnam"* — czyli **chce widzieć oba**.
W notatkach ze spotkania: *„żeby nie mógł trener 2× mieć aktywności"* — czyli **nie chce dwóch**.

Prototyp rozstrzyga to tak: **dwa spotkania w jednym dniu to norma i oba są widoczne;
ostrzegamy tylko wtedy, gdy GODZINY SIĘ NAKŁADAJĄ, ale zapisu nie blokujemy.**
Uzasadnienie: w realnych danych Kinga Król ma 44 zajęcia w miesiącu, więc kilka
dziennie to codzienność — problemem jest wyłącznie fizyczna niemożliwość
bycia w dwóch szkołach naraz. Czy to jest to, o co chodziło?

### B2. Kolizje, które już są w danych — poprawić czy zostawić?

Na zaimportowanych danych prototyp znalazł **30 realnych nakładek** w czerwcu, m.in.:

- `04. Zemela` — 1.06, `15:00–16:00` w SP 6 i `15:40–16:40` w SP 10 (dwie różne szkoły)
- `02. Olszewska` — 1.06, `15:30–16:30`, grupa 1 **i** grupa 2 w tej samej szkole
  o tej samej godzinie
- `32. Pustelnik` — 2.06, `14:45–15:45` w SP 40 i `15:30–16:30` w SP 1 Specjalnej

Czy to błędy w arkuszu, czy coś, czego nie rozumiemy (np. dwie grupy prowadzone
równolegle w dwóch salach)?

### B3. Czy plansza STARTY to na pewno tylko zajęcia cykliczne?

Sprawdziliśmy 3942 karty — **ani jedna nie dotyczy DT**. Wpisy to
`CYKLICZNE - <DZIEŃ>` albo `START - <DZIEŃ>`, gdzie `START` wygląda na pierwsze
zajęcia nowej grupy. Prototyp tak to traktuje. Potwierdzić.

### B4. Typ placówki — czy ten podział wystarcza?

Prototyp ma: szkoła podstawowa · przedszkole miejskie (PM) · przedszkole prywatne (PP) ·
zespół szkolno-przedszkolny (ZSP) · instytucja kultury · inna (uczelnia, firma).
Podstawa: prefiksy z ich pliku (`SP` 99, `PM` 36, `PP` 9, `MSP` 4, `ZSP` 3, `KSP` 1)
+ ręczna legenda `Chytry dograne!Q4` („PP – prywatne przedszkole, PM – publiczne").
Z notatek doszły „instytucje kultury". Czy czegoś brakuje?

### B5. Nowe statusy — czy nazwy są w porządku?

Dołożyliśmy do ich czterech statusów:

| status | skąd |
|---|---|
| `00. Nieprzydzielony` | potrzebny na bazę do rozdania |
| `00b. Rezerwacja` | ich `Rezerwacja Werka` / `Rez Wera` / `zuza - rezerwacja` — 5 zapisów w 4 zakładkach |
| `02b. DT w trakcie umawiania` | wprost z notatek ze spotkania |
| `03b. Grupa cykliczna otwarta` | ich `GOTOWE :) - jest umowa, są zajęcia` |
| `03c. Grupa się nie otworzyła` | ich `BYŁO DT ALE NIE MA ZAJĘĆ - NIE OTWORZYŁA SIĘ GRUPA` |

### B6. Miejscowości — scalone warianty

Ich plik miał **trzy różne listy** miejscowości z rozjechaną numeracją.
Scaliliśmy do jednej, przyjmując numerację z `BAZA`, i potraktowaliśmy jako
to samo: `09. Pszczyna powiat` ≡ `09. Pszczyna`, `15. Będzin powiat` ≡ `15. Będzin`,
`19. Chorzow` ≡ `16. Chorzów`, `08. Katowice Południe` ≡ `08. Katowice`,
`14. Dąbrowa Górnicza` ≡ `17. Dąbrowa Górnicza` (dublet w jednej liście).
Dołożyliśmy brakujące: Czeladź, Psary, Miedźna, Wola, Frydek, Góra, Mysłowice.
Czy „Katowice Południe" i „Pszczyna powiat" to naprawdę to samo, co miasto?

---

## C. Do decyzji o dalszym zakresie

### C1. Czego nie ma w prototypie, a było w zeszłorocznym pliku

| Co | Uwaga |
|---|---|
| **Dostępność trenerów** (`DOSTĘPNA 8–12:00`, `XXX`) | To była połowa treści kalendarza DT i jedyne wejście do umawiania. Tabela jest w bazie, ekranu nie ma. Robimy? |
| **Rejestr Tinkercada** (link, kod, płytkarz, drukarz, nr sali) | Kod i link są w prototypie przy zajęciach; osobnego rejestru nie ma. |
| **Logistyka placówki** (parking, wejście, „obowiązkowo KRK") | Dziś przepisywane do każdej karty z osobna. Powinno być raz przy szkole. |
| **Rozliczenia** (`JEDNORAZÓWKI`, `PRZEDSZKOLA FAKTURY`) | Logika prosta: 30% trener, 30% handlowiec, 5% Julia, reszta firma. 1–2 dni pracy. |
| **Rejon trenera** | Bez tego nie da się sensownie podpowiadać, kogo wysłać. |
| **Licznik wizyt / historia kontaktów per placówka** | Prototyp loguje zmiany, ale nie ma osobnego ekranu historii. |
| **Flaga „czerwona lista" / nie kontaktować** | `nie jechać, czerwona lista` — realnie używane. |
| **Google Calendar per trener** | Klient sam napisał, że to przyszłość. Nie robimy. |
| **Logowanie i role** | Prototyp jest bez logowania — każdy widzi wszystko. Do decyzji, czy izolacja handlowców jest twardym wymogiem. |

### C2. Cztery telefony wymagające decyzji

Nie da się ich naprawić automatycznie:
`785-61-99`, `253-93-09`, `254-51-24` (7 cyfr — brak numeru kierunkowego)
oraz `2 264 16 66` (8 cyfr — brakuje jednej).

### C3. Daty bez roku

W zeszłorocznym pliku są wpisy typu `24.09 8:00 - 10:00` i `od 29.09 do 3.10 nie mozna`.
Świadomie ich nie zgadujemy — wstawienie złego roku szkolnego byłoby gorsze
niż puste pole.

---

## D. Rzeczy, które znaleźliśmy i warto, żeby o nich wiedzieli

1. **Źródło ich buga z kalendarzem.** Komórka kalendarza to
   `XLOOKUP(data & "||" & trener; ...)`, a `XLOOKUP` zwraca **pierwsze** trafienie.
   Drugie i trzecie DT tego samego trenera w tym dniu **istnieje w danych**,
   tylko formuła fizycznie nie umie pokazać więcej niż jednego.
   W wierszach 50+ arkusza WRZESIEŃ widać ich własną, niedokończoną próbę naprawy
   przez `TEXTJOIN(... FILTER(...))`.
2. **`Zbiorczy!A2` ma literówkę w odwołaniu:**
   `FILTER(Chytry!A2:Y1075; Chytrychi!A2:A1075<>"")` — `Chytrychi` nie istnieje.
3. **`Niewykorzystane rekordy` i `Szkoły z DT` czytają tylko z 4 zakładek**
   (`Sacawa; Olszewska; Małolepsza; Chytry`) — **Młynarczyk wypada z tych widoków**.
4. **Zakładka `Kalendarz LUTY DT` jest pusta** (`A1:A1`) — mechanizm „nowy miesiąc
   tworzy się sam" nie działa; luty trzeba było zrobić ręcznie i nie zrobiono.
5. **Zakładka `Sacawa` ma 50 500 wierszy** — stąd plik waży 4,5 MB i muli.
6. **Legenda kolorów z września jest już nieaktualna.** `#9900FF` to w legendzie
   „Jula Gajkiewicz", a w kartach od listopada — Paulina Zemela. Julia Wesołowska
   ma 6 różnych odcieni. Dwa kolory są współdzielone przez dwie osoby.
7. **Kolor czerwony `#FF0000` na planszy to nie trener, a flaga „problem"**
   (151 kart, 30+ różnych trenerów), a ciemnoszary `#434343` = „brak obsady".
8. **`BAZA` ma 544 wiersze i jest wypełniona tylko w 7 kolumnach** — to książka
   adresowa, nie rejestr procesu. 49 przedszkoli już w niej siedzi bez oznaczenia typu.
