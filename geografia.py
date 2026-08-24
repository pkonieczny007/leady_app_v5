# -*- coding: utf-8 -*-
"""
Geografia placówek — powiat i gmina z rejestru RSPO (etap M5 projektu
`docs/poprawka 23.08.2026/PROJEKT_BAZY_RSPO.md`).

PO CO POWIAT, SKORO JEST MIEJSCOWOŚĆ
Bo klient prowadzi sprzedaż powiatami, a nasza lista miejscowości powstała
z ręcznych wpisów w arkuszu i miesza trzy skale naraz: miasta (`08. Katowice`),
wsie dopisane z ręki (`23. Strzyżowice`) i WORKI POWIATOWE po urwanym przy
imporcie słowie „powiat" (`09. Pszczyna` to w pliku klienta było
`09. Pszczyna powiat`, czyli 27 różnych miejscowości; `15. Będzin` — 17).

Stąd wzięło się zgłoszenie Kasi „nie ma bazy w Czeladzi": Czeladź nie zniknęła,
tylko przestała być widoczna jako nazwa — wpadła do worka `15. Będzin`.
Rejestr RSPO nie ma tego problemu, bo powiat jest tam osobną kolumną.

SKĄD BIERZEMY POWIAT
Dwie drogi, w tej kolejności:

  1. `placowki.rspo` → wprost z lustra. Pewne, bo to ten sam rekord rejestru.
  2. Bez numeru RSPO → po nazwie miejscowości, przez lustro. Brzmi jak
     zgadywanie, ale nie jest: w rejestrze śląskim nazwa miejscowości wskazuje
     jeden powiat w 22 z 23 wartości naszego słownika. Jedyny wyjątek to
     `Psary` (będziński i lubliniecki) — rozstrzyga go reguła „powiat, po
     którym firma jeździ, wygrywa".

Droga 2 istnieje, bo NIE MOŻEMY czekać na nadanie numerów RSPO wszystkim 545
rekordom (etap M3, wymaga decyzji koordynatorki przy kilkudziesięciu wierszach).
Bez niej przełączenie filtrów na powiat schowałoby handlowcom całą ich bazę —
a filtr, przez który znikają rekordy, wygląda jak utrata danych.
"""
import re

import obszary


def _fold(s):
    return (s or "").strip().lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))


def bez_prefiksu(wartosc):
    """`08. Katowice` → `Katowice`. Prefiks to kolejność klienta, nie nazwa."""
    return re.sub(r"^\d+[a-z]?\.\s*", "", wartosc or "").strip()


def _powiaty_firmy(conn):
    """Powiaty i gminy z obszarów działania — do rozstrzygania nazw dwuznacznych."""
    try:
        return {_fold(r["wartosc"]) for r in
                conn.execute("SELECT wartosc FROM obszar_zakres")}
    except Exception:
        return set()


def mapa_miejscowosci(conn):
    """
    {nazwa miejscowości bez ogonków: (powiat, gmina)} z lustra rejestru.

    Gdy nazwa występuje w kilku powiatach, wygrywa ten, po którym firma jeździ;
    gdy i to nie rozstrzyga — ten z większą liczbą placówek (czyli zwykle ten,
    o który chodziło człowiekowi wpisującemu nazwę do arkusza).
    """
    nasze = _powiaty_firmy(conn)
    kandydaci = {}
    for r in conn.execute("""
            SELECT miejscowosc, powiat, gmina, COUNT(*) n
              FROM rspo_rejestr
             WHERE miejscowosc IS NOT NULL AND miejscowosc <> ''
             GROUP BY miejscowosc, powiat, gmina"""):
        kandydaci.setdefault(_fold(r["miejscowosc"]), []).append(
            (r["powiat"], r["gmina"], r["n"]))

    out = {}
    for nazwa, lista in kandydaci.items():
        lista.sort(key=lambda x: (_fold(x[0]) not in nasze and _fold(x[1]) not in nasze,
                                  -x[2]))
        out[nazwa] = (lista[0][0], lista[0][1])
    return out


