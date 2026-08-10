# 15. Domena i wdrożenie — krok po kroku

Instrukcja do **wykonania z palca**, nie do czytania. Pisana dlatego, że
podpinanie domeny robi się raz na rok i za każdym razem od nowa przypomina się,
co po czym idzie.

**Najważniejsza rzecz w całym dokumencie:** DNS propaguje się od kilkunastu minut
do kilku godzin, a `certbot` **odmówi wystawienia certyfikatu, dopóki domena nie
wskazuje na serwer** (Let's Encrypt sprawdza to, pukając z zewnątrz pod adres,
który właśnie certyfikujesz). Dlatego rekord DNS ustawiamy **jako pierwszą
czynność poniedziałku**, a resztę robimy, kiedy on się rozchodzi. Odwrócenie tej
kolejności to godzina czekania w środku dnia i błąd `Timeout during connect`,
który wygląda jak awaria, a jest tylko niecierpliwością.

---

## 0. Konkrety tego wdrożenia

| Rzecz | Wartość |
|---|---|
| VPS | `ubuntu@57.128.241.52` (OVH) |
| DNS domeny `silesia3d.site` | OVH — `ns10.ovh.net`, `dns10.ovh.net` |
| nginx | `nginx/1.26.3 (Ubuntu)`, działa |
| certbot | skonfigurowany, konto Let's Encrypt istnieje (`librus.silesia3d.site`, ważny do 24.10.2026) |
| gdzie mieszkają aplikacje | `/home/ubuntu/apps/<subdomena>/` — tak stoi librus |
| nasz katalog | `/home/ubuntu/apps/ph.silesia3d.site` |

### Nazwy subdomen

| | subdomena | port | profil bazy |
|---|---|---|---|
| demo | `demo-ph.silesia3d.site` | 5302 | `test` (realne dane, wolno psuć) |
| produkcja | `ph.silesia3d.site` | 5301 | `prod` |

Płaskie `demo-ph`, a nie `demo.ph` — w panelach DNS trzeci poziom bywa kłopotliwy,
a certyfikat i tak bierzemy osobny dla każdej nazwy.

**Demo idzie pierwsze i to nie jest formalność.** Na demo wolno wywalić kontener,
zresetować bazę i pomylić się w nginx. Kiedy ta sama ścieżka przejdzie drugi raz,
na produkcji nie ma już niespodzianek — a we wtorek rano nie ma czasu na
niespodzianki.

### Jak stoi librus — wzór do powtórzenia (sprawdzone 09.08)

| | |
|---|---|
| katalog | `/home/ubuntu/apps/librus.silesia3d.site` (etykieta compose `working_dir`) |
| kontener | `librus_raport_app`, gunicorn, port kontenera 5000 |
| port na hoście | `5100` |
| nginx | `proxy_pass http://127.0.0.1:5100`, blok w `sites-available` + dowiązanie w `sites-enabled` |
| certyfikat | Let's Encrypt, tylko dla `librus.silesia3d.site` |

Nasza aplikacja wchodzi w tę samą konwencję: `/home/ubuntu/apps/ph.silesia3d.site`.
**Jeden katalog obsługuje obie subdomeny**, bo to jedno `docker-compose.yml`
z dwiema usługami (`leady_v5` i `leady_v5_demo`) — ten sam kod, dwie bazy.
Osobny katalog na demo znaczyłby dwa klony repozytorium i pytanie „który jest
świeższy" przy każdej aktualizacji.

`5301` i `5302` są wolne — `ss -tlnp` nie pokazuje na nich niczego.

### ⚠️ Czego z librusa NIE kopiujemy

**Librus jest wystawiony na świat na porcie 5100, z pominięciem nginx.**
`docker ps` pokazuje `0.0.0.0:5100->5000/tcp`, a z zewnątrz
`http://57.128.241.52:5100/` odpowiada `200` od gunicorna — **czystym HTTP,
bez certyfikatu**, mimo że `https://librus.silesia3d.site` działa poprawnie.
Ktoś, kto zna adres IP, omija HTTPS jednym numerem portu.

Tak działa docker: `ports: - "5100:5000"` bez adresu z przodu otwiera port na
wszystkich interfejsach i **wpisuje regułę wprost do iptables, z pominięciem
`ufw`** — firewall pokazuje wtedy, że wszystko jest zamknięte, a port stoi
otworem. To jedna z tych rzeczy, które wyglądają na skonfigurowane i nie są.

Dlatego nasz `docker-compose.yml` publikuje porty jako `127.0.0.1:5301`
i `127.0.0.1:5302` — aplikacja jest dostępna **wyłącznie przez nginx**.
U nas w bazie są telefony i maile dyrektorów szkół; wystawienie tego po HTTP
to nie jest usterka kosmetyczna.

