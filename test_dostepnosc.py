# -*- coding: utf-8 -*-
"""
Testy modułu „Dostępność trenerów" (v2) — logika wolnych okien + API + ostrzeżenia.

Uruchomienie:  python test_dostepnosc.py
Działa na WŁASNEJ, tymczasowej bazie (nie rusza `data/leady_v3.db`).
"""
import datetime as dt
import json
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

TMP = tempfile.mkdtemp(prefix="leady_v3_av_test_")
os.environ["DATA_DIR"] = TMP

import app as A                      # noqa: E402
import db                            # noqa: E402
import dostepnosc_view as dv         # noqa: E402
from seed import bootstrap           # noqa: E402

KL = A.app.test_client()

# --- logowanie w testach ---------------------------------------------------
# Od v5 aplikacja wymaga konta i tokenu CSRF. Testy sprawdzają logikę biznesową,
# nie ekran logowania (ten ma własny plik), więc zakładamy konto koordynatora
# i logujemy klienta raz, na starcie.
def _zaloguj_testowo():
    import db as _db, uzytkownicy as _uz
    c = _db.get_conn()
    _uz.init(c)
    if not _uz.znajdz(c, "TEST-koordynator"):
        _uz.utworz(c, "TEST-koordynator", "koordynator", "1379")
    c.close()
    r = KL.post("/api/logowanie", json={"osoba": "TEST-koordynator", "pin": "1379"})
    assert r.status_code == 200, "logowanie testowe nie przeszło: %s" % r.get_data()
    with KL.session_transaction() as s:
        s["csrf"] = "test-csrf"
    KL.environ_base["HTTP_X_CSRF"] = "test-csrf"

WYNIKI = []


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


def post(url, payload):
    r = KL.post(url, data=json.dumps(payload), content_type="application/json")
    return r.status_code, r.get_json()


def delete(url, payload):
    r = KL.delete(url, data=json.dumps(payload), content_type="application/json")
    return r.status_code, r.get_json()


