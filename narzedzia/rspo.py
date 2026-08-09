# -*- coding: utf-8 -*-
"""
Wykaz placówek z rejestru RSPO — z pliku CSV pobranego z rspo.gov.pl.

PO CO TO JEST
Wojtek chce mieć w aplikacji całą aktualną bazę szkół, a Kasia — konkretne
rejony, po których jeżdżą trenerzy. Do 09.08.2026 robiło się to ręcznie: Kasia
pobierała CSV z wyszukiwarki i PRZEPISYWAŁA interesujące szkoły do arkusza.
To narzędzie robi ten sam wybór automatem i zapisuje wykaz w formacie, który
łyka istniejący import RSPO w aplikacji („↑ Import" → źródło RSPO).

DLACZEGO Z PLIKU, A NIE Z API
Oficjalne API (`api.rspo.gov.pl`) wymaga wniosku i do 14 dni na rozpatrzenie
— wniosek składamy osobno, ale wtorkowe wdrożenie nie może na nim wisieć.
Plik CSV jest publiczny, pobiera się go klikiem i zawiera dokładnie te same
dane. Gdy API przyjdzie, dołoży się je jako drugie źródło — reszta ścieżki
(dopasowanie po numerze RSPO, import, raport) zostaje bez zmian.

DLACZEGO NUMER RSPO JEST KLUCZEM
Szkoły zmieniają nazwy („SP nr 12" → „SP nr 12 im. Jana Pawła II"). Gdyby
tożsamość niósł tekst nazwy, każde odświeżenie tworzyłoby duplikat obok
starego rekordu z całą historią kontaktów. Numer RSPO jest stały, więc
odświeżenie aktualizuje TEN SAM wiersz — kolumna `rspo` w `placowki` ma
unikalny indeks i importer dopasowuje właśnie po niej.

UŻYCIE
    python narzedzia/rspo.py rejony  --csv "rspo_2026_08_08.csv"
    python narzedzia/rspo.py wykaz   --csv "rspo_2026_08_08.csv" --do wykaz.xlsx
    python narzedzia/rspo.py wykaz   --csv "…" --wszystkie-slaskie --do calosc.xlsx

Potem: aplikacja → „↑ Import" → źródło **RSPO** → tryb **dopisz**.
Raz na miesiąc ten sam ruch pokazuje, co doszło (raport „nowe/zmienione").
"""
import argparse
import collections
import csv
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KATALOG)

PROFILE = ["prod", "test", "pusta"]

# ---------------------------------------------------------------- rejony

# Rejony działania SILESIA 3D — lista od Kasi z 08.08.2026. Trzymamy je TUTAJ,
# w jednym miejscu, bo to jedyna rzecz, która zmienia się, gdy firma wchodzi
# w nowy teren. W RSPO „powiat" dla miasta na prawach powiatu ma nazwę miasta
# (np. „Katowice"), a dla powiatu ziemskiego jest z małej litery („mikołowski").
POWIATY = [
    "Katowice", "Tychy", "Sosnowiec", "Dąbrowa Górnicza", "Jaworzno",
    "Zabrze", "Ruda Śląska", "Chorzów", "Siemianowice Śląskie",
    "Świętochłowice", "Piekary Śląskie", "Rybnik", "Żory",
    "mikołowski",        # Kasia: „powiat Mikołowski z Mikołowem" (i Orzesze)
    "będziński",         # „Będzin z powiatem"
    "pszczyński",        # „Powiat pszczyński z Pszczyną"
]

# Gminy spoza powyższych powiatów, wskazane pojedynczo.
GMINY = [
    "Knurów",            # gmina w powiecie gliwickim — reszty powiatu nie bierzemy
]

# Typy placówek, w których SILESIA 3D realnie prowadzi zajęcia. Reszty rejestru
# (licea, technika, poradnie, bursy, biblioteki pedagogiczne) nie wciągamy —
# nie po to, żeby oszczędzać miejsce, tylko żeby koordynatorka nie przewijała
# 6 tysięcy pozycji w poszukiwaniu podstawówki. Pełny zrzut: `--wszystkie-typy`.
TYPY_DOMYSLNE = [
    "Szkoła podstawowa",
    "Przedszkole",
    "Punkt przedszkolny",
    "Zespół szkół i placówek oświatowych",   # bywa tu i podstawówka, i przedszkole
    "Młodzieżowy dom kultury",
    "Szkoła podstawowa specjalna",
    "Przedszkole specjalne",
]

