#!/bin/bash
#
# Ściąganie kopii z VPS na Mac mini (Debian). Automatycznie przez timer systemd
# albo z ręki, kiedy chcesz.
#
#     ./kopia_na_maca.sh                        # sama baza, katalog domyślny
#     ./kopia_na_maca.sh --librus               # dołóż zrzut wolumenu librusa
#     ./kopia_na_maca.sh --kod                  # odśwież lustro repozytorium
#     ./kopia_na_maca.sh --cel ~/kopia_reczna_vps --librus --kod
#
# `--cel` służy do uruchomień z ręki, obok automatu: automat pisze do
# ~/Backups/leady, a Ty możesz zrzucić komplet gdzie indziej, nie mieszając
# w tym, co pilnuje timer. Każdy katalog ma własny log i własny znacznik
# ostatniego udanego przebiegu.
#
# PO CO
# Kopia leżąca na tym samym serwerze co oryginał chroni przed pomyłką człowieka,
# nie przed awarią maszyny. Mac mini jest warstwą awaryjną: stoi w biurze, bywa
# wyłączony i to jest w porządku — próbuje przy każdej okazji.
#
# DLACZEGO MAC CIĄGNIE, A SERWER NIE PCHA
# Gdyby VPS został przejęty, atakujący ma dostęp do wszystkiego, co ten serwer
# potrafi dosięgnąć — przy pchaniu skasowałby także kopie tutaj. Klucz SSH idzie
# Z MACA NA SERWER, nigdy odwrotnie.
#
# DLACZEGO TIMER systemd, A NIE cron
# Maszyna to Mac mini, ale system to Debian. Cron nie nadrabia pominiętych
# uruchomień: jeśli o 6:30 komputer był wyłączony, zadanie przepada do jutra.
# Timer systemd z `Persistent=true` odpala je przy najbliższym starcie — a przy
# maszynie, która bywa wyłączona, to jest różnica między kopią co dzień a kopią
# co czasem. Nawet z UPS-em: restart po aktualizacji jądra wystarczy, żeby
# trafić w tę jedną minutę.
#
# INSTALACJA — patrz docs/15_DOMENA_I_WDROZENIE.md punkt 9b.
set -uo pipefail

SERWER="ubuntu@57.128.241.52"
KONTENER="leady_app_v5"
PRZEJSCIOWY="~/kopie-vps"
REPO="https://github.com/pkonieczny007/leady_app_v5.git"

CEL="$HOME/Backups/leady"
LIBRUS=0
KOD=0
while [ $# -gt 0 ]; do
    case "$1" in
        --librus) LIBRUS=1 ;;
        --kod)    KOD=1 ;;
        --cel)    shift; CEL="${1:-}"
                  [ -n "$CEL" ] || { echo "--cel wymaga katalogu"; exit 2; } ;;
        -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Nieznany argument: $1"; exit 2 ;;
    esac
    shift
done

# Log, znacznik i lustro idą do katalogu docelowego — dzięki temu uruchomienie
# z ręki do innego katalogu nie nadpisuje śladu po automacie i odwrotnie.
LOG="$CEL/kopia.log"
ZNACZNIK="$CEL/OSTATNIA_UDANA.txt"
LUSTRO="$CEL/leady_app_v5.git"

mkdir -p "$CEL"
log() { echo "$(date '+%Y-%m-%d %H:%M')  $*" >> "$LOG"; echo "$*"; }

# BatchMode: bez tego przy braku klucza ssh czeka na hasło, a uruchomiony
# z launchd nie ma komu go wpisać — zadanie wisiałoby w nieskończoność.
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15"

if ! $SSH "$SERWER" "echo ok" >/dev/null 2>&1; then
    # Serwer nieosiągalny, brak sieci ALBO brak klucza SSH. To NIE jest awaria
    # warstwy awaryjnej — wychodzimy spokojnie, żeby timer nie świecił się na
    # czerwono po każdym przebiegu bez łączności. Ślad w logu zostaje.
    log "POMINIETE: brak polaczenia z $SERWER"
    if [ ! -f "$HOME/.ssh/id_ed25519" ] && [ ! -f "$HOME/.ssh/id_rsa" ]; then
        # Najczęstsza przyczyna przy pierwszym uruchomieniu: klucza po prostu
        # nie ma. `ssh-copy-id` mówi wtedy „No identities found", co brzmi jak
        # problem z serwerem, a jest brakiem klucza po naszej stronie.
        log "PRZYCZYNA: nie ma klucza SSH. Zrob:"
        log "   ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519"
        log "   ssh-copy-id $SERWER"
    fi
    exit 0
fi

DZIS="$CEL/$(date '+%Y-%m-%d_%H%M')"
mkdir -p "$DZIS"

# --------------------------------------------------------------- baza
# Kopie leżą w wolumenie dockera (/var/lib/docker/... — prawa drwx--x--- dla
# roota), więc rsync ich nie zobaczy. Najpierw trzeba je wyłożyć tam, gdzie
# sięga użytkownik `ubuntu`. Pliki -shm/-wal to towarzysze SQLite; przy
# odtwarzaniu tylko mylą, więc nie zabieramy ich ze sobą.
$SSH "$SERWER" "rm -rf $PRZEJSCIOWY && mkdir -p $PRZEJSCIOWY \
    && docker cp $KONTENER:/data/kopie/. $PRZEJSCIOWY/ \
    && rm -f $PRZEJSCIOWY/*-shm $PRZEJSCIOWY/*-wal \
    && chmod 700 $PRZEJSCIOWY && chmod 600 $PRZEJSCIOWY/*" || {
        log "BLAD: nie udalo sie wylozyc kopii na serwerze"; exit 1; }

