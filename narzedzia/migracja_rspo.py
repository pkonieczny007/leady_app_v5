# -*- coding: utf-8 -*-
"""
Migracja bazy na rejestr RSPO — narzędzie etapów M0–M7.

Projekt i uzasadnienia: `docs/poprawki/2026-08-23/PROJEKT_BAZY_RSPO.md`.
Zasada rytmu: każdy etap najpierw na profilu `test`, na `prod` dopiero po
obejrzeniu wyniku; etap wymagający decyzji człowieka kończy się PLIKIEM do
zatwierdzenia, nie automatem.

KOMENDY (M1, M2, M7a; M3–M4 dojdą po decyzjach Kasi):
    python narzedzia/migracja_rspo.py lustro  --csv rspo_2026_08_13.csv
    python narzedzia/migracja_rspo.py obszary
    python narzedzia/migracja_rspo.py stan
    python narzedzia/migracja_rspo.py doloz --grupa przedszkola
    python narzedzia/migracja_rspo.py doloz --grupa przedszkola --zapisz
    python narzedzia/migracja_rspo.py doloz --cofnij --zapisz

`doloz` domyślnie NIE ZAPISUJE — bez `--zapisz` pokazuje liczby i wychodzi.
Ta sama zasada co w `statusy.py`: przy operacji na 700 rekordach człowiek ma
zobaczyć wynik, zanim się wydarzy.
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
    conn = db.get_conn()
    # Bazy profili powstały wcześniej niż kolumny `powiat`/`gmina`/`obszar`.
    # Aplikacja dokłada je przy starcie, ale narzędzie z linii poleceń bywa
    # pierwsze — na serwerze to normalna kolejność: `wdroz.sh`, migracja, potem
    # restart. Bez tego dołożenie wywala się na pierwszym INSERT-cie.
    db.migruj(conn)
    conn.commit()
    return conn


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


def cmd_doloz(a):
    """M7a: dołożenie brakujących placówek z lustra do bazy roboczej."""
    import collections
    import dokladanie
    conn = _polacz(a.profil)
    if conn.execute("SELECT name FROM sqlite_master WHERE name='rspo_obszar'")\
           .fetchone() is None:
        print("Najpierw M1 i M2 (`lustro`, potem `obszary`).")
        conn.close()
        return 1

    if a.cofnij:
        if not a.zapisz:
            ile = conn.execute(
                "SELECT COUNT(*) FROM placowki WHERE zrodlo='rspo'").fetchone()[0]
            print("Profil %s: %d placówek ze źródłem „rspo”. "
                  "Dodaj --zapisz, żeby skasować te bez śladu pracy." % (a.profil, ile))
            conn.close()
            return 0
        r = dokladanie.cofnij(conn)
        print("Profil %s: skasowano %d, zostało %d "
              "(zostają rekordy, na których ktoś już pracował)."
              % (a.profil, r["skasowane"], r["zostalo_z_rspo"]))
        conn.close()
        return 0

    plan = dokladanie.przygotuj(conn, a.grupa, pomijaj_zespoly=not a.wszystkie_zespoly)
    print("Profil %s — dołożenie „%s” (typy z rejestru: %s)"
          % (a.profil, a.grupa, ", ".join(plan["typy"])))
    print()

    if plan["braki_slownikow"]:
        print("  ⚠ Słownik TEGO profilu nie zna wartości, które trzeba wpisać:")
        for rodzaj, wartosc in plan["braki_slownikow"]:
            print("      %s / %s" % (rodzaj, wartosc))
        print("    Bez tego powstałyby rekordy, których karty nie da się zapisać.")
        print()

    wg_obszaru = collections.Counter()
    wg_typu = collections.Counter()
    for r in plan["do_zapisu"]:
        wg_obszaru[r["obszar"]] += 1
        wg_typu[r["typ"]] += 1

    print("  DO DOŁOŻENIA: %d" % len(plan["do_zapisu"]))
    for nazwa, n in sorted(wg_obszaru.items()):
        print("      %-24s %4d" % (nazwa, n))
    print("  wg typu:")
    for nazwa, n in sorted(wg_typu.items()):
        print("      %-38s %4d" % (nazwa, n))

    if plan.get("obce_typy"):
        print()
        print("  POMINIĘTE — zespół bez ani jednej podstawówki i przedszkola (%d):"
              % len(plan["obce_typy"]))
        for z in plan["obce_typy"][:6]:
            print("      %s (%s)" % (z["nazwa"][:64], z["miejscowosc"]))
        if len(plan["obce_typy"]) > 6:
            print("      … i %d dalszych" % (len(plan["obce_typy"]) - 6))
        print("    To technika, branżówki i licea — nie ten produkt.")

    if plan.get("ze_skladowymi"):
        print()
        print("  POMINIĘTE — zespół, którego szkołę albo przedszkole już mamy (%d):"
              % len(plan["ze_skladowymi"]))
        for z in plan["ze_skladowymi"][:10]:
            print("      %s (%s)" % (z["nazwa"][:64], z["miejscowosc"]))
        if len(plan["ze_skladowymi"]) > 10:
            print("      … i %d dalszych" % (len(plan["ze_skladowymi"]) - 10))
        print("    Dołożenie dałoby trzeci rekord pod tym samym adresem.")

    if plan["kolizje"]:
        print()
        print("  ODŁOŻONE — wyglądają na placówkę, którą już mamy (%d):"
              % len(plan["kolizje"]))
        for k in plan["kolizje"]:
            print("      %s (%s) ≈ nasz id %d „%s”"
                  % (k["nazwa"], k["miejscowosc"], k["nasz"]["id"], k["nasz"]["nazwa"]))
        print("    Nie dokładamy ich — dubel jest gorszy niż brak wiersza.")
    if plan["odlozone"]:
        print()
        print("  ODŁOŻONE — nie umiem przypisać miejscowości (%d):"
              % len(plan["odlozone"]))
        for o in plan["odlozone"][:20]:
            print("      %s — %s (%s)" % (o["nazwa"], o["miejscowosc"], o["powod"]))

    if not a.zapisz:
        print()
        print("  To był PODGLĄD — nic nie zapisano. Dodaj --zapisz.")
        conn.close()
        return 0

    try:
        dodane = dokladanie.zapisz(conn, plan, kto="migracja-rspo")
    except ValueError as e:
        print()
        print("  ODMAWIAM: %s" % e)
        conn.close()
        return 1
    print()
    print("  Zapisano %d placówek + %d nieprzydzielonych leadów." % (dodane, dodane))
    print("  Cofnięcie: doloz --cofnij --zapisz")
    conn.close()
    return 0


def cmd_geografia(a):
    """M5+M8: powiat i gmina dla wszystkich placówek, potem czyste miejscowości."""
    import geografia
    conn = _polacz(a.profil)
    if conn.execute("SELECT name FROM sqlite_master WHERE name='rspo_rejestr'")\
           .fetchone() is None:
        print("Najpierw M1 (`lustro`) — powiaty biorą się z rejestru.")
        conn.close()
        return 1

    r = geografia.uzupelnij(conn, zapisz=a.zapisz)
    print("Profil %s — powiat i gmina:" % a.profil)
    print("  z rejestru (po numerze RSPO): %d" % r["z_rejestru"])
    print("  po nazwie miejscowości:       %d" % r["z_nazwy"])
    print("  bez odpowiedzi:               %d" % len(r["bez_odpowiedzi"]))
    for b in r["bez_odpowiedzi"][:20]:
        print("      id %-5s %-40s miejscowość: %s"
              % (b["id"], (b["nazwa"] or "")[:40], b["miejscowosc"] or "(puste)"))

    if a.miejscowosci:
        zmiany = geografia.czysc_miejscowosci(conn, zapisz=a.zapisz)
        print("  miejscowości do wyczyszczenia: %d" % len(zmiany))
        from collections import Counter
        pary = Counter((str(z[1]), str(z[2])) for z in zmiany)
        for (bylo, jest), n in sorted(pary.items())[:25]:
            print("      %-28s → %-24s %d" % (bylo, jest, n))

    if a.zapisz:
        print()
        for w in geografia.podsumowanie(conn):
            print("  %-24s %5d  (szkoły %d, przedszkola %d)"
                  % (w["powiat"], w["ile"], w["szkoly"], w["przedszkola"]))
    else:
        print()
        print("  To był PODGLĄD — nic nie zapisano. Dodaj --zapisz.")
    conn.close()
    return 0


def cmd_dopasuj(a):
    """M3: nadanie numerów RSPO placówkom, które ich nie mają."""
    import collections
    import dopasowanie
    conn = _polacz(a.profil)
    if conn.execute("SELECT name FROM sqlite_master WHERE name='rspo_rejestr'")\
           .fetchone() is None:
        print("Najpierw M1 (`lustro`).")
        conn.close()
        return 1

    if a.decyzje:
        if not os.path.exists(a.decyzje):
            print("Nie ma pliku: %s" % a.decyzje)
            conn.close()
            return 1
        wiersze = dopasowanie.wczytaj_decyzje(a.decyzje)
        print("Decyzje człowieka z pliku: %d" % len(wiersze))
        if not a.zapisz:
            print("  To był PODGLĄD — nic nie zapisano. Dodaj --zapisz.")
            conn.close()
            return 0
        print("  Wpisano numerów: %d" % dopasowanie.wpisz(conn, wiersze))
        conn.close()
        return 0

    wiersze = dopasowanie.dopasuj(conn, a.plik)
    ile = collections.Counter(w["werdykt"] for w in wiersze)
    print("Profil %s — dopasowanie %d placówek bez numeru RSPO:"
          % (a.profil, len(wiersze)))
    for werdykt in ("zgodne", "pewne", "rozjazd", "tylko plik klienta",
                    "niepewne", "dubel", "numer zajęty", "brak"):
        if ile.get(werdykt):
            znak = "→ WPISZE" if werdykt in dopasowanie.WPISYWANE else "  do decyzji"
            print("  %-20s %4d   %s" % (werdykt, ile[werdykt], znak))
    jak = collections.Counter(w["jak"] for w in wiersze
                              if w["werdykt"] in dopasowanie.WPISYWANE)
    for k, n in jak.most_common():
        print("      trafione przez %-24s %4d" % (k, n))

    for w in wiersze:
        if w["werdykt"] == "rozjazd":
            print("  ROZJAZD id %-5s %-38s my %s / klient %s"
                  % (w["id"], w["nazwa"][:38], w["nasz"], w["klient"]))

    if a.xlsx:
        do_decyzji = sum(1 for w in wiersze if w["werdykt"] not in dopasowanie.WPISYWANE)
        dopasowanie.do_xlsx(conn, wiersze, a.xlsx)
        print("  Plik do decyzji (%d wierszy): %s" % (do_decyzji, a.xlsx))

    if not a.zapisz:
        print()
        print("  To był PODGLĄD — nic nie zapisano. Dodaj --zapisz.")
        conn.close()
        return 0

    n = dopasowanie.wpisz(conn, wiersze)
    print()
    print("  Wpisano numerów: %d" % n)
    zostalo = conn.execute("SELECT COUNT(*) FROM placowki "
                           "WHERE rspo IS NULL OR rspo=''").fetchone()[0]
    print("  Bez numeru zostało: %d" % zostalo)
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

    p = pod.add_parser("doloz", help="M7a: dołóż brakujące placówki z lustra")
    p.add_argument("--grupa", default="przedszkola",
                   choices=["przedszkola", "szkoly", "pozaszkolne", "zespoly",
                            "wszystkie"],
                   help="przedszkola i pozaszkolne: bez ryzyka dubli (nie mamy "
                        "ani jednej takiej placówki); szkoly: dopiero po nadaniu "
                        "numerów RSPO (M3), inaczej powstanie ~540 dubli; "
                        "zespoly: stanęłyby OBOK własnych składowych")
    p.add_argument("--zapisz", action="store_true",
                   help="bez tego pokazuje tylko liczby")
    p.add_argument("--cofnij", action="store_true",
                   help="kasuje dołożone rekordy BEZ śladu pracy")
    p.add_argument("--wszystkie-zespoly", action="store_true",
                   help="zespoły WSZYSTKIE, także stojące obok własnych składowych "
                        "— gdy liczby mają się pokrywać z rejestrem co do sztuki")
    p.add_argument("--profil", default=os.environ.get("PROFIL", "test"), choices=PROFILE)
    p.set_defaults(fn=cmd_doloz)

    p = pod.add_parser("geografia", help="M5: powiat i gmina dla wszystkich placówek")
    p.add_argument("--zapisz", action="store_true", help="bez tego tylko liczby")
    p.add_argument("--miejscowosci", action="store_true",
                   help="M8: przy okazji czyste nazwy miejscowości "
                        "(WOLNO dopiero razem z filtrem po powiecie)")
    p.add_argument("--profil", default=os.environ.get("PROFIL", "test"), choices=PROFILE)
    p.set_defaults(fn=cmd_geografia)

    p = pod.add_parser("dopasuj", help="M3: nadaj numery RSPO tym, co ich nie mają")
    p.add_argument("--plik", help="plik klienta z numerami (drugie źródło)")
    p.add_argument("--xlsx", help="gdzie zapisać plik decyzyjny dla koordynatorki")
    p.add_argument("--decyzje", help="wczytaj UZUPEŁNIONY plik decyzyjny i wpisz numery")
    p.add_argument("--zapisz", action="store_true", help="bez tego tylko liczby")
    p.add_argument("--profil", default=os.environ.get("PROFIL", "test"), choices=PROFILE)
    p.set_defaults(fn=cmd_dopasuj)

    p = pod.add_parser("stan", help="liczby kontrolne")
    p.add_argument("--profil", default=os.environ.get("PROFIL", "test"), choices=PROFILE)
    p.set_defaults(fn=cmd_stan)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
