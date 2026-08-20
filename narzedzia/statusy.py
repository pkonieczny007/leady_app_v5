# -*- coding: utf-8 -*-
"""
Statusy pośrednie w słowniku `status_realizacji` (P25, lista Zuzi z 20.08).

PO CO
Zuzia opisała realny przebieg pracy handlowca:

    przydzielona szkoła → próba kontaktu → kontakt → spotkanie →
    zainteresowanie → oczekiwanie na decyzję/termin → ustalenie szczegółów →
    DT → ustalenie cykli → zakończone

Aplikacja znała z tego siedem stanów, ale trzech nie — a bez nich część pracy
NIE MA JAK zostać zapisana. To nie jest kosmetyka słownika: „byłam, dyrektor
się zastanawia do przyszłego tygodnia" bez pozycji „czekam na decyzję" ląduje
albo jako „01. Próba kontaktu", albo (gorzej) jako nic, i szkoła wygląda na
nietkniętą.

DLACZEGO OSOBNE NARZĘDZIE
Słownik to DANE, nie kod — każdy profil ma własny, a demo bywa zasiewane kopią
produkcji (`odswiez_demo.sh`), która te pozycje zetrze. Skrypt jest
idempotentny, więc po każdym odświeżeniu demo puszcza się go jeszcze raz.
Koordynator może dodać te same pozycje ręcznie w ekranie Słowniki — to jest
ta sama operacja, tylko wolniejsza i podatna na literówkę w prefiksie.

⚠ PREFIKS NIESIE ZNACZENIE, NIE TYLKO KOLEJNOŚĆ
`db.STATUS_SUKCES_PREFIX = "03."` i `STATUS_ODPADL_PREFIX = "04."`. Kod pyta
o nie w kilkunastu miejscach: auto-zwrot szkół po terminie, „moje szkoły",
liczniki na pulpicie, raport wykonania. Dlatego:

  * stany „w toku" dostają 01x/02x — szkoła zostaje żywa i dalej podlega
    auto-zwrotowi, czyli nie da się jej zaparkować na zawsze;
  * „po DT, ustalamy cykle" dostaje prefiks `03. ` — DT się odbyło, więc to
    jest sukces i szkoła NIE ma prawa wrócić do puli;
  * ⚠ NIE dokładamy pozycji „brak kontaktu" z prefiksem `04.` — taka już jest
    („04. BRAK KONTAKTU ZE SZKOŁĄ") i znaczy „odpadł", czyli szkoła znika
    handlowcowi z listy. Zuzi chodzi o stan przejściowy, stąd `01c.`.

UŻYCIE
    python narzedzia/statusy.py                      # pokaż, co brakuje
    python narzedzia/statusy.py --zapisz --profil test
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

# (wartość, po której istniejącej pozycji wstawić)
# Kolejność w słowniku ma znaczenie: handlowiec czyta tę listę z góry na dół
# jak ścieżkę, a nie jak alfabetyczny spis.
NOWE = [
    ("01b. Ponowić kontakt", "01. Próba kontaktu (Brak konkretów)"),
    ("01c. Brak kontaktu (próbuję dalej)", "01b. Ponowić kontakt"),
    ("02c. Czekam na decyzję", "02b. DT w trakcie umawiania"),
    ("03. Po DT — ustalić cykle", "03. DT umówione"),
]

RODZAJ = "status_realizacji"


def _polacz(profil):
    os.environ["PROFIL"] = profil
    import db
    return db, db.get_conn()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--profil", default=os.environ.get("PROFIL", "test"),
                    choices=PROFILE)
    ap.add_argument("--zapisz", action="store_true",
                    help="bez tego tylko pokazuje, co by dopisał")
    a = ap.parse_args()

    db, conn = _polacz(a.profil)
    obecne = db.slownik_values(conn, RODZAJ)
    print("Profil %s — słownik „%s” ma %d pozycji" % (a.profil, RODZAJ, len(obecne)))

    # Pozycje trzymamy w pamięci, a nie odpytujemy bazy za każdym razem —
    # bo `01c.` zaczepia się o `01b.`, którego w trybie podglądu jeszcze
    # w bazie NIE MA. Bez tego podgląd kłamał, że jednej pozycji nie doda.
    pozycje = {r["wartosc"]: r["sort_order"] for r in conn.execute(
        "SELECT wartosc, sort_order FROM slowniki WHERE rodzaj=?", (RODZAJ,))}

    dopisane, byly = [], []
    for wartosc, po_czym in NOWE:
        if wartosc in obecne:
            byly.append(wartosc)
            continue
        # Wstawiamy TUŻ ZA pozycją, po której ta rzecz następuje w pracy
        # handlowca. Doklejanie na koniec listy (MAX(sort_order)+1) dawałoby
        # słownik, w którym „ponowić kontakt" leży pod „odpuścić" — czyli
        # ścieżkę czyta się skokami.
        if po_czym not in pozycje:
            print("  ! nie ma pozycji „%s” — pomijam „%s”" % (po_czym, wartosc))
            continue
        miejsce = pozycje[po_czym]
        if a.zapisz:
            conn.execute("UPDATE slowniki SET sort_order = sort_order + 1 "
                         "WHERE rodzaj=? AND sort_order > ?", (RODZAJ, miejsce))
            conn.execute("INSERT OR IGNORE INTO slowniki (rodzaj, wartosc, sort_order) "
                         "VALUES (?,?,?)", (RODZAJ, wartosc, miejsce + 1))
        for k in list(pozycje):
            if pozycje[k] > miejsce:
                pozycje[k] += 1
        pozycje[wartosc] = miejsce + 1
        dopisane.append(wartosc)

    if a.zapisz:
        conn.commit()

    for w in byly:
        print("  = już jest: %s" % w)
    for w in dopisane:
        print("  %s %s" % ("+ dopisane:" if a.zapisz else "→ dopisałbym:", w))

    if dopisane and not a.zapisz:
        print("\nNic nie zmieniłem. Powtórz z --zapisz.")
    elif a.zapisz:
        print("\nSłownik ma teraz %d pozycji." % len(db.slownik_values(conn, RODZAJ)))
        print("Kolejność:")
        for w in db.slownik_values(conn, RODZAJ):
            print("   %s" % w)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
