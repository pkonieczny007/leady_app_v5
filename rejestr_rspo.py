# -*- coding: utf-8 -*-
"""
Lustro rejestru RSPO — tabele `rspo_rejestr`, `rspo_importy`, `rspo_zmiany`.

Kod przejęty z aplikacji pomocniczej `rspo_app` (etap M1 projektu
`docs/poprawka 23.08.2026/PROJEKT_BAZY_RSPO.md`), gdzie przeszedł próbę na
realnych plikach. Tu zmieniają się tylko nazwy tabel i połączenie z bazą.

DLACZEGO LUSTRO TO OSOBNA TABELA, A NIE KOLUMNY W `placowki`
Rejestr i baza robocza mają SPRZECZNE polityki nadpisywania. W lustrze wygrywa
rejestr: zmieniła się nazwa — podmieniamy. W `placowki` wygrywa człowiek:
telefon do sekretariatu wpisany przez handlowca w terenie jest cenniejszy niż
telefon z rejestru i żaden import nie ma prawa go zetrzeć. W jednej tabeli
jedna z tych zasad musiałaby po cichu przegrywać — a taka strata wychodzi
dopiero, gdy ktoś dzwoni pod zły numer.

ZASADA WGRYWANIA: PLIK JEST OBRAZEM REJESTRU, LUSTRO JEGO KOPIĄ
  1. czego nie było — dopisuje
  2. co się zmieniło — nadpisuje i notuje w dzienniku `rspo_zmiany` co dokładnie
  3. czego w pliku zabrakło — OZNACZA (`nieobecna_od`), nigdy nie kasuje

Punkt 3 jest ważniejszy, niż wygląda: eksport z wyszukiwarki rejestru ma
kolumnę „Data likwidacji" PUSTĄ we wszystkich 56 tysiącach wierszy (oddaje
wyłącznie czynne placówki). Zamknięcia szkoły NIE DA SIĘ odczytać z kolumny —
widać je tylko jako różnicę między dwoma wgraniami. Dlatego też bezpiecznik:
gdyby ktoś wgrał plik przefiltrowany w wyszukiwarce (same Katowice), naiwne
porównanie oznaczyłoby 96% lustra jako „zniknięte" — przy dużym ubytku
wstrzymujemy oznaczanie i mówimy o tym wprost.

Duplikat nie może powstać: `rspo` jest kluczem głównym tabeli. To warunek
narzucony przez bazę, nie staranność w kodzie.
"""
import collections
import csv
import os
import re
import time

csv.field_size_limit(10_000_000)

WOJEWODZTWO_DOMYSLNE = "ŚLĄSKIE"

# ---------------------------------------------------------------------------
# Pola rejestru, które trzymamy w lustrze — (klucz, nagłówek w pliku, typ,
# etykieta). Z 54 kolumn eksportu bierzemy te, które czemuś służą:
#   powiat/gmina     — oś filtrów i obszarów działania (sedno całej migracji)
#   liczba_uczniow   — szkoła na 600 dzieci to inny potencjał niż punkt na 12
#   organ_nazwa      — 6 na 10 przedszkoli prowadzi ten sam organ co szkoła,
#                      którą już mamy; to nie jest zimny telefon
#   rspo_nadrzedny   — zespół szkolno-przedszkolny to w rejestrze KILKA wierszy
#                      wskazujących na siebie; bez tego pola nie da się ich
#                      z powrotem skleić w jedną szkołę klienta
# ---------------------------------------------------------------------------

