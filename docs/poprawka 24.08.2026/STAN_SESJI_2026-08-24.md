# Stan sesji — poniedziałek 24.08.2026

Plik do przeczytania NA STARCIE następnej sesji, **przed** czymkolwiek innym.
Poprzedni: `docs/poprawka 23.08.2026/STAN_SESJI_2026-08-23.md`.

| | |
|---|---|
| Gałąź | `poprawki-2026-08`, ostatni commit **`48c198a`** |
| Produkcja | nietknięta, `main` = `6a3e181`; cofnięcie: tag `przed-poprawkami-2026-08-20` |
| Demo | **nadal stoi na `main`** — klient NIE WIDZI ani jednej z tych zmian |
| Testy | 10 plików, **896 sprawdzeń** + 93 (`test_parsers`), komplet OK |
| Profil `test` | **1618 placówek**, 1593 z numerem RSPO, 69 eventów |
| Profil `prod` | **NIETKNIĘTY** — 545 placówek, zero RSPO, zero powiatów |

---

## 1. Co się stało w jednym zdaniu

Baza przestała być listą 545 szkół z arkusza i stała się **lustrem rejestru
RSPO w zakresie firmy**: 1618 placówek, filtrowanych po powiatach, pokrywających
rejestr co do wiersza. Do tego powstał piąty formularz (v5) z kaskadą
powiat → miejscowość → placówka.

---

## 2. Commity tej sesji (od `093f636`)

| commit | co |
|---|---|
| `2831cd1` | **M7a** — 732 przedszkola i punkty; w bazie nie było ani jednego |
| `80c6f69` | **formularz v5** — piąty przycisk, kaskada, API rozszerzone o `zajecia` |
| `c348da3` | **M5+M6** — powiat jako oś filtrowania; Czeladź przestaje znikać |
| `5b1b798` | kaskada v5: miejscowości tylko z wybranego powiatu, z rejestru |
| `7a1c115` | 29 domów kultury, ognisk i ośrodków |
| `ae609d6` | **M3** — numery RSPO dla 514 z 545; worki powiatowe rozpakowane |
| `d7fa8da` | 34 brakujące szkoły podstawowe; numer szkoły wchodzi do tożsamości |
| `42ecc4f` | zespoły wg wariantu ostrożnego — wyszło 0 do dołożenia |
| `232233a` | **pełne pokrycie**: wszystkie 278 zespołów, 0 braków wobec rejestru |
| `48c198a` | katalog `do_sprawdzenia_recznego` + plik 25 placówek bez numeru |
| `ffbafa0` | stan i plan po 24.08 (pierwsze podejście do kontaktu w v5) |
| — | zakładanie placówek wypadło z formularza; kontakt nadpisywany zawsze |

---

## 3. Stan bazy `test` — liczby kontrolne

```
placówki 1618   leady 1618   eventy 69   z numerem RSPO 1593   bez numeru 25

01. Szkoła podstawowa                573
02. Przedszkole miejskie (PM)        468
03. Przedszkole prywatne (PP)        264
04. Zespół szkolno-przedszkolny      278
05. Instytucja kultury                29
04. Inna                               6
```

**Pokrycie rejestru: 0 wierszy bez odpowiednika** (typy klienta × 17 obszarów =
1589 wierszy rejestru). Nadwyżka 29 = 25 rekordów klienta bez numeru + 4
ogólnokształcące szkoły muzyczne I stopnia (typ spoza listy, klient obrabia je
od początku).

Powiaty: wszystkie 1618 mają powiat poza jednym (`SP 5`, id 532, bez
miejscowości — znane P28). Mikołowski 88 = 88 w rejestrze.

---

## 4. Ustalenia, które zmieniają sposób myślenia o tej bazie

**Import urwał słowo „powiat" i to jest źródło połowy zgłoszeń.** W pliku
klienta były `09. Pszczyna powiat` i `15. Będzin powiat`; w bazie zostało
`09. Pszczyna` i `15. Będzin`. Czeladź nie zniknęła — wpadła do worka razem
z 16 innymi miejscowościami. Po M3 68 rekordów odzyskało prawdziwą miejscowość.
Czeladź ma dziś 12 placówek (3 szkoły, 9 przedszkoli).

