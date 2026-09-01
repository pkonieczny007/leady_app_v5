# -*- coding: utf-8 -*-
"""
Zarządzanie kontami z linii poleceń.

Panel `/uzytkownicy` w aplikacji robi to samo, ale wymaga zalogowania — a bywa
sytuacja, w której nie da się wejść: świeży profil bez kont, zapomniany PIN
koordynatora, albo konto serwisowe zakładane przed pierwszym startem.
To narzędzie jest wyjściem awaryjnym i działa wprost na pliku bazy.

    python narzedzia/konto.py lista --profil test
    python narzedzia/konto.py ustaw --osoba Developer --rola koordynator --pin 7777
    python narzedzia/konto.py ustaw --osoba "01. Sacawa" --pin losowy
    python narzedzia/konto.py wylacz --osoba Developer
    python narzedzia/konto.py usun --osoba Developer

`ustaw` zakłada konto, jeśli go nie ma, a istniejącemu podmienia PIN i rolę —
jedno polecenie zamiast trzech, bo w praktyce zawsze idą razem.
"""
import argparse
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KATALOG)

PROFILE = ["prod", "test", "pusta"]

# PIN-y, które ludzie wpisują odruchowo. Nie blokujemy ich — to świadoma decyzja
# człowieka przy klawiaturze — ale mówimy głośno, bo na koncie z uprawnieniami
# koordynatora czterocyfrowy „7777" w internecie to realne ryzyko.
SLABE = {"0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777",
         "8888", "9999", "1234", "4321", "1212", "0123", "2580", "1379"}


def _polacz(profil):
    os.environ["PROFIL"] = profil
    import db                       # noqa: E402 — po ustawieniu PROFIL
    import uzytkownicy as uz        # noqa: E402
    conn = db.get_conn()
    uz.init(conn)
    return conn, uz


def cmd_lista(args):
    conn, uz = _polacz(args.profil)
    konta = uz.lista(conn)
    conn.close()
    if not konta:
        print("Profil %r nie ma jeszcze żadnych kont." % args.profil)
        return 0
    print("%-26s %-13s %-10s %-18s %s" % ("OSOBA", "ROLA", "PIN", "OSTATNIE LOGOWANIE", "STAN"))
    print("-" * 82)
    for k in konta:
        stan = "aktywne" if k["aktywny"] else "WYŁĄCZONE"
        if k["nieudane"] >= uz.MAX_PROB:
            stan = "ZABLOKOWANE (%d prób)" % k["nieudane"]
        elif k["nieudane"]:
            stan = "aktywne (%d błędnych)" % k["nieudane"]
        print("%-26s %-13s %-10s %-18s %s" % (
            k["osoba"], k["rola"], "ustawiony" if k["ma_pin"] else "BRAK",
            (k["ostatnie_logowanie"] or "—")[:16], stan))
    return 0


def cmd_ustaw(args):
    conn, uz = _polacz(args.profil)
    try:
        pin = args.pin
        if pin == "losowy":
            pin = uz.losowy_pin()
        if pin is not None and not uz.poprawny_format(pin):
            print("BŁĄD: PIN musi mieć dokładnie 4 cyfry (albo słowo 'losowy')")
            return 1

        istnieje = uz.znajdz(conn, args.osoba)
        if istnieje:
            if args.rola:
                uz.ustaw_role(conn, args.osoba, args.rola)
            if pin:
                uz.ustaw_pin(conn, args.osoba, pin)
            print("zaktualizowano konto %r w profilu %r" % (args.osoba, args.profil))
        else:
            uz.utworz(conn, args.osoba, args.rola or "handlowiec", pin)
            print("utworzono konto %r w profilu %r" % (args.osoba, args.profil))

        u = uz.znajdz(conn, args.osoba)
        print("   rola:  %s" % u["rola"])
        print("   PIN:   %s" % (pin if pin else "bez zmian"))
        print("   stan:  %s" % ("aktywne" if u["aktywny"] else "wyłączone"))
        if pin:
            dziala = uz.sprawdz_pin(pin, u["sol"], u["pin_hash"])
            print("   sprawdzenie logowania: %s" % ("OK" if dziala else "NIE DZIAŁA"))
            if not dziala:
                return 1
            if pin in SLABE:
                print()
                print("   UWAGA: %s to jeden z PIN-ów wpisywanych odruchowo." % pin)
                if u["rola"] == "koordynator":
                    print("   Na koncie koordynatora, wystawionym do internetu, to realne")
                    print("   ryzyko — zmień go przed wdrożeniem na VPS.")
        return 0
    except ValueError as e:
        print("BŁĄD: %s" % e)
        return 1
    finally:
        conn.close()


def cmd_wylacz(args):
    conn, uz = _polacz(args.profil)
    try:
        if not uz.znajdz(conn, args.osoba):
            print("BŁĄD: nie ma konta %r" % args.osoba)
            return 1
        uz.ustaw_aktywny(conn, args.osoba, args.wlacz)
        print("konto %r: %s" % (args.osoba, "włączone" if args.wlacz else "wyłączone"))
        return 0
    finally:
        conn.close()


def cmd_usun(args):
    conn, uz = _polacz(args.profil)
    try:
        u = uz.znajdz(conn, args.osoba)
        if not u:
            print("BŁĄD: nie ma konta %r" % args.osoba)
            return 1
        if u["rola"] == "koordynator":
            ilu = conn.execute("SELECT COUNT(*) c FROM uzytkownicy "
                               "WHERE rola='koordynator' AND aktywny=1").fetchone()["c"]
            if ilu <= 1:
                print("BŁĄD: to jedyny koordynator — bez niego nikt nie nada PIN-ów.")
                return 1
        uz.usun(conn, args.osoba)
        print("usunięto konto %r" % args.osoba)
        return 0
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profil", default="test", choices=PROFILE)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("lista", help="wypisz konta profilu")

    p = sub.add_parser("ustaw", help="załóż konto albo zmień PIN/rolę istniejącego")
    p.add_argument("--osoba", required=True)
    # Lista z `uzytkownicy.ROLE`, a nie wpisana tu z ręki — od 31.08 doszło
    # „biuro" i wpisana kopia znaczyłaby, że konta tej roli nie da się założyć
    # jedynym narzędziem, które działa, gdy nie da się zalogować.
    p.add_argument("--rola", choices=list(uz.ROLE))
    p.add_argument("--pin", help="4 cyfry albo słowo 'losowy'")

    p = sub.add_parser("wylacz", help="wyłącz konto (nie kasuje danych)")
    p.add_argument("--osoba", required=True)
    p.add_argument("--wlacz", action="store_true", help="odwrotnie: włącz z powrotem")

    p = sub.add_parser("usun", help="skasuj konto")
    p.add_argument("--osoba", required=True)

    args = ap.parse_args()
    return {"lista": cmd_lista, "ustaw": cmd_ustaw,
            "wylacz": cmd_wylacz, "usun": cmd_usun}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