POLA_RSPO = [
    ("rspo",                "Numer RSPO",                   "int",  "Nr RSPO"),
    ("nazwa",               "Nazwa",                        "text", "Nazwa"),
    ("typ",                 "Typ",                          "text", "Typ"),
    ("regon",               "REGON",                        "text", "REGON"),
    ("nip",                 "NIP",                          "text", "NIP"),

    ("wojewodztwo",         "Województwo",                  "text", "Województwo"),
    ("powiat",              "Powiat",                       "text", "Powiat"),
    ("gmina",               "Gmina",                        "text", "Gmina"),
    ("miejscowosc",         "Miejscowość",                  "text", "Miejscowość"),
    ("rodzaj_miejscowosci", "Rodzaj miejscowości",          "text", "Rodzaj miejscowości"),
    ("teryt_gmina",         "Kod terytorialny gmina",       "text", "TERYT gminy"),

    ("ulica",               "Ulica",                        "text", "Ulica"),
    ("nr_budynku",          "Numer budynku",                "text", "Nr budynku"),
    ("nr_lokalu",           "Numer lokalu",                 "text", "Nr lokalu"),
    ("kod_pocztowy",        "Kod pocztowy",                 "text", "Kod pocztowy"),
    ("poczta",              "Poczta",                       "text", "Poczta"),

    ("telefon",             "Telefon",                      "text", "Telefon"),
    ("faks",                "Faks",                         "text", "Faks"),
    ("email",               "E-mail",                       "text", "E-mail"),
    ("www",                 "Strona www",                   "text", "Strona www"),
    ("dyrektor",            "Imię i nazwisko dyrektora",    "text", "Dyrektor"),

    ("publicznosc",         "Publiczność status",           "text", "Publiczność"),
    ("kategoria_uczniow",   "Kategoria uczniów",            "text", "Kategoria uczniów"),
    ("specyfika",           "Specyfika placówki",           "text", "Specyfika"),
    ("liczba_uczniow",      "Liczba uczniów",               "int",  "Uczniów"),
    ("jezyki",              "Języki nauczane",              "text", "Języki"),

    ("organ_typ",           "Typ organu prowadzącego",      "text", "Typ organu"),
    ("organ_nazwa",         "Nazwa organu prowadzącego",    "text", "Organ prowadzący"),
    ("organ_regon",         "REGON organu prowadzącego",    "text", "REGON organu"),

    ("miejsce_w_strukturze", "Miejsce w strukturze",        "text", "Miejsce w strukturze"),
    ("rspo_nadrzedny",      "RSPO podmiotu nadrzędnego",    "text", "RSPO nadrzędnego"),
    ("nazwa_nadrzedna",     "Nazwa podmiotu nadrzędnego",   "text", "Podmiot nadrzędny"),

    ("data_zalozenia",      "Data założenia",               "text", "Data założenia"),
    ("data_likwidacji",     "Data likwidacji",              "text", "Data likwidacji"),
]

KLUCZE_RSPO = [p[0] for p in POLA_RSPO]
NAGLOWKI_RSPO = {p[1]: p[0] for p in POLA_RSPO}
ETYKIETY = {p[0]: p[3] for p in POLA_RSPO}

# Pola, których zmianę notujemy w dzienniku. Wszystkie poza kluczem i polami
# porządkowymi — dziennik ma odpowiadać na „co się zmieniło od zeszłego
# miesiąca", nie „co przestawiono w TERYT".
POLA_SLEDZONE = [k for k in KLUCZE_RSPO
                 if k not in ("rspo", "teryt_gmina", "data_zalozenia")]

# Bezpiecznik zniknięć — odpala się dopiero, gdy ubytek jest JEDNOCZEŚNIE duży
# względnie i bezwzględnie. Przy comiesięcznym odświeżeniu realny ubytek to
# promile; próg 25 sztuk chroni małe bazy testowe przed fałszywym alarmem.
PROG_ZNIKNIEC = 0.20
MIN_ZNIKNIEC = 25

# Limit wpisów dziennika przy jednym wgraniu — zabezpieczenie przed dziennikiem
# na 200 tysięcy wierszy, gdyby rejestr przestawił format zapisu jakiegoś pola.
LIMIT_ZMIAN = 5000


# ---------------------------------------------------------------------------
# Schemat
# ---------------------------------------------------------------------------

