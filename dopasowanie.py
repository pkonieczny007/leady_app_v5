# -*- coding: utf-8 -*-
"""
Nadanie numerów RSPO placówkom, które ich nie mają — etap M3 projektu
`docs/poprawka 23.08.2026/PROJEKT_BAZY_RSPO.md`.

PO CO NUMER, SKORO POWIAT JUŻ DZIAŁA
Powiat dało się wywieść z nazwy miejscowości (etap M5) i to wystarczyło do
filtrów. Numer RSPO jest potrzebny do trzech rzeczy, których obejść się nie da:

  1. Dołożenie brakujących SZKÓŁ. W rejestrze jest ich w naszych obszarach 549,
     mamy 539 — ale bez numeru nie sposób powiedzieć, które z tych 549 już
     mamy. Dołożenie „na oko" zrobiłoby ~540 dubli dokładnie tam, gdzie
     handlowcy mają całą swoją pracę.
  2. Prawdziwa miejscowość dla 68 rekordów, które siedziały w workach
     `09. Pszczyna` i `15. Będzin`. Ich miejscowość została po migracji
     przybliżona nazwą miasta powiatowego, bo w danych klienta nigdy jej nie
     było — urwała się przy imporcie razem ze słowem „powiat".
  3. Comiesięczne odświeżenie rejestru. Bez numeru nie ma po czym dopasować
     zmiany nazwy czy telefonu.

CZEGO AUTOMAT NIE ZROBI
Nie wpisze numeru tam, gdzie dwa źródła się nie zgadzają. Złe powiązanie nie
boli od razu — boli przez lata, bo comiesięczne odświeżanie będzie „poprawiać"
nie tę szkołę, a nikt nie skojarzy przyczyny. Rozjazd zawsze idzie do człowieka.

DWA ŹRÓDŁA
  · nasze dopasowanie po nazwie i geografii (kod niżej),
  · plik klienta `POPRAWKA BAZY - RSPO dopasowane.xlsx`, kluczowany po NASZYM
    `id` — więc nie wymaga zgadywania, tylko sprawdzenia, czy nazwa się zgadza
    (plik powstał 20.08 na kopii produkcji; gdyby id się przesunęły, wpisanie
    numeru po samym id podpięłoby szkołę pod cudzy rekord).
"""
import collections
import re

_RE_NUMER = re.compile(r"(?:^|\s|\b)(?:M|Z)?(?:SP|PM|PP|PS|ZSP|ZPO|ZS)\s*(?:NR\s*)?(\d+)",
                       re.IGNORECASE)
_RE_NUMER_REJESTR = re.compile(r"\bNR\s+(\d+)", re.IGNORECASE)

# Werdykty. Kolejność od najmocniejszego — tak też sortuje się raport.
WPISYWANE = ("zgodne", "pewne")


def _fold(s):
    s = (s or "").lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _numer(nazwa, z_rejestru=False):
    m = (_RE_NUMER_REJESTR if z_rejestru else _RE_NUMER).search(nazwa or "")
    return int(m.group(1)) if m else None


def kategoria(nazwa, typ=""):
    """
    Zgrubny podział szkoła/przedszkole/inne — ale bez niego „MSP 2" w Knurowie
    dopasowywało się do BRANŻOWEJ SZKOŁY I STOPNIA NR 2 w tym samym mieście.
    Trzy kubełki wystarczą, bo dopasowujemy w obrębie jednej miejscowości.
    """
    t, n = _fold(typ), _fold(nazwa)
    if "przedszkol" in t or "przedszkol" in n or re.match(r"^(pm|pp|ps) ?\d", n):
        return "przedszkole"
    if "szkola podstawowa" in t or "szkola podstawowa" in n \
            or re.match(r"^m?sp ?\d", n) or re.match(r"^(zsp|zpo) ?\d", n):
        return "podstawowa"
    return "inne"


