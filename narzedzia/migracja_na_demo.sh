#!/usr/bin/env bash
#
# Migracja bazy DEMO na rejestr RSPO — jednym poleceniem, w kolejności
# przećwiczonej 24.08 na KOPII PRODUKCJI (545 placówek → 1613, eventy 65 → 65).
#
#     cd /home/ubuntu/apps/demo-ph.silesia3d.site
#     ./narzedzia/migracja_na_demo.sh ~/rspo_2026_08_13.csv
#
# Po co skrypt zamiast dwunastu poleceń z palca: bo KOLEJNOŚĆ tu nie jest
# kwestią stylu. `geografia` przed `dopasuj` nadaje powiaty po nazwie
# miejscowości i przy okazji rozpakowuje worki „09. Pszczyna powiat" — dopiero
# na czystych nazwach dopasowanie trafia 520 z 545 numerów zamiast garstki.
# `dopasuj` przed `doloz` jest warunkiem koniecznym: bez numerów RSPO dołożenie
# szkół zrobiłoby ~540 dubli, bo nie miałoby po czym rozpoznać naszych.
#
# Skrypt NIE robi niczego, czego nie da się cofnąć: pierwszym krokiem jest kopia
# bazy, a nazwa pliku do przywrócenia wypisuje się na końcu.
#
# Ten sam skrypt pojedzie kiedyś na produkcję (`--profil prod` w środku), ale
# dopiero po tygodniu obserwacji demo. Dlatego świadomie nie ma tu przełącznika
# „prod" — decyzja o produkcji ma być osobnym, świadomym ruchem, a nie literą
# w poleceniu wklejonym z pamięci.
set -euo pipefail

KONTENER=leady_app_v5_demo
USLUGA=leady_v5_demo
PROFIL=test

CSV="${1:-}"
POTWIERDZONE="${2:-}"

cd "$(dirname "$0")/.."

if [ -z "$CSV" ]; then
    echo "Użycie: ./narzedzia/migracja_na_demo.sh <plik_rejestru.csv> [--tak]"
    echo "        plik z rejestru RSPO (eksport CSV, ~41 MB) — z Twojego komputera."
    exit 2
fi
if [ ! -f "$CSV" ]; then
    echo "BŁĄD: nie ma pliku $CSV"
    exit 1
fi

# --- 0/9 bezpiecznik: czy to na pewno katalog DEMO ------------------------
# Usługa `leady_v5_demo` jest zdefiniowana w OBU katalogach (jedno wspólne
# docker-compose.yml). Odpalone z katalogu produkcyjnego `docker compose exec`
# celowałoby w inny projekt — ta sama pułapka co w `odswiez_demo.sh`.
if ! docker inspect "$KONTENER" >/dev/null 2>&1; then
    echo "BŁĄD: nie ma kontenera $KONTENER. Najpierw: ./wdroz.sh demo"
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

# Kod musi być NOWY, zanim ruszy migracja: `dokladanie.py`, `geografia.py`
# i `dopasowanie.py` doszły w tej rundzie. Na starym obrazie pierwsza komenda
# wywali się na imporcie — i dobrze, ale lepiej powiedzieć to od razu.
if ! docker compose exec -T "$USLUGA" test -f geografia.py 2>/dev/null; then
    echo 'BŁĄD: kontener nie zna geografia.py — to stary obraz.'
    echo "      Najpierw:  git checkout poprawki-2026-08 && ./wdroz.sh demo"
    exit 1
fi

echo "== co się wydarzy =="
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py stan --profil "$PROFIL"
echo
echo "   → słowniki (statusy pośrednie, CYKLICZNE-PRZEDSZKOLE)"
echo "   → lustro rejestru, obszary działania"
echo "   → powiat i gmina dla wszystkich placówek, czyste miejscowości"
echo "   → numery RSPO (na kopii produkcji: 520 z 545, reszta do decyzji Kasi)"
echo "   → dołożenie brakujących placówek z rejestru (na kopii: +790, +278 zespołów)"
echo
if [ "$POTWIERDZONE" != "--tak" ]; then
    read -r -p "Robimy to na DEMO? [tak/nie] " ODP
    [ "$ODP" = "tak" ] || { echo "przerwane"; exit 0; }
