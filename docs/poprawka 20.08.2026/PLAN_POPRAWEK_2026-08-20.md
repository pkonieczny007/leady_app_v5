# Poprawki po testach klienta — plan techniczny (20.08.2026)

Dotyczy: `leady_app_v5` (produkcja `https://ph.silesia3d.site`, demo `https://demo-ph.silesia3d.site`).

Trzy rzeczy naraz: (1) sporo poprawek z testów klienta, (2) poszerzenie bazy szkół,
(3) zmiany w typach kont / w bazie. Do tego demo ma przestać być „tą samą apką
z inną bazą", a stać się **osobnym środowiskiem z własnym kodem** — żeby dało się
na nim pokazać gałąź z poprawkami, zanim cokolwiek dotknie produkcji.

---

## 0. Odpowiedzi na Twoje trzy pytania

**Czy potrzebuję informacji od Claude z VPS?**
Do samych poprawek — nie. Kod poprawiamy lokalnie, w repozytorium, na gałęzi.
Ale do rozdzielenia demo potrzebne są **cztery fakty z serwera**, których nie da
się zgadnąć: nazwa projektu compose i nazwy wolumenów, na którym commicie stoi
produkcja, jak katalog na VPS uwierzytelnia się do GitHuba (klucz SSH czy token)
i co dokładnie mówi nginx. Gotowy blok poleceń → **Etap A**. To jedno wklejenie
i jedna odpowiedź, nie dialog.

