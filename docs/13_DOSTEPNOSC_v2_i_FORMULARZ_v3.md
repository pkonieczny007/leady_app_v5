# Dostępność „zaznacz dni" + formularz v3 — propozycja

Z uwag z testów na telefonie, 09.08.2026 (Przemek):
- *„moja dostępność jest nieintuicyjna"* (rola trener),
- *„w formularzu v2 brak sprawdzenia, czy trener jest dostępny i czy nie ma kolizji"*,
- *„przydałaby się lista osób w danym dniu"*,
- *„zróbmy formularz v3 — v2, ale ulepszony"*.

---

# A. Dostępność — dlaczego dziś jest nieintuicyjna

Stan faktyczny (sprawdzony w kodzie):

| Co | Jak jest teraz |
|---|---|
| Ustawienie **jednego** dnia | klik w komórkę → edytor wsuwa się do środka komórki → wpisujesz godziny w dwa pola `time` → „Zapisz" → **przeładowanie całej strony** |
| Ustawienie **wielu** dni | osobny formularz „Wypełnij zakres" **nad siatką**, oderwany od kalendarza: wybierz trenera z listy, datę od, datę do, odhacz dni tygodnia, wybierz tryb |
| Zaznaczanie wielu komórek | **nie istnieje** — ani przeciągnięciem, ani z Shiftem, ani checkboxem |
| Po każdym zapisie | `location.reload()` — przy wypełnianiu miesiąca to 20+ przeładowań |

Trzy realne bolączki, wszystkie potwierdzone w kodzie:

1. **Praca jest „per komórka”, a myślenie trenera jest „per kilka dni”.** Trener wie:
   „w tym tygodniu jestem rano, w przyszłym mnie nie ma”. Musi to rozbić na 5–10
   osobnych edycji.
2. **Formularz zakresu nie zna roli** — lista trenerów pokazuje wszystkich, także
   gdy zalogowany trener może zmieniać wyłącznie siebie. Wybór kolegi kończy się
   odmową serwera. Do tego domyślne „do” to sztywne `28` dnia miesiąca, a wpisów
   istniejących ten formularz **nie nadpisuje** (`INSERT OR IGNORE`).
3. **Wpisywanie godzin z klawiatury na telefonie.** Nie ma żadnych gotowych
   wariantów typu „8–12”, „cały dzień”, choć w praktyce powtarza się ich kilka.

## Trzy drogi (do wyboru)

### Wariant A — zaznaczanie kliknięciem + pasek akcji  ⭐ rekomendacja

Dokładnie ten wzorzec, który w aplikacji **już działa** na `/baza` (checkboxy →
pasek masowy → jedno żądanie). Trener zna go z listy szkół, my mamy gotowy kod.

```
 [tryb: ✎ zaznaczanie ]        ← przełącznik nad siatką

 Trener \ dzień   pn 1   wt 2   śr 3   cz 4   pt 5
 04. Zemela      [ ✓ ]  [ ✓ ]  [   ]  [ ✓ ]  [   ]     ← tap = zaznacz/odznacz
                  ▔▔▔▔   ▔▔▔▔          ▔▔▔▔

 ┌─ 3 dni zaznaczone ────────────────────────────────────┐
 │ [cały dzień]  [8–12] [8–16] [12–16]  [własne: __:__ – __:__]
 │ [niedostępny]  [wyczyść]        [odznacz wszystko]     │
 └────────────────────────────────────────────────────────┘
```

- **tap w komórkę** zaznacza (nie otwiera edytora — edytor zostaje pod
  długim naciśnięciem albo drugim tapnięciem w już zaznaczoną komórkę),
- **gotowe warianty godzin** zamiast wpisywania: cztery przyciski pokrywają
  to, co realnie występuje w ich grafiku, plus „własne” dla wyjątków,
- **jedno żądanie** na całą paczkę i **jedno** przeładowanie,
- działa palcem na telefonie tak samo jak myszą.

Koszt: ~2–3 h. Backend prawie gotowy — `api_dostepnosc_zakres` przyjmuje już
paczkę, trzeba dołożyć wariant „lista konkretnych dat” i nadpisywanie
istniejących wpisów (dziś świadomie ich nie rusza).

### Wariant B — zaznaczanie przeciągnięciem po siatce