def _indeksy(conn):
    """Trzy sposoby trafienia w rekord rejestru — od najpewniejszego."""
    po_nazwie_miejsc = collections.defaultdict(list)
    po_nazwie_powiat = collections.defaultdict(list)
    po_numerze = collections.defaultdict(list)
    for r in conn.execute("SELECT rspo, nazwa, typ, powiat, miejscowosc "
                          "FROM rspo_rejestr WHERE nieobecna_od IS NULL"):
        kat = kategoria(r["nazwa"], r["typ"])
        po_nazwie_miejsc[(_fold(r["nazwa"]), _fold(r["miejscowosc"]))].append(r)
        po_nazwie_powiat[(_fold(r["nazwa"]), _fold(r["powiat"]))].append(r)
        nr = _numer(r["nazwa"], z_rejestru=True)
        if nr is not None:
            po_numerze[(_fold(r["powiat"]), nr, kat)].append(r)
    return po_nazwie_miejsc, po_nazwie_powiat, po_numerze


def _po_wsi_w_nazwie(conn, nazwa, powiat, kat):
    """
    Kandydaci z miejscowości, której nazwa siedzi w NAZWIE naszego rekordu.

    Bierze się to z worków powiatowych: „Sp Góra" i „Sp Miedźna" mają
    miejscowość `Pszczyna` (bo tyle zostało po urwanym słowie „powiat"),
    ale handlowiec dopisał wieś do nazwy szkoły. Szukamy więc nazwy wsi
    w tekście — od najdłuższej, żeby „Wisła Wielka" wygrała z „Wisłą".
    """
    igla = _fold(nazwa)
    wsie = sorted({r[0] for r in conn.execute(
        "SELECT DISTINCT miejscowosc FROM rspo_rejestr WHERE powiat=? "
        "AND miejscowosc IS NOT NULL AND miejscowosc <> ''", (powiat,))},
        key=lambda s: -len(s))
    for wies in wsie:
        f = _fold(wies)
        # `w mizerowie` nie zawiera `mizerow`, więc porównujemy po RDZENIU:
        # odmiana zmienia końcówkę, nie początek.
        rdzen = f[:max(4, len(f) - 2)]
        if len(rdzen) < 4 or rdzen not in igla:
            continue
        kand = [r for r in conn.execute(
            "SELECT rspo, nazwa, typ, miejscowosc FROM rspo_rejestr "
            "WHERE powiat=? AND lower(miejscowosc)=lower(?) AND nieobecna_od IS NULL",
            (powiat, wies))]
        kand = [k for k in kand if kategoria(k["nazwa"], k["typ"]) == kat]
        if kand:
            return kand
    return []


def _z_pliku_klienta(sciezka):
    """{id naszego rekordu: (numer rspo, nazwa z pliku)} — do kontroli krzyżowej."""
    if not sciezka:
        return {}
    import openpyxl
    wb = openpyxl.load_workbook(sciezka, read_only=True, data_only=True)
    ws = wb["Szkoły"] if "Szkoły" in wb.sheetnames else wb[wb.sheetnames[0]]
    out, naglowki = {}, None
    for wiersz in ws.iter_rows(values_only=True):
        if naglowki is None:
            naglowki = [str(c or "").strip() for c in wiersz]
            continue
        d = dict(zip(naglowki, wiersz))
        try:
            ident = int(str(d.get("id") or "").strip())
            numer = int(str(d.get("Nr RSPO") or "").strip())
        except (TypeError, ValueError):
            continue
        out[ident] = (numer, str(d.get("Nazwa placówki") or "").strip())
    wb.close()
    return out


