#!/usr/bin/env bash
#
# Przełącznik stanu bazy na DEMO. Jeden adres, kilka przygotowanych wzorców.
#
#     ./stan.sh lista                # jakie wzorce są przygotowane
#     ./stan.sh zapisz pelna         # bieżący stan zapisz jako wzorzec „pelna"
#     ./stan.sh wgraj pelna          # wgraj wzorzec
#     ./stan.sh pusta                # stan startowy: skasuj bazę, niech app zbuduje od zera
#
# PO CO
# Klient chce zobaczyć trzy rzeczy: świeżo postawioną aplikację, poligon
# z danymi do prób i komplet danych „jak na produkcji". To są trzy STANY
# jednej instalacji, nie trzy instalacje. Trzy osobne adresy znaczyłyby trzy
# certyfikaty, trzy kontenery do aktualizowania i — najgorsze — trzy podobnie
# wyglądające adresy, w które handlowiec może wpisać realną pracę nie tam,
# gdzie trzeba.
#
# CZEGO NIE ROBI
# Nie dotyka produkcji. Świadomie, bo polecenie „wgraj wzorzec" pomylone
# o jedną literę kasowałoby pracę handlowców. Produkcję odtwarza się
# narzedzia/baza.py z ręki, na spokojnie i z pełną świadomością.
set -euo pipefail

USLUGA=leady_v5_demo
WZORCE=/data/wzorce

cd "$(dirname "$0")"

# Każde nadpisanie bazy poprzedzamy kopią bieżącego stanu. Kosztuje pół sekundy
# i 0,5 MB, a ratuje sytuację „przełączyłem się, a tam były wpisy z pokazu".
kopia_bezpieczenstwa() {
    docker compose exec -T "$USLUGA" python narzedzia/baza.py backup \
        --profil test --bez-excela --trzymaj 30 >/dev/null 2>&1 \
        || echo "UWAGA: kopia bieżącego stanu się nie udała (baza jeszcze nie istnieje?)"
}

policz() {
    docker compose exec -T "$USLUGA" python - <<'PY' 2>/dev/null || echo "  (baza jeszcze nie odpowiada — daj jej sekundę)"
import db
c = db.get_conn()
def ile(t):
    try:
        return c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    except Exception:
        return "?"
print("  stan: %s placówek, %s leadów, %s eventów, %s kont, %s rejonów"
      % (ile("placowki"), ile("leady"), ile("eventy"), ile("uzytkownicy"), ile("rejony")))
PY
}

case "${1:-}" in

lista)
    echo "Wzorce w $WZORCE:"
    docker compose exec -T "$USLUGA" sh -c "ls -lh $WZORCE 2>/dev/null || echo '  (żadnego jeszcze nie zapisano)'"
    echo
    echo "Bieżący stan demo:"
    policz
    ;;

zapisz)
    NAZWA="${2:-}"
    [ -n "$NAZWA" ] || { echo "Podaj nazwę: ./stan.sh zapisz pelna"; exit 2; }
    # sqlite .backup, nie kopiowanie pliku — działa poprawnie na działającej
    # bazie w trybie WAL, gdzie część zapisów leży jeszcze poza plikiem .db
    docker compose exec -T "$USLUGA" python - "$NAZWA" <<'PY'
import os, sqlite3, sys
nazwa = sys.argv[1]
os.makedirs("/data/wzorce", exist_ok=True)
cel = "/data/wzorce/%s.db" % nazwa
src, dst = sqlite3.connect("/data/leady_v3.db"), sqlite3.connect(cel)
try:
    src.backup(dst)
finally:
    dst.close(); src.close()
print("zapisano wzorzec %r (%.1f MB)" % (nazwa, os.path.getsize(cel) / 1048576.0))
PY
    ;;

wgraj)
    NAZWA="${2:-}"
    [ -n "$NAZWA" ] || { echo "Podaj nazwę: ./stan.sh wgraj pelna"; exit 2; }
    docker compose exec -T "$USLUGA" test -f "$WZORCE/$NAZWA.db" \
        || { echo "BŁĄD: nie ma wzorca $NAZWA. Zobacz: ./stan.sh lista"; exit 1; }
    kopia_bezpieczenstwa
    docker compose stop "$USLUGA"
    # pliki -wal i -shm należą do STAREJ bazy; zostawione przy podmianie
    # potrafią dać „database disk image is malformed"
    docker compose run --rm "$USLUGA" sh -c \
        "cp $WZORCE/$NAZWA.db /data/leady_v3.db && rm -f /data/leady_v3.db-wal /data/leady_v3.db-shm"
    docker compose start "$USLUGA"
    sleep 3
    echo "wgrano wzorzec $NAZWA"
    policz
    ;;

pusta)
    # Nie wzorzec, tylko prawdziwy stan startowy: kasujemy bazę i pozwalamy
    # aplikacji zbudować ją od zera. To pokazuje dokładnie to, co zobaczy
    # klient po świeżej instalacji — schemat, słowniki, konta bez PIN-ów.
    kopia_bezpieczenstwa
    docker compose stop "$USLUGA"
    docker compose run --rm "$USLUGA" sh -c 'rm -f /data/leady_v3.db*'
    docker compose start "$USLUGA"
    sleep 4
    echo "stan startowy odtworzony"
    echo "UWAGA: świeży bootstrap nadaje koordynatorowi PIN domyślny. Ustaw własny:"
    echo "  docker compose exec $USLUGA python narzedzia/konto.py ustaw \\"
    echo "      --osoba Koordynator --rola koordynator --pin losowy --profil test"
    policz
    ;;

*)
    sed -n '3,12p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
