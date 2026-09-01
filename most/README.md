# Most — wystawianie grafiku zajęć aplikacji partnerskiej

Katalog na serwerze, w którym leży zawsze aktualny grafik naszych zajęć. Odbiorca
czyta go, kiedy chce; my nie wiemy kiedy i nie musimy wiedzieć.

## Dlaczego plik, a nie zapis wprost do ich bazy

Aplikacja partnera to statyczny front z bazą w chmurze. Nie ma żadnego mechanizmu
przyjmowania danych z zewnątrz — nie ma tabeli „przychodzące", nie ma importu
z pliku, nie ma endpointu. Nie mamy też do tej bazy konta ani potwierdzenia reguł
dostępu.

Plik jest jedynym końcem, który możemy zbudować i **sprawdzić sami**, bez czekania
na cudzą decyzję. Gdy konto się pojawi, format zostaje bez zmiany, a dochodzi
wyłącznie strona wpisująca — po ich stronie albo po naszej.

## Co powstaje

| plik | dla kogo | co to jest |
|---|---|---|
| `zajecia.json` | dla maszyny | **plik główny** — pełna migawka: wszystkie cykle i DT |
| `zajecia.xlsx` | dla człowieka | te same dane do otwarcia dwuklikiem, plus zakładka „Wystąpienia" (1 wiersz = 1 termin) |
| `zmiany.jsonl` | dla maszyny | co się zmieniło od poprzedniej migawki, 1 linia JSON na zdarzenie |
| `stan.json` | dla obu | kiedy powstało, ile czego, czy most żyje |

⚠️ **Pierwszy przebieg NIE jest zmianą w grafiku** i nie wolno mu tak wyglądać.
Wystawienie mostu w nowym katalogu daje **jedną** linię `pierwsza_migawka` z liczbą
rekordów, a nie tyle wpisów `dodane`, ile jest spotkań (na produkcji byłyby 124).
Odbiorca musi umieć odróżnić „wystawiliśmy most" od „handlowcy wpisali dziś
124 spotkania" — gdyby po jego stronie cokolwiek reagowało na dziennik, dostałby
lawinę na powitanie. Ten sam warunek łapie odtworzenie katalogu po awarii: skoro
nie mamy poprzednich skrótów, to nie WIEMY, co się zmieniło, i jedna uczciwa linia
mówi o tym więcej niż setka zmyślonych. `stan.json` niesie `pierwsza_migawka`.

Katalog: `MOST_DIR` (w kontenerze `/data/most`, mapowane na `/srv/most/<profil>`).
Poza kontenerem `most_dane/` w repozytorium.

## Kiedy się odświeża

Dwa zegary, oba w `most.czy_pora()`:

- **zmiana w bazie** → przepisujemy po `MOST_ODSTEP_SEK` (domyślnie 20 s). To jest
  „aktualizuje się, jak handlowiec coś wpisze". Odstęp chroni przed przepisywaniem
  pliku kilka razy w trakcie jednego zapisu formularza.
- **cisza** → przepisujemy i tak co `MOST_CO_ILE_MINUT` (domyślnie 60). Bicie serca:
  bez niego zamarły znacznik w `stan.json` wygląda identycznie jak „nic się nie
  zmieniło", a awaria wychodzi dopiero, gdy ktoś zapyta.

Znacznik „coś się ruszyło" stawia `db.zapisz_log()` — jedyne miejsce, przez które
przechodzi każdy zapis eventu i leada. Endpointów piszących po kalendarzu jest osiem
i dziewiąty powstanie bez przypomnienia; jedno miejsce nie ma jak przeoczyć zmiany.

Most wisi na `before_request`, nie na cronie — ten sam powód co przy automacie zwrotu
leadów: cron na VPS potrafi cicho przestać działać i nikt nie zauważa przez tydzień,
a wątek w tle ginie przy restarcie gunicorna. Trafia przy tym dokładnie tam, gdzie
trzeba: handlowiec, który właśnie zapisał zajęcia, zaraz potem otwiera ekran, bo
udany zapis kończy się przeładowaniem strony.

