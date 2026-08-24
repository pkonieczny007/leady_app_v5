# Wdrożenie na demo — 24.08.2026

Instrukcja do wykonania z palca na serwerze. **Ścieżka jest przećwiczona
lokalnie na kopii bazy produkcyjnej** (545 placówek → 1613, eventy 65 → 65),
więc liczby niżej to nie szacunki, tylko wynik próby.

Demo stoi dziś na `main` i **klient nie widzi ANI JEDNEJ zmiany z 20–24.08**.
To była najczęstsza przyczyna nieporozumień w tej rundzie: Kasia i Zuzia
zgłaszają rzeczy dawno naprawione, bo oglądają wersję sprzed poprawek.

Serwer: `ubuntu@57.128.241.52`, katalog `/home/ubuntu/apps/demo-ph.silesia3d.site`.
Wejście: VS Code Remote na hasło.

---

## 0. Czego potrzebujesz pod ręką

| co | gdzie | po co |
|---|---|---|
| plik rejestru RSPO | `C:\XEN\AI-szkolenie\SIERPIEN2026\24.08.2026\rspo_2026_08_13.csv` (41 MB) | lustro rejestru — bez niego nie ma powiatów ani dokładania |

**To jedyny plik, który trzeba przenieść.** Arkusz klienta z numerami RSPO
(`--plik` przy komendzie `dopasuj`) okazał się **niepotrzebny**: przy nowej
kolejności kroków dopasowanie po samym rejestrze trafia **520 z 545** numerów,
czyli tyle samo co z arkuszem. Jeden plik osobowy mniej na serwerze.

Przenieść można przeciągnięciem do panelu plików VS Code Remote — do katalogu
domowego `~`, nie do repozytorium (repo jest publiczne, a `git add .` już dwa
razy w tej rundzie zgarnął plik klienta).

---

## 1. Kod na demo

```bash
cd /home/ubuntu/apps/demo-ph.silesia3d.site
git fetch origin
git checkout poprawki-2026-08
git pull --ff-only
./wdroz.sh demo
```

`wdroz.sh` sam sprawdza, że aplikacja odpowiada na porcie 5302 — brak
odpowiedzi kończy się czerwonym komunikatem i kodem błędu, a nie ciszą.