Jak zaznaczanie komórek w Excelu. Wygodne myszą, **kłopotliwe palcem** (przeciąganie
po ekranie telefonu koliduje z przewijaniem strony) — a dostępność ustawia się
głównie z telefonu. Realnie i tak trzeba by dołożyć wariant A jako zapasowy.
Koszt: ~4 h. **Odradzam jako jedyne rozwiązanie.**

### Wariant C — gotowe wzorce tygodnia

„Ustaw mi poniedziałki i środy 8–16 na cały miesiąc”, „wolne w przyszłym
tygodniu”. To ulepszenie istniejącego formularza zakresu, nie kalendarza.
Rozwiązuje przypadek regularny, nie rozwiązuje „w środę wyjątkowo do 12”.
Koszt: ~1,5 h. **Dobre jako dodatek do A, złe jako zamiennik.**

**Rekomendacja: A teraz, C po wtorku.** A daje sposób pracy zgodny z tym, jak
trener myśli, i używa wzorca, który w aplikacji już jest.

---

# B. Formularz v3 — co dokładnie ulepszamy

Kluczowa rzecz: **backend już wszystko liczy**. `GET /api/kandydaci` zwraca dla
każdego trenera kategorię (wolny / nieznany / zastrzeżenie / niedostępny), powód,
**wolne okna**, **listę jego zajęć w tym dniu**, obciążenie miesięczne i flagę
rejonu. Wariant 2 zużywa z tego jakieś 30% i wyrzuca resztę.

| # | Problem w v2 (potwierdzony w kodzie) | Co robi v3 |
|---|---|---|
| 1 | `<select>` prowadzącego zawiera **pełny słownik**; wybór osoby niedostępnej albo mającej kolizję przechodzi **bez słowa** aż do ekranu sukcesu | po każdej zmianie trenera/daty/godzin **plakietka przy polu**: „✅ wolny 8–16” / „⚠️ ma DT 9–12 w Gliwicach” / „⛔ niedostępny (XXX)” |
| 2 | Lista kandydatów pokazuje tylko wolnych, twarde `slice(0,8)`, bez „pokaż resztę” | wszystkie cztery kategorie, zwinięte sekcje: „Wolni (3)”, „Bez deklaracji (12)”, „Z zastrzeżeniem (2)”, „Niedostępni (4)” |
| 3 | Odpowiedź API niesie `wolne` i `zajete` — **nikt tego nie pokazuje** | przy kandydacie widać jego wolne okna i to, co już ma tego dnia |
| 4 | **Brak godziny startu po cichu wyłącza** liczenie kolizji — nikt o tym nie mówi | dopóki nie ma godziny: „podaj godzinę, żeby sprawdzić kolizje” |
| 5 | Nie da się zobaczyć, **co się dzieje tego dnia w firmie** | rozwijane „Co się dzieje 15.09” — lista osób z godzinami i szkołami, budowana z tej samej odpowiedzi API (`zajete` każdego trenera), **bez nowego endpointu** |
| 6 | Komunikat „nikt nie zadeklarował” pokazuje się **razem z listą nazwisk** — przeczy temu, co widać | jeden spójny komunikat |
| 7 | Zapowiedź „kto jeździ po tej okolicy” — rejon **nie filtruje**, jest tylko dopiskiem | tekst zgodny z tym, co robi kod: rejon podbija kolejność, nie ukrywa nikogo |

**Czego v3 NIE zmienia — celowo:** zapisuje przez to samo `POST /api/formularz`,
tę samą walidację i ten sam `klucz_zapisu`. Trzy warianty mają się różnić
**sposobem podania**, nie funkcjami — inaczej klient wybierałby między
możliwościami, a nie między układem, i porównanie nic by nie znaczyło.
Ostrzeżenia **nie blokują zapisu** (zasada z CLAUDE.md: ostrzegamy, nie blokujemy).

## Skąd bierzemy „listę osób w danym dniu”

`/api/kandydaci?data=…` zwraca każdego trenera z jego `zajete` (godziny, typ,
szkoła, miasto). Wystarczy to przełożyć na listę „kto ma dziś co”, posortowaną
po godzinie. Zero nowego kodu po stronie serwera, zero dodatkowych zapytań —
odpowiedź i tak już przychodzi.