def zaloz_tabele(conn):
    """Tabele lustra. Nie dotykają niczego istniejącego — M1 jest addytywny."""
    kolumny = []
    for klucz, _n, typ, _e in POLA_RSPO:
        if klucz == "rspo":
            # Klucz główny wprost z rejestru — duplikat numeru nie może
            # powstać niezależnie od jakości kodu wyżej.
            kolumny.append("rspo INTEGER PRIMARY KEY")
        else:
            kolumny.append("%s %s" % (klucz, "INTEGER" if typ == "int" else "TEXT"))
    kolumny += [
        "pierwszy_import TEXT",       # kiedy pojawiła się w lustrze
        "ostatni_import TEXT",        # ostatnie wgranie, które ją widziało
        "ostatnia_zmiana TEXT",       # ostatnie wgranie, które coś w niej zmieniło
        "nieobecna_od TEXT",          # zniknęła z rejestru — oznaczona, nie skasowana
    ]
    conn.execute("CREATE TABLE IF NOT EXISTS rspo_rejestr (%s)" % ", ".join(kolumny))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rspo_importy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kiedy TEXT, plik TEXT, rozmiar_mb REAL, zakres TEXT,
            wierszy_w_pliku INTEGER, w_zakresie INTEGER,
            nowych INTEGER, zmienionych INTEGER, bez_zmian INTEGER,
            zniknelo INTEGER, wrocilo INTEGER, sekundy REAL, uwagi TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rspo_zmiany (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER, rspo INTEGER, nazwa TEXT,
            pole TEXT, bylo TEXT, jest TEXT
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rspo_rejestr_powiat "
                 "ON rspo_rejestr (powiat)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rspo_rejestr_gmina "
                 "ON rspo_rejestr (gmina)")


# ---------------------------------------------------------------------------
# Czytanie pliku z rspo.gov.pl (CSV z wyszukiwarki albo XLSX „poprawiony"
# po drodze Excelem)
# ---------------------------------------------------------------------------

_PANCERZ = re.compile(r'^="(.*)"$', re.S)


def czysc(v):
    """
    Zdejmuje „pancerz Excela" `="0123"` i przycina białe znaki. Rejestr owija
    tak pola z wiodącym zerem (telefony, kody pocztowe, REGON) — bez zdjęcia
    telefon trafiłby do bazy jako `="604616936"`.
    """
    s = ("" if v is None else str(v)).strip()
    m = _PANCERZ.match(s)
    if m:
        s = m.group(1)
    return s.strip()


def _otworz_csv(sciezka):
    """CSV z RSPO bywa z BOM-em, bywa w cp1250 — próbujemy po kolei."""
    for kod in ("utf-8-sig", "utf-8", "cp1250"):
        try:
            f = open(sciezka, encoding=kod, newline="")
            f.readline()
            f.seek(0)
            return f
        except UnicodeDecodeError:
            continue
    raise ValueError("Nie umiem odczytać pliku — nieznane kodowanie")


def _wiersze_csv(sciezka):
    f = _otworz_csv(sciezka)
    with f:
        # Rejestr daje średnik, ale gdyby kiedyś dał przecinek, lepiej to
        # wykryć niż wczytać cały plik jako jedną kolumnę.
        probka = f.readline()
        f.seek(0)
        sep = ";" if probka.count(";") >= probka.count(",") else ","
        for w in csv.DictReader(f, delimiter=sep):
            yield w


def _wiersze_xlsx(sciezka):
    import openpyxl
    wb = openpyxl.load_workbook(sciezka, read_only=True, data_only=True)
    ws = wb.active
    naglowki = None
    for wiersz in ws.iter_rows(values_only=True):
        if naglowki is None:
            naglowki = [czysc(c) for c in wiersz]
            continue
        yield dict(zip(naglowki, wiersz))
    wb.close()