def dopasuj(conn, plik_klienta=None):
    """
    Lista wierszy decyzyjnych — po jednym na placówkę bez numeru RSPO.

    Kolejność prób jest kolejnością pewności:
      1. nazwa + miejscowość zgodne co do znaku,
      2. nazwa + POWIAT — dla 68 rekordów z worków powiatowych miejscowość jest
         przybliżeniem, więc krok 1 by ich nie złapał, a nazwa urzędowa
         w obrębie powiatu jest praktycznie unikalna,
      3. numer szkoły + powiat + kategoria, gdy w rejestrze jest DOKŁADNIE
         jeden taki kandydat.
    """
    po_nm, po_np, po_nr = _indeksy(conn)
    klient = _z_pliku_klienta(plik_klienta)

    wynik = []
    for p in conn.execute(
            "SELECT id, nazwa, miejscowosc, powiat, typ FROM placowki "
            "WHERE rspo IS NULL OR rspo = '' ORDER BY powiat, miejscowosc, nazwa"):
        nazwa = (p["nazwa"] or "").strip()
        w = {"id": p["id"], "nazwa": nazwa, "miejscowosc": p["miejscowosc"] or "",
             "powiat": p["powiat"] or "", "nasz": None, "jak": "", "nazwa_rspo": "",
             "klient": None, "alternatywy": "", "werdykt": "brak"}

        trafienia = po_nm.get((_fold(nazwa), _fold(p["miejscowosc"]))) or []
        jak = "nazwa+miejscowość"
        if len(trafienia) != 1:
            trafienia = po_np.get((_fold(nazwa), _fold(p["powiat"]))) or []
            jak = "nazwa+powiat"
        if len(trafienia) != 1:
            nr = _numer(nazwa)
            if nr is not None:
                trafienia = po_nr.get((_fold(p["powiat"]), nr,
                                       kategoria(nazwa, p["typ"] or ""))) or []
                jak = "numer w nazwie+powiat"
            else:
                trafienia = []
        if len(trafienia) != 1 and not trafienia:
            # OSTATNIA PRÓBA: miejscowość schowana w NAZWIE, nie w kolumnie.
            # „Sp Miedźna", „Sp Góra", „Sp Frydyk" siedzą pod miejscowością
            # `Pszczyna`, bo tyle zostało z worka powiatowego — ale nazwę wsi
            # handlowiec dopisał do nazwy szkoły. Z tego NIGDY nie wpisujemy
            # numeru automatem: to podpowiedź do pliku decyzyjnego, żeby Kasia
            # wybierała z trzech kandydatów zamiast szukać od zera.
            trafienia = _po_wsi_w_nazwie(conn, nazwa, p["powiat"],
                                         kategoria(nazwa, p["typ"] or ""))
            if trafienia:
                w["alternatywy"] = " | ".join(
                    "%s → %s (%s)" % (t["rspo"], t["nazwa"], t["miejscowosc"])
                    for t in trafienia[:5])
                w["werdykt"] = "niepewne"
            trafienia = []              # podpowiedź, nie trafienie

        if len(trafienia) == 1:
            w["nasz"] = trafienia[0]["rspo"]
            w["nazwa_rspo"] = trafienia[0]["nazwa"]
            w["jak"] = jak
        elif trafienia:
            w["alternatywy"] = " | ".join("%s → %s" % (t["rspo"], t["nazwa"])
                                          for t in trafienia[:5])
            w["werdykt"] = "niepewne"

        z_pliku = klient.get(p["id"])
        if z_pliku:
            # Plik powstał na kopii produkcji z 20.08 i jest kluczowany po id.
            # Gdyby id się przesunęły, wpisanie numeru po samym id podpięłoby
            # szkołę pod cudzy rekord — dlatego wpierw sprawdzamy nazwę.
            if _fold(z_pliku[1]) == _fold(nazwa):
                w["klient"] = z_pliku[0]
            else:
                w["alternatywy"] = (w["alternatywy"] + " ; " if w["alternatywy"] else "") \
                    + "plik klienta ma pod tym id inną placówkę: %s" % z_pliku[1]

        if w["nasz"] and w["klient"]:
            w["werdykt"] = "zgodne" if w["nasz"] == w["klient"] else "rozjazd"
        elif w["nasz"]:
            w["werdykt"] = "pewne"
        elif w["klient"]:
            # Sam plik klienta to za mało: jego dopasowania nie sprawdzaliśmy,
            # a numer wpisany omyłkowo zwiąże nas z cudzą szkołą na lata.
            w["werdykt"] = "tylko plik klienta"
        wynik.append(w)

    # DUBLE WEWNĄTRZ NASZEJ BAZY — dopiero numer daje wspólny punkt odniesienia.
    # Dwa nasze rekordy wskazujące ten sam numer to ta sama szkoła zapisana
    # dwa razy: raz pełną nazwą, raz skrótem handlowca. Numeru nie dostaje ŻADEN
    # z nich — na jednym wisi historia, na drugim jedyne umówione DT, więc wybór
    # nie jest techniczny i należy do człowieka (etap M4).
    licznik = collections.Counter(w["nasz"] for w in wynik if w["nasz"])
    zajete = {int(r[0]) for r in conn.execute(
        "SELECT rspo FROM placowki WHERE rspo IS NOT NULL AND rspo <> ''")}
    for w in wynik:
        if w["nasz"] and licznik[w["nasz"]] > 1:
            w["werdykt"] = "dubel"
            w["alternatywy"] = ("%d nasze rekordy wskazują ten sam numer"
                                % licznik[w["nasz"]])
        elif w["nasz"] and w["nasz"] in zajete:
            # Numer wzięty już przez inną placówkę (np. dołożoną z rejestru).
            w["werdykt"] = "numer zajęty"
    return wynik


