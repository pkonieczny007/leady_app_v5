# Ścieżka „koordynator wybiera → handlowiec pracuje w terenie" — stan faktyczny

Analiza z 09.08.2026, na pytanie: *„w weekend koordynator wybiera 5 szkół
i nadaje deadline, handlowiec w terenie działa na tych szkołach — jak to
wygląda u nas i czym różnią się v1, v2, v3?"*

---

## 1. Ścieżka działa, ale urywa się w formularzu

| Etap | Gdzie | Stan |
|---|---|---|
| Koordynator zaznacza szkoły, wybiera handlowca i termin | `/baza`, pasek masowy | ✅ działa |
| Termin domyślnie dziś+14, „Przedłuż termin" masowo | `/baza` | ✅ (09.08) |
| Handlowiec widzi swoje szkoły z terminami, posortowane | `/leady` = „Moje szkoły" | ✅ działa |
| Przeterminowane podświetlone na czerwono | `/leady`, kolumna termin | ✅ działa |
| **Handlowiec w formularzu widzi, KTÓRE szkoły ma zrobić i DO KIEDY** | `/formularz/*` | ⚠️ **połowicznie** |

**Sedno problemu:** po zalogowaniu handlowiec ląduje **od razu na formularzu**
(`app.py`, `_po_zalogowaniu`), a formularz **nie pokazuje terminu ani jednej
szkoły**. Dane są pod ręką — kontekst formularza niesie `moje[].deadline`,
wyszukiwarka też selectuje termin — i w obu przypadkach docierają do
przeglądarki **nieużyte**. Do tego z wnętrza formularza nie ma linku do „Moich
szkół" (wszystkie warianty nadpisują pasek nawigacji), więc handlowiec, który
chce zobaczyć listę zadań na dziś, musi wyjść przez „Zakończ".

Jedyna informacja o terminie w formularzu to blok ostrzeżeń u góry — ale on
mówi „ta szkoła wraca do puli za 2 dni", czyli pokazuje **tylko te, które za
chwilę stracisz**, i tylko w oknie 2 dni, i tylko bez umówionego DT.

## 2. Czym różnią się warianty (w tym konkretnym aspekcie)

| | v1 (kroki) | v2 (ciągły) | v3 (nowy) |
|---|---|---|---|
| Wybór szkoły | jedno pole „szukaj" | Miejscowość → Placówka | jak v2 |
| „Moje szkoły" pokazane od razu | ✅ przy kliknięciu w puste pole, nagłówek „Twoje szkoły" | ❌ trzeba najpierw wybrać miasto | ❌ jak v2 |
| Oznaczenie moich | plakietka „moja" + „ma DT" | gwiazdka ★ + „N placówek, w tym M twoich" | jak v2 |
| Moje na górze listy | ✅ (sortuje serwer) | ✅ (sortuje przeglądarka) | ✅ |
| Podpowiedź, w których miastach mam szkoły | ❌ | ✅ „(twoje: 3)" przy mieście | ✅ |
| **Termin przy szkole** | ❌ | ❌ | ❌ |
| Ostrzeżenie „wraca do puli" | ✅ + licznik „i N więcej" | ✅ (ucina na 5 bez śladu) | ✅ (jak v2) |
| Limit pokazanych „moich" | **12** | wszystkie w mieście | wszystkie w mieście |

**Wniosek:** v1 jest dziś **najbliżej** pracy „z listy od koordynatora" — otwiera
się listą Twoich szkół, zanim cokolwiek wpiszesz. v2 i v3 zakładają, że
handlowiec wie, do jakiego miasta jedzie, i dopiero tam szuka. Żaden nie mówi
„masz 5 szkół, termin do 23.08".

## 3. Podpowiedź trenera a zajęcia — czy v1 to uwzględnia?

**Tak, ale pokazuje mniej, niż serwer policzył.**

Serwer (`przydzial.kandydaci`) dla każdego trenera liczy: kategorię
(wolny / bez deklaracji / z zastrzeżeniem / niedostępny), powód, wolne okna,
listę zajęć tego dnia, obciążenie miesięczne i rejon. Kolizja z istniejącymi
zajęciami **jest liczona** i wpływa na kategorię oraz powód.

