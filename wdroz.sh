#!/usr/bin/env bash
#
# Wdrożenie nowej wersji na VPS: git pull + przebudowa + sprawdzenie, że wstała.
#
#     ./wdroz.sh              # demo (bezpieczne, tam próbujemy najpierw)
#     ./wdroz.sh prod         # produkcja
#
# Po co skrypt zamiast trzech poleceń z palca: bo za trzecim razem ktoś pominie
# sprawdzenie i zostawi na produkcji kontener, który się nie podniósł. Tu brak
# odpowiedzi z aplikacji kończy się czerwonym komunikatem i kodem błędu.
set -euo pipefail

CO="${1:-demo}"
case "$CO" in
    demo) USLUGA=leady_v5_demo; PORT=5302 ;;
    prod) USLUGA=leady_v5;      PORT=5301 ;;
    *) echo "Użycie: ./wdroz.sh [demo|prod]"; exit 2 ;;
esac

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "BŁĄD: brak pliku .env (SECRET_KEY, PIN_KOORDYNATORA)."
    echo "      cp .env.example .env && nano .env && chmod 600 .env"
    exit 1
fi

# Kopia PRZED aktualizacją, nie po. Jeśli nowa wersja zrobi coś złego danym,
# po jej starcie jest już za późno. Na demo pomijamy — tam nie ma czego żałować.
if [ "$CO" = "prod" ]; then
    echo "== kopia bazy przed aktualizacją =="
    docker compose exec -T "$USLUGA" python narzedzia/baza.py backup \
        --profil prod --trzymaj 30 || echo "UWAGA: kopia się nie udała (kontener nie działa?)"
fi

echo "== git pull =="
git pull --ff-only

echo "== przebudowa $USLUGA =="
docker compose up -d --build "$USLUGA"

echo "== czekam, aż aplikacja odpowie =="
for i in $(seq 1 20); do
    KOD=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/logowanie" || true)
    if [ "$KOD" = "200" ]; then
        echo "OK — $USLUGA odpowiada na porcie $PORT"
        exit 0
    fi
    sleep 1
done

echo "BŁĄD: $USLUGA nie odpowiada na porcie $PORT (ostatni kod: ${KOD:-brak})."
echo "      docker compose logs --tail 50 $USLUGA"
exit 1