def main():
    print("Baza testowa:", TMP)
    bootstrap()
    _zaloguj_testowo()
    conn = db.get_conn()
    trenerzy = db.slownik_values(conn, "trener")
    conn.close()
    T1, T2 = trenerzy[0], trenerzy[1]

    print("\nD1 — czysta logika wolnych okien")
    wpis = {"godz_od": "08:00", "godz_do": "16:00", "niedostepny": 0}
    zajete = [{"godz_od": "09:40", "godz_do": "11:55"},
              {"godz_od": "14:00", "godz_do": "15:00"}]
    wolne = dv.wolne_okna(wpis, zajete)
    sprawdz("deklaracja 8–16 minus 2 zajęcia = 3 okna", wolne ==
            ["08:00–09:40", "11:55–14:00", "15:00–16:00"], str(wolne))
    sprawdz("okno < 45 min jest pomijane",
            dv.wolne_okna(wpis, [{"godz_od": "08:30", "godz_do": "16:00"}]) == [])
    sprawdz("cały dzień = 8:00–18:00",
            dv.wolne_okna({"godz_od": None, "godz_do": None, "niedostepny": 0}, [])
            == ["08:00–18:00"])
    sprawdz("niedostępny → zero okien",
            dv.wolne_okna({"godz_od": "08:00", "godz_do": "16:00",
                           "niedostepny": 1}, []) == [])
    sprawdz("zajęcie bez godziny końca liczone jako 60 min",
            dv.wolne_okna(wpis, [{"godz_od": "08:00", "godz_do": None}])
            == ["09:00–16:00"])

    print("\nD2 — zapis komórki przez API")
    kod, d = post("/api/dostepnosc", {"trener": T1, "data": "2026-09-07",
                                      "godz_od": "08:00", "godz_do": "12:00"})
    sprawdz("wpis okna 8–12 przyjęty", kod == 200 and d["ok"])
    kod, d = post("/api/dostepnosc", {"trener": T1, "data": "2026-09-08",
                                      "niedostepny": True,
                                      "godz_od": "08:00", "godz_do": "12:00"})
    conn = db.get_conn()
    w = dict(conn.execute("SELECT * FROM dostepnosc WHERE trener=? AND data=?",
                          (T1, "2026-09-08")).fetchone())
    conn.close()
    sprawdz("niedostępny zeruje godziny", w["niedostepny"] == 1
            and w["godz_od"] is None and w["godz_do"] is None)
    kod, d = post("/api/dostepnosc", {"trener": "99. Niema Takiego",
                                      "data": "2026-09-07"})
    sprawdz("trener spoza słownika odrzucony (400)", kod == 400)
    kod, d = post("/api/dostepnosc", {"trener": T1, "data": "07.09.2026"})
    sprawdz("zła data odrzucona (400)", kod == 400)

    print("\nD3 — wypełnienie zakresu bez nadpisywania")
    kod, d = post("/api/dostepnosc/zakres", {
        "trener": T1, "od": "2026-09-07", "do": "2026-09-11",
        "dni": [0, 1, 2, 3, 4], "godz_od": "08:00", "godz_do": "16:00"})
    sprawdz("zakres pon–pt: wypełnione 3 z 5 (2 już istniały)",
            kod == 200 and d["n"] == 3, "n=%s" % d.get("n"))
    conn = db.get_conn()
    w = dict(conn.execute("SELECT * FROM dostepnosc WHERE trener=? AND data=?",
                          (T1, "2026-09-07")).fetchone())
    conn.close()
    sprawdz("istniejący wpis 8–12 NIE nadpisany", w["godz_do"] == "12:00")

    # D3b — zaznaczone dni: paczka NADPISUJE (w odróżnieniu od zakresu).
    # Z uwagi trenera 09.08: „wypełnianie jest nieintuicyjne" — dostał tryb,
    # w którym zaznacza dni palcem i nadaje im wszystkim jedną deklarację.
    print("\nD3b — zapis zaznaczonych dni jedną paczką")
    kod, d = post("/api/dostepnosc/dni", {
        "trener": T1, "dni": ["2026-09-21", "2026-09-22", "2026-09-23"],
        "tryb": "okno", "godz_od": "08:00", "godz_do": "12:00"})
    sprawdz("trzy dni zapisane jednym żądaniem", kod == 200 and d["n"] == 3,
            str(d)[:80])
    conn = db.get_conn()
    ile = conn.execute("SELECT COUNT(*) c FROM dostepnosc WHERE trener=? "
                       "AND data IN ('2026-09-21','2026-09-22','2026-09-23') "
                       "AND godz_od='08:00'", (T1,)).fetchone()["c"]
    conn.close()
    sprawdz("wszystkie trzy mają okno 8–12", ile == 3, "jest %d" % ile)

    kod, d = post("/api/dostepnosc/dni", {
        "trener": T1, "dni": ["2026-09-21"], "tryb": "nie"})
    conn = db.get_conn()
    w = dict(conn.execute("SELECT * FROM dostepnosc WHERE trener=? AND data=?",
                          (T1, "2026-09-21")).fetchone())
    conn.close()
    sprawdz("paczka NADPISUJE istniejący wpis (inaczej niż zakres)",
            w["niedostepny"] == 1 and w["godz_od"] is None)

    kod, d = post("/api/dostepnosc/dni", {
        "trener": T1, "dni": ["2026-09-22"], "tryb": "usun"})
    conn = db.get_conn()
    zostal = conn.execute("SELECT COUNT(*) c FROM dostepnosc WHERE trener=? AND data=?",
                          (T1, "2026-09-22")).fetchone()["c"]
    conn.close()
    sprawdz("tryb „usuń” kasuje deklarację (dzień wraca do „nie wiadomo”)",
            kod == 200 and zostal == 0)

    kod, _ = post("/api/dostepnosc/dni", {"trener": T1, "dni": [], "tryb": "caly"})
    sprawdz("pusta paczka odrzucona", kod == 400)
    kod, _ = post("/api/dostepnosc/dni", {"trener": T1, "dni": ["2026-09-21"],
                                          "tryb": "okno"})
    sprawdz("okno bez godziny początku odrzucone", kod == 400)
    kod, _ = post("/api/dostepnosc/dni", {"trener": T1, "dni": ["2026-09-21"],
                                          "tryb": "okno", "godz_od": "14:00",
                                          "godz_do": "09:00"})
    sprawdz("koniec przed początkiem odrzucony", kod == 400)
    kod, _ = post("/api/dostepnosc/dni", {"trener": T1, "dni": ["07.09.2026"],
                                          "tryb": "caly"})
    sprawdz("zła data w paczce odrzuca całość", kod == 400)
    kod, _ = post("/api/dostepnosc/dni", {"trener": "99. Niema Takiego",
                                          "dni": ["2026-09-21"], "tryb": "caly"})
    sprawdz("trener spoza słownika odrzucony", kod == 400)

    print("\nD4 — ekran: statusy komórek i wolne okna z kalendarza")
    kod, d = post("/api/lead", {"nazwa": "SP Testowa", "miejscowosc": None,
                                "typ": None})
    lead_id = d["id"]
    kod, d = post("/api/event", {"lead_id": lead_id, "typ": "DT",
                                 "data": "2026-09-09", "godz_od": "09:00",
                                 "godz_do": "11:00", "trener": T1})
    sprawdz("DT dodane w środku zadeklarowanego okna, bez ostrzeżenia",
            kod == 200 and not d.get("kolizja"), str(d.get("kolizja")))
    conn = db.get_conn()
    grid = dv.build_dostepnosc(conn, "2026-09")
    conn.close()
    kom = {}
    for t in grid["tygodnie"]:
        for wr in t["wiersze"]:
            if wr["trener"] != T1:
                continue
            for c in wr["cells"]:
                kom[c["iso"]] = c
    sprawdz("7.09 = status okno", kom["2026-09-07"]["status"] == "okno")
    sprawdz("8.09 = status niedostępny", kom["2026-09-08"]["status"] == "niedostepny")
    sprawdz("9.09: zajęte 9–11 widoczne", len(kom["2026-09-09"]["zajete"]) == 1)
    sprawdz("9.09: wolne okna 8–9 i 11–16",
            kom["2026-09-09"]["wolne"] == ["08:00–09:00", "11:00–16:00"],
            str(kom["2026-09-09"]["wolne"]))
    sprawdz("dzień bez wpisu = status brak (nieznana ≠ niedostępny)",
            kom["2026-09-14"]["status"] == "brak")

    print("\nD5 — ostrzeżenia przy umawianiu (nigdy blokada)")
    kod, d = post("/api/event", {"lead_id": lead_id, "typ": "DT",
                                 "data": "2026-09-08", "godz_od": "10:00",
                                 "godz_do": "12:00", "trener": T1})
    sprawdz("DT u NIEDOSTĘPNEGO trenera: zapis przechodzi",
            kod == 200 and d["ok"])
    sprawdz("…ale wraca ostrzeżenie o niedostępności",
            d.get("kolizja") and "NIEDOST" in d["kolizja"], str(d.get("kolizja")))
    kod, d = post("/api/event", {"lead_id": lead_id, "typ": "DT",
                                 "data": "2026-09-10", "godz_od": "17:00",
                                 "godz_do": "18:30", "trener": T1})
    sprawdz("DT poza oknem 8–16: zapis + ostrzeżenie „poza dostępnością”",
            kod == 200 and d.get("kolizja") and "poza dostępnością" in d["kolizja"],
            str(d.get("kolizja")))
    kod, d = post("/api/event", {"lead_id": lead_id, "typ": "DT",
                                 "data": "2026-09-21", "godz_od": "17:00",
                                 "godz_do": "18:30", "trener": T2})
    sprawdz("brak deklaracji trenera = brak ostrzeżenia (nieznana ≠ zakaz)",
            kod == 200 and not d.get("kolizja"), str(d.get("kolizja")))

    print("\nD6 — czyszczenie i demo")
    kod, d = delete("/api/dostepnosc", {"trener": T1, "data": "2026-09-08"})
    conn = db.get_conn()
    n = conn.execute("SELECT COUNT(*) c FROM dostepnosc WHERE trener=? AND data=?",
                     (T1, "2026-09-08")).fetchone()["c"]
    sprawdz("wyczyszczenie komórki działa", kod == 200 and n == 0)
    kod, d = post("/api/dostepnosc/demo", {"m": "2026-09"})
    sprawdz("demo wypełnia miesiąc", kod == 200 and d["n"] > 100, "n=%s" % d.get("n"))
    n2 = conn.execute("SELECT COUNT(*) c FROM dostepnosc WHERE uwagi='demo' "
                      "AND trener=? AND data=?", (T1, "2026-09-07")).fetchone()["c"]
    sprawdz("demo nie nadpisało ręcznego wpisu", n2 == 0)
    conn.close()

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