def wpisz(conn, wiersze, kto="migracja-rspo"):
    """
    Wpisuje numery tylko tam, gdzie werdykt na to pozwala. Każdy UPDATE zostawia
    ślad w `log`, żeby dało się to odkręcić listą, a nie z pamięci.
    """
    import db
    n = 0
    for w in wiersze:
        if w["werdykt"] not in WPISYWANE or not w["nasz"]:
            continue
        conn.execute("UPDATE placowki SET rspo=?, updated_at=datetime('now') WHERE id=?",
                     (str(w["nasz"]), w["id"]))
        lead = conn.execute("SELECT id FROM leady WHERE placowka_id=? ORDER BY id LIMIT 1",
                            (w["id"],)).fetchone()
        db.zapisz_log(conn, lead_id=lead["id"] if lead else None, kto=kto,
                      co="migracja-rspo: numer", pole="rspo", przed=None,
                      po="%s (%s)" % (w["nasz"], w["jak"]))
        n += 1
    conn.commit()
    return n


def do_xlsx(wiersze, docelowy):
    """Plik decyzyjny dla koordynatorki — tylko to, czego automat nie ruszył."""
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Do decyzji"
    naglowki = ["id", "Nazwa u nas", "Miejscowość", "Powiat", "Werdykt",
                "Nasz numer", "Numer z pliku klienta", "Nazwa w rejestrze",
                "Kandydaci / uwagi", "DECYZJA — wpisz numer RSPO"]
    ws.append(naglowki)
    for c in ws[1]:
        c.font = Font(bold=True)
    for w in wiersze:
        if w["werdykt"] in WPISYWANE:
            continue
        ws.append([w["id"], w["nazwa"], w["miejscowosc"], w["powiat"], w["werdykt"],
                   w["nasz"] or "", w["klient"] or "", w["nazwa_rspo"],
                   w["alternatywy"], ""])
    for kol, szer in zip("ABCDEFGHIJ", (7, 48, 18, 18, 16, 12, 14, 48, 60, 22)):
        ws.column_dimensions[kol].width = szer
    ws.freeze_panes = "A2"
    wb.save(docelowy)
    return docelowy


def wczytaj_decyzje(sciezka):
    """Plik po ręcznym uzupełnieniu → [{id, nasz, jak, werdykt}] gotowe dla `wpisz`."""
    import openpyxl
    wb = openpyxl.load_workbook(sciezka, read_only=True, data_only=True)
    ws = wb.active
    out, naglowki = [], None
    for wiersz in ws.iter_rows(values_only=True):
        if naglowki is None:
            naglowki = [str(c or "").strip() for c in wiersz]
            continue
        d = dict(zip(naglowki, wiersz))
        try:
            ident = int(str(d.get("id") or "").strip())
            numer = int(str(d.get("DECYZJA — wpisz numer RSPO") or "").strip())
        except (TypeError, ValueError):
            continue
        out.append({"id": ident, "nasz": numer, "jak": "decyzja człowieka",
                    "werdykt": "zgodne"})
    wb.close()
    return out
