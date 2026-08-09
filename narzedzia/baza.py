# -*- coding: utf-8 -*-
"""
Zarządzanie profilami baz i kopiami zapasowymi.

Trzy bazy (prod / test / pusta) to NIE trzy gałęzie gita — to jeden kod
czytający zmienną PROFIL. To narzędzie te bazy zakłada, kopiuje i archiwizuje.

    python narzedzia/baza.py lista
    python narzedzia/baza.py nowa    --profil pusta
    python narzedzia/baza.py nowa    --profil test --z-pliku "PH Nowy.xlsx"
    python narzedzia/baza.py kopiuj  --z prod --do test
    python narzedzia/baza.py backup  --profil prod
    python narzedzia/baza.py przywroc --profil prod --z kopie/prod_2026-08-11_0600.db

Uwaga: PROFIL czytany jest przy imporcie `db`, dlatego każda komenda ustawia
zmienną środowiskową PRZED wczytaniem modułów aplikacji i robi to w podprocesie
(`_w_profilu`), gdy potrzebuje dwóch różnych profili naraz.

W kontenerze (DATA_DIR=/data) baza nie leży w data/<profil>, tylko wprost
w DATA_DIR, a kopie w DATA_DIR/kopie — inaczej ginęłyby przy przebudowie obrazu.
Wtedy widoczny jest wyłącznie profil z PROFIL; polecenie na inny profil kończy
się błędem zamiast po cichu ruszyć nie tę bazę.
"""
import argparse
import datetime as dt
import os
import shutil
import sqlite3
import subprocess
import sys

# Konsola Windows startuje w cp1250, która nie zna „→" — bez tego narzędzie
# wywala się na własnym komunikacie zamiast na błędzie merytorycznym.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(KATALOG, "data")
PROFILE = ["prod", "test", "pusta"]

# W kontenerze aplikacja NIE siada na data/<profil> — docker-compose ustawia
# DATA_DIR=/data i baza leży wprost tam (tak samo czyta to db.py). Bez tego
# nocny cron „backup --profil prod" co rano meldowałby „nie ma bazy profilu
# 'prod'" i przez tydzień nikt by nie zauważył, że kopii nie ma.
DATA_DIR = (os.environ.get("DATA_DIR") or "").strip()
PROFIL_SRODOWISKA = (os.environ.get("PROFIL") or "").strip().lower()

# Kopie w kontenerze muszą trafić na wolumen (/data/kopie), bo /app znika przy
# każdym `docker compose build`. Poza kontenerem zostaje katalog w repozytorium.
KOPIE = (os.environ.get("KOPIE_DIR")
         or (os.path.join(DATA_DIR, "kopie") if DATA_DIR else os.path.join(KATALOG, "kopie")))

sys.path.insert(0, KATALOG)


def sciezka_db(profil):
    if DATA_DIR and profil == PROFIL_SRODOWISKA:
        return os.path.join(DATA_DIR, "leady_v3.db")
    return os.path.join(DATA, profil, "leady_v3.db")


def _obcy_profil(*profile):
    """
    Czy któryś z profili jest niedostępny w tym uruchomieniu.

    Przy ustawionym DATA_DIR widać dokładnie JEDNĄ bazę — tę wskazaną przez
    PROFIL. Podprocesy z `_w_profilu` dziedziczą DATA_DIR, więc `--profil test`
    w kontenerze produkcyjnym nie otworzyłby bazy testowej, tylko po cichu
    produkcyjną. Lepiej odmówić niż zrobić backup nie tej bazy.
    """
    if not DATA_DIR:
        return None
    obce = [p for p in profile if p != PROFIL_SRODOWISKA]
    if not obce:
        return None
    return ("BŁĄD: przy DATA_DIR=%s widoczny jest wyłącznie profil %r, "
            "a polecenie dotyczy %s.\n"
            "      Uruchom je w kontenerze tego profilu albo bez DATA_DIR."
            % (DATA_DIR, PROFIL_SRODOWISKA or "(nieustawiony)",
               ", ".join(repr(p) for p in obce)))


def _stempel():
    return dt.datetime.now().strftime("%Y-%m-%d_%H%M")