def sprawdz_naglowki(sciezka):
    """
    (ok, brakujace, znalezione) — czy plik w ogóle wygląda na eksport z RSPO.
    Komunikat „nie znalazłem kolumny »Numer RSPO«" jest użyteczny; `KeyError`
    w połowie importu 56 tysięcy wierszy nie jest.
    """
    zrodlo = _wiersze_xlsx if sciezka.lower().endswith((".xlsx", ".xlsm")) else _wiersze_csv
    try:
        pierwszy = next(iter(zrodlo(sciezka)))
    except StopIteration:
        return False, ["plik jest pusty"], []
    znalezione = [czysc(k) for k in pierwszy.keys() if k]
    wymagane = ["Numer RSPO", "Nazwa", "Typ", "Województwo", "Powiat", "Gmina"]
    brak = [k for k in wymagane if k not in znalezione]
    return (not brak), brak, znalezione


def czytaj(sciezka, wojewodztwo=WOJEWODZTWO_DOMYSLNE):
    """
    (lista_wierszy, statystyki). `wojewodztwo=None` → cała Polska; domyślnie
    ŚLĄSKIE, bo 56 tysięcy wierszy z kraju to 50 tysięcy pozycji, po których
    nikt nigdy nie zadzwoni.
    """
    zrodlo = _wiersze_xlsx if sciezka.lower().endswith((".xlsx", ".xlsm")) else _wiersze_csv
    woj = (wojewodztwo or "").strip().upper()

    stat = collections.Counter()
    wg_typu = collections.Counter()
    wg_powiatu = collections.Counter()
    out = []
    widziane = set()

    for w in zrodlo(sciezka):
        stat["wierszy"] += 1
        if woj and czysc(w.get("Województwo")).upper() != woj:
            continue
        # W eksporcie z wyszukiwarki ta kolumna jest pusta w CAŁYM pliku —
        # filtr to zabezpieczenie na wypadek innego eksportu, nie realne sito.
        if czysc(w.get("Data likwidacji")):
            stat["zlikwidowane"] += 1
            continue

        rekord = {}
        for klucz, naglowek, typ, _et in POLA_RSPO:
            wartosc = czysc(w.get(naglowek))
            if typ == "int":
                # „0" uczniów to prawdziwe zero, pusty string to brak danych —
                # dwie różne rzeczy przy sortowaniu „od największej szkoły".
                rekord[klucz] = int(wartosc) if wartosc.isdigit() else None
            else:
                rekord[klucz] = wartosc or None

        if not rekord["rspo"]:
            stat["bez_numeru"] += 1
            continue
        if rekord["rspo"] in widziane:
            stat["powtorki_w_pliku"] += 1
            continue
        widziane.add(rekord["rspo"])

        out.append(rekord)
        stat["w_zakresie"] += 1
        wg_typu[rekord["typ"] or "—"] += 1
        wg_powiatu[rekord["powiat"] or "—"] += 1

    stat["wg_typu"] = wg_typu
    stat["wg_powiatu"] = wg_powiatu
    return out, stat


def adres(rekord):
    """„ul. Orla 6/8" z trzech kolumn rejestru — aplikacja leadów chce jedną."""
    czesci = [rekord.get("ulica") or "", rekord.get("nr_budynku") or ""]
    a = " ".join(c for c in czesci if c).strip()
    if rekord.get("nr_lokalu"):
        a = (a + "/" + rekord["nr_lokalu"]).strip("/")
    return a


def rozmiar_mb(sciezka):
    try:
        return round(os.path.getsize(sciezka) / (1024 * 1024), 1)
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Wgrywanie do lustra
# ---------------------------------------------------------------------------

