# Rejestr poprawek — runda 20.08.2026

Jeden wiersz = jedna poprawka. **ID `Pnn` nie zmienia się nigdy** — ten sam numer
trafia do commita, do testu i do wiadomości do Kasi („P04 gotowe, sprawdź na demo").
Kolumna `K` wskazuje zgłoszenie źródłowe w `ZGLOSZENIA_KASI_2026-08-20.html`.

**Typ:** `kod` (gałąź → demo → merge → produkcja) · `dane` (skrypt, osobno na demo
i osobno na produkcji) · `słownik` (Kasia może sama przez panel) · `pytanie`
(dopytać PRZED pracą).

**Status:** `nowa` → `w pracy` → `na demo` → `sprawdzone` → `na produkcji`.
Do tego `czeka` (na odpowiedź Kasi), `wraca` (sprawdziła i to nie to), `odłożone`.

Puste pole „Test" przy statusie `sprawdzone` to sygnał ostrzegawczy, nie drobiazg.

---

## Paczka A — uprawnienia · BLOKER, idzie osobno na produkcję

| ID | K | Typ | Gdzie | Co robimy | Status | Test |
|---|---|---|---|---|---|---|
| P01 | K01 | kod | `api_lead_update` | handlowiec zapisuje tylko na swoim leadzie; podgląd cudzych zostaje | nowa | `test_filtr_osob` — PATCH cudzego leada → 403 |
| P02 | K01 | kod | `api_lead_update` | `handlowiec` i `deadline` wyłącznie ścieżką koordynatora — dziś PH może przejąć lead i przedłużyć sobie termin | nowa | j.w. — PATCH obu pól przez PH → 403 |
| P03 | K02 | dane | produkcja | sprawdzić rolę konta Zuzy (i przejrzeć wszystkie 49 kont); kod ruszamy dopiero, gdyby rola była poprawna | nowa | — |

## Paczka B — błędy widoczne przy każdym użyciu

| ID | K | Typ | Gdzie | Co robimy | Status | Test |
|---|---|---|---|---|---|---|
| P04 | K09 | kod | `formularz2/3/4.js` | zmiana szkoły **nadpisuje** dane kontaktowe i mówi o tym; dziś zostają po poprzedniej | nowa | `test_formularz` — po jednym na wariant |
| P05 | K11 | kod | `app.py` `_miesiac_ekranu` | najpierw odtworzyć na demo; zapamiętany miesiąc z przeszłości przestaje wygrywać | nowa | `test_scenariusze` |
| P06 | K04 | kod | lista szkół w formularzu | jawna plakietka „widzisz 12 z 545 · filtr: moje szkoły [pokaż wszystkie]" przy samej liście | nowa | `test_filtr_osob` |
| P07 | K08 | kod | wybór szkoły | wpisywanie z klawiatury; „12" trafia w „Szkoła Podstawowa nr 12", miasto + numer naraz | nowa | `test_formularz` |

## Paczka C — kalendarz i obsada DT

| ID | K | Typ | Gdzie | Co robimy | Status | Test |
|---|---|---|---|---|---|---|
| P08 | K12 | kod | kalendarz | odwołanie DT ze śladem (powód, kto, kiedy); twarde kasowanie tylko koordynator | nowa | `test_scenariusze` |
| P09 | K18 | dane | produkcja | wpisy z prezentacji 06.08 (DT „Paziewski") — lista do potwierdzenia przez Kasię, potem usunięcie | nowa | — |
| P10 | K13 | kod | grafik | **czeka na pytanie 1** — N wolnych miejsc na evencie zamiast jednego wiersza „bez prowadzącego" | czeka | `test_przydzial` |
| P11 | K10 | kod | formularz + grafik | **czeka na pytanie 2** — prowadzący praktyki + praktykant, wpis u obu trenerów | czeka | `test_przydzial` |

## Paczka D — baza szkół (czeka na `POPRAWKA BAZY.xlsx` od Kasi)

| ID | K | Typ | Gdzie | Co robimy | Status | Test |
|---|---|---|---|---|---|---|
| P14 | K07 | słownik | słownik miast | zdjąć Gliwice, Mysłowice, Bytom — zero placówek, więc trzy wiersze | czeka | — |
| P13 | K05 | kod + dane | `placowki`, filtry | kolumna `powiat` + filtr na „Bazie", „Moich szkołach" i w formularzu | czeka | `test_scenariusze` |
| P12 | K03 | dane | `rspo.py` | import brakujących gmin; **`Nr RSPO` pusty dla 545 rekordów** → dopasowanie po nazwie + mieście, raport do ręcznego przejrzenia | czeka | próba na demo, liczby przed/po |
| P16 | K14 | kod | placówka | uwagi **trwałe przy placówce** (dziś `uwagi` są na leadzie i znikają przy zwrocie) + „ostatnio prowadził: X, zwrot: data" | czeka | `test_scenariusze` |
| P15 | K06 | pytanie | słownik miast | **nie wiemy, co poprawiać** — w bazie nie ma miast z nawiasem; pytanie 3 | czeka | — |

## Paczka E — konta i role

| ID | K | Typ | Gdzie | Co robimy | Status | Test |
|---|---|---|---|---|---|---|
| P17 | K17 | dane | `/uzytkownicy` | administracja tylko Kasia + Julia; Weronika zdjęta — **co jej zostaje: pytanie 8**; Przemek: pytanie 9 | czeka | `test_logowanie` |
| P18 | K16 | kod | model kont | jeden PIN na osobę, przełączanie roli w środku; **przebudowa, nie poprawka** — wymaga tabeli mapowania 49 kont | czeka | komplet 4 plików uprawnień |
| P19 | K22 | dane | `/uzytkownicy` | wymiana PIN-u koordynatora (poszedł czatem); najlepiej jednym drukiem kart razem z P18 | nowa | — |

## Paczka F — raport (po paczce D)

| ID | K | Typ | Gdzie | Co robimy | Status | Test |
|---|---|---|---|---|---|---|
| P20 | K15 | kod | nowy ekran / eksport | raport wykonania per handlowiec — 3 z 7 liczb wymagają P12, P13 i P16 | czeka | `test_scenariusze` |

## Poza aplikacją PH

| ID | K | Typ | Gdzie | Co robimy | Status | Test |
|---|---|---|---|---|---|---|
| P21 | K19 | kod | eksport | plik DT dla appki Zuzi; sprawdzić, czy pole „sala komputerowa / nasze laptopy" w ogóle istnieje | nowa | — |
| — | K20 | — | — | moduł zastępstw **u Zuzi**, nie u nas — zapisane, żeby nikt tego nie zaczął budować przy P10/P11 | poza zakresem | — |
| — | K21 | — | — | kalendarz DT w appce Zuzi na szkolenie trenerów — nasza część to P21; **jedyny zewnętrzny termin**, pytanie 10 | poza zakresem | — |

---

## Dziennik rund

| Data | Co poszło na demo | Co poszło na produkcję | Kto sprawdzał |
|---|---|---|---|
| 20.08.2026 | demo przeniesione do własnego katalogu, zasiane kopią produkcji (545/544) | — | Paweł |