**Czy listę poprawek pisać w czacie?**
Nie w czacie — do pliku. Obok tego planu jest `LISTA_POPRAWEK_szablon.md`.
Wklej tam surową listę od klienta i ponadawaj identyfikatory (P01, P02, …).
Powód jest praktyczny: ten sam identyfikator wchodzi potem do commita, do testu
i do wiadomości zwrotnej do klienta („P07 gotowe, sprawdź na demo"). Przy
kilkudziesięciu poprawkach lista w czacie rozpłynie się po dwóch godzinach,
a plik zostaje i widać na nim postęp. Wersję roboczą trzymaj w repozytorium
(`docs/18_POPRAWKI_2026-08.md`) — wtedy jest wersjonowana razem z kodem
i asystent ją widzi bez wklejania.

**Czy otwierać VSCode bezpośrednio w aplikacji?**
Tak, i to jest ważniejsze, niż wygląda. Otwieraj w
`C:\XEN\AI-szkolenie\SIERPIEN2026\leady_app_v5` — nie w folderze nadrzędnym.
Tylko wtedy wczyta się `CLAUDE.md` (grabie, konwencje, decyzje projektowe),
działa git i testy widzą swoje ścieżki. Ten folder z poprawkami zostaje na
surowe materiały od klienta i na ten plan.

---

## 1. Zasada, wokół której kręci się cała reszta

**Kod jedzie gitem, dane jadą skryptem.**

- Kod: gałąź → demo → akceptacja → merge do `main` → produkcja. Nigdy odwrotnie.
- Dane: identyczna operacja wykonana **osobno na demo i osobno na produkcji**,
  tym samym skryptem, z policzeniem rekordów przed i po.
- **Bazy demo NIGDY nie kopiujemy na produkcję.** Produkcja pracuje cały czas —
  w chwili, gdy kopiujesz prod → demo, demo zaczyna się starzeć. Wgranie jej
  z powrotem skasowałoby wszystko, co handlowcy wpisali w międzyczasie.

Z tego wynika kierunek jedyny słuszny: **prod → demo (dane)**, **demo → prod (kod)**.

---

## 2. Co się zmienia w układzie środowisk

**Dziś:** jeden katalog na VPS `/home/ubuntu/apps/ph.silesia3d.site`, w nim jedno
`docker-compose.yml` z dwiema usługami. Obie budują się **z tego samego katalogu
źródłowego**, czyli demo i produkcja mają zawsze **identyczny kod** — różnią się
tylko wolumenem i zmienną `PROFIL`. Dlatego dziś nie da się „pokazać poprawek na
demo": przebudowa demo przebudowałaby ten sam kod, który idzie na produkcję.

**Docelowo:** dwa katalogi, dwa klony, dwie gałęzie.

```
/home/ubuntu/apps/ph.silesia3d.site/        gałąź main               → 127.0.0.1:5301
/home/ubuntu/apps/demo-ph.silesia3d.site/   gałąź poprawki-2026-08   → 127.0.0.1:5302
```

Plik `docker-compose.yml` zostaje **jeden i wspólny** (jest w repozytorium), ale
w każdym katalogu **uruchamiamy tylko swoją usługę po nazwie**:

```bash
docker compose up -d --build leady_v5        # w katalogu produkcyjnym
docker compose up -d --build leady_v5_demo   # w katalogu demo
```

Nazwa projektu compose bierze się z nazwy katalogu, więc wolumeny same się
rozjeżdżają — katalog demo dostaje **nowy, pusty wolumen**, który zaraz zasiejemy
kopią produkcji. Katalogu produkcyjnego **nie ruszamy** (żadnego `COMPOSE_PROJECT_NAME`
w jego `.env`!) — zmiana nazwy projektu odczepiłaby produkcję od jej wolumenu
z danymi.

Bezpiecznik, który już tam jest: `container_name` jest globalny, więc pomyłkowe
`docker compose up -d` bez nazwy usługi w katalogu demo skończy się **głośnym
błędem** o zajętej nazwie `leady_app_v5`, a nie cichym drugim kontenerem produkcji.

Nginx nie wymaga zmian, o ile porty zostają 5301/5302 — potwierdzamy w Etapie A.

---

## 3. Kalendarz etapów

| Etap | Co | Gdzie |
|---|---|---|
| A | Meldunek z VPS | serwer, 5 min |
| B | Rejestr poprawek | ten folder + repo |
| C | Gałąź i praca lokalna | Windows / VSCode |
| D | Demo w osobnym katalogu | serwer |
| E | Kopia bazy produkcyjnej na demo | serwer |
| F | Pętla poprawek: kod → testy → demo → klient | oba |
| G | Poszerzenie bazy szkół (RSPO) | osobno demo, osobno prod |
| H | Typy kont i zmiany w schemacie | oba |
| I | Wejście na produkcję + wycofanie | serwer |

Etapy A–E robimy raz, na początku. F–H to praca właściwa. I — na końcu.

---

## Etap A — meldunek z VPS (wklej to Claude'owi na serwerze)

```bash
cd /home/ubuntu/apps/ph.silesia3d.site
echo "=== git ==="
git rev-parse --short HEAD; git status -sb; git log --oneline -5
git config --get remote.origin.url
ls -la ~/.ssh/ 2>/dev/null | head; ls -la ~/.git-credentials 2>/dev/null
echo "=== compose i kontenery ==="
docker compose ls
docker compose ps
echo "=== wolumeny (nazwa projektu widać po prefiksie) ==="
docker volume ls | grep -i leady
docker inspect leady_app_v5      --format '{{range .Mounts}}{{.Name}} -> {{.Destination}}{{"\n"}}{{end}}'
docker inspect leady_app_v5_demo --format '{{range .Mounts}}{{.Name}} -> {{.Destination}}{{"\n"}}{{end}}' 2>/dev/null
echo "=== nginx ==="
ls /etc/nginx/sites-enabled/
grep -n -E "server_name|proxy_pass" /etc/nginx/sites-enabled/*silesia3d* 2>/dev/null
echo "=== cron kopii ==="
crontab -l
echo "=== stan baz ==="
docker compose exec -T leady_v5      python narzedzia/baza.py lista
docker compose exec -T leady_v5_demo python narzedzia/baza.py lista 2>/dev/null
echo "=== miejsce na dysku ==="
df -h /
```

Z tego potrzebne są konkretnie:

1. **commit produkcji** — czy `main` na serwerze to `6a3e181` (ostatni lokalnie),
   czy produkcja stoi na czymś starszym. Jeśli starszym, poprawki dokładamy na to,
   co realnie działa, a nie na to, co leży lokalnie.
2. **nazwa projektu compose i nazwy wolumenów** — żeby świadomie nie ruszyć
   wolumenu produkcyjnego i wiedzieć, który stary wolumen demo zostanie sierotą.
3. **sposób logowania do GitHuba** (SSH czy token) — drugi klon musi umieć `git pull`.
4. **`proxy_pass` dla obu subdomen** — potwierdzenie, że to 127.0.0.1:5301/5302
   i że nginx nie trzeba tykać.

---

## Etap B — rejestr poprawek

1. Surową listę od klienta zapisz w tym folderze (`_od_klienta_2026-08-20.*`).
2. Przepisz ją do `LISTA_POPRAWEK_szablon.md` → zapisz jako
   `docs/18_POPRAWKI_2026-08.md` w repozytorium.
3. Każdej pozycji nadaj **ID (P01…)** i **typ**:
   - `kod` — zmiana w plikach, idzie gałęzią,
   - `dane` — zmiana w bazie, idzie skryptem na obu bazach,
   - `słownik` — wartość w słowniku (klient może sam przez panel),
   - `pytanie` — nie wiadomo, co klient miał na myśli; dopytać przed pracą.
4. Osobno oznacz **blokery** (uniemożliwiają pracę) i **kosmetykę**. Blokery robimy
   pierwsze i wypuszczamy na produkcję nie czekając na resztę listy.

To rozdzielenie jest kluczowe: przy „sporo poprawek" najczęstszy sposób na
utopienie tygodnia to trzymanie jednej wielkiej gałęzi, w której siedzi zarówno
poprawiona literówka, jak i przebudowa kont.

---

## Etap C — gałąź i praca lokalna

```powershell
cd C:\XEN\AI-szkolenie\SIERPIEN2026\leady_app_v5
git checkout main
git pull --ff-only
git tag przed-poprawkami-2026-08-20        # punkt powrotu dla KODU
git push origin przed-poprawkami-2026-08-20
git checkout -b poprawki-2026-08
git push -u origin poprawki-2026-08
```

Porządki przy okazji: gałąź `CYKLICZNE-PRZEDSZKOLE` jest już scalona do `main`
(sprawdzone), można ją skasować lokalnie i na origin.

**Lokalna baza do pracy.** W repo leży `data/prod` z 10.08 — to **nieaktualna
atrapa produkcji** i pułapka: uruchomienie lokalnie z `PROFIL=prod` wygląda jak
produkcja, a nią nie jest. Zasada na czas poprawek: **lokalnie pracujemy wyłącznie
na `PROFIL=test`**, zasianym świeżą kopią produkcji:

```powershell
.\narzedzia\kopia_z_serwera.ps1                     # ściąga kopie z VPS + sprawdza je
python narzedzia\baza.py przywroc --profil test --z "C:\XEN\AI-szkolenie\SIERPIEN2026\kopie_vps\<data>\prod_<stempel>.db"
$env:PROFIL="test"; python app.py                   # http://127.0.0.1:5301
```

Po każdej poprawce, przed commitem — komplet testów (wszystkie muszą przejść):

```powershell
python test_parsers.py; python test_scenariusze.py; python test_dostepnosc.py
python test_przydzial.py; python test_filtr_osob.py; python test_formularz.py
python test_logowanie.py; python test_serwis.py; python test_trener.py
```

Commit na poprawkę (albo na spójną grupę), w treści ID i **decyzja**, nie lista
plików: `P07 termin DT bez godziny wypada z planu dnia — zamiast pustki „godz. nieustalona"`.

---

## Etap D — demo w osobnym katalogu (na VPS, raz)

```bash
# 1. Zdejmij STARE demo z projektu produkcyjnego.
#    Wolumen zostaje (nie usuwamy!) — to jedyna kopia dotychczasowych danych demo.
cd /home/ubuntu/apps/ph.silesia3d.site
docker compose stop leady_v5_demo
docker compose rm -f leady_v5_demo          # nazwa kontenera musi się zwolnić
docker volume ls | grep -i demo             # zapisz nazwę osieroconego wolumenu

# 2. Drugi klon repozytorium — katalog nazwany jak subdomena.
cd /home/ubuntu/apps
git clone <URL_Z_ETAPU_A> demo-ph.silesia3d.site
cd demo-ph.silesia3d.site
git checkout poprawki-2026-08

# 3. Własny .env (nie ma go w gicie — trzeba założyć z ręki).
cp .env.example .env && chmod 600 .env
nano .env
```

W `.env` katalogu demo:
- `SECRET_KEY` — **własny, inny niż produkcyjny** (`python3 -c "import secrets; print(secrets.token_hex(32))"`).
  Wspólny klucz oznacza, że ciastko sesji z demo działa na produkcji.
- `PIN_KOORDYNATORA` — wypełnij, choć konta i tak przyjdą z kopiowanej bazy.
- `HTTPS=1` — certyfikat dla `demo-ph.silesia3d.site` już jest.
- `PIN_SERWISOWY` — **NIE ustawiać.** Po Etapie E na demo leżą prawdziwe dane.

```bash
# 4. Start demo z nowego katalogu (nazwa usługi OBOWIĄZKOWO).
docker compose up -d --build leady_v5_demo
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5302/logowanie   # ma być 200
docker compose ps
docker volume ls | grep -i leady    # powinien dojść NOWY wolumen z prefiksem demo-ph...
```

Po tym kroku demo ma pusty wolumen — aplikacja sama założy bazę ze słownikami.
To stan przejściowy, zaraz go nadpiszemy.

**Od tej chwili wdrożenia wyglądają tak:**

```bash
cd /home/ubuntu/apps/demo-ph.silesia3d.site && ./wdroz.sh demo   # gałąź poprawek
cd /home/ubuntu/apps/ph.silesia3d.site      && ./wdroz.sh prod   # main, z kopią przed
```

`wdroz.sh` robi `git pull --ff-only` w swoim katalogu, więc każdy katalog ciągnie
swoją gałąź. Przed produkcją robi kopię — i o to chodzi.

---

## Etap E — demo dostaje kopię bazy produkcyjnej

Dokładnie to, o czym pisałeś: demo ma być identyczne z produkcją — ten sam kod
(dopóki nie odbijemy gałęzi) i **prawdziwe dane**, nie wymyślone.

**Zanim to zrobisz, świadoma decyzja:** po tej operacji demo przestaje być
poligonem, na którym wolno wszystko. Na publicznej subdomenie lądują telefony
i maile dyrektorów szkół oraz skróty PIN-ów. Skutki praktyczne: demo trzyma się
tych samych zasad co produkcja (`.env` z własnym kluczem, żadnego `PIN_SERWISOWY`,
dostęp tylko po PIN-ie), a linka do demo nie rozsyłamy szerzej niż do osób, które
i tak mają dostęp do produkcji. To Twoja decyzja i jest sensowna — testowanie na
atrapie nie wykrywa błędów, które wychodzą dopiero na 545 placówkach — ale musi
być podjęta świadomie, a nie przy okazji.

**Pasek profilu zostaje.** Demo trzyma `PROFIL=test`, więc u góry wisi kolorowy
pasek „test". Wygląda jak niekonsekwencja („demo ma być identyczne"), ale to
jedyna rzecz, która w dwóch otwartych kartach przeglądarki powstrzyma kogoś przed
zrobieniem importu w trybie „replace" w oknie produkcji.

