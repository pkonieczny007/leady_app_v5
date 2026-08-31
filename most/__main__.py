# -*- coding: utf-8 -*-
"""
Most z linii poleceń.

    python -m most                 # przepisz pliki teraz
    python -m most --stan          # co leży w katalogu i kiedy powstało
    python -m most --podglad       # policz i wypisz, NIC nie zapisując

W kontenerze:
    docker compose exec -T leady_v5 python -m most

Dlaczego `python -m most`, a nie skrypt w `narzedzia/`: skrypty stamtąd wkładają
katalog repozytorium na początek `sys.path`, a plik o nazwie `narzedzia/most.py`
leżałby wtedy w cieniu pakietu `most/` (albo odwrotnie, zależnie od kolejności)
— czyli `import most` znaczyłby raz jedno, raz drugie. Uruchomienie modułem
nie ma tej dwuznaczności.

Zapas na wypadek, gdyby hak na ruchu okazał się za wolny albo trzeba było
wystawić plik przy wyłączonej aplikacji. Na co dzień nikt tego nie uruchamia.
"""
import argparse
import json
import sys

for _s in (sys.stdout, sys.stderr):
    # Konsola Windows startuje w cp1250 i wywala się na własnym komunikacie
    # zawierającym „→" — zanim w ogóle dojdzie do sprawy merytorycznej.
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from db import get_conn, opis_profilu          # noqa: E402

import most                                     # noqa: E402
from most import dane, pliki                    # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description="Most do aplikacji partnerskiej")
    p.add_argument("--stan", action="store_true", help="co leży w katalogu wymiany")
    p.add_argument("--podglad", action="store_true", help="policz i wypisz, nie zapisuj")
    a = p.parse_args(argv)

    profil = opis_profilu()
    print("Profil: %s (%s)" % (profil["klucz"], profil["etykieta"]))
    print("Katalog wymiany: %s" % pliki.KATALOG)

    if a.stan:
        stan = pliki.czytaj_stan()
        if not stan:
            print("  (pusto — most jeszcze nic nie wystawił)")
            return 1
        print(json.dumps(stan, ensure_ascii=False, indent=2))
        return 0

    conn = get_conn()
    try:
        if a.podglad:
            m = dane.zbuduj(conn)
            print("  cykle: %d (aktywne %d) · DT: %d (aktywne %d) · niekompletne: %d"
                  % (m["liczby"]["cykle"], m["liczby"]["cykle_aktywne"],
                     m["liczby"]["dt"], m["liczby"]["dt_aktywne"],
                     m["liczby"]["niekompletne"]))
            for rec in (m["cykle"] + m["dt"]):
                if rec["missing"]:
                    print("    ! %s — brakuje: %s"
                          % (rec.get("school") or "?", ", ".join(rec["missing"])))
            return 0
        stan = most.zapisz(conn)
        print("  zapisano: cykle %d · DT %d · zmian w tym przebiegu %d"
              % (stan["liczby"]["cykle"], stan["liczby"]["dt"],
                 stan["zmian_w_tym_przebiegu"]))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
