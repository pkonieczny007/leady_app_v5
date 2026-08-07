# -*- coding: utf-8 -*-
"""
Dane do prezentacji — WYCIĄGANE Z BAZY, nie wpisane z palca.

Powód: prezentacja pokazuje aplikację na realnym pliku klientki, więc każda
liczba i każde nazwisko na slajdzie ma pochodzić z `data/leady_v3.db`. Gdyby
ktoś zapytał „skąd te 152", odpowiedź ma być „z bazy", a nie „tak wyszło".
Po zmianie danych wystarczy uruchomić `zbuduj.py` jeszcze raz.

Uruchamiane z katalogu `prezentacja/`, więc dokładamy katalog wyżej do ścieżki.
"""
import os
import sys

TU = os.path.dirname(os.path.abspath(__file__))
APKA = os.path.dirname(TU)
if APKA not in sys.path:
    sys.path.insert(0, APKA)

import calendar_view as cv          # noqa: E402
import db                           # noqa: E402
import dostepnosc_view as dv        # noqa: E402
import filtry as fl                 # noqa: E402
import przydzial as pz              # noqa: E402
import repo                         # noqa: E402

# Miesiąc, na którym pokazujemy grafik i obsadę. Wrzesień, bo tam są deklaracje
# dostępności — bez nich panel „Kogo wysłać?" pokazywałby same „brak deklaracji".
MIESIAC_GRAFIK = "2026-09"
MIESIAC_KOLIZJE = "2026-06"         # czerwiec: pełny miesiąc zajęć cyklicznych
OSOBA_PRZYKLAD = "02. Olszewska"    # jednocześnie handlowiec I trenerka


def _d(rows):
    return [dict(r) for r in rows]


