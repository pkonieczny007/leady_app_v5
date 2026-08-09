# -*- coding: utf-8 -*-
"""
Testy modułu „Przydzielanie trenerów" (v4) — ranking kandydatów, rejony, API.

Uruchomienie:  python test_przydzial.py
Działa na WŁASNEJ, tymczasowej bazie (nie rusza `data/leady_v3.db`).
"""
import json
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

TMP = tempfile.mkdtemp(prefix="leady_v4_pz_test_")
os.environ["DATA_DIR"] = TMP

import app as A                      # noqa: E402
import db                            # noqa: E402
import przydzial as pz               # noqa: E402
from seed import bootstrap           # noqa: E402

KL = A.app.test_client()

# --- logowanie w testach ---------------------------------------------------
# Od v5 aplikacja wymaga konta i tokenu CSRF. Testy sprawdzają logikę biznesową,
# nie ekran logowania (ten ma własny plik), więc zakładamy konto koordynatora
# i logujemy klienta raz, na starcie.
def _sprawdz_parser_rejonow(sprawdz):
    """
    Rejony klient wpisuje swobodnym tekstem w jednej komórce:
    „Zabrze/Knurów/??? nie odebrała telefonu", „SP 27 Katowice",
    „Chorzów (od grudnia powiat Mikołów)". Parser z narzedzia/trenerzy.py
    ma z tego wyciągnąć same miasta — sprawdzone na REALNYCH wpisach z pliku
    klienta z 08.08.2026.
    """
    import importlib.util
    sciezka = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "narzedzia", "trenerzy.py")
    spec = importlib.util.spec_from_file_location("_trenerzy", sciezka)
    tr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tr)

    przypadki = [
        ("Knurów/Rybnik", ["Knurów", "Rybnik"]),
        ("Ruda Śląska, Zabrze, Świętochłowice, Chorzów", 4),
        ("Knurów - nie odebrała telefonu", ["Knurów"]),
        ("Zabrze/Knurów/??? nie odebrała telefonu", ["Zabrze", "Knurów"]),
        ("Chorzów/Świętochłowice/Zabrze/Katowice (tylko duże grypy i dwie pod rząd)", 4),
    ]
    for tekst, oczekiwane in przypadki:
        wynik = tr._czysc_region(tekst)
        if isinstance(oczekiwane, int):
            sprawdz("rejon %r → %d miast" % (tekst[:34], oczekiwane),
                    len(wynik) == oczekiwane, str(wynik))
        else:
            sprawdz("rejon %r → %s" % (tekst[:34], oczekiwane),
                    wynik == oczekiwane, str(wynik))

    # „SP 27 Katowice" to szkoła, ale niesie tę samą informację co miasto
    miasta = [("08. Katowice", "katowice"), ("05. Knurów", "knurow")]
    fold = lambda s: (s or "").lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    sprawdz("nazwa szkoły z miastem w środku daje miasto",
            tr.dopasuj_miasto("SP 27 Katowice", miasta, fold) == "08. Katowice")
    sprawdz("miejscowość spoza słownika zwraca None (nie zgaduje)",
            tr.dopasuj_miasto("Pyrzowice", miasta, fold) is None)


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


def get(url):
    r = KL.get(url)
    return r.status_code, r.get_json()


def znajdz(lista, trener):
    for k in lista:
        if k["trener"] == trener:
            return k
    return None


