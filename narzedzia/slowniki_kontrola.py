# -*- coding: utf-8 -*-
"""
Kontrola zgodności słowników z kodem — wartości, które KOD zna, a słownika
danego profilu może nie być.

PO CO (E0 planu formularza, 23.08)
Kod zna typy zajęć przez stałe (`db.TYPY_CYKLICZNE`), ale słownik `typ_eventu`
to DANE — każdy profil ma własny. Baza produkcyjna powstała 10.08, ZANIM
doszedł typ `CYKLICZNE-PRZEDSZKOLE`, więc formularz v4 pozwala go zapisać
(walidacja idzie po stałej), ale późniejsza edycja takiego eventu na karcie
szkoły odbija się od twardej blokady słownika — jednej z dwóch jedynych
twardych blokad w aplikacji. Zapisać się dało, poprawić już nie.

Skrypt porównuje i dopisuje braki. Idempotentny — po odświeżeniu demo kopią
produkcji puszcza się go jeszcze raz, jak `statusy.py`.

UŻYCIE
    python narzedzia/slowniki_kontrola.py                    # tylko pokaż
    python narzedzia/slowniki_kontrola.py --zapisz --profil prod
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
    # DATA_DIR wygrywa z PROFIL — ta sama odmowa co w baza.py i statusy.py.
    wlasciwy = os.environ.get("PROFIL")
    if os.environ.get("DATA_DIR") and wlasciwy and wlasciwy != profil:
        print("Odmawiam: DATA_DIR wskazuje bazę profilu „%s”, a prosisz o „%s”."
              % (wlasciwy, profil))
        sys.exit(2)
    os.environ["PROFIL"] = profil
    import db
    return db, db.get_conn()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--profil", default=os.environ.get("PROFIL", "test"),
                    choices=PROFILE)
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args()

    db, conn = _polacz(a.profil)

    # Co kod zna, a słownik znać musi. Na dziś jeden rodzaj; jak dojdzie
    # następna stała (np. TYPY_JEDNORAZOWE z planu baz PH), dopisuje się
    # jedną parę tutaj — nie nowy skrypt.
    WYMAGANE = {
        "typ_eventu": list(db.TYPY_CYKLICZNE),
    }

    cos_brakowalo = False
    for rodzaj, wartosci in WYMAGANE.items():
        obecne = db.slownik_values(conn, rodzaj)
        brak = [w for w in wartosci if w not in obecne]
        print("Profil %s — %s: %d pozycji, kod wymaga %d"
              % (a.profil, rodzaj, len(obecne), len(wartosci)))
        for w in wartosci:
            if w in obecne:
                print("  = jest: %s" % w)
        for w in brak:
            cos_brakowalo = True
            if a.zapisz:
                nast = conn.execute(
                    "SELECT COALESCE(MAX(sort_order),0)+1 FROM slowniki "
                    "WHERE rodzaj=?", (rodzaj,)).fetchone()[0]
                conn.execute("INSERT OR IGNORE INTO slowniki "
                             "(rodzaj, wartosc, sort_order) VALUES (?,?,?)",
                             (rodzaj, w, nast))
                print("  + dopisane: %s" % w)
            else:
                print("  ! BRAKUJE: %s" % w)

    if a.zapisz:
        conn.commit()
    elif cos_brakowalo:
        print("\nNic nie zmieniłem. Powtórz z --zapisz.")
    else:
        print("\nKomplet — słowniki zgodne z kodem.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
