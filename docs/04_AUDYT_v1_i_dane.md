# 04 — Audyt v1/v2 + inwentarz realnych danych klienta

Stan na 30.07.2026. Dokument ma dwie części:

* **CZĘŚĆ 1** — audyt kodu `leady_app` (v1) i `leady_app — kopia` (v2): plik po pliku,
  bugi z numerami linii, co brać do v3, luki funkcjonalne.
* **CZĘŚĆ 2** — inwentarz REALNYCH wartości w plikach klienta, moduł `parsers.py`
  dla v3, wynik przepuszczenia wszystkich danych przez parsery.

Artefakty powstałe razem z tym dokumentem:

| Plik | Rola |
|---|---|
| `leady_app_v3/parsers.py` | 10 funkcji czystych + dane `SLOWNIKI` / `ALIASY`. Bez Flask, bez DB, bez openpyxl. |
| `leady_app_v3/test_parsers.py` | 93 testy (`python test_parsers.py` → OK). Przypadki wyłącznie z realnych danych. |

## Werdykt w skrócie (5 punktów)

1. **Architektura v1 jest dobra, implementacja nie.** Do v3 bierzemy: `LEAD_FIELDS`
   jako jedno źródło definicji kolumn, tablicę `ALIASES` nazw kolumn klienta,
   zasadę „kalendarz = widok z danych", szkielet `find_collisions`, makro `tile`
   z pętlą po zdarzeniach. Routing, walidację, dostęp i import — przepisać.
2. **`leady_app — kopia` (v2) to wyłącznie reskin.** Cała logika Pythona jest bajt
   w bajt identyczna, zero naprawionych bugów. Z v2 bierzemy tylko warstwę
   prezentacji (`style.css` 310 linii vs 141, sticky nagłówki, tokeny `:root`) —
   po naprawie kolizji klasy `.bar` i po wyrzuceniu Google Fonts.
3. **Dwa bugi klasy „funkcja jest, ale nie działa"**: martwy ekran Słowniki
   (brak `id` w zapytaniu → błąd składni JS) i wyłączona detekcja kolizji trenera
   (`overlaps()` wymaga 4 godzin, źródło ma jedną). Oba są obiecane w README.
4. **Aplikacja w obecnym stanie nie może zobaczyć prawdziwych danych**: zero auth,
   zero CSRF, destrukcyjny import zaznaczony domyślnie, `debug=True` na `0.0.0.0`,
   root w kontenerze, SQLite bez WAL przy 2 workerach. A import na realnych plikach
   klienta i tak wczyta śmieci (nagłówki z wiersza 1 zamiast 4, jedna zakładka
   z sześciu, `max_row = 50500`, brak obsługi formuł z eksportu Google Sheets).
5. **Największa luka to model danych**, nie UI: 1 lead = max 1 DT, brak kalendarza
   zajęć cyklicznych, brak kolumn Julki (AA–AG), brak nazwy i typu placówki,
   brak RSPO, brak historii aktywności (bez niej „kontrola ruchu przed terminem"
   jest niewykonalna), brak ról. Z 23 nowo znalezionych luk **12 jest w skali S**
   i daje szybkie zwycięstwa na demo.

---

# CZĘŚĆ 1 — AUDYT KODU v1 / v2

Data: 2026-07-30. Zakres: **read-only audyt pod przepisanie na v3**.
Porównane kopie:

- **A** = `C:\XEN\AI-szkolenie\LIPIEC2026\leady_app\` (20.07.2026)
- **B** = `C:\XEN\AI-szkolenie\LIPIEC2026\leady_app — kopia\` (24.07.2026)

Kontekst wymagań wzięty z: `leady_app_v3\docs\01_USTALENIA_analiza.md`,
`WYMAGANIA_klient_docx.md`, `notatki-spotkanie-2026-07-24-silesia-3d.md`.

Skala werdyktów: **TAKE AS IS** / **TAKE WITH FIXES** / **REWRITE** / **DROP**.

Wynik `diff -rq` (bez `__pycache__`, `data/`): różnią się **11 plików** —
`app.py`, `Dockerfile`, `docker-compose.yml`, `DEPLOY.md`, `README.md`,
`static/style.css` i **wszystkie 5 szablonów**. Identyczne w obu kopiach:
`db.py`, `calendar_view.py`, `importer.py`, `exporter.py`, `parsers.py`,
`seed.py`, `static/app.js`, `requirements.txt`, `.dockerignore`, `.gitignore`.

---

## Plik: app.py

**Co robi:** wszystkie trasy Flask — 4 widoki (`/tabela`, `/kalendarz`, `/pulpit`,
`/slowniki`), REST-owe API do edycji inline (`PATCH/POST/DELETE /api/lead`,
`/api/slownik`), eksport XLSX, import XLSX. Buduje `SLOWNIK_FIELDS` i `INT_FIELDS`
z `LEAD_FIELDS` (metadane napędzają walidację).

**Liczba linii:** A = **249**, B = **253**.

**Werdykt: TAKE WITH FIXES** — struktura tras i pomysł „metadane napędzają
walidację" są dobre, ale warstwa bezpieczeństwa i walidacji jest do napisania od zera.

### Bugi i słabe punkty

1. **`app.py:147` — SQL budowany interpolacją `%` po nazwie kolumny:**
   ```python
   conn.execute("UPDATE leady SET %s=?, updated_at=datetime('now') WHERE id=?" % field, ...)
   ```
   Dziś *nie* jest to injection, bo `app.py:129` sprawdza `field not in LEAD_KEYS`
   (whitelist). Ale to jedna linijka od dziury: wystarczy, że ktoś doda pole
   dynamicznie albo poluzuje warunek. W v3: mapa `{klucz: "kolumna"}` +
   `sqlite3` z quotowaniem identyfikatora, nigdy `%`.
2. **`app.py:0` (całość) — ZERO autoryzacji.** Brak logowania, brak roli, brak
   sesji, brak `SECRET_KEY`. Każdy, kto zna URL, może przez `DELETE /api/lead/<id>`
   wykasować dowolny rekord, a przez `POST /import` z `tryb=replace` **wyczyścić całą
   bazę**. Wymóg klienta jest wprost przeciwny: *„koordynator odbiera mu dostęp"*
   (`WYMAGANIA_klient_docx.md` p.4) — model dostępu jest funkcją biznesową, nie dodatkiem.
3. **`app.py:223-238` — import bez CSRF, bez potwierdzenia, destrukcyjny domyślnie.**
   `replace = request.form.get("tryb") == "replace"` a w `base.html:27` radio
   `replace` jest `checked`. Jeden klik = `DELETE FROM leady` (`importer.py:137`).
   Brak backupu, brak transakcji z rollbackiem, brak podglądu „co się wgra".
   Dodatkowo dowolna strona w internecie może wysłać ten multipart POST (brak CSRF).
4. **`app.py:237` — `os.remove(tmp)` poza `try/finally`.** Jeśli `import_into`
   rzuci (a rzuci przy byle jakim pliku), plik zostaje, połączenie `conn` z linii 234
   **nie jest zamknięte**, a wyjątek leci do Werkzeuga.
5. **`app.py:249` — `debug=True` + `host="0.0.0.0"`.** Interaktywna konsola
   Werkzeuga = zdalne wykonanie kodu. W Dockerze ratuje nas gunicorn, ale
   README (`README.md:40`) każe uruchamiać `python app.py`.
6. **`app.py:68-80` — wyciek połączenia przy błędzie.** `conn = get_conn()` w
   linii 68, `conn.close()` w 80; między nimi `cv.build_grid`/`month_label`, które
   **rzucają na złym parametrze `m`**. Brak `try/finally`, brak `teardown_appcontext`.
   To samo w każdym widoku (`tabela`, `pulpit`, `slowniki_view`).
7. **`app.py:70` — brak walidacji `m` → 500.** `/kalendarz?m=abc` →
   `calendar_view.py:52` `y, m = month.split("-")` → `ValueError`.
   `/kalendarz?m=2026-13` → `MIESIACE[13]` → `IndexError`.
   `/kalendarz?m=0000-00` → `calendar.monthrange` → `IllegalMonthError`.
   Trzy różne 500-tki z samego query stringa.
8. **`app.py:70` — zły domyślny miesiąc.** `months[0]` to **najstarszy** miesiąc
   (`calendar_view.py:46` `ORDER BY m` rosnąco). Wchodząc na kalendarz w lipcu
   widzisz np. wrzesień 2025. Powinno być: miesiąc bieżący, a jeśli pusty — najbliższy przyszły.
9. **`app.py:92, 98, 106` — reguła biznesowa zakodowana jako prefiks `'03.%'`.**
   `status_realizacji LIKE '03.%'` = „DT umówione". Klient **prosi o nowy status**
   („DT w trakcie umawiania", notatki k.1 p.2) — wstawienie go przenumeruje listę
   i `03.` zacznie znaczyć coś innego. Do tego `exporter.py:47` używa **innej**
   reguły (`"DT um" not in st`), a `tabela.html:44` trzeciej (`startswith('03.')`).
   Trzy definicje tego samego pojęcia w jednym repo.
10. **`app.py:140-144` — koercja `int` tylko dla 2 pól; brak walidacji `date`/`time`.**
    `PATCH {"field":"deadline","value":"jutro"}` zapisze się bez mrugnięcia.
    Potem `deadline < today()` (`app.py:152`) porównuje **stringi** —
    `"jutro" < "2026-07-30"` = `False`, więc rekord po terminie nigdy nie zapali się
    na czerwono. To samo dla `data_dt` → wpis wypada z kalendarza
    (`substr(data_dt,1,7)` nie trafi w żaden miesiąc) i **nie ma żadnego sygnału**, że coś zginęło.
11. **`app.py:157-166` — `api_create` omija wymuszanie słownika.**
    `POST /api/lead {"handlowiec":"02. Olaszewska"}` wchodzi do bazy bez sprawdzenia,
    mimo że `PATCH` (linia 134-139) by to odrzucił. Dokładnie ten błąd, który system
    ma eliminować (`01_USTALENIA`, sekcja „rozjazdy": literówka `02. Olaszewska`).
12. **`app.py:169-175` — twardy `DELETE FROM leady`.** Sprzeczne z zasadą przyjętą
    dla v3: *„Nic nie jest usuwane ani kopiowane"* (`01_USTALENIA` E.3). Brak soft-delete,
    brak audytu, brak „kto i kiedy".
13. **`app.py:202-208` — usunięcie wartości ze słownika nie sprawdza referencji.**
    Kasujesz „03. Majewska", a 12 leadów nadal ma tę wartość w `prowadzacy_dt`.
    Efekt: w `tabela.html:54-59` `<select>` nie ma pasującej `<option>` → **pokazuje
    puste** → pierwszy przypadkowy `change` nadpisuje trenera. Cicha utrata danych.
14. **`app.py:185-186, 196` — `kolor` przyjmowany bez walidacji** i wstawiany do
    atrybutu `style` (`slowniki.html:19`, `kalendarz.html:41`, `tabela.html`).
    Jinja escapuje cudzysłowy, więc XSS-a nie ma, ale CSS injection
    (`red;position:fixed;inset:0`) — owszem. Waliduj `^#[0-9a-fA-F]{6}$`.
15. **`app.py:246` — `bootstrap()` na poziomie importu modułu.** Przy `--workers 2`
    (Dockerfile:21) dwa procesy jednocześnie robią `init_db` + `seed_slowniki` +
    ewentualny import startowy. `INSERT OR IGNORE` ratuje słowniki, ale nie ratuje
    `import_into(replace=True)`, które dwa razy wyczyści i wgra tabelę.
16. **`app.py:52-53` — `LIKE` bez escapowania i ASCII-only.**
    `p += ["%%%s%%" % q] * 4` — znaki `%` i `_` wpisane przez użytkownika działają
    jako wildcard. Gorzej: `LIKE` w SQLite jest case-insensitive **tylko dla ASCII**,
    więc szukanie `łaziska` nie znajdzie `Łaziska Górne`. Przy polskich nazwach szkół
    i miast to wada użytkowa, nie kosmetyka.
17. **`app.py:55` — nieograniczony `fetchall()` bez paginacji.** Dziś 70 leadów.
    Docelowo `BAZA` = 980 szkół, a po RSPO (szkoły + przedszkola + instytucje kultury,
    notatki k.1 p.3) — kilka tysięcy. `tabela.html` renderuje ~26 inputów i 5 `<select>`
    (po ~20 `<option>`) na wiersz → przy 980 wierszach to ~120 tys. elementów DOM.
    Strona nie do użycia.
18. **`app.py:54` — `ORDER BY` z NULL-ami bez intencji.** SQLite w `ASC` daje NULL
    pierwsze, więc leady nieprzypisane (`handlowiec IS NULL`) lądują na górze.
    Przypadkowo sensowne, ale nigdzie nie zadeklarowane — a klient chce „wybrane szkoły
    na tydzień **do góry**" (notatki k.1 p.4), czyli własną kolejność (pinning).
19. **`app.py:74` — logika weekendu przemycona w wyrażeniu warunkowym:**
    `weekend = (widok != "tygodnie") if wk is None else (wk == "1")`.
    Działa, ale to reguła prezentacji ukryta w kontrolerze; każdy inny widok
    (plansza STARTY) będzie musiał ją powtórzyć.
20. **Brak walidacji kolizji przy zapisie.** Klient napisał wprost:
    *„żeby nie mógł trener 2× mieć aktywności"* (notatki k.2). `PATCH` nie sprawdza
    nic — kolizja jest tylko *raportowana* po fakcie na pulpicie. Brak `409` /
    ostrzeżenia „ten trener ma już DT o 8:00 w Knurowie".

### Warte przeniesienia do v3 verbatim

- `app.py:19-21` — metadane jako źródło walidacji, wzorzec do utrzymania:
  ```python
  SLOWNIK_FIELDS = {f[1]: f[2].split(":", 1)[1]
                    for f in LEAD_FIELDS if f[2].startswith("slownik:")}
  INT_FIELDS = {f[1] for f in LEAD_FIELDS if f[2] == "int"}
  ```
- `app.py:133-139` — sam **pomysł** wymuszania słownika przy każdym zapisie
  (do przeniesienia jako reguła, ale realizowana w warstwie serwisowej, nie w widoku):
  ```python
  if field in SLOWNIK_FIELDS and value is not None:
      allowed = slownik_values(conn, SLOWNIK_FIELDS[field])
      if value not in allowed:
          return jsonify(ok=False, error="Wartość spoza słownika"), 400
  ```
- `app.py:96-98` — definicja „po terminie" jako zapytanie (do przeniesienia po
  zamianie `LIKE '03.%'` na flagę statusu):
  ```sql
  SELECT * FROM leady WHERE deadline IS NOT NULL AND deadline<?
  AND status_realizacji NOT LIKE '03.%' ORDER BY deadline
  ```
