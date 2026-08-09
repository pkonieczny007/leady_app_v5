# Plan v5 — profile, formularz terenowy, wdrożenie

**Punkt startowy:** `leady_app_v4` = commit `33d9874` „PRZED SPOTKANIEM 06.08" (wersja zaprezentowana 06.08, funkcje zatwierdzone).
**Termin twardy:** wtorek 11.08.2026 — handlowcy zaczynają pracować na aplikacji.
**Priorytet nr 1:** handlowiec w terenie wpisuje szybko i bez błędów. Wszystko inne jest niżej.

## Decyzje podjęte 07.08

| Temat | Decyzja |
|---|---|
| Logowanie | wybór osoby z listy + **PIN 4-cyfrowy**; role: handlowiec / koordynator (admin) |
| Offline | **na start tylko online** (telefon po LTE). Szkic formularza zapisywany lokalnie w przeglądarce i odtwarzany po powrocie. Pełna kolejka offline — etap po wtorku |
| Dane startowe produkcji | **import z aktualnego pliku `PH Nowy … .xlsx`** — potrzebna świeża wersja od klienta |
| Aplikacja mobilna | **PWA** (jedna aplikacja: Android + iPhone + komputer), nie natywna — uzasadnienie niżej |

## Decyzje z odpowiedzi Kasi — 08.08 wieczór

Odpowiedzi na pytania z sekcji E. Zmieniają zakres etapu 3b i dokładają poprawki.

| Temat | Decyzja | Skutek dla planu |
|---|---|---|
| Świeży plik danych | **jest**: `PH PRÓBA Nowy dla handlowców.xlsx` (08.08, 21:15) | blokada etapu 5 zdjęta |
| Kto przypisuje szkoły | **wyłącznie koordynator handlowców (Kasia)** — handlowiec NIE przypisuje sam | ścieżka „chcę wziąć tę szkołę" **wypada z 3b**; zostaje komunikat „skontaktuj się z koordynatorem" |
| Auto-zwrot po terminie | automatyczny, bez ręcznego odpinania; zwrócona szkoła ma się **„świecić, że wróciła"** | automat już jest (`zwrot.py`); dochodzi plakietka „wróciła DATA" |
| **Karencja zwrotu — DECYZJA Przemka 08.08 (późny wieczór)** | zwrot **tak, jak chciała Kasia: od razu po terminie, BEZ karencji po**. Dwa dni zostają, ale jako **ostrzeżenie PRZED terminem**, nie karencja po nim | do zrobienia (etap 3c): `KARENCJA_DNI` 2→**0**, `OSTRZEZENIE_DNI` 3→**2**, poprawka `docker-compose.yml` i testów, które zakładają karencję 2 |
| Limit zajęć trenera | **4–5 dziennie to norma** (rano przedszkole 2–3 grupy, potem DT albo szkoła) | sprawdzić, że nic nie zakłada max 2; kolizje dalej tylko ostrzegają |
| Co widzi trener | kalendarz DT + cykliczne **tylko do odczytu**, własna dostępność do edycji, **reszty ma nie widzieć** | zgodne z obecnym stanem — potwierdzić testem |
| Co widzi handlowiec (PH) | każdy widzi każdego, edytuje swoje | zgodne z obecnym stanem |
| Konta na start | koordynatorki: **Kasia + Weronika Małolepsza**; admini: **Julia Młynarczyk + Przemek** — admin ma uprawnienia koordynatora | zostają 3 role; „admin" = konto z rolą koordynator, osobnej roli nie budujemy |
| Dane trenerów | Kasia uzupełnia arkusz trenerów (biuro + rekruterka dopiszą); importować **tylko mail i telefon** (bez adresu i notatek prywatnych) | uwaga przy imporcie |
| RSPO / baza szkół | Wojtek chce **całą aktualną bazę szkół**; rejony: Rybnik, Żory, Knurów, Orzesze, pow. mikołowski, Tychy, Katowice, Jaworzno, Sosnowiec, Dąbrowa Górnicza, Będzin z powiatem, Świętochłowice, Ruda Śląska, Zabrze, Siemianowice, Chorzów, pow. pszczyński, Piekary Śląskie | **etap po wtorku** — projekt niżej (sekcja F) |

---

# A. Git i bazy danych

## A1. Dlaczego bazy nie mogą być gałęziami

Pytanie brzmiało: „chcę wersję z bazą testową, pustą i produkcyjną, ale żeby się nie różniły".
To zdanie samo w sobie zawiera odpowiedź — **skoro mają się nie różnić, to nie mogą być osobnymi wersjami kodu.**

Gałąź per baza wyglądałaby tak:

