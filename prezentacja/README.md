# Prezentacja produktu — System Leadów v4

**Otwórz `index.html` dwuklikiem.** Nie potrzeba internetu, serwera ani aplikacji —
styl i skrypt siedzą w środku pliku. Działa też z pendrive'a.

| Klawisz | Co robi |
|---|---|
| `→` `←` (albo spacja) | następny / poprzedni slajd |
| `O` | spis wszystkich slajdów — kliknięcie przeskakuje |
| `Esc` | zamyka spis |
| `Home` / `End` | pierwszy / ostatni slajd |
| `Ctrl+P` | wydruk do PDF — jeden slajd na stronę |

Adres pamięta slajd (`index.html#s14`), więc da się wysłać komuś link
do konkretnego miejsca albo wrócić tam po odświeżeniu.

---

## Jak jest prowadzona

Nie listą funkcji, tylko **dniem pracy** — w kolejności, w jakiej rzeczy dzieją się
naprawdę. Funkcja pokazana bez sytuacji, w której jest potrzebna, nie broni się sama.

| Część | Kto mówi | Ekrany |
|---|---|---|
| 1 | Koordynator, poniedziałek rano | Pulpit, Baza |
| 2 | Handlowiec — mój dzień | Leady, karta leada |
| 3 | Kogo wysłać na to DT | Panel kandydatów, Dostępność |
| 4 | Grafik | Kalendarz: kolizje, filtr, trzy widoki |
| 5 | Porządek w danych | Słowniki, aliasy, eksport XLSX |
| 6 | Granice | co świadomie poza zakresem + pytania na koniec |

21 slajdów, ok. 20–25 minut z komentarzem.

---

## Skąd biorą się liczby

**Z bazy `data/leady_v3.db`, nie z głowy.** `dane.py` czyta ją tymi samymi funkcjami,
z których korzysta aplikacja (`repo`, `calendar_view`, `dostepnosc_view`, `przydzial`,
`filtry`), a `zbuduj.py` wstawia wyniki do slajdów. Dzięki temu na pytanie
„skąd te 152?" odpowiedź brzmi *„z Twojego pliku"*, a nie *„tak wyszło"*.

Po zmianie danych (import, czyszczenie, nowy miesiąc) przebuduj:

```bash
cd leady_app_v4/prezentacja
python zbuduj.py
```

Podgląd samych danych, bez budowania slajdów: `python dane.py`.

### Co ustawia się na górze `dane.py`

| Stała | Domyślnie | Po co |
|---|---|---|
| `MIESIAC_GRAFIK` | `2026-09` | miesiąc obsady i dostępności — tam są deklaracje |
| `MIESIAC_KOLIZJE` | `2026-06` | miesiąc kolizji i filtra — pełny miesiąc zajęć |
| `OSOBA_PRZYKLAD` | `02. Olszewska` | osoba, która jest **i handlowcem, i trenerką** — na niej pokazujemy różnicę zakresów filtra |

Przykłady (kolizja, lead z cyklem, spotkanie do obsadzenia, komórka dostępności)
**wyszukują się same** według warunków, a nie są wpisane na sztywno — więc po
podmianie bazy prezentacja dalej pokazuje sensowne przypadki, a nie puste miejsca.

---

## Zanim pokażesz to klientce

Deklaracje dostępności w tej bazie są **wypełnione przykładowo** (1700 wierszy
z `uwagi='demo'`) — to jedyna rzecz w prezentacji, której nie ma w pliku `PH Nowy`.
Prezentacja mówi o tym wprost, przypisem na dwóch slajdach, żeby dopisek „(demo)"
pojawiający się przy powodach nie wyglądał na usterkę.

Jeśli wolisz pokazać ekran bez danych przykładowych:

```sql
DELETE FROM dostepnosc WHERE uwagi = 'demo';
```

Po wyczyszczeniu i ponownym `python zbuduj.py` przypis znika sam, ale panel
„Kogo wysłać?" pokaże wtedy głównie kategorię „bez deklaracji" — bo faktycznych
deklaracji jest w bazie 48.

---

## Pliki

| Plik | Co to |
|---|---|
| `index.html` | **gotowa prezentacja** — to się otwiera i pokazuje |
| `zbuduj.py` | generator: układ slajdów, styl, treść |
| `dane.py` | wyciąganie liczb i przykładów z bazy |
| `README.md` | ten plik |

`index.html` jest generowany — poprawki wpisuj w `zbuduj.py` i przebuduj,
inaczej znikną przy następnym uruchomieniu.