WOJEWODZTWO = "ŚLĄSKIE"

# Nagłówki wykazu = nazwy, które rozumie `importer.NAGLOWKI_RSPO`. Dzięki temu
# plik wchodzi do aplikacji bez ani jednej linijki nowego kodu po stronie importu.
NAGLOWKI_WYKAZU = ["Nr RSPO", "Nazwa", "Typ", "Miejscowość", "Adres",
                   "Telefon", "E-mail", "Dyrektor"]


def _czysc(v):
    """
    Zdejmuje „pancerz Excela": RSPO zapisuje część pól jako ="0123", żeby
    arkusz nie zjadł wiodącego zera z numeru telefonu czy kodu pocztowego.
    Bez tego telefon trafiłby do bazy jako `="604616936"`.
    """
    s = (v or "").strip()
    if s.startswith('="') and s.endswith('"'):
        s = s[2:-1]
    return s.strip()


def _otworz(sciezka):
    """CSV z RSPO bywa zapisany z BOM-em; cp1250 to awaryjne wyjście."""
    for kod in ("utf-8-sig", "utf-8", "cp1250"):
        try:
            f = open(sciezka, encoding=kod, newline="")
            f.readline()
            f.seek(0)
            return f, kod
        except UnicodeDecodeError:
            continue
    raise SystemExit("Nie umiem odczytać pliku %s — nieznane kodowanie" % sciezka)


def czytaj(sciezka, wszystkie_typy=False, wszystkie_slaskie=False):
    """
    Zwraca (wiersze, statystyki). Wiersz to słownik gotowy do zapisania
    w wykazie. Placówki zlikwidowane pomijamy — mają datę likwidacji i nie ma
    do kogo w nich dzwonić.
    """
    csv.field_size_limit(10_000_000)
    powiaty = {p.lower() for p in POWIATY}
    gminy = {g.lower() for g in GMINY}
    typy = {t.lower() for t in TYPY_DOMYSLNE}

    stat = collections.Counter()
    wg_typu = collections.Counter()
    wg_powiatu = collections.Counter()
    out = []

    f, kod = _otworz(sciezka)
    with f:
        for w in csv.DictReader(f, delimiter=";"):
            stat["wierszy"] += 1
            if (w.get("Województwo") or "").strip().upper() != WOJEWODZTWO:
                continue
            stat["slaskie"] += 1
            if _czysc(w.get("Data likwidacji")):
                stat["zlikwidowane"] += 1
                continue
            powiat = (w.get("Powiat") or "").strip()
            gmina = (w.get("Gmina") or "").strip()
            if not wszystkie_slaskie and \
                    powiat.lower() not in powiaty and gmina.lower() not in gminy:
                continue
            stat["w_rejonach"] += 1
            typ = (w.get("Typ") or "").strip()
            if not wszystkie_typy and typ.lower() not in typy:
                stat["inny_typ"] += 1
                continue

            ulica = _czysc(w.get("Ulica"))
            nr_bud = _czysc(w.get("Numer budynku"))
            nr_lok = _czysc(w.get("Numer lokalu"))
            adres = " ".join(x for x in (ulica, nr_bud) if x)
            if nr_lok:
                adres += "/" + nr_lok

            out.append({
                "Nr RSPO": _czysc(w.get("Numer RSPO")),
                "Nazwa": _czysc(w.get("Nazwa")),
                "Typ": typ,
                "Miejscowość": _czysc(w.get("Miejscowość")),
                "Adres": adres,
                "Telefon": _czysc(w.get("Telefon")),
                "E-mail": _czysc(w.get("E-mail")),
                "Dyrektor": _czysc(w.get("Imię i nazwisko dyrektora")),
            })
            stat["wybrane"] += 1
            wg_typu[typ] += 1
            wg_powiatu[powiat] += 1

    stat["kodowanie"] = kod
    return out, stat, wg_typu, wg_powiatu