**Powiat dało się nadać BEZ numerów RSPO.** To była cała sztuka etapu M5: numery
wymagają decyzji człowieka przy kilkudziesięciu wierszach, a przełączenie filtrów
bez powiatu schowałoby handlowcom całą bazę. Nazwa miejscowości wskazuje jeden
powiat w 22 z 23 wartości słownika; jedyny wyjątek (`Psary` — będziński
i lubliniecki) rozstrzyga reguła „powiat, po którym firma jeździ, wygrywa".

**Miejscowość przestała być pozycją słownika** (`text` w `PLACOWKA_FIELDS`).
Musiała, bo miejscowości w zakresie jest ~150, w tym wsie, których słownik nigdy
nie zawierał — twarda blokada zamieniłaby każdą nową wieś w rekord NIE DO
POPRAWIENIA w karcie. Słownik `miasto` zostaje w bazie: używa go tabela `aliasy`
przy imporcie arkuszy klienta.

**Listy filtrów idą z DANYCH, listy formularza z REJESTRU.** To wygląda na
niekonsekwencję i nią nie jest: filtr po miejscowości bez placówek daje pustą
tabelę (marnuje kliknięcie), a formularz służy do ZAKŁADANIA placówki, więc musi
mieć nazwę, w której nas jeszcze nie ma. W powiecie będzińskim to różnica
17 nazw (nasze) wobec 22 (rejestr).

**Zakres rejestru w formularzu przycinamy obszarami, nie powiatem.** Bez tego
przy powiecie gliwickim — z którego bierzemy samą gminę Knurów — formularz
proponowałby 31 miejscowości od Toszka po Żernicę.

**`RSPO podmiotu nadrzędnego` bywa w rejestrze PUSTE.** W całym Orzeszu nie ma
go ani jedna placówka, choć ZESPÓŁ SZKOLNO-PRZEDSZKOLNY NR 6 stoi pod tym samym
adresem co SZKOŁA PODSTAWOWA NR 6. Poleganie na tej kolumnie kazałoby dołożyć
zespół jako „niewidoczny w bazie" i zrobić dubla.

**504 z 536 rekordów klienta ma w adresie samą ulicę, bez numeru budynku.**
Dlatego porównanie adresów musi umieć obie postaci — inaczej ZESPÓŁ
SZKOLNO-PRZEDSZKOLNY NR 17 przy Sztolniowej 29b wygląda na nieobecny, choć stoi
tam nasza SP NR 36 zapisana jako „ul. Sztolniowa".

**Numer szkoły jest częścią tożsamości.** „MIEJSKA SZKOŁA PODSTAWOWA NR 7
W KNUROWIE" po odrzuceniu słów pustych i nazwy miejscowości nie zostawia ani
jednego znaczącego słowa — numer wypadał, bo ma jeden znak. Efekt: szkoła nr 9
„rozpoznawała się" jako nasza nr 7.

**Decyzja Pawła o zespołach: pokrycie bije czystość.** Weszły wszystkie 278,
także 92 złożone z techników i 186 stojących obok własnych składowych. Skutek:
pod jednym adresem stoją trzy rekordy (zespół, jego szkoła, jego przedszkole).
Rozróżnia je typ `04. ZSP`, więc da się je zdjąć jednym chipem, a
`doloz --cofnij --zapisz` usuwa je bez śladu.

---

## 5. Co powstało w kodzie

| plik | rola |
|---|---|
| `rejestr_rspo.py` | lustro rejestru (M1) — było |
| `obszary.py` | obszary działania, gmina bije powiat (M2) — było |
| **`geografia.py`** | powiat/gmina dla placówek, listy filtrów (M5, M8) |
| **`dokladanie.py`** | dołożenie z rejestru, wykrywanie dubli (M7) |
| **`dopasowanie.py`** | nadanie numerów RSPO, plik decyzyjny (M3) |
| `narzedzia/migracja_rspo.py` | CLI: `lustro`/`obszary`/`geografia`/`dopasuj`/`doloz`/`stan` |

Formularz v5: `templates/formularz5.html`, `static/formularz5.js`,
`static/formularz5.css`, trasy `/formularz/v5`, `/api/formularz/geografia`,
`/api/formularz/placowki`; API `/api/formularz` przyjmuje **dodatkowo** listę
`zajecia` (stare warianty wysyłają jak dotąd — jest na to test-zapora).

Wszystkie komendy migracji domyślnie **NIE ZAPISUJĄ** — bez `--zapisz` pokazują
liczby i wychodzą.

---

## 6. Co dalej, w kolejności

