# Wdrożenie

**Aktualna instrukcja: [`docs/15_DOMENA_I_WDROZENIE.md`](docs/15_DOMENA_I_WDROZENIE.md)**
— domena, DNS, nginx, certbot, kopie zapasowe i checklista do odhaczenia.

Ten plik opisywał wdrożenie **v3** (kontener `leady_v3`, port 5058, jedna usługa,
bez logowania). Zostawiony był jako punkt wyjścia, ale w v5 nie zgadza się już
nic poza adresem serwera: są dwie usługi (demo 5302 + produkcja 5301), sekrety
w `.env` i logowanie PIN-em. Trzymanie dwóch instrukcji równolegle skończyłoby
się tym, że w poniedziałek ktoś otworzy tę starszą.

Skrót dla niecierpliwych:

```bash
cp .env.example .env && nano .env && chmod 600 .env   # SECRET_KEY, PIN_KOORDYNATORA
./wdroz.sh demo                                        # demo idzie pierwsze
./wdroz.sh prod
```

Kolejność, której nie wolno odwrócić:

```
DNS → nslookup → kontener → nginx bez SSL → certbot → HTTPS=1 → restart
```
