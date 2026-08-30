#!/usr/bin/env bash
#
# Migracja bazy PRODUKCYJNEJ na rejestr RSPO.
#
#     cd /home/ubuntu/apps/ph.silesia3d.site
#     ./narzedzia/migracja_na_produkcje.sh ~/rspo_2026_08_13.csv
#
# Osobny plik od `migracja_na_demo.sh`, choć kroki są te same. Nie z lenistwa
# przy parametrach: przełącznik `--profil prod` w skrypcie demo znaczyłby, że
# produkcję da się ruszyć poleceniem wklejonym z pamięci, z jedną zmienioną
# literą. Tu trzeba wpisać inną nazwę pliku i potwierdzić słowem PRODUKCJA.
#
# CZYM PRODUKCJA RÓŻNI SIĘ OD DEMO — trzy rzeczy, każda kosztuje osobny krok:
#
# 1. NA PRODUKCJI JEST CZYJAŚ PRACA. Kopia jest OBOWIĄZKOWA i idzie razem
#    z eksportem do .xlsx — plik, który da się otworzyć bez tej aplikacji.
#    Kopia bazy jest do odtworzenia, arkusz jest na wypadek, gdyby odtwarzanie
#    z jakiegoś powodu nie wystarczyło.
#
# 2. LUDZIE PRACUJĄ W TRAKCIE. Zatrzymujemy usługę na czas migracji zamiast
#    liczyć na to, że nikt akurat nie kliknie. Handlowiec, który trafi w środek,
#    zobaczy błąd połączenia (i spróbuje ponownie za minutę) zamiast bazy
#    w połowie przerobionej — a formularz i tak trzyma szkic w telefonie.
#    Przestój to ~2 minuty; robić wieczorem.
#
# 3. LICZBA EVENTÓW MUSI SIĘ ZGADZAĆ CO DO SZTUKI. Skrypt zapisuje ją przed
#    i po, i sam krzyczy, gdy się rozjedzie. Migracja dokłada placówki i nadaje
#    geografię — nie ma prawa dotknąć kalendarza.
#
# Próba na kopii produkcji z 24.08 (08:24): 555 placówek → 1614, leady 554 →
# 1613, eventy 87 → 87, przydzielone 438 → 438, konta 49 → 49.
set -euo pipefail

KONTENER=leady_app_v5
USLUGA=leady_v5
PROFIL=prod
PORT=5301

CSV="${1:-}"
cd "$(dirname "$0")/.."

if [ -z "$CSV" ] || [ ! -f "$CSV" ]; then
    echo "Użycie: ./narzedzia/migracja_na_produkcje.sh <plik_rejestru.csv>"
    [ -n "$CSV" ] && echo "        (nie ma pliku: $CSV)"
    exit 2
fi

# --- 0/9 bezpieczniki -----------------------------------------------------
if ! docker inspect "$KONTENER" >/dev/null 2>&1; then
    echo "BŁĄD: nie ma kontenera $KONTENER."
    exit 1