## Format `zajecia.json`

```json
{
  "format": "leady_app_v5 most v1",
  "wygenerowano": "2026-08-31T14:02:11",
  "profil": "prod",
  "strefa": "Europe/Warsaw (czas lokalny, znaczniki bez przesunięcia)",
  "liczby": { "cykle": 12, "cykle_aktywne": 11, "dt": 65, "dt_aktywne": 64,
              "niekompletne": 43 },
  "cykle": [ … ],
  "dt": [ … ]
}
```

**Nazwy pól w rekordach są ODBIORCY, nie nasze** (`school`, `weekday`, `start_time`,
`starts_on`). Gdybyśmy wysłali `placowka`, `godz_od`, `cykl_dzien`, po drugiej stronie
ktoś musiałby napisać tłumacza i utrzymywać go w nieskończoność. Tak import jest
przepisaniem pola w pole, a rozbieżność widać gołym okiem.

### Rekord cyklu

`id` · `source_event_id` · `kind: "recurring"` · `stan` (`aktywny` / `odwolany`) ·
`title` · `source_type` · `group` · `weekday` (**1 = poniedziałek … 7 = niedziela**) ·
`start_time` · `end_time` · `starts_on` · `ends_on` · `every_n_weeks` ·
`occurrences_agreed` · `occurrences_horizon_weeks` · `occurrences` ·
`cancelled_occurrences` · `school` · `address` · `city` · `region` · `county` ·
`commune` · `school_type` · `rspo` · `trainer_name` · `second_trainer_name` ·
`printer_name` · `room` · `equipment` · `classes` · `children` · `salesperson` ·
`updated_at` · `missing`

### Rekord DT

Jak wyżej, plus `kind: "one_off"` · `activity_type: "school_visit"` ·
`status` (`planned` / `cancelled`) · `date` · `starts_at` · `ends_at`.

## Sześć decyzji, które trzeba znać, żeby czytać ten plik

**1. `id` jest stabilnym kluczem zewnętrznym** (`leady-v5:event:<numer>`). Odbiorca
musi po nim rozpoznać, że to ten sam cykl co poprzednio — inaczej każdy import mnoży
wiersze.