**Sprawdź w przeglądarce**, zanim pójdziesz dalej: `https://demo-ph.silesia3d.site`
— logowanie działa, na `/formularz` jest **pięć** kafelków (piąty: „Formularz v5,
testowy: kaskada").

Gdyby coś poszło źle, powrót to jedno polecenie:
```bash
git checkout main && ./wdroz.sh demo
```

---

## 2. Baza demo na rejestr RSPO

```bash
cd /home/ubuntu/apps/demo-ph.silesia3d.site
./narzedzia/migracja_na_demo.sh ~/rspo_2026_08_13.csv
```

Skrypt pyta „Robimy to na DEMO?" i dopiero wtedy rusza. Robi po kolei: kopię
bazy (punkt cofnięcia), słowniki, lustro rejestru, obszary, powiaty, numery
RSPO, powiaty jeszcze raz, dołożenie placówek, zespoły. Na końcu wypisuje
liczby i polecenie cofające.

### Dlaczego migracja NA SERWERZE, a nie gotowym plikiem `.db`

Bazę produkcyjną w sierpniu zbudowaliśmy lokalnie i wysłaliśmy plikiem —
i to była dobra decyzja, bo importer potrafił zaskoczyć. Tu jest inaczej
z dwóch powodów:

1. **Produkcja żyje.** Handlowcy pracują na niej od 11.08, więc jej bazy nie da
   się podmienić plikiem — trzeba ją migrować w miejscu. Demo jest jedynym
   miejscem, gdzie tę operację można przećwiczyć, a przećwiczyć trzeba
   dokładnie ją, nie coś innego.
2. **Konta.** Lokalna baza `test` ma PIN-y tylko przy trzech kontach z 46.
   Wgranie jej plikiem odebrałoby wszystkim na demo możliwość zalogowania się.

### Liczby kontrolne — porównaj po migracji

Z próby na kopii produkcji:

```
placowki 1613   leady 1613   eventy 65   z rspo 1588
lustro rspo_rejestr 6117   obszary 17   rspo_obszar 2553

01. Szkoła podstawowa                573
02. Przedszkole miejskie (PM)        463
03. Przedszkole prywatne (PP)        264
04. Zespół szkolno-przedszkolny      278
05. Instytucja kultury                29
04. Inna                               6

bez powiatu 1 (to znane P28: „SP 5", id 532, bez miejscowości)
powiat mikołowski 88  ← tyle samo co w rejestrze, to była pierwotna reklamacja
Czeladź 18            ← miejscowość, której „nie było" (zgłoszenie Kasi)
```

**Najważniejsza z tych liczb to EVENTY: 65 przed i 65 po.** Migracja dokłada
placówki i nadaje im geografię — nie ma prawa ruszyć niczyjej pracy
w kalendarzu. Jeśli ta liczba się zmieni, cofnij i nie idź dalej.

Liczby na demo mogą różnić się o kilka sztuk od lokalnego profilu `test`
(1618), bo demo pochodzi z kopii produkcji z innego dnia. Różnica rzędu
kilkunastu rekordów jest normalna, kilkuset — nie jest.

---

## 3. Co obejrzeć na demo po migracji

Kolejność od najbardziej „to była reklamacja klienta":

1. **`/baza` → filtr Powiat.** Ma stać PRZED „Miejscowością", a miejscowość
   ma się zawężać wybranym powiatem. To jest odpowiedź na zgłoszenie Kasi
   („na liście są porozbijane miasta, a w RSPO jest to powiatami").
2. **Powiat będziński → Czeladź.** Placówki są. Wcześniej Czeladź siedziała
   w worku `15. Będzin powiat`, bo import urwał słowo „powiat".
3. **Powiat mikołowski, wszystkie typy** — 88, tyle co w rejestrze.
4. **`/formularz` → piąty kafelek (v5).** Kaskada powiat → miejscowość →
   placówka; zaznacz chip „DT" i chip „Cykliczne" naraz — przy każdej sekcji
   ma być wybór prowadzącego i panel dostępności.
5. **Formularz: nie ma już „dodaj nową placówkę"** (zgłoszenie Kasi z 24.08).
   W jego miejscu podpowiedź kierująca do filtra powiatu.
6. **`/obszary`** — podgląd zakresu firmy wg rejestru.

---

## 4. Czego NIE robić po migracji

**Nie uruchamiać `narzedzia/odswiez_demo.sh`.** Ten skrypt zasiewa demo świeżą
kopią PRODUKCJI, czyli skasowałby całą migrację i wrócił do 545 placówek bez
powiatów. Do czasu migracji produkcji demo i produkcja mają różne bazy i to
jest stan zamierzony, nie usterka.

---

## 5. Produkcja — dopiero po tygodniu obserwacji

Ta sama ścieżka, ale **świadomie osobną decyzją**: w `migracja_na_demo.sh`
nie ma przełącznika „prod", żeby nie dało się tego zrobić z pamięci, wklejając
polecenie z jedną zmienioną literą. Przed produkcją trzeba jeszcze:

- **M4 — scalanie par.** 18 par dubli w bloku id 517–545, w 16 z nich jedyne DT
  wisi na rekordzie SKRÓCONYM. Narzędzia jeszcze NIE MA; kolejność w nim jest
  krytyczna: eventy i log przepinamy PRZED skasowaniem rekordu, bo
  `ON DELETE CASCADE` zabiera DT bez śladu.
- **Plik `do_sprawdzenia_recznego/BEZ_RSPO_2026-08-24.xlsx` do Kasi** — 25
  placówek, dwie kolumny decyzji. Ich numery wchodzą przez
  `dopasuj --decyzje <plik> --zapisz`.
- Zgoda Pawła po obejrzeniu demo.