Sprawdzenie po starcie: `docker ps` ma pokazywać `127.0.0.1:5301->`, nie `0.0.0.0:`.

W librusie poprawka to jedna linia w jego `docker-compose.yml`
(`"127.0.0.1:5100:5000"`) i `docker compose up -d` — ale to osobna aplikacja
i osobna decyzja, nie ruszamy jej przy okazji naszego wdrożenia.

---

## 1. DNS w OVH — rób to najpierw, o poranku

**OVH Manager → Web Cloud → Domeny → `silesia3d.site` → zakładka „Strefa DNS"
→ Dodaj wpis → typ `A`.** Dwa razy:

| Pole w formularzu OVH | Wpis 1 | Wpis 2 |
|---|---|---|
| Subdomena | `ph` | `demo-ph` |
| TTL | `1 minuta` (albo `Domyślny`) | `1 minuta` |
| Cel | `57.128.241.52` | `57.128.241.52` |

Uwagi, na których łatwo się przewrócić:

- **W polu „Subdomena" wpisuje się samo `ph`, bez domeny.** OVH dokleja
  `.silesia3d.site` sam i pokazuje pod spodem podgląd pełnej nazwy — przeczytaj
  go, zanim klikniesz „Dalej". Wpisanie pełnej nazwy daje
  `ph.silesia3d.site.silesia3d.site`, a `nslookup` powie wtedy „nie ma takiej
  domeny" i będziesz sprawdzał IP zamiast literówki.
- **Nie ruszaj rekordu głównego** — `silesia3d.site` wskazuje na `213.186.33.5`
  (hosting OVH) i tak ma zostać. Dodajemy subdomeny, nie zmieniamy strony.
- **Bez CNAME.** CNAME ma sens, gdy celujesz w cudzą nazwę, która może zmienić IP.
  Tu celujemy we własny serwer o stałym adresie — `A` jest prostsze i o jedno
  zapytanie szybsze.
- **`AAAA` (IPv6) na razie pomijamy.** VPS-y OVH mają IPv6, ale rekord `AAAA`
  wskazujący adres, na którym nginx nie nasłuchuje, daje najbardziej mylący
  możliwy objaw: z biura po wifi działa, a **z telefonu po LTE „nie można
  połączyć"** — bo komórka woli IPv6. Handlowcy pracują właśnie z telefonów.
  Sam IPv4 działa wszędzie; IPv6 można dodać spokojnie po wtorku.
- **Niski TTL na czas wdrożenia.** Jeśli pomylisz IP, przy TTL 3600 czekasz
  godzinę na poprawkę. Po wdrożeniu można podnieść.

OVH pokazuje po zapisaniu komunikat, że zmiany w strefie wchodzą w życie do
**24 godzin**. W praktyce przy TTL 60 s subdomena wstaje w kilka–kilkanaście
minut, bo to nowa nazwa — nic nie musi wygasnąć z cache'u.

## 2. Sprawdź, czy DNS już działa (zanim ruszysz cokolwiek dalej)

```powershell
nslookup ph.silesia3d.site 8.8.8.8
nslookup demo-ph.silesia3d.site 8.8.8.8
```

Pytamy wprost serwera Google (`8.8.8.8`), bo domowy router lubi zapamiętać
odpowiedź „nie ma takiej domeny" i potem uparcie ją powtarzać.

Ma zwrócić **`57.128.241.52`**. Dopóki zwraca „Non-existent domain" — nie ma sensu
iść dalej, `certbot` i tak odmówi.

