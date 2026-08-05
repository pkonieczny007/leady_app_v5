# Handoff: Nowy frontend „System Leadów"

## Cel
Modernizacja wyglądu istniejącej aplikacji Flask (`leady_app`) — zarządzanie leadami
szkół, grafikiem DT i handlowcami. Zadanie: przenieść nowy wygląd na istniejący
projekt **bez zmiany logiki, danych i API** — te zostają. Zmienia się warstwa
prezentacji (szablony Jinja + CSS).

## O plikach w tym pakiecie
Pliki w tym pakiecie to **referencje projektowe wykonane w HTML** — makieta pokazująca
docelowy wygląd i zachowanie, a NIE kod produkcyjny do skopiowania 1:1.
- `System Leadów.dc.html` — makieta jest napisana jako „Design Component" i działa na
  osobnym runtime podglądu; **nie wrzucaj jej wprost do Flaska.** Traktuj ją jako
  wzorzec wyglądu, z którego odczytujesz layout, kolory, typografię i zachowania.
- `starty-czerwiec.js` — realne dane zakładki „STARTY CZERWIEC" sparsowane do struktury
  (tylko pomocniczo, do zrozumienia widoku Starty; w aplikacji dane pochodzą z bazy).

Zadanie polega na **odtworzeniu tego wyglądu w istniejącym środowisku aplikacji**
(Flask + Jinja2 + zwykły CSS/JS w `static/`), używając jej obecnych wzorców:
`templates/base.html` + `pulpit.html` / `tabela.html` / `kalendarz.html` / `slowniki.html`
oraz `static/style.css` i `static/app.js`. Trasy, modele i endpointy API
(`/api/lead/...`, `/api/slownik/...`, import/eksport XLSX) zostają nietknięte.

## Fidelity
**High-fidelity (hifi).** Makieta ma finalne kolory, typografię, odstępy i interakcje.
Odtwórz UI wiernie, zachowując istniejące `{{ }}` Jinja i podpięcie pod prawdziwe dane.

## System wizualny (Broadsheet)
Styl gazetowy: serif na papierowym tle, dwa akcenty (cyan, magenta) używane oszczędnie,
hierarchia budowana skalą pisma i światłem — bez ramek/pudełek do budowy layoutu.

### Tokeny — wklej do `:root` w `static/style.css`
```css
:root{
  --color-bg:#f3f2f2;         /* papierowe tło całej strony */
  --color-surface:#eae9e9;    /* wypełnienie kart / pól formularzy */
  --color-text:#201e1d;       /* niemal czarny tekst */
  --color-divider:color-mix(in srgb,#201e1d 16%,transparent);
  --color-accent:#0088b0;     /* cyan — elementy interaktywne, cykliczne */
  --color-accent-700:#006786; /* cyan tekst na jasnym tle */
  --color-accent-100:#e9f8ff; /* cyan tło tagów */
  --color-accent-800:#004961;
  --color-accent-2:#d6006c;   /* magenta — alerty, STARTy, kolizje */
  --color-accent-2-600:#d82071;
  --color-accent-2-700:#aa0b56;
  --color-accent-2-100:#fff1f4;
  --color-neutral-100:#f8f4f4; --color-neutral-200:#eae7e7;
  --color-neutral-300:#d7d3d3; --color-neutral-500:#9b9797;
  /* skala odstępów (density 1.25×) */
  --space-1:5px; --space-2:10px; --space-3:15px; --space-4:20px; --space-6:30px; --space-8:40px;
  --radius-sm:1px; --radius-md:2px; --radius-lg:4px;
  --shadow-sm:0 1px 2px color-mix(in srgb,#2d2b2b 14%,transparent);
  --shadow-md:0 3px 10px color-mix(in srgb,#2d2b2b 16%,transparent);
}
body{ background:var(--color-bg); color:var(--color-text);
  font-family:"Source Serif 4",Georgia,serif; font-size:15px; line-height:1.55; }
```
Font: **Source Serif 4** (Google Fonts, wagi 400/600 + italic 400) — jeden krój na
nagłówki i treść. Nagłówki weight 600, `letter-spacing:-0.015em`. Kicker/etykiety:
11px, UPPERCASE, `letter-spacing:.08–.14em`, kolor `--color-accent-700`.