Zapisz jako `narzedzia/odswiez_demo.sh` (w repozytorium, na gałęzi poprawek —
przyda się jeszcze wiele razy), `chmod +x`:

```bash
#!/usr/bin/env bash
#
# Odświeża bazę DEMO świeżą kopią PRODUKCJI. Uruchamiać w katalogu demo.
#
# Po co skrypt: to pięć kroków, z których pominięcie jednego (plików -wal/-shm
# po starej bazie) daje bazę, która otwiera się i pokazuje NIE TE dane. Skrypt
# jest jednokierunkowy — z produkcji do demo. Odwrotnie nigdy.
set -euo pipefail

PROD_KONTENER=leady_app_v5
DEMO_USLUGA=leady_v5_demo
PRZEJSCIOWY=$HOME/przenosiny-demo

echo "== 1/5 świeża kopia produkcji =="
docker exec "$PROD_KONTENER" python narzedzia/baza.py backup --profil prod --bez-excela

echo "== 2/5 wyjmuję plik z kontenera produkcyjnego =="
rm -rf "$PRZEJSCIOWY"; mkdir -p "$PRZEJSCIOWY"; chmod 700 "$PRZEJSCIOWY"
PLIK=$(docker exec "$PROD_KONTENER" sh -lc 'ls -1t /data/kopie/prod_*.db | head -1' | tr -d '\r')
NAZWA=$(basename "$PLIK")
docker cp "${PROD_KONTENER}:${PLIK}" "$PRZEJSCIOWY/"
echo "   $NAZWA"

echo "== 3/5 zatrzymuję demo =="
docker compose stop "$DEMO_USLUGA"

echo "== 4/5 wstawiam bazę do demo =="
# Kontener jednorazowy, bo aplikacja nie może trzymać pliku w trakcie podmiany.
# -wal/-shm to towarzysze STAREJ bazy — zostawione, dokleiłyby się do nowej.
docker compose run --rm --no-deps -v "$PRZEJSCIOWY:/wejscie:ro" "$DEMO_USLUGA" \
    sh -lc "mkdir -p /data/kopie && cp /wejscie/$NAZWA /data/kopie/ && \
            rm -f /data/leady_v3.db-wal /data/leady_v3.db-shm && \
            python narzedzia/baza.py przywroc --profil test --z /data/kopie/$NAZWA"

echo "== 5/5 start i kontrola =="
docker compose up -d "$DEMO_USLUGA"
for i in $(seq 1 20); do
    KOD=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5302/logowanie || true)
    [ "$KOD" = "200" ] && break
    sleep 1
done
echo "   HTTP: ${KOD:-brak}"
docker compose exec -T "$DEMO_USLUGA" python narzedzia/baza.py lista

# W tych plikach są dane osobowe — nie zostają w katalogu domowym.
rm -rf "$PRZEJSCIOWY"
echo "== gotowe =="
```