def _licz(db_path, tabela):
    """Ile wierszy w tabeli — bez ładowania aplikacji, samo SQL."""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM %s" % tabela).fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _w_profilu(profil, kod):
    """Uruchamia fragment kodu w podprocesie z ustawionym PROFIL.

    Potrzebne, bo `db.PROFIL` ustala się raz przy imporcie — w jednym procesie
    nie da się obsłużyć dwóch baz naraz.
    """
    env = dict(os.environ, PROFIL=profil, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-c", kod], cwd=KATALOG, env=env)


# ------------------------------------------------------------------ komendy

def cmd_lista(_args):
    if DATA_DIR:
        print("DATA_DIR=%s — widoczny tylko profil %r (tak działa kontener)\n"
              % (DATA_DIR, PROFIL_SRODOWISKA or "(nieustawiony)"))
    print("%-8s %-10s %8s %8s %8s  %s" % (
        "PROFIL", "STAN", "PLACÓWKI", "LEADY", "MB", "ŚCIEŻKA"))
    for p in PROFILE:
        db = sciezka_db(p)
        if not os.path.exists(db):
            print("%-8s %-10s %8s %8s %8s  %s" % (p, "brak", "-", "-", "-", db))
            continue
        mb = os.path.getsize(db) / 1048576.0
        print("%-8s %-10s %8s %8s %8.1f  %s" % (
            p, "jest", _licz(db, "placowki"), _licz(db, "leady"), mb, db))

    if os.path.isdir(KOPIE):
        kopie = sorted(f for f in os.listdir(KOPIE) if f.endswith(".db"))
        print("\nkopie (%d): %s" % (
            len(kopie), kopie[-1] if kopie else "—"))
    else:
        print("\nkopie: brak katalogu %s" % KOPIE)
    return 0


def cmd_nowa(args):
    db = sciezka_db(args.profil)
    if os.path.exists(db) and not args.nadpisz:
        print("BŁĄD: %s już istnieje. Użyj --nadpisz, żeby zacząć od zera." % db)
        return 1
    if os.path.exists(db):
        kopia = _archiwizuj(args.profil, "przed-nadpisaniem")
        print("stara baza odłożona do %s" % kopia)
        os.remove(db)

    os.makedirs(os.path.dirname(db), exist_ok=True)
    print("zakładam bazę profilu %r → %s" % (args.profil, db))
    r = _w_profilu(args.profil, "from seed import bootstrap; "
                                "i = bootstrap(); "
                                "print('slowniki:', i['slowniki'], 'aliasy:', i['aliasy'])")
    if r.returncode:
        return r.returncode

    if args.z_pliku:
        plik = os.path.abspath(args.z_pliku)
        if not os.path.exists(plik):
            print("BŁĄD: nie ma pliku %s" % plik)
            return 1
        print("importuję %s" % plik)
        r = _w_profilu(args.profil,
                       "import db, importer; c = db.get_conn(); "
                       "print(importer.importuj_ph_nowy(c, %r)); c.commit()" % plik)
        if r.returncode:
            return r.returncode

    print("gotowe. Uruchom:  $env:PROFIL=\"%s\"; python app.py" % args.profil)
    return 0


def cmd_kopiuj(args):
    zrodlo, cel = sciezka_db(args.z), sciezka_db(args.do)
    if not os.path.exists(zrodlo):
        print("BŁĄD: nie ma bazy profilu %r (%s)" % (args.z, zrodlo))
        return 1
    if args.do == "prod" and not args.tak_wiem:
        print("BŁĄD: nadpisanie PRODUKCJI wymaga --tak-wiem. "
              "Najpierw zrób backup: python narzedzia/baza.py backup --profil prod")
        return 1
    if os.path.exists(cel):
        print("cel istnieje — odkładam kopię: %s" % _archiwizuj(args.do, "przed-kopiowaniem"))

    os.makedirs(os.path.dirname(cel), exist_ok=True)
    # .backup zamiast copy: działa poprawnie także gdy źródło jest w użyciu (WAL)
    src = sqlite3.connect(zrodlo)
    dst = sqlite3.connect(cel)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    print("%s → %s  (%d leadów)" % (args.z, args.do, _licz(cel, "leady")))
    return 0


def _archiwizuj(profil, etykieta=""):
    """Kopia .db do kopie/ ze stemplem czasu. Zwraca ścieżkę."""
    os.makedirs(KOPIE, exist_ok=True)
    nazwa = "%s_%s%s.db" % (profil, _stempel(), ("_" + etykieta) if etykieta else "")
    cel = os.path.join(KOPIE, nazwa)
    src = sqlite3.connect(sciezka_db(profil))
    dst = sqlite3.connect(cel)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return cel


def cmd_backup(args):
    db = sciezka_db(args.profil)
    if not os.path.exists(db):
        print("BŁĄD: nie ma bazy profilu %r" % args.profil)
        return 1

    cel = _archiwizuj(args.profil)
    print("baza  → %s  (%.1f MB)" % (cel, os.path.getsize(cel) / 1048576.0))

    if not args.bez_excela:
        xlsx = cel[:-3] + ".xlsx"
        r = _w_profilu(args.profil,
                       "import db, repo, exporter; c = db.get_conn(); "
                       "f = repo.pusty_filtr(); "
                       "bio = exporter.build_workbook(c, repo.filtruj_leady(c, f), f); "
                       "open(%r, 'wb').write(bio.getvalue()); print('ok')" % xlsx)
        if r.returncode == 0 and os.path.exists(xlsx):
            print("excel → %s" % xlsx)
        else:
            print("UWAGA: eksport do excela się nie udał — kopia .db jest, to ona liczy się "
                  "do odtworzenia.")

    if args.trzymaj:
        usuniete = _sprzataj(args.profil, args.trzymaj)
        if usuniete:
            print("usunięto %d starych kopii (retencja %d dni)" % (usuniete, args.trzymaj))
    return 0


def _sprzataj(profil, dni):
    """Kasuje kopie starsze niż `dni`, ale ZAWSZE zostawia poniedziałkowe."""
    granica = dt.datetime.now() - dt.timedelta(days=dni)
    n = 0
    for f in os.listdir(KOPIE):
        if not f.startswith(profil + "_"):
            continue
        try:
            stamp = dt.datetime.strptime(f[len(profil) + 1:len(profil) + 16], "%Y-%m-%d_%H%M")
        except ValueError:
            continue
        if stamp >= granica or stamp.weekday() == 0:
            continue
        os.remove(os.path.join(KOPIE, f))
        n += 1
    return n


def cmd_przywroc(args):
    zrodlo = os.path.abspath(args.z)
    if not os.path.exists(zrodlo):
        print("BŁĄD: nie ma pliku %s" % zrodlo)
        return 1
    leadow = _licz(zrodlo, "leady")
    if leadow is None:
        print("BŁĄD: %s nie wygląda na bazę leadów" % zrodlo)
        return 1

    cel = sciezka_db(args.profil)
    if os.path.exists(cel):
        print("obecna baza odłożona do %s" % _archiwizuj(args.profil, "przed-przywroceniem"))
    os.makedirs(os.path.dirname(cel), exist_ok=True)
    shutil.copy2(zrodlo, cel)
    print("przywrócono %s → profil %r (%d leadów)" % (zrodlo, args.profil, leadow))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("lista", help="jakie profile istnieją i ile mają danych")

    p = sub.add_parser("nowa", help="załóż bazę profilu (schemat + słowniki)")
    p.add_argument("--profil", required=True, choices=PROFILE)
    p.add_argument("--z-pliku", dest="z_pliku", help="zaimportuj po założeniu (PH Nowy .xlsx)")
    p.add_argument("--nadpisz", action="store_true", help="skasuj istniejącą (z kopią)")

    p = sub.add_parser("kopiuj", help="przenieś dane między profilami")
    p.add_argument("--z", required=True, choices=PROFILE)
    p.add_argument("--do", required=True, choices=PROFILE)
    p.add_argument("--tak-wiem", dest="tak_wiem", action="store_true",
                   help="wymagane przy nadpisywaniu produkcji")

    p = sub.add_parser("backup", help="kopia .db + eksport .xlsx do kopie/")
    p.add_argument("--profil", default="prod", choices=PROFILE)
    p.add_argument("--bez-excela", dest="bez_excela", action="store_true")
    p.add_argument("--trzymaj", type=int, default=0,
                   help="usuń kopie starsze niż N dni (poniedziałkowe zostają)")

    p = sub.add_parser("przywroc", help="odtwórz profil z pliku kopii")
    p.add_argument("--profil", required=True, choices=PROFILE)
    p.add_argument("--z", required=True, help="ścieżka do pliku .db z kopie/")

    args = ap.parse_args()

    uzyte = [p for p in (getattr(args, "profil", None), getattr(args, "z", None),
                         getattr(args, "do", None)) if p in PROFILE]
    blad = _obcy_profil(*uzyte)
    if blad:
        print(blad)
        return 1

    return {"lista": cmd_lista, "nowa": cmd_nowa, "kopiuj": cmd_kopiuj,
            "backup": cmd_backup, "przywroc": cmd_przywroc}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