### Zasady
- Sekcje rozdzielaj **światłem i cienką linią** (`border-bottom:1px solid var(--color-divider)`),
  nie ramkami. Karty (`.card`, tło `--color-surface`) tylko dla dyskretnych elementów
  (pozycje słowników, karty startów) — nigdy do budowy układu.
- Cyan = interaktywne i cykliczne. Magenta = tylko alerty / STARTy / kolizje. Nie łącz
  obu akcentów w jednym małym komponencie.
- Liczby: `font-variant-numeric:tabular-nums`. Kolumny liczbowe wyrównane do prawej.
- Focus: `:focus-visible{ outline:2px solid var(--color-accent); outline-offset:2px; }`.
- Cały layout na desktop, max szerokość treści ~1360px, wyśrodkowana, padding boczny `--space-6`.

## Pasek górny (`base.html`)
Zostaje jak dziś (górna nawigacja), ale przestylowany:
- Tło `--color-bg`, dolna linia `1px solid var(--color-divider)` (zamiast granatowego paska).
- Brand „System Leadów" serif 18px + mały tag `demo · zamiast arkusza`
  (11px, UPPERCASE, ramka `1px var(--color-accent-300)`, `border-radius:2px`, `white-space:nowrap`).
- Linki nawigacji: kolor `--color-text`; aktywny/hover `--color-accent`, aktywny weight 600.
- Po prawej: „↓ Pobierz XLSX" (`.btn-secondary` — ramka), „↑ Import" (`.btn-primary` — cyan fill).
- Panel importu: rozwijany pod paskiem, tło `--color-surface`, `border-top:1px solid var(--color-divider)`.

### Klasy komponentów (przenieś do `style.css`)
```
.btn{font-family:serif;font-weight:600;font-size:14px;padding:10px 18px;border-radius:2px;
  border:1px solid transparent;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.btn-primary{background:var(--color-accent);color:var(--color-bg)}
.btn-primary:hover{background:#1186ac}
.btn-secondary{border-color:var(--color-divider);background:transparent;color:var(--color-text)}
.btn-secondary:hover{background:color-mix(in srgb,var(--color-text) 7%,transparent)}
.tag{font-size:11px;padding:3px 10px;border-radius:1.5px}
.tag-accent{background:var(--color-accent-100);color:var(--color-accent-800)}
.tag-accent-2{background:var(--color-accent-2-100);color:var(--color-accent-2-700)}
.tag-outline{border:1px solid var(--color-accent);color:var(--color-accent)}
.input{width:100%;min-height:36px;padding:6px 10px;font:inherit;font-size:14px;
  background:var(--color-surface);border:1px solid var(--color-divider);border-radius:2px}
.input:focus-visible{border-color:var(--color-accent);outline:none}
.card{background:var(--color-surface);border-radius:2px;padding:15px;display:flex;flex-direction:column;gap:10px}
.table{width:100%;border-collapse:collapse;font-size:14px}
.table th{text-align:left;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:color-mix(in srgb,var(--color-text) 60%,transparent);padding:10px;
  border-bottom:1px solid var(--color-divider)}
.table td{padding:10px;border-bottom:1px solid color-mix(in srgb,var(--color-text) 8%,transparent)}
.table tbody tr:hover{background:color-mix(in srgb,var(--color-text) 4%,transparent)}
```

## Ekrany

### 1. Pulpit (`pulpit.html`)
- **Nagłówek**: kicker „Przegląd · <miesiąc>" + `<h1>Pulpit</h1>` (~46px serif).
- **Pasek wskaźników**: rząd flex, gap `--space-8`, `border-bottom` pod spodem. Każdy
  wskaźnik = wielka liczba (serif ~52px, `line-height:.95`) + etykieta pod nią (12px,
  60% ink). Kolejność: `total` leadów, `DT umówione` (cyan), `z ustaloną datą DT`,
  `po terminie` (magenta), `kolizji trenerów` (magenta). Alertowe liczby w `--color-accent-2-600`.