fi
KATALOG=$(docker inspect "$KONTENER" \
    --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')
if [ "$KATALOG" != "$PWD" ]; then
    echo "BŁĄD: kontener $KONTENER należy do katalogu:"
    echo "        $KATALOG"
    echo "      a skrypt uruchomiono w: $PWD"
    exit 1
fi
if ! docker compose exec -T "$USLUGA" test -f geografia.py 2>/dev/null; then
    echo 'BŁĄD: kontener nie zna geografia.py — to stary obraz.'
    echo "      Najpierw:  git checkout poprawki-2026-08 && ./wdroz.sh prod"
    exit 1
fi

# Wolumen i obraz czytamy z ŻYWEGO kontenera, nie wpisujemy na sztywno — nazwa
# wolumenu bierze się z nazwy katalogu i każdy zapis na sztywno rozjechałby się
# po cichu przy jej zmianie. (Ta sama lekcja co w `odswiez_demo.sh`.)
WOLUMEN=$(docker inspect "$KONTENER" \
    --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')
OBRAZ=$(docker inspect "$KONTENER" --format '{{.Config.Image}}')
[ -n "$WOLUMEN" ] || { echo "BŁĄD: kontener nie ma wolumenu na /data."; exit 1; }

PRZEJSCIOWY=$(mktemp -d)
trap 'rm -rf "$PRZEJSCIOWY"' EXIT
cp "$CSV" "$PRZEJSCIOWY/rejestr.csv"

# Migracja idzie w JEDNORAZOWYM kontenerze na tym samym wolumenie — bo usługa
# jest w tym czasie zatrzymana, więc nie ma do czego zrobić `exec`.
w_kontenerze() {
    docker run --rm \
        -e PROFIL="$PROFIL" \
        -v "$WOLUMEN":/data \
        -v "$PRZEJSCIOWY":/wejscie:ro \
        "$OBRAZ" "$@"
}

echo "== co się wydarzy =="
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py stan --profil "$PROFIL"
EVENTY_PRZED=$(docker compose exec -T "$USLUGA" python -c \
    "import db; c=db.get_conn(); print(c.execute('SELECT COUNT(*) FROM eventy').fetchone()[0])" | tr -d '\r')
echo
echo "   Na kopii produkcji z 24.08 wyszło: 555 placówek → 1614, eventy 87 → 87."
echo "   Usługa będzie ZATRZYMANA na czas migracji (~2 minuty)."
echo
read -r -p 'Migrujemy PRODUKCJĘ? Wpisz PRODUKCJA, żeby potwierdzić: ' ODP
[ "$ODP" = "PRODUKCJA" ] || { echo "przerwane"; exit 0; }

echo "== 1/9 kopia bazy + eksport do .xlsx (punkt cofnięcia) =="
docker compose exec -T "$USLUGA" python narzedzia/baza.py backup --profil "$PROFIL" --trzymaj 30
KOPIA=$(docker compose exec -T "$USLUGA" sh -lc 'ls -1t /data/kopie/prod_*.db | head -1' | tr -d '\r')
echo "   $KOPIA"

echo "== 2/9 zatrzymuję usługę =="
# Gunicorn nie może pisać do bazy w trakcie jej przebudowy. Alternatywą byłoby
# liczenie na to, że nikt akurat nie kliknie — a to nie jest plan, tylko życzenie.
docker compose stop "$USLUGA"

echo "== 3/9 słowniki: statusy pośrednie =="
w_kontenerze python narzedzia/statusy.py --zapisz --profil "$PROFIL" | tail -3

echo "== 4/9 słowniki: wartości, które zna kod =="
w_kontenerze python narzedzia/slowniki_kontrola.py --zapisz --profil "$PROFIL" | tail -3

echo "== 5/9 lustro rejestru (M1) =="
w_kontenerze python narzedzia/migracja_rspo.py lustro \
    --csv /wejscie/rejestr.csv --profil "$PROFIL"

echo "== 6/9 obszary działania (M2) =="
w_kontenerze python narzedzia/migracja_rspo.py obszary --profil "$PROFIL" | tail -3

echo "== 7/9 powiat, gmina, czyste miejscowości (M5+M8) =="
w_kontenerze python narzedzia/migracja_rspo.py geografia \
    --miejscowosci --zapisz --profil "$PROFIL"

echo "== 8/9 numery RSPO (M3), potem powiaty jeszcze raz — już z rejestru =="
w_kontenerze python narzedzia/migracja_rspo.py dopasuj \
    --zapisz --profil "$PROFIL" | grep -E "Wpisano|Bez numeru"
w_kontenerze python narzedzia/migracja_rspo.py geografia \
    --miejscowosci --zapisz --profil "$PROFIL"

echo "== 9/9 dołożenie brakujących placówek z rejestru (M7) =="
w_kontenerze python narzedzia/migracja_rspo.py doloz \
    --grupa wszystkie --zapisz --profil "$PROFIL" | grep -E "Zapisano|ODMAWIAM"
w_kontenerze python narzedzia/migracja_rspo.py doloz \
    --grupa zespoly --wszystkie-zespoly --zapisz --profil "$PROFIL" | grep -E "Zapisano|ODMAWIAM"

echo "== start usługi =="
docker compose up -d "$USLUGA"
KOD=""
for _ in $(seq 1 30); do
    KOD=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/logowanie" || true)
    [ "$KOD" = "200" ] && break
    sleep 1
done
echo "   HTTP: ${KOD:-brak}"

echo
echo "== liczby po migracji =="
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py stan --profil "$PROFIL"
EVENTY_PO=$(docker compose exec -T "$USLUGA" python -c \
    "import db; c=db.get_conn(); print(c.execute('SELECT COUNT(*) FROM eventy').fetchone()[0])" | tr -d '\r')

echo
echo "Cofnięcie całości:"
echo "  docker compose stop $USLUGA"
echo "  docker compose exec $USLUGA python narzedzia/baza.py przywroc --profil $PROFIL --z $KOPIA"
echo "  docker compose up -d $USLUGA"
echo

if [ "$EVENTY_PRZED" != "$EVENTY_PO" ]; then
    echo "⛔ EVENTY SIĘ ROZJECHAŁY: przed $EVENTY_PRZED, po $EVENTY_PO."
    echo "   Migracja nie ma prawa dotknąć kalendarza. COFNIJ (polecenie wyżej)"
    echo "   i nie wypuszczaj tego do ludzi."
    exit 1
fi
echo "✓ eventy: $EVENTY_PRZED → $EVENTY_PO (bez zmian)"

if [ "$KOD" != "200" ]; then
    echo "BŁĄD: produkcja nie odpowiada na porcie $PORT."
    echo "      docker compose logs --tail 50 $USLUGA"
    exit 1
fi
echo "== gotowe =="