def _drukuj_statystyki(stat, wg_typu, wg_powiatu):
    print("\nPRZEKRÓJ")
    print("  wierszy w pliku          %d" % stat["wierszy"])
    print("  w województwie śląskim   %d" % stat["slaskie"])
    print("  zlikwidowane (pominięte) %d" % stat["zlikwidowane"])
    print("  w naszych rejonach       %d" % stat["w_rejonach"])
    print("  odrzucone przez typ      %d" % stat["inny_typ"])
    print("  DO WYKAZU                %d" % stat["wybrane"])
    print("\n  wg typu:")
    for k, v in wg_typu.most_common():
        print("    %-42s %d" % (k, v))
    print("\n  wg powiatu:")
    for k, v in sorted(wg_powiatu.items()):
        print("    %-28s %d" % (k, v))


def zapisz_xlsx(wiersze, docelowy):
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("Brak openpyxl — zainstaluj: python -m pip install openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "RSPO"
    ws.append(NAGLOWKI_WYKAZU)
    for w in wiersze:
        ws.append([w[k] for k in NAGLOWKI_WYKAZU])
    # szerokości kolumn — plik bywa oglądany przez człowieka przed importem
    for kol, szer in zip("ABCDEFGH", (10, 60, 30, 22, 34, 16, 32, 26)):
        ws.column_dimensions[kol].width = szer
    ws.freeze_panes = "A2"
    wb.save(docelowy)


def zapisz_csv(wiersze, docelowy):
    with open(docelowy, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=NAGLOWKI_WYKAZU, delimiter=";")
        wr.writeheader()
        wr.writerows(wiersze)


# ------------------------------------------------- dopasowanie do numerów RSPO
#
# PROBLEM (zgłoszenie Kasi, 09.08): w zakładce z bazą szkoły figurują pod pełnymi
# nazwami z rejestru, ale leady z umówionym DT — pod tym, co handlowiec wpisał
# w terenie: „MSP 1", „sp32", „Sp 13", „ZS 3 Rybnik". To ta sama szkoła w dwóch
# zapisach. Dopóki nie mają numeru RSPO, każdy kolejny import z rejestru dokłada
# obok NOWY rekord zamiast uzupełnić istniejący.
#
# CZEGO TO NARZĘDZIE NIE ROBI: nie zapisuje niczego do bazy. Produkuje raport
# w Excelu do przejrzenia przez człowieka. Automat, który sam sklei „SP 1"
# z niewłaściwą podstawówką, przeniósłby historię kontaktów pod złą szkołę —
# a tego nie da się cofnąć po tygodniu pracy handlowców.

_RE_NUMER_RSPO = re.compile(r"\bNR\s+(\d+)\b", re.IGNORECASE)
# „MSP 1", „sp32", „Sp 13", „SP nr 7" — numer po kodzie typu placówki
_RE_NUMER_SKROT = re.compile(r"^(?:M|Z)?(?:SP|PM|PP|PS|ZSP|ZPO|ZS)\s*(?:NR\s*)?(\d+)",
                             re.IGNORECASE)


def _bez_prefiksu(s):
    """„05. Knurów" → „Knurów". Prefiks sortujący klienta nie jest częścią nazwy."""
    return re.sub(r"^\s*\d+[a-z]?\.\s*", "", (s or "").strip())


def _fold(s):
    s = (s or "").lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _numer_szkoly(nazwa, z_rejestru=False):
    m = (_RE_NUMER_RSPO if z_rejestru else _RE_NUMER_SKROT).search(nazwa or "")
    return int(m.group(1)) if m else None


def _kategoria(nazwa, typ=""):
    """
    „przedszkole" / „podstawowa" / „inne" — zgrubny podział, ale wystarczy, żeby
    „MSP 2" w Knurowie nie dopasowało się do BRANŻOWEJ SZKOŁY I STOPNIA nr 2
    w tym samym mieście (tak było przed tym rozróżnieniem).
    """
    t = _fold(typ)
    n = _fold(nazwa)
    if "przedszkol" in t or "przedszkol" in n or re.match(r"^(pm|pp|ps) ?\d", n):
        return "przedszkole"
    if "szkola podstawowa" in t or "szkola podstawowa" in n \
            or re.match(r"^m?sp ?\d", n) or re.match(r"^(zsp|zpo) ?\d", n):
        return "podstawowa"
    return "inne"


def dopasuj(profil, sciezka_csv, wszystkie_slaskie=True):
    """
    Zwraca listę wyników dopasowania placówek z bazy do rekordów RSPO.
    Trzy poziomy pewności, bo tyle realnie da się rozróżnić:

      pewne     — nazwa i miejscowość zgadzają się po normalizacji
      numer     — zgadza się typ (szkoła/przedszkole), numer i miejscowość,
                  i w rejestrze jest DOKŁADNIE JEDEN taki kandydat
      niepewne  — kandydatów jest kilku; człowiek wybiera
      brak      — nic sensownego (nazwy typu „Piasek", „EduHub", „29.0")
    """
    os.environ["PROFIL"] = profil
    import db                                  # noqa: E402 — po ustawieniu PROFIL

    rejestr, _, _, _ = czytaj(sciezka_csv, wszystkie_typy=True,
                              wszystkie_slaskie=wszystkie_slaskie)
    po_nazwie = {}
    po_numerze = collections.defaultdict(list)
    for r in rejestr:
        miasto = _fold(r["Miejscowość"])
        po_nazwie.setdefault((_fold(r["Nazwa"]), miasto), r)
        nr = _numer_szkoly(r["Nazwa"], z_rejestru=True)
        if nr is not None:
            po_numerze[(miasto, nr, _kategoria(r["Nazwa"], r["Typ"]))].append(r)

    conn = db.get_conn()
    placowki = conn.execute(
        "SELECT id, nazwa, miejscowosc, typ, rspo FROM placowki ORDER BY nazwa").fetchall()
    conn.close()

    wynik = []
    for p in placowki:
        if (p["rspo"] or "").strip():
            continue                            # już ma numer — nie ruszamy
        miasto = _fold(_bez_prefiksu(p["miejscowosc"]))
        nazwa = (p["nazwa"] or "").strip()
        poz = {"id": p["id"], "nazwa": nazwa, "miejscowosc": p["miejscowosc"],
               "pewnosc": "brak", "rspo": "", "nazwa_rspo": "", "alternatywy": ""}

        traf = po_nazwie.get((_fold(nazwa), miasto))
        if traf:
            poz.update(pewnosc="pewne", rspo=traf["Nr RSPO"], nazwa_rspo=traf["Nazwa"])
            wynik.append(poz)
            continue

        nr = _numer_szkoly(nazwa)
        if nr is not None:
            kand = po_numerze.get((miasto, nr, _kategoria(nazwa, p["typ"] or "")), [])
            if len(kand) == 1:
                poz.update(pewnosc="numer", rspo=kand[0]["Nr RSPO"],
                           nazwa_rspo=kand[0]["Nazwa"])
            elif kand:
                poz.update(pewnosc="niepewne",
                           alternatywy=" | ".join("%s → %s" % (k["Nr RSPO"], k["Nazwa"])
                                                  for k in kand[:5]))
        wynik.append(poz)

    # DUPLIKATY WEWNĄTRZ NASZEJ BAZY. Jeśli dwa nasze rekordy wskazują ten sam
    # numer RSPO, to ta sama szkoła zapisana dwa razy — raz pełną nazwą
    # z rejestru, raz skrótem handlowca („MSP 1" obok „MIEJSKA SZKOŁA
    # PODSTAWOWA NR 1 … W KNUROWIE"). Wychodzi to dopiero teraz, bo dopiero
    # numer RSPO daje wspólny punkt odniesienia. Scalenia NIE robimy automatem:
    # na jednym z tych rekordów wisi już historia kontaktów i umówione DT.
    licznik = collections.Counter(w["rspo"] for w in wynik if w["rspo"])
    for w in wynik:
        if w["rspo"] and licznik[w["rspo"]] > 1:
            w["duplikat"] = "TAK — %d rekordy na ten sam numer RSPO" % licznik[w["rspo"]]
        else:
            w["duplikat"] = ""
    return wynik


def zapisz_raport_dopasowania(wynik, docelowy):
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("Brak openpyxl — zainstaluj: python -m pip install openpyxl")
    naglowki = ["id", "Nazwa w bazie", "Miejscowość", "Pewność",
                "Nr RSPO", "Nazwa w RSPO", "Zdublowane?", "Kandydaci do wyboru"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dopasowanie"
    ws.append(naglowki)
    # najpierw to, co wymaga decyzji człowieka — duplikaty i niepewne
    kolejnosc = {"niepewne": 0, "brak": 1, "numer": 2, "pewne": 3}
    for w in sorted(wynik, key=lambda x: (not x.get("duplikat"),
                                          kolejnosc.get(x["pewnosc"], 9),
                                          x["nazwa"])):
        ws.append([w["id"], w["nazwa"], w["miejscowosc"], w["pewnosc"],
                   w["rspo"], w["nazwa_rspo"], w.get("duplikat", ""),
                   w["alternatywy"]])
    for kol, szer in zip("ABCDEFGH", (7, 46, 22, 11, 10, 52, 34, 60)):
        ws.column_dimensions[kol].width = szer
    ws.freeze_panes = "A2"
    wb.save(docelowy)


def main():
    ap = argparse.ArgumentParser(
        description="Wykaz placówek z CSV rejestru RSPO — do importu w aplikacji.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    pod = ap.add_subparsers(dest="cmd", required=True)

    for nazwa, opis in (("rejony", "pokaż, ile placówek wchodzi (bez zapisu)"),
                        ("wykaz", "zapisz wykaz do pliku .xlsx / .csv")):
        p = pod.add_parser(nazwa, help=opis)
        p.add_argument("--csv", required=True, help="plik pobrany z rspo.gov.pl")
        p.add_argument("--wszystkie-typy", action="store_true",
                       help="bez filtra typów — cały rejestr z rejonów")
        p.add_argument("--wszystkie-slaskie", action="store_true",
                       help="całe województwo, nie tylko nasze rejony")
        if nazwa == "wykaz":
            p.add_argument("--do", required=True, help="plik wynikowy .xlsx albo .csv")

    p = pod.add_parser("dopasuj",
                       help="raport: które placówki w bazie to które rekordy RSPO")
    p.add_argument("--csv", required=True, help="plik pobrany z rspo.gov.pl")
    p.add_argument("--profil", default="test", choices=PROFILE)
    p.add_argument("--do", required=True, help="raport .xlsx do przejrzenia")

    a = ap.parse_args()
    if not os.path.exists(a.csv):
        raise SystemExit("Nie ma pliku: %s" % a.csv)

    if a.cmd == "dopasuj":
        wynik = dopasuj(a.profil, a.csv)
        licz = collections.Counter(w["pewnosc"] for w in wynik)
        print("profil %s — placówek bez numeru RSPO: %d" % (a.profil, len(wynik)))
        for k in ("pewne", "numer", "niepewne", "brak"):
            print("  %-10s %d" % (k, licz.get(k, 0)))
        dubl = [w for w in wynik if w.get("duplikat")]
        if dubl:
            print("\n  UWAGA: %d rekordów wskazuje numer RSPO, który ma też inny"
                  % len(dubl))
            print("  rekord — czyli ta sama szkoła jest w bazie kilka razy:")
            for w in sorted(dubl, key=lambda x: x["rspo"])[:12]:
                print("    RSPO %-8s %-34s | %s" % (w["rspo"], w["nazwa"][:34],
                                                    w["miejscowosc"]))
        if not wynik:
            print("Nie ma czego dopasowywać — wszystkie placówki mają numer RSPO.")
            return 0
        zapisz_raport_dopasowania(wynik, a.do)
        print("\nraport: %s" % a.do)
        print("Nic nie zapisano do bazy — to materiał do przejrzenia. „pewne”")
        print("i „numer” można przyjąć hurtem, „niepewne” wymagają wyboru")
        print("człowieka, a „brak” to zwykle nazwy potoczne (dzielnica, skrót).")
        return 0

    wiersze, stat, wg_typu, wg_powiatu = czytaj(
        a.csv, wszystkie_typy=a.wszystkie_typy,
        wszystkie_slaskie=a.wszystkie_slaskie)
    print("plik: %s (kodowanie %s)" % (a.csv, stat["kodowanie"]))
    _drukuj_statystyki(stat, wg_typu, wg_powiatu)

    if a.cmd == "rejony":
        print("\nTo był podgląd — nic nie zapisano. Wykaz: komenda `wykaz --do plik.xlsx`")
        return 0

    if not wiersze:
        raise SystemExit("Wykaz byłby pusty — sprawdź plik i listę rejonów")
    if a.do.lower().endswith(".csv"):
        zapisz_csv(wiersze, a.do)
    else:
        zapisz_xlsx(wiersze, a.do)
    print("\nzapisano: %s  (%d placówek)" % (a.do, len(wiersze)))
    print("Teraz w aplikacji: Import → źródło RSPO → tryb „dopisz”.")
    print("Dopasowanie idzie po numerze RSPO, więc ponowny import tego samego")
    print("pliku niczego nie zdubluje — zaktualizuje istniejące wpisy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
