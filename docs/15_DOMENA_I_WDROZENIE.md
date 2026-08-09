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

## 8. Kopie zapasowe — cron o 6:00

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

```powershell
scp "ubuntu@57.128.241.52:~/apps/ph.silesia3d.site/kopie/*" C:\XEN\AI-szkolenie\SIERPIEN2026\kopie_vps\
```

Próbę **przywracania** trzeba przejść zanim ruszy produkcja (etap 9) — kopia,
której nigdy nie odtworzono, jest tylko nadzieją:

```bash
docker compose exec -T leady_v5_demo python narzedzia/baza.py przywroc \
  --profil test --z /data/kopie/test_2026-08-10_0600.db
```

## 9. Wdrożenie nowej wersji

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

**`docker compose exec` bez `-T` w cronie.** Patrz punkt 8.

**Kolejny błąd nginx kładzie cudze aplikacje.** Zawsze `nginx -t` przed `reload`.

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