def dla_nowej(conn, miejscowosc):
    """
    (powiat, gmina) dla świeżo zakładanej placówki — po nazwie miejscowości.

    Wołane przy KAŻDYM tworzeniu placówki (formularz terenowy, ekran „Baza"),
    a nie tylko w migracji. Bez tego rekord założony w terenie miałby pusty
    powiat i zniknąłby z filtra, po którym pracuje cała firma — a rekord,
    którego nie widać, jest tym samym co rekord, którego nie ma.

    Gdy nazwy nie ma w rejestrze (literówka, przysiółek, nowa placówka
    pod nietypowym adresem) — zwraca (None, None). Zostaje wtedy bez powiatu
    i widać ją na liście „bez powiatu", zamiast wylądować w przypadkowym.
    """
    nazwa = bez_prefiksu(miejscowosc)
    if not nazwa:
        return None, None
    try:
        wiersze = conn.execute("""
            SELECT powiat, gmina, COUNT(*) n FROM rspo_rejestr
             WHERE lower(miejscowosc) = lower(?)
             GROUP BY powiat, gmina""", (nazwa,)).fetchall()
    except Exception:
        return None, None          # profil bez lustra — nie ma z czego wziąć
    if not wiersze:
        return None, None
    nasze = _powiaty_firmy(conn)
    wiersze = sorted(wiersze, key=lambda r: (
        _fold(r["powiat"]) not in nasze and _fold(r["gmina"]) not in nasze, -r["n"]))
    return wiersze[0]["powiat"], wiersze[0]["gmina"]


def uzupelnij(conn, zapisz=False):
    """
    Wpisuje `powiat`/`gmina` wszystkim placówkom. Zwraca raport.

    Nie nadpisuje tego, co już jest — poza rekordami z numerem RSPO, gdzie
    rejestr jest z definicji ważniejszy niż cokolwiek wpisanego wcześniej.
    """
    mapa = mapa_miejscowosci(conn)
    z_rejestru, z_nazwy, bez_odpowiedzi = [], [], []

    for r in conn.execute("SELECT id, rspo, nazwa, miejscowosc, powiat FROM placowki"):
        nowy = None
        if r["rspo"]:
            w = conn.execute(
                "SELECT powiat, gmina FROM rspo_rejestr WHERE rspo=?",
                (r["rspo"],)).fetchone()
            if w:
                nowy = (w["powiat"], w["gmina"], "rejestr")
        if nowy is None:
            trafienie = mapa.get(_fold(bez_prefiksu(r["miejscowosc"])))
            if trafienie:
                nowy = (trafienie[0], trafienie[1], "nazwa")
        if nowy is None:
            bez_odpowiedzi.append({"id": r["id"], "nazwa": r["nazwa"],
                                   "miejscowosc": r["miejscowosc"]})
            continue
        (z_rejestru if nowy[2] == "rejestr" else z_nazwy).append(
            {"id": r["id"], "powiat": nowy[0]})
        if zapisz:
            conn.execute("UPDATE placowki SET powiat=?, gmina=? WHERE id=?",
                         (nowy[0], nowy[1], r["id"]))
    if zapisz:
        conn.commit()
    return {"z_rejestru": len(z_rejestru), "z_nazwy": len(z_nazwy),
            "bez_odpowiedzi": bez_odpowiedzi}


