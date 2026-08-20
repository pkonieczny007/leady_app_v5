# -*- coding: utf-8 -*-
"""
Testy własności rekordu przy ZAPISIE (P01, P02 — zgłoszenie K01 Kasi, 20.08.2026).

Zgłoszenie brzmiało: „Zablokuj PH możliwość edycji danych innego PH, bo teraz
mogą zmienić dosłownie wszystko". Przy sprawdzaniu okazało się, że jest gorzej,
niż wyglądało: wśród pól edytowalnych są `handlowiec` i `deadline`, więc
handlowiec mógł PRZYPISAĆ SOBIE cudzą szkołę i PRZEDŁUŻYĆ SOBIE termin, po
którym szkoła wraca do puli. W historii zmian wyglądało to jak zwykła praca.

Dlaczego to osobny plik testów: blokada w interfejsie już wcześniej „była" —
przycisków po prostu nie było widać. Zapis idzie zwykłym `fetch`, a numer leada
stoi w pasku adresu, więc jedyna blokada, która cokolwiek znaczy, siedzi przy
zapisie. Ten plik pilnuje właśnie tej warstwy i niczego innego.

Czego te testy NIE sprawdzają: podglądu. Kasia chce widzieć, kto miał szkołę
wcześniej i co z nią zrobił — odbieramy zapis, nie widok.

Uruchomienie:  python test_uprawnienia.py
Działa na WŁASNEJ, tymczasowej bazie.
"""
import json
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

TMP = tempfile.mkdtemp(prefix="leady_v5_uprawnienia_test_")
os.environ["DATA_DIR"] = TMP

import app as A                      # noqa: E402
import db                            # noqa: E402
import uzytkownicy as uz             # noqa: E402
from seed import bootstrap           # noqa: E402

KL = A.app.test_client()

PH_A = "90. Test-Handlowiec-A"
PH_B = "91. Test-Handlowiec-B"
KOOR = "99. Test-Koordynator"
PIN = {PH_A: "1111", PH_B: "2222", KOOR: "3333"}

WYNIKI = []


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


def zaloguj(osoba):
    """Przelogowanie w trakcie testu — każdy scenariusz zaczyna się od tego,
    KTO siedzi przy klawiaturze. To jest cała istota tych sprawdzeń."""
    r = KL.post("/api/logowanie", json={"osoba": osoba, "pin": PIN[osoba]})
    assert r.status_code == 200, "logowanie %s nie przeszło: %s" % (osoba, r.get_data())
    with KL.session_transaction() as s:
        s["csrf"] = "test-csrf"
    KL.environ_base["HTTP_X_CSRF"] = "test-csrf"


def patch(url, payload):
    r = KL.patch(url, data=json.dumps(payload), content_type="application/json")
    return r.status_code, (r.get_json() or {})


def post(url, payload):
    r = KL.post(url, data=json.dumps(payload), content_type="application/json")
    return r.status_code, (r.get_json() or {})


def usun(url):
    r = KL.delete(url)
    return r.status_code, (r.get_json() or {})


# --------------------------------------------------------------- przygotowanie

def przygotuj():
    conn = db.get_conn()
    bootstrap()
    conn = db.get_conn()
    uz.init(conn)
    for osoba in (PH_A, PH_B):
        conn.execute("INSERT INTO slowniki (rodzaj, wartosc, aktywny) VALUES ('handlowiec', ?, 1)",
                     (osoba,))
    conn.commit()
    for osoba, rola in ((PH_A, "handlowiec"), (PH_B, "handlowiec"), (KOOR, "koordynator")):
        if not uz.znajdz(conn, osoba):
            uz.utworz(conn, osoba, rola, PIN[osoba])

    def szkola(nazwa, wlasciciel):
        cur = conn.execute("INSERT INTO placowki (nazwa, zrodlo) VALUES (?, 'test')", (nazwa,))
        pid = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO leady (placowka_id, handlowiec, status_realizacji, deadline) "
            "VALUES (?,?,?,?)", (pid, wlasciciel, "01. Próba kontaktu (Brak konkretów)",
                                 "2026-09-30"))
        return cur.lastrowid

    ids = {
        "a": szkola("Szkoła A (moja)", PH_A),
        "b": szkola("Szkoła B (cudza)", PH_B),
        "niczyja": szkola("Szkoła bez opiekuna", None),
    }
    # po jednym wpisie w kalendarzu na szkołę A i B
    for klucz in ("a", "b"):
        cur = conn.execute(
            "INSERT INTO eventy (lead_id, typ, data, godz_od) VALUES (?, 'DT', '2026-09-15', '09:00')",
            (ids[klucz],))
        ids["event_" + klucz] = cur.lastrowid
    conn.commit()
    conn.close()
    return ids