# --------------------------------------------------------------- librus
if [ "$LIBRUS" = "1" ]; then
    WOL=$($SSH "$SERWER" "docker inspect librus_raport_app --format '{{range .Mounts}}{{if eq .Type \"volume\"}}{{.Name}} {{end}}{{end}}'" | tr -d '[:space:]')
    if [ -z "$WOL" ]; then
        log "librus: brak nazwanego wolumenu — pomijam"
    else
        TAR="librus_$(date '+%Y-%m-%d').tar.gz"
        # Kopia na poziomie plików z DZIAŁAJĄCEJ bazy może złapać stan
        # niespójny. Dopóki raz jej nie odtworzymy, to jest „lepsze niż nic",
        # a nie sprawdzona kopia — tak też jest opisane w docs/15.
        $SSH "$SERWER" "docker run --rm -v $WOL:/v -v $PRZEJSCIOWY:/out alpine tar czf /out/$TAR -C /v . && chmod 600 $PRZEJSCIOWY/$TAR" \
            && log "librus: spakowany $TAR" \
            || log "BLAD: zrzut librusa sie nie udal"
    fi
fi

# --------------------------------------------------------------- pobranie
rsync -az "$SERWER:kopie-vps/" "$DZIS/" || { log "BLAD: rsync sie nie udal — nie kasuje niczego na serwerze"; exit 1; }
$SSH "$SERWER" "rm -rf $PRZEJSCIOWY" || log "UWAGA: nie udalo sie sprzatnac $PRZEJSCIOWY"

ILE=$(ls -1 "$DZIS" 2>/dev/null | wc -l | tr -d ' ')
if [ "$ILE" = "0" ]; then
    rmdir "$DZIS" 2>/dev/null
    log "BLAD: nic nie pobrano"
    exit 1
fi

# --------------------------------------------------------------- kontrola
# Plik o poprawnej nazwie i rozmiarze to jeszcze nie kopia. Kopią jest coś,
# co daje się otworzyć i policzyć.
#
# Na Debianie sqlite3 nie jest instalowany domyślnie. Brak narzędzia NIE jest
# powodem, żeby przerwać kopiowanie — pliki już są ściągnięte i to jest
# najważniejsze. Ale mówimy o tym głośno, bo niesprawdzona kopia to kopia,
# w którą się wierzy, a nie taka, o której się wie.
ZLE=0
if ! command -v sqlite3 >/dev/null 2>&1; then
    log "UWAGA: brak sqlite3 — kopie sciagniete, ale NIESPRAWDZONE."
    log "       Instalacja:  sudo apt install sqlite3"
fi
for db in "$DZIS"/*.db; do
    command -v sqlite3 >/dev/null 2>&1 || break
    [ -e "$db" ] || continue
    STAN=$(sqlite3 "file:$db?mode=ro" "PRAGMA integrity_check;" 2>/dev/null | head -1)
    PLAC=$(sqlite3 "file:$db?mode=ro" "SELECT COUNT(*) FROM placowki;" 2>/dev/null)
    if [ "$STAN" = "ok" ] && [ "${PLAC:-0}" -gt 0 ] 2>/dev/null; then
        log "OK   $(basename "$db")  $PLAC placowek"
    else
        log "BLAD $(basename "$db")  integrity=$STAN placowki=${PLAC:-brak}"
        ZLE=$((ZLE + 1))
    fi
done

# --------------------------------------------------------------- kod
if [ "$KOD" = "1" ]; then
    # Lustro, nie zwykły klon: z gałęziami, tagami i całą historią. Gdyby
    # GitHub zniknął albo konto zostało zablokowane, z tego katalogu odtworzysz
    # repozytorium jednym `git clone`.
    if [ -d "$LUSTRO" ]; then
        (cd "$LUSTRO" && git remote update --prune >/dev/null 2>&1) \
            && log "lustro repo odswiezone" || log "BLAD: nie udalo sie odswiezyc lustra"
    else
        git clone --mirror "$REPO" "$LUSTRO" >/dev/null 2>&1 \
            && log "lustro repo zalozone" || log "BLAD: nie udalo sie sklonowac lustra"
    fi
fi

# --------------------------------------------------------------- znacznik
if [ "$ZLE" = "0" ]; then
    # Ten plik istnieje po to, żeby dało się jednym spojrzeniem sprawdzić, czy
    # warstwa awaryjna jeszcze żyje. Wyłączony Mac nie zgłasza błędu — jedyną
    # obroną przed „myślałem, że mamy kopie" jest data.
    date '+%Y-%m-%d %H:%M' > "$ZNACZNIK"
    log "gotowe: $ILE plikow w $DZIS"
else
    log "ZAKONCZONE Z BLEDAMI: $ZLE baz nie przeszlo kontroli"
    exit 1
fi