Uruchomienie i kontrola:

```bash
cd /home/ubuntu/apps/demo-ph.silesia3d.site
./narzedzia/odswiez_demo.sh
```

Liczby z `baza.py lista` na demo **muszą się zgadzać** z produkcją (dziś rzędu
545 placówek / 545 leadów — porównaj z meldunkiem z Etapu A). Potem wejdź na
`https://demo-ph.silesia3d.site` swoim produkcyjnym PIN-em — PIN-y przyszły
z kopią, więc zadziała ten sam.

**Kiedy powtarzać:** przed każdą rundą testów klienta i **zawsze przed próbą
generalną migracji danych** (Etapy G i H). Demo starzeje się od pierwszej minuty.

---

## Etap F — pętla robocza

Jedna runda, powtarzana:

1. **Lokalnie** — poprawki z jednej grupy (np. wszystkie „kalendarz"), commit po ID.
2. **Testy** — komplet 9 plików. Do poprawki, która zmieniła zachowanie, dopisz
   sprawdzenie w odpowiednim `test_*.py`. Bez tego przy następnej rundzie ta sama
   rzecz wróci i nikt się nie zorientuje.
3. `git push` gałęzi.
4. **Demo** — `cd /home/ubuntu/apps/demo-ph.silesia3d.site && ./wdroz.sh demo`.
5. **Do klienta** — lista ID gotowych do sprawdzenia, z nazwą ekranu. Nie „wrzuciłem
   poprawki", tylko „P07, P08, P12 — kalendarz, sprawdź proszę".
6. W rejestrze: status `do sprawdzenia` → `sprawdzone` / `wraca`.

Blokery mogą pójść na produkcję osobno, nie czekając na resztę: `git checkout main`,
`git cherry-pick <commit>`, testy, `wdroz.sh prod`, potem `git rebase main` na gałęzi
poprawek, żeby się nie rozjechała.

---

## Etap G — poszerzenie bazy szkół (RSPO)

To **zmiana danych**, nie kodu — i tu rozjazd demo↔prod boli najbardziej, bo
w międzyczasie handlowcy dopisują leady.

Narzędzie jest: `narzedzia/rspo.py` (wykaz z CSV rejestru RSPO + raport dopasowania
nazw), warianty zakresu opisane w `docs/12_RSPO.md`. Kluczem jest **numer RSPO**,
nie nazwa — zmiana nazwy szkoły nie rozwala bazy.

Kolejność:

1. **Zakres do decyzji Kasi** — cały Śląsk, wybrane powiaty, tylko szkoły
   podstawowe + przedszkola? Warianty i liczby są w `docs/12_RSPO.md`. Bez tej
   decyzji nie zaczynaj: różnica to setki albo tysiące rekordów, które potem
   trzeba by usuwać z bazy, w której już ktoś pracował.
2. **Próba generalna na demo** — świeże `odswiez_demo.sh`, potem import z liczbami
   przed/po:
   ```bash
   docker compose exec -T leady_v5_demo python narzedzia/baza.py lista       # PRZED
   docker compose exec -T leady_v5_demo python narzedzia/rspo.py <argumenty> # import
   docker compose exec -T leady_v5_demo python narzedzia/baza.py lista       # PO
   ```
3. **Kontrola na demo, zanim ruszysz produkcję:**
   - czy istniejące 545 placówek **nie zdublowało się** (dopasowanie po RSPO),
   - czy przypisania handlowców i terminy DT **przetrwały**,
   - czy ekrany „Baza" i „Moje szkoły" nie zamieniły się w ścianę tysięcy rekordów
     bez filtra (to jest realne ryzyko użytkowe — handlowiec ma dziś 159 szkół,
     po poszerzeniu może mieć tysiące),
   - raport dopasowania nazw: ile trafiło automatem, ile do ręki.
4. **Klient ogląda demo** i akceptuje — na demo, nie na produkcji.
5. **Produkcja** — kopia, ten sam skrypt z tymi samymi argumentami, te same trzy
   `lista` przed/po, porównanie liczb z próbą na demo:
   ```bash
   cd /home/ubuntu/apps/ph.silesia3d.site
   docker compose exec -T leady_v5 python narzedzia/baza.py backup --profil prod --trzymaj 30
   docker compose exec -T leady_v5 python narzedzia/baza.py lista
   docker compose exec -T leady_v5 python narzedzia/rspo.py <te same argumenty>
   docker compose exec -T leady_v5 python narzedzia/baza.py lista
   ```
6. **Po wszystkim** — `odswiez_demo.sh`, żeby demo znów było lustrem produkcji.

Jeśli poszerzenie bazy ma stać się czynnością comiesięczną koordynatorki
(a tak było planowane), to po tej rundzie `rspo.py` powinien dostać ekran
w panelu koordynatora — ale **osobną poprawką, po tej liście**, nie w środku niej.

---

## Etap H — typy kont i zmiany w schemacie

**Nowe kolumny są darmowe.** `db.migruj()` przy starcie dokłada do `placowki`,
`leady` i `eventy` kolumny, których nie ma. Dopisujesz klucz do `PLACOWKA_KEYS` /
`LEAD_KEYS` / `EVENT_KEYS` i po restarcie kolumna jest w obu bazach. Nic więcej
nie trzeba.

**Wszystko poza dokładaniem kolumn — nie.** Nowa tabela, zmiana znaczenia
istniejącego pola, przepisanie ról kont: to wymaga skryptu migracyjnego, który
1. jest **idempotentny** (drugie uruchomienie nic nie psuje),
2. wypisuje liczby przed i po,
3. przechodzi **najpierw na świeżej kopii produkcji na demo**,
4. na produkcji idzie po kopii, którą umiesz odtworzyć.

**Typy kont — o co konkretnie zapytać, zanim zaczniesz kodować.** Dziś osoba
będąca i handlowcem, i trenerem ma **dwa konta** (różne prefiksy w słownikach),
a wielorolowość rozwiązano dopiskiem w nazwie (`03. Małolepsza (koordynator)`).
Jest 49 kont z PIN-ami. Jeśli poprawki klienta zmieniają ten model, to jest
przebudowa, nie poprawka — i potrzebuje:
- **tabeli mapowania stare konto → nowe** (wypełnionej i zatwierdzonej przez Kasię),
- decyzji, **co się dzieje z PIN-ami** (PIN-ów nie da się odczytać — PBKDF2 z solą;
  scalenie dwóch kont w jedno oznacza, że jeden z dwóch PIN-ów przestaje działać
  i trzeba wydać nową kartę dostępu),
- wpisu w rejestrze jako osobny blok, nie jako „P23".

Testy do przepuszczenia po każdej zmianie ról: `test_logowanie.py`, `test_serwis.py`,
`test_trener.py`, `test_filtr_osob.py`. Uprawnienia siedzą w **trzech warstwach**
(`before_request`, sprawdzenie właściciela w endpoincie, interfejs) — ukrycie
przycisku nie jest zmianą uprawnień.

---

## Etap I — wejście na produkcję

```powershell
# 1. lokalnie: komplet testów jeszcze raz, na świeżej kopii produkcji
# 2. scalenie
git checkout main
git pull --ff-only
git merge --no-ff poprawki-2026-08 -m "Poprawki po testach klienta 20.08 (P01-Pnn)"
git tag v5.1-poprawki-2026-08
git push origin main --tags
```

```bash
# 3. na serwerze
cd /home/ubuntu/apps/ph.silesia3d.site
./wdroz.sh prod          # sam robi kopię PRZED aktualizacją i sprawdza, czy wstała
```

4. **Smoke test z telefonu, po LTE** (nie z komputera w biurze): logowanie PIN-em,
   formularz → zapis → czy lead jest w kalendarzu, jeden ekran z każdej roli.
5. **Odśwież demo** (`odswiez_demo.sh`), przełącz katalog demo z powrotem na `main`
   albo od razu na nową gałąź poprawek — demo znów jest lustrem produkcji.
6. Skasuj scaloną gałąź `poprawki-2026-08` lokalnie i na origin.

**Wycofanie, gdyby coś poszło nie tak:**

```bash
# kod — wracamy na tag sprzed poprawek
cd /home/ubuntu/apps/ph.silesia3d.site
git checkout przed-poprawkami-2026-08-20
docker compose up -d --build leady_v5

# dane — kopia z chwili przed wdrożeniem (wdroz.sh ją zrobił)
docker compose exec -T leady_v5 sh -lc 'ls -1t /data/kopie/prod_*.db | head -5'
docker compose stop leady_v5
docker compose run --rm --no-deps leady_v5 \
    sh -lc "rm -f /data/leady_v3.db-wal /data/leady_v3.db-shm && \
            python narzedzia/baza.py przywroc --profil prod --z /data/kopie/<plik>"
docker compose up -d leady_v5
```

Odtwarzanie bazy **było przećwiczone** na demo (545 → 0 → 545), więc to nie jest
teoria. Ale ćwiczone było na starym układzie — **przećwicz je raz na nowym demo
zaraz po Etapie E**, zanim będzie potrzebne naprawdę.

---

## Ryzyka i rzeczy, których nie robimy

| Nie robimy | Dlaczego |
|---|---|
| `COMPOSE_PROJECT_NAME` w `.env` produkcji | odczepi produkcję od jej wolumenu z danymi |
| `docker compose up -d` bez nazwy usługi | w katalogu demo dotknęłoby usługi produkcyjnej |
| `docker volume prune` przez najbliższe tygodnie | skasuje osierocony wolumen starego demo |
| kopiowanie bazy demo na produkcję | skasuje pracę handlowców z okresu testów |
| import przez ekran „Import" na produkcji | ten importer już raz wziął 165 placówek zamiast 545 |
| `PIN_SERWISOWY` na demo | po Etapie E demo ma prawdziwe dane osobowe |
| kopie `.db` w gicie | dane osobowe w historii, której git nie zapomina |
| długa gałąź ze wszystkim naraz | blokery utkną za kosmetyką; wypuszczaj je osobno |

Dwie rzeczy z `CLAUDE.md`, o które łatwo się potknąć przy pracy lokalnej:
Windows pozwala **dwóm procesom** słuchać na 5301 (stary serwer odpowiada
na przemian z nowym — „raz działa, raz nie"; PID przez
`netstat -ano | Select-String ":5301"`), a `pip` na tym komputerze celuje w innego
Pythona niż `python` (instalować przez `python -m pip`).

---

## Checklista startowa (do odhaczenia dziś)

- [ ] A. Meldunek z VPS wklejony i przeczytany (commit produkcji, wolumeny, nginx, auth do GitHuba)
- [ ] B. Lista klienta w `LISTA_POPRAWEK_szablon.md` → `docs/18_POPRAWKI_2026-08.md`, ID nadane, blokery oznaczone
- [ ] C. Tag `przed-poprawkami-2026-08-20`, gałąź `poprawki-2026-08` na origin
- [ ] C. Lokalny profil `test` zasiany świeżą kopią produkcji; komplet testów przechodzi PRZED pierwszą zmianą
- [ ] D. Katalog `demo-ph.silesia3d.site` stoi, własny `.env`, HTTP 200 na 5302
- [ ] E. `odswiez_demo.sh` w repo, uruchomiony, liczby na demo = liczby na produkcji
- [ ] E. Odtwarzanie z kopii przećwiczone na nowym demo
- [ ] F. Pierwsza runda poprawek na demo, klient ma listę ID do sprawdzenia