def czysc_miejscowosci(conn, zapisz=False):
    """
    Miejscowość na czystą nazwę: bez prefiksu, a przy rekordach z numerem RSPO —
    prosto z rejestru.

    TO WOLNO ZROBIĆ DOPIERO RAZEM Z PRZEŁĄCZENIEM FILTRÓW NA POWIAT i ani chwili
    wcześniej. Dopóki filtr chodzi po słowniku `miasto`, rekord z wartością
    `Katowice` zamiast `08. Katowice` NIE WPADA W ŻADEN FILTR i znika
    handlowcowi z oczu — a znikające rekordy zgłasza się jako utratę danych.
    Kolejność jest tu jedyną zaporą, dlatego etap M8 projektu siedzi PO M6.

    Czego ta funkcja NIE UMIE, i trzeba to powiedzieć wprost: 27 rekordów
    z worka `15. Będzin` i 41 z `09. Pszczyna` dostanie nazwę miasta
    powiatowego, bo prawdziwa miejscowość NIE ISTNIEJE w danych klienta —
    urwała się przy imporcie razem ze słowem „powiat". Ich POWIAT jest
    prawdziwy (i to on jest teraz osią filtrowania), miejscowość będzie
    przybliżeniem do czasu nadania numerów RSPO w etapie M3.
    """
    zmiany = []
    for r in conn.execute("SELECT id, rspo, miejscowosc FROM placowki"):
        nowa = None
        if r["rspo"]:
            w = conn.execute("SELECT miejscowosc FROM rspo_rejestr WHERE rspo=?",
                             (r["rspo"],)).fetchone()
            if w and w["miejscowosc"]:
                nowa = w["miejscowosc"]
        if nowa is None:
            nowa = bez_prefiksu(r["miejscowosc"]) or None
        if nowa != r["miejscowosc"]:
            zmiany.append((r["id"], r["miejscowosc"], nowa))
            if zapisz:
                conn.execute("UPDATE placowki SET miejscowosc=? WHERE id=?",
                             (nowa, r["id"]))
    if zapisz:
        conn.commit()
    return zmiany


# ---------------------------------------------------------------------------
# Listy do filtrów — z DANYCH, nie ze słownika
#
# Słownik `miasto` ma 33 pozycje, z których 11 nie ma ani jednej placówki,
# a jednocześnie NIE MA w nim miejscowości, które doszły z rejestru. Lista
# filtra brana ze słownika kłamie więc w obie strony naraz: proponuje wybory
# dające pustkę i ukrywa te, w których coś jest.
# ---------------------------------------------------------------------------

def powiaty(conn):
    """Powiaty, w których faktycznie mamy placówki — do listy filtra."""
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT powiat FROM placowki "
        "WHERE powiat IS NOT NULL AND powiat <> '' ORDER BY powiat")]


def miasta(conn, powiat=None):
    """Miejscowości — wszystkie albo zawężone do powiatu (druga oś kaskady)."""
    if powiat:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT miejscowosc FROM placowki "
            "WHERE powiat = ? AND miejscowosc IS NOT NULL AND miejscowosc <> '' "
            "ORDER BY miejscowosc", (powiat,))]
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT miejscowosc FROM placowki "
        "WHERE miejscowosc IS NOT NULL AND miejscowosc <> '' ORDER BY miejscowosc")]


# Była tu `miasta_do_wyboru()` — lista miejscowości powiatu z REJESTRU, także
# tych, w których nie mamy ani jednej placówki. Miała jedno uzasadnienie:
# handlowiec stoi w Brudzowicach właśnie dlatego, że jeszcze tam nie byliśmy,
# i musi mieć tę nazwę, żeby ZAŁOŻYĆ placówkę.
#
# Zakładanie placówek wypadło z formularza 24.08 (zgłoszenie Kasi: „PH wpisują
# coś z ręki sami i będą się dublować rzeczy"). Uzasadnienie zniknęło, został
# sam koszt: wybór miejscowości, po którym lista placówek jest pusta i nic się
# z tym nie da zrobić. Wszystkie listy miejscowości idą dziś z `miasta()`,
# czyli z DANYCH — bo każdy ekran służy już tylko do wskazania placówki, która
# istnieje. Gdyby zakładanie kiedyś wróciło, ta funkcja jest w historii gita.


def podsumowanie(conn):
    """Ile placówek per powiat — do ekranu i do kontroli po migracji."""
    return [dict(r) for r in conn.execute("""
        SELECT COALESCE(NULLIF(powiat,''), '— bez powiatu —') AS powiat,
               COUNT(*) AS ile,
               SUM(CASE WHEN COALESCE(typ,'') LIKE '01.%' THEN 1 ELSE 0 END) AS szkoly,
               SUM(CASE WHEN COALESCE(typ,'') LIKE '02.%'
                          OR COALESCE(typ,'') LIKE '03.%' THEN 1 ELSE 0 END) AS przedszkola
          FROM placowki
         GROUP BY 1 ORDER BY 1""")]