# ------------------------------------------------------------------- scenariusze

def test_zapis_na_cudzym(ids):
    print("\n-- handlowiec przy CUDZEJ szkole --")
    zaloguj(PH_A)
    kod, odp = patch("/api/lead/%d" % ids["b"], {"field": "uwagi", "value": "podmieniam"})
    sprawdz("PATCH cudzego leada odrzucony", kod == 403, "kod %s" % kod)
    sprawdz("komunikat mówi, KTO prowadzi szkołę", PH_B in (odp.get("error") or ""),
            odp.get("error"))

    conn = db.get_conn()
    w_bazie = conn.execute("SELECT uwagi FROM leady WHERE id=?", (ids["b"],)).fetchone()["uwagi"]
    conn.close()
    sprawdz("cudzy rekord naprawdę nietknięty", not w_bazie, "uwagi=%r" % w_bazie)

    kod, _ = patch("/api/lead/%d" % ids["b"], {"field": "telefon", "value": "999888777"})
    sprawdz("pole PLACÓWKI na cudzej szkole też odrzucone", kod == 403, "kod %s" % kod)

    kod, _ = post("/api/pin", {"id": ids["b"], "pin": True})
    sprawdz("przypięcie cudzej szkoły na swój tydzień odrzucone", kod == 403, "kod %s" % kod)


def test_zapis_na_wlasnym(ids):
    print("\n-- handlowiec przy WŁASNEJ szkole (ma działać jak dotąd) --")
    zaloguj(PH_A)
    kod, _ = patch("/api/lead/%d" % ids["a"], {"field": "uwagi", "value": "dzwoniłem"})
    sprawdz("PATCH własnego leada przechodzi", kod == 200, "kod %s" % kod)

    conn = db.get_conn()
    w_bazie = conn.execute("SELECT uwagi FROM leady WHERE id=?", (ids["a"],)).fetchone()["uwagi"]
    conn.close()
    sprawdz("zapis naprawdę wszedł do bazy", w_bazie == "dzwoniłem", "uwagi=%r" % w_bazie)

    kod, _ = post("/api/pin", {"id": ids["a"], "pin": True})
    sprawdz("przypięcie własnej szkoły przechodzi", kod == 200, "kod %s" % kod)


def test_pola_zastrzezone(ids):
    print("\n-- pola, których handlowiec nie rusza nawet u siebie --")
    zaloguj(PH_A)
    kod, odp = patch("/api/lead/%d" % ids["a"], {"field": "handlowiec", "value": PH_A})
    sprawdz("przypisanie szkoły sobie samemu odrzucone", kod == 403, "kod %s" % kod)

    kod, _ = patch("/api/lead/%d" % ids["a"], {"field": "deadline", "value": "2027-12-31"})
    sprawdz("przedłużenie sobie terminu odrzucone", kod == 403, "kod %s" % kod)

    conn = db.get_conn()
    r = conn.execute("SELECT handlowiec, deadline FROM leady WHERE id=?", (ids["a"],)).fetchone()
    conn.close()
    sprawdz("termin w bazie bez zmian", r["deadline"] == "2026-09-30", r["deadline"])

    # to samo, ale na cudzej szkole — czyli próba przejęcia
    kod, _ = patch("/api/lead/%d" % ids["b"], {"field": "handlowiec", "value": PH_A})
    sprawdz("przejęcie cudzej szkoły odrzucone", kod == 403, "kod %s" % kod)
    conn = db.get_conn()
    r = conn.execute("SELECT handlowiec FROM leady WHERE id=?", (ids["b"],)).fetchone()
    conn.close()
    sprawdz("cudza szkoła dalej ma swojego opiekuna", r["handlowiec"] == PH_B, r["handlowiec"])


def test_szkola_niczyja(ids):
    print("\n-- szkoła bez opiekuna (przydziela koordynator, nie handlowiec) --")
    zaloguj(PH_A)
    kod, odp = patch("/api/lead/%d" % ids["niczyja"], {"field": "uwagi", "value": "biorę"})
    sprawdz("zapis na nieprzydzielonej szkole odrzucony", kod == 403, "kod %s" % kod)
    sprawdz("komunikat kieruje do koordynatora",
            "koordynator" in (odp.get("error") or "").lower(), odp.get("error"))


