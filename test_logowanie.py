# -*- coding: utf-8 -*-
"""
Testy v5: logowanie PIN-em, role, domyślny filtr „moje szkoły", CSRF.

Uruchomienie:  python test_logowanie.py
Działa na WŁASNEJ, tymczasowej bazie.
"""
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

TMP = tempfile.mkdtemp(prefix="leady_v5_log_test_")
os.environ["DATA_DIR"] = TMP
os.environ["PIN_KOORDYNATORA"] = "7391"

import app as A                      # noqa: E402
import db                            # noqa: E402
import uzytkownicy as uz             # noqa: E402
from seed import bootstrap           # noqa: E402

WYNIKI = []
KOORD, PIN_K = "Koordynator", "7391"


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


def klient():
    """Świeży klient = świeża sesja. Każda rola dostaje własnego."""
    return A.app.test_client()


def zaloguj(kl, osoba, pin):
    r = kl.post("/api/logowanie", json={"osoba": osoba, "pin": pin})
    if r.status_code == 200:
        # token CSRF podstawiamy wprost — testujemy uprawnienia, nie przeglądarkę
        with kl.session_transaction() as s:
            s["csrf"] = "t"
        kl.environ_base["HTTP_X_CSRF"] = "t"
    return r.status_code, r.get_json()


