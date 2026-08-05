# Projekt: przydzielanie trenerów (v4)

Data: 04.08.2026 · Status: **zaimplementowane w tej wersji (leady_app_v4)**

## Skąd się bierze ta funkcja

v2 dała ekran dostępności — widać, kto kiedy może. Ale między „widzę siatkę
40 trenerów × 30 dni" a „wpisuję nazwisko w spotkanie" była dziura, którą
koordynatorka wypełniała pamięcią:

- kto jeździ w którą stronę województwa (**rejonu nie było w arkuszu w ogóle**),
- kto ma już za dużo zajęć (obciążenie),
- czy nie wchodzi to na inne zajęcia tego dnia (kolizja).

Dopóki te trzy rzeczy siedzą w trzech miejscach (albo w głowie), wybór trenera
jest zgadywaniem. Ten moduł zbiera je w jedną listę, posortowaną tak, że
najlepszy kandydat jest u góry.

To odpowiedź na pozycję z `07_PYTANIA_do_klienta.md`, C1:
*„Rejon trenera — bez tego nie da się sensownie podpowiadać, kogo wysłać."*

## Cztery kategorie kandydata

Kolejność na liście = kolejność w `przydzial.KATEGORIE`:

| Kategoria | Kiedy | Kolor |
|---|---|---|
| **wolny** | deklaracja pokrywa godziny spotkania i nic się nie nakłada | zielony |
| **nieznany** | brak deklaracji na ten dzień — **nie zakaz**, po prostu nie wiadomo | szary |
| **zastrzeżenie** | kolizja godzin albo spotkanie poza zadeklarowanym oknem | bursztyn |
| **niedostępny** | arkuszowe „XXX" na ten dzień | czerwony |

Rozdzielenie „nieznany" od „niedostępny" jest tą samą decyzją co w v2:
pusta komórka w arkuszu nie znaczyła „nie może", znaczyła „nikt nie wpisał".

## Sortowanie

```
kategoria → rejon (z rejonu przed spoza) → obciążenie rosnąco → nazwisko
```

Obciążenie to liczba zajęć w miesiącu spotkania — dzięki temu przy równych
warunkach podpowiada się ten, kto ma najmniej roboty, a nie ten, kto jest
pierwszy alfabetycznie (w arkuszu zawsze wygrywały te same nazwiska z góry listy).

## Czego moduł NIE robi

**Nie blokuje.** Każdego kandydata da się przydzielić — także oznaczonego jako
niedostępny; przycisk zmienia się wtedy na „Mimo to przydziel", a po zapisie
wraca ostrzeżenie. Ta sama zasada co przy kolizjach: *ostrzegamy, nigdy nie
blokujemy*, bo w realnej pracy zastępstwo w niedostępny dzień bywa jedynym
wyjściem, a arkusz nigdy niczego nie zabraniał.

**Nie ukrywa trenerów spoza rejonu.** Rejon zmienia kolejność, nie widoczność —
w wakacje i przy zastępstwach jeździ się wszędzie.

## Rejon trenera

Nowa tabela `rejony(trener, miasto)`, wiele miast na trenera (część osób
obsługuje dwa obszary — dlatego nie pojedyncze pole „rejon" ani sztywne grupy).

Ekran `/rejony` ma jedną rzecz, która oszczędza najwięcej klikania:
**podpowiedź z historii zajęć**. Rejon jest już w danych — skoro trener uczył
11× w Knurowie i 7× w Orzeszu, to jest jego teren; nikt tego tylko nigdy nie
zapisał. Zamiast klikać 33 miasta z listy, klikasz „Przyjmij jako rejon".

Sprawdzone na realnych danych: `04. Zemela` → Knurów (11), Orzesze (7),
Rybnik (5), Mikołów (4).

## Ekrany i API

| Gdzie | Co |
|---|---|
| karta leada → spotkanie → **„Kogo wysłać?"** | panel z rankingiem, klik = przydzielenie |
| `/rejony` | rejony wszystkich trenerów + edytor z podpowiedzią |
| `GET /api/kandydaci?event_id=` | ranking dla istniejącego spotkania (kontekst z bazy) |
| `GET /api/kandydaci?data=&godz_od=&godz_do=&miasto=` | ranking dla spotkania, którego jeszcze nie ma |
| `POST /api/rejon` | podmiana rejonu `{trener, miasta:[...]}` — miasta walidowane słownikiem |
| `GET /api/rejon/podpowiedz?trener=` | miasta z historii zajęć |

Przydzielenie idzie istniejącym `PATCH /api/event/<id>` (`field=trener`) —
nie dublujemy ścieżki zapisu, więc log zmian i ostrzeżenia działają tak samo
jak przy ręcznej edycji pola.

## Szczegóły, które łatwo przeoczyć

- **Spotkanie nie koliduje samo ze sobą.** Przy zmianie obsady istniejącego
  wpisu pomijamy go w liczeniu kolizji (`pomin_key`), inaczej każdy obecnie
  przypisany trener wyglądałby na zajętego.
- **Cykle są rozwijane.** Kandydat liczy też wystąpienia zajęć cyklicznych
  w tym dniu, nie tylko DT — przez `events_for_month`.
- **Brak godziny startu** wyłącza liczenie kolizji i wyjścia poza okno; panel
  mówi to wprost zamiast po cichu pokazywać wszystkich jako wolnych.
- **Brak miasta placówki** wyłącza rejon — też komunikowane w panelu.

## Poza zakresem tej iteracji (świadomie)

- **Masowa obsada** — ekran „spotkania bez trenera" z przydzielaniem hurtem.
- **Zastępstwa** — trener wypada na tydzień, kto przejmuje jego zajęcia
  (tabela `wyjatki_cyklu` i pole `zastepstwo` czekają gotowe).
- **Dojazd między szkołami** — dwa DT tego samego dnia w odległych miastach są
  dziś traktowane jak zwykła para zajęć; rejon rozstrzyga tylko „czy to jego teren".
- **Preferencje i kompetencje trenera** (VR, festyny, przedszkola vs szkoły) —
  ranking patrzy tylko na czas i teren.
