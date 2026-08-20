# Poprawki po testach klienta — rejestr (runda 20.08.2026)

Docelowe miejsce tego pliku: `leady_app_v5/docs/18_POPRAWKI_2026-08.md`
(w repozytorium, żeby był wersjonowany razem z kodem i widoczny dla asystenta).

Surowa lista od klienta — bez przerabiania — zostaje w tym folderze jako
`_od_klienta_2026-08-20.*`. Ten plik to jej wersja robocza: z identyfikatorami,
typem i statusem.

---

## Jak to wypełnić

**ID** — `P01`, `P02`… Nadawaj po kolei, nigdy nie przenumerowuj. Ten sam
identyfikator trafia do commita, do testu i do wiadomości do klienta.

**Typ** — decyduje o tym, jaką drogą poprawka jedzie:

| Typ | Co to znaczy | Droga |
|---|---|---|
| `kod` | zmiana w plikach aplikacji | gałąź → demo → merge → produkcja |
| `dane` | zmiana w bazie | skrypt, osobno na demo i osobno na produkcji |
| `słownik` | wartość w słowniku | klient może sam przez panel koordynatora |
| `pytanie` | nie wiadomo, o co chodzi | dopytać PRZED pracą, nie po |

**Waga** — `bloker` (uniemożliwia pracę, idzie na produkcję nie czekając na
resztę listy) / `zwykła` / `kosmetyka`.

**Status** — `nowa` → `w pracy` → `na demo` → `sprawdzone` → `na produkcji`.
Do tego `wraca` (klient sprawdził i to nie to) oraz `odłożone`.

**Test** — nazwa pliku i sprawdzenia, które pilnuje, żeby ta rzecz nie wróciła.
Puste pole przy statusie `sprawdzone` to sygnał ostrzegawczy, nie drobiazg.

---

## Lista

| ID | Waga | Typ | Ekran / miejsce | Co jest źle (słowami klienta) | Co robimy | Status | Test |
|---|---|---|---|---|---|---|---|
| P01 | | | | | | nowa | |
| P02 | | | | | | nowa | |
| P03 | | | | | | nowa | |
| P04 | | | | | | nowa | |
| P05 | | | | | | nowa | |
| P06 | | | | | | nowa | |
| P07 | | | | | | nowa | |
| P08 | | | | | | nowa | |
| P09 | | | | | | nowa | |
| P10 | | | | | | nowa | |

---

## Bloki osobne (nie mieszczą się w jednym wierszu tabeli)

### B1. Typy kont

Stan dzisiejszy: 49 kont z PIN-ami, trzy role (trener / handlowiec / koordynator),
wielorolowość rozwiązana **dopiskiem w nazwie** (`03. Małolepsza (koordynator)`),
osoba będąca handlowcem i trenerem ma **dwa osobne konta**.

Do ustalenia przed kodowaniem:
- [ ] co dokładnie ma się zmienić w modelu ról
- [ ] tabela mapowania: stare konto → nowe (wypełnia i zatwierdza Kasia)
- [ ] co z PIN-ami przy scalaniu kont — PIN-ów nie da się odczytać, więc scalenie
      oznacza nową kartę dostępu dla tej osoby
- [ ] czy zmiana dotyka uprawnień (jeśli tak: trzy warstwy, nie sam wygląd menu)

Testy: `test_logowanie.py`, `test_serwis.py`, `test_trener.py`, `test_filtr_osob.py`.

### B2. Poszerzenie bazy szkół (RSPO)

- [ ] zakres zatwierdzony przez Kasię (warianty i liczby: `docs/12_RSPO.md`)
- [ ] próba na demo ze świeżą kopią produkcji, liczby przed/po
- [ ] kontrola: brak duplikatów (klucz = numer RSPO), przypisania i terminy DT
      przetrwały, ekrany „Baza" i „Moje szkoły" użyteczne przy nowej skali
- [ ] raport dopasowania nazw: ile automatem, ile do ręki
- [ ] klient obejrzał na demo i zaakceptował
- [ ] produkcja: kopia → ten sam skrypt, te same argumenty → liczby przed/po
- [ ] demo odświeżone po wszystkim

### B3. Zmiany w schemacie bazy

Dokładanie kolumn do `placowki` / `leady` / `eventy` załatwia `db.migruj()` przy
starcie — wystarczy dopisać klucz do odpowiedniej listy.

Wszystko inne (nowa tabela, zmiana znaczenia istniejącego pola) potrzebuje
skryptu migracyjnego: idempotentnego, wypisującego liczby przed i po,
przećwiczonego na świeżej kopii produkcji na demo.

| Zmiana | Rodzaj | Skrypt | Przećwiczone na demo | Na produkcji |
|---|---|---|---|---|
| | | | | |

---

## Pytania do klienta (zanim ruszymy)

Zebrane w jedno miejsce, żeby poszły jedną wiadomością, a nie sześcioma.

| # | Pytanie | Kogo dotyczy | Odpowiedź | Data |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |

Wiszące jeszcze z poprzedniej rundy (`CLAUDE.md`, sekcja „Czeka na odpowiedź klienta"):
- podpowiedź trenera w formularzu — czy handlowiec może obiecać termin, czy wiążąco
  potwierdza koordynator
- czy w formularzu czegoś brakuje (osoba kontaktowa, zgoda na salę, sprzęt)
- osoba figurująca i jako handlowiec, i jako trener ma dziś dwa konta — czy ma być jedno

---

## Dziennik rund

| Data | Co poszło na demo | Co poszło na produkcję | Kto sprawdzał |
|---|---|---|---|
| 20.08.2026 | | | |