1. **Wdrożenie na demo** — dalej blokuje wszystko inne. Klient nie widzi ANI
   JEDNEJ zmiany z 20–24.08. Instrukcja gotowa i **przećwiczona lokalnie na
   kopii bazy produkcyjnej**: `docs/poprawka 24.08.2026/WDROZENIE_NA_DEMO.md`.
   Dwa polecenia:
   ```bash
   cd /home/ubuntu/apps/demo-ph.silesia3d.site
   git fetch origin && git checkout poprawki-2026-08 && ./wdroz.sh demo
   ./narzedzia/migracja_na_demo.sh ~/rspo_2026_08_13.csv
   ```
   Na serwer trzeba przenieść **jeden plik** — rejestr CSV (41 MB). Arkusz
   klienta z numerami okazał się niepotrzebny: przy tej kolejności kroków
   dopasowanie po samym rejestrze trafia 520 z 545, czyli tyle samo.
2. **Plik `do_sprawdzenia_recznego/BEZ_RSPO_2026-08-24.xlsx`** do Kasi — 25
   placówek, dwie kolumny decyzji („numer RSPO" i „scalić z id").
3. **M4 — scalanie par.** Narzędzia jeszcze NIE MA; piszemy je, gdy wróci
   wypełniony plik, bo dopiero wtedy wiadomo, ile par realnie jest.
   Kolejność w scalaniu jest krytyczna: eventy i log przepinamy PRZED
   skasowaniem rekordu (`ON DELETE CASCADE` zabiera DT bez śladu).
4. **Migracja na `prod`** — dopiero po tygodniu obserwacji dema. Baza
   produkcyjna zmienia się gotowym, sprawdzonym skryptem, nie ekranem Import
   (lekcja z 10.08 zostaje w mocy).
5. Formularz v5: dokończenie (podpowiedź trenera z v3, nowe typy zajęć E4 po
   decyzjach Kasi, wspólny moduł JS E6).
6. Konto handlowca dla Zuzi · P29 „zgłoś do usunięcia" · P28 `SP 5` bez
   miejscowości (jedyny rekord bez powiatu).

**Czego NIE zaczynać:** etapów E2 i E3 z `PLAN_FORMULARZA.md` — dotykają
„Twoich szkół", czyli ekranu, na którym handlowcy pracują.

---

## 6b. Zgłoszenia z wieczora 24.08 — zrobione

**Zakładanie placówek wypadło z formularza (Kasia).** „Usuń tę możliwość, bo to
powoduje, że PH wpisują coś z ręki sami i będą się dublować rzeczy, a wpisują
nazwy jak popadnie". Przycisk zniknął z **pięciu** wariantów; w jego miejscu
stoi podpowiedź kierująca najpierw do filtra powiatu. Blokada przy ZAPISIE:
`/api/formularz` odmawia handlowcowi bloku `placowka` (403),
`api_lead_create` doszedł do `TYLKO_KOORDYNATOR`. Koordynator zakłada dalej,
na ekranie „Baza". Testy: `test_uprawnienia.py` (obie drogi), `test_formularz.py`
(komplet wariantów), `test_logowanie.py` (L6 przepisane — podszycie sprawdzamy
teraz na szkole niczyjej, bo tam handlowiec dziś w ogóle może się podpisać).

⚠️ **Na `prod` ta zmiana ma sens dopiero razem z bazą RSPO** — produkcja ma 545
placówek i zero powiatów, więc sam zakaz zabrałby handlowcowi możliwość zapisania
wizyty w przedszkolu spoza tych 545. Obie rzeczy jadą tą samą gałęzią; nie
rozdzielać ich przy wdrożeniu.

**Kontakt w v5 nadpisywany ZAWSZE (Paweł, drugie zgłoszenie tego samego).**
Pierwsza poprawka rozróżniała kontakt podstawiony od wpisanego ręcznie i ten
drugi chroniła. Nie działa: sekcja kontaktu jest zakryta, dopóki placówka nie
jest wybrana, więc każda wpisana wartość dotyczy POPRZEDNIEJ szkoły. v5 robi
teraz to samo co v2–v4 od czerwca — nadpisuje wszystkie trzy pola, także pustą
wartością, i mówi o podmianie.

**v5 robił dubla placówki sam z siebie.** Przy placówce bez leada wysyłał blok
`placowka` z nazwą przepisaną z rekordu; serwer bez `lead_id` po prostu wstawia
wiersz. Teraz jedzie `placowka_id`, a serwer zakłada lead do ISTNIEJĄCEGO
rekordu — z testem na liczbę placówek i leadów przed zapisem i po nim.