def main():
    print("Baza testowa:", TMP)
    bootstrap()
    _zaloguj_testowo()
    conn = db.get_conn()
    trenerzy = db.slownik_values(conn, "trener")
    miasta = db.slownik_values(conn, "miasto")
    conn.close()
    T_WOLNY, T_KOLIZJA, T_NIEDOST, T_POZA, T_NIEZNANY = trenerzy[:5]
    M1, M2 = miasta[0], miasta[1]
    DATA = "2026-09-15"

    # ---------------------------------------------------------------- dane
    kod, d = post("/api/lead", {"nazwa": "SP Testowa", "miejscowosc": M1,
                                "typ": None})
    lead_id = d["id"]
    # spotkanie, na które szukamy trenera: 10:00–12:00
    kod, d = post("/api/event", {"lead_id": lead_id, "typ": "DT", "data": DATA,
                                 "godz_od": "10:00", "godz_do": "12:00"})
    event_id = d["id"]
    sprawdz("spotkanie bez trenera dodane", kod == 200 and d["ok"])

    for t, payload in [
            (T_WOLNY, {"godz_od": "08:00", "godz_do": "16:00"}),
            (T_KOLIZJA, {"godz_od": "08:00", "godz_do": "16:00"}),
            (T_POZA, {"godz_od": "13:00", "godz_do": "16:00"}),
            (T_NIEDOST, {"niedostepny": True})]:
        p = {"trener": t, "data": DATA}
        p.update(payload)
        post("/api/dostepnosc", p)
    # T_KOLIZJA ma już zajęcia 11:00–13:00 w innej szkole
    post("/api/event", {"lead_id": lead_id, "typ": "DT", "data": DATA,
                        "godz_od": "11:00", "godz_do": "13:00", "trener": T_KOLIZJA})

    print("\nP1 — kategorie kandydatów")
    conn = db.get_conn()
    lista = pz.kandydaci(conn, DATA, "10:00", "12:00", M1, event_id)
    conn.close()
    sprawdz("trener z deklaracją 8–16 i bez zajęć = wolny",
            znajdz(lista, T_WOLNY)["kategoria"] == "wolny",
            znajdz(lista, T_WOLNY)["powod"])
    sprawdz("trener z zajęciami 11–13 = zastrzeżenie (kolizja)",
            znajdz(lista, T_KOLIZJA)["kategoria"] == "zastrzezenie"
            and "kolizja" in znajdz(lista, T_KOLIZJA)["powod"],
            znajdz(lista, T_KOLIZJA)["powod"])
    sprawdz("trener dostępny 13–16 = zastrzeżenie (poza deklaracją)",
            znajdz(lista, T_POZA)["kategoria"] == "zastrzezenie"
            and "poza deklaracją" in znajdz(lista, T_POZA)["powod"],
            znajdz(lista, T_POZA)["powod"])
    sprawdz("trener oznaczony XXX = niedostępny",
            znajdz(lista, T_NIEDOST)["kategoria"] == "niedostepny")
    sprawdz("trener bez deklaracji = nieznany, NIE niedostępny",
            znajdz(lista, T_NIEZNANY)["kategoria"] == "nieznany",
            znajdz(lista, T_NIEZNANY)["powod"])
    sprawdz("na liście są wszyscy trenerzy ze słownika",
            len(lista) == len(trenerzy), "%d z %d" % (len(lista), len(trenerzy)))

    print("\nP2 — kolejność: wolni na górze, niedostępni na dole")
    kategorie = [k["kategoria"] for k in lista]
    sprawdz("kategorie posortowane wg wagi",
            kategorie == sorted(kategorie, key=pz.KATEGORIE.index))
    sprawdz("pierwszy kandydat jest wolny", lista[0]["kategoria"] == "wolny")
    sprawdz("ostatni kandydat jest niedostępny", lista[-1]["kategoria"] == "niedostepny")

    print("\nP3 — rejon podnosi kandydata w swojej kategorii")
    conn = db.get_conn()
    pz.ustaw_rejon(conn, T_NIEZNANY, [M1])
    conn.commit()
    lista2 = pz.kandydaci(conn, DATA, "10:00", "12:00", M1, event_id)
    conn.close()
    nieznani = [k for k in lista2 if k["kategoria"] == "nieznany"]
    sprawdz("trener z rejonu jest pierwszy w swojej kategorii",
            nieznani[0]["trener"] == T_NIEZNANY and nieznani[0]["rejon"] is True)
    sprawdz("rejon NIE usuwa pozostałych z listy",
            len(lista2) == len(trenerzy) and any(not k["rejon"] for k in lista2))
    conn = db.get_conn()
    lista3 = pz.kandydaci(conn, DATA, "10:00", "12:00", M2, event_id)
    conn.close()
    sprawdz("inne miasto → ten sam trener już nie ma flagi rejonu",
            znajdz(lista3, T_NIEZNANY)["rejon"] is False)

    print("\nP4 — spotkanie nie koliduje samo ze sobą")
    post("/api/event", {"lead_id": lead_id, "typ": "DT", "data": DATA,
                        "godz_od": "10:00", "godz_do": "12:00"})
    conn = db.get_conn()
    conn.execute("UPDATE eventy SET trener=? WHERE id=?", (T_WOLNY, event_id))
    conn.commit()
    lista4 = pz.kandydaci(conn, DATA, "10:00", "12:00", M1, event_id)
    conn.close()
    sprawdz("obecnie przypisany trener nadal jest 'wolny' (pomijamy jego wpis)",
            znajdz(lista4, T_WOLNY)["kategoria"] == "wolny",
            znajdz(lista4, T_WOLNY)["powod"])

    print("\nP5 — API /api/kandydaci")
    kod, d = get("/api/kandydaci?event_id=%d" % event_id)
    sprawdz("API po event_id zwraca grupy", kod == 200 and d["ok"] and d["grupy"])
    sprawdz("kontekst niesie miasto placówki", d["miasto"] == M1, str(d.get("miasto")))
    sprawdz("liczba wolnych policzona", d["n_wolnych"] >= 1, "n_wolnych=%s" % d["n_wolnych"])
    kod, d = get("/api/kandydaci?data=%s&godz_od=10:00&godz_do=12:00" % DATA)
    sprawdz("API działa też bez event_id (spotkanie jeszcze nie istnieje)",
            kod == 200 and d["ok"])
    kod, d = get("/api/kandydaci?data=")
    sprawdz("brak daty odrzucony (400)", kod == 400)
    kod, d = get("/api/kandydaci?event_id=999999")
    sprawdz("nieistniejące spotkanie → 404", kod == 404)

    print("\nP6 — przydzielenie nigdy nie jest blokowane")
    r = KL.patch("/api/event/%d" % event_id,
                 data=json.dumps({"field": "trener", "value": T_NIEDOST}),
                 content_type="application/json")
    d = r.get_json()
    sprawdz("przydzielenie NIEDOSTĘPNEGO trenera przechodzi",
            r.status_code == 200 and d["ok"])
    sprawdz("…ale wraca ostrzeżenie", bool(d.get("kolizja")), str(d.get("kolizja")))

    print("\nP7 — rejony: API i podpowiedź z historii")
    kod, d = post("/api/rejon", {"trener": T_WOLNY, "miasta": [M1, M2]})
    sprawdz("zapis rejonu (2 miasta)", kod == 200 and d["n"] == 2)
    kod, d = post("/api/rejon", {"trener": T_WOLNY, "miasta": [M2]})
    sprawdz("ponowny zapis PODMIENIA rejon, nie dokłada", kod == 200 and d["n"] == 1)
    kod, d = post("/api/rejon", {"trener": T_WOLNY, "miasta": ["Zmyślone Miasto"]})
    sprawdz("miasto spoza słownika odrzucone (400)", kod == 400)
    kod, d = post("/api/rejon", {"trener": "99. Niema Takiego", "miasta": [M1]})
    sprawdz("trener spoza słownika odrzucony (400)", kod == 400)
    kod, d = get("/api/rejon/podpowiedz?trener=%s" % T_KOLIZJA)
    sprawdz("podpowiedź bierze miasta z historii zajęć",
            kod == 200 and d["miasta"] and d["miasta"][0]["miasto"] == M1,
            str(d.get("miasta")))
    conn = db.get_conn()
    stan = pz.stan_rejonow(conn)
    conn.close()
    sprawdz("stan rejonów obejmuje wszystkich trenerów", len(stan) == len(trenerzy))

    print("\nP8 — ekrany się renderują")
    sprawdz("/rejony zwraca 200", KL.get("/rejony").status_code == 200)
    sprawdz("karta leada z panelem zwraca 200",
            KL.get("/lead/%d" % lead_id).status_code == 200)

    # Rejony z arkusza klienta — tabela `rejony` była pusta do 09.08, choć
    # klient ma te dane od dawna; podpowiedź trenera działała przez to ubożej.
    print("\nP7 — parser rejonów z arkusza „Trenerzy regiony”")
    _sprawdz_parser_rejonow(sprawdz)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
