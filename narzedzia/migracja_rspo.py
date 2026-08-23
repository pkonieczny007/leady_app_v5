# -*- coding: utf-8 -*-
"""
Migracja bazy na rejestr RSPO — narzędzie etapów M0–M7.

Projekt i uzasadnienia: `docs/poprawka 23.08.2026/PROJEKT_BAZY_RSPO.md`.
Zasada rytmu: każdy etap najpierw na profilu `test`, na `prod` dopiero po
obejrzeniu wyniku; etap wymagający decyzji człowieka kończy się PLIKIEM do
zatwierdzenia, nie automatem.

KOMENDY (na razie M1–M2; M3+ dojdą po decyzjach Kasi):
    python narzedzia/migracja_rspo.py lustro  --csv rspo_2026_08_08.csv
    python narzedzia/migracja_rspo.py obszary
    python narzedzia/migracja_rspo.py stan
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KATALOG)

PROFILE = ["prod", "test", "pusta"]


def _polacz(profil):
    # `DATA_DIR` WYGRYWA z `PROFIL` — ta sama odmowa co w `baza.py`
    # i `statusy.py`: w kontenerze `--profil prod` ruszyłoby bazę demo
    # i wyglądało na wykonane.
    wlasciwy = os.environ.get("PROFIL")
    if os.environ.get("DATA_DIR") and wlasciwy and wlasciwy != profil:
        print("Odmawiam: DATA_DIR wskazuje bazę profilu „%s”, a prosisz o „%s”."
              % (wlasciwy, profil))
        sys.exit(2)
    os.environ["PROFIL"] = profil
    import db
    return db.get_conn()


def cmd_lustro(a):
    """M1: wgranie pliku rejestru do lustra `rspo_rejestr`. Addytywne."""
    import rejestr_rspo
    if not os.path.exists(a.csv):
        print("Nie ma pliku: %s" % a.csv)
        return 1
    ok, brak, _ = rejestr_rspo.sprawdz_naglowki(a.csv)
    if not ok:
        print("To nie wygląda na eksport z RSPO — brakuje kolumn: %s"
              % ", ".join(brak))
        return 1
    conn = _polacz(a.profil)
    r = rejestr_rspo.wgraj(conn, a.csv,
                           wojewodztwo=None if a.cala_polska else "ŚLĄSKIE")
    conn.close()
    print("Profil %s — lustro po wgraniu:" % a.profil)
    print("  wierszy w pliku: %(wierszy_w_pliku)d, w zakresie: %(w_zakresie)d" % r)
    print("  nowych: %(nowych)d, zmienionych: %(zmienionych)d, "
          "bez zmian: %(bez_zmian)d, zniknęło: %(zniknelo)d" % r)
    print("  razem w lustrze: %(razem_w_lustrze)d (%(sekundy)ss)" % r)
    for u in r["uwagi"]:
        print("  UWAGA: %s" % u)
    return 0


def cmd_obszary(a):
    """M2: obszary działania + przypisanie lustra do obszarów."""
    import obszary
    conn = _polacz(a.profil)
    if conn.execute("SELECT name FROM sqlite_master WHERE name='rspo_rejestr'")\
           .fetchone() is None:
        print("Najpierw M1: lustro jest puste (komenda `lustro`).")
        conn.close()
        return 1
    zasiane = obszary.zasiej(conn)
    n = obszary.przelicz(conn)
    w_typach = obszary.w_zakresie_liczby(conn)
    print("Profil %s — obszary działania:" % a.profil)
    if zasiane:
        print("  zasiano %d obszarów startowych (lista Kasi)" % zasiane)
    for o in obszary.lista(conn):
        zakres = ", ".join("%s %s" % (z["rodzaj"], z["wartosc"]) for z in o["zakresy"])
        print("  %-24s %4d placówek   (%s)" % (o["nazwa"], o["placowek_w_lustrze"], zakres))
    print("  razem w obszarach: %d, w typach klienta (SP/przedszkola/punkty/zespoły): %d"
          % (n, w_typach))
    conn.close()
    return 0


def cmd_stan(a):
    """Liczby kontrolne — do porównania przed/po każdym etapie."""
    conn = _polacz(a.profil)
    def jedna(sql, params=()):
        try:
            return conn.execute(sql, params).fetchone()[0]
        except Exception:
            return "—"
    print("Profil %s:" % a.profil)
    print("  placowki: %s   leady: %s   eventy: %s   log: %s" % (
        jedna("SELECT COUNT(*) FROM placowki"),
        jedna("SELECT COUNT(*) FROM leady"),
        jedna("SELECT COUNT(*) FROM eventy"),
        jedna("SELECT COUNT(*) FROM log")))
    print("  placowki z rspo: %s" % jedna(
        "SELECT COUNT(*) FROM placowki WHERE rspo IS NOT NULL AND rspo <> ''"))
    print("  lustro rspo_rejestr: %s   obszary: %s   rspo_obszar: %s" % (
        jedna("SELECT COUNT(*) FROM rspo_rejestr"),
        jedna("SELECT COUNT(*) FROM obszary_dzialania"),
        jedna("SELECT COUNT(*) FROM rspo_obszar")))
    conn.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description="Migracja bazy na rejestr RSPO (M0–M7)")
    pod = ap.add_subparsers(dest="komenda", required=True)

    p = pod.add_parser("lustro", help="M1: wgraj plik rejestru do lustra")
    p.add_argument("--csv", required=True)
    p.add_argument("--profil", default=os.environ.get("PROFIL", "test"), choices=PROFILE)
    p.add_argument("--cala-polska", action="store_true",
                   help="bez filtra województwa (domyślnie tylko ŚLĄSKIE)")
    p.set_defaults(fn=cmd_lustro)

    p = pod.add_parser("obszary", help="M2: obszary działania + przypisanie")
    p.add_argument("--profil", default=os.environ.get("PROFIL", "test"), choices=PROFILE)
    p.set_defaults(fn=cmd_obszary)

    p = pod.add_parser("stan", help="liczby kontrolne")
    p.add_argument("--profil", default=os.environ.get("PROFIL", "test"), choices=PROFILE)
    p.set_defaults(fn=cmd_stan)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