- każda poprawka kodu × 3 merge'e, w kółko, do końca życia projektu,
- plik `.db` to binarium — git nie umie go scalić, każdy merge to konflikt bez rozwiązania,
- prędzej czy później produkcja dostaje poprawkę, której test nie ma (albo odwrotnie) i masz dokładnie ten problem, przed którym uciekasz.

Baza to **konfiguracja uruchomienia**, nie wersja kodu. `data/` jest już w `.gitignore` — czyli intuicja była dobra od początku, wystarczy ją dokończyć.

## A2. Jak to robimy — profile baz

`db.py` już czyta katalog bazy ze zmiennej `DATA_DIR`. Dokładamy nad tym `PROFIL`:

```
data/
  test/   leady_v3.db    ← kopia realnych danych, do prób i szkoleń
  pusta/  leady_v3.db    ← same słowniki, zero leadów — do przejrzystego dodawania od zera
  prod/   leady_v3.db    ← produkcja (na VPS w wolumenie dockera)
```

Uruchomienie tego samego kodu na innej bazie:

```powershell
$env:PROFIL="test";  python app.py       # http://127.0.0.1:5000
$env:PROFIL="pusta"; python app.py
```

Narzędzie do zarządzania profilami (`narzedzia/baza.py`):

```powershell
python narzedzia/baza.py lista                        # jakie profile, ile leadów, data ostatniej kopii
python narzedzia/baza.py nowa --profil pusta          # pusta baza + słowniki
python narzedzia/baza.py nowa --profil test --z-pliku "PH Nowy.xlsx"
python narzedzia/baza.py kopiuj --z prod --do test    # zrzut produkcji do testów
python narzedzia/baza.py backup --profil prod         # kopia .db + .xlsx ze stemplem czasu
python narzedzia/baza.py przywroc --profil prod --z kopie/2026-08-11_0600.db
```

**Pasek profilu w interfejsie.** U góry ekranu kolorowy pasek z nazwą bazy:
`PRODUKCJA` (czerwony) / `TEST` (pomarańczowy) / `PUSTA` (szary). Produkcja bez paska —
żeby nie straszyć handlowców — ale test i pusta **zawsze** z paskiem.
To nie kosmetyka: chroni przed zaimportowaniem czegoś w trybie `replace` do złej bazy.

## A3. Gałęzie — do czego naprawdę służą

```
main ────●────────────●───────────●──────────●────►  zawsze działa, to leci na VPS
      33d9874         │           │          │
                      │           │          │
  feat/profile-role ──┘           │          │       PIN, role, „moje dane"
  feat/formularz-terenowy ────────┘          │       nowy formularz + PWA
  feat/przydzial-terminowy ──────────────────┘       auto-zwrot szkół po terminie
```

Zasady, które utrzymają porządek:

1. **`main` zawsze działa.** Nic nie commitujesz bezpośrednio na `main` — tylko merge z gałęzi funkcji.
2. **Jedna gałąź = jedna funkcja.** Krótko żyje (1–2 dni), potem merge i kasujesz. Im krócej żyje, tym mniej konfliktów.
3. **Tagi na punktach kontrolnych** — do nich zawsze wrócisz:
   ```
   v4.0-spotkanie   ← 33d9874, wersja pokazana klientowi
   v5.0-wtorek      ← to, co wdrażamy 11.08
   ```
4. Merge z `--no-ff`, żeby w historii było widać, co przyszło z jakiej funkcji.

Komendy startowe:

```bash
git tag -a v4.0-spotkanie 33d9874 -m "Wersja zaprezentowana 06.08"
git push origin v4.0-spotkanie

git switch -c feat/profile-role
# … praca, commity …
git switch main
git merge --no-ff feat/profile-role
git branch -d feat/profile-role
git push
```

**Odpowiedź na „czy można je później połączyć?"** — tak, `git merge` dokładnie temu służy i przy krótkich gałęziach funkcji to bezbolesne. Konflikt pojawia się tylko wtedy, gdy dwie gałęzie zmieniły ten sam fragment tego samego pliku — wtedy git pyta, którą wersję zostawić. Dlatego gałęzie mają żyć krótko.

## A4. Kopie zapasowe (uwaga nr 2 i 3 z Twojej listy)

Na VPS, cron codziennie o 6:00:

```
kopie/
  2026-08-11_0600.db        pełna baza SQLite (odtworzenie 1:1)
  2026-08-11_0600.xlsx      eksport do excela (czytelny dla człowieka, do wglądu klienta)
```