**Prowadzący przy zajęciach cyklicznych.** Sekcja cykliczna v5 rysowała sam
harmonogram, więc definicje jej pól (prowadzący, godziny, sprzęt, grupa, uwagi)
były MARTWYM kodem — cykl dało się umówić, ale nie dało się powiedzieć, kto go
poprowadzi. Pola rodzaju rysuje teraz jedna funkcja wspólna dla obu gałęzi.
Prowadzący **nieobowiązkowy** (decyzja Pawła).

**Panel dostępności prowadzących w v5**, przeniesiony z v3 w komplecie:
kandydaci w grupach, plakietka statusu wybranej osoby, „co się dzieje tego
dnia". Różnica wobec v3 wynika z kaskady — panel jest PRZY SEKCJI, bo v5 umawia
kilka rzeczy naraz i każda ma własną datę. Odpowiedzi buforowane kluczem
`data|od|do|miasto`, bo `rysujSekcje()` przerysowuje wszystko przy każdym
kliknięciu chipa.

Testy po tej rundzie: **11 plików, 959 sprawdzeń + 93 (`test_parsers`) + 17
w node**, komplet OK.

---

## 6c. Próba wdrożenia — przećwiczona lokalnie 24.08 wieczorem

Cała ścieżka migracji przeszła na **kopii bazy produkcyjnej** (`data/prod`,
545 placówek) w osobnym `DATA_DIR`, czyli na tym, co realnie stoi na demo:

```
545 placówek → 1613     eventy 65 → 65 (BEZ ZMIAN)
numery RSPO: 520 z 545, 25 do decyzji Kasi
mikołowski 88 (= rejestr)   Czeladź 18   bez powiatu 1 (znane P28)
```

Trzy rzeczy, które ta próba ustaliła i których nie dało się przewidzieć:

- **Arkusz klienta przy `dopasuj` jest niepotrzebny.** Przy kolejności
  `geografia` PRZED `dopasuj` czyste nazwy miejscowości wystarczą: 520 z 545
  po samym rejestrze. Na serwer jedzie więc JEDEN plik zamiast dwóch, i to
  publiczny rejestr zamiast arkusza z danymi osobowymi.
- **Druga tura `geografia` nie jest zapasowa.** Po nadaniu numerów 520 rekordów
  bierze powiat i miejscowość z REJESTRU zamiast z nazwy — to tam Czeladź
  wychodzi z worka „15. Będzin powiat". Bez tego kroku zostaje w worku.
- **`| head` w skrypcie z `pipefail` zabija polecenie.** `head` zamyka potok,
  python dostaje SIGPIPE, skrypt kończy się „błędem", którego nie było
  (potknąłem się o to najpierw w PowerShellu, przy `Select-Object -First`).

Wynik: `narzedzia/migracja_na_demo.sh` — jedno polecenie zamiast dwunastu,
z kopią bazy jako pierwszym krokiem i poleceniem cofającym na końcu.
Instrukcja: `WDROZENIE_NA_DEMO.md`.

---

## 7. Grabie z tej sesji

**Podgląd, który liczy inaczej niż zapis, jest gorszy niż jego brak.**
`dokladanie.przygotuj()` jest wspólnym jądrem podglądu i zapisu właśnie dlatego.

**Reguła wykrywania dubli musi znać numer.** Bez tego „miejska szkoła
podstawowa" to same słowa puste i wszystko skleja się ze wszystkim (289
fałszywych trafień w pierwszym podejściu).

**`git add <katalog>` dalej jest groźny.** Katalog `do_sprawdzenia_recznego`
i pliki `docs/poprawka */*.xlsx` są w `.gitignore`; README zostaje, bo opisuje
procedurę, a nie dane.

**Test opierający się na cudzym rekordzie zależy od kolejności bloków.**
`test_formularz.py:443` czyści `placowki` w połowie pliku — blok F7 zakłada
własne rekordy zamiast korzystać z „SP 2" z bloku F2.

**Sprawdzać ZAWARTOŚĆ, nie tylko liczbę.** 93 zespoły „bez składowych u nas"
wyglądały na brakującą bazę, dopóki nie policzyłem, co zawierają: 68 techników,
53 branżówki, 30 liceów i ani jednej podstawówki.