**2. Wysyłamy policzone daty, nie regułę.** Cykl bywa u nas listą konkretnych dat
(uzgodniony pakiet wygrywa nad regułą „co N tygodni") i miewa wyjątki na pojedynczą
datę. Wysłanie samego „co wtorek od 2 października" zgubiłoby jedno i drugie,
a odbiorca liczyłby wystąpienia własnym kodem — czyli po pół roku firma miałaby dwa
różne kalendarze tych samych zajęć. Liczy to `calendar_view`, ten sam kod, co nasz
kalendarz na ekranie.

**3. `ends_on` tylko dla pakietu z uzgodnioną listą dat.** Cykl z reguły nie ma daty
końca; ostatnia policzona data to nasz horyzont liczenia
(`occurrences_horizon_weeks`), czyli miejsce, w którym przestaliśmy liczyć.
Podanie go jako `ends_on` byłoby nieprawdą, której odbiorca nie ma jak wykryć.
Stąd `occurrences_agreed`: `true` = ustalenie ze szkołą, `false` = nasze wyliczenie,
przy następnej migawce dłuższe.

**4. Odwołane też wysyłamy.** Zajęcia zdjęte z grafiku muszą dojechać, inaczej
zostaną u odbiorcy na zawsze jako duch. Odwołany cykl ma `stan: "odwolany"`, odwołany
pojedynczy termin siedzi w `cancelled_occurrences`. Rekord, który **zniknął** z migawki
(skasowany u nas), pojawia się w `zmiany.jsonl` jako `zniknelo` — u odbiorcy ma zostać
**wyłączony, nie skasowany**: przy jego zajęciach mogą już wisieć zastępstwa i wpisy
rozliczeniowe.

**5. `missing` mówi, czego brakuje do wstawienia.** Nasza aplikacja świadomie nie
blokuje zapisu przy brakach — handlowiec zapisuje to, co ustalił, a brak jest widoczny,
nie zakazany. Po stronie odbiorcy część tych pól bywa wymagana. Rekord jedzie razem
z listą braków, żeby dało się go odłożyć na bok zamiast wywalić import albo — gorzej —
wstawić wiersz z podstawionymi wartościami.

⚠️ To nie jest przypadek brzegowy: **na realnych danych 43 z 66 rekordów nie ma
godziny rozpoczęcia**. Godzina DT bywa ustalana później niż sam termin i tak wygląda
ta praca naprawdę.

**6. Czas jest LOKALNY, bez przesunięcia strefy.** `starts_at` to `2026-09-15T09:00:00`,
nie `…+02:00`. Świadomie: doklejenie strefy wymagałoby bazy stref w obrazie dockera
(`python:3.13-slim` jej nie ma) i przy zmianie czasu przesunęłoby zajęcia o godzinę.

## Czego most nie wysyła

**Telefon, mail, osoba kontaktowa i notatki** zostają u nas. Most przekracza granicę
zespołu handlowego, a pytanie „czy w pliku mają być telefony do szkół" postawione
w sierpniu nie doczekało się odpowiedzi — brak odpowiedzi znaczy „nie wysyłamy", bo
dane raz wysłane wracają tylko w teorii.

Notatek nie wysyłamy **w całości**, choć bywają przydatne („wejście od podwórza"):
to pole wolnego tekstu, a w wolnym tekście lądują nazwiska i numery telefonów. Gdyby
klient świadomie zdecydował inaczej, jest to jedna stała (`dane.WYSYLAJ_UWAGI`)
i jeden test do poprawienia.

Pilnuje tego `test_most.py`, który szuka po **wartościach** wpisanych do bazy testowej,
a nie po nazwach pól — samo przemianowanie kolumny go nie oszuka.

**Trenerów podajemy nazwiskiem, nie identyfikatorem.** Nie mamy identyfikatorów
odbiorcy i nie chcemy ich mieć — to byłaby druga baza ludzi do utrzymania. Mapowanie
i przypisanie obsady należy do nich.

**Typy inne niż cykle i DT nie wychodzą wcale.** Po ich stronie nie ma dla nich
miejsca, a wysyłanie „na zapas" zamienia most w drugi eksport wszystkiego.

## Obsługa

```bash
python -m most                 # przepisz pliki teraz
python -m most --podglad       # policz i wypisz braki, nic nie zapisuj
python -m most --stan          # co leży w katalogu i kiedy powstało

docker compose exec -T leady_v5 python -m most --stan
```

Wyłącznik awaryjny: `MOST=0` w środowisku i restart — bez cofania wdrożenia.

## Wdrożenie na serwer

```bash
sudo mkdir -p /srv/most/prod /srv/most/demo
sudo chown ubuntu:ubuntu /srv/most/prod /srv/most/demo
sudo chmod 755 /srv /srv/most /srv/most/prod /srv/most/demo   # odbiorca musi móc czytać
```

Potem `./wdroz.sh demo`, sprawdzenie ekranów z ręki, dopiero `./wdroz.sh prod`.

⚠️ Zmiana `docker-compose.yml` wymaga odtworzenia kontenera (`up -d`), nie samego
restartu — `wdroz.sh` robi `up -d --build`, więc wystarczy.

⚠️ Ścieżka w compose jest **bezwzględna**, nie `./most`: katalog aplikacji na VPS to
klon gita, w którym leży ten pakiet. `./most` przykryłby kod katalogiem danych.

⚠️ Kontener pisze jako `root`, więc pliki wyjdą `root:root 644` — odbiorca je
przeczyta, ale nie skasuje. Tak ma być.
