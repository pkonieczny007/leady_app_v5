# 17. Kopie na Mac mini — ściąganie z ręki i odtwarzanie

Kartka do trzymania na Macu. Cztery rzeczy: jak zrobić kopię teraz, jak
sprawdzić, że automat żyje, co znaczą komunikaty i **jak z tej kopii odtworzyć
aplikację**, gdy będzie trzeba.

Aktualna wersja: `~/src/leady_app_v5/docs/17_KOPIE_NA_MACU.md`
(odświeżenie: `cd ~/src/leady_app_v5 && git pull`).

---

## 1. Kopia z ręki, teraz

```bash
~/bin/kopia_na_maca.sh --cel ~/kopia_reczna_vps --librus --kod
```

Ląduje w `~/kopia_reczna_vps/<data>_<godzina>/`. Katalog jest osobny od tego,
do którego pisze automat (`~/Backups/leady`) — dzięki temu Twoje ręczne
uruchomienia nie zacierają śladu po automacie i odwrotnie.

Warto to zrobić **przed każdą większą zmianą na produkcji**: przed importem
nowych danych, przed wdrożeniem nowej wersji, przed masową operacją
w aplikacji. Kopia sprzed ryzykownego kroku jest warta więcej niż dziesięć
kopii z tygodnia, w którym nic się nie działo.

Bez przełączników działa też krócej:

| polecenie | co robi |
|---|---|
| `~/bin/kopia_na_maca.sh` | sama baza aplikacji, do `~/Backups/leady` |
| `--cel <katalog>` | zapisz gdzie indziej |
| `--librus` | dołóż dane sąsiedniej aplikacji `librus` |
| `--kod` | odśwież lustro repozytorium z GitHuba |

---

## 2. Codzienna kontrola — dwie komendy

```bash
cat ~/Backups/leady/OSTATNIA_UDANA.txt
tail -20 ~/Backups/leady/kopia.log
```

Data w pierwszym pliku to **jedyna rzecz, która odróżnia maszynę robiącą kopie
od maszyny, która przestała je robić**. Obie wyglądają tak samo. Jeśli data jest
starsza niż wczoraj — coś się zacięło i warto zajrzeć do logu.

Stan automatu:

```bash
systemctl --user list-timers kopia-leady     # kiedy następne, kiedy ostatnie
journalctl --user -u kopia-leady -n 30       # co się działo
```

---

## 3. Co znaczą komunikaty

| Komunikat | Znaczenie |
|---|---|
| `OK prod_….db 545 placowek` | kopia pobrana **i sprawdzona** — otwiera się i ma dane |
| `POMINIETE: brak polaczenia` | serwer niedostępny albo brak sieci. **To nie jest awaria** — przy pierwszym uruchomieniu zwykle znaczy brak klucza SSH; skrypt dopisze wtedy do logu, co zrobić |
| `librus: katalog … -> librus_….tar.gz` | dane librusa spakowane |
| `BLAD … (prawa dostepu?)` | katalog należy do roota i `tar` nie dał rady. Lepszy czytelny błąd niż niepełne archiwum udające komplet |
| `UWAGA: brak sqlite3` | pliki są, ale **niesprawdzone**. `sudo apt install sqlite3` |

---

## 4. Odtworzenie bazy z kopii

To jest powód, dla którego to wszystko istnieje. Kopia, której nigdy nie
odtworzono, jest tylko nadzieją — ta ścieżka została przećwiczona na demo
10.08 i przeszła w komplecie (545 placówek, 69 eventów, 44 rejony wróciły).

**Najpierw sprawdź, co odtwarzasz.** Nazwa pliku nie mówi wszystkiego:

```bash
sqlite3 ~/kopia_reczna_vps/2026-08-10_1403/prod_2026-08-10_0911.db \
  "SELECT COUNT(*) FROM placowki; SELECT COUNT(*) FROM leady;"
```

**Potem wyślij ją na serwer:**

```bash
scp ~/kopia_reczna_vps/2026-08-10_1403/prod_2026-08-10_0911.db ubuntu@57.128.241.52:/tmp/
```

**I na serwerze podłóż ją kontenerowi:**

```bash
ssh ubuntu@57.128.241.52
cd ~/apps/ph.silesia3d.site

# kopia stanu SPRZED odtwarzania — nawet jeśli jest zepsuty
docker compose exec -T leady_v5 python narzedzia/baza.py backup --profil prod

docker compose stop leady_v5
docker compose run --rm leady_v5 sh -c \
  'cp /tmp/prod_2026-08-10_0911.db /data/leady_v3.db && rm -f /data/leady_v3.db-wal /data/leady_v3.db-shm'
docker compose start leady_v5

# sprawdzenie — ma pokazać 545
docker compose exec leady_v5 python -c "import db; c=db.get_conn(); print(c.execute('SELECT COUNT(*) FROM placowki').fetchone()[0], 'placowek')"
```

Dwie rzeczy, które łatwo pominąć, a psują odtwarzanie:

- **`docker compose stop` przed podmianą.** Gunicorn trzyma plik otwarty;
  podmiana pod działającą aplikacją kończy się bazą w stanie nie do przewidzenia.
- **Skasowanie `-wal` i `-shm`.** To pliki towarzyszące STAREJ bazie. Zostawione
  przy nowej potrafią dać „database disk image is malformed".

`docker compose run` nie publikuje portów, więc nie wchodzi w drogę niczemu,
co akurat działa.

---

## 5. Co gdzie leży

| | |
|---|---|
| kopie automatu | `~/Backups/leady/<data>/` |
| kopie z ręki | `~/kopia_reczna_vps/<data>/` |
| log i znacznik | w każdym z tych katalogów osobno |
| lustro repozytorium | `<katalog>/leady_app_v5.git` |
| skrypt | `~/bin/kopia_na_maca.sh` |
| źródła | `~/src/leady_app_v5` |
| na serwerze | wolumen dockera, `/data/kopie` widziane z kontenera |

---

## 6. Czego w tych kopiach NIE MA

**Pliku `.env` z serwera** — a w nim `SECRET_KEY` i PIN koordynatora. Nie jest
w repozytorium i nie powinien leżeć na dysku obok kopii; jego miejsce jest
w menedżerze haseł. Bez niego odtworzysz dane i kod, ale postawienie serwera od
zera wymaga wpisania nowych wartości (co unieważni wszystkie zalogowane sesje —
zadziała, tylko wszyscy będą musieli zalogować się ponownie).

**Uwaga o zawartości:** w tych plikach są telefony i maile dyrektorów szkół oraz
skróty PIN-ów. Katalogi mają prawa `700`, pliki `600` i tak ma zostać. Nie
wrzucaj ich na GitHuba ani do chmury bez szyfrowania — git nigdy nie zapomina,
a skasowanie pliku nie usuwa go z historii.
