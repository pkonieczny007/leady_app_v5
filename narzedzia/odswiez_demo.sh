#!/usr/bin/env bash
#
# Odświeża bazę DEMO świeżą kopią PRODUKCJI. Uruchamiać w katalogu demo:
#
#     cd /home/ubuntu/apps/demo-ph.silesia3d.site && ./narzedzia/odswiez_demo.sh
#
# Po co skrypt zamiast pięciu poleceń z palca: pominięcie jednego kroku
# (plików -wal/-shm po starej bazie) daje bazę, która OTWIERA SIĘ POPRAWNIE
# i pokazuje nie te dane — czyli błąd, którego nie widać, dopóki ktoś nie
# zacznie się kłócić o liczby.
#
# Kierunek jest jednokierunkowy: PRODUKCJA -> DEMO. Nigdy odwrotnie. Produkcja
# pracuje cały czas, więc demo starzeje się od pierwszej minuty; wgranie go
# z powrotem skasowałoby to, co handlowcy wpisali w międzyczasie.
set -euo pipefail

PROD_KONTENER=leady_app_v5
DEMO_KONTENER=leady_app_v5_demo
DEMO_USLUGA=leady_v5_demo
PORT_DEMO=5302
PRZEJSCIOWY=$HOME/przenosiny-demo

cd "$(dirname "$0")/.."

# --- 0/6 bezpiecznik: czy na pewno jesteśmy w katalogu DEMO ---------------
# Usługa `leady_v5_demo` jest zdefiniowana w OBU katalogach (jedno wspólne
# docker-compose.yml w repozytorium). Odpalone z katalogu produkcyjnego to samo
# polecenie utworzyłoby DRUGI projekt compose z własnym, pustym wolumenem —
# demo "wyczyściłoby się" bez śladu, a prawdziwe dane zostałyby w sierocie.
if ! docker inspect "$DEMO_KONTENER" >/dev/null 2>&1; then
    echo "BŁĄD: nie ma kontenera $DEMO_KONTENER. Najpierw:  docker compose up -d --build $DEMO_USLUGA"
    exit 1
fi
KATALOG_DEMO=$(docker inspect "$DEMO_KONTENER" \
    --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')
if [ "$KATALOG_DEMO" != "$PWD" ]; then
    echo "BŁĄD: kontener $DEMO_KONTENER należy do katalogu:"
    echo "        $KATALOG_DEMO"
    echo "      a skrypt uruchomiono w:"
    echo "        $PWD"
    echo "      Uruchom go w katalogu demo."
    exit 1
fi

# Wolumen i obraz czytamy z żywego kontenera, a nie wpisujemy na sztywno:
# nazwa wolumenu bierze się z nazwy katalogu, więc każdy zapis na sztywno
# rozjedzie się przy pierwszej zmianie nazwy katalogu — i to po cichu.
WOLUMEN=$(docker inspect "$DEMO_KONTENER" \
    --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')
OBRAZ=$(docker inspect "$DEMO_KONTENER" --format '{{.Config.Image}}')
if [ -z "$WOLUMEN" ]; then
    echo "BŁĄD: kontener $DEMO_KONTENER nie ma wolumenu na /data."
    exit 1
fi
echo "demo: wolumen=$WOLUMEN obraz=$OBRAZ"

echo "== 1/6 świeża kopia produkcji =="
# docker exec po NAZWIE kontenera, nie docker compose — działa niezależnie od
# tego, w którym katalogu stoimy, i nie tworzy niczego w projekcie demo.
docker exec "$PROD_KONTENER" python narzedzia/baza.py backup --profil prod --bez-excela

echo "== 2/6 wyjmuję plik z kontenera produkcyjnego =="
rm -rf "$PRZEJSCIOWY"; mkdir -p "$PRZEJSCIOWY"; chmod 700 "$PRZEJSCIOWY"
PLIK=$(docker exec "$PROD_KONTENER" sh -lc 'ls -1t /data/kopie/prod_*.db | head -1' | tr -d '\r')
NAZWA=$(basename "$PLIK")
docker cp "${PROD_KONTENER}:${PLIK}" "$PRZEJSCIOWY/"
echo "   $NAZWA"

echo "== 3/6 zatrzymuję demo =="
# Aplikacja nie może trzymać pliku bazy otwartego w trakcie podmiany:
# gunicorn pisałby dalej do starego i-węzła, a my podmienialibyśmy nazwę.
docker compose stop "$DEMO_USLUGA"

echo "== 4/6 wstawiam bazę do demo =="
# Jednorazowy kontener na wolumenie podanym PO NAZWIE. Świadomie nie
# `docker compose run`: usługa ma ustawione container_name, a nazwa
# zatrzymanego kontenera jest wciąż zajęta — compose potrafi się o to wywalić
# w połowie podmiany.
# -wal/-shm to towarzysze STAREJ bazy; zostawione, dokleiłyby się do nowej.
docker run --rm \
    -e PROFIL=test \
    -v "$WOLUMEN":/data \
    -v "$PRZEJSCIOWY":/wejscie:ro \
    "$OBRAZ" \
    sh -lc "mkdir -p /data/kopie && cp /wejscie/$NAZWA /data/kopie/ && \
            rm -f /data/leady_v3.db-wal /data/leady_v3.db-shm && \
            python narzedzia/baza.py przywroc --profil test --z /data/kopie/$NAZWA"

echo "== 5/6 start demo =="
docker compose up -d "$DEMO_USLUGA"
KOD=""
for _ in $(seq 1 20); do
    KOD=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT_DEMO/logowanie" || true)
    [ "$KOD" = "200" ] && break
    sleep 1
done
echo "   HTTP: ${KOD:-brak}"

echo "== 6/6 liczby do porównania =="
# Wypisujemy OBIE strony obok siebie. Sam komunikat "gotowe" nic nie znaczy —
# dopiero zgodne liczby placówek i leadów mówią, że demo jest lustrem produkcji.
echo "-- produkcja --"
docker exec "$PROD_KONTENER" python narzedzia/baza.py lista
echo "-- demo --"
docker compose exec -T "$DEMO_USLUGA" python narzedzia/baza.py lista

# W tych plikach są telefony i maile dyrektorów szkół — nie zostają w katalogu
# domowym „na wszelki wypadek".
rm -rf "$PRZEJSCIOWY"

if [ "$KOD" != "200" ]; then
    echo "BŁĄD: demo nie odpowiada na porcie $PORT_DEMO. docker compose logs --tail 50 $DEMO_USLUGA"
    exit 1
fi
echo "== gotowe =="