def main():
    print("Baza testowa:", TMP)
    bootstrap()
    conn = db.get_conn()
    uz.bootstrap_konta(conn, db.slownik_values(conn, "handlowiec"))
    handlowcy = db.slownik_values(conn, "handlowiec")
    H, H2 = handlowcy[0], handlowcy[1]
    miasto = db.slownik_values(conn, "miasto")[0]
    conn.close()

    # ================================================ L1 — nic bez logowania
    print("\nL1 — bez logowania nie ma dostępu do niczego")
    goscie = klient()
    for sciezka in ("/", "/pulpit", "/leady", "/baza", "/formularz",
                    "/lead/1", "/kalendarz", "/uzytkownicy", "/export.xlsx"):
        r = goscie.get(sciezka)
        sprawdz("%s odsyła do logowania" % sciezka,
                r.status_code == 302 and "/logowanie" in r.headers.get("Location", ""),
                "status %d" % r.status_code)
    sprawdz("/logowanie jest dostępne", goscie.get("/logowanie").status_code == 200)
    sprawdz("pliki statyczne są dostępne",
            goscie.get("/static/style.css").status_code == 200)

    r = goscie.post("/api/formularz", json={})
    sprawdz("API bez sesji zwraca 401, nie przekierowanie", r.status_code == 401)
    sprawdz("API mówi wprost, że sesja wygasła",
            "esja" in (r.get_json() or {}).get("error", ""))

    # ============================================ L2 — PIN: dobry, zły, blokada
    print("\nL2 — logowanie PIN-em")
    kl = klient()
    kod, j = zaloguj(kl, KOORD, "0000")
    sprawdz("zły PIN odrzucony", kod == 401)
    sprawdz("komunikat nie zdradza, czy osoba istnieje",
            "PIN" in (j or {}).get("error", "") and "nie ma" not in (j or {}).get("error", "").lower())
    kod, j = zaloguj(kl, "Nie Ma Takiego", "1234")
    sprawdz("nieznana osoba odrzucona tak samo", kod == 401)

    kod, j = zaloguj(kl, KOORD, PIN_K)
    sprawdz("dobry PIN wpuszcza", kod == 200, str(j))
    sprawdz("odpowiedź niesie rolę", (j or {}).get("rola") == "koordynator")
    sprawdz("koordynator ląduje na pulpicie", (j or {}).get("dalej") == "/pulpit")
    sprawdz("po zalogowaniu ekrany działają", kl.get("/pulpit").status_code == 200)

    conn = db.get_conn()
    sprawdz("licznik nieudanych wyzerowany po udanym wejściu",
            uz.znajdz(conn, KOORD)["nieudane"] == 0)
    sprawdz("zapisana data ostatniego logowania",
            bool(uz.znajdz(conn, KOORD)["ostatnie_logowanie"]))

    # blokada po serii błędnych prób
    uz.utworz(conn, "TEST-blokada", "handlowiec", "1379")
    conn.close()
    kb = klient()
    for i in range(uz.MAX_PROB):
        zaloguj(kb, "TEST-blokada", "0000")
    kod, j = zaloguj(kb, "TEST-blokada", "1379")
    sprawdz("po %d błędach konto blokuje się mimo dobrego PIN-u" % uz.MAX_PROB,
            kod == 401 and "ablokowan" in (j or {}).get("error", ""),
            (j or {}).get("error", "")[:60])

    conn = db.get_conn()
    uz.ustaw_pin(conn, "TEST-blokada", "2468")
    conn.close()
    kod, j = zaloguj(kb, "TEST-blokada", "2468")
    sprawdz("nadanie nowego PIN-u odblokowuje konto", kod == 200)

    # wylogowanie
    kw = klient(); zaloguj(kw, KOORD, PIN_K)
    kw.get("/wyloguj")
    sprawdz("po wylogowaniu znów odsyła do logowania",
            kw.get("/pulpit").status_code == 302)

    # ==================================================== L3 — role
    print("\nL3 — role: handlowiec widzi swoje, koordynator wszystko")
    conn = db.get_conn()
    uz.ustaw_pin(conn, H, "1111")
    conn.close()
    kh = klient()
    kod, j = zaloguj(kh, H, "1111")
    sprawdz("handlowiec się loguje", kod == 200)
    sprawdz("handlowiec ląduje na formularzu", (j or {}).get("dalej") == "/formularz")

    for sciezka in ("/formularz", "/formularz/kroki", "/formularz/ciagly",
                    "/leady", "/tydzien", "/kalendarz", "/dostepnosc"):
        sprawdz("handlowiec wchodzi na %s" % sciezka,
                kh.get(sciezka).status_code == 200)

    for sciezka in ("/baza", "/zbiorczy", "/niewykorzystane", "/slowniki",
                    "/import", "/uzytkownicy", "/pulpit", "/rejony"):
        r = kh.get(sciezka)
        sprawdz("handlowiec NIE wchodzi na %s" % sciezka, r.status_code == 302,
                "status %d" % r.status_code)

    r = kh.post("/api/przypisz", json={"ids": [1], "handlowiec": H})
    sprawdz("handlowiec nie przypisze sobie szkoły przez API", r.status_code == 403)
    r = kh.post("/api/zwrot", json={})
    sprawdz("handlowiec nie uruchomi automatu zwrotu", r.status_code == 403)
    r = kh.post("/api/uzytkownik/pin", json={"osoba": KOORD})
    sprawdz("handlowiec nie zresetuje cudzego PIN-u", r.status_code == 403)

    sprawdz("nawigacja handlowca nie ma pozycji koordynatora",
            "Słowniki</a>" not in kh.get("/leady").get_data(as_text=True))
    sprawdz("nawigacja koordynatora ma Konta",
            "Konta</a>" in kl.get("/pulpit").get_data(as_text=True))

    # ======================================= L4 — filtr „moje" domyślny, zdejmowalny
    print("\nL4 — filtr własnych szkół: przypięty, ale zmienialny")
    conn = db.get_conn()
    pid = conn.execute("INSERT INTO placowki (nazwa, miejscowosc) VALUES (?,?)",
                       ("Moja Szkola", miasto)).lastrowid
    conn.execute("INSERT INTO leady (placowka_id, handlowiec, status_realizacji) "
                 "VALUES (?,?,?)", (pid, H, "01. Próba kontaktu (Brak konkretów)"))
    pid2 = conn.execute("INSERT INTO placowki (nazwa, miejscowosc) VALUES (?,?)",
                        ("Cudza Szkola", miasto)).lastrowid
    conn.execute("INSERT INTO leady (placowka_id, handlowiec, status_realizacji) "
                 "VALUES (?,?,?)", (pid2, H2, "01. Próba kontaktu (Brak konkretów)"))
    conn.commit(); conn.close()

    html = kh.get("/leady").get_data(as_text=True)
    sprawdz("domyślnie widzi swoją szkołę", "Moja Szkola" in html)
    sprawdz("domyślnie NIE widzi cudzej", "Cudza Szkola" not in html)
    sprawdz("widać, że filtr jest włączony", "Pokazuję tylko Twoje szkoły" in html)
    sprawdz("jest jak go zdjąć", "Pokaż wszystkie" in html)

    html = kh.get("/leady?handlowiec=").get_data(as_text=True)
    sprawdz("po zdjęciu filtra widzi cudze szkoły", "Cudza Szkola" in html)
    sprawdz("i wie, że filtr jest zdjęty",
            "szkoły wszystkich handlowców" in html)

    html = kh.get("/leady").get_data(as_text=True)
    sprawdz("WRACA do swoich po zwykłym wejściu na ekran",
            "Cudza Szkola" not in html and "Moja Szkola" in html)

    html = kh.get("/leady?handlowiec=" + H2).get_data(as_text=True)
    sprawdz("może obejrzeć konkretnego kolegę", "Cudza Szkola" in html)

    html = kl.get("/leady").get_data(as_text=True)
    sprawdz("koordynator domyślnie widzi WSZYSTKICH",
            "Moja Szkola" in html and "Cudza Szkola" in html)
    sprawdz("koordynator nie ma wskaźnika 'tylko twoje'",
            "Pokazuję tylko Twoje szkoły" not in html)

    # ==================================================== L5 — CSRF
    print("\nL5 — CSRF: zapis bez tokenu odrzucony")
    kc = klient()
    zaloguj(kc, KOORD, PIN_K)
    kc.environ_base.pop("HTTP_X_CSRF", None)
    r = kc.post("/api/przypisz", json={"ids": [1], "handlowiec": H})
    sprawdz("zapis bez tokenu odrzucony", r.status_code == 403)
    sprawdz("komunikat podpowiada odświeżenie",
            "dśwież" in (r.get_json() or {}).get("error", ""))
    kc.environ_base["HTTP_X_CSRF"] = "t"
    r = kc.post("/api/przypisz", json={"ids": [1], "handlowiec": H})
    sprawdz("z tokenem ten sam zapis przechodzi", r.status_code == 200)
    sprawdz("odczyty nie wymagają tokenu", kc.get("/pulpit").status_code == 200)

    # ============================== L6 — formularz podpisuje się sesją, nie ciałem
    print("\nL6 — nie da się podpisać cudzym nazwiskiem")
    r = kh.post("/api/formularz", json={
        "handlowiec": H2,                       # próba podszycia się pod kolegę
        "placowka": {"nazwa": "SP Podszycie", "miejscowosc": miasto},
        "dt": {"data": "2026-10-01", "godz_od": "09:00"}})
    sprawdz("zapis przechodzi", r.status_code == 200, str(r.get_json())[:90])
    conn = db.get_conn()
    wl = conn.execute(
        "SELECT l.handlowiec FROM leady l JOIN placowki p ON p.id=l.placowka_id "
        "WHERE p.nazwa=?", ("SP Podszycie",)).fetchone()["handlowiec"]
    conn.close()
    sprawdz("właściciel wzięty z SESJI, nie z żądania", wl == H, "jest %s" % wl)

    conn = db.get_conn()
    kto = conn.execute("SELECT kto FROM log ORDER BY id DESC LIMIT 1").fetchone()["kto"]
    conn.close()
    sprawdz("historia notuje prawdziwego autora, nie 'demo'", kto == H, "jest %s" % kto)

    # ==================================================== L7 — panel kont
    print("\nL7 — panel kont koordynatora")
    r = kl.post("/api/uzytkownik", json={"osoba": "TEST-nowy", "rola": "handlowiec"})
    j = r.get_json()
    sprawdz("konto zakładane z wygenerowanym PIN-em",
            r.status_code == 200 and uz.poprawny_format((j or {}).get("pin")),
            "pin=%s" % (j or {}).get("pin"))
    kn = klient()
    sprawdz("nowe konto od razu działa",
            zaloguj(kn, "TEST-nowy", j["pin"])[0] == 200)

    r = kl.post("/api/uzytkownik", json={"osoba": "TEST-nowy", "rola": "handlowiec"})
    sprawdz("dublet konta odrzucony", r.status_code == 400)

    r = kl.post("/api/uzytkownik/pin", json={"osoba": "TEST-nowy", "pin": "12"})
    sprawdz("PIN krótszy niż 4 cyfry odrzucony", r.status_code == 400)
    r = kl.post("/api/uzytkownik/pin", json={"osoba": "TEST-nowy", "pin": "abcd"})
    sprawdz("PIN z literami odrzucony", r.status_code == 400)

    r = kl.patch("/api/uzytkownik", json={"osoba": KOORD, "rola": "handlowiec"})
    sprawdz("ostatni koordynator nie może zdegradować sam siebie",
            r.status_code == 400 and "jedyny" in (r.get_json() or {}).get("error", ""))

    conn = db.get_conn()
    sprawdz("generator PIN-u omija oczywiste kombinacje",
            all(uz.losowy_pin() not in ("0000", "1234", "1111") for _ in range(60)))
    sprawdz("PIN w bazie trzymany jako skrót, nie jawnie",
            "1111" not in str(uz.znajdz(conn, H)["pin_hash"]))
    sprawdz("dwa te same PIN-y dają różne skróty (sól per konto)",
            uz.zahashuj("1111")[1] != uz.zahashuj("1111")[1])
    conn.close()

    r = kl.delete("/api/uzytkownik", json={"osoba": KOORD})
    sprawdz("nie da się usunąć konta, na którym się pracuje", r.status_code == 400)
    r = kl.delete("/api/uzytkownik", json={"osoba": "TEST-nowy"})
    sprawdz("obce konto da się usunąć", r.status_code == 200)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