- `app.py:104-107` — agregat per handlowiec (baza pod „minimum na tydzień"):
  ```sql
  SELECT handlowiec, COUNT(*) c,
  SUM(CASE WHEN status_realizacji LIKE '03.%' THEN 1 ELSE 0 END) u
  FROM leady GROUP BY handlowiec ORDER BY c DESC
  ```

### B vs A

B ma **nowsze i lepsze**: przekazuje `colors = trener_colors(conn)` do `tabela.html`
(B:58, B:62) i do `pulpit.html` (B:109, B:114) → kropki kolorów trenera w rejestrze
i na liście kolizji, plus `month_label` na pulpicie. Reszta różnic to zmiana portu
5000→5001, żeby dwie kopie chodziły równolegle (B:252-253) — czysto operacyjne.
**Żaden bug z listy 1-20 nie został w B naprawiony.**

---

## Plik: db.py

**Co robi:** ścieżki do bazy, `LEAD_FIELDS` (jedno źródło definicji 26 kolumn:
etykieta / klucz / typ), `SLOWNIK_RODZAJE`, `get_conn`, `init_db` (DDL z `LEAD_KEYS`),
helpery `slownik`, `slownik_values`, `trener_colors`.

**Liczba linii:** **99** (identyczne w A i B).

**Werdykt: TAKE WITH FIXES** — `LEAD_FIELDS` jako pojedyncze źródło prawdy o
kolumnach to najlepszy pomysł w całym projekcie i musi przejść do v3. Warstwa
DDL/połączeń jest do przepisania.

### Bugi i słabe punkty

21. **`db.py:85-90` — `slownik()` nie zwraca `id`**, a szablon `slowniki.html:17`
    i `:22` woła `ustawKolor({{ item.id }}, ...)` / `usunSlownik({{ item.id }}, this)`.
    `item.id` → Jinja `Undefined` → renderuje się **pusty string** → w HTML wychodzi
    `onchange="ustawKolor(, this.value)"` = **SyntaxError w JS**.
    **Cała zakładka Słowniki jest funkcjonalnie martwa** w zakresie zmiany koloru
    i usuwania pozycji (dodawanie działa, bo idzie po `rodzaj`).
    To najpoważniejszy „ciche zepsucie" w repo — i jest w **obu** kopiach.
    Fix: `SELECT id, wartosc, kolor ...`.
22. **`db.py:61-82` — brak jakiejkolwiek migracji.** `CREATE TABLE IF NOT EXISTS`
    z kolumnami wygenerowanymi z `LEAD_KEYS`. Dodanie pola do `LEAD_FIELDS`
    (a v3 dodaje: typ placówki, RSPO, nazwa, kolumny Julki) **nie zmieni istniejącej
    tabeli** — dostaniesz `OperationalError: table leady has no column named ...`
    przy pierwszym INSERT z `importer.py:141`. Potrzebny `PRAGMA user_version` +
    kroki migracyjne.
23. **`db.py:62-63` — DDL składany `%`-interpolacją.** Dziś bezpieczne (`LEAD_KEYS`
    są stałe), ale ta sama technika co bug #1. Kolumny typu wybierane przez
    `if k not in ("ilosc_klas","ilosc_dzieci")` — hardkod nazw obok deklaratywnego
    `LEAD_FIELDS`, w którym typ *już jest* (`"int"`). Duplikacja prawdy.
24. **`db.py:55` — `sqlite3.connect` bez `timeout` i bez `PRAGMA journal_mode=WAL`.**
    Przy `--workers 2` + zapisach inline z każdej komórki → `database is locked`
    (domyślny timeout 5 s, brak WAL = writer blokuje readerów).
25. **`db.py:57` — `PRAGMA foreign_keys = ON` bez ani jednego klucza obcego.**
    `leady.handlowiec` to wolny TEXT, `slowniki` nie jest z niczym powiązane.
    Deklaracja spójności bez spójności.
26. **`db.py:66-79` — brak indeksów** na `data_dt`, `handlowiec`,
    `status_realizacji`, `prowadzacy_dt`, `deadline` oraz brak `UNIQUE` czegokolwiek
    (import w trybie „dopisz" = duplikaty bez ostrzeżenia).
27. **`db.py:11-38` — model płaski, 1 lead = max 1 DT.** Nie ma tabeli eventów.
    Kalendarz jest liczony z `leady.data_dt`, więc **jedna szkoła nie może mieć
    dwóch DT**, a zajęcia cykliczne są wciśnięte w te same wiersze jako
    `cykl_dzien/cykl_godz_od`. To fundament, który v3 musi rozbić
    (`01_USTALENIA` E.2 — dokładnie ta decyzja).
28. **`db.py:31` — `cykle` jako `"text"`, choć w źródle to słownik `01. Tak/02. Nie`**
    (`01_USTALENIA` tab. słowników). Niespójność z `dt`, które słownik ma.
29. **`db.py:32` + `app.py:134-139` — `cykl_dzien` jako **jedna** wartość słownikowa.**
    Realne dane mają `Poniedziałek i piątek` (`01_USTALENIA`, „Zbitki w danych",
    kolumna V). Po imporcie taka wartość siedzi w bazie, ale UI **nie da jej zapisać
    ponownie** (spoza słownika) — użytkownik nie może edytować własnych danych.
30. **`db.py:11-38` — brakuje pól, które w źródle istnieją:** nazwa placówki
    (jest tylko `numer_placowki` = „MSP 2"), typ placówki (szkoła / przedszkole /
    instytucja kultury), nr RSPO, kolumna Q `mail propozycja lub ustalenie DT`,
    oraz **cały blok Julki AA-AG** (dane do umowy, standardy ochrony małoletnich,
    oświadczenia trenerów, zaświadczenie o niekaralności, podanie o wynajem sali,
    umowa podpisana, Librus).
31. **`db.py:98` — `(r["kolor"] or "#888")`** — poprawnie traktuje `''` i `NULL`
    tak samo. To jeden z niewielu miejsc, gdzie NULL-e są obsłużone świadomie.

### Warte przeniesienia do v3 verbatim

- **Cała lista `db.py:11-38`** jako punkt wyjścia mapowania kolumn (do rozbudowy),
  wraz z komentarzem `# Pola leada. Kolejność = kolejność kolumn w tabeli i w eksporcie XLSX.`
- `db.py:40` — `LEAD_KEYS = [f[1] for f in LEAD_FIELDS]`
- `db.py:93-99`:
  ```python
  def slownik_values(conn, rodzaj):
      return [r["wartosc"] for r in slownik(conn, rodzaj)]

  def trener_colors(conn):
      return {r["wartosc"]: (r["kolor"] or "#888") for r in slownik(conn, "trener")}
  ```
- `db.py:6` — `DATA_DIR` z ENV z sensownym fallbackiem (ważne dla Dockera):
  ```python
  DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
  ```

### B vs A
Identyczne. Bug #21 (brak `id` w `slownik()`) jest w obu.

---

## Plik: calendar_view.py

**Co robi:** kalendarz jako **widok** liczony z tabeli `leady`:
`events_for_range`, `available_months`, `month_label`, `find_collisions`,
`build_grid` (macierz trener × dni miesiąca) i `build_weeks` (tygodnie pionowo).

**Liczba linii:** **159** (identyczne w A i B).

**Werdykt: TAKE WITH FIXES** — architektura („kalendarz to widok, nie malowana
plansza") jest dokładnie tym, czego wymaga `01_USTALENIA` E.2/E.6 i rozwiązuje
zgłoszony bug z `XLOOKUP`. Implementacja ma jednak trzy poważne błędy logiczne.

### Bugi i słabe punkty

32. **`calendar_view.py:99-103` + `parsers.py:99-103` — detekcja kolizji w praktyce
    nie działa.** `overlaps()` zwraca `False`, gdy brakuje **którejkolwiek** z czterech
    godzin:
    ```python
    if not (od1 and do1 and od2 and do2):
        return False
    ```
    W źródłowym arkuszu jest **jedna** kolumna „Godzina DT" (N), więc importer
    ustawia tylko `godz_dt_od`, a `godz_dt_do` zostaje `NULL`
    (`importer.py:84-88`). Wniosek: **dwa DT tego samego trenera tego samego dnia
    o tej samej godzinie nie zostaną wykryte jako kolizja.** Sztandarowa funkcja
    z notatek („żeby nie mógł trener 2× mieć aktywności") jest de facto wyłączona
    na realnych danych. Fix w v3: domyślny czas trwania DT (np. 4 h) albo
    reguła „ten sam trener + ten sam dzień + brak `do` ⇒ kolizja/ostrzeżenie".
33. **`calendar_view.py:126` vs `142-145` — dziura na granicy miesiąca w widoku
    tygodni.** `events_for_range(conn, month)` filtruje `substr(data_dt,1,7)=month`,
    ale `monthdatescalendar(y, m)` zwraca też dni z miesiąca poprzedniego i następnego
    (`in_month == False`). W tych komórkach **nigdy nic się nie pokaże**, mimo że DT
    tam istnieją. Klient akurat na tym styku pracuje: *„WRZESIEŃ startuje 2026-08-31"*
    (`01_USTALENIA`, layout kalendarza) — czyli pierwszy dzień pierwszego tygodnia
    września to 31 sierpnia i będzie **zawsze pusty**. Do tego `n_events`
    (`calendar_view.py:158`) liczy zdarzenia z miesiąca, więc licznik nie zgadza się
    z tym, co widać.
34. **`calendar_view.py:51-53` — `month_label` bez walidacji.**
    `MIESIACE[int(m)]` → `IndexError` dla `m>12`, `ValueError` dla nie-liczby,
    `ValueError: too many values to unpack` dla `"2026-07-01"`. Wywoływane z
    `app.py:82` bezpośrednio z query stringa → 500.
35. **`calendar_view.py:81` i `123` — `[int(x) for x in month.split("-")]`** —
    ten sam brak walidacji, powtórzony w dwóch funkcjach (`ValueError` → 500).
36. **`calendar_view.py:40` — sortowanie z podmianą NULL na `""`:**
    `key=lambda e: (e["data"], e["od"] or "", e["trener"])`. Wpisy bez godziny
    trafiają **przed** te z godziną. Wygląda jak decyzja, ale nie jest udokumentowana;
    a `e["trener"]` nigdy nie jest `None` tylko dlatego, że zapytanie ma
    `prowadzacy_dt IS NOT NULL` — przy zmianie zapytania to się wywali na
    `TypeError: '<' not supported between NoneType and str`.
37. **`calendar_view.py:24-25` — `prowadzacy_dt IS NOT NULL` gubi DT bez trenera.**
    Lead z datą DT, ale bez przypisanego prowadzącego **nie istnieje w kalendarzu
    i nie ma o tym żadnego komunikatu**. A to najczęstszy stan pośredni: handlowiec
    umówił termin, koordynator jeszcze nie przydzielił trenera. Potrzebny wiersz
    „(bez trenera)" albo osobny licznik „do przydzielenia".
38. **`calendar_view.py:23-25` — pusty string vs NULL.** Warunek łapie tylko `NULL`.
    Jeśli do `data_dt` wpadnie `''` (a `PATCH` zamienia `""` na `None`, ale
    importer/ręczny SQL nie muszą), rekord przejdzie filtr i wywali
    `dt.date.fromisoformat('')` w linii 98 → 500 na całym kalendarzu.
39. **`calendar_view.py:98` i `132` — `fromisoformat` bez ochrony.** Każda
    niepoprawna data w bazie (a nie ma constraintu, patrz #10) **zabija cały widok
    kalendarza**, nie tylko jeden wpis.
40. **`calendar_view.py:21-41` — kalendarz zna tylko DT, nie zna zajęć cyklicznych.**
    Pola `cykl_dzien`, `cykl_godz_od`, `trener` nigdzie nie są używane do budowy
    widoku. Wymóg: *„dane wpadają do kalendarza DT ... i kalendarza zajęć
    cyklicznych"* (`WYMAGANIA_klient_docx.md` p.3) — drugi kalendarz nie istnieje.
41. **`calendar_view.py:56-68` — kolizje O(n²) w grupie**, liczone przy **każdym**
    żądaniu i dodatkowo drugi raz w `pulpit` (`app.py:100-102`) na **wszystkich**
    zdarzeniach bez zakresu. Przy skali 980 szkół to jeszcze przejdzie, ale wynik
    nie jest nigdzie cache'owany ani utrwalany.
42. **`calendar_view.py:16-18` — twarde polskie nazwy dni/miesięcy w kodzie.**
    Do przeniesienia, ale jako dane/konfiguracja, nie stała modułu.
43. **`calendar_view.py:142` — `firstweekday=0`** (poniedziałek) jest poprawne dla PL,
    ale w połączeniu z `wk[:ndni]` (linia 143) zakłada „5 pierwszych dni = pon-pt".
    Założenie prawdziwe tylko przy `firstweekday=0` — zmiana jednej stałej cicho
    zepsuje widok. Brak testu.
44. **`calendar_view.py:102-105`, `136-139` — roster trenerów = słownik + „extra"
    spoza słownika.** Dobre rozwiązanie (nie gubi danych), ale `extra` nie ma koloru
    (`colors.get(tr, "#888")`) i nic nie sygnalizuje, że w bazie jest trener spoza
    słownika — czyli dokładnie ten rozjazd, który system ma tępić
    (`01_USTALENIA`: `23. Trenner 5` vs `24. Trener 5`). Powinien być alert.
45. **`calendar_view.py:87` — brak weekendu = ciche ukrycie danych.** Częściowo
    zaadresowane licznikiem `n_weekend` (linia 99) i ostrzeżeniem w
    `kalendarz.html:36-38` — to jest **dobre** i warte przeniesienia.
46. **Brak strefy czasowej / brak `data_dt` z godziną.** Cały moduł działa na
    naiwnych datach ISO. W kontenerze bez `TZ` (patrz Dockerfile) „dziś" to UTC,
    więc między 22:00 a 24:00 czasu polskiego deadline'y i kalendarz przesuwają się
    o dzień.

### Warte przeniesienia do v3 verbatim

- **Docstring `calendar_view.py:2-10`** — to jest uzasadnienie architektury v3,
  gotowe do wklejenia do dokumentacji:
  ```
  Kalendarz jako WIDOK z jednego źródła (tabela leady), nie ręcznie malowana plansza.
    * dwa spotkania trenera jednego dnia to po prostu dwa wpisy pod tą samą datą
    * kolizja godzin trenera jest wykrywalna, bo godziny są osobnymi polami czasu,
    * nowy miesiąc nie wymaga żadnego kodowania — bierze się z daty wpisu.
  ```
- `calendar_view.py:44-48` — „miesiące same się generują" (odpowiedź na wymóg
  *„bez sztywnego kodowania"*):
  ```sql
  SELECT DISTINCT substr(data_dt,1,7) m FROM leady WHERE data_dt IS NOT NULL ORDER BY m
  ```
- `calendar_view.py:56-68` — szkielet `find_collisions` (grupowanie po
  `(trener, data)` + porównanie par) — logika do zachowania, `overlaps` do naprawy.
- `calendar_view.py:100` — wzorzec budowy komórek jednym przebiegiem (zero N+1):
  ```python
  cell.setdefault((e["trener"], e["data"]), []).append(e)
  ```
- `calendar_view.py:109-111` — flaga `has` na wierszu (pozwala wyszarzać trenerów
  bez zajęć zamiast ich ukrywać).

### B vs A
Identyczne — B nie ruszył logiki kalendarza, mimo że to najważniejszy moduł.

---

## Plik: importer.py

**Co robi:** wczytuje XLSX. Najpierw próbuje mapować kolumny po **nagłówkach**
(`ALIASES`, z normalizacją polskich znaków), a gdy nie rozpozna ≥5 nagłówków —
spada na **układ pozycyjny** `SRC`. Przy okazji rozbija zbitki (`_set_value`).

**Liczba linii:** **145** (identyczne w A i B).

**Werdykt: REWRITE** — pomysł (mapowanie po nagłówkach + fallback + rozbijanie
zbitek) jest słuszny i `ALIASES` jest cennym aktywem, ale sam przebieg importu
nie zadziała na realnych plikach klienta.

### Bugi i słabe punkty

47. **`importer.py:75` — nagłówki czytane **tylko z wiersza 1**.**
    `01_USTALENIA` (linia 166): *„Dane zaczynają się w wierszu 4 (handlowcy, BAZA)
    lub 2 (widoki)"*. Dla zakładek `Sacawa`/`Olszewska`/`BAZA` nagłówek jest niżej →
    `_header_map` zwróci pustkę → `use_headers = False` (linia 112) → **cichy fallback
    na pozycyjny układ innej zakładki**. Import „się udaje" i wsypuje śmieci.
48. **`importer.py:120` — `range(2, ws.max_row + 1)` na twardo.** Dla arkuszy z danymi
    od wiersza 4 wiersze 2-3 (nagłówki/legendy) wjadą jako leady.
49. **`importer.py:120` — `ws.max_row` bez ograniczenia.** Dokument mówi wprost:
    *„`Sacawa` ma `max_row = 50500` (rozdmuchany arkusz)"*. To 50 500 iteracji ×
    ~25 wywołań `ws.cell()` = ~1,25 mln dostępów na jeden arkusz, w żądaniu HTTP
    bez timeoutu (gunicorn `--timeout 120`, Dockerfile:21). Realne ryzyko 504.
50. **`importer.py:109` — `data_only=True` bez sprawdzenia, czy cache istnieje.**
    Zakładka `Zbiorczy` to **w całości formuły** (`VSTACK(FILTER(...))`,
    `01_USTALENIA` sekcja A). `data_only=True` zwraca **ostatnią wartość zapisaną
    przez Excela**; plik wygenerowany przez Google Sheets / LibreOffice / skrypt
    może cache'a nie mieć → wszystkie komórki `None` → import kończy się
    komunikatem sukcesu i **0 rekordów**. Brak jakiegokolwiek raportu z importu.
51. **`importer.py:66-70` — `_pick_sheet` importuje **jedną** zakładkę.**
    Klient ma 5 zakładek handlowców + `BAZA` + widoki. Import `Zbiorczy` pobiera
    tylko to, co już przeszło przez formuły (70 wierszy z 980). Nie ma trybu
    „wczytaj wszystkie zakładki handlowców" ani wyboru arkusza w UI
    (parametr `sheet` istnieje w API, ale `app.py:235` go nie przekazuje).
52. **`importer.py:13-21` — komentarz kłamie o pochodzeniu układu.**
    Napisane „układ pozycyjny (fallback) ... w »Zbiorczy«", ale wg
    `01_USTALENIA` (linie 46-48) `Zbiorczy` jest **przesunięty o 1** względem BAZY
    od kolumny Z. Mapowanie `SRC` (`mail_rodzice:20, cykle:21, ..., trener:25`)
    odpowiada **BAZIE**, nie `Zbiorczy`. Fallback wsypie dane do złych kolumn
    dokładnie w tym arkuszu, dla którego niby był pisany.
53. **`importer.py:123-126` — heurystyka pustego wiersza gubi dane.**
    Wiersz pomijany, gdy `handlowiec` i `miejscowosc` są puste — czyli **każda szkoła
    z RSPO bez przypisanego handlowca i bez miasta** (a to jest właśnie pula do
    rozdania) zostanie wyrzucona. Do tego `str(hv).strip() == "#N/A"` (linia 125)
    jest martwe dla `hv=None` (bo `str(None)=='None'`), a rekord z `#N/A`
    w handlowcu i wypełnionym miastem jest **odrzucany** mimo poprawnych danych.
54. **`importer.py:134-145` — brak transakcji i raportu.** `DELETE FROM leady`
    (linia 137) wykonuje się **przed** `executemany`; jeśli insert padnie na typie,
    zostaje pusta tabela (brak `with conn:`/rollback). Funkcja zwraca tylko `len(rows)`,
    a `app.py:235` nawet tego nie pokazuje użytkownikowi (`n` jest przypisane i
    nieużyte, `app.py:235`).
55. **`importer.py:138-142` — SQL składany `%`** (`cols`, `ph`). Bezpieczne, bo
    z `LEAD_KEYS`, ale ten sam wzorzec co #1/#23.
56. **`importer.py:112` — magiczna liczba `>= 5`** jako próg rozpoznania nagłówków,
    bez logu, który wariant został wybrany. Debugowanie importu u klienta = wróżenie.
57. **`importer.py:127-129` — brak walidacji wartości słownikowych przy imporcie.**
    Import **omija** cały mechanizm z `app.py:134-139`, więc `02. Olaszewska`
    i `23. Trenner 5` wjeżdżają do bazy bez mrugnięcia — i dopiero potem UI ich nie
    wyświetli w `<select>` (bug #13). Import to najważniejsze miejsce do normalizacji
    (fuzzy match do słownika + raport „18 wartości nierozpoznanych").
58. **Brak deduplikacji / klucza.** Dwa importy w trybie „dopisz" = podwojona baza.
    Nie ma `nr RSPO` ani żadnego naturalnego klucza (`01_USTALENIA` E.1).

### Warte przeniesienia do v3 verbatim

- **`importer.py:24-50` (cała tabela `ALIASES`)** — to jest przepisana ręcznie wiedza
  o nazwach kolumn klienta, najbardziej pracochłonny fragment repo. Przenieść 1:1
  i tylko rozszerzyć.
- `importer.py:56-63` — normalizacja nagłówków (odporna na polskie znaki i spacje):
  ```python
  _PL = str.maketrans("ąćęłńóśźż", "acelnoszz")

  def _norm(h):
      if h is None:
          return ""
      s = str(h).strip().lower().translate(_PL)
      return re.sub(r"\s+", " ", s)
  ```
- `importer.py:83-105` — `_set_value` jako punkt wejścia dla parserów
  (rozdzielenie „jedna kolumna źródłowa → dwa pola docelowe" przez markery
  `_godzina_dt` / `_cykl_godzina`). Wzorzec do zachowania.

### B vs A
Identyczne.

---

## Plik: exporter.py

**Co robi:** generuje XLSX w pamięci: arkusz `Leady` (wszystkie pola, nagłówek
stylowany, podświetlenie przeterminowanych), arkusz `Kalendarz DT`
(1 wiersz = 1 spotkanie, wygenerowany z `events_for_range`) i arkusz `Słowniki`.

**Liczba linii:** **80** (identyczne w A i B).

**Werdykt: TAKE WITH FIXES** — mały, czysty, spełnia obietnicę „nikt nie jest
uwięziony w aplikacji". Trzy rzeczy do naprawy.

### Bugi i słabe punkty

59. **`exporter.py:47` — trzecia, niezgodna definicja „DT umówione":**
    ```python
    if dl and dl < today and "DT um" not in st:
    ```
    `app.py:98` używa `NOT LIKE '03.%'`, `tabela.html:44` `startswith('03.')`.
    Eksport pokaże inny zbiór „po terminie" niż pulpit. Klasyczne źródło
    „aplikacja kłamie" w rozmowie z klientem.
60. **`exporter.py:47` — porównanie `dl < today` na stringach** bez sprawdzenia
    formatu (patrz #10). Dla `deadline='2026-7-5'` (bez zera) porównanie leksykalne
    daje zły wynik.
61. **`exporter.py:37` — `SELECT *` + `fetchall()` bez limitu**, a potem
    `ws.append` per wiersz. Przy kilku tysiącach rekordów RSPO cały workbook
    siedzi w RAM-ie procesu gunicorna (2 workery). Brak `write_only=True`.
62. **`exporter.py:37` — `ORDER BY handlowiec, miejscowosc`** bez `numer_placowki`,
    więc kolejność wierszy w eksporcie nie jest deterministyczna (różni się od
    `tabela`, `app.py:54`) — diffowanie dwóch eksportów niemożliwe.
63. **`exporter.py:56` — eksport zawsze **wszystkiego**.** `prompt_v2` / sekcja D
    dokumentu wymienia to jako jawne życzenie: **brak eksportu wyfiltrowanego**.
    `build_workbook(conn)` nie przyjmuje filtrów, a `app.py:213-220` nie przekazuje
    parametrów z `request.args`.
64. **`exporter.py:57` — czwarta kopia listy `DNI`** (są też w `calendar_view.py:16`
    i w `seed.py:22`). Dokładnie ten rozjazd, który projekt zwalcza w danych,
    powtórzony w kodzie.
65. **`exporter.py:66-75` — arkusz „Słowniki" bez kolorów i bez `sort_order`**;
    eksport→import nie jest round-trip (kolory trenerów gubione).
66. **Brak walidacji danych na wyjściu** — `openpyxl` rzuci `IllegalCharacterError`
    na znaku kontrolnym w tekście (a teksty pochodzą z niekontrolowanego importu).
    Brak `try` → 500 na `/export.xlsx` bez wskazania winnego wiersza.

### Warte przeniesienia do v3 verbatim

- `exporter.py:17-25` — kompletny, działający styling nagłówka + `freeze_panes`:
  ```python
  def _style_header(ws, ncols):
      for c in range(1, ncols + 1):
          cell = ws.cell(1, c)
          cell.fill = HEAD_FILL; cell.font = HEAD_FONT
          cell.alignment = Alignment(vertical="center", wrap_text=True)
          cell.border = BORDER
      ws.row_dimensions[1].height = 30
      ws.freeze_panes = "A2"
  ```
- `exporter.py:53-64` — **koncepcja arkusza „Kalendarz DT" jako listy zdarzeń**
  (1 wiersz = 1 spotkanie). To jest dokładnie model, do którego v3 ma przejść
  w bazie; tu już istnieje na wyjściu.
- `exporter.py:10-14` — paleta i obramowania jako stałe modułu.
- `exporter.py:77-80` — eksport do `BytesIO` (bez plików tymczasowych):
  ```python
  bio = io.BytesIO(); wb.save(bio); bio.seek(0); return bio
  ```

### B vs A
Identyczne.

---

## Plik: parsers.py

**Co robi:** „naprawianie Excela" — `parse_int_leading` (`"10 klas"` → 10),
`parse_time_range` (`"08:00-12:30"` → dwa pola), `parse_date` (6 formatów +
fallback regex), `clean_text` (błędy Excela → `None`), `overlaps` (kolizja godzin).

**Liczba linii:** **103** (identyczne w A i B).

**Werdykt: TAKE WITH FIXES** — najlepszy technicznie plik w repo; do przeniesienia
prawie w całości, z jednym krytycznym wyjątkiem (`overlaps`).

### Bugi i słabe punkty

67. **`parsers.py:99-103` — `overlaps` wyłącza detekcję kolizji na realnych danych**
    (opis w #32). Wymaga wszystkich czterech godzin, a `do` w danych klienta
    praktycznie nie istnieje. **To jest bug, który wywraca główną obietnicę produktu.**
    Do tego porównanie `od1 < do2 and od2 < do1` traktuje styk (08:00-12:00 i
    12:00-16:00) jako brak kolizji — słusznie — ale nie ma pojęcia dojazdu
    między szkołami, o które klientka pyta („szybka lokalizacja trenera").
68. **`parsers.py:16-23` — `parse_int_leading` bierze **pierwszą** liczbę.**
    `"klasy 1-4, ok. 12"` → `1`. `"Ilość klas 1-4"` jako nagłówek w danych → `1`.
    `int(float)` obcina (`12.6` → `12`), bez sygnału. Dla `True` (bool jest `int`)
    zwróci 1.
69. **`parsers.py:42-60` — `parse_time_range` nie waliduje zakresu.**
    `_to_hhmm` sprawdza `h>23 / mm>59` (linia 37), ale `parse_time_range`
    (linie 54-57) formatuje **bez tej kontroli** → `"99:99"` wjedzie do bazy jako
    `"99:99"` i zepsuje sortowanie oraz `overlaps`.
70. **`parsers.py:51-52` — `timedelta` nieobsługiwany.** `01_USTALENIA` (linia 158)
    mówi wprost: kolumna N zawiera *„raz `timedelta(31800s)`"* (Excel zapisuje
    czas > 24 h jako różnicę). `isinstance` łapie tylko `time` i `datetime`,
    a `str(timedelta(seconds=31800))` = `"8:50:00"` → regex `(\d{1,2})[:.](\d{2})`
    dopasuje `8:50` → przypadkowo poprawnie. Ale `timedelta(days=1, seconds=...)`
    da `"1 day, 8:50:00"` → wynik `"01:00"`... czyli **cicho zły czas**.
71. **`parsers.py:63-87` — `parse_date` bez kontroli sensowności.**
    Excel często trzyma daty jako **liczby seryjne** (np. `46231`). Ta funkcja
    zwróci `None` (regex nie trafi) — dane zniknął bez śladu. Brak obsługi
    `int/float` jako serial date. Dodatkowo `%d.%m.%y` przy `"05.07.26"`
    → 2026 (dobrze), ale `"05.07.99"` → 2099.
72. **`parsers.py:78` — regex fallback zakłada kolejność dzień-miesiąc-rok.**
    `"2026-07-05"` obsłużone wcześniej przez `strptime`, ale `"7/5/2026"`
    (format US, realny przy eksportach z Google Sheets) → 7 maja, nie 5 lipca.
    Cichy błąd o dwa miesiące.
73. **`parsers.py:90-96` — `clean_text` zwraca `None` dla `"None"` (string).**
    Sprytne, ale ryzykowne: uzasadniona wartość tekstowa „None" (nazwisko?) zginie.
    Lista błędów Excela niekompletna (brak `#DIV/0!`, `#NAME?`, `#NULL!`, `#NUM!`).
74. **Brak testów.** Ani jednego pliku testowego w repo. Dla modułu parserów,
    który ma 6 gałęzi formatu daty, to jest podstawowy brak — i jednocześnie
    najtańszy zysk w v3 (parsery są czystymi funkcjami).

### Warte przeniesienia do v3 verbatim

- **Docstring `parsers.py:2-8`** — najlepsze zdanie sprzedażowe w całym projekcie:
  ```
  To jest sedno przewagi nad arkuszem: z komórki "10 klas" nie policzysz sumy,
  z "08:00-12:30" nie wykryjesz kolizji trenera.
  ```
- `parsers.py:26-39` — `_to_hhmm` **z walidacją zakresu** (to ta poprawna wersja,
  której brakuje w `parse_time_range`):
  ```python
  m = _TIME_RE.search(str(value))
  if not m: return None
  h, mm = int(m.group(1)), int(m.group(2))
  if h > 23 or mm > 59: return None
  return "%02d:%02d" % (h, mm)
  ```
- `parsers.py:63-87` — cała lista formatów daty (`"%Y-%m-%d", "%d.%m.%Y",
  "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%d.%m.%y"`) + fallback regex — wiedza o realnych
  danych, do rozszerzenia o serial date.
- `parsers.py:90-96` — `clean_text` z listą błędów Excela.

### B vs A
Identyczne.

---

## Plik: seed.py

**Co robi:** zasila słowniki wartościami startowymi, nadaje trenerom kolory z palety,
szuka pliku `PH Nowy*.xlsx` w katalogu nadrzędnym i importuje go przy pierwszym
starcie (`bootstrap`).

**Liczba linii:** **68** (identyczne w A i B).

**Werdykt: REWRITE** — słowniki muszą być danymi (plik/migracja), nie stałą w kodzie,
a auto-import z losowego pliku obok repo nie ma prawa istnieć na produkcji.

### Bugi i słabe punkty

75. **`seed.py:7-24` — słowniki zahardkodowane w kodzie i **niekompletne**.**
    Trenerzy: **9 pozycji**, a źródło ma 23-40 (`01_USTALENIA`, „Trenerzy: dwie
    różne listy — 40-pozycyjna i 24-pozycyjna"). Miejscowości: **13**, a źródło
    20-22 w trzech wariantach. Skutek: przy realnych danych większość wartości
    jest „spoza słownika" i UI ich nie zapisze (bug #29/#13).
76. **`seed.py:14-16` — przeniesiony błąd z arkusza:** `"08. Katowice"` **i**
    `"10. Katowice"` w jednej liście. Dokument wskazuje analogiczny dublet
    (`14. Dąbrowa Górnicza` / `17. Dąbrowa Górnicza`) jako **rozjazd do usunięcia** —
    a tu został skopiowany do kodu.
77. **`seed.py:20` — zmieniona wielkość liter statusu.** W kodzie
    `"04. Brak kontaktu ze szkołą"`, w źródle `"04. BRAK KONTAKTU ZE SZKOŁĄ"`
    (`01_USTALENIA` linia 122, oraz zapytanie
    `QUERY(... WHERE Col3 = '04. BRAK KONTAKTU ZE SZKOŁĄ')`). Każde porównanie
    „na sztywno" z widokiem `Niewykorzystane rekordy` się rozjedzie.
78. **`seed.py:11-12` — lista trenerów miesza dwie różne role.** `01. Małolepsza`,
    `02. Olszewska` są jednocześnie **handlowcami** (linie 8-9) i trenerami.
    W v3 to jedna tabela `osoby` z rolami, nie dwa niezależne słowniki z tymi
    samymi nazwiskami (dziś zmiana nazwiska trzeba robić w dwóch miejscach).
79. **`seed.py:41-47` — `os.listdir(parent)` na katalogu nadrzędnym repo.**
    Wywoływane z `bootstrap()`, które leci przy **imporcie `app.py`** (`app.py:246`).
    Jeśli katalog nie istnieje / brak uprawnień → `OSError` i **aplikacja się nie
    startuje**. Wybiera pierwszy pasujący plik w nieokreślonej kolejności — na
    dysku sieciowym QNAP to loteria.
80. **`seed.py:56-59` — auto-import `replace=True` przy pustej bazie.**
    Cicha operacja na danych osobowych szkół, uruchamiana przez sam start procesu,
    dwukrotnie przy dwóch workerach (#15). Powinna być jawną komendą CLI.
81. **`seed.py:60-62` — `print()` jako jedyny kanał raportowania.** Brak `logging`,
    więc w Dockerze informacja „zaimportowano 0 leadów" ginie w tłumie.
82. **`seed.py:34` — kolory z palety przypisywane po indeksie** (`PALETA[i % len]`).
    Przy 23 trenerach i 10 kolorach powtórki są nieuniknione, a klient chce
    *„każdy trener ma swój kolor"* (`WYMAGANIA_klient_docx.md` p.3). Trzeba
    generatora deterministycznego (HSL po hashu) — decyzja zapisana już
    w `01_USTALENIA` („kolory generowane deterministycznie").

### Warte przeniesienia do v3 verbatim

- `seed.py:26-28` — paleta startowa (rozszerzyć do 24+ albo zamienić na generator):
  ```python
  PALETA = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
            "#0891b2", "#db2777", "#65a30d", "#475569", "#c026d3"]
  ```
- `seed.py:31-38` — idempotentny seed (`INSERT OR IGNORE` + `sort_order = i`)
  — wzorzec dobry, treść do wymiany na dane z pliku.
- **Wartości słownikowe** z `seed.py:17-23` (`status_szkoly`, `status_realizacji`,
  `dt`, `dzien_tyg`) po korekcie wielkości liter — są zgodne ze źródłem.

### B vs A
Identyczne.

---

## Plik: templates/base.html

**Co robi:** szkielet HTML — topbar z nawigacją, przyciski eksport/import,
rozwijany panel importu, `<main>`, toast, `app.js`.

**Liczba linii:** A = **39**, B = **44**.

**Werdykt: TAKE WITH FIXES**

### Bugi i słabe punkty

83. **`base.html:25-31` (A) — formularz importu bez CSRF i bez `onsubmit`-owego
    potwierdzenia**, z domyślnie zaznaczonym `replace` (linia 27). Patrz #3.
84. **`base.html:13-16` — nawigacja bez pojęcia roli.** Każdy widzi wszystko
    (Słowniki = edycja globalnych list). Klient chce izolacji handlowców
    (`WYMAGANIA_klient_docx.md` p.4: *„koordynator odbiera mu dostęp"*).
85. **`base.html:20` — logika w atrybucie `onclick`** (`classList.toggle`).
    Drobne, ale w B rozlało się na `style="..."` inline w szablonach (patrz niżej).
86. **`base.html:13-16` — `{{ 'on' if nav_active=='tabela' }}`** bez `else`:
    przy `StrictUndefined` (typowe ustawienie w większych projektach) to wybuchnie.
    Dziś działa, bo Jinja renderuje `Undefined` jako `""`.
87. **B:7-9 — `<link href="https://fonts.googleapis.com/...">`.** W B dodano
    **zewnętrzną zależność do Google Fonts**. Trzy konsekwencje:
    (a) aplikacja w sieci wewnętrznej / bez internetu traci typografię i miga
    przy ładowaniu; (b) każdy render wysyła IP użytkownika do Google — przy danych
    osobowych szkół i kontaktów to zbędne ryzyko RODO; (c) brak fallbacku offline.
    W v3: font self-hosted albo tylko stos systemowy.
88. **Brak `<meta name="csrf-token">`**, brak `aria-*`/`<label for>` w panelu importu,
    brak `lang` na treściach dynamicznych. Dostępność zerowa.

### Warte przeniesienia
- Struktura „topbar + panel importu + `<main>` + toast" jest prosta i wystarczająca.
- `base.html:26` — `accept=".xlsx"` na input file (drobiazg, ale poprawny).

### B vs A
B jest **ładniejszy** (nowa nawigacja z pulpitem na pierwszym miejscu, spójne klasy
`btn-primary`/`btn-secondary`, emoji zamienione na strzałki `↓ ↑`), ale
**wprowadza regres**: zewnętrzny Google Fonts (#87) oraz `<div class="bar">`,
który koliduje z regułą `.bar` z pulpitu (patrz sekcja „Różnice A vs B", bug #101).
Netto: **B lepszy wizualnie, gorszy operacyjnie.**

---

## Plik: templates/tabela.html

**Co robi:** rejestr leadów jako edytowalna siatka — filtry (handlowiec / miasto /
status / szukaj), `<select>` dla pól słownikowych, `input[type=date|time|number|text]`
dla reszty, podświetlenie przeterminowanych, przyciski dodaj/usuń.

**Liczba linii:** A = **82**, B = **89**.

**Werdykt: REWRITE** — jako demo działa, ale model „każda komórka to input,
wszystkie wiersze naraz" nie skaluje się do skali klienta.

### Bugi i słabe punkty

89. **`tabela.html:50-70` — 26 inputów × N wierszy, bez paginacji ani wirtualizacji.**
    5 kolumn słownikowych renderuje pełny `<select>` z ~20 `<option>`.
    Przy 980 szkołach: ~25 tys. inputów + ~100 tys. `<option>`.
    Strona ważyłaby kilka MB i zamroziłaby przeglądarkę. Patrz #17.
90. **`tabela.html:54-59` — wartość spoza słownika = pusty `<select>`.**
    Jeśli `r[key]` nie ma wśród `slowniki[rodzaj]` (a po imporcie to norma, #57),
    żaden `<option>` nie ma `selected` → pokazuje się pusty wybór. Użytkownik
    **nie widzi, że dane są**, a pierwszy `change` je nadpisuje. Cicha utrata danych.
    Fix: dorzucać bieżącą wartość jako `<option>` z klasą „poza słownikiem".
91. **`tabela.html:44` — czwarta definicja „po terminie"** (`startswith('03.')`),
    liczona w szablonie. Reguła biznesowa w warstwie prezentacji.
92. **`tabela.html:44` — porównanie `r.deadline < today` na stringach w Jinja.**
    Działa dla ISO, ale każda inna forma (patrz #10) daje zły wynik bez błędu.
93. **`tabela.html:39` — pełny nagłówek 26 kolumn bez możliwości ukrycia/wyboru
    kolumn.** Klient pracuje na podzbiorach (kolumny Julki AA-AG vs kolumny
    handlowca) — jeden widok „wszystko" jest nieużywalny.
94. **`tabela.html:31` — „+ Nowy lead" tworzy **pusty** rekord** (`app.py:161`)
    i przeładowuje stronę. Po `ORDER BY handlowiec` z NULL-em na początku wiersz
    ląduje na górze — przypadkiem dobrze, ale bez formularza i bez walidacji
    (nie da się utworzyć leada z wymaganymi polami).
95. **`tabela.html:48` — `onclick="usunLead({{ r.id }}, this)"`** — `id` w atrybucie,
    jeden `confirm()` jako cała ochrona przed twardym `DELETE` (#12).
96. **Brak sortowania po kliknięciu w nagłówek, brak filtra „w każdej komórce"** —
    a klient prosi o to wprost: *„ważne filtrowanie w każdej komórce"*
    (`WYMAGANIA_klient_docx.md` p.3).
97. **`tabela.html:7,13,19` — `onchange="filterForm.submit()"`** korzysta z
    globalnej nazwy formularza (legacy DOM). Działa, ale każdy submit to pełny
    reload i utrata pozycji scrolla w tabeli 26-kolumnowej.

### Warte przeniesienia do v3 verbatim
- `tabela.html:50-68` — **wzorzec renderowania komórki na podstawie typu z metadanych**
  (`typ.startswith('slownik:')` / `date` / `time` / `int` / else). To jest dobry
  szkielet generycznej siatki:
  ```jinja
  {% if typ.startswith('slownik:') %}{% set rodzaj = typ.split(':')[1] %}
  ...
  {% elif typ=='date' %}<input type="date" class="cell" data-id=... data-field=...>
  ```
- `tabela.html:65` — poprawne rozróżnienie 0 od NULL w polu liczbowym:
  ```jinja
  value="{{ r[key] if r[key] is not none else '' }}"
  ```
  (jedyne miejsce w repo, gdzie NULL vs `0` jest zrobione **dobrze** — reszta
  używa `r[key] or ''`, co zamienia `0` na pusty string; patrz linie 61, 63, 67).
- `tabela.html:77-81` — legenda tłumacząca funkcję („literówka typu »Olaszewska«
  jest niemożliwa") — świetny materiał na demo.

### B vs A
B **lepszy**: dorzuca kropkę koloru trenera przy `prowadzacy_dt`/`trener`
(B:55-57) — realna wartość dla użytkownika, spójna z kalendarzem:
```jinja
{% set dot = key in ['prowadzacy_dt', 'trener'] %}
{% if dot and r[key] %}<span class="dot" style="background:{{ colors.get(r[key], '#9b9797') }}"></span>{% endif %}
```
plus pogrubienie kolumny `numer_placowki` (`col-bold`) i nagłówek strony
(`kicker` + `h1`). Minus: `style="..."` wstawiony inline w szablonie (B:8, B:11).
Bugi #89-#97 **nie naprawione**.

---

## Plik: templates/kalendarz.html

**Co robi:** dwa widoki kalendarza — „miesiąc" (macierz trener × wszystkie dni,
scroll w prawo) i „tygodnie" (osobna tabela na tydzień). Makro `tile()` renderuje
kafelek spotkania. Przełącznik weekendów i pustych tygodni.

**Liczba linii:** A = **136**, B = **138**.

**Werdykt: TAKE WITH FIXES** — to jest najbliżej życzeń klienta i najlepszy
materiał na demo. Braki są w treści kafelka i w interakcji.

### Bugi i słabe punkty

98. **`kalendarz.html:40-48` — kafelek nie pokazuje tego, o co klient prosił.**
    Notatki k.2 („KALENDARZ — pola do pokazania"): **NAZWA szkoły · MIEJSCOWOŚĆ ·
    ILOŚĆ KLAS · NR SALI**. Kafelek pokazuje godziny, `e.szkola`
    (czyli `numer_placowki`, nie nazwę!) i miejscowość. **Brakuje ilości klas
    i nr sali** — a `events_for_range` (`calendar_view.py:23-24`) ich nawet nie
    pobiera. Do tego `title=` (linia 42) wrzuca handlowca do tooltipa,
    czego nikt nie prosił.
99. **`kalendarz.html:9-14` — wybór miesiąca to `<select>` z surowym `YYYY-MM`**
    (`{{ m }}`), mimo że `month_label()` istnieje i daje „Wrzesień 2026".
    Miesiące pochodzą wyłącznie z istniejących danych (`available_months`) —
    **nie da się wejść na miesiąc, w którym nie ma jeszcze ani jednego DT**,
    czyli nie da się planować naprzód. Brak strzałek ‹ ›, brak „dzisiaj".
100. **`kalendarz.html:71-77` — brak jakiejkolwiek interakcji.** Kalendarz jest
    read-only: nie ma drag&drop, nie ma „dodaj DT w tej komórce", nie ma linku
    z kafelka do wiersza w tabeli. Trener nie ma swojego widoku („z tego kalendarza
    będą korzystali trenerzy planując swój czas pracy", `WYMAGANIA_klient_docx.md` p.2).
101. **`kalendarz.html:41` — kolor brany z **wiersza**, nie ze zdarzenia**
    (`tile(e, row.color)`). Poprawne dla widoku trener × dzień, ale nie da się
    użyć tego makra w planszy „STARTY", gdzie kolor musi być cechą trenera
    niezależnie od układu.
102. **`kalendarz.html:36-38` — ostrzeżenie o ukrytych weekendach jest **dobre**,
    ale analogicznego ostrzeżenia nie ma dla trzech innych ukryć:** DT bez trenera
    (#37), DT w dniach z sąsiedniego miesiąca w widoku tygodni (#33) i leady
    z datą, ale z niepoprawnym formatem (#10).
103. **`kalendarz.html:133-135` — inline `<script>` w szablonie** zamiast w `app.js`.
104. **Brak druku.** Klientka dziś ten kalendarz **drukuje/rozsyła** — nie ma
    `@media print`, nie ma eksportu widoku do PDF/PNG.

### Warte przeniesienia do v3 verbatim
- **Makro `tile` (`kalendarz.html:40-48`)** — po dodaniu klas i sali to gotowy
  komponent:
  ```jinja
  {% macro tile(e, color) %}
    <div class="ev2 {{ 'ev-collision' if e.collision }}" style="--c: {{ color }}"
         title="{{ e.szkola }} {{ e.miejscowosc }} — {{ e.handlowiec }}">
      <b class="hrs">{{ e.od or '—' }}{% if e.do %}–{{ e.do }}{% endif %}</b>
      <span class="school">{{ e.szkola }}</span>
      {% if e.miejscowosc %}<span class="city">{{ e.miejscowosc }}</span>{% endif %}
      {% if e.collision %}<span class="badge">kolizja</span>{% endif %}
    </div>
  {% endmacro %}
  ```
  Kluczowe: `{% for e in cell %}` (linia 74) — **pętla po liście zdarzeń w komórce**.
  To jest jednolinijkowa odpowiedź na bug `XLOOKUP` klienta i główny argument na demo.
- `kalendarz.html:36-38` — ostrzeżenie „N spotkań wypada w weekend, włącz »pokaż«".
- `kalendarz.html:69` i `111` — `class="muted"` dla trenera bez zajęć
  (pokazuje pełny roster, nie tylko zajętych).

### B vs A
B **lepszy w organizacji nagłówka**: licznik spotkań i kolizji wjechał do paska
narzędzi obok wyboru miesiąca (B:12-14), przełącznik przemianowany na
„▦ Macierz / ☰ Tygodnie" (B:31-34), skrócone nazwy dni w widoku tygodni
`{{ d.dow[:3] }}` (B:105) — węższe kolumny. Usunięty przycisk „🎨 kolory"
(link do słowników) — **to jest strata**, ustawianie kolorów stało się mniej odkrywalne.
B usunął też klasę `daycell` z komórek (B:75, B:117), przenosząc styl na
`.cal-month td` / `.cal2 td` — mniej klas, ale **zniknęła gwarantowana wysokość
komórki** (`min-height:78px` z A `style.css:77`), więc puste dni kolapsują.
Bugi #98-#104 nie naprawione.

---

## Plik: templates/pulpit.html

**Co robi:** kokpit — 5 liczników (leady / DT umówione / z datą / po terminie /
kolizje), tabela „po terminie", tabela kolizji, podział wg handlowca.

**Liczba linii:** A = **56**, B = **74**.

**Werdykt: TAKE WITH FIXES**

### Bugi i słabe punkty

105. **`pulpit.html:9-10` — liczniki bez kontekstu czasowego.** „DT umówione"
    liczone dla **całej historii**, nie dla wybranego okresu. Klient myśli
    w tygodniach („STATUS — minimum na tydzień", notatki k.1 p.4) — brak
    jakiegokolwiek filtra dat na pulpicie.
106. **`pulpit.html:44-54` — „Podział wg handlowca" to `GROUP BY handlowiec`**
    (`app.py:104-107`) → osobny wiersz dla każdej literówki
    (`02. Olszewska` i `02. Olaszewska` = dwóch handlowców), a NULL renderuje się
    jako `(brak)` (linia 50) — poprawnie, ale bez informacji, że to pula do rozdania.
107. **Brak celu tygodniowego i licznika realizacji** — wprost wymagane:
    *„STATUS — minimum na tydzień"* (notatki k.1 p.4).
108. **Brak listy „niewykorzystane rekordy"** — czwarta faza cyklu życia leada
    z `.docx` p.4 nie ma na pulpicie żadnej reprezentacji (jest tylko „po terminie",
    które jest przesłanką, nie stanem).
109. **`pulpit.html:20-23`, `35-38` — tabele bez limitu.** Przy 980 leadach lista
    „po terminie" może mieć setki wierszy na jednej stronie, bez paginacji i bez
    akcji masowych („przypisz innemu handlowcowi") — czyli bez tego, po co ta
    lista istnieje.
110. **Brak linków** z wiersza pulpitu do rekordu w tabeli / do kalendarza.
    Diagnoza bez możliwości działania.

### Warte przeniesienia do v3 verbatim
- Zestaw pięciu wskaźników (`pulpit.html:6-10`) jako punkt wyjścia; szczególnie
  para „po terminie" + „kolizje trenerów" — to są dwa realne bóle klienta.
- `pulpit.html:50` — `{{ r.handlowiec or '(brak)' }}` (świadome NULL → etykieta).

### B vs A
B jest **wyraźnie lepszy**:
- kropka koloru trenera na liście kolizji (B:45) i miejscowość obok szkoły (B:47);
- **pasek postępu** per handlowiec (B:63, B:69):
  ```jinja
  {% set pct = (r.u * 100 // r.c) if r.c else 0 %}
  <td><span class="bar"><span style="width:{{ pct }}%"></span></span></td>
  ```
  z **poprawnym zabezpieczeniem dzielenia przez zero** (`if r.c else 0`) —
  to jest fragment wart przeniesienia i zalążek „minimum na tydzień";
- status jako `tag-outline` zamiast surowego tekstu, `tabnums` na datach
  (cyfry tabelaryczne — daty się wyrównują w kolumnie);
- przebudowany layout (2 kolumny: overdue+kolizje | podział), `month_label`
  w nagłówku.
Bugi #105-#110 nie naprawione.

---

## Plik: templates/slowniki.html

**Co robi:** karty ze wszystkimi słownikami; przy trenerach `input[type=color]`,
przy każdej pozycji „✕", pod listą formularz dodawania.

**Liczba linii:** A = **34**, B = **40**.

**Werdykt: TAKE WITH FIXES** (po naprawie bugu #21 — dziś ekran jest w połowie martwy)

### Bugi i słabe punkty

111. **`slowniki.html:17` i `:22` — `{{ item.id }}` renderuje się jako pusty string**,
    bo `db.slownik()` nie zwraca `id` (#21). Wygenerowany HTML:
    `onchange="ustawKolor(, this.value)"` → **JS SyntaxError** →
    **zmiana koloru i usuwanie pozycji nie działają w żadnej z dwóch kopii.**
112. **`slowniki.html:22` — usuwanie bez `confirm()` i bez sprawdzenia użycia.**
    Klik = wartość znika ze słownika, a leady z tą wartością stają się
    nieedytowalne (#13). Brak „ta wartość jest użyta w 12 rekordach".
113. **Brak edycji istniejącej wartości.** Literówkę `23. Trenner 5` można tylko
    usunąć i dodać od nowa — co odwiąże wszystkie leady, które ją miały.
    Potrzebny rename z kaskadowym `UPDATE` (to jest **kluczowa** operacja
    czyszczenia danych klienta, opisana w `01_USTALENIA` jako „rozjazdy").
114. **Brak zmiany kolejności (`sort_order`).** Pole jest w schemacie (`db.py:77`),
    UI go nie tyka; nowe pozycje dostają `0` (`app.py:185-186`) i wskakują
    na początek listy przed pozycjami seedowanymi.
115. **Brak walidacji formatu wartości.** Klient używa prefiksów `01. `, `02. `
    do sortowania (`01_USTALENIA` E.5) — nic tego nie pilnuje ani nie podpowiada
    następnego numeru.
116. **Brak scalania duplikatów** („08. Katowice" + „10. Katowice" → jedno miasto).
    To jest funkcja, po którą klient przychodzi.

### Warte przeniesienia do v3 verbatim
- Cała **koncepcja ekranu** (jedno miejsce dla wszystkich list, kolor przy trenerze)
  + tekst wprowadzający (`slowniki.html:4-6`) — dobry materiał na demo.
- `slowniki.html:26-30` — formularz dodawania per karta z `onsubmit` zwracającym `false`.

### B vs A
B **kosmetycznie lepszy**: licznik pozycji na karcie
(`{{ data[rodzaj]|length }} pozycji`, B:16), `swatch` zamiast `dot`,
domyślny kolor `#0088b0` zgodny z motywem, `title="Usuń"` na przycisku.
Bug #111 **nie naprawiony w B** — obie kopie mają martwy ekran słowników.

---

## Plik: static/app.js

**Co robi:** edycja inline (`PATCH` na `change` dowolnego `.cell`), toast,
dodawanie/usuwanie leadów i pozycji słownika, ustawianie koloru.

**Liczba linii:** **85** (identyczne w A i B).

**Werdykt: TAKE WITH FIXES**

### Bugi i słabe punkty

117. **`app.js:13` + `:27` — `el.defaultValue` nie istnieje na `<select>`.**
    To właściwość `<input>`/`<textarea>`. Dla pól słownikowych (a to 5 najważniejszych
    kolumn) `prev` = `undefined`, więc **rollback po błędzie serwera ustawia
    `el.value = undefined`** → `<select>` czyści się na pustą opcję.
    Efekt: odrzucona wartość „spoza słownika" **wygląda jak wyczyszczenie pola**.
118. **`app.js:46-48` — jeden globalny `change` na `document`** bez rozróżnienia
    kontekstu. Każdy przyszły element z klasą `cell` zacznie strzelać do
    `/api/lead/undefined`.
119. **`app.js:11-44` — brak kolejkowania i debounce.** Szybkie tabowanie po
    komórkach = wiele równoległych `PATCH`, każdy z własnym `UPDATE` i `commit`
    na SQLite bez WAL (#24) → `database is locked` i utrata zapisu (błąd pokaże
    się jako „Błąd zapisu" bez wskazania, które pole).
120. **`app.js:29-36` — martwa zmienna `td`** i podwójne wyszukiwanie DOM;
    aktualizacja podświetlenia dotyczy tylko `deadline`, choć zmiana statusu
    wpływa też na inne wskaźniki (liczniki pulpitu nie odświeżają się nigdy).
121. **`app.js:16, 51, 57, 66, 75, 83` — brak nagłówka CSRF** (bo nie ma CSRF),
    brak `credentials`, brak obsługi 401/403 (bo nie ma logowania).
    Po dodaniu auth wszystkie te wywołania trzeba przejść ręcznie.
122. **`app.js:52, 70` — `location.reload()` po dodaniu**: przy 980 wierszach
    to sekundy przestoju i utrata pozycji scrolla.
123. **`app.js:55-59` — `confirm()` jako jedyna bariera przed twardym `DELETE`,
    brak „przywróć" (undo).**
124. **`app.js:56` — brak `await r.json()` przy błędzie w `usunLead`/`dodajLead`**
    → serwerowy błąd 500 przechodzi bez komunikatu poza `if (r.ok)`.

### Warte przeniesienia do v3 verbatim
- `app.js:3-9` — kompletny, minimalny toast (bez zależności):
  ```js
  function toast(msg, err) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show' + (err ? ' err' : '');
    clearTimeout(t._t);
    t._t = setTimeout(() => (t.className = 'toast'), 1800);
  }
  ```
- `app.js:11-44` — **wzorzec „optimistic edit z rollbackiem i podświetleniem
  wiersza"** (po naprawie #117 na własne `dataset.prev`):
  ```js
  const tr = el.closest('tr');
  tr.classList.remove('flash'); void tr.offsetWidth; tr.classList.add('flash');
  ```
  (reflow-trick do restartu animacji — poprawnie zrobiony).
- `app.js:46-48` — delegacja zdarzeń na `document` (jedna, zamiast N listenerów).

### B vs A
Identyczne (`85` linii, ten sam plik) — mimo że B zmienił szablony, JS został.
Dlatego bug #117 i #111 żyją w obu.

---

## Plik: static/style.css

**Co robi:** cała warstwa wizualna.

**Liczba linii:** A = **141**, B = **310**.

**Werdykt: A = DROP (zastąpić), B = TAKE WITH FIXES** — B to pełny redesign
(motyw „Broadsheet": serif, papierowe tło, akcenty cyan/magenta, tokeny w
`:root`, skala odstępów, `@media`) i jest o klasę lepszy jako punkt startowy.

### Bugi i słabe punkty

125. **B:67 vs B:162 — kolizja nazw klas `.bar` psuje topbar.**
     ```css
     .topbar .bar{...display:flex;gap:var(--space-4);padding:var(--space-3) var(--space-6)}
     ...
     .bar{display:block;height:8px;border-radius:2px;background:var(--color-neutral-200);overflow:hidden}
     ```
     `.topbar .bar` (specyficzność 0,2,0) wygrywa tylko dla `display`, bo tylko to
     deklaruje wspólnie. **`height:8px`, `overflow:hidden` i `background` z reguły
     `.bar` stosują się do kontenera topbara** → górny pasek ma 8 px wysokości
     z obciętą zawartością. Ta sama klasa jest użyta w `pulpit.html` jako pasek
     postępu (`<span class="bar">`) i w `base.html` jako kontener nawigacji
     (`<div class="bar">`). **Realny, widoczny regres w B.**
126. **B:164-165 — `td.deadline-over` to reguła-widmo.** Żaden szablon nie używa
     tej klasy (jest `cell-overdue`, B:201). Martwy CSS.
127. **B: usunięcie `min-height`/`height` z komórek kalendarza.** A miała
     `.cal2 td.daycell{min-height:78px;height:78px}` (A:77) i
     `.cal-month td.daycell{height:80px}` (A:107). B stylizuje `.cal-month td`
     / `.cal2 td` bez wysokości → w miesiącach o małym obłożeniu wiersze zapadają
     się do 1 linii i siatka przestaje wyglądać jak kalendarz.
128. **A:83-88 i B:270-276 — `color-mix()`** bez fallbacku. Wspierany od
     Chrome 111 / Safari 16.2 (2023) — na starszym firmowym Edge/przeglądarce
     w szkole kolory kafelków znikną (brak `@supports`).
129. **A:42 / B:174 / B:224 — `max-height: calc(100vh - 190px|250px|240px)`**
     — magiczne stałe dopasowane do bieżącej wysokości nagłówka. Każda zmiana
     topbara psuje scroll (na małym laptopie tabela dostanie kilkadziesiąt px).
130. **B: brak jakiegokolwiek `@media print`** przy 310 liniach stylu, choć
     kalendarz jest dokumentem do wydruku (#104).
131. **B:306-310 — jedyny breakpoint 900 px** i `min-width:1000px` na tabeli
     (B:175) → na tablecie/telefonie rejestr jest nieużywalny. Handlowiec
     w terenie z telefonem = realny scenariusz.
132. **B:38-39 — `--font-body` i `--font-heading` mają identyczną wartość**
     (dwa tokeny, jedna wartość) — tokeny bez znaczenia, plus zależność od
     Google Fonts (#87).
133. **A:60 vs B — klasa `.chip`** (A:60) używana w A (`tabela.html:78`,
     `kalendarz.html:128`) i zastąpiona w B przez `.sq`. Migrując CSS z B do v3
     trzeba pamiętać, że stare szablony się rozjadą.

### Warte przeniesienia do v3 verbatim
- **B:9-41 — cały blok tokenów `:root`** (kolory, skala odstępów `--space-*`,
  radiusy, cienie, `--maxw`). To gotowy design system.
- **B:194-204 — sticky kolumna numeru wiersza z ukrywaniem numeru na hover:**
  ```css
  .rownum{position:sticky;left:0;z-index:4;background:var(--color-bg);text-align:right;...}
  thead .rownum{z-index:6}
  tr:hover .rownum .idx{display:none}
  tr:hover .rownum .del{display:inline}
  ```
- **B:226-241 — sticky nagłówek + sticky kolumna trenera w macierzy**
  (`position:sticky` z warstwami `z-index` 5/6/1 i `left:0` na `.corner`).
  Rozwiązany „zamrożony wiersz+kolumna" jak w Excelu — nietrywialne, działa.
- **B:270-279 — kafelek zdarzenia z kolorem trenera przez `--c` i wariantem kolizji:**
  ```css
  .ev2{--c:#888;background:color-mix(in srgb,var(--c) 12%,var(--color-bg));
    border-left:3px solid var(--c);...}
  .ev-collision{background:var(--color-accent-2-100)!important;
    border-left-color:var(--color-accent-2-600)!important}
  ```
  Wzorzec „kolor jako custom property przekazywana z szablonu" — dokładnie to,
  czego potrzeba przy 23 trenerach (zero CSS-a per trener).
- B:60 `.tabnums{font-variant-numeric:tabular-nums}` — drobiazg, duża różnica
  w czytelności kolumn z datami i godzinami.
- B:133-135 — stylizowany `.scroll-x` (widoczny scrollbar poziomy — ważne,
  bo kalendarz przewija się w prawo i użytkownik musi to zauważyć).

### B vs A
**B jednoznacznie nowszy i lepszy** (tokeny, sticky, responsywność szczątkowa,
spójny system komponentów). Do przeniesienia jako baza v3 — po naprawie #125
(kolizja `.bar`), #127 (wysokość komórek) i po usunięciu Google Fonts.

---

## Plik: requirements.txt

**Co robi:** `Flask==3.1.3`, `openpyxl==3.1.5`, `gunicorn==23.0.0`.
**Liczba linii:** **3** (identyczne). **Werdykt: TAKE AS IS.**

134. Wersje przypięte dokładnie (`==`) — dobrze. Brak `pip-tools`/lockfile
     (zależności tranzytywne nieprzypięte) — do rozważenia w v3.
135. Brak `pytest` (bo nie ma testów), brak `python-dotenv`.
     Po dodaniu auth/CSRF dojdzie `Flask-WTF` lub własny middleware.
136. `openpyxl` bez `defusedxml` — wgrywany XLSX to niezaufany XML
     (billion-laughs / XXE). Przy publicznym endpointcie importu bez auth (#2/#3)
     to realna ścieżka DoS.

---

## Plik: Dockerfile

**Co robi:** `python:3.13-slim`, instalacja z `requirements.txt`, `COPY . .`,
`mkdir /data` + `VOLUME`, `EXPOSE`, `CMD gunicorn --workers 2 --timeout 120`.

**Liczba linii:** **21** (A i B; różnica tylko port 5000→5001).

**Werdykt: TAKE WITH FIXES**

137. **Dockerfile:12 — brak `USER`: kontener działa jako root.** Przy montowanym
     wolumenie `/data` i endpointcie przyjmującym pliki to niepotrzebna eskalacja.
     Dodać `RUN adduser --system app && chown -R app /data` + `USER app`.
138. **Dockerfile:21 — `--workers 2` na SQLite bez WAL** (#24) → `database is locked`
     przy edycji inline z dwóch przeglądarek. Do skali tej apki lepszy
     **1 worker + kilka wątków** (`--workers 1 --threads 4`).
139. **Brak `ENV TZ=Europe/Warsaw`** → kontener liczy „dziś" w UTC.
     Deadline'y i kalendarz przesuwają się o dzień po 22:00 czasu polskiego (#46).
140. **Brak `HEALTHCHECK`**, brak `--access-logfile -`, brak
     `--error-logfile -` → w `docker compose logs` nie widać żądań ani błędów.
141. **`COPY . .` przed utworzeniem użytkownika i bez `--chown`**; brak
     wielostopniowego builda (choć przy czystym Pythonie to mały zysk).
142. **`VOLUME ["/data"]` w Dockerfile + named volume w compose** — dublowanie;
     `VOLUME` w obrazie tworzy anonimowy wolumen przy `docker run` bez `-v`
     (ciche gubienie danych przy testach). Lepiej tylko w compose.
143. **`bootstrap()` przy imporcie** (#15) w połączeniu z 2 workerami i brakiem
     `--preload` → dwa równoległe seedy/importy przy każdym starcie.

### B vs A
Tylko port (5000→5001). **B nie jest lepszy — jest równoległy.**

---

## Plik: docker-compose.yml

**Co robi:** jedna usługa `leady`, build z katalogu, restart `unless-stopped`,
port hosta 5057, named volume na `/data`, `DATA_DIR=/data`.

**Liczba linii:** **16** (A i B).

**Werdykt: TAKE WITH FIXES**

144. **`docker-compose.yml:13` — `SECRET_KEY` zakomentowany** („`# - SECRET_KEY=zmien_mnie`"),
     a `app.py` nigdy go nie czyta (`app.secret_key` nie jest ustawiany).
     Po dodaniu sesji/logowania to pierwsza rzecz do zrobienia.
145. **Brak limitów zasobów** (`deploy.resources`), brak `logging` z rotacją —
     import 50 500-wierszowego arkusza (#49) potrafi zjeść pamięć hosta.
146. **Wolumen na `/data` jest** — i to jest dobrze zrobione (baza przeżywa
     przebudowę obrazu, `DEPLOY.md:61` to opisuje). Brak natomiast **backupu**
     (cron z `docker cp` / `sqlite3 .backup`) — jest tylko instrukcja ręczna.
147. **Brak sieci wewnętrznej i brak reverse-proxy w compose** — port wystawiony
     bezpośrednio na hosta, ochrona hasłem opisana tylko w `DEPLOY.md:77-81`
     jako opcja do wklejenia ręcznie.

### B vs A
B zmienia nazwy (`leady_app_kopia`, `leady_data_kopia`) i porty (`5058:5001`),
żeby dwie kopie żyły równolegle. Sensowne operacyjnie, merytorycznie neutralne.

---

## Plik: README.md

**Co robi:** opis projektu, tabela „ból arkusza → rozwiązanie", opis ekranów,
uruchomienie lokalne i w Dockerze, spis plików, nota o prywatności.

**Liczba linii:** A = **70**, B = **75**.

**Werdykt: TAKE WITH FIXES** — jako materiał sprzedażowy bardzo dobry.

148. **`README.md:45-46` — kłamie o wolumenie liczb:** „importuje z niego dane
     (67 leadów)" — twarda liczba w dokumentacji, zależna od pliku klienta.
149. **`README.md:17` — obiecuje „literówka niemożliwa"**, a `api_create` (#11)
     i import (#57) omijają walidację. Dokumentacja opisuje intencję, nie stan.
150. **`README.md:21` — „Pulpit: po terminie ... kolizje trenerów"** — kolizje
     w praktyce nie są wykrywane (#32/#67). To najbardziej ryzykowne zdanie
     w kontakcie z klientem: obiecuje dokładnie tę funkcję, która nie działa.
151. **Brak rozdziału „czego to jeszcze nie robi"** — brak listy ograniczeń
     (brak logowania, 1 lead = 1 DT, brak zajęć cyklicznych w kalendarzu).
     Przy demo dla klienta to konieczne.

### Warte przeniesienia
- **Tabela `README.md:14-22` („Ból arkusza | Rozwiązanie w aplikacji")** — gotowy
  szkielet prezentacji dla klienta; przenieść i uzupełnić o eventy i role.

### B vs A
B dodaje blok o motywie „Broadsheet" i porcie 5001 (B:3-6). Poza tym identyczny.

---

## Plik: DEPLOY.md

**Co robi:** instrukcja wdrożenia na VPS opxen.xyz — scp, `docker compose up`,
nginx + certbot, dane startowe, aktualizacja, backup, uwagi bezpieczeństwa.

**Liczba linii:** **81** (A i B; różnica: 5057→5058).

**Werdykt: TAKE AS IS** (z dopiskami)

152. **`DEPLOY.md:51` — nieprawda:** „plik `PH Nowy.xlsx` nie jedzie do obrazu —
     jest w `.dockerignore`". `.dockerignore` **nie zawiera** tego wzorca
     (ma `data/`, `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.git/`, `*.log`).
     Plik nie trafia do obrazu tylko dlatego, że leży **poza** kontekstem builda.
     Uzasadnienie fałszywe → przy zmianie struktury katalogów dane osobowe
     szkół wjadą do obrazu.
153. **`DEPLOY.md:72-81` — ochrona to `auth_basic` w nginx.** Uczciwie opisane
     jako tymczasowe, ale: brak rozdziału ról (handlowiec widzi wszystko),
     brak audytu „kto zmienił", jedno wspólne hasło dla całej firmy.
154. **`DEPLOY.md:63-68` — backup ręczny.** Brak crona, brak retencji, brak
     `sqlite3 .backup` (kopiowanie żywego pliku SQLite bez WAL potrafi dać
     niespójny plik).
155. **Brak sekcji „przywracanie z backupu"** i brak wersjonowania schematu (#22),
     więc restore starej bazy do nowej wersji kodu = `OperationalError`.

### Warte przeniesienia verbatim
- **Cały blok nginx `DEPLOY.md:28-46`** (server + `client_max_body_size 25M` pod
  XLSX + `proxy_set_header X-Forwarded-*` + certbot) — działający, sprawdzony
  fragment infrastruktury.
- `DEPLOY.md:77-81` — `auth_basic` jako natychmiastowa zapora **do czasu**
  wdrożenia logowania.

---

## Plik: .dockerignore

**Liczba linii:** **7** (identyczne). **Werdykt: TAKE WITH FIXES.**

156. Brak `*.xlsx` i `*.db` — patrz #152. Dodać `*.xlsx`, `*.xlsm`, `*.db`,
     `.env`, `Dockerfile`, `README.md` (nie są potrzebne w obrazie).

## Plik: .gitignore

**Liczba linii:** **7** (identyczne). **Werdykt: TAKE WITH FIXES.**

157. Ma `data/` i `_upload.xlsx` — dobrze. Brakuje `*.xlsx` (pliki klienta z danymi
     osobowymi leżą w katalogu nadrzędnym — ryzyko commita), `.env`, `.idea/`,
     `.vscode/`, `*.sqlite`.

---

## Różnice A vs B (kopia)

**Wniosek nadrzędny: B to reskin, nie nowa wersja.** Cała logika
(`db.py`, `calendar_view.py`, `importer.py`, `exporter.py`, `parsers.py`,
`seed.py`, `static/app.js`) jest **bajt w bajt identyczna**. Zmieniono
prezentację (nowy `style.css`, 5 szablonów), porty (żeby obie kopie chodziły
naraz) i dwie linijki w `app.py`, które dowożą kolory do widoków.
**Ani jeden z ~130 bugów logicznych nie został w B naprawiony**, w tym martwy
ekran Słowniki (#111) i wyłączona detekcja kolizji (#32).

| Plik | A | B | Kto lepszy | Co dokładnie |
|---|---|---|---|---|
| `app.py` | 249 | 253 | **B** | B przekazuje `trener_colors()` do `tabela` (B:58,62) i `pulpit` (B:109,114) + `month_label` na pulpicie. Reszta: port 5000→5001. Żaden bug nienaprawiony. |
| `templates/base.html` | 39 | 44 | **A** (netto) | B: lepsza nawigacja (Pulpit pierwszy), spójne `btn-primary/secondary`, kontener `.bar`. **Ale**: dodany Google Fonts (zewnętrzna zależność + RODO, #87) i klasa `.bar` kolidująca z paskiem postępu (#125). |
| `templates/tabela.html` | 82 | 89 | **B** | Kropka koloru trenera przy `prowadzacy_dt`/`trener`, `col-bold` na placówce, nagłówek `kicker+h1`. Minus: `style=` inline. |
| `templates/kalendarz.html` | 136 | 138 | **B** (prawie) | Licznik kolizji w pasku narzędzi, „▦ Macierz / ☰ Tygodnie", `d.dow[:3]` (węższe kolumny). Minus: usunięty link „🎨 kolory" i klasa `daycell` (utrata gwarantowanej wysokości komórki, #127). |
| `templates/pulpit.html` | 56 | 74 | **B** | Pasek postępu per handlowiec z ochroną `if r.c else 0`, kropki kolorów na kolizjach, miejscowość obok szkoły, `tabnums`, status jako tag, 2-kolumnowy layout. Najlepiej przemyślana zmiana w B. |
| `templates/slowniki.html` | 34 | 40 | **B** | Licznik pozycji na karcie, `swatch`, `title="Usuń"`, kolor domyślny z motywu. Bug `item.id` (#111) w obu. |
| `static/style.css` | 141 | **310** | **B, wyraźnie** | Pełny redesign „Broadsheet": tokeny `:root`, skala `--space-*`, sticky nagłówek+kolumna w macierzy, `tabular-nums`, `@media`, komponenty (`btn-*`, `tag-*`, `input`, `card`, `stat`, `seg`). **To jest baza CSS dla v3.** Do naprawy: #125 `.bar`, #126 martwe `deadline-over`, #127 wysokość komórek, #130 brak `@media print`. |
| `Dockerfile` | 21 | 21 | remis | tylko 5000→5001. |
| `docker-compose.yml` | 16 | 16 | remis | `leady_app_kopia`, `5058:5001`, `leady_data_kopia`. |
| `README.md` | 70 | 75 | **B** | +blok o motywie i porcie. |
| `DEPLOY.md` | 81 | 81 | remis | tylko port 5058. |

**Rekomendacja dla v3:** wziąć **B jako punkt wyjścia warstwy prezentacji**
(`style.css` + 5 szablonów, po naprawie #87/#125/#127), a warstwę logiki
napisać od nowa, zachowując wypunktowane fragmenty z A (`ALIASES`, parsery,
`LEAD_FIELDS`, `find_collisions`, `_style_header`, koncepcja „kalendarz = widok").

---

## LUKI FUNKCJONALNE

Weryfikacja i rozszerzenie sekcji D `01_USTALENIA_analiza.md`.
Skala trudności: **S** ≤ 0,5 dnia · **M** 0,5-2 dni · **L** > 2 dni.

### Luki z sekcji D — potwierdzone (wszystkie prawdziwe)

| # | Luka | Weryfikacja w kodzie | Źródło wymagania | Trudność |
|---|---|---|---|---|
| L1 | **Brak modelu eventów** — kalendarz liczony z leadów, więc 1 lead = max 1 DT | `calendar_view.py:21-41` czyta `leady.data_dt`; brak tabeli `eventy`; `db.py:11-38` ma jedno pole `data_dt` | *„czasem 2-3 eventy dziennie u jednego trenera"* (`.docx` p.3). **Uwaga: to nie to samo, co bug XLOOKUP.** Bug klienta = wiele eventów RÓŻNYCH szkół u jednego trenera (v1 to obsługuje). Luka = jedna szkoła z 2 terminami (v1 tego NIE obsługuje) | **L** |
| L2 | Brak **typu placówki** | brak pola w `db.py:11-38` | *„RSPO — szkoła, przedszkola, instytucje kultury"* (notatki k.1 p.3) | **S** |
| L3 | Brak **RSPO / klucza naturalnego** | brak pola, brak `UNIQUE`; import dubluje rekordy (`importer.py:134-145`) | *„do pliku zostanie wgrana czysta baza szkół z rejestru RSPO"* (`.docx` p.3) | **S** |
| L4 | **Brak ról i logowania** | zero auth w `app.py`; `DEPLOY.md:73` przyznaje: „To demo nie ma logowania" | *„koordynator odbiera mu dostęp"* (`.docx` p.4) — odbieranie dostępu **jest** modelem uprawnień | **L** |
| L5 | Brak przepływu **„niewykorzystane rekordy"** | jest tylko lista „po terminie" na pulpicie (`app.py:96-98`); brak akcji „odbierz i zwróć do puli", brak historii przypisań | *„koordynator ... przenosi rekord do zakładki niewykorzystane rekordy, z której może przydzielić go innemu handlowcowi"* (`.docx` p.4) | **M** |
| L6 | Brak **planszy STARTY** (trenerzy × dni, cała firma) | jest macierz DT (`build_grid`), ale nie ma widoku zajęć cyklicznych ani „gdzie jest kto" | *„my musimy mieć taką planszę gdzie widzimy całą firmę kto gdzie jest"* (`.docx` p.3, „to już jest Meksyk") | **M** |
| L7 | Brak **celu tygodniowego** | `app.py:104-107` liczy tylko sumy globalne | *„STATUS — minimum na tydzień"* (notatki k.1 p.4) | **S** |
| L8 | Brak **eksportu wyfiltrowanego** | `build_workbook(conn)` (`exporter.py:28`) nie przyjmuje filtrów; `app.py:213-220` nie przekazuje `request.args` | jawne życzenie z `prompt_v2` (sekcja D dokumentu) | **S** |
| L9 | Brak **historii aktywności** | brak tabeli logu; `updated_at` (`db.py:70`) nadpisywane, więc nie wiadomo CO i KTO zmienił | *„System musi kontrolować, czy handlowiec wykonał jakikolwiek wpis/ruch przy przypisanej szkole przed upływem wpisanej daty"* (`.docx` p.3) — bez logu to niewykonalne | **M** |

### Luki NOWE — nieujęte w sekcji D

| # | Luka | Dlaczego jest luką | Źródło wymagania (cytat) | Trudność |
|---|---|---|---|---|
| L10 | **Detekcja kolizji nie działa na realnych danych** | `parsers.py:99-103` wymaga 4 godzin; źródło ma jedną kolumnę „Godzina DT" → `godz_dt_do IS NULL` → `overlaps()` zawsze `False`. Funkcja **jest w kodzie i nie działa** — to gorsze niż jej brak (README:21 ją obiecuje) | *„żeby nie mógł trener 2× mieć aktywności"* (notatki k.2) | **S** |
| L11 | **Brak blokady/ostrzeżenia przy zapisie kolizji** | `app.py:124-154` (`PATCH`) nie sprawdza nic; kolizja jest tylko raportowana po fakcie na pulpicie | *„żeby nie mógł trener 2× mieć aktywności"* — „nie mógł" = walidacja przy zapisie, nie raport | **M** |
| L12 | **Kalendarz zajęć cyklicznych nie istnieje** | pola `cykl_dzien`, `cykl_godz_od/do`, `cykl_sala`, `trener` są w bazie, ale **żaden widok ich nie używa** | *„dane wpadają do kalendarza DT ..., kalendarza zajęć cyklicznych i zbiorczego arkusza Julki"* (`.docx` p.3) — 1 z 3 miejsc zrobione | **M** |
| L13 | **Brak kolumn Julki (AA-AG)** | `db.py:11-38` nie ma: dane do umowy, standardy ochrony małoletnich, oświadczenia trenerów, zaświadczenie o niekaralności, podanie o wynajem sali, umowa podpisana, Librus | *„Plik zbiorczy Julki: ... gdzie Julka ma swoje własne kolumny do ręcznego uzupełniania"* (`.docx` p.2) — **cała rola Julki jest nieobsłużona** | **S** (pola) / **M** (widok + checklisty) |
| L14 | **Brak nazwy placówki** | jest tylko `numer_placowki` („MSP 2"); kalendarz pokazuje numer jako nazwę (`calendar_view.py:36`) | *„KALENDARZ — pola do pokazania: NAZWA szkoły, MIEJSCOWOŚĆ, ILOŚĆ KLAS, NR SALI"* (notatki k.2) | **S** |
| L15 | **Kafelek kalendarza nie pokazuje ilości klas ani nr sali** | `events_for_range` (`calendar_view.py:23-24`) nie pobiera `ilosc_klas` ani `numer_sali_dt`; `tile()` ich nie renderuje | ten sam cytat co L14 — **2 z 4 wymaganych pól brakuje** | **S** |
| L16 | **Brak przypinania „szkół na tydzień do góry"** | `ORDER BY handlowiec, miejscowosc, numer_placowki` (`app.py:54`) na sztywno, brak pola `pinned`/`tydzien` | *„wybrane szkoły na tydzień **do góry** (przypinane na wierzchu listy)"* (notatki k.1 p.4) | **S** |
| L17 | **Brak statusu „DT w trakcie umawiania"** i brak odporności na zmianę listy statusów | `seed.py:18-20` ma 4 statusy; kod rozpoznaje „umówione" przez prefiks `'03.'` w 4 miejscach (`app.py:92,98,106`, `exporter.py:47`, `tabela.html:44`) → **dodanie statusu przenumeruje listę i zepsuje logikę** | *„Arkusze po statusie → np. »DT w trakcie umawiania«"* (notatki k.1 p.2) | **M** (potrzebna flaga semantyczna, nie prefiks) |
| L18 | **Brak widoków-arkuszy per status** | jest jeden filtr `status` w `/tabela`; brak zapisanych widoków („Szkoły z DT", „Szkoły z cyklami", „Niewykorzystane") | *„Arkusze po statusie"* (notatki k.1 p.2); w źródle to 3 osobne zakładki (`01_USTALENIA` A, poz. 2-4) | **S** |
| L19 | **Brak filtrowania „w każdej komórce"** | 3 selecty + 1 wyszukiwarka po 4 kolumnach (`app.py:38-53`); 22 z 26 kolumn niefiltrowalne | *„ważne filtrowanie w każdej komórce"* (`.docx` p.3) | **M** |
| L20 | **Brak Google Calendar per trener** | brak jakiejkolwiek integracji; nie ma nawet eksportu **iCal**, który dałby 80% wartości za 5% kosztu | *„będę chciała, żeby to się przenosiło do kalendarza google każdemu trenerowi, ale to jest przyszłość — chyba że nie zajmie to dużo czasu"* (`.docx` p.2) | **S** (iCal/ICS na trenera) / **L** (dwukierunkowa synchronizacja OAuth) |
| L21 | **Brak importu wielu zakładek** | `_pick_sheet` (`importer.py:66-70`) bierze **jedną** zakładkę | *„W pliku znajduje się 5 zakładek imiennych handlowców: Sacawa, Olszewska, Małolepsza, Chytry, Młynarczyk"* (`.docx` p.1) — dziś wczyta się jedna | **M** |
| L22 | **Import nie startuje od właściwego wiersza** | nagłówki tylko z wiersza 1 (`importer.py:75`), dane od wiersza 2 (`:120`) | *„Dane zaczynają się w wierszu 4 (handlowcy, BAZA) lub 2 (widoki)"* (`01_USTALENIA` linia 166) | **S** |
| L23 | **Brak raportu z importu i normalizacji do słownika** | `import_into` zwraca `len(rows)`, `app.py:235` tego nie pokazuje; wartości spoza słownika wchodzą bez korekty (`importer.py:127-129`) | *„Muszą być listy rozwijane na każdym arkuszu takie same"* (`.docx` p.3) + udokumentowane rozjazdy (`02. Olaszewska`, `23. Trenner 5`) — bez normalizacji przy imporcie słownik centralny jest fikcją | **M** |
| L24 | **Brak edycji/scalania wartości słownika** | `slowniki.html` umie tylko dodać i usunąć (a usuwanie i kolory są zepsute, #111); brak rename z kaskadą | *„Dublet w tej samej liście: 14. Dąbrowa Górnicza i 17. Dąbrowa Górnicza"*, *„literówka 02. Olaszewska"* (`01_USTALENIA`) — czyszczenie danych to główna obietnica | **M** |
| L25 | **Nie da się otworzyć miesiąca bez danych** | `available_months` (`calendar_view.py:44-48`) zwraca tylko miesiące z DT; select w `kalendarz.html:9-14` nie ma innych opcji → **nie można planować naprzód** | *„mechanizm musi działać płynnie dla kolejnych miesięcy, bez sztywnego kodowania na stałe"* (`.docx` p.2). Uwaga: sam mechanizm generowania miesiąca z daty **jest** zrobiony dobrze — brakuje nawigacji | **S** |
| L26 | **Brak wydruku / eksportu widoku kalendarza** | zero `@media print`, eksport XLSX daje listę zdarzeń, nie planszę | *„my to im nanosimy na google kalendarz z ręki, ale my musimy mieć taką planszę"* (`.docx` p.3) — plansza jest artefaktem do pokazania/rozesłania | **S** |
| L27 | **Brak paginacji / brak skalowania do RSPO** | `SELECT *` bez `LIMIT` (`app.py:55`), 26 inputów × N wierszy (`tabela.html:50-70`) | *„980 wierszy szkół"* (`01_USTALENIA` „Skala realnych danych") + RSPO ze szkołami, przedszkolami i instytucjami kultury → kilka tysięcy rekordów | **M** |
| L28 | **Brak automatyzacji „po terminie → zwrot do puli"** | pulpit tylko wyświetla listę; brak zadania cyklicznego i brak akcji zbiorczej | *„Jeśli brak aktywności po terminie: Wiersz ... ma automatycznie zniknąć z widoku handlowca i zostać przeniesiony"* (`.docx` p.3) | **M** |
| L29 | **Brak obsługi wielowartościowych pól** | `cykl_dzien` = jedna wartość słownikowa (`db.py:32`); `PATCH` odrzuci „Poniedziałek i piątek" (`app.py:134-139`) | *„w v1 pliku były wpisy typu »Poniedziałek i piątek«"* (`01_USTALENIA`, „Zbitki w danych", kolumna V) — realne dane są wielowartościowe | **S** |
| L30 | **Brak stref czasowych i brak `TZ` w kontenerze** | `dt.date.today()` (`app.py:24`) + brak `ENV TZ` w Dockerfile | pochodna wymogu kontroli terminów (`.docx` p.3) — deadline liczony w UTC myli się o dzień wieczorami | **S** |
| L31 | **Brak backupu automatycznego i brak migracji schematu** | `DEPLOY.md:63-68` = backup ręczny; `db.py:61-82` = `CREATE TABLE IF NOT EXISTS` bez wersjonowania | wymóg operacyjny: to ma zastąpić plik, który klient kopiował ręcznie; utrata bazy = utrata firmy | **M** |
| L32 | **Brak testów** | zero plików testowych | pochodna: 6 gałęzi formatu daty, 3 definicje „DT umówione", logika granic tygodnia — bez testów każda zmiana w v3 będzie regresją | **M** |

---

## Werdykt w 5 punktach

1. **Architektura jest dobra, implementacja nie.** Trzy decyzje z v1/v2
   przechodzą do v3 bez dyskusji: (a) `LEAD_FIELDS` jako jedno źródło definicji
   kolumn napędzające UI, walidację, DDL i eksport (`db.py:11-38`);
   (b) „kalendarz to widok z danych, nie malowana plansza" (`calendar_view.py:2-10`)
   — to rozwiązuje bug `XLOOKUP` klienta jedną pętlą `{% for e in cell %}`;
   (c) parsery rozbijające zbitki Excela na typowane pola (`parsers.py`).
   Wszystko powyżej tej warstwy — routing, walidacja, dostęp, import — do przepisania.

2. **B (kopia) to wyłącznie reskin.** Cała logika jest bajt w bajt identyczna;
   różnią się `style.css` (141 → 310 linii, motyw „Broadsheet" z tokenami,
   sticky nagłówkiem i kolumną, `tabular-nums`), 5 szablonów, port i 2 linijki
   `app.py` dowożące kolory trenerów. **Bierzemy z B warstwę prezentacji**
   (po naprawie: kolizja klasy `.bar` psująca topbar, usunięcie Google Fonts,
   przywrócenie wysokości komórek kalendarza), **z A nic wizualnego**.
   Żaden bug logiczny nie został w B naprawiony.

3. **Dwa bugi klasy „funkcja jest, ale nie działa" — najgorszy rodzaj przed demo.**
   (a) **Ekran Słowniki jest martwy w obu kopiach**: `db.slownik()` nie zwraca `id`,
   a szablon go używa (`slowniki.html:17,22`) → wygenerowany HTML zawiera
   `ustawKolor(, ...)` → SyntaxError → nie da się ani zmienić koloru, ani usunąć
   pozycji. (b) **Detekcja kolizji trenera nie działa na realnych danych**:
   `overlaps()` wymaga godziny końcowej, której źródłowy arkusz nie ma
   (`parsers.py:99-103`) → sztandarowa funkcja z notatek („żeby nie mógł trener
   2× mieć aktywności") jest wyłączona, a README ją obiecuje. Do tego reguła
   „DT umówione" ma **cztery różne definicje** w czterech plikach.

4. **Aplikacja nie może zobaczyć prawdziwych danych w obecnym stanie.**
   Brak jakiejkolwiek autoryzacji + brak CSRF + endpoint `POST /import`
   z domyślnie zaznaczonym `replace` = jeden request kasuje całą bazę.
   `debug=True` w `app.py:249` = zdalne wykonanie kodu, jeśli ktoś uruchomi
   wg README (`python app.py`). Kontener chodzi jako root, bez `TZ`, na SQLite
   bez WAL z 2 workerami. Do tego import na realnych plikach klienta poleci
   źle: nagłówki czytane tylko z wiersza 1 (a dane klienta zaczynają się w wierszu 4),
   jedna zakładka z sześciu, `max_row = 50500` bez limitu, `data_only=True`
   bez sprawdzenia cache'a formuł.

5. **Największa luka nie jest kosmetyczna — to model danych.**
   `1 lead = max 1 DT` (brak tabeli eventów), brak zajęć cyklicznych w kalendarzu,
   brak kolumn Julki, brak nazwy i typu placówki, brak RSPO, brak historii
   aktywności (bez której wymóg „kontrola ruchu przed terminem" jest nierealizowalny)
   i brak ról (bez których „koordynator odbiera dostęp" jest tylko zmianą tekstu
   w komórce). Sekcja D `01_USTALENIA` opisuje to trafnie — dorzucam do niej
   **23 nowe luki (L10-L32)**, z czego 12 jest w skali **S** i daje szybkie
   zwycięstwa na demo: pola do kafelka kalendarza (nazwa, klasy, sala),
   eksport wyfiltrowany, nawigacja po miesiącach bez danych, przypinanie „na tydzień",
   cel tygodniowy, eksport iCal per trener, `TZ`, start importu od wiersza 4.

---

# CZĘŚĆ 2 — INWENTARZ REALNYCH DANYCH I PARSERY v3

Narzędzia: Python 3.13.14, openpyxl 3.1.5. Każda zakładka czytana dwa razy:
`data_only=True` (wartości z cache) i `data_only=False` (formuły).
Skrypty jednorazowe: `scratchpad/inwentarz.py`, `scratchpad/przepusc_dane.py`.

Źródła:

* **[PH]** `PH Nowy  Nad którym pracuję jako główny  .xlsx` — stan aktualny, 16 zakładek
* **[DT]** `DT 2025-2026 NOWY PIĘKNY PLIK.xlsx` — poprzedni sezon, 40 zakładek.
  **To tu mieszkają najbrudniejsze wartości** (zakresy godzin, wielodniowe cykle,
  daty w tekście). `PH Nowy` jest „czysty" tylko dlatego, że jest jeszcze prawie pusty —
  jak handlowcy zaczną go wypełniać, wróci brud z `[DT]`. Parsery muszą znieść oba.

---

## A. Skala realnych danych — KOREKTA wobec `01_USTALENIA_analiza.md`

| Zakładka [PH] | `max_row` | ostatni wiersz z danymi | wierszy z danymi | uwaga |
|---|---|---|---|---|
| `Sacawa` | **50 500** | 45 | **42** | arkusz rozdmuchany 1200× wobec zawartości |
| `Olszewska` | 389 | 28 | **25** | |
| `Małolepsza` | 392 | 3 | **0** | **PUSTA** |
| `Chytry` | 394 | 3 | **0** | **PUSTA** |
| `Młynarczyk` | 390 | 3 | **0** | **PUSTA** |
| `BAZA` | 984 | 547 | **544** | nie ~980, jak zakładał dokument |
| `Zbiorczy` | 1075 | — | **70** (w tym 3 wiersze `#N/A`) | 67 realnych |
| `Niewykorzystane rekordy` | 327 | — | **1** (sam `#N/A`) | realnie pusta |
| `Szkoły z DT` | 327 | — | **46** | |
| `Szkoły z cyklami` | 2 | — | **1** | realnie pusta |

**Wnioski dla v3:**

1. Realny wolumen leadów to **67 wierszy** (Sacawa 42 + Olszewska 25), a nie 70+.
   `Zbiorczy` to widok, nie źródło.
2. **Trzy z pięciu zakładek handlowców są puste.** Migracja v3 to nie „przenieś
   5 arkuszy" — to „przenieś 2 arkusze + bazę kontaktów". Reszta struktury jest
   przygotowana na przyszłość i nie ma czego z niej brać.
3. `BAZA` wypełniona jest **tylko w 7 kolumnach**: `A` (167 z 544 przypisanych),
   `E`, `F`, `G`, `H`, `I`, `J`. Kolumny `B`, `C`, `D`, `K` oraz **całe `L`–`AG`
   są puste** — `BAZA` jest książką adresową, nie rejestrem procesu.
4. Import MUSI iterować po jawnym zakresie, a nie po `ws.max_row` (Sacawa: 50 500
   wierszy, z czego 42 z danymi = 99,92 % pustych iteracji).

---

## B. Inwentarz kolumn A→AG (5 zakładek handlowców + `BAZA`, razem)

Kolumna „typy" = dosłownie to, co zwraca `openpyxl` przy `data_only=True`.

| Kol | Nagłówek | niepuste | unikalne | typy Pythona | przykłady dosłowne | WARTOŚCI ODSTAJĄCE |
|---|---|---|---|---|---|---|
| A | Handlowiec | 234 | 5 | `str` | `01. Sacawa`×196, `02. Olszewska`×29, `04. Chytry`×7, `03. Małolepsza`×1 | **`Bitner`** — jedyna wartość BEZ prefiksu (BAZA!A) |
| B | Status szkoły | 67 | 2 | `str` | `02. Kontynuacja`×56, `01. Nowa szkoła`×11 | — |
| C | Status realizacji | 61 | 3 | `str` | `03. DT umówione`×43, `02. Próba kontaktu (czekam na termin)`×13, `01. Próba kontaktu (Brak konkretów)`×5 | `04. BRAK KONTAKTU ZE SZKOŁĄ` **nie występuje ani raz** — a to na nim opiera się widok „Niewykorzystane rekordy" |
| D | death line | 13 | 5 | `datetime` (100 %) | `2026-07-03`×8, `2026-08-28`×2, `2026-07-14`, `2026-08-30`, `2026-08-31` | wypełnione w 13 z 611 wierszy (2 %) — „kontrola przed terminem" nie ma na czym pracować |
| E | Miejscowość | 611 | 21 | `str` | `08. Katowice`×90, `19. Zabrze`×51, `13. Sosnowiec`×46, `09. Pszczyna powiat`×45, `06. Rybnik`×43 | **`09. Pszczyna powiat`×45 obok `09. Pszczyna`×1**; **`10. Katowice`×5 obok `08. Katowice`×90**; `15. Będzin powiat`×41 |
| F | Numer placówki | 611 | 591 | `str` | `SP 6`, `sp1`, `MSP 1`, `SZKOŁA PODSTAWOWA NR 24 IM. POWSTAŃCÓW ŚLĄSKICH` | **trzy konwencje w jednej kolumnie**: skrót z odstępem (`SP 6`), skrót bez odstępu małą literą (`sp1`, `sp42`), pełna nazwa RSPO (95 znaków). Plus `Książenice`, `Piasek`, `EduHub`, `korczakowska`, `MSP 3 ZSP1`, `ZS 3 Rybnik` |
| G | Adres placówki | 553 | 391 | `str` | `ul. Szkolna`, `Thomasa Woodrowa Wilsona 22` | **`13.06 godz 9:00`** w `Olszewska!G` — data i godzina w kolumnie adresu |
| H | Osoby decyzyjne i kontakt | 360 | 355 | `str` | `Barbara Starek`, `DOMINIKA BRZEZINKA` | BAZA pisze KAPITALIKAMI, handlowcy normalnie |
| I | numer telefonu | 545 | 539 | `str`×544, **`float`×1** | `32 235 27 15`, `322525199` | **535 z 545 komórek to formuła `="322525199"`**; 1 komórka to `float`; w `Zbiorczy` i `Szkoły z DT` formuła ma postać `=IFERROR(__xludf.DUMMYFUNCTION(…),"32 235 27 15")` |
| J | mail | 551 | 541 | `str` | `msp1@knurow.edu.pl ` | spacja końcowa w wielu wartościach |
| K | Uwagi | 20 | 16 | `str` | `wrócić we wrześniu - nowa dyrektor, są chętni` | wolny tekst, do 200 znaków |
| L | DT | 62 | 2 | `str` | `01. Tak`, `02. Do ustalenia` | — |
| M | Data DT | 45 | 17 | `datetime` (100 %) | `2026-09-10`×5, `2026-09-16`×5 | 43 z 45 wpada we wrzesień 2026 — kalendarz demo musi startować od września |
| N | Godzina DT | 10 | 7 | **`time`×9, `timedelta`×1** | `08:55`×3, `10:45`×2, `08:00`, `09:50`, `07:45`, `12:30` | **`timedelta(seconds=31800)` = 08:50** — jedna komórka innego typu w tej samej kolumnie. Naiwny parser wywala się albo gubi wartość |
| O | Prowadzący DT | 48 | 9 | `str` | `04. Zemela`×18, `02. Olszewska`×14 | **`18. Młynarczyk Adam`** — prefiks 18 oznacza w liście `Y` osobę `18. Bitner`; **`20. Trener 1`** — prefiks 20 to w liście `Y` `20. Sacawa` |
| P | Numer sali DT | **0** | 0 | — | — | **PUSTA** — a notatki ze spotkania wymagają nr sali w kalendarzu |
| Q | mail propozycja/ustalenie DT | **0** | 0 | — | — | PUSTA (3 wartości tylko w `Zbiorczy`) |
| R | Ilość klas 1-4 | 10 | 5 | `str` (100 %) | `8 klas`×4, `10 klas`×2, `14 klas`×2, `12 klas`, `7 klas` | **nigdy nie jest liczbą** — zawsze `"N klas"` |
| S | Ilość dzieci w klasach | 9 | 6 | **`float`×5, `str`×4** | `około 240`×3, `190.0`×2, `około 200`, `330.0`, `340.0`, `170.0` | **dwa typy w jednej kolumnie**; `float` bo Excel, `str` bo „około" |
| T | Mail do rodziców (dziennik) | 0 | 0 | — | — | PUSTA |
| U | Cykle | 1 | 1 | `str` | `01. Tak` | wypełnione RAZ |
| V | Zajęcia cykliczne (dzień tygodnia) | 1 | 1 | `str` | `wtorek` | wypełnione RAZ — wielodniowe wpisy są w `[DT]`, patrz sekcja C |
| W | Numer sali cykle | 1 | 1 | **`time`** | `13:30:00` | **w kolumnie „numer sali" siedzi GODZINA** — kolumna używana wbrew nagłówkowi |
| X | Zajęcia cykliczne (godzina) | **0** | 0 | — | — | PUSTA w `[PH]`; w `[DT]` to najbrudniejsza kolumna w całym projekcie |
| Y | Trener | **0** | 0 | — | — | PUSTA — a ma własną, 40-pozycyjną listę walidacji |
| Z–AG | kolumny Julki | **0** | 0 | — | — | **wszystkie PUSTE** — cała rola Julki jeszcze nie ruszyła |

### B1. Rozjazd kolumn między zakładkami — potwierdzony pomiarem

`Zbiorczy` **nie ma kolumny `Z` „Mail z wnioskiem o wynajem sali"**. Nagłówki:

```
BAZA/handlowcy:  … Y=Trener   Z=Mail z wnioskiem o wynajem sali   AA=Dane do umowy …
Zbiorczy:        … Y=Trener   Z=Dane do umowy WYPEŁNIA JULIA      AA=Standardy …
```

Skutek: od kolumny `Z` wszystko jest przesunięte o 1, a `AG` w `Zbiorczym` to
**`Klucz`** (wielolinijkowa karta leada), `AH` = `trener`, `AI` = `kod do kalendarza`.
Import pozycyjny (po literze kolumny) da w `Zbiorczym` śmieci w 8 kolumnach.
**v3 musi mapować po nagłówku, nigdy po pozycji.**

### B2. Typy placówek w `BAZA!F` — typ JUŻ JEST w danych, tylko nie ma pola

| Rozpoznany typ | ile |
|---|---|
| szkoła podstawowa (`SZKOŁA PODSTAWOWA…`, `SP/MSP/ZSP/ZS/ZPO`) | 485 |
| **przedszkole** (`PRZEDSZKOLE…`) | **49** |
| inne szkoły (muzyczne, mistrzostwa sportowego, filialne) | 10 |
| instytucje kultury | **0** |

Czyli: notatka ze spotkania („RSPO da szkoły + przedszkola + instytucje kultury")
jest **już w połowie faktem** — 49 przedszkoli siedzi w bazie bez żadnego
oznaczenia typu. Instytucji kultury jeszcze nie ma, ale `norm_placowka` je rozpoznaje.

---

## C. Wartości odstające z `[DT]` — to one wysadzą naiwny parser

Kolumny odpowiadające `M`, `N`, `R`, `S`, `V`, `X`, `I`, `P` w pliku poprzedniego sezonu.

### C1. `M Data DT` — 68 z 100 komórek to STRING, nie data

Zakładka `Chytry BRUDNOPIS`, kolumna „Data i godzina DT" (`str`×68, `datetime`×32):

```
5-09-2025 8:00-9:35            10.09.2025 8:00-10:34       08.09.2025 od 8:00-9:10
26.11.2025 8:00-11:00          9:00 2025-10-21             2025-10-30 godzina 10:45
20.01.2026r. 9:30-13:00        24,04,2026 9:30-11:00       10:00 16 .10.2025
2025-09-08 08:00-11            2025-10-06 godz.9:50        22.09.2025  8:00- 10:30
7.10.2025 (4 klasy)   09.10.2025 (3 klasy)                 2025-09-18 09:45 i 12:15 w innej sali
17-09-2025 start 8:00       oraz 5 czerwca 15:30 piknik do 18:30
```

Nieparsowalne z założenia (brak roku albo brak daty):
`24.09 8:00 - 10:00` · `od 29.09 do 3.10 nie mozna` · ` 08:00- 10:35` · `.` ×2 ·
`usuwam natali z kalendarza` · `kontakt@malutkiemisie.pl` · `sekretariat@p1.dg.pl`

### C2. `N Godzina DT` — zakres, nie punkt (`str`×117, `time`×24)

```
8:00-11:30 ×10   8:00-10:00 ×7   9:30-11:00 ×5   8:55 - 12:45 ×2   08:00- 9.50
8:00-9:35        08:00-10:45     09:50-12:55     10:05 - 14:30     8:00 - 13:00
8:00-14:35       8:00-12:05      8:00-10:34      8:00 -11:30       15:00-16:00
```

Nagłówek klienta mówi wprost: *„GODZINA rozpoczęcia i zakończenia WZÓR: 08:00-12:30"*.
`[PH]` ma na to **jedną** kolumnę `N` typu `time` → **traci godzinę zakończenia**,
a bez niej detekcja kolizji trenera jest matematycznie niemożliwa (bug L10 z części 1).
**v3 musi mieć `godz_od` i `godz_do`.**

### C3. `X Zajęcia cykliczne (godzina)` — 1–3 zakresy + rozkład miesięczny w jednej komórce

```
13:30-14:30, 14:40-15:40  ×5      12:55-13:55, 14:00-15:00  ×3
13:40-14:40, 14:40-15:40  ×3      12:40-13:40, 13:50-14:50  ×2
9:40-10:40, 12:30-13:30, 13:30-14:30            (trzy grupy)
12:45-13.45 i 13:55-14:55                       (separator „i", kropka w minutach)
15:20-16:20 16:30-17:30                         (separator = spacja)
13:45-14:45\n14:50-15:50                        (separator = nowa linia)
PN. 12:25-13:25, 13:35-14:35\nPT. 11:25-12:25    (dwa dni w jednej komórce)
WT 15:00-16:00\nŚR. 15:00-16:00
2gi Piątek miesiąca : 13.30-14:15, daty:10.10, 14.11, 05.12, 09.01, 13,02, 13.03, …
3cia środa miesiąca 9:30-11:30 są 2 grupy 15 Października, 19 listopada, 17 grudnia, …
1wsze czwartki miesiąca 15:00-15:45   2 pażdziernik, 6 listopad, 4 grudzień, …
"2gi" Pon miesiąca 15:00:15:45   22.09, 13.10, 17.11, …      ← dwukropek zamiast myślnika
```

To nie jest „godzina". To **cały harmonogram grupy**: dzień tygodnia + 1–3 zakresy
+ reguła powtarzania (co tydzień / 2. w miesiącu / 3. środa) + lista dat wyjątków.
**v3 potrzebuje osobnej tabeli `grupy_cykliczne`** (lead, grupa, dzień, godz_od,
godz_do, reguła, trener) — jedno pole tekstowe tego nie udźwignie.

### C4. `V dzień tygodnia` — realnie WIELOWARTOŚCIOWE

```
Środa ×27   Poniedziałek ×26   Czwartek ×26   Wtorek ×19   Piątek ×18
Wtorek i środa ×3        Poniedziałek i piątek ×1
```

Plus skróty wplecione w tekst innej kolumny: `Czw`, `Pt`, `Wt`, `Śr`, `Pon`, `PN.`,
`PT.`, oraz **bez spacji przed godziną**: `Pon12:40-13:40`.
Walidacja klienta dopuszcza jedną wartość — dane mają dwie. Pole musi być listą.

### C5. `R`/`S` klasy i dzieci — jedna kolumna „klasy/dzieci" wg wzoru `10/186`

```
8/200 ×11   2/50 ×6   3/ ×5   8/ ×4   7/ ×4   8/150 ×3   13/254   4 / 60   /9   /40
8 klas ×5   4 klasy ×4   9 klas ×4   11 klas ×3   3 gr ×2
8 grup 140 dzieci        8 klas, 80 dzieci,       2 klasy 43 dzieci
/50 (ogl jest 120)       2/50 (ogl jest 120)      podzielone na 2:  277 dzieci 13 grup
sala nr 13 5gr 100 dzieci (1gr=20min)             8 klas 200 dzieci po 2 na 20 minut
```

Odstające: **`datetime(2025,7,30)`, `datetime(2025,2,20)`, `datetime(2025,1,20)`
w kolumnie liczbowej** (3 komórki) oraz `świetlica`, `jest tablica - mieć swój rzutnik`.
Parser MUSI zwrócić `None` dla daty — inaczej „ilość klas" = 2025.

### C6. `I telefon` — 6 formatów + wiele numerów w komórce

```
="601290441"        (formuła-tekst, 535 komórek w BAZA)
322672142.0         (float z Excela, 8-13 komórek)
32 235 27 15        32 2675035        32 25715 85        2 264 16 66  ← 8 cyfr!
32 264-13-00        (032) 267-49-96   32/266-10-02       (32) 220 13 78
693-873-496         512-328-878       +48 601 290 441
32 762 93 51, 32 762 93 57                      (dwa numery, przecinek)
(32) 258-35-66  lub  513 - 065 - 806            (dwa numery, słowo „lub")
32 211 62 29 \n693 945 512                      (dwa numery, nowa linia)
697989257 (można SMS)                           (numer + komentarz)
32 262 69 68 Anna Nauczycielka klas 1-3 tel: 505081686
Jolanta: 604063813, sekretariat: 32 266 75 78
785-61-99   253-93-09   254-51-24               ← 7 cyfr, brak kierunkowego
Szkolna 24  ·  Są cykliczne ×11  ·  telefon     ← w ogóle nie telefon
```

### C7. `#N/A` i formuły z eksportu Google Sheets

`Zbiorczy` i `Niewykorzystane rekordy` to arkusze liczone formułami przeniesionymi
z Google Sheets. Przy `data_only=True` **79 komórek zwraca tekst `#N/A`**,
a przy `data_only=False` formuły mają postać:

```
=IFERROR(__xludf.DUMMYFUNCTION("""VSTACK( FILTER(Sacawa!A2:Y1075, …))"""),"01. Sacawa")
=IFERROR(__xludf.DUMMYFUNCTION("""COMPUTED_VALUE"""),"32 235 27 15")
=IFERROR(__xludf.DUMMYFUNCTION("""COMPUTED_VALUE"""),"#N/A")
```

Dwa wnioski:

1. `#N/A` **nie jest daną** — musi być traktowany jak pusta komórka, inaczej wejdzie
   do bazy jako nazwa handlowca.
2. **Ostatni literał tekstowy w `IFERROR` to ostatnio policzona wartość.** To jest
   ratunek na wypadek pliku bez cache'a — dokładnie tego zabrakło importerowi v1,
   który w takiej sytuacji wczytywał 0 rekordów i meldował sukces (bug 13 z części 1).

---

## D. Moduł `leady_app_v3/parsers.py`

10 funkcji publicznych, zero zależności zewnętrznych, docstringi po polsku
z realnymi przykładami. Każda funkcja jest tolerancyjna: **śmieci dają `None`,
nigdy wyjątek** — jedna zła komórka nie może wysadzić importu 544 wierszy.

| Funkcja | Zwraca | Co obsługuje (skrót) |
|---|---|---|
| `parse_date(v)` | `date \| None` | `datetime`/`date`; ISO; `dd.mm.yyyy`, `dd-mm-yyyy`, `dd/mm/yyyy`, `dd,mm,yyyy`; `dd.mm.yy` → 20yy; datę **zanurzoną w tekście** (bierze pierwszą poprawną); serial Excela (z pluskwą 1900). Bez roku → `None` |
| `parse_time(v)` | `time \| None` | `time`, `datetime`, **`timedelta`** (zawija mod 24 h), `float` 0–1 jako część dnia, `float` ≥ 1 (część ułamkowa serialu), `"8:00"`, `"08:55"`, `"8.00"`, `"9:30:00"`, `"godz 9:40"`, `"15"`. `"330"` → `None` |
| `parse_time_range(v, ze_reszta=False)` | `(time\|None, time\|None)` lub `(start, koniec, reszta)` | pierwszy zakres; separatory `-`, `–`, `—`, `do`, spacja, `i`, nowa linia; `"8-9:35"`; z `ze_reszta=True` oddaje ogon (pozostałe zakresy + tekst) |
| `parse_time_ranges(v)` | `(list[(time,time)], list[str])` | WSZYSTKIE zakresy + reszta tekstu. Potrzebne, bo jedna komórka = 1–3 grupy cykliczne |
| `parse_int_loose(v)` | `int \| None` | `"10 klas"`→10, `"około 200"`→200, `"ok. 240"`→240, `330`→330, `"8/200"`→8, `"13?"`→13, `"/9"`→9. **`datetime` → `None`** |
| `parse_phone(v)` | `str \| None` | formuła `="601290441"`, `float`, wszystkie 6 formatów z C6, `+48`/`0048`, wiele numerów → `", "`. Format: stacjonarny `32 235 27 15`, komórkowy `601 290 441` |
| `parse_dni_tygodnia(v)` | `list[str]` | pełne nazwy, odmiany (`poniedziałki`, `czwartki`), skróty (`Pon`, `PN.`, `Wt`, `Śr`, `Czw`, `Pt`), **skrót bez spacji** (`Pon12:40`), wiele dni w jednej wartości. Wynik zawsze w kolejności tygodnia |
| `strip_prefix(v)` | `(str\|None, str)` | `"01. Sacawa"` → `("01", "Sacawa")`. Prefiks jako `str` (wiodące zero!). Wymaga kropki/nawiasu, żeby `"8 klas"` nie stało się prefiksem |
| `norm_slownik(v, rodzaj, aliasy=None)` | `str \| None` | 5-stopniowe rozstrzyganie: alias → trafienie dokładne → **trafienie po części nazwowej** → dopasowanie rozmyte (Levenshtein ≤ 1, tylko jednoznaczne). Wartość nieznana wraca oczyszczona (nic nie ginie) |
| `norm_placowka(v)` | `(typ, nazwa_krótka)` | typ ∈ `szkoła / przedszkole / instytucja kultury / nieznany`; `"sp1"`→`("szkoła","SP 1")`, `"SZKOŁA PODSTAWOWA NR 24 IM. …"`→`("szkoła","SP 24")`, `"PM20"`→`("przedszkole","PM 20")` |

Dane (nie kod): `SLOWNIKI` (10 list kanonicznych), `ALIASY` (mapowania literówek
per rodzaj), `DNI_TYGODNIA`, `TYPY_PLACOWKI`, `RODZAJE_SLOWNIKOW`.

### D1. Jedna decyzja projektowa, którą trzeba znać

**Prefiks numeryczny u klienta NIE JEST identyfikatorem.** Dowód z danych:

| Prefiks | w liście `Y` (40 poz.) | w liście `O` (24 poz.) | w kolumnie A kalendarza (23 poz.) |
|---|---|---|---|
| 18 | `18. Bitner` | `18. Młynarczyk Adam` | `18. Młynarczyk Adam` |
| 20 | `20. Sacawa` | `20. Trener 1` | `20. Trener 1` |
| 21 | `21. Płaszczymąka` | `21. Trener 2` | **`21. Trener 3`** |
| 22 | `22. Kopczyński` | `22. Trene 3` | `22. Trener 4` |
| 23 | `23. Bednarek` | `23. Trener 4` | `23. Trenner 5` |
| 24 | `24. Palus` | `24. Trener 5` | — |

Dlatego w v3: **tożsamością jest część nazwowa**, prefiks to atrybut sortowania
i **może się powtarzać** w liście kanonicznej. `norm_slownik` dopasowuje po nazwie,
nie po numerze — i tylko dzięki temu `10. Katowice` → `08. Katowice`,
`17. Dąbrowa Górnicza` → `14. Dąbrowa Górnicza`, `23. Trener 4` → `22. Trener 4`
działają bez wypisywania 40 aliasów ręcznie.

### D2. Naprawiane literówki (dane w `ALIASY`, nie w kodzie)

| Wejście | Wyjście | Źródło rozjazdu |
|---|---|---|
| `02. Olaszewska` | `02. Olszewska` | walidacja `Sacawa!A20:A200`, `Olszewska!A29:A340` |
| `11. Białass (Pszczyna)` | `11. Białas (Pszczyna)` | `Kalendarz *!A13` vs walidacja `Y` |
| `23. Trenner 5` | `24. Trener 5` | `Kalendarz *!A25` vs walidacja `O` |
| `22. Trene 3` | `21. Trener 3` | walidacja `O` vs `Kalendarz *!A23` |
| `23. Trener 4` | `22. Trener 4` | walidacja `O` vs `Kalendarz *!A24` |
| `09. Pszczyna powiat` | `09. Pszczyna` | `BAZA!E` vs zakładki handlowców |
| `15. Będzin powiat` | `15. Będzin` | to samo |
| `19. Chorzow` | `16. Chorzów` | walidacja `Sacawa!E14:E200` (własna numeracja) |
| `10. Katowice` | `08. Katowice` | to samo |
| `17. Dąbrowa Górnicza` | `14. Dąbrowa Górnicza` | **dublet w JEDNEJ liście** walidacji |
| `21. Strzyzowice` | `21. Strzyżowice` | walidacja `E4:E13` |
| `11. Zabrze`, `12. Ruda Śląska`, `13. Świętochłowice`, `14. Siemianowice Śląskie`, `15. Piekary Śląskie`, `16. Dąbrowa Górnicza`, `17. Sosnowiec`, `20. Ornontowice`, `21. Wyry`, `22. Gostyń`, `08. Katowice Południe` | numeracja z `BAZA` | rozjazd całej listy Sacawy |
| `31.` … `40.` | `None` | puste pozycje listy trenerów |
| `#N/A`, `#REF!`, `=B2+1`, `=XLOOKUP(…)` | `None` | błędy i formuły to nie dane |

---

## E. Testy — `leady_app_v3/test_parsers.py`

```
$ python test_parsers.py
Ran 93 tests in 0.066s
OK
```

**93 przypadki, 0 błędów.** Struktura: 12 klas testowych (jedna na funkcję +
`TestBledyFormul` + `TestOdpornoscOgolna`) + 10 doctestów wciąganych przez
`load_tests`. Każdy przypadek ma w komentarzu znacznik źródła `[PH]` / `[DT]` / `[WAL]`
i lokalizację komórki — **żadna wartość testowa nie jest wymyślona**.

Testy pilnują też trzech niezmienników, których łatwo nie zauważyć:

* `test_slowniki_sa_stabilne` — każda wartość kanoniczna normalizuje się do siebie
  (`norm_slownik(v) == v`), więc powtórny import nie przesuwa danych
* `test_slowniki_maja_unikalne_nazwy` — prefiks może się dublować, **nazwa nie**
* `test_aliasy_wskazuja_na_istniejace_wartosci` — żaden alias nie prowadzi poza słownik
* `test_nic_nie_wybucha` — 26 rodzajów śmieci × 10 funkcji × 10 rodzajów słowników

Trzy testy to regresje na **realnych bugach znalezionych w trakcie pisania**:

1. `test_regresja_przedszkole_nie_jest_szkola` — wzorzec `SZKO[ŁL]` bez `\b` trafiał
   w środek słowa **PRZED-SZKOL-E** i klasyfikował 49 przedszkoli jako szkoły
2. `test_liczba_ze_slowem_to_nie_prefiks` — `strip_prefix("8 klas")` nie może dać `("8","klas")`
3. `test_zakres_godzin_to_nie_data` — `parse_date("12.35-13.35")` nie może dać miesiąca 35

---

## F. Wynik przepuszczenia WSZYSTKICH danych przez parsery

Skrypt: `scratchpad/przepusc_dane.py`. Przepuszczono 10 zakładek z `[PH]`
i 5 z `[DT]`. Kryterium niesparsowania: niepuste wejście dało `None` /
pustą listę / `(None, None)`, a dla `norm_slownik` — wynik poza listą kanoniczną.

| Parser | wartości | sparsowane | niesparsowane | skuteczność |
|---|---|---|---|---|
| `norm_slownik/handlowiec` | 348 | 348 | 0 | **100 %** |
| `norm_slownik/miejscowosc` | 725 | 725 | 0 | **100 %** |
| `norm_slownik/trener` | 141 | 141 | 0 | **100 %** |
| `norm_slownik/status_realizacji` | 167 | 167 | 0 | **100 %** |
| `norm_slownik/status_szkoly` | 181 | 181 | 0 | **100 %** |
| `norm_slownik/dt` | 171 | 171 | 0 | **100 %** |
| `norm_slownik/tak_nie` | 4 | 4 | 0 | **100 %** |
| `parse_date` [PH] | 168 | 168 | 0 | **100 %** |
| `parse_time` [PH] | 31 | 31 | 0 | **100 %** |
| `parse_phone` [PH] | 559 | 559 | 0 | **100 %** |
| `parse_int_loose` [PH] | 53 | 53 | 0 | **100 %** |
| `parse_dni_tygodnia` [PH] | 4 | 4 | 0 | **100 %** |
| `norm_placowka` [PH] | 725 | 713 | 12 | 98,3 % |
| `parse_time_range` [DT] | 312 | 308 | 4 | 98,7 % |
| `parse_date` [DT] | 335 | 324 | 11 | 96,7 % |
| `parse_int_loose` [DT] | 319 | 308 | 11 | 96,6 % |
| `norm_placowka` [DT] | 191 | 187 | 4 | 97,9 % |
| `parse_phone` [DT] | 345 | 326 | 19 | 94,5 % |
| `parse_dni_tygodnia` [DT] | 280 | 244 | 36 | 87,1 % |
| kolumny tekstowe (bez parsowania) | 1 616 | 1 616 | 0 | — |

**RAZEM: 6 675 wartości · sparsowane 6 578 · niesparsowane 97 (1,45 %).**
Dodatkowo pominięto **79 komórek z błędem formuły** (`#N/A`) — nie są danymi.

### F1. Plik, który v3 MUSI zaimportować (`PH Nowy`) — bez ręcznego czyszczenia

**Wszystkie parsery skalarne i wszystkie słowniki: 100 %.**
Jedyne 12 wartości „niesparsowanych" to `norm_placowka` zwracające typ `nieznany`
dla nazw, które faktycznie nie mają w sobie żadnego znacznika typu:

| Wartość | ile | Co to jest |
|---|---|---|
| `EduHub` | 4 | niepubliczna szkoła w Katowicach (w `BAZA` jest jako `NIEPUBLICZNA SZKOŁA PODSTAWOWA EDUHUB W KATOWICACH`) |
| `Książenice` | 3 | szkoła w dzielnicy Rybnika |
| `Piasek` | 3 | szkoła w gminie Pszczyna |
| `korczakowska` | 2 | `KORCZAKOWSKA SZKOŁA MARZEŃ W KATOWICACH` |

To nie jest błąd parsera — to **4 unikalne placówki, które handlowiec zapisał
potoczną nazwą dzielnicy/patrona**. Rozwiązanie w v3: przy imporcie te 4 rekordy
lądują na liście „do potwierdzenia typu" (jedno kliknięcie), a `nr RSPO`
albo dopasowanie do `BAZA!F` uzupełni je automatycznie.

### F2. Pełna lista wartości NIESPARSOWANYCH — każda świadoma

Plik `[DT]` (poprzedni sezon, import opcjonalny). Grupy:

**(a) Wolny tekst w kolumnie, która nie jest jego kolumną** — 36 wartości
w `parse_dni_tygodnia` i 4 w `parse_time_range`. Kolumna `Cykliczne / sala /
dodatkowe info` jest u klienta workiem na wszystko:

```
LAPTOPY ×5 · INFORMATYCZNA ×4 · WŁASNE LAPTOPY · Zuza i Damian · rzutnik swój
Nikt się nie zapisał · nikt się nie zapisał :( · NIKT SIĘ NIE WPISAŁ :(
dyrekcja mówi że nikt się nie zapisał · 3 osoby zapisane - co dalej? · ??? lista???
mało osób · NA CYKLICZNE  wpisało sie tylko 3 osoby
Chcą nas co miesiąć - nie mają konkretnych dat - trenerki ustalają terminy
Maja ustala terminy - Chcą nas co miesiąc · 2 x miesiąc, ustalane po zebraniu grupy
*po feriach wynajem sali · dyr. urlop
wysłałam maila bo pani wice dyrekto jest zajęta - cykliczne będą ustalane po DT
JEDNORAZOWE CHCĄ ZAJĘCIA W PAŹDZIERNIKU 1 DZIEŃ I NIE CYKICZNIE CO MIESIĄC…
NIE MA NIKOGO NA LIŚCIE ZADZWONIĆ O JEDNORAZOWE ZAJĘCIA
2026 kaledarz- CHCĄ NAS W STYCZNIU NA DZIEŃ DZIADKA/BABCI… MGR MONIKA MAJDA TEL: 608296539
32 353 91 40  biuro@wesoly-przedszkolak.pl ul. Armii Krajowej 268,
Najem start 1 najmu  zawsze 8:00 do 8:45 start 11 września potem 9 październik, …
Wstępnie ustalony termin ZAJĘCIA CYKLICZNE 1\nAkademia wyobraźni Będzin\n9:30-11:30\n2gr
O 12:40-13:40 - > TA GRUPA ZAMIENIA SIE NA 14:50-15:50 sala nr. 32 cykliczne 13.10.2025, …
lista pusta jest tylko 1 osoba w active now/ dzwonić miedzy  9-11 …
10:15-11:00\n11.05,  18.06 mamy umowę do maja 2027 …
15 osób - wysłany mail o terminach zajęć kiedy możemy zacząć\n27.04.2026 od godziny 14.30-15:15…
```

**Werdykt:** to notatki, nie dane strukturalne. W v3 idą do pola `uwagi`, a nie
do `cykl_dzien` / `cykl_godz`. Parser poprawnie odmawia ich interpretacji.

**(b) Wiersze nagłówkowe powtórzone w danych** — 6 wartości:
`ilość dzieci/ klas`, `ilość dzieci/klasy`, `ILOŚĆ DZIECI /KLAS`, `Cykliczne data`,
`Cykliczne / sala / dodatkowe info`, `CYKLICZNE ZAJĘCIA`, `Data i godzina DT`,
`DT Data i godz`, `telefon`, `TELEFON`.
**Werdykt:** import musi pomijać wiersze, których treść równa się nagłówkowi.

**(c) Daty nie do odzyskania** — 5 wartości:
`24.09 8:00 - 10:00` i `od 29.09 do 3.10 nie mozna` (brak roku — zgadywanie
wsadziłoby DT w zły rok szkolny), ` 08:00- 10:35` (sama godzina), `.` ×2.
**Werdykt:** świadome `None`; import raportuje je jako „data do uzupełnienia".

**(d) Wartości w złej kolumnie** — 5:
`kontakt@malutkiemisie.pl` i `sekretariat@p1.dg.pl` w kolumnie daty ·
`Szkolna 24` w kolumnie telefonu · `Są cykliczne` ×11 i `Cykliczne` w kolumnie
telefonu · `usuwam natali z kalendarza` · `Nie są zainteresowani ofertą…` ·
`świetlica`, `jest tablica - mieć swój rzutnik`, `do ustalenia w sekretariacie`,
`EDIT: Natalka napisała na telegramie że zwykła ////…` w kolumnach liczbowych.
**Werdykt:** `None` + wpis do raportu importu.

**(e) `datetime` w kolumnie „ilość klas/dzieci"** — 3 komórki
(`2025-07-30`, `2025-02-20`, `2025-01-20`).
**Werdykt:** świadome `None` — najgorszy możliwy błąd byłby tu „ilość klas = 2025".

**(f) Telefony niepełne — WYMAGAJĄ DECYZJI KLIENTA** — 4 komórki:

| Wartość | Cyfr | Problem |
|---|---|---|
| `785-61-99` | 7 | stary numer bez kierunkowego (prawdop. `32 785 61 99`) |
| `253-93-09` | 7 | to samo |
| `254-51-24` | 7 | to samo |
| `2 264 16 66` | 8 | brakuje jednej cyfry (prawdop. `32 264 16 66`) |

**Werdykt:** parser zwraca `None` zamiast zgadywać kierunkowy. To jedyne 4 wartości
z całego zbioru, które naprawdę wymagają pytania do klienta.

---

## G. Wnioski wykonawcze dla v3 (z części 2)

1. **Import po nagłówku, nie po pozycji.** `Zbiorczy` nie ma kolumny `Z` — import
   pozycyjny da śmieci w 8 kolumnach.
2. **Dane od wiersza 4** (handlowcy, `BAZA`) lub 2 (widoki); pomijać wiersze
   powtarzające nagłówek; iterować po jawnym zakresie, nie po `max_row`
   (Sacawa: 50 500 wierszy na 42 z danymi).
3. **Czytać `data_only=True`**, a formuły traktować jako brak danych — z jednym
   wyjątkiem: `="literał"` i `IFERROR(__xludf.DUMMYFUNCTION(…),"wartość")`.
   `#N/A` = pusta komórka. (`parsers._txt` robi to w jednym miejscu dla wszystkich funkcji.)
4. **Rozbić `N Godzina DT` na `godz_od` + `godz_do`.** Bez godziny zakończenia
   detekcja kolizji trenera jest niemożliwa — a to sztandarowa funkcja na demo.
5. **`X Zajęcia cykliczne (godzina)` to nie pole, to tabela.** Jedna komórka realnie
   opisuje 1–3 grupy z regułą powtarzania i listą wyjątków → tabela `grupy_cykliczne`.
6. **`V dzień tygodnia` musi być wielowartościowe** (`Poniedziałek i piątek`,
   `Wtorek i środa` — 4 realne komórki).
7. **`R`/`S` przechowywać jako `int` + zachować tekst źródłowy** (`około 240`).
   Klient wpisuje szacunki i chce je widzieć.
8. **Typ placówki wyliczać przy imporcie** — 49 przedszkoli już siedzi w `BAZA`
   bez oznaczenia; 4 placówki wymagają jednego kliknięcia potwierdzenia.
9. **Prefiks nie jest kluczem.** Tożsamość = nazwa; prefiks = kolejność sortowania,
   edytowalna w słownikach, dopuszczalnie zdublowana.
10. **Raport z importu jest funkcją, nie logiem.** Ma pokazywać: ile wierszy,
    ile wartości znormalizowanych (i z czego na co), ile do uzupełnienia ręcznego.
    Na realnym pliku klienta ten raport zawiera dziś **16 pozycji** — to jest
    do pokazania klientowi jako dowód, że system pilnuje jego danych.

## H. Pytania do klienta wynikające z danych

1. **4 niepełne telefony** (`785-61-99`, `253-93-09`, `254-51-24`, `2 264 16 66`) —
   dopisać kierunkowy `32`?
2. **`08. Katowice Południe`** — to osobny rejon czy wariant `08. Katowice`?
   (`parsers.py` trzyma je dziś jako `25. Katowice Południe`, osobno.)
3. **`Bitner` w `BAZA!A`** bez prefiksu — to handlowiec, czy trener wpisany
   w złą kolumnę? (W liście trenerów jest `18. Bitner`.)
4. **`04. BRAK KONTAKTU ZE SZKOŁĄ`** nie występuje w żadnym wierszu, a to na nim
   opiera się widok „Niewykorzystane rekordy" — status jest nieużywany, czy proces
   jeszcze nie ruszył?
5. **`Trener 1`…`Trener 5`** — to miejsca na przyszłych trenerów, czy anonimizacja
   istniejących osób? Od tego zależy, czy w v3 mają być rekordami, czy placeholderem.
6. **Kolumna `W Numer sali cykle`** zawiera godzinę `13:30` — pomyłka wpisu,
   czy kolumna jest używana wbrew nagłówkowi?