def wgraj(conn, sciezka, nazwa_pliku=None, wojewodztwo=WOJEWODZTWO_DOMYSLNE,
          wykryj_znikniete=True):
    """
    Wgrywa plik do lustra i zwraca raport (słownik do pokazania).
    Połączenie przychodzi z zewnątrz (db.get_conn()) — commit robimy tu,
    ale zamknięcie należy do wołającego, jak wszędzie w aplikacji.
    """
    import datetime as _dt
    start = time.time()
    zaloz_tabele(conn)
    nazwa_pliku = nazwa_pliku or os.path.basename(sciezka)
    wiersze, stat = czytaj(sciezka, wojewodztwo=wojewodztwo)
    zakres = wojewodztwo or "cała Polska"
    dzis = _dt.date.today().isoformat()

    # Stan sprzed wgrania — tylko pola śledzone, żeby nie ciągnąć całej tabeli
    # do pamięci przy pliku ogólnopolskim.
    kolumny = ["rspo"] + POLA_SLEDZONE + ["nieobecna_od", "wojewodztwo"]
    kolumny = list(dict.fromkeys(kolumny))
    przed = {}
    for w in conn.execute("SELECT %s FROM rspo_rejestr" % ", ".join(kolumny)):
        przed[w["rspo"]] = dict(w)

    nowe, zmienione, bez_zmian, wrocilo = [], [], 0, 0
    dziennik = []

    # Jedna transakcja na całość — przy 6 tysiącach wierszy to różnica między
    # ułamkiem sekundy a minutami; commit na końcu.
    for r in wiersze:
        stary = przed.get(r["rspo"])
        if stary is None:
            kol = KLUCZE_RSPO + ["pierwszy_import", "ostatni_import"]
            conn.execute("INSERT INTO rspo_rejestr (%s) VALUES (%s)"
                         % (", ".join(kol), ", ".join("?" * len(kol))),
                         [r.get(k) for k in KLUCZE_RSPO] + [dzis, dzis])
            nowe.append(r["rspo"])
            continue

        roznice = [(p, stary.get(p), r.get(p)) for p in POLA_SLEDZONE
                   if _inne(stary.get(p), r.get(p))]
        wrocila = stary.get("nieobecna_od") is not None
        if wrocila:
            wrocilo += 1

        if roznice or wrocila:
            ustaw = ["%s=?" % k for k in KLUCZE_RSPO if k != "rspo"]
            wartosci = [r.get(k) for k in KLUCZE_RSPO if k != "rspo"]
            ustaw.append("ostatni_import=?"); wartosci.append(dzis)
            if roznice:
                ustaw.append("ostatnia_zmiana=?"); wartosci.append(dzis)
            if wrocila:
                ustaw.append("nieobecna_od=NULL")
            wartosci.append(r["rspo"])
            conn.execute("UPDATE rspo_rejestr SET %s WHERE rspo=?" % ", ".join(ustaw),
                         wartosci)
            if roznice:
                zmienione.append(r["rspo"])
                for pole, bylo, jest in roznice[:20]:
                    if len(dziennik) < LIMIT_ZMIAN:
                        dziennik.append((r["rspo"], r.get("nazwa"), pole,
                                         _tekst(bylo), _tekst(jest)))
        else:
            conn.execute("UPDATE rspo_rejestr SET ostatni_import=? WHERE rspo=?",
                         (dzis, r["rspo"]))
            bez_zmian += 1

    # --- zniknięcia ---------------------------------------------------------
    zniknelo, uwagi = 0, []
    w_pliku = {r["rspo"] for r in wiersze}
    if wykryj_znikniete:
        kandydaci = [rspo for rspo, s in przed.items()
                     if rspo not in w_pliku and s.get("nieobecna_od") is None
                     and _w_zakresie(s, wojewodztwo)]
        baza_w_zakresie = sum(1 for s in przed.values()
                              if _w_zakresie(s, wojewodztwo))
        if (baza_w_zakresie and len(kandydaci) > MIN_ZNIKNIEC
                and len(kandydaci) > PROG_ZNIKNIEC * baza_w_zakresie):
            uwagi.append(
                "Wstrzymano oznaczanie zniknięć: w pliku zabrakło %d z %d placówek "
                "(%.0f%%). To wygląda na plik przefiltrowany w wyszukiwarce, "
                "a nie na pełny wykaz — nic nie oznaczono."
                % (len(kandydaci), baza_w_zakresie,
                   100.0 * len(kandydaci) / baza_w_zakresie))
        else:
            for rspo in kandydaci:
                conn.execute("UPDATE rspo_rejestr SET nieobecna_od=? WHERE rspo=?",
                             (dzis, rspo))
            zniknelo = len(kandydaci)
    else:
        uwagi.append("Wykrywanie zniknięć wyłączone przy tym wgraniu.")

    if stat.get("powtorki_w_pliku"):
        uwagi.append("W pliku %d wierszy powtarzało numer RSPO — wzięliśmy "
                     "pierwsze wystąpienie." % stat["powtorki_w_pliku"])
    if stat.get("bez_numeru"):
        uwagi.append("%d wierszy bez numeru RSPO — pominięte." % stat["bez_numeru"])

    sekundy = round(time.time() - start, 1)
    cur = conn.execute("""
        INSERT INTO rspo_importy (kiedy, plik, rozmiar_mb, zakres, wierszy_w_pliku,
                                  w_zakresie, nowych, zmienionych, bez_zmian,
                                  zniknelo, wrocilo, sekundy, uwagi)
        VALUES (datetime('now'),?,?,?,?,?,?,?,?,?,?,?,?)
    """, (nazwa_pliku, rozmiar_mb(sciezka), zakres,
          stat["wierszy"], stat["w_zakresie"], len(nowe), len(zmienione),
          bez_zmian, zniknelo, wrocilo, sekundy, " ".join(uwagi) or None))
    import_id = cur.lastrowid
    for rspo, nazwa, pole, bylo, jest in dziennik:
        conn.execute("INSERT INTO rspo_zmiany (import_id, rspo, nazwa, pole, bylo, jest)"
                     " VALUES (?,?,?,?,?,?)", (import_id, rspo, nazwa, pole, bylo, jest))
    conn.commit()

    return {
        "import_id": import_id, "plik": nazwa_pliku, "zakres": zakres,
        "wierszy_w_pliku": stat["wierszy"], "w_zakresie": stat["w_zakresie"],
        "nowych": len(nowe), "zmienionych": len(zmienione), "bez_zmian": bez_zmian,
        "zniknelo": zniknelo, "wrocilo": wrocilo, "sekundy": sekundy,
        "razem_w_lustrze": conn.execute(
            "SELECT COUNT(*) FROM rspo_rejestr").fetchone()[0],
        "uwagi": uwagi,
        "wg_typu": stat["wg_typu"].most_common(),
        "wg_powiatu": sorted(stat["wg_powiatu"].items(), key=lambda x: -x[1]),
        "zmiany": dziennik[:200],
    }


def historia(conn, ile=20):
    return [dict(w) for w in conn.execute(
        "SELECT * FROM rspo_importy ORDER BY id DESC LIMIT ?", (ile,))]


def zmiany_importu(conn, import_id, ile=500):
    return [dict(w) for w in conn.execute(
        "SELECT * FROM rspo_zmiany WHERE import_id=? ORDER BY nazwa, pole LIMIT ?",
        (import_id, ile))]


# ---------------------------------------------------------------------------

def _inne(a, b):
    """`None` i pusty string to to samo — rejestr raz oddaje puste pole, raz
    spację, a wpis „telefon: (puste) → (puste)" w dzienniku byłby szumem."""
    a = (a if a is not None else "")
    b = (b if b is not None else "")
    if isinstance(a, str):
        a = a.strip()
    if isinstance(b, str):
        b = b.strip()
    return a != b


def _tekst(v):
    return "" if v is None else str(v)


def _w_zakresie(stan, wojewodztwo):
    """Bez tego wgranie pliku ze śląskiego oznaczyłoby jako „zniknięte"
    wszystko, co ktoś kiedyś wciągnął z innych województw."""
    if not wojewodztwo:
        return True
    return (stan.get("wojewodztwo") or "").upper() == wojewodztwo.upper()