- retencja: 30 dni dziennych + 1 kopia z każdego poniedziałku przez rok,
- **przed każdym importem** aplikacja robi kopię automatycznie (to zamyka dziurę „import w trybie replace kasuje bazę" z `DEPLOY.md`),
- odtworzenie jedną komendą: `python narzedzia/baza.py przywroc`,
- kopie ściągane raz w tygodniu z VPS na Twój dysk — serwer może paść w całości.

Eksport do excela masz już w [exporter.py](../exporter.py) — cron będzie go wywoływał tym samym kodem, więc nie ma drugiej ścieżki do utrzymania.

---

# B. Plan na wtorek — co, kiedy, ile

Kolejność jest celowa: najpierw to, bez czego handlowiec nie ruszy.

| # | Etap | Kiedy | Stan |
|---|---|---|---|
| 0 | Git + profile baz + pasek profilu | pt 07.08 | **✅** |
| 2 | Formularz terenowy — dwa warianty + ekran wyboru | pt 07.08 | **✅** |
| 3a | Auto-zwrot szkół po terminie | pt 07.08 | **✅** |
| — | Nowe repo `leady_app_v5` na GitHubie | pt 07.08 | **✅** |
| 1 | PIN, role, filtr „moje szkoły", CSRF | pt 07.08 | **✅** |
| — | Karta dostępu w PDF + `narzedzia/konto.py` | pt 07.08 | **✅** |
| — | Tryb serwisowy (jeden PIN, bez wyboru osoby) | pt 07.08 | **✅** |
| 6 | **Konta ↔ Słowniki** — dodawanie pracowników działa z obu miejsc | sob 08.08 | **✅** |
| 3b | **„Przedłuż termin"** masowo (licznik dni, domyślnie 14, ±/wpisanie) + termin przy przypisaniu z góry dziś+14 | sob 08.08 | **✅** |
| 7 | Plakietka „wróciła do puli" na `/baza` + skok do daty w kalendarzu | sob 08.08 | **✅** |
| 3c | **Zwrot bez karencji po terminie** (decyzja 08.08): `KARENCJA_DNI=0`, ostrzeżenie **2 dni PRZED terminem** (`OSTRZEZENIE_DNI=2`); testy Z1–Z5 dostosowane | nd 09.08 rano | **✅** |
| 8 | **Weryfikacja ścieżek**: testy ✅ (585/585) · **zostaje ręczny test z telefonu**: trener ustawia dostępność, handlowiec formularz→kalendarz | nd 09.08 | ⬜ |
| 11 | **Instrukcja podpięcia domeny** — krok po kroku, do zrobienia PRZED wdrożeniem | pon 10.08 rano, ~0,5h | ⬜ **pierwsze** |
| 2b | PWA — ikona na ekranie telefonu | pon 10.08 (po HTTPS) | ⬜ |
| 4 | VPS: **demo** (subdomena, profile pusta/test) → potem prod; HTTPS, cron kopii, `SECRET_KEY` | pon 10.08, ~4h | ⬜ |
| 9 | Próba backup → przywracanie na profilu test; na VPS cron 6:00 (`.db` + `.xlsx`) | pon 10.08, ~1h | ⬜ |
| 5 | Import `PH PRÓBA Nowy dla handlowców.xlsx` do prod + przejście na sucho po LTE | pon wieczór, ~2h | ⬜ |
| 10 | Szybkie wdrażanie wersji: git push → skrypt na VPS (`git pull` + `docker compose up -d --build`) | pon, przy okazji etapu 4 | ⬜ |

### Zrobione dodatkowo w niedzielę 09.08 (poza planem, z testów na telefonie)

| Rzecz | Skąd |
|---|---|
| **3c** — zwrot bez karencji, ostrzeżenie 2 dni PRZED terminem | decyzja Przemka 08.08 |
| ⚠️ **import brał 165 placówek zamiast 545** — zakładka bazy zmieniła nazwę | próba importu świeżego pliku |
| Nowe statusy klienta („04. Brak zgody na DT", „04. Odpuścić"), alias „Julia" | ten sam import |
| **`narzedzia/rspo.py`** — wykaz z CSV rejestru + raport dopasowania nazw | prośba o RSPO, `docs/12` |
| **Formularz v3** — status wybranego trenera, wszystkie kategorie, wolne okna, „co się dzieje tego dnia" | test z telefonu |
| ⚠️ **rok „0002" w polu daty** zabierał kalendarz bez drogi powrotnej | test z telefonu |
| **Dostępność: tryb zaznaczania dni** + gotowe godziny + trener widzi tylko siebie | „wypełnianie jest nieintuicyjne" |
| **„Plan na dziś"** w v1/v2/v3 — szkoły od koordynatora z terminami, gwiazdka cudzej szkoły z ostrzeżeniem | `docs/14` |
| **Zapamiętany miesiąc** kalendarz ↔ dostępność | test z telefonu |

### Świadomie odłożone (nie porzucone)

| Rzecz | Kiedy | Dlaczego teraz nie |
|---|---|---|
| Kilka zakresów godzin dziennie (8–12 + 16–18) | **wstrzymane** — tylko jeśli poproszą 11.08 | zmiana schematu (`UNIQUE(trener, data)`), 3–4 h z ryzykiem |
| Ostrzeżenie o przerwie na dojazd (<30 min) | po wtorku, ~45 min | poniedziałek zajmuje wdrożenie |
| Usterki z `docs/14` (pasek koordynatora u handlowca, limit 60 w wyszukiwarce, `/api/pin` bez właściciela) | po wtorku | żadna nie blokuje pracy |

**Stan na sobotę 08.08 późny wieczór.** Rdzeń v5 zamknięty, poprawki 6, 3b i 7
zrobione tego samego wieczora. Testy: **585 sprawdzeń w 9 plikach**, komplet OK.
Na niedzielę/poniedziałek zostają: serwer, dane, backup, telefon.

### Etap 3b — jak ostatecznie wygląda (doprecyzowanie z 08.08)

Zamiast sztywnego „+2 tygodnie": w pasku masowych akcji jest **licznik dni**
(domyślnie 14, przyciski −/+, można wpisać własną liczbę) i przycisk
**„Przedłuż termin"** działający na wszystkie zaznaczone leady. Nowy termin =
obecny termin + N dni; dla leadów już po terminie liczymy **od dziś** — inaczej
przedłużenie szkoły przeterminowanej od miesiąca dawałoby datę nadal w przeszłości
i automat zabrałby ją mimo przedłużenia. Każde przedłużenie zostawia ślad
w historii leada. Dodatkowo pole terminu przy zwykłym „Przypisz" jest z góry
wypełnione na **dziś + 14 dni** (edytowalne) — Kasia rozdaje szkoły „na 2 tygodnie".

| ~~„Chcę wziąć tę szkołę" dla handlowca~~ | **wypadło 08.08** — Kasia: „tylko koordynator ma prawo przypisu" |
|---|---|

### Etap 6 — Konta ↔ Słowniki (zgłoszone i **zrobione** 08.08)

Objaw: „nie można dodawać pracowników; trener dodany w Słownikach nie pojawia się
w Kontach". Przyczyna jest w kodzie, nie w danych:

- panel `/uzytkownicy` buduje listę „bez konta" **tylko ze słownika `handlowiec`**
  (`app.py`, `uzytkownicy_view`) — trenerzy nigdy się tam nie pokażą,
- `api_slownik_add` dodaje wartość do słownika i **nie tworzy konta** — konta
  hurtowo zakłada tylko `bootstrap_konta()` przy pierwszym starcie profilu.

Naprawa (dwustronna, żeby nie trzeba było pamiętać kolejności):

1. dodanie do słownika `handlowiec`/`trener` **automatycznie zakłada konto** z rolą
   wg rodzaju słownika, bez PIN-u (bez PIN-u nie da się zalogować — PIN nadaje
   koordynator, dokładnie jak przy bootstrapie),
2. lista „bez konta" w `/uzytkownicy` czyta **oba** słowniki,
3. test: dodaj trenera w słowniku → konto istnieje z rolą `trener` → nadaj PIN → loguje się.

### Filtr daty w kalendarzu (etap 7, **zrobione** 08.08)

Pole daty w pasku kalendarza: wybór daty przeskakuje na właściwy miesiąc,
podświetla tydzień z tą datą (obwódka + plakietka „tydzień z …") i przewija do
niego ekran. Działa we wszystkich trzech widokach (macierz / agenda / starty);
data w adresie wygrywa z wyborem miesiąca, a ręczna zmiana miesiąca czyści datę.
Osobny widok „tydzień" (7 dni od wybranej daty) — dopiero po wtorku, jeśli
handlowcy o niego poproszą po realnym użyciu.

### Co doszło poza planem (z uwag w trakcie)

| Rzecz | Skąd |
|---|---|
| **Dwa warianty formularza** (v1 kroki / v2 makieta) + ekran wyboru | „zaprezentuj im co mamy i sobie wybiorą" |
| **Pełny ekran** formularzy, wyjście tylko przez „Zakończ" | pasek aplikacji rozjeżdżał się na telefonie |
| **Obsługa awarii przy zapisie** — kolejka „niewysłane" + ponowienie bez dubla | pytanie „co w przypadku awarii w trakcie wypełniania" |
| Własny port 5301 zamiast 5000 | kolizja z innymi testowymi aplikacjami |
| Ochrona przed dublem (`klucz_zapisu`, tabela `zapisy_formularza`) | wynikło z obsługi awarii |
| **Karta dostępu w PDF** — PIN-y, tabela uprawnień, paski do rozcięcia | „utwórz plik pdf z informacjami o pinach i uprawnieniach" |
| **Token CSRF** na wszystkich zapisach | wyszło przy logowaniu — `fetch` szedł bez niczego |
| **`kto` w historii z sesji** zamiast stałego „demo" | dopiero logowanie dało czym to wypełnić |
| **Tryb serwisowy** — jeden PIN, bez wyboru osoby | „utwórz mi konto developera 7777… bez użytkownika, tylko hasło" |
| **`narzedzia/konto.py`** — konta z linii poleceń | wyjście awaryjne, gdy nie da się zalogować |
| **Odmowa startu przy zajętym porcie** | trzy instancje naraz na 5301 kosztowały pół godziny szukania błędu, którego nie było |

## Etap 1 — profile (sobota)

**Model:** rola `handlowiec` / `koordynator`. Logowanie: lista osób ze słownika `handlowiec` → PIN 4-cyfrowy → sesja na 30 dni (żeby nie logował się co rano w terenie).

**Kluczowa rzecz — „przyczepiony, ale zmienialny filtr".** Dokładnie jak napisałeś:

- handlowiec po wejściu widzi **tylko swoje leady** — filtr ustawiony i podświetlony,
- może go zdjąć i zobaczyć wszystko (nic nie ukrywamy — to zespół, nie konkurencja),
- ale po przejściu na inny ekran, odświeżeniu albo „Wyczyść" **filtr wraca do jego nazwiska**.

Mechanizm już istnieje w v4 — kłódka w [filtr_osob.js](../static/filtr_osob.js) przypina filtr na stałe. Tu dochodzi to, że handlowiec startuje z domyślnie przypiętym własnym nazwiskiem, a koordynator z pustym.

Co widzi kto:

| | handlowiec | koordynator |
|---|---|---|
| Formularz terenowy | ✅ | ✅ |
| Moje szkoły / leady | ✅ swoje domyślnie | ✅ wszystkie |
| Kalendarz, dostępność | ✅ podgląd | ✅ edycja |
| Baza do rozdania, przydzielanie | ❌ | ✅ |
| Słowniki, import, eksport | ❌ | ✅ |
| Zbiorczy (kolumny Julii) | ❌ | ✅ |

Zabezpieczenia przy okazji (są dziurą od v1, a teraz idzie to do internetu z danymi dyrektorów szkół): token CSRF na zapisach, hasła PIN hashowane, cała aplikacja za logowaniem.

## Etap 2 — formularz terenowy (sobota–niedziela) — **rdzeń zadania**

Wzór ze spotkania (`ChatGPT Image 6 sie 2026, 16_33_49.png`) ma dobre sekcje, ale jest zaprojektowany pod monitor: dwie kolumny, cztery pola w rzędzie, wszystko naraz. Na telefonie w szkolnym korytarzu to nie zadziała. Zostawiamy **jego strukturę i kolejność**, zmieniamy sposób podania.

**Adres: `/formularz`** — osobny, uproszczony ekran. Nie dotykamy istniejących ekranów, żeby nie zepsuć tego, co się spodobało.

### Jak to ma działać

**Jedna kolumna, duże pola.** Minimum 48 px wysokości pola i przycisku (palec, nie mysz). Font 16 px — poniżej tego iPhone sam przybliża ekran przy kliknięciu w pole i handlowiec walczy z widokiem zamiast wpisywać.

**Cztery kroki zamiast jednej długiej ściany:**

```
[1 Placówka] → [2 Dzień Technologii] → [3 Zajęcia cykliczne] → [4 Podsumowanie]
     ●━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━○━━━━━━━━━━━━━━━━━━━━○
```
Pasek postępu na górze. Wstecz/dalej. Krok 3 do pominięcia jednym przyciskiem („Bez zajęć cyklicznych") — nie każde spotkanie je ustala.

**Krok 1 — placówka: wyszukiwarka, nie dwa selecty.**
Wzór ma „Miejscowość" → „Placówka". Przy kilkuset szkołach to przewijanie listy kciukiem. Zamiast tego jedno pole „szukaj": wpisujesz `zabrz` albo `sp 12` i dostajesz podpowiedzi z bazy. **Na górze listy zawsze „moje szkoły"** (przydzielone przez koordynatora) — w praktyce handlowiec trafi w swoją szkołę po 2–3 znakach.
Jeśli szkoły nie ma — „Dodaj nową placówkę", pola rozwijają się w miejscu.

**Krok 2 — DT: podpowiedź trenera.**
Po wybraniu daty aplikacja pokazuje, **kto jest wolny tego dnia i jeździ po tym mieście** — logika jest już napisana w [przydzial.py](../przydzial.py) (dostępność + kolizje + rejon + obciążenie), tu tylko wystawiamy ją w formularzu:

```
Prowadzący DT
┌────────────────────────────────────────────┐
│ ✅ 05. Nowak      wolny 8–14 · rejon Zabrze │
│ ✅ 12. Kowalska   wolny 8–12 · rejon Zabrze │
│ ⚠️ 07. Wiśniewski  ma DT 9–12 (Gliwice)     │
│ ○  inny trener…                             │
└────────────────────────────────────────────┘
```
Handlowiec przy dyrektorze widzi od razu, czy może ten termin obiecać. **To jest największa realna wartość formularza** i to trzeba potwierdzić u klienta, że o to im chodziło (pkt 3 poniżej).

**Krok 3 — zajęcia cykliczne:** cykl, dzień tygodnia, godzina, sala. Tu bez zmian względem wzoru.

**Krok 4 — podsumowanie:** wszystko na jednym ekranie do przeczytania na głos dyrektorowi, przycisk „Zapisz" i „Popraw".

### Ochrona przed błędami (to był ich wyraźny problem — „handlowiec czegoś nie wpisał")

- pola wymagane blokują przejście dalej, z konkretnym komunikatem przy polu, nie ogólnym „wypełnij formularz",
- **szkic zapisywany lokalnie w telefonie po każdej zmianie pola** — wyjście z przeglądarki, telefon do ucha, utrata zasięgu: po powrocie formularz jest wypełniony tam, gdzie skończył. To spełnia „zapisywało szkic lokalnie",
- po wysłaniu wyraźne potwierdzenie z nazwą szkoły i datą DT — bez tego handlowiec nie wie, czy poszło,
- data DT w przeszłości albo trener zajęty → ostrzeżenie, ale **nie blokada** (czasem tak jest naprawdę),
- godziny jako osobne pola, nie tekst — dzięki temu wykrywanie kolizji działa.

### Dlaczego PWA, a nie aplikacja natywna

Chcą Android + iPhone + komputer. Są trzy drogi:

| | Nakład | iPhone | Aktualizacja | Werdykt |
|---|---|---|---|---|
| **PWA** (ta sama aplikacja z ikoną na pulpicie) | ~4h ponad formularz | działa | natychmiastowa, bez sklepu | **to bierzemy** |
| React Native / Flutter | 3–4 tygodnie + osobny kod | działa | przez App Store, 1–7 dni na zatwierdzenie | nierealne na wtorek |
| Tylko strona w przeglądarce | 0 | działa | natychmiastowa | brak ikony, brak trybu pełnoekranowego |

PWA to ta sama aplikacja, ale z pliku `manifest.json` i ikony: handlowiec wchodzi raz na adres, robi „Dodaj do ekranu początkowego" i ma ikonę jak zwykła aplikacja, uruchamia się na pełnym ekranie bez paska adresu. Jeden kod, zero sklepów, aktualizacja przez `git push`.
Ograniczenie iPhone'a warte świadomości: powiadomienia push są tam ubogie, a system może skasować dane offline po ~7 dniach nieużywania — dlatego pełne offline projektujemy jako „kolejka do wysłania", nie jako „druga baza w telefonie".

## Etap 3 — przydział szkół na 2 tygodnie (niedziela–poniedziałek)

Sprawdziłem w kodzie, jak jest dzisiaj. Odpowiedź na pkt 3 ze spotkania:

| Czego chcieli | Stan w v4 | Do zrobienia |
|---|---|---|
| Koordynator przydziela 10 szkół z terminem 2 tygodnie | **✅ jest** — `/baza`, zaznacz wiele, wybierz handlowca i termin, „Przypisz" ([app.py:349](../app.py#L349)) | dodać przycisk „termin: +2 tygodnie" |
| Handlowiec widzi swoje szkoły | częściowo — filtr jest, ale bez logowania każdy widzi wszystko | ekran **„Moje szkoły"** + podpowiedzi w formularzu (etap 1–2) |
| Dodatkowe szkoły przydziela koordynator | **❌ nie ma** ograniczenia — każdy może wszystko | ścieżka „poproś koordynatora" |
| Samodzielne przypisanie — możliwe, ale trudniejsze | **❌ nie ma** rozróżnienia | osobny przycisk z komunikatem i powodem |
| **Po terminie szkoły wracają automatycznie do puli** | **❌ NIE MA — trzeba zbudować** | poniżej |

**Auto-zwrot — jak zrobimy.** Dziś jest tylko filtr „po terminie" na pulpicie i ręczne „odbierz handlowcowi" ([repo.py:199](../repo.py#L199)). Automatu nie ma.

Reguła: raz na godzinę aplikacja przegląda leady i zwraca do puli te, które **równocześnie**:
- mają termin ostateczny wcześniejszy niż dziś,
- nie mają statusu sukcesu (`03.`) ani odpadnięcia (`04.`),
- nie mają umówionego DT.

Zwrot = handlowiec wyczyszczony, status „niewykorzystane", **wpis do historii** (kto miał, do kiedy, kiedy wrócił). Nic się nie kasuje.

Dwie rzeczy, które trzeba dopowiedzieć, bo inaczej to zaboli ludzi:
- **karencja i ostrzeżenie** — handlowiec dostaje sygnał „ta szkoła wraca do puli za 2 dni", a nie budzi się z pustą listą. Wartość do ustawienia, proponuję 2 dni.
- **zwrot nie kasuje pracy** — notatki, kontakty i ustalenia zostają przy placówce. Wraca tylko przypisanie.

To wymaga potwierdzenia u klienta — pytania na końcu dokumentu.

## Etap 11 — instrukcja podpięcia domeny (PRZED wdrożeniem)

Przemek: *„dawno nie podpinałem i nie pamiętam, trzeba coś stworzyć wcześniej"*.
DNS propaguje się do kilku godzin, a `certbot` **nie wystawi certyfikatu, dopóki
domena nie wskazuje na serwer** — więc to musi być zrobione jako pierwsze
w poniedziałek, inaczej HTTPS (a z nim PWA) czeka bezczynnie.

Instrukcja do napisania w `docs/15_DOMENA_I_WDROZENIE.md`, z konkretami:

1. **Co gdzie kliknąć u operatora domeny** — rekord `A` subdomeny
   (np. `leady.silesia3d.site`) na adres IP VPS-a; jeśli serwer ma IPv6,
   dodatkowo rekord `AAAA`. Bez CNAME — przy subdomenie na własny VPS to
   niepotrzebna warstwa.
2. **Jak sprawdzić, czy już działa**, zanim ruszy się cokolwiek dalej:
   `nslookup leady.silesia3d.site` i porównanie z IP serwera.
3. **Dwie subdomeny od razu**: `demo.…` (profile `pusta`/`test`) i docelowa
   produkcyjna. Obie wskazują na ten sam VPS, różnią się konfiguracją nginx
   i zmienną `PROFIL`.
4. **nginx**: blok `server` per subdomena, `proxy_pass` na port kontenera,
   nagłówki `X-Forwarded-*` (bez nich Flask nie wie, że jest za HTTPS).
5. **certbot**: `--nginx -d demo.… -d …`, automatyczne odnawianie i sprawdzenie,
   że timer działa (`systemctl list-timers | grep certbot`).
6. **Zmienna `HTTPS`** w kontenerze — dopiero ona włącza `Secure` na ciastku sesji.
7. **Kolejność bez pomyłki**: DNS → sprawdzenie → nginx bez SSL → certbot →
   dopiero teraz `HTTPS=1` i restart.

Punkt wyjścia: działający wzór `librus.silesia3d.site` na tym samym serwerze —
wystarczy odtworzyć jego układ, nie wymyślać od nowa.

## Etap 4 — wdrożenie (poniedziałek)

Masz już działający wzór: `librus.silesia3d.site`. Ta sama ścieżka, port 5058.

1. kontener `docker compose up -d --build` (plik gotowy w repo),
2. nginx jako subdomena + `certbot` → HTTPS (bez tego PWA nie zainstaluje się na telefonie — to warunek, nie ozdoba),
3. `PROFIL=prod`, WAL włączony w SQLite (przy kilku handlowcach naraz bez tego wyskakuje `database is locked`),
4. cron 6:00 → kopia `.db` + `.xlsx`,
5. test z prawdziwego telefonu po LTE, nie z komputera w biurze.

## Etap 5 — dane i próba na sucho (poniedziałek wieczór)

Import `PH Nowy … .xlsx` do profilu `prod`, potem **przejście całej ścieżki jako handlowiec, z telefonu**: zaloguj się PIN-em → zobacz swoje szkoły → wypełnij formularz dla jednej → sprawdź, czy wpis pojawił się u koordynatora i w kalendarzu.

Do tego jedna kartka A5 dla handlowca: adres, jak dodać ikonę do ekranu, PIN, cztery kroki formularza, numer do Ciebie.

---

# C. Poza wtorek

| Etap | Kiedy | Co |
|---|---|---|
| 11 | śr–czw 12–13.08 | pełne offline: kolejka wysyłkowa, synchronizacja po odzyskaniu zasięgu, oznaczenie „czeka na wysłanie" |
| 12 | tydzień 18.08 | poprawki z pierwszego tygodnia realnego użycia — **to najcenniejszy materiał, jaki dostaniesz** |
| 13 | tydzień 18.08 | **baza szkół z RSPO** — projekt w sekcji F |
| 14 | wrzesień | rozliczenia (30/30/5), powiadomienia mailowe, Google Calendar |

---

# D. Ryzyka

| Ryzyko | Waga | Co robimy |
|---|---|---|
| Nie dostaniesz świeżego `PH Nowy.xlsx` na czas | wysoka | poprosić o plik **dziś**; awaryjnie start z profilu `pusta` + import w środę |
| Formularz nie pokryje realnej rozmowy w szkole | wysoka | krok 4 to podsumowanie do przeczytania dyrektorowi — pokazać klientowi w niedzielę, przed wdrożeniem |
| SQLite przy kilku osobach naraz | średnia | WAL + 1 worker gunicorna; przy 5 handlowcach to spokojnie wystarcza |
| Auto-zwrot zabierze szkołę, nad którą ktoś pracuje | średnia | karencja 2 dni + ostrzeżenie + zwrot tylko bez umówionego DT |
| Handlowiec zapomni PIN-u w terenie | niska | koordynator resetuje PIN z panelu w 10 sekund |
| Termin wtorkowy | wysoka | etapy 1–3 są niezależne — jeśli coś nie zdąży, wdrażamy resztę i dokładamy w środę |

---

# E. Pytania do klienta — stan po odpowiedziach z 08.08

1. ~~Plik `PH Nowy … .xlsx`~~ — **jest** (`PH PRÓBA Nowy dla handlowców.xlsx`, 08.08).
2. ~~Auto-zwrot~~ — **automatyczny**, zwrócona szkoła ma się świecić. Karencja
   zostaje na naszych 2 dniach (`KARENCJA_DNI`), Kasia nie podała innej wartości.
3. ~~Samodzielne przypisanie~~ — **NIE**. Tylko koordynator handlowców (Kasia).
4. **Podpowiedź trenera w formularzu** — czy handlowiec może obiecać termin
   dyrektorowi, czy wiążąco potwierdza koordynator? **⬜ nadal bez odpowiedzi.**
5. ~~Konta~~ — koordynatorki: Kasia, Weronika Małolepsza; admini (te same
   uprawnienia): Julia Młynarczyk, Przemek. Handlowcy i trenerzy ze słowników.
6. **Formularz — czy czegoś brakuje?** — **⬜ nadal bez odpowiedzi** (osoba
   kontaktowa, zgoda na salę, sprzęt).
7. **Osoba będąca i handlowcem, i trenerem** ma dziś dwa konta (różne prefiksy
   w słownikach) — jedno konto czy dwa? **⬜ nadal bez odpowiedzi.**
8. ~~Karencja auto-zwrotu~~ — **rozstrzygnięte 08.08 (Przemek)**: zwrot od razu
   po terminie (bez karencji po), 2 dni jako **ostrzeżenie przed terminem**.
   Zostaje pod-pytanie na wtorek: czy „ruch" handlowca (notatka, zmiana statusu)
   ma chronić przed zwrotem, czy — jak teraz — chroni wyłącznie umówione DT,
   a życie leada przedłuża koordynator przyciskiem „Przedłuż termin"? **⬜**
9. **Minimum tygodniowe na pulpicie** — pojęcie z notatek ze spotkania 24.07
   („STATUS — minimum na tydzień", k.1 p.4); wartość **5 DT/tydzień to nasze
   założenie robocze** (`CEL_TYGODNIOWY`), pytanie A4 z `07_PYTANIA` wciąż bez
   odpowiedzi. Jaka ma być realna liczba? **⬜ na wtorek.**

---

# F. Baza szkół z RSPO — propozycja

**Pełna propozycja (do pokazania Wojtkowi): `docs/12_RSPO.md`.** Skrót i fakty
zweryfikowane 08.08:

- fundament **już jest w kodzie**: kolumna `rspo` z unikalnym indeksem,
  `importuj_rspo()` (import z pliku przez ekran Import), dopasowanie placówek
  po numerze RSPO → zmiana nazwy w rejestrze nie tworzy duplikatu,
- oficjalne API `api.rspo.gov.pl` **wymaga wniosku** (e-mail na `rspo@cie.gov.pl`,
  rozpatrzenie do 14 dni) — wniosek wysłać w poniedziałek, zegar tyka,
- otwarte dane na dane.gov.pl są z lat 2013–2017 — odpadają,
- plan dwuetapowy: **A** (od wtorku, zero kodu) — wykazy rejonów Kasi
  z wyszukiwarki rspo.gov.pl wgrywane istniejącym importem; **B** (po dostępie
  do API, ~1 dzień pracy) — `narzedzia/rspo.py`, przycisk „Odśwież z RSPO"
  z raportem nowych/zmienionych/zniknięć, flaga „objęta działaniem".