- **Dwie kolumny** (grid `1.15fr 1fr`, gap `--space-8`):
  - Lewa: „Po terminie" (`overdue`) — `.table`: Deadline (magenta, tło `--color-accent-2-100`),
    Handlowiec, Placówka, Miejscowość, Status (`.tag-outline`). Pod nią „Kolizje trenerów"
    (`kolizje`) — Data, Trener (z kropką koloru), Godziny (magenta bold), Placówka.
  - Prawa: „Podział wg handlowca" (`per_h`) — Handlowiec, Leadów (prawo), DT umówione (prawo),
    Postęp = pasek: tło `--color-neutral-200`, wypełnienie `--color-accent`, szerokość = `u/c%`.

### 2. Tabela (`tabela.html`)
- **Nagłówek**: kicker „Rejestr leadów" + `<h1>Tabela</h1>`.
- **Pasek filtrów** (flex, gap `--space-2`): select handlowiec, select status, search
  (placeholder „szukaj: placówka / miejscowość…"), „Wyczyść" (`.btn-secondary`); po prawej
  licznik „{n} rekordów" (13px, muted) i „+ Nowy lead" (`.btn-primary`). Wszystkie pola `.input`.
- **Siatka** (`.table`, `min-width:1000px`, poziomy scroll, `overflow-x:auto`): kolumny
  #, Handlowiec, Placówka (bold), Miejscowość (muted), Status realizacji, Deadline,
  Data DT (muted), Prowadzący DT (kropka koloru trenera + nazwa), Klas (prawo), Dzieci (prawo).
  - **Edycja inline** zachowana: Status jako `<select>` w komórce (styl „lead-cell": brak
    ramki, tło transparent, hover tło `--color-accent 9%`). Zmiana → istniejące `PATCH /api/lead/<id>`.
  - **Przeterminowane**: komórka Deadline z tłem `--color-accent-2-100` i tekstem
    `--color-accent-2-700` bold, gdy `deadline < dziś` i status nie zaczyna się od „03." i brak DT.
- Legenda pod tabelą (12px, muted): kwadrat magenta = przekroczony deadline; nota o wymuszonych listach.

### 3. Kalendarz DT (`kalendarz.html`) — TRZY WIDOKI (przełącznik segmentowy)
Nagłówek: kicker „Grafik trenerów · <miesiąc>" + `<h1>Kalendarz DT</h1>`. Po prawej licznik
spotkań/kolizji + segmentowy przełącznik (`.seg` / `.seg-opt`, aktywny = cyan fill) z trzema
opcjami: **▦ Macierz**, **☰ Agenda**, **▤ Starty**. Przełącznik można trzymać w query param
`?widok=` (jak dziś `widok`).

- **Macierz** (rozbudowa obecnego „miesiąc"): tabela trener × dzień. Sticky pierwsza kolumna
  (trener + kropka koloru) i sticky nagłówek. Nagłówki dni: mały DOW (UPPERCASE) + duży numer
  (serif ~19px). Komórka dnia = stos kafli. Kafel: `border-left:3px solid <kolor trenera>`,
  tło `color-mix(in srgb,<kolor> 12%,var(--color-bg))`, `border-radius:2px`, padding 4px 7px;
  godziny bold (kolor `color-mix(<kolor> 70%,#000)`), placówka bold 11.5px, miejscowość muted.
  Kolizja: tło `--color-accent-2-100`, lewy border magenta, tag „kolizja" (magenta fill, białe).
- **Agenda** (nowy, czytelny): grid `120px 1fr` na dzień, dolna linia. Lewo: DOW + wielki numer
  dnia (serif ~40px) + miesiąc. Prawo: lista spotkań (sort po godzinie), każdy wiersz: kropka
  koloru trenera, godziny (bold, tabular), placówka (bold), „· miejscowość" (muted), po prawej
  nazwisko trenera; kolizja → tło `--color-accent-2-100` + tag „kolizja".
- **Starty** (odwzorowanie zakładki „STARTY CZERWIEC" — DUŻE, CZYTELNE DANE): tygodnie jeden
  pod drugim; każdy tydzień = grid 5 kolumn (Pon–Pt), `align-items:start`. Kolumna dnia:
  nagłówek z wielkim numerem daty (serif ~34px) + DOW + „{n} zajęć" (cyan), pod nim
  `border-bottom:2px solid var(--color-text)`. Poniżej stos **kart** zajęć (`.card`,
  `border-left:4px solid` — magenta dla STARTU, cyan dla cyklicznych):
    - górny wiersz: badge typu (START = magenta fill/biały; CYKLICZNE = tag cyan) + godziny (bold ~15px, prawo);
    - nazwa placówki (serif bold 16px), adres (muted 12px);
    - meta „Gr. {grupa} · {sala/laptopy}" (12px, `--color-accent-800`);
    - „TRENER {nazwa}" (etykieta 11px uppercase muted + nazwa 13px); opcjonalnie „Zastępstwo:";
    - stopka: kod dzieci (mono 11.5px, tło `--color-neutral-100`, `padding:2px 7px`) + link „Tinkercad ↗".
  Źródło danych: rekordy `leady` z ustaloną `data_dt`/cyklem, pogrupowane po tygodniu i dniu
  roboczym; typ START vs CYKLICZNE z pola statusu/rodzaju wpisu. Struktura pól widoczna w
  `starty-czerwiec.js` (school, address, grupa, godz, sprzet, trener, zastepstwo, drukarz, kod, link).

### 4. Słowniki (`slowniki.html`)
- Nagłówek: kicker „Jedno źródło list" + `<h1>Słowniki</h1>` + akapit wyjaśniający (muted, max 70ch).
- Grid kart `repeat(auto-fill,minmax(230px,1fr))`, gap `--space-4`. Każda karta (`.card .elev-sm`):
  kicker „{n} pozycji", tytuł (nazwa słownika), lista pozycji (każda: opcjonalna próbka koloru
  14×14 dla trenerów, nazwa, przycisk „✕" ghost), na dole pole „nowa pozycja…" + „+" (`.btn-primary`).
- Trenerzy: kolor jako próbka (`<input type="color">` w realnej wersji, zapis przez `PATCH /api/slownik/<id>`).

## Interakcje i zachowanie
- Nawigacja: górny pasek przełącza ekrany (osobne trasy Flask, jak dziś).
- Filtry tabeli: submit GET (jak obecnie) lub live; zachowaj `handlowiec/miasto/status/q`.
- Edycja komórki: `change` → `PATCH /api/lead/<id>` z `{field,value}`; toast „Zapisano",
  rollback na błąd (logika `app.js` zostaje). Po zmianie deadline/statusu przelicz podświetlenie.
- Przełącznik widoku kalendarza: zapis w `?widok=macierz|agenda|starty`.
- Toast: prawy dolny róg, ciemny (`--color-neutral-900` tło), `--color-accent-2` przy błędzie.
- Stany focus/hover/pressed z rampy akcentów (patrz tokeny). Bez domyślnego niebieskiego focusa.

## Zależności zewnętrzne
- Google Fonts: Source Serif 4 (`ital,wght@0,400;0,600;1,400`). Reszta to czysty CSS — bez bibliotek.
- Ikony: znaki tekstowe (↓ ↑ ▦ ☰ ▤ ✕ ↗) lub Phosphor (duotone) jeśli chcesz spójny zestaw.

## Pliki w tym pakiecie
- `System Leadów.dc.html` — makieta wszystkich czterech ekranów + trzech widoków kalendarza (referencja wyglądu).
- `starty-czerwiec.js` — sparsowane dane „STARTY CZERWIEC" (struktura pól karty startu).
- `README.md` — ten dokument (samowystarczalny opis do implementacji).