Z serwera to samo z drugiej strony (tu liczy się to, co widzi Let's Encrypt):

```bash
dig +short ph.silesia3d.site demo-ph.silesia3d.site
```

**Dopiero gdy oba adresy odpowiadają poprawnie, przechodź dalej.** W międzyczasie
możesz robić punkty 3 i 4 — nie wymagają DNS-u.

---

## 3. Kod i sekrety na serwerze

```bash
ssh ubuntu@57.128.241.52
cd ~/apps
git clone https://github.com/pkonieczny007/leady_app_v5.git ph.silesia3d.site
cd ph.silesia3d.site
```

Katalog nazwany subdomeną, bo tak stoi librus i tak łatwiej po miesiącach
znaleźć, co obsługuje daną nazwę.

Repozytorium jest prywatne — jeśli `clone` pyta o hasło, użyj tokenu z GitHuba
albo klucza SSH (`gh auth login` na serwerze też załatwia sprawę).

### Plik `.env` — trzy rzeczy, bez których nie wolno tego wystawić

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

| Zmienna | Domyślnie w kodzie | Dlaczego to blokada wdrożenia |
|---|---|---|
| `SECRET_KEY` | `leady-v3-demo` | Wartość leży **w repozytorium na GitHubie**. Kto ją zna, podpisze sobie ciastko sesji koordynatora i wejdzie bez PIN-u. |
| `PIN_KOORDYNATORA` | `0000` | PIN startowy konta z pełnymi uprawnieniami. |
| `PIN_SERWISOWY` | (brak) | **Nie ustawiaj.** Jeden PIN wpuszcza bez wyboru osoby, na uprawnienia koordynatora — to klucz uniwersalny do bazy z telefonami dyrektorów. Na profilu `prod` kod wymaga dodatkowo `PIN_SERWISOWY_PROD=tak`, więc przypadkiem się nie włączy; ale świadomie też nie. |

Nowy `SECRET_KEY` wygeneruj **na serwerze**, żeby nigdzie nie przeszedł przez
schowek ani historię poleceń na Twoim komputerze:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

PIN koordynatora **wpisz w edytorze**, nie poleceniem w konsoli — polecenie
z PIN-em zostaje w `~/.bash_history` i w logu narzędzi.

Po pierwszym starcie i tak zmień PIN w panelu `/uzytkownicy`; dopóki jest
startowy, aplikacja krzyczy o tym czerwoną ramką.

## 4. Kontenery — najpierw demo

```bash
docker compose up -d --build leady_v5_demo
docker compose logs -f leady_v5_demo          # Ctrl+C wychodzi z podglądu
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5302/logowanie   # 200
```

`200` z `curl` na `127.0.0.1` znaczy, że aplikacja żyje — jeszcze bez nginx,
bez domeny i bez HTTPS. To dobry moment, żeby się zatrzymać: jeśli tu nie ma
`200`, żadna konfiguracja domeny tego nie naprawi.

Produkcję stawia się tym samym poleceniem, ale **dopiero po demo**:

```bash
docker compose up -d --build leady_v5
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5301/logowanie
```

Baza siedzi w wolumenie dockera (`leady_v5_data` / `leady_v5_demo_data`), osobnym
dla każdej usługi — `docker compose build` i restart jej nie ruszają. **Ale
`docker compose down -v` kasuje wolumeny.** Nigdy nie dopisuj `-v` odruchowo.

## 5. nginx — subdomena bez SSL

Plik `/etc/nginx/sites-available/ph.silesia3d.site`:

```nginx
server {
    listen 80;
    server_name ph.silesia3d.site;

    # xlsx klienta ma ~5 MB, domyślny limit nginx to 1 MB — bez tego import
    # kończy się błędem 413, który w przeglądarce wygląda jak zawieszenie.
    client_max_body_size 32M;

    location / {
        proxy_pass         http://127.0.0.1:5301;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        # eksport większych zbiorów do XLSX bywa wolny; tyle samo ma gunicorn
        proxy_read_timeout 180s;
    }
}
```

Drugi plik, `demo-ph.silesia3d.site`, jest identyczny z dwoma zmianami:
`server_name` i `proxy_pass` na port **5302**.

```bash
sudo ln -s /etc/nginx/sites-available/ph.silesia3d.site      /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/demo-ph.silesia3d.site /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t` przed każdym `reload` — literówka w konfiguracji potrafi położyć
**wszystkie** aplikacje na serwerze, także rozliczenia, których nie ruszałeś.

Co robią te nagłówki: `X-Forwarded-Proto` mówi aplikacji, że pierwotne żądanie
przyszło po HTTPS, mimo że do kontenera trafia zwykłym HTTP. Aplikacja **dziś go
nie czyta** — o ciastku `Secure` decyduje zmienna `HTTPS` (punkt 7) — ale nagłówki
ustawiamy od razu, bo bez `X-Real-IP` w logach zobaczysz wyłącznie `127.0.0.1`
i nie odróżnisz handlowca od bota.

## 6. certbot — HTTPS

**Osobno dla każdej subdomeny**, nie jednym poleceniem z dwoma `-d`. Powód
praktyczny: jeśli DNS jednej jeszcze się nie rozszedł, wspólne polecenie
wywala się w całości i nie dostajesz żadnego certyfikatu.

```bash
sudo certbot --nginx -d demo-ph.silesia3d.site
sudo certbot --nginx -d ph.silesia3d.site
```

Certbot sam dopisze do plików nginx sekcję `listen 443 ssl`, ścieżki do
certyfikatów i przekierowanie z `http` na `https` (na pytanie o redirect
odpowiedz **tak**). Nie edytuj tych dopisanych linii ręcznie — przy odnowieniu
i tak zostaną nadpisane.

Sprawdź, że odnawianie jest włączone — certyfikat żyje 90 dni i nikt o nim nie
pamięta w listopadzie:

```bash
systemctl list-timers | grep certbot     # ma być wpis z datą następnego uruchomienia
sudo certbot renew --dry-run             # próba na sucho, bez zużywania limitów
```

## 7. Dopiero teraz `HTTPS=1`

W `.env` dopisz `HTTPS=1` i zrestartuj:

```bash
docker compose up -d leady_v5 leady_v5_demo
```

Ta zmienna włącza flagę `Secure` na ciastku sesji — przeglądarka przestaje je
wysyłać po zwykłym HTTP. **Dlatego ustawia się ją po certyfikacie, nie przed:**
włączona na serwerze bez HTTPS oznacza „logowanie nie działa, wraca na ekran
logowania w kółko" i szukanie błędu w kodzie logowania, w którym go nie ma.

Kolejność w jednej linii, do zapamiętania:

```
DNS → nslookup → kontener → nginx bez SSL → certbot → HTTPS=1 → restart
```

## 8. Dane produkcyjne — przygotuj LOKALNIE, wgraj gotowe

Kuszące jest wejść na ekran „Import" na produkcji i wgrać tam plik klienta.
Nie rób tego. Import z pliku Excela klienta to operacja, która **już raz nas
zaskoczyła** — importer brał 165 placówek zamiast 545, bo zakładka zmieniła
nazwę. Gdyby to wyszło na serwerze we wtorek rano, poprawiasz kod na produkcji,
przy ludziach czekających na dane.

Kolejność odwrotna kosztuje tyle samo, a jest powtarzalna:

```powershell
# 1. u siebie: świeży profil prod z pliku klienta
python narzedzia/baza.py nowa --profil prod --z-pliku "C:\XEN\AI-szkolenie\SIERPIEN2026\8.08.2026-home\PH PRÓBA Nowy dla handlowców.xlsx"

# 2. rejony trenerów (tabela `rejony` po samym imporcie jest PUSTA,
#    a bez niej podpowiedź „jeździ tu" milczy)
python narzedzia/trenerzy.py rejony --plik "…\PH PRÓBA Nowy dla handlowców.xlsx" --zapisz --profil prod

# 3. sprawdź liczby ZANIM cokolwiek pojedzie na serwer
python narzedzia/baza.py lista          # ma być 545 placówek

# 4. czysta kopia do wysłania
python narzedzia/baza.py backup --profil prod --bez-excela
scp kopie\prod_*.db ubuntu@57.128.241.52:/tmp/
```

Na serwerze:

```bash
cd ~/apps/ph.silesia3d.site
docker compose stop leady_v5
docker compose run --rm leady_v5 sh -c \
  'cp /tmp/prod_*.db /data/leady_v3.db && rm -f /data/leady_v3.db-wal /data/leady_v3.db-shm'
docker compose start leady_v5
docker compose exec leady_v5 python narzedzia/konto.py ustaw \
  --osoba Koordynator --rola koordynator --pin losowy --profil prod
```

`docker compose run` nie publikuje portów, więc nie wchodzi w drogę działającej
usłudze. PIN-y dla reszty zespołu — `narzedzia/karta_dostepu.py`, wydruk na
wtorek.

### Trzy stany na demo — jeden adres, przełącznik

Klient chce zobaczyć aplikację świeżo postawioną, z danymi do prób i z kompletem
danych. To trzy **stany** jednej instalacji, nie trzy instalacje — trzy adresy
znaczyłyby trzy certyfikaty, trzy kontenery do aktualizowania i trzy podobne
adresy, w które ktoś może wpisać realną pracę nie tam, gdzie trzeba.

```bash
./stan.sh zapisz pelna     # bieżący stan zachowaj jako wzorzec
./stan.sh pusta            # stan startowy: baza budowana od zera
./stan.sh wgraj pelna      # powrót do danych
./stan.sh lista            # co jest przygotowane + liczby bieżącego stanu
```

Skrypt **działa wyłącznie na demo** i przed każdą podmianą robi kopię bieżącego
stanu. Produkcji celowo nie dotyka: „wgraj wzorzec" pomylone o jedną literę
kasowałoby pracę handlowców.

## 9. Kopie zapasowe — cron o 6:00

```bash
crontab -e
```

```cron
0 6 * * * cd /home/ubuntu/apps/ph.silesia3d.site && docker compose exec -T leady_v5 \
  python narzedzia/baza.py backup --profil prod --trzymaj 30 >> /var/log/leady_backup.log 2>&1
```

`-T` jest konieczne: bez niego `docker compose exec` chce terminala, a cron go nie
ma — zadanie kończy się cicho błędem i przez tydzień nikt nie zauważy, że kopii
nie ma. Kopie lądują w `/data/kopie` **w wolumenie**, więc przeżywają przebudowę
kontenera.

Retencja 30 dni z zachowaniem wszystkich poniedziałkowych (tak działa
`--trzymaj`) — kopia sprzed miesiąca przydaje się rzadko, ale kiedy się przyda,
to bardzo.

**Ściągaj kopie z serwera raz w tygodniu na swój dysk.** Serwer może paść
w całości razem z wolumenem; kopia leżąca obok oryginału to nie jest kopia.

**Dwa kroki, nie jeden — i to nie jest niepotrzebna ceremonia.** Kopie leżą
w wolumenie dockera (`/var/lib/docker/volumes/…`), a ten katalog ma prawa
`drwx--x---` i należy do `root`. Użytkownik `ubuntu` — czyli także `scp`
i eksplorator plików w VS Code — dostaje tam „Permission denied". Trzeba
najpierw wyłożyć pliki tam, gdzie sięga, dopiero potem je ściągać:

```bash
# 1. na serwerze — wyjmij kopie z wolumenu
mkdir -p ~/kopie-vps && docker cp leady_app_v5:/data/kopie/. ~/kopie-vps/
rm -f ~/kopie-vps/*.db-shm ~/kopie-vps/*.db-wal     # pliki towarzyszące SQLite, tylko mylą
chmod 700 ~/kopie-vps && chmod 600 ~/kopie-vps/*
ls -lh ~/kopie-vps
```

```powershell
# 2. u siebie — dopiero teraz scp cokolwiek zobaczy
scp "ubuntu@57.128.241.52:~/kopie-vps/*" C:\XEN\AI-szkolenie\SIERPIEN2026\kopie_vps\
```

```bash
# 3. na serwerze — sprzątnij, to są telefony i maile dyrektorów oraz skróty PIN-ów
rm -rf ~/kopie-vps
```

⚠️ **Poprzednia wersja tej instrukcji celowała w `~/apps/ph.silesia3d.site/kopie/`
i była błędna** — tego katalogu nie ma, kopie idą do wolumenu. `scp` zwracał
„No such file or directory" i nie ściągał nic. Gdyby ktoś odhaczał cotygodniowe
ściąganie bez patrzenia na wynik, przez miesiąc byłby przekonany, że ma kopie
u siebie. Znalezione 10.08 przy pierwszym realnym użyciu.

**Po wtorku warto to uprościć**: podmontować `./kopie` z katalogu aplikacji na
`/data/kopie` w kontenerze (bind mount obok wolumenu). Kopie lądowałyby wtedy
wprost w `~/apps/ph.silesia3d.site/kopie/`, czytelne dla `ubuntu` i dla VS Code,
a `scp` byłby jednym poleceniem. Nie robimy tego przed startem — zmiana dotyka
`docker-compose.yml` produkcji, a zysk jest wygodowy, nie krytyczny.

Próbę **przywracania** trzeba przejść zanim ruszy produkcja (etap 9) — kopia,
której nigdy nie odtworzono, jest tylko nadzieją:

```bash
docker compose exec -T leady_v5_demo python narzedzia/baza.py przywroc \
  --profil test --z /data/kopie/test_2026-08-10_0600.db
```

## 9b. Kopie poza serwerem — Mac mini (do zrobienia po wtorku)

Kopia leżąca na tym samym serwerze co oryginał **nie jest kopią zapasową** —
jest zabezpieczeniem przed pomyłką człowieka, nie przed awarią maszyny. Reguła,
którą chcemy osiągnąć, to 3-2-1: trzy kopie, dwa różne nośniki, jedna poza
budynkiem.

| gdzie | co | jak często | stan |
|---|---|---|---|
| VPS, wolumen dockera | `.db` + `.xlsx` | 6:00 codziennie | ✅ działa |
| Mac mini w biurze (Debian) | to samo, ściągane | 6:30 codziennie | ⬜ |
| dysk Przemka / zewnętrzny | co jakiś czas | ręcznie | ⬜ |

### Dlaczego Mac CIĄGNIE, a serwer nie PCHA

To nie jest szczegół techniczny. Gdyby VPS został przejęty, atakujący ma dostęp
do wszystkiego, co ten serwer potrafi dosięgnąć — przy pchaniu skasowałby także
kopie na Macu. Przy ciąganiu serwer nie zna żadnych danych logowania do Maca
i nie ma jak tam sięgnąć. Klucz SSH idzie **z Maca na serwer**, nigdy odwrotnie.

### Nasza aplikacja

Gotowy skrypt: **`narzedzia/kopia_na_maca.sh`**. Maszyna to Mac mini, ale system
to **Debian** — więc zwykły bash, `rsync`, `ssh` i `systemd`, bez niczego
apple'owego.

```bash
# 0. czego brakuje na świeżym Debianie
sudo apt install rsync sqlite3 git

# 1. klucz SSH: Z MACA NA SERWER, nigdy odwrotnie
#    -N '' czyli BEZ hasła do klucza — inaczej timer stanie i będzie czekał,
#    aż ktoś je wpisze, a nie ma komu. Klucz chroni wtedy uprawnieniami pliku.
ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519 -C "mac-mini kopie"
ssh-copy-id ubuntu@57.128.241.52
ssh -o BatchMode=yes ubuntu@57.128.241.52 echo ok     # ma odpowiedzieć „ok" bez pytania o hasło

# 2. skrypt na miejsce (repozytorium jest prywatne, więc przez klon albo scp)
git clone https://github.com/pkonieczny007/leady_app_v5.git ~/src/leady_app_v5
mkdir -p ~/bin ~/Backups/leady
cp ~/src/leady_app_v5/narzedzia/kopia_na_maca.sh ~/bin/
chmod +x ~/bin/kopia_na_maca.sh
~/bin/kopia_na_maca.sh --librus --kod                 # pierwsze uruchomienie z ręki
```

`sqlite3` nie jest na Debianie domyślnie, a bez niego skrypt **ściągnie kopie,
ale ich nie sprawdzi** — powie o tym wprost w logu. Niesprawdzona kopia to kopia,
w którą się wierzy, a nie taka, o której się wie.

### Uruchamianie automatyczne: timer systemd, nie cron

Mówisz, że maszyna chodzi ciągle i ma UPS — mimo to **nie cron**. Cron nie
nadrabia pominiętych uruchomień: wystarczy restart po aktualizacji jądra
o niewłaściwej porze i kopia z tego dnia przepada bez śladu. Timer systemd
z `Persistent=true` uruchomi zaległe zadanie przy najbliższym starcie.

`~/.config/systemd/user/kopia-leady.service`:

```ini
[Unit]
Description=Kopia bazy leadów z VPS

[Service]
Type=oneshot
ExecStart=%h/bin/kopia_na_maca.sh --librus --kod
```

`~/.config/systemd/user/kopia-leady.timer`:

```ini
[Unit]
Description=Codzienna kopia bazy leadów

[Timer]
OnCalendar=*-*-* 06:30:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now kopia-leady.timer
sudo loginctl enable-linger $USER      # bez tego timer stoi, dopóki się nie zalogujesz
systemctl --user start kopia-leady     # próba od razu, nie czekając do 6:30
```

`loginctl enable-linger` jest **konieczne**: usługi użytkownika bez tego działają
tylko, gdy ktoś jest zalogowany, a serwer kopii ma pracować sam. To najczęstszy
powód, dla którego „timer jest włączony, a nic się nie dzieje".

Podgląd:

```bash
systemctl --user list-timers kopia-leady    # kiedy następne, kiedy ostatnie
journalctl --user -u kopia-leady -n 30      # co się działo
```

### Jak sprawdzić, że warstwa awaryjna żyje

Skrypt zapisuje `~/Backups/leady/OSTATNIA_UDANA.txt` z datą ostatniego udanego
przebiegu i dopisuje wszystko do `~/Backups/leady/kopia.log`. **To nie jest
ozdoba** — maszyna, która nie robi kopii, wygląda dokładnie tak samo jak ta,
która je robi. Skoro deklarujesz codzienne zaglądanie, to są dwie komendy:

```bash
cat ~/Backups/leady/OSTATNIA_UDANA.txt
tail -20 ~/Backups/leady/kopia.log
```

Brak sieci albo wyłączony serwer to dla skryptu **nie jest błąd** — wpisuje
„POMINIETE" do logu i kończy się spokojnie, żeby `systemctl --user status` nie
świecił się na czerwono po każdym przebiegu bez łączności.

⚠️ Przy pierwszym uruchomieniu „POMINIETE" najczęściej znaczy **brak klucza SSH**,
nie problem z serwerem — `ssh-copy-id` mówi wtedy „No identities found", co brzmi
myląco. Skrypt sam to rozpoznaje i dopisuje do logu, co zrobić.

### Uruchomienie z ręki, obok automatu

```bash
~/bin/kopia_na_maca.sh --cel ~/kopia_reczna_vps --librus --kod
```

Automat pisze do `~/Backups/leady`, `--cel` pozwala zrzucić komplet gdzie indziej,
nie mieszając w tym, co pilnuje timer. Każdy katalog dostaje własny `kopia.log`,
własny `OSTATNIA_UDANA.txt` i własne lustro repozytorium — dzięki temu data
w katalogu automatu zawsze mówi prawdę o automacie, a nie o Twoim ostatnim
ręcznym uruchomieniu.

Kopie NIE są kasowane po stronie Maca (`rsync` bez `--delete`). Na serwerze
retencja usuwa je po 30 dniach; tutaj chcemy trzymać dłużej, inaczej lustro
skasowałoby to samo co serwer i cała warstwa straciłaby sens.

**Mac chodzi ciągle i ma UPS, ale i tak zakładamy, że bywa niedostępny** — to warstwa awaryjna, nie
podstawowa. Cron po prostu nie odpali się tego dnia, próbuje przy każdym
kolejnym. Ale jest w tym pułapka: **wyłączony Mac nie zgłasza błędu**. Jeśli
przestanie się budzić na miesiąc, nic o tym nie powie, a Ty będziesz przekonany,
że masz kopie. Jedyną obroną jest patrzenie na DATĘ najnowszego pliku —
`narzedzia\kopia_z_serwera.ps1` wypisuje ją przy każdym uruchomieniu i krzyczy,
gdy przekroczy tydzień.

### Ręcznie, z komputera Przemka

```powershell
.\narzedzia\kopia_z_serwera.ps1              # sama baza
.\narzedzia\kopia_z_serwera.ps1 -Librus -Kod # plus librus i lustro repozytorium
```

Skrypt wykłada kopie z wolumenu, ściąga je do `kopie_vps\<data>\`, sprząta
katalog przejściowy na serwerze i **sprawdza, czy pobrane bazy dają się otworzyć**
(`PRAGMA integrity_check` plus liczba placówek). Sam fakt, że plik ma poprawną
nazwę i rozmiar, nie znaczy nic — kopia jest kopią dopiero wtedy, gdy da się
z niej policzyć rekordy.

Po zrobieniu bind mountu `./kopie` (patrz punkt 9) całość upraszcza się do
samego `rsync` — `docker cp` i sprzątanie znikają.

### Librus — ta sama maszyna, to samo ryzyko

`librus.silesia3d.site` stoi na tym samym VPS-ie i dziś **nie ma żadnej kopii,
o której byśmy wiedzieli**. Jeśli serwer padnie, przepada razem z naszą bazą.
Nie jest to nasza aplikacja, więc niczego w niej nie zmieniamy — ale kopia
wolumenu jest operacją wyłącznie do odczytu i nie wymaga wchodzenia w jej kod.

Najpierw rozpoznanie, bo nie wiemy, co i gdzie ta aplikacja trzyma:

```bash
docker inspect librus_raport_app \
  --format '{{range .Mounts}}{{.Type}} {{.Name}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

Potem zrzut wolumenu przez jednorazowy kontener (działa niezależnie od tego,
co jest w środku — to kopia na poziomie plików):

```bash
docker run --rm -v <NAZWA_WOLUMENU>:/v -v ~/kopie-vps:/out alpine \
  tar czf /out/librus_$(date +%F).tar.gz -C /v .
```

⚠️ **Zastrzeżenie, którego nie wolno pominąć:** kopia na poziomie plików
z DZIAŁAJĄCEJ bazy potrafi złapać stan niespójny — w połowie zapisu. U nas
`baza.py` używa `sqlite .backup`, który jest na to odporny; przy librusie nie
wiemy, czym jest jego baza. Jeśli to SQLite, właściwym rozwiązaniem jest ten sam
mechanizm; jeśli Postgres — `pg_dump`. Dopóki tego nie ustalimy, tar jest lepszy
niż nic, ale **nie należy go nazywać sprawdzoną kopią**, dopóki raz nie odtworzymy
z niego działającej aplikacji.

### Kopia awaryjna KODU

Kod ma główną kopię na GitHubie (repozytorium prywatne) i to jest właściwe
miejsce. Na Macu robimy **lustro**, nie zwykły klon — z gałęziami, tagami
i całą historią:

```bash
git clone --mirror https://github.com/pkonieczny007/leady_app_v5.git ~/Backups/leady_app_v5.git
cd ~/Backups/leady_app_v5.git && git remote update --prune     # z crona, raz w tygodniu
```

### Czego NIE wkładamy na GitHub

**Kopii bazy.** Trzy powody, każdy wystarczający: (1) w środku są telefony
i maile dyrektorów szkół, a git **nigdy nie zapomina** — skasowanie pliku nie
usuwa go z historii, więc żądanie usunięcia danych wymagałoby przepisania całego
repozytorium; (2) `.db` to binarium, którego git nie różnicuje — każda dzienna
kopia to 450 kB na zawsze, po roku 160 MB nieusuwalnych blobów; (3) kto dostanie
dostęp do repozytorium, dostaje wszystkie dane historyczne. Kopia bazy ma być
plikiem, który da się skasować; kod ma mieć historię. To dwie różne rzeczy.

### Luka, o której się zapomina

**`.env` nie jest w gicie i nie będzie** — siedzą w nim `SECRET_KEY` i PIN
koordynatora. Mając kopię kodu i kopię danych, wciąż **nie mamy kopii
konfiguracji**. Nie kładziemy jej na dysku obok kopii; zawartość `.env` wpisujemy
do menedżera haseł. To jedyne miejsce zrobione do trzymania takich rzeczy.

## 10. Wdrożenie nowej wersji

```bash
cd ~/apps/ph.silesia3d.site && ./wdroz.sh
```

Skrypt robi `git pull`, przebudowę i sprawdzenie, czy aplikacja wstała. Wchodzi
razem z etapem 10.

---

## Grabie

**„Za mało nie działa, za dużo działa" przy DNS.** Rekord z nazwą wpisaną
w pełnej formie tam, gdzie panel dokleja domenę, daje
`ph.silesia3d.site.silesia3d.site` — nazwa istnieje, tylko nie ta.
`nslookup` powie „Non-existent domain", a Ty będziesz sprawdzał IP.

**Certbot przed DNS-em.** Objaw: `Timeout during connect (likely firewall
problem)`. Firewall nie ma z tym nic wspólnego — Let's Encrypt po prostu nie ma
gdzie zapukać. Poczekaj i powtórz. Uwaga: **5 nieudanych prób na godzinę dla tej
samej nazwy blokuje ją na godzinę**, więc nie da się tego „przeklikać".

**Port 80 musi zostać otwarty także po włączeniu HTTPS.** Odnowienie certyfikatu
idzie po HTTP. Zamknięcie „bo mamy już HTTPS" oznacza wygaśnięcie za 90 dni
i awarię w listopadzie, po której nikt nie pamięta tej decyzji.

**`HTTPS=1` bez certyfikatu = logowanie w pętli.** Patrz punkt 7.

**`docker compose down -v` kasuje bazę.** Bez `-v` kontener można wywalać do woli.

**`DATA_DIR` w compose wygrywa z `PROFIL`.** Aplikacja siada wtedy wprost na
`/data`, a nie na `/data/<profil>`. Dlatego demo i produkcja **muszą mieć osobne
wolumeny** — inaczej dwie usługi z różnym `PROFIL` pisałyby do jednego pliku,
a kolorowy pasek u góry ekranu kłamałby, że to różne bazy. W `docker-compose.yml`
jest to już rozdzielone; nie scalaj tych wolumenów.

**`docker compose exec` bez `-T` w cronie.** Patrz punkt 9.

**Kolejny błąd nginx kładzie cudze aplikacje.** Zawsze `nginx -t` przed `reload`.

**Do wolumenu dockera nie zajrzysz jako `ubuntu`.** `/var/lib/docker` ma prawa
`drwx--x---` i należy do `root`, więc ani `scp`, ani eksplorator plików w VS Code
nic tam nie zobaczą — a komunikat („Permission denied", „No such file") łatwo
wziąć za „nie ma kopii". Pliki są; trzeba je wyłożyć przez `docker cp`. Patrz
punkt 9.

**`grep -r` nie wchodzi w dowiązania.** `sites-enabled` to same dowiązania do
`sites-available`, więc `grep -rn "librus" /etc/nginx/sites-enabled/` nic nie
znajduje, choć konfiguracja tam jest — wygląda to jak „nie ma takiego pliku".
Szukaj przez `sudo nginx -T` (wypisuje konfigurację, która naprawdę działa)
albo `grep -Rn` z wielkim `R`.

**Port publikowany bez `127.0.0.1` omija ufw.** Patrz sekcja o librusie —
to nie teoria, tak stoi sąsiednia aplikacja na tym serwerze.

---

## Checklista poniedziałku

- [ ] w OVH rekordy `A`: `ph` i `demo-ph` → `57.128.241.52`
- [ ] `nslookup … 8.8.8.8` obu nazw zwraca `57.128.241.52`
- [ ] `git clone` na serwerze, `.env` z własnym `SECRET_KEY` i `PIN_KOORDYNATORA`
- [ ] `PIN_SERWISOWY` **nie występuje** w `.env` ani w środowisku
- [ ] demo wstaje, `curl` na 5302 daje 200
- [ ] `docker ps` pokazuje porty jako `127.0.0.1:5301->` i `127.0.0.1:5302->`,
      a nie `0.0.0.0:` — inaczej aplikacja stoi w internecie bez HTTPS
- [ ] nginx dla obu subdomen, `nginx -t` czysty
- [ ] `certbot` osobno dla demo i produkcji, `renew --dry-run` przechodzi
- [ ] `HTTPS=1` dopisane, kontenery zrestartowane
- [ ] logowanie z telefonu **po LTE**, nie z biurowego wifi
- [ ] cron 6:00 + jedno uruchomienie z ręki, żeby zobaczyć, że kopia powstała
- [ ] próba przywrócenia kopii na demo
- [ ] produkcja: import realnych danych, przejście ścieżki handlowca z telefonu