fi

echo "== 1/9 kopia bazy (punkt cofnięcia) =="
docker compose exec -T "$USLUGA" python narzedzia/baza.py backup --profil "$PROFIL" --bez-excela
KOPIA=$(docker compose exec -T "$USLUGA" sh -lc 'ls -1t /data/kopie/test_*.db | head -1' | tr -d '\r')
echo "   $KOPIA"

echo "== 2/9 plik rejestru do kontenera =="
# Katalog repozytorium jest WBUDOWANY w obraz, nie podmontowany — plik położony
# obok tego skryptu byłby dla kontenera niewidoczny. Wkładamy go na wolumen.
docker cp "$CSV" "$KONTENER:/data/_rejestr.csv"

echo "== 3/9 słowniki: statusy pośrednie =="
docker compose exec -T "$USLUGA" python narzedzia/statusy.py --zapisz --profil "$PROFIL" | tail -3

echo "== 4/9 słowniki: wartości, które zna kod =="
docker compose exec -T "$USLUGA" python narzedzia/slowniki_kontrola.py --zapisz --profil "$PROFIL" | tail -3

echo "== 5/9 lustro rejestru (M1) =="
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py lustro \
    --csv /data/_rejestr.csv --profil "$PROFIL"

echo "== 6/9 obszary działania (M2) =="
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py obszary --profil "$PROFIL" | tail -3

echo "== 7/9 powiat, gmina, czyste miejscowości (M5+M8) =="
# Bez `| head` świadomie: `head` zamyka potok, python dostaje SIGPIPE i przy
# `pipefail` cały skrypt kończy się „błędem", którego nie było.
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py geografia \
    --miejscowosci --zapisz --profil "$PROFIL"

echo "== 8/9 numery RSPO (M3), potem powiaty jeszcze raz — już z rejestru =="
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py dopasuj \
    --zapisz --profil "$PROFIL" | grep -E "Wpisano|Bez numeru"
# Druga tura geografii nie jest zapasową: 520 rekordów ma teraz numer RSPO, więc
# powiat i miejscowość biorą się z REJESTRU, a nie z nazwy. To tutaj Czeladź
# wychodzi z worka „15. Będzin powiat" i zaczyna istnieć jako miejscowość.
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py geografia \
    --miejscowosci --zapisz --profil "$PROFIL"

echo "== 9/9 dołożenie brakujących placówek z rejestru (M7) =="
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py doloz \
    --grupa wszystkie --zapisz --profil "$PROFIL" | grep -E "Zapisano|ODMAWIAM"
# Zespoły osobno i w komplecie — decyzja Pawła z 24.08: „wolę mieć za dużo niż
# za mało". Część stanie obok własnych składowych, rozróżnia je typ `04. ZSP`.
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py doloz \
    --grupa zespoly --wszystkie-zespoly --zapisz --profil "$PROFIL" | grep -E "Zapisano|ODMAWIAM"

docker compose exec -T "$USLUGA" rm -f /data/_rejestr.csv

echo
echo "== liczby po migracji =="
docker compose exec -T "$USLUGA" python narzedzia/migracja_rspo.py stan --profil "$PROFIL"
echo
echo "Na kopii produkcji wyszło: placowki 1613, leady 1613, EVENTY BEZ ZMIAN (65),"
echo "z rspo 1588, lustro 6117, obszary 17. Liczba eventów to najważniejsza"
echo "z tych liczb — migracja NIE ma prawa ruszyć niczyjej pracy w kalendarzu."
echo
echo "Cofnięcie całości:"
echo "  docker compose exec $USLUGA python narzedzia/baza.py przywroc \\"
echo "      --profil $PROFIL --z $KOPIA"
echo "Cofnięcie samego dołożenia (zostawia numery i powiaty):"
echo "  docker compose exec $USLUGA python narzedzia/migracja_rspo.py doloz --cofnij --zapisz"