| | v1 | v2 | v3 |
|---|---|---|---|
| Wszystkie 4 kategorie | ✅ | ❌ tylko wolni i bez deklaracji | ✅ zwijane grupy |
| Powód („ma DT 9–12") | ✅ widoczny | ⚠️ schowany w dymku | ✅ widoczny |
| Wolne okna trenera | ❌ | ❌ | ✅ |
| Lista zajęć trenera w tym dniu | ❌ | ❌ | ✅ |
| Ile pokazuje | 5 + „pokaż pozostałych" | 8, bez reszty | wszystkich, grupami |
| Reakcja na zmianę godzin | ✅ | ✅ | ✅ |
| Ostrzeżenie po wyborze osoby z listy | ❌ | ❌ | ✅ plakietka |

Czyli: **v1 uwzględnia zajęcia trenera pośrednio** — widać „uwaga · ma DT
9–12", ale nie widać, co dokładnie ten trener ma i kiedy jest wolny.
v3 jako jedyny pokazuje jedno i drugie.

## 4. Gwiazdki (plan tygodnia) — co to naprawdę jest

`pin_tydzien` to **własny wybór handlowca**, nie polecenie koordynatora:
gwiazdka zapisuje datę poniedziałku bieżącego tygodnia, więc lista **czyści się
sama w nowym tygodniu**. Ekran `/tydzien` pokazuje to, co przypięte.

Trzy rzeczy warte uwagi:
- **gwiazdka przebija termin w sortowaniu** — przypięte idą na górę przed
  szkołami z bliskim terminem (`repo.py`, domyślne sortowanie),
- **przypięcie nie sprawdza właściciela** — handlowiec może przypiąć cudzą
  szkołę (endpoint `/api/pin` nie zagląda w `leady.handlowiec`),
- przypięcie znika razem z przypisaniem przy auto-zwrocie i przy „odbierz".

## 5. Usterki znalezione przy okazji (nie zgłaszane wcześniej)

| # | Co | Skutek | Waga |
|---|---|---|---|
| 1 | Formularz nie pokazuje terminu, choć go ma | handlowiec w terenie nie wie, co pilne | **wysoka** |
| 2 | v1 pokazuje najwyżej **12** „moich szkół" | przy 15 przydzielonych trzech nie widać bez wpisania nazwy | średnia |
| 3 | `pasek_masowy` renderuje się handlowcowi na `/leady` | widzi „Przypisz / Odbierz / Przedłuż", klika → 403 | średnia |
| 4 | `/api/pin` bez sprawdzenia właściciela | handlowiec przypina cudzą szkołę | średnia |
| 5 | Wyszukiwarka: `LIMIT 60` **przed** wyniesieniem moich na górę | przy częstym słowie („szkoła") moja szkoła może w ogóle nie wejść do wyników | średnia |
| 6 | v2/v3 ucinają listę ostrzeżeń na 5 bez śladu, że jest więcej | handlowiec nie wie o 6. i 7. szkole, którą traci | niska |
| 7 | `/api/placowki` robi `JOIN leady` | placówka bez leada nie pojawi się wcale, z dwoma leadami — dwa razy | niska |
| 8 | `base.html` nie zna `formularz_v3` w podświetleniu nawigacji | kosmetyka | niska |

## 6. Propozycja: „Plan na dziś" w formularzu

Najtańsza rzecz, która domyka ścieżkę ze spotkania (~1,5 h, bez zmian w bazie):

W każdym wariancie, nad wyszukiwarką szkoły, sekcja zwijana:

```
 📋 Twoje szkoły od koordynatora (5)                      [rozwiń]
 ─────────────────────────────────────────────────────────────
  SP 12 Knurów            termin: 23.08  (za 14 dni)      [wypełnij →]
  MSP 3 Knurów            termin: 23.08  (za 14 dni)      [wypełnij →]
  SP 5 Zabrze             termin: 18.08  ⚠ za 3 dni       [wypełnij →]
  ZSP 1 Orzesze           ✅ DT umówione 16.09
```

- kliknięcie „wypełnij" wybiera tę szkołę w formularzu (dane już są w `FX_MOJE`),
- sortowanie po terminie rosnąco — najpilniejsze u góry,
- szkoły z umówionym DT na końcu, wyszarzone (robota zrobiona),
- **bez limitu 12**.

To działa tak samo w v1, v2 i v3, więc porównanie wariantów zostaje uczciwe:
różnią się dalej sposobem wypełniania, a nie tym, co widzą.
