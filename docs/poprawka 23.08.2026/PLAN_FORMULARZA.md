# Plan: nowy formularz terenowy (v5) + filtry „Twoje szkoły"

**Data:** 23.08.2026. **Status na 24.08 (wieczór):** ZROBIONE E0, E5 (lista
`zajecia` w API), E7-lite i E8 — piąty przycisk `/formularz/v5` z kaskadą
powiatową działa. Doszedł **panel dostępności prowadzących przeniesiony z v3**
(kandydaci w grupach, status wybranej osoby, „co się dzieje tego dnia") —
z jedną różnicą wymuszoną przez kaskadę: panel jest **przy sekcji**, bo v5
umawia kilka rzeczy naraz i każda ma własną datę. ZOSTAŁO: E1, E2, E3,
E4 (nowe typy zajęć — czeka na odpowiedzi 1–4) i E6 (wspólny moduł JS).
**Źródła wymagań:** `POPRAWKA_FORMULARZA/formularz` i
`POPRAWKA_FORMULARZA/poprawka_dzialania_filtrow` (notatki Kasi + dopiski Pawła),
lista Zuzi (`ZUZIA_lista_błędów v3.md`), rejestr `REJESTR_POPRAWEK_2026-08.md`,
projekt `PROJEKT_BAZY_RSPO.md`.

Czego chce klient, jednym zdaniem: **jeden formularz, w którym jest wszystko**
(szkoły i przedszkola, DT, cykliczne, jednorazówki, festyny, VR, sama wizyta),
rozsuwający sekcje kaskadą od placówki, z geografią po powiatach z RSPO —
a obok tego ekran „Twoje szkoły" z filtrami pokazującymi efekt pracy handlowca.

---

## 1. Rozstrzygnięcie: nowy wariant v5, OBOK czterech istniejących

**To już nie jest pytanie — to decyzja klienta (Paweł, 23.08):** docelowo jeden
formularz, ale starych wariantów nie usuwamy; nowy powstaje obok, żeby dało się
porównać na żywych danych. Wygaszanie starych to **osobna decyzja po testach,
bez terminu w tym planie** (pkt 6).

Dlaczego ta decyzja jest też technicznie dobra:

- **v4 jest przedmiotem porównania.** Klient testuje v4 („na razie zróbmy to
  w nowym formularzu v4, jak przetestuję, to wprowadzimy jeden zwycięski").
  Przebudowa v4 w miejscu zniszczyłaby punkt odniesienia w połowie testu —
  klient porównywałby ruchomy cel.
- **Kaskada to inna architektura ekranu, nie kolejna sekcja.** v4 (1281 linii JS)
  jest zbudowany wokół stałej kolejności sekcji z wyłącznikiem DT; kaskada
  „placówka → rodzaje → sekcje" odwraca sterowanie. Doklejanie jej do v4
  dałoby trzecią warstwę przełączników na dwóch istniejących.
- **Funkcja zostaje wspólna.** Zasada z CLAUDE.md („oba zapisują przez to samo
  API i tę samą walidację") obowiązuje v5 w całości: zapis idzie przez
  `POST /api/formularz` (app.py:1836–2034), rozszerzany **addytywnie**
  (pkt 4, etap E5) — stare warianty wysyłają ten sam payload co dziś i niczego
  nie zauważają.

Twarde reguły na czas współistnienia pięciu wariantów:

1. **Stare warianty (v1–v4) dostają wyłącznie poprawki błędów** — np. POWROT
   w v3 wskazujący na v2 (`formularz3.js:661` i `:692`). Żadnych nowych funkcji:
   inaczej porównanie przestaje porównywać układ. Braki funkcji w v1
   (bez „Wyniku wizyty" P22, bez P27, bez `podstawKontakt` P04 — raport
   rozpoznania, tabela §2) **nie są błędami do łatania** — są argumentem przy
   przyszłej decyzji o wygaszeniu.
2. **Wspólny moduł JS zamiast piątej kopii.** `formularz2/3/4.js` mają
   identyczne bloki: toast/api/esc, `bezOgonkow`/`pasuje`/`rysujSzkoly`/
   `wczytajSzkoly`/`podstawKontakt`, `bladPola`/`czyscBlad`,
   `zapiszSzkic`/`wczytajSzkic`. Powstaje `static/formularz_wspolne.js`
   (wydzielony z v4, bo v4 ma wersje najświeższe — z P04/P06/P07), używany
   **tylko przez v5**. Stare warianty zostają przy swoich kopiach — przepięcie
   ich na moduł to zmiana w kodzie testowanym przez klienta, czyli złamanie
   reguły 1. `FxCykl` (formularz4.js:43–105) już jest czystym modułem
   z testem `test_cykl.js` — v5 go importuje, nie kopiuje.

---

## 2. Model interakcji v5 — kaskada od placówki

Zasady nadrzędne: jedna kolumna (praca kciukiem, na stojąco), sekcje **rozsuwają
się dopiero po wyborze**, wynik wizyty jest **zawsze** dostępny (bo „można tylko
zaznaczenie z uwagami, jeżeli się było — ruchy poczynione, ale bez sukcesu"),
zapis jednym żądaniem z `klucz_zapisu` i kolejką awaryjną (`formularz_awaria.js`
bez zmian).

```
┌──────────────────────────────────────────────┐
│ pasek: profil · KTO WYPEŁNIA (z sesji)       │  ← .f-pasek jak w v1–v4
├──────────────────────────────────────────────┤
│ 1. PLACÓWKA                     (zawsze)     │
│    [Powiat ▾]*  [Miejscowość ▾]              │  ← *powiat dopiero po M5/M6
│    typ:  (Szkoła) (Przedszkole) (Inna)       │     RSPO; do tego czasu jeden
│    [ szukaj po nazwie… ]        (P07)        │     poziom: miejscowość
│    ○ SP 5 Piekary Śląskie  ★                 │  ← gwiazdki P06, filtr lokalny
│    ○ MSP 1 Katowice                          │
│    ▸ nie ma na liście? dodaj nową placówkę   │
├──────────────────────────────────────────────┤
│ 2. KONTAKT          (rozsuwa się po wyborze) │
│    osoba / telefon / mail  (podstawKontakt   │
│    z bazy + ostrzeżenie o nadpisaniu — P04)  │
├──────────────────────────────────────────────┤
│ 3. CO USTALIŁEŚ?    (rozsuwa się po wyborze) │
│    [ DT ] [ Cykliczne ] [ Jednorazówka ]     │  ← chipy WIELOKROTNEGO wyboru;
│    [ Cykliczne inne ] [ Festyn ] [ VR ]      │     nic nie zaznaczasz = sama
│    [ Inne ]                                  │     wizyta (wynik + notatka)
│                                              │
│    ── zaznaczenie chipa rozsuwa sekcję: ──   │
│    ▾ DT: data (twarda — P27), godz., klasy,  │
│      dzieci, trener (status trenera, wolne   │
│      okna, „co się dzieje tego dnia" — z v3) │
│    ▾ CYKLICZNE: tryb reguła / daty z listy   │
│      (FxCykl z v4), godz. od–DO (z v1)       │
│    ▾ JEDNORAZÓWKA: data, godz., odbiorca     │
│    ▾ FESTYN / VR / INNE: data, godz., uwagi  │
├──────────────────────────────────────────────┤
│ 4. WYNIK WIZYTY                 (zawsze)     │
│    status ze słownika + notatka              │
│    „podpisze się: Zuzanna K., 23.08" ← sesja │
├──────────────────────────────────────────────┤
│ [        ZAPISZ  (jedno żądanie)        ]    │  ← przyklejony do dołu ekranu
└──────────────────────────────────────────────┘
```

Rozstrzygnięcia w modelu:

- **Typ placówki steruje kaskadą, nie mnoży chipów.** Kasia wymienia „cykliczne
  szkoła" i „cykliczne przedszkole" jako osobne pozycje — ale to ten sam chip
  „Cykliczne", który przy placówce typu przedszkole zapisuje
  `CYKLICZNE-PRZEDSZKOLE` i domyślnie włącza tryb „daty z listy" (przedszkola
  umawiają pakiet dat, szkoły regułę — komentarz w seed.py:138–141; v4 robi to
  już dziś w `formularz4.js:875–879`). Handlowiec nie musi wiedzieć, że to dwa
  typy w bazie.
- **„Wizyta" nie jest rodzajem zajęć.** Wizyta bez umówienia czegokolwiek =
  wypełniony wynik wizyty bez żadnego chipa. Nie tworzy eventu, nie wchodzi do
  kalendarza — kalendarz to grafik zajęć, a status + notatka żyją na leadzie
  (dokładnie po to powstało P22/P27). Pozycja „wizyta" z listy Kasi jest w v5
  obsłużona, tylko nie jako event.
- **Odznaczenie chipa zwija sekcję, ale nie kasuje wpisanego.** Dane zostają
  w szkicu (localStorage), do żądania nie wchodzą (wzorzec `pokazDT()`
  z formularz4.js:821–833 — ukryta sekcja czyści też swoje błędy walidacji).
  Przy zapisie z wypełnioną-a-odznaczoną sekcją: ostrzeżenie „sekcja X
  wypełniona, ale odznaczona — nie zostanie zapisana", zapis przechodzi
  (ostrzegamy, nie blokujemy).
- **Nazwisko przy notatce — automatycznie z sesji, nie z pola.** Kasia prosi
  o „nazwisko osoby wprowadzającej wiadomość". Właściciel wpisu zawsze z sesji
  (zasada projektu) — więc żadnego pola do wpisania: notatka wyniku wizyty
  **dopisuje się** do `uwagi` leada z sygnaturą `[23.08 · Nazwisko]` zamiast
  nadpisywać. Kolejny PH po zwrocie szkoły widzi, kto tam był i co zostawił —
  bez zmiany schematu. (Trwałość uwag przy placówce po zwrocie to osobne P16
  z rejestru — sygnatura jest z nim zgodna, nie zastępuje go.)
- **Plan dnia („zakładka od koordynatora") w v5 NIE występuje** — Kasia: „robi
  chaos". Znika też z v1–v4, ale dopiero po tym, jak filtry w „Twoich szkołach"
  przejmą jego rolę (kolejność w pkt 5 etapu E3 — inaczej handlowiec traci
  jedyną listę zadań).

### Rodzaje zajęć vs słownik `typ_eventu` — co jest, czego brakuje

Stan słownika na **prod** (odczyt `data/prod/leady_v3.db` 23.08): `DT`, `START`,
`CYKLICZNE`, `JEDNORAZÓWKA`, `FESTYN`, `VR` — **bez `CYKLICZNE-PRZEDSZKOLE`**,
choć kod go zna (`db.py:190 TYPY_CYKLICZNE`), seed go sieje (seed.py:142)
i v4 pozwala go wybrać (formularz4.html:374). Zapis z formularza przechodzi
(API waliduje po stałej `TYPY_CYKLICZNE`, nie po słowniku), ale **edycja takiego
eventu w karcie leada trafi na twardą blokadę „wartość spoza słownika"**.
To poprawka danych na prod do zrobienia od ręki (etap E0).

| pozycja Kasi | typ w bazie | stan |
|---|---|---|
| wizyta | — (status + notatka na leadzie) | jest (P22) |
| DT | `DT` | jest |
| cykliczne szkoła | `CYKLICZNE` | jest |
| cykliczne przedszkole | `CYKLICZNE-PRZEDSZKOLE` | jest w kodzie, **brak w słowniku prod** |
| jednorazówka (szkoła/przedszkole/seniorzy) | `JEDNORAZÓWKA` + odbiorca w polu `grupa` | typ jest; odbiorca — pytanie 1 |
| cykliczne inne (seniorzy, MDK) | `CYKLICZNE-INNE` | **NOWY** — musi wejść do `TYPY_CYKLICZNE` |
| festyn | `FESTYN` | jest |
| VR | `VR` | jest |
| inne | `INNE` | **NOWY** |
| — | `START` | jest; **poza kaskadą** (inauguracja grupy — wpis koordynatora/importu, nie z terenu; pytanie 4) |

Skutki dla kodu — wszystkie w miejscach, które już są „jednym źródłem":

- `EVENT_FIELDS` (db.py:109–130) **nie wymaga nowych kolumn**: jednorazówka,
  festyn, VR i inne używają `data`/`godz_od`/`godz_do`/`trener`/`uwagi`/`grupa`;
  cykliczne-inne używa pól cyklu. To ważny wynik: nowe rodzaje to wartości
  słownika + walidacja, nie migracja schematu.
- `TYPY_CYKLICZNE` (db.py:190) rośnie o `CYKLICZNE-INNE` — jedno miejsce,
  z którego czytają kalendarz (`calendar_view.py:145 TYPY_POWTARZALNE`), repo
  (filtr „z cyklami", statystyki) i walidacja API. Komentarz przy stałej
  przypomina, czemu to jedno miejsce istnieje: rozjazd = wpis siedzący w bazie
  i **niewidoczny w kalendarzu** (usterka z 10.08).
- presety filtra typów w kalendarzu (app.py:654–656) dostają nowe wartości.
- seed.py:142 `TYP_EVENTU` + aliasy (seed.py:357–363) — nowe wartości
  i ich potoczne aliasy.

### Geografia: NIE czekamy na migrację RSPO — kaskada za adapterem

Rozstrzygnięcie: **v5 powstaje na dzisiejszej osi `miejscowosc` i przełącza się
na powiaty bez przepisywania**. Uzasadnienie:

- Brak Czeladzi to problem **danych, nie formularza**: Czeladź wejdzie do bazy
  dopiero w etapie M7 migracji (dołożenie ~714 placówek z lustra rejestru).
  Formularz z kaskadą powiatową nad dzisiejszymi danymi dalej nie pokazałby
  Czeladzi — czekanie nic nie daje, a klient potrzebuje reszty kaskady teraz.
- Kolumny `powiat`/`gmina`/`obszar` powstają w M5, przełączenie ekranów to M6.
  Projekt RSPO (pkt 4, aneks) i tak przewiduje w M6 „formularz: wybór obszaru
  zamiast miasta" — v5 ma być **pierwszym ekranem gotowym na to przełączenie**,
  zamiast piątym do przerobienia.
- Adapter konkretnie: v5 pobiera listę grup geograficznych z jednego endpointu
  (`/api/formularz/geografia` — nazwa robocza), który zwraca
  `{osie: [{poziom, etykieta, wartosci}]}`. Dziś serwer zwraca jedną oś
  (miejscowości ze słownika — to, co v2–v4 mają dziś w `#f2-miasto`);
  po M5/M6 dwie (powiat → miejscowość). **JS renderuje tyle selectów, ile
  dostał osi — nie zna nazw kolumn.** Przełączenie = zmiana zapytania po
  stronie serwera, zero zmian w formularz5.js.
- Filtr „Miasto" **zostaje obok powiatu** (prośba Kasi wprost) — w modelu
  adaptera to po prostu druga oś, nie osobny mechanizm.

Przy okazji v5 dostaje własną wersję listy placówek bez dwóch znanych defektów
wspólnych endpointów (nie ruszamy ich dla v1–v4): `/api/placowki` robi JOIN
z `leady`, przez co placówka bez leada jest niewidoczna, a z dwoma leadami —
podwójna (app.py:1716–1741); `/api/placowki/szukaj` tnie LIMIT-em 60 **przed**
wyniesieniem „moich" (app.py:1744–1781, defekt opisany w docs/14 §5.5).

---

## 3. Telefon: „nie da się zmniejszyć obrazu, widok trzeba przesuwać"

Diagnoza z kodu — to **dwie osobne przyczyny**, nie jedna:

1. **„Nie da się zmniejszyć" = PWA w trybie standalone.** Kod nigdzie nie
   blokuje zoomu (base.html:5 — viewport bez `user-scalable`/`maximum-scale`;
   zero `touch-action`), ale `manifest.webmanifest` ma `"display":"standalone"`
   ze `"scope":"/"` na całą aplikację + `apple-mobile-web-app-capable=yes`
   (base.html:59). Aplikacja uruchomiona z ikony na iOS ma pinch-zoom wyłączony
   **systemowo**. To skutek celowej decyzji (ikona na ekranie — punkt z 10.08),
   więc zmiana `display` na `minimal-ui`/`browser` to decyzja produktowa —
   pytanie 8 do klienta. Właściwa odpowiedź i tak brzmi: ekran ma się mieścić,
   a nie dać się oddalać.
2. **„Widok trzeba przesuwać" = poziome przepełnienie topbara.**
   `.topbar-right` (style.css:232 — flex bez wrap; :258 w @media 700px
   `flex:0 0 auto` — zakaz kurczenia) z czterema przyciskami koordynatora
   (base.html:134–147, ~370 px) wypycha stronę w bok na ekranach bez własnego
   paska (formularze mają `.f-pasek` i są w porządku — dlatego objaw dotyczy
   /baza, /leady, /pulpitu, /kalendarza).

**Poprawka przyczyny 2 (`topbar-right`/`.seg`/`.kv`) jest robiona równolegle
przez Pawła na gałęzi — w tym planie to ZROBIONA ZALEŻNOŚĆ, nie zadanie.**

Co z diagnozy zostaje dla tego planu:

- `.seg` (style.css:622–626: `inline-flex` + `overflow:hidden` bez wrap) dziś
  nie wypycha strony, ale **ucina zakładki bez możliwości dojechania** — na
  375 px czwarta zakładka jest przycięta. Filtry Kasi to 6 chipów: bez poprawki
  połowa będzie niewidoczna. Etap E2 MUSI objąć `.seg` wzorcem z `.nav`
  (style.css:260–271 — `overflow-x:auto` + ujemny margines), o ile poprawka
  równoległa tego nie zamknie (sprawdzić przed startem E2).
- v5 projektujemy mobile-first z listą ryzyk z rozpoznania w ręku (`.kv` 882,
  `.julia-grid` 891, `.event-grid` 904 — siatki z twardymi minimami px bez
  progów @media): sekcje v5 nie używają tych klas, tylko jednokolumnowego
  układu z progiem @media dopiero KU GÓRZE (desktop dostaje kolumny, telefon
  jest stanem bazowym).

---

## 4. Etapy — każdy osobno wdrażalny

Rozmiary: S = do pół dnia, M = 0,5–1,5 dnia, L = 2+ dni. Każdy etap kończy się
kompletem testów (9 plików) na zielono i wpisem do rejestru poprawek.

### E0 · Słownik `typ_eventu` na prod — `CYKLICZNE-PRZEDSZKOLE` (dane/słownik, S)
- Wejście: brak. **Jedyny etap do zrobienia PRZED poniedziałkIEM.**
- Robi: dodanie wartości do słownika na prod (Kasia może przez panel Słowniki;
  typ „słownik" z rejestru) + test spójności w `test_scenariusze.py`:
  każda wartość `TYPY_CYKLICZNE` istnieje w seedzie słownika `typ_eventu`
  (żeby rozjazd kod↔słownik nie wrócił z kolejnym typem).
- Wyjście: edycja eventu `CYKLICZNE-PRZEDSZKOLE` w karcie leada przechodzi
  walidację słownika.

### E1 · Chipy i spójność filtrów na `/baza` (kod, S)
- Wejście: poprawka mobilna Pawła zmergowana (dotyka tych samych okolic CSS).
- Robi: poprawki błędów istniejącego ekranu — zakładki na `/baza` gubią
  parametr `handlowiec` z URL (baza.html:15–21 nie przekazują; leady.html
  przekazuje — wzorzec jest); `/baza` nie pokazuje plakietki `moj_filtr`,
  choć mechanizm działa (ciche zawężenie = ukryty filtr, wprost wbrew zasadzie
  projektu); krucha linia `td:nth-child(3)` w baza.html:87.
- Wyjście: `test_filtr_osob.py` rozszerzony; filtr zawsze jawny.

### E2 · Filtry Kasi w „Twoich szkołach" `/leady` (kod, M)
- Wejście: E1 (spójny mechanizm chipów), `.seg` przewijalny (zależność z pkt 3).
- Robi — cała robota w JEDNYM miejscu, `repo._warunki()` (repo.py:162–222),
  przez co licznik, eksport XLSX i stronicowanie dostają nowe filtry gratis:
  - **„W pracy"** — nowy zakres: statusy pośrednie (`01.`–`02b.`), nie samo
    posiadanie handlowca (Kasia: „umówione spotkanie albo rozmowy w toku");
  - **„Cała moja baza"** — istniejący zakres `przydzielone`;
  - **„DT umówione"** — istniejący zakres `umowione` (chip już jest na /leady);
  - **„Jednorazówki/VR umówione"** — nowy zakres: EXISTS event
    `JEDNORAZÓWKA`/`VR` nieodwołany (`sql_nieodwolane`, db.py:147) z datą;
  - **„Po terminie (z historią)"** — nowy zakres z `log`: leady z wpisem
    `co='auto-zwrot po terminie'` (zwrot.py:155), gdzie zwrócony handlowiec =
    osoba z filtra. Dzisiejszy zakres `po_terminie` (deadline < dziś) tego NIE
    pokrywa: auto-zwrot czyści handlowca (zwrot.py:150–152), więc szkoła znika
    z „mojej bazy" — Kasia chce ją widzieć jako historię. Tylko-do-odczytu;
  - **„Z cyklami"** — istniejący zakres `cykle`;
  - **kolumna „efekt pracy"** — renderer `_td` (templates/_makra.html:161–253)
    już umie `dt_data`/`ile_dt`/`ile_cykl`/`aktywnosc`: dopisanie kluczy
    w leady.html:45–46 + nowa miara „dni bez ruchu"
    (`julianday('now')-julianday(l.ostatnia_aktywnosc)` w BAZOWY_SELECT);
  - **„do zrobienia podbijają się na górę"** — rozszerzenie domyślnego
    `_order_by()` (repo.py:225–236): najpierw statusy pośrednie z terminem,
    potem reszta (dziś: pin → z terminem → deadline).
- Wyjście: 6 chipów na `/leady`, każdy z licznikiem; `test_scenariusze.py` —
  `sprawdz()` na każdy zakres (w tym: zwrócona szkoła widoczna w „Po terminie"
  i niewidoczna w „Całej mojej bazie").
- Do tego zadanie **dane** (osobno, z Kasią): zaczytanie przypisań z jej pliku
  („te szkoły które miałam w moim pliku pozaznaczane do PH — tam był odpowiedni
  arkusz") — dopytać o plik, jednorazowy skrypt w `narzedzia/`.

### E3 · Zdjęcie „zakładki od koordynatora" z formularzy (kod, S)
- Wejście: **E2 na produkcji i obejrzane przez Kasię** — dopiero gdy „Twoje
  szkoły" przejmują rolę listy zadań, wolno zabrać ją z formularza. Odwrotna
  kolejność = handlowiec zostaje bez żadnej listy.
- Robi: usunięcie 4×include `_plan_dnia.html` (formularz.html:75, f2:80, f3:90,
  f4:99), `fx_plan.js`, 4×`FX_PLAN_WYBIERZ`, 4×wywołanie `FX_PLAN_ZROBIONE`
  z `pokazSukces`, CSS style.css:1044–1108. **Klucz `moje`
  w `_kontekst_formularza` (app.py:1566–1583) ZOSTAJE** — używają go
  `oznaczMojeMiasta` (gwiazdki P06) i `pokazMoje` w v1.
- To jest poprawka „ujmująca", więc formalnie zmiana w starych wariantach —
  ale zgodna z regułą 1: wykonuje wprost życzenie klienta, niczego nie dokłada.
- Wyjście: `test_formularz.py` — formularze bez planu dnia, gwiazdki działają.

### E4 · Nowe typy zajęć w kodzie i słownikach (kod + słownik, S)
- Wejście: odpowiedzi na pytania 1–4 (pkt 8). Bez odpowiedzi NIE zaczynać —
  wartości słownika po wejściu na prod zostają na zawsze (pułapka semantyczna
  z P25 pokazuje koszt pochopnej wartości).
- Robi: `CYKLICZNE-INNE` + `INNE` w seed.py:142 i aliasach; `CYKLICZNE-INNE`
  do `TYPY_CYKLICZNE` (db.py:190); presety kalendarza (app.py:654–656);
  wartości do słownika na test/demo/prod.
- Wyjście: test S16-bis w `test_scenariusze.py` — event `CYKLICZNE-INNE`
  zapisany przez API **widoczny** w `events_for_month` (dokładnie ta klasa
  usterki kosztowała pół dnia 10.08); test spójności z E0 łapie nowe typy
  automatycznie.

### E5 · API: wiele zajęć w jednym zapisie (kod, M)
- Wejście: E4 (typy istnieją).
- Robi: `POST /api/formularz` przyjmuje **dodatkowo** listę
  `zajecia: [{typ, data, godz_od, …, terminy?}, …]` obok dzisiejszych bloków
  `dt`/`cykl` (pętla app.py:1945 zostaje — stare warianty wysyłają po staremu
  i niczego nie zauważają). Walidacja per typ: DT — twarda tylko data (P27);
  typy cykliczne — reguła albo terminy, limit `MAX_TERMINOW_CYKLU=60`;
  jednorazowe — data. Typ spoza słownika `typ_eventu` → 400 (twarda blokada,
  jak dziś dla `TYPY_CYKLICZNE`). Reguła „termin bije deklarację"
  (app.py:1927–1931) rozszerzona świadomie: status `03. DT umówione` ustawia
  wyłącznie event `DT` — festyn ani VR nie mają prawa przestawić statusu leada.
  Notatka wyniku wizyty: dopisywanie do `uwagi` z sygnaturą
  `[data · handlowiec z sesji]` zamiast nadpisania.
- Całość w tej samej transakcji z tym samym `klucz_zapisu` — jeden commit
  (app.py:2014), błąd w trzecim evencie = rollback wszystkiego; powtórka po
  zerwanym połączeniu z listą zajęć nie tworzy dubli (mechanizm
  `zapisy_formularza` bez zmian).
- Wyjście: `test_formularz.py` — payload z 3 zajęciami różnych typów → 3 wiersze
  `eventy` albo 0 przy błędzie; powtórka klucza → `powtorka:true`, licznik
  eventów bez zmian; stare payloady v2/v3/v4 przechodzą bajt w bajt jak dziś.

### E6 · Wspólny moduł JS (kod, M)
- Wejście: brak zależności twardych; przed E7.
- Robi: `static/formularz_wspolne.js` — wydzielone z formularz4.js: toast/api/esc,
  `bezOgonkow`/`pasuje`, `rysujSzkoly`/`wczytajSzkoly`/`podstawKontakt`,
  `bladPola`/`czyscBlad`, szkic. Konwencja jak `FxCykl`: czyste funkcje
  z `module.exports` na końcu, testowalne nodem. Używa go tylko v5.
- Wyjście: `test_formularz.py` — serwerowy dowód, że v1–v4 serwują niezmienione
  pliki (suma kontrolna / brak `formularz_wspolne.js` w ich szablonach).

### E7 · Ekran v5 (kod, L — największy etap)
- Wejście: E4 + E5 + E6. Geografia: NIE czeka na RSPO (adapter, pkt 2).
- Robi: `templates/formularz5.html` + `static/formularz5.js` + trasa
  `/formularz/v5`; kaskada z pkt 2; endpoint `/api/formularz/geografia`
  (adapter osi) i lista placówek bez defektów JOIN/LIMIT; sekcja DT przejmuje
  z v3/v4 status trenera, kategorie dostępności i „co się dzieje tego dnia";
  cykl przejmuje `FxCykl` + `godz_do` (z v1 — jedyny wariant, który je ma);
  wpis do `formularz_wybor.html` jako „testowy — kaskada" (v3 zostaje
  „Rekomendowany" do decyzji klienta); szkic pod własnym kluczem `f5-`.
- Wyjście: pełny scenariusz w `test_formularz.py` (pkt 7 planu testów);
  klik-test na telefonie przez LTE na demo (rytuał z 10.08).

### E8 · Kaskada powiatowa (kod, M — ZALEŻNE OD MIGRACJI RSPO: M5+M6)
- Wejście: kolumny `powiat`/`obszar` wypełnione na danych (etap **M5** projektu
  RSPO); zgoda na przełączenie ekranów (etap **M6** — v5 jest jego częścią,
  nie osobnym bytem). Brak Czeladzi znika dopiero po **M7** (dołożenie placówek)
  — komunikować to klientowi wprost, żeby nie odebrał E8 jako „nadal nie ma
  Czeladzi, czyli nie działa".
- Robi: endpoint geografii zwraca dwie osie (powiat → miejscowość);
  filtr „Miasto" zostaje jako druga oś. Zmiany TYLKO po stronie serwera.
- Wyjście: handlowiec na profilu `test` znajduje te same szkoły co przed
  przełączeniem (warunek wyjścia M6 z projektu RSPO).

### Co przed poniedziałkiem — wprost

Poprawki rundy sierpniowej (P01–P29) są na gałęzi i to ONE mają działać
w poniedziałek. Z tego planu:

- **robić:** E0 (kwadrans, czysta poprawka danych/słownika);
- **zależność robiona równolegle:** poprawka mobilna Pawła
  (topbar/.seg/.kv) — nie dublować jej;
- **NIE zaczynać:** E2 i E3 — dotykają ekranów, na których ludzie pracują
  w poniedziałek, a zostawione w połowie zostawiają rozgrzebany widok.
  E3 nie wolno ruszyć przed E2 z definicji.

**Korekta z 23.08 wieczorem (decyzja Pawła): E5 i E7 wolno robić w dowolnym
momencie.** Nowy formularz powstaje jako **PIĄTY PRZYCISK** na ekranie wyboru
`/formularz`, obok czterech istniejących — czyli jest ścieżką, w którą nikt nie
wchodzi przypadkiem. Rozgrzebany v5 nie zablokuje pracy, bo handlowiec dalej
klika swój v3; w najgorszym razie piąty kafelek prowadzi do ekranu, który nie
robi jeszcze wszystkiego. To jest ta sama zasada, dla której cztery warianty
w ogóle istnieją: **porównanie na żywych danych zamiast sporu o układ**.

Dwa warunki, żeby to pozostało prawdą:
1. **E5 musi być addytywne.** Lista `zajecia:[…]` dochodzi OBOK bloków
   `dt`/`cykl`; stare payloady mają jechać bajt w bajt jak dziś. Test
   „v1–v4 nietknięte" (pkt 7) przestaje być formalnością i staje się zaporą.
2. **Piąty kafelek ma być opisany jako testowy** — jak dziś v4 („testowy:
   CYKLICZNE-PRZEDSZKOLE"). Handlowiec, który wejdzie tam z ciekawości, ma
   wiedzieć, na czym stoi; v3 zostaje „Rekomendowany" do końca testów.

---

## 5. Punkt 5 i 6 klienta („zakładka koordynatora", filtry) — jedno zadanie czy dwa?

**Dwa zadania, wykonywane w twardej kolejności, w jednej narracji dla klienta.**
Punkt 6 (filtry + kolumna efektu w „Twoich szkołach") to E2 — ekran `/leady`,
zero wspólnego kodu z formularzem. Punkt 5 (zniknięcie zakładki z formularza)
to E3 — formularze. Rozdzielenie jest ważne wdrożeniowo: E2 można wystawić na
demo i dać Kasi do klikania bez dotykania formularzy, którymi ludzie pracują;
E3 jest trywialne technicznie, ale **zakazane przed odbiorem E2** — bo zabiera
handlowcowi jedyną listę zadań, zanim nowa zacznie działać.

---

## 6. Co z czterema istniejącymi wariantami

- **Zostają wszystkie cztery.** Decyzja klienta: porównanie na żywych danych.
  Terminu wygaszenia NIE planujemy — to osobna decyzja po testach v5.
- Do tego czasu: **wyłącznie poprawki błędów**. Znane na dziś: POWROT w v3
  prowadzi do v2 (`formularz3.js:661`, `:692`); rozjazd czyszczenia kontaktu
  (klient czyści pole, serwer zapisuje tylko niepuste — app.py:1919; naprawa
  dotyka wspólnego API, więc z testem „trzy warianty identycznie" jak w P04).
- **Nic z działającego nie zginie przy przyszłym wygaszeniu**, bo v5 wchłania
  z góry: tryb terminów z listy + `czyDT()` + typ przedszkolny (v4, przez
  `FxCykl` i moduł wspólny), status trenera + kategorie + „co się dzieje tego
  dnia" (v3), `godz_do` cyklu (v1 — jedyny, który je ma). Jedyna funkcja,
  której v5 świadomie NIE przejmuje, to searchbox całobazowy v1
  (`/api/placowki/szukaj`) — kaskada geografia→placówka + filtr tekstowy
  pokrywa ten sam przypadek bez defektu LIMIT-u.
- Gdy decyzja o wygaszeniu zapadnie (poza tym planem): trasy starych wariantów
  → redirect na zwycięzcę, szablony i JS zostają w repo jeden tag wstecz,
  szkice localStorage starych kluczy (`fx-szkic-v1`, `f2-`…`f4-`) czytane
  jednorazowo z komunikatem „masz niedokończony szkic w starym formularzu".

---

## 7. Testy (konwencja `sprawdz(nazwa, warunek, opis)`, własna tymczasowa baza)

`test_formularz.py`:
1. serwerowo: `/formularz/v5` renderuje sekcje kaskady, chipy rodzajów brane ze
   słownika `typ_eventu` (nie z HTML na sztywno), `START` NIE jest chipem;
2. API: `zajecia` z trzema typami (`DT` + `CYKLICZNE-INNE` + `FESTYN`) → trzy
   eventy w jednej transakcji; błąd walidacji trzeciego → zero eventów (rollback);
3. `klucz_zapisu` z listą zajęć: powtórka → `powtorka:true`, liczniki bez zmian;
4. wynik wizyty bez żadnego chipa → zapis przechodzi, `status_realizacji`
   ustawiony, `uwagi` z sygnaturą `[data · nazwisko z sesji]`, dopisanie nie
   nadpisuje poprzedniej notatki;
5. DT z samą datą przechodzi (P27 w v5); status `03.` ustawia tylko event DT —
   zapis samego FESTYN-u statusu nie zmienia;
6. typ przedszkolny placówki → chip Cykliczne zapisuje `CYKLICZNE-PRZEDSZKOLE`
   w trybie „daty";
7. stare warianty nietknięte: payload v4 sprzed E5 przechodzi identycznie
   (dowód „stare API bez zmian"), szablony v1–v4 nie ładują
   `formularz_wspolne.js`;
8. endpoint geografii: jedna oś przed M6 (miejscowość), format `{osie:[…]}` —
   test kontraktu, na którym stoi E8.

`test_scenariusze.py`:
1. **spójność typów**: każda wartość `TYPY_CYKLICZNE` obecna w seedzie słownika
   `typ_eventu` (zapora na powrót rozjazdu z E0);
2. event `CYKLICZNE-INNE` widoczny w `events_for_month` i w zajętości trenera
   (lekcja 10.08: zapis, którego kalendarz nie pokazuje, jest gorszy niż odmowa);
3. zakresy `/leady`: „W pracy" łapie `01.`–`02b.` a nie `03.`; „Jednorazówki/VR"
   nie łapie odwołanych (`sql_nieodwolane`); „Po terminie z historią" pokazuje
   szkołę PO auto-zwrocie temu handlowcowi, któremu ją zabrano, i nie pokazuje
   jej w „Całej mojej bazie";
4. sortowanie: lead ze statusem pośrednim i terminem ląduje nad leadem `03.`;
5. `/baza`: zakładki niosą parametr `handlowiec`, plakietka `moj_filtr` obecna.

---

## 8. Ryzyka — gdzie ten formularz może zgubić pracę handlowca

1. **Nowy typ niewidoczny w kalendarzu** (precedens 10.08, pół dnia szukania):
   zapora — `TYPY_CYKLICZNE` jako jedyne miejsce + testy spójności (7.2, 7.-s1).
2. **Słownik prod uboższy niż kod** (dziś: `CYKLICZNE-PRZEDSZKOLE`): zapis
   przechodzi, a późniejsza edycja odbija się od twardej blokady — handlowiec
   widzi „błąd przy poprawianiu", czyli klasyczne „aplikacja zgubiła". Zapora:
   E0 od ręki + test spójności.
3. **Kaskada ukrywa wypełnioną sekcję**: handlowiec wpisał DT, odznaczył chip,
   zapisał — myśli, że DT poszło. Zapora: ostrzeżenie przy zapisie (jawne,
   nie blokujące) + dane żyją w szkicu.
4. **Częściowy zapis wielu zajęć**: bez rollbacku całości powstaje lead
   z połową zajęć i handlowiec nie wie, co dosłać (dokładnie problem, przed
   którym broni „formularz zapisuje JEDNYM żądaniem"). Zapora: jeden commit,
   test 7.2; `MAX_TERMINOW_CYKLU` = odmowa, nie obcięcie (jak dziś).
5. **Dubel po zerwanym LTE przy liście zajęć**: `klucz_zapisu` musi obejmować
   CAŁY payload — nie klucz per zajęcie. Zapora: mechanizm bez zmian + test 7.3.
6. **E3 przed E2**: handlowiec traci listę zadań. Zapora: twardy warunek
   wejścia E3 („E2 na produkcji i odebrane").
7. **Refaktor starych wariantów przy okazji modułu**: regresja w ekranie,
   którym klient właśnie porównuje układy. Zapora: moduł używany tylko przez
   v5, test 7.7.
8. **Rozjazd statusu i grafiku**: gdyby FESTYN/VR ustawiały `03. DT umówione`,
   raporty „ile DT" kłamią. Zapora: reguła „status `03.` ustawia wyłącznie
   event DT" + test 7.5.
9. **Przełączenie geografii ze starymi danymi** (E8 przed M5/M6): puste listy =
   „zniknęły szkoły". Zapora: adapter po stronie serwera + warunek wejścia E8
   związany wprost z etapami migracji; test kontraktu 7.8.
10. **Sygnatura w `uwagi` a przyszłe P16**: gdy uwagi przejdą na placówkę,
    dopisywanie musi przejść razem z nimi — odnotowane w P16, żeby nikt nie
    zaimplementował go bez tej wiedzy.

---

## 9. Pytania do klienta (każde z rekomendacją)

| # | pytanie | rekomendacja |
|---|---|---|
| 1 | Jednorazówka „szkoła/przedszkole/seniorzy": trzy wartości słownika czy jedna `JEDNORAZÓWKA` + odbiorca w polu? | jedna wartość + odbiorca w istniejącym polu `grupa` — kalendarz nie potrzebuje trzech kolorów, raport policzy po polu, słownik nie puchnie |
| 2 | „Cykliczne inne" (seniorzy, MDK): planowane regułą („co wtorek") czy pakietem dat? | przełącznik reguła/daty jak w v4 — mechanizm już istnieje (`FxCykl`), zero dodatkowego kodu |
| 3 | Czy „wizyta" ma być widoczna w kalendarzu? | nie — wizyta to wynik + notatka na leadzie (widać w karcie szkoły i w „Twoich szkołach"); kalendarz to grafik zajęć trenerów |
| 4 | Czy handlowiec w terenie kiedykolwiek wpisuje `START` (inaugurację grupy)? | nie — START powstaje u koordynatora/z importu; w kaskadzie go nie ma |
| 5 | Nazwisko przy notatce: automatyczny podpis z sesji zamiast pola do wpisania? | tak — pole ręczne pozwoliłoby podpisać się cudzym nazwiskiem (zasada „właściciel z sesji"); podpis widoczny przy notatce dla następnego PH |
| 6 | „Po terminie": co dokładnie ma być widoczne — lista szkół, które spadły, z datą zwrotu i notatkami? | tak, tylko-do-odczytu z historii zmian; bez możliwości „odzyskania" z tej listy (przypisuje wyłącznie koordynator — decyzja Kasi z 08.08) |
| 7 | Kolejność: najpierw filtry + kolumna efektu w „Twoich szkołach", dopiero potem zniknięcie zakładki z formularza — akceptujesz przejściowy tydzień z jednym i drugim? | tak — odwrotna kolejność zostawia handlowców bez listy zadań |
| 8 | Zoom na iPhone: zostawić aplikację „z ikony" bez zoomu (naprawiamy mieszczenie się ekranów), czy zmienić tryb PWA i odzyskać zoom kosztem paska przeglądarki? | zostawić standalone — po poprawce topbara i mobile-first v5 zoom przestaje być potrzebny; pasek przeglądarki na 6-calowym ekranie to strata miejsca na pracę |
| 9 | Placówki „cyklicznych innych" (MDK, kluby seniora): wystarczą istniejące typy `05. Instytucja kultury` / `06. Inna`? | tak — nie dokładać typów, dopóki nie ma placówek, które się nie mieszczą |
| 10 | Który wariant jest dziś dla Kasi „rekomendowany" (w wyborze formularzy v3 nosi tę etykietę) — utrzymać do końca testów v5? | tak, v3 zostaje „rekomendowany", v5 wchodzi jako „testowy — kaskada"; etykiety zmieniamy dopiero decyzją o zwycięzcy |

---

## Kolejność wykonania (podsumowanie zależności)

```
E0 (słownik prod)  ──────────────► przed poniedziałkiem
[poprawka mobilna Pawła] ────────► ZROBIONA 23.08 (commit 45c11a2)
E1 (/baza spójność) ─► E2 (filtry /leady) ─► E3 (zdjęcie zakładki)
                       └─ E2/E3 dopiero PO poniedziałku (ekrany w pracy)
pytania 1–4 ─► E4 (typy) ─► E5 (API zajęcia) ─┐
                            E6 (moduł JS) ────┴─► E7 (ekran v5)
                       └─ E5/E6/E7 KIEDYKOLWIEK: v5 to piąty przycisk
                          na /formularz, nikt nie wchodzi tam przypadkiem
migracja RSPO M5+M6 ─────────────────────────────► E8 (kaskada powiatowa)
wygaszanie v1–v4: POZA planem, osobna decyzja po testach v5
```