def zbierz():
    conn = db.get_conn()
    d = {}

    d["metryki"] = repo.metryki(conn)
    d["per_handlowiec"], d["poniedzialek"] = repo.per_handlowiec(conn)
    d["slowniki"] = _d(conn.execute(
        "SELECT rodzaj, COUNT(*) c FROM slowniki GROUP BY rodzaj ORDER BY c DESC"))
    d["n_aliasow"] = conn.execute("SELECT COUNT(*) FROM aliasy").fetchone()[0]
    # Aliasy pokazujemy na osobach i miastach — tam rozjazd bolał najbardziej
    # („02. Olaszewska" obok „02. Olszewska", ten sam Katowice pod trzema numerami).
    d["aliasy"] = _d(conn.execute(
        "SELECT rodzaj, alias, wartosc FROM aliasy "
        "WHERE alias <> wartosc AND rodzaj IN ('handlowiec','trener','miasto') "
        "ORDER BY CASE rodzaj WHEN 'handlowiec' THEN 0 WHEN 'trener' THEN 1 ELSE 2 END, "
        "         alias LIMIT 6"))
    d["statusy"] = _d(conn.execute(
        "SELECT status_realizacji s, COUNT(*) c FROM leady "
        "GROUP BY s ORDER BY c DESC"))

    # --- leady po terminie: kandydaci do odebrania handlowcowi
    d["po_terminie"] = _d(conn.execute(
        "SELECT l.id, l.handlowiec, l.deadline, l.status_realizacji, "
        "       p.nazwa, p.miejscowosc "
        "FROM leady l JOIN placowki p ON p.id = l.placowka_id "
        "WHERE l.deadline IS NOT NULL AND l.deadline <> '' AND l.deadline < date('now') "
        "  AND (l.status_realizacji IS NULL OR l.status_realizacji NOT LIKE '03%') "
        "ORDER BY l.deadline LIMIT 5"))

    # --- lead z wieloma spotkaniami: DT + cykl w jednym miejscu
    lead = repo.lead_szczegoly(conn, 519)
    d["lead"] = lead

    # --- kolizje: dwa zajęcia jednego trenera z zachodzącymi godzinami
    kol = cv.lista_kolizji(conn, MIESIAC_KOLIZJE)
    # bierzemy parę w RÓŻNYCH szkołach — to najmocniejszy przykład (dojazd)
    para = None
    po_kluczu = {}
    for e in kol:
        po_kluczu.setdefault((e["trener"], e["data"]), []).append(e)
    for grupa in po_kluczu.values():
        if len(grupa) >= 2 and grupa[0]["placowka"] != grupa[1]["placowka"]:
            para = grupa[:2]
            break
    d["kolizja"] = para or (kol[:2] if len(kol) >= 2 else [])
    d["n_kolizji"] = len(kol)
    d["miesiac_kolizje"] = cv.month_label(MIESIAC_KOLIZJE)

    # --- „Kogo wysłać?": realny ranking na realnym spotkaniu
    kandydat_ev = None
    for e in cv.events_for_month(conn, MIESIAC_GRAFIK):
        if e["typ"] in ("DT", "START") and e["godz_od"] and e["godz_do"]:
            kandydat_ev = e
            break
    d["obsada_event"] = kandydat_ev
    if kandydat_ev:
        lista = pz.kandydaci(conn, kandydat_ev["data"], kandydat_ev["godz_od"],
                             kandydat_ev["godz_do"], kandydat_ev["miejscowosc"],
                             kandydat_ev["id"])
        d["kandydaci"] = lista
        d["kandydaci_ile"] = {k: sum(1 for x in lista if x["kategoria"] == k)
                              for k in pz.KATEGORIE}

    # --- dostępność: komórka, w której widać odejmowanie zajęć od deklaracji
    grid = dv.build_dostepnosc(conn, MIESIAC_GRAFIK)
    d["dostepnosc_przyklad"] = None
    for t in grid["tygodnie"]:
        for w in t["wiersze"]:
            for c in w["cells"]:
                if (c["status"] in ("okno", "caly") and len(c["zajete"]) >= 2
                        and c["wolne"]):
                    d["dostepnosc_przyklad"] = {"trener": w["trener"], "cell": c}
                    break
            if d["dostepnosc_przyklad"]:
                break
        if d["dostepnosc_przyklad"]:
            break
    d["n_trenerow"] = grid["n_trenerow_all"]

    # Czy deklaracje dostępności to wypełnienie przykładowe (`uwagi='demo'`).
    # Prezentacja MA to powiedzieć wprost — inaczej dopisek „(demo)", który
    # wychodzi w powodach przy kandydatach, wygląda jak usterka, a nie jak
    # informacja. Po `DELETE FROM dostepnosc WHERE uwagi='demo'` przypis znika sam.
    n_dost = conn.execute("SELECT COUNT(*) FROM dostepnosc").fetchone()[0]
    n_demo = conn.execute(
        "SELECT COUNT(*) FROM dostepnosc WHERE uwagi = 'demo'").fetchone()[0]
    d["dostepnosc_demo"] = n_demo > 0
    d["dostepnosc_n"] = n_dost
    d["dostepnosc_n_demo"] = n_demo

    # --- filtr osób: liczby, które uzasadniają zakres „nazwisko"
    evs = cv.events_for_month(conn, MIESIAC_KOLIZJE)
    d["filtr_wszystko"] = len(fl.filtruj_eventy(
        list(evs), fl.parsuj("w:" + OSOBA_PRZYKLAD, fl.ZAKRESY_GRAFIK), "lub"))
    tylko_osoba = fl.filtruj_eventy(
        list(evs), fl.parsuj("n:" + OSOBA_PRZYKLAD, fl.ZAKRESY_GRAFIK), "lub")
    d["filtr_nazwisko"] = len(tylko_osoba)
    d["filtr_role"] = sum(1 for e in tylko_osoba if e.get("_rola"))
    d["filtr_osoba"] = OSOBA_PRZYKLAD
    d["filtr_wiersze_w"] = len({e["trener"] for e in fl.filtruj_eventy(
        list(evs), fl.parsuj("w:" + OSOBA_PRZYKLAD, fl.ZAKRESY_GRAFIK), "lub")
        if e["trener"]})
    d["filtr_wiersze_n"] = len({e["trener"] for e in tylko_osoba if e["trener"]})
    d["n_eventow_miesiac"] = len(evs)

    # --- ten sam filtr na liście leadów, po handlowcu i po prowadzącym
    def ile(osoby, tryb="lub"):
        f = repo.pusty_filtr()
        f["osoby"], f["osoby_tryb"] = osoby, tryb
        return repo.policz_leady(conn, f)

    d["leady_sacawa"] = ile("h:Sacawa")
    d["leady_zemela"] = ile("t:Zemela")
    d["leady_oba"] = ile("h:Sacawa|t:Zemela", "oraz")

    conn.close()
    return d


if __name__ == "__main__":
    import pprint
    dane = zbierz()
    pprint.pprint({k: v for k, v in dane.items() if k != "lead"})
