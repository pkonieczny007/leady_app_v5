# Wdrożenie — VPS `opxen.xyz`

Na serwerze działa już jedna aplikacja Flask (rozliczenia, port 5057).
Ta wchodzi obok jako osobny kontener na porcie **5058**, bez dotykania tamtej.

---

## 1. Kontener

```bash
scp -r leady_app_v3 user@opxen.xyz:~/
ssh user@opxen.xyz
cd ~/leady_app_v3
docker compose up -d --build
docker compose logs -f leady_v3          # kontrola startu
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5058/pulpit   # 200
```

Baza SQLite siedzi w wolumenie `leady_v3_data` (montowanym na `/data`),
więc `docker compose down` i przebudowa nie tracą danych.

## 2. nginx — subdomena

```nginx
server {
    listen 80;
    server_name leady3.opxen.xyz;

    client_max_body_size 32M;          # wgrywane pliki xlsx klienta mają ~5 MB

    location / {
        proxy_pass         http://127.0.0.1:5058;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;        # eksport większych zbiorów do XLSX
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d leady3.opxen.xyz
```

## 3. Wgranie danych

Prototyp startuje z pustą bazą i gotowymi słownikami. Dwie drogi:

**A. Przez przeglądarkę** — ekran „Import", wgraj `PH Nowy … .xlsx`,
źródło `ph_nowy`, tryb `merge`.

**B. Z pliku na serwerze** — skopiuj xlsx do wolumenu i zaimportuj:

```bash
docker cp "PH Nowy  Nad którym pracuję jako główny  .xlsx" leady_app_v3:/data/ph.xlsx
docker compose exec leady_v3 python -c \
  "import db,importer; c=db.get_conn(); print(importer.importuj_ph_nowy(c,'/data/ph.xlsx'))"
```

Przycisk „Wczytaj dane demo" szuka pliku pod ścieżką z `PLIK_PH_NOWY` —
w kontenerze ustaw ją na `/data/ph.xlsx`, jeśli chcesz go używać.

## 4. Kopia bazy

```bash
# backup
docker compose exec leady_v3 sh -c 'sqlite3 /data/leady_v3.db ".backup /data/kopia.db"' \
  || docker cp leady_app_v3:/data/leady_v3.db ./leady_v3_$(date +%F).db

# odtworzenie
docker cp ./leady_v3_2026-07-30.db leady_app_v3:/data/leady_v3.db
docker compose restart leady_v3
```

Warto wpisać w cron codzienny `docker cp` bazy na dysk hosta —
plik jest mały (przy 550 leadach rzędu kilku MB).

---

## Zanim to zobaczy ktoś poza wami — czego brakuje

Prototyp jest świadomie „goły". Do pokazu na spotkaniu to bez znaczenia,
ale **nie wystawiaj tego publicznie w tym stanie**:

| Brak | Konsekwencja | Minimum na produkcję |
|---|---|---|
| **Brak logowania** | każdy z linkiem widzi i edytuje wszystko, w tym telefony i maile dyrektorów szkół | choćby Basic Auth w nginx, docelowo logowanie + role |
| **Brak CSRF** | zapisy idą przez `fetch` bez tokenu | token w sesji + nagłówek |
| **Import w trybie `replace` czyści dane** | jedno kliknięcie kasuje bazę | potwierdzenie + kopia przed importem |
| **Dane osobowe** | telefony i maile osób decyzyjnych + informacje o dzieciach (liczba, potrzeby) — to RODO | zamknięty dostęp, świadoma decyzja o retencji |
| **SQLite + 2 workery gunicorna** | przy równoczesnych zapisach możliwe `database is locked` | włączyć WAL albo zejść do 1 workera |
| `debug=True` w `python app.py` | interaktywna konsola w przeglądarce przy błędzie | na serwerze uruchamiać tylko przez gunicorn (tak działa Dockerfile) |

Włączenie WAL (jednorazowo, poprawia współbieżność SQLite):

```bash
docker compose exec leady_v3 python -c \
  "import db; c=db.get_conn(); c.execute('PRAGMA journal_mode=WAL'); print(c.execute('PRAGMA journal_mode').fetchone()[0])"
```