def test_kalendarz(ids):
    print("\n-- wpisy w kalendarzu należą do szkoły, nie do klikającego --")
    zaloguj(PH_A)
    kod, _ = usun("/api/event/%d" % ids["event_b"])
    sprawdz("skasowanie cudzego DT odrzucone", kod == 403, "kod %s" % kod)

    conn = db.get_conn()
    ile = conn.execute("SELECT COUNT(*) c FROM eventy WHERE id=?",
                       (ids["event_b"],)).fetchone()["c"]
    conn.close()
    sprawdz("cudze DT nadal jest w kalendarzu", ile == 1)

    kod, _ = patch("/api/event/%d" % ids["event_b"], {"field": "godz_od", "value": "07:00"})
    sprawdz("przestawienie godziny cudzego DT odrzucone", kod == 403, "kod %s" % kod)

    kod, _ = post("/api/event", {"lead_id": ids["b"], "typ": "DT", "data": "2026-10-01"})
    sprawdz("dopisanie DT do cudzej szkoły odrzucone", kod == 403, "kod %s" % kod)

    kod, _ = patch("/api/event/%d" % ids["event_a"], {"field": "godz_od", "value": "08:30"})
    sprawdz("własne DT dalej da się przestawić", kod == 200, "kod %s" % kod)


def test_tworzenie_leada(ids):
    print("\n-- nowa szkoła podpisuje się nazwiskiem z SESJI, nie z żądania --")
    zaloguj(PH_A)
    kod, odp = post("/api/lead", {"nazwa": "Podrzucona szkoła", "handlowiec": PH_B})
    sprawdz("utworzenie przechodzi", kod == 200, "kod %s" % kod)
    conn = db.get_conn()
    r = conn.execute("SELECT handlowiec FROM leady WHERE id=?", (odp.get("id"),)).fetchone()
    conn.close()
    sprawdz("właściciel wzięty z sesji, nie z ciała żądania",
            r and r["handlowiec"] == PH_A, r["handlowiec"] if r else "brak")


def test_koordynator(ids):
    print("\n-- koordynator: bez zmian, wolno mu wszystko --")
    zaloguj(KOOR)
    kod, _ = patch("/api/lead/%d" % ids["b"], {"field": "uwagi", "value": "przejrzane"})
    sprawdz("koordynator zapisuje na cudzej szkole", kod == 200, "kod %s" % kod)

    kod, _ = patch("/api/lead/%d" % ids["b"], {"field": "deadline", "value": "2026-10-15"})
    sprawdz("koordynator ustawia termin", kod == 200, "kod %s" % kod)

    kod, _ = patch("/api/lead/%d" % ids["niczyja"], {"field": "handlowiec", "value": PH_A})
    sprawdz("koordynator przypisuje szkołę", kod == 200, "kod %s" % kod)

    kod, _ = usun("/api/event/%d" % ids["event_b"])
    sprawdz("koordynator kasuje wpis z kalendarza", kod == 200, "kod %s" % kod)


def test_podglad_zostaje(ids):
    print("\n-- podgląd cudzych rekordów ZOSTAJE (Kasia chce widzieć historię) --")
    zaloguj(PH_A)
    r = KL.get("/lead/%d" % ids["b"])
    sprawdz("handlowiec otwiera kartę cudzej szkoły", r.status_code == 200,
            "kod %s" % r.status_code)
    r = KL.get("/api/placowki")
    sprawdz("lista placówek dalej dostępna", r.status_code == 200, "kod %s" % r.status_code)


def main():
    print("=" * 62)
    print("UPRAWNIENIA — właściciel rekordu przy zapisie (P01, P02)")
    print("=" * 62)
    ids = przygotuj()
    test_zapis_na_cudzym(ids)
    test_zapis_na_wlasnym(ids)
    test_pola_zastrzezone(ids)
    test_szkola_niczyja(ids)
    test_kalendarz(ids)
    test_tworzenie_leada(ids)
    test_koordynator(ids)
    test_podglad_zostaje(ids)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n" + "=" * 62)
    print("WYNIK: %d/%d sprawdzeń OK" % (ok, len(WYNIKI)))
    print("=" * 62)
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
