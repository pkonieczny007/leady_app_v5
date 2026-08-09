# -*- coding: utf-8 -*-
"""
Testy v5: formularz terenowy + auto-zwrot przeterminowanych leadów.

Uruchomienie:  python test_formularz.py
Działa na WŁASNEJ, tymczasowej bazie (nie rusza żadnego profilu z `data/`).
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

TMP = tempfile.mkdtemp(prefix="leady_v5_fx_test_")
os.environ["DATA_DIR"] = TMP

import app as A                      # noqa: E402
import db                            # noqa: E402
import zwrot                         # noqa: E402
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

DZIS = dt.date.today()


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


def post(url, payload):
    r = KL.post(url, data=json.dumps(payload), content_type="application/json")
    return r.status_code, r.get_json()


def dni(n):
    return (DZIS + dt.timedelta(days=n)).isoformat()


def dodaj_lead(conn, nazwa, miasto, handlowiec=None, deadline=None, status=None):
    """Lead prosto w bazie — testujemy zwrot, nie ścieżkę tworzenia."""
    pid = conn.execute("INSERT INTO placowki (nazwa, miejscowosc, zrodlo) VALUES (?,?,?)",
                       (nazwa, miasto, "test")).lastrowid
    lid = conn.execute(
        "INSERT INTO leady (placowka_id, handlowiec, deadline, status_realizacji) "
        "VALUES (?,?,?,?)", (pid, handlowiec, deadline,
                             status or "01. Próba kontaktu (Brak konkretów)")).lastrowid
    conn.commit()
    return lid


def nazwy(lista):
    return sorted(x["placowka"] for x in lista)


def main():
    print("Baza testowa:", TMP)
    bootstrap()
    _zaloguj_testowo()
    conn = db.get_conn()
    handlowcy = db.slownik_values(conn, "handlowiec")
    trenerzy = db.slownik_values(conn, "trener")
    miasta = db.slownik_values(conn, "miasto")
    typy = db.slownik_values(conn, "typ_placowki")
    sprzet = db.slownik_values(conn, "sprzet")
    H, H2 = handlowcy[0], handlowcy[1]
    T, M = trenerzy[0], miasta[0]
    conn.close()

    # ==================================================== F1 — zapis formularza
    print("\nF1 — formularz zapisuje wszystko jednym żądaniem")

    kod, j = post("/api/formularz", {
        "handlowiec": H,
        "placowka": {"nazwa": "SP 1 Nowa", "miejscowosc": M, "typ": typy[0],
                     "adres": "ul. Szkolna 1"},
        "kontakt": {"osoba_kontakt": "Anna Dyrektor", "telefon": "500 600 700",
                    "mail": "sekretariat@sp1.pl"},
        "mail_rodzice": "01. Tak",
        "dt": {"data": dni(30), "godz_od": "09:00", "godz_do": "12:00", "trener": T,
               "numer_sali": "12", "ilosc_klas": "4", "ilosc_dzieci": "80",
               "uwagi": "zbiórka w holu"},
        "cykl": {"cykl_dzien": "wtorek", "godz_od": "14:00", "numer_sali": "5",
                 "sprzet": sprzet[0]},
    })
    sprawdz("zapis zwraca 200", kod == 200, str(j)[:120])
    lead_id = (j or {}).get("lead_id")
    sprawdz("powstał lead", bool(lead_id))
    sprawdz("odpowiedź niesie nazwę szkoły do potwierdzenia",
            (j or {}).get("placowka") == "SP 1 Nowa")
    sprawdz("powstały DWA spotkania (DT + cykl)", len((j or {}).get("eventy") or []) == 2)

    conn = db.get_conn()
    ev = {e["typ"]: dict(e) for e in conn.execute(
        "SELECT * FROM eventy WHERE lead_id=?", (lead_id,))}
    sprawdz("DT ma datę, godzinę i prowadzącego",
            ev["DT"]["data"] == dni(30) and ev["DT"]["godz_od"] == "09:00"
            and ev["DT"]["trener"] == T)
    sprawdz("liczby klas i dzieci zapisane jako liczby",
            ev["DT"]["ilosc_klas"] == 4 and ev["DT"]["ilosc_dzieci"] == 80)
    sprawdz("cykl ma dzień tygodnia, a nie datę",
            ev["CYKLICZNE"]["cykl_dzien"] == "wtorek" and not ev["CYKLICZNE"]["data"])

    lead = dict(conn.execute("SELECT * FROM leady WHERE id=?", (lead_id,)).fetchone())
    sprawdz("status leada poszedł na sukces", lead["status_realizacji"] == "03. DT umówione")
    sprawdz("lead trafił do handlowca, który wypełniał", lead["handlowiec"] == H)
    sprawdz("odpowiedź na maila do rodziców zapisana", lead["mail_rodzice"] == "01. Tak")

    pl = dict(conn.execute("SELECT * FROM placowki WHERE id=?",
                           (lead["placowka_id"],)).fetchone())
    sprawdz("kontakt z terenu wylądował przy placówce",
            pl["telefon"] == "500 600 700" and pl["osoba_kontakt"] == "Anna Dyrektor")
    sprawdz("źródło rekordu oznaczone jako formularz", pl["zrodlo"] == "formularz")
    log = [dict(r) for r in conn.execute("SELECT * FROM log WHERE lead_id=?", (lead_id,))]
    sprawdz("zapis zostawił ślad w historii", len(log) >= 2)
    conn.close()

    # ============================================ F2 — walidacja i przypadki brzegowe
    print("\nF2 — formularz nie wpuszcza śmieci do bazy")

    kod, j = post("/api/formularz", {"handlowiec": H, "placowka": {"nazwa": ""}})
    sprawdz("placówka bez nazwy odrzucona", kod == 400 and "nazw" in (j["error"] or "").lower())

    kod, j = post("/api/formularz", {
        "handlowiec": H,
        "placowka": {"nazwa": "SP 2", "miejscowosc": "Zmyślone Miasto"}})
    sprawdz("miejscowość spoza słownika odrzucona", kod == 400, (j or {}).get("error"))

    kod, j = post("/api/formularz", {
        "handlowiec": "Ktoś Kogo Nie Ma",
        "placowka": {"nazwa": "SP 3", "miejscowosc": M}})
    sprawdz("nieznany handlowiec odrzucony", kod == 400, (j or {}).get("error"))

    kod, j = post("/api/formularz", {
        "handlowiec": H,
        "placowka": {"nazwa": "SP 4 Bez DT", "miejscowosc": M},
        "dt": {"data": "", "godz_od": ""}})
    sprawdz("formularz bez daty DT zapisuje samą placówkę",
            kod == 200 and not (j or {}).get("eventy"))

    conn = db.get_conn()
    st = conn.execute("SELECT status_realizacji FROM leady WHERE id=?",
                      ((j or {}).get("lead_id"),)).fetchone()["status_realizacji"]
    sprawdz("lead bez DT NIE dostaje statusu sukcesu", not st.startswith("03."))
    conn.close()

    # formularz nie może po cichu odebrać szkoły innemu handlowcowi
    conn = db.get_conn()
    cudzy = dodaj_lead(conn, "SP 5 Cudza", M, handlowiec=H2)
    conn.close()
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": cudzy,
        "dt": {"data": dni(20), "godz_od": "10:00", "trener": T}})
    conn = db.get_conn()
    wlasciciel = conn.execute("SELECT handlowiec FROM leady WHERE id=?",
                              (cudzy,)).fetchone()["handlowiec"]
    conn.close()
    sprawdz("formularz nie przejmuje szkoły innego handlowca",
            kod == 200 and wlasciciel == H2)

    # ================================================== F3 — ekran wyboru wariantu
    print("\nF3 — wybór wariantu formularza")
    r = KL.get("/formularz")
    sprawdz("/formularz zwraca 200", r.status_code == 200)
    html = r.get_data(as_text=True)
    sprawdz("pokazuje DWA linki, nie kafelki", html.count('class="fw-link"') == 2)
    sprawdz("linki prowadzą do obu wariantów",
            "/formularz/kroki" in html and "/formularz/ciagly" in html)
    sprawdz("nazwy wariantów jak ustalone",
            "FORMULARZ v1" in html and "Formularz v2" in html)
    sprawdz("pyta, kto wypełnia", 'id="fw-kto"' in html)

    # ============================================ F4 — wariant 1 (krok po kroku)
    print("\nF4 — wariant 1: krok po kroku")
    sprawdz("/formularz/kroki zwraca 200", KL.get("/formularz/kroki").status_code == 200)
    html = KL.get("/formularz/kroki?handlowiec=" + H).get_data(as_text=True)
    sprawdz("cztery kroki", html.count('class="fx-krok"') == 4)
    sprawdz("dołącza własny arkusz stylów", "formularz.css" in html)
    sprawdz("nagłówki sekcji jak we wzorze klienta",
            "Dane placówki" in html and "Dzień Technologii" in html
            and "Zajęcia cykliczne" in html)

    # ============================================== F5 — wariant 2 (jeden ciągły)
    print("\nF5 — wariant 2: jeden ciągły, wg makiety klienta")
    sprawdz("/formularz/ciagly zwraca 200", KL.get("/formularz/ciagly").status_code == 200)
    html = KL.get("/formularz/ciagly?handlowiec=" + H).get_data(as_text=True)
    sprawdz("trzy sekcje makiety, jedna pod drugą", html.count('class="f2-sekcja"') == 3)
    sprawdz("para list Miejscowość → Placówka",
            'id="f2-miasto"' in html and 'id="f2-szkola"' in html)
    sprawdz("lista szkół zablokowana do czasu wyboru miasta",
            'id="f2-szkola" class="f2-pole" disabled' in html)
    sprawdz("stopka z dwoma przyciskami jak w makiecie",
            "Wyczyść formularz" in html and "Zapisz formularz" in html)
    sprawdz("pola z makiety obecne",
            "Numer sali DT" in html and "Ilość dzieci w klasach" in html
            and "Zajęcia cykliczne (dzień tygodnia)" in html)
    sprawdz("dołącza własny arkusz stylów", "formularz2.css" in html)

    # Oba warianty muszą zapisywać TAK SAMO — gdyby się rozjechały, klient
    # wybierałby między funkcjami, a nie między układem, i porównanie nic nie znaczy.
    kod2, j2 = post("/api/formularz", {
        "handlowiec": H,
        "placowka": {"nazwa": "SP 6 z wariantu 2", "miejscowosc": M},
        "cykle": "01. Tak",
        "mail_rodzice": "01. Tak",
        "dt": {"data": dni(25), "godz_od": "10:00", "trener": T,
               "ilosc_klas": "3", "ilosc_dzieci": "60"},
        "cykl": {"cykl_dzien": "środa", "godz_od": "13:00", "sprzet": sprzet[0]},
    })
    sprawdz("wariant 2 zapisuje przez to samo API", kod2 == 200, str(j2)[:110])
    sprawdz("wariant 2 też tworzy DT i cykl", len((j2 or {}).get("eventy") or []) == 2)
    conn = db.get_conn()
    sprawdz("pole „Cykle” z makiety trafia do leada",
            conn.execute("SELECT cykle FROM leady WHERE id=?",
                         ((j2 or {}).get("lead_id"),)).fetchone()["cykle"] == "01. Tak")
    conn.close()

    poz = KL.get("/api/placowki?miejscowosc=" + M + "&handlowiec=" + H).get_json()["pozycje"]
    sprawdz("lista placówek dla miasta niepusta", len(poz) > 0)
    sprawdz("oznacza szkoły handlowca", any(p["moja"] for p in poz))
    sprawdz("bez miasta zwraca pustą listę",
            KL.get("/api/placowki").get_json()["pozycje"] == [])

    # ================================================ A1 — awaria przy zapisie
    print("\nA1 — awaria w trakcie wysyłki: ponowienie nie tworzy dubla")

    # Scenariusz: zapis DOSZEDŁ, ale odpowiedź nie wróciła (zerwane LTE).
    # Formularz uzna to za błąd i zaproponuje „Ponów wysyłkę". Bez ochrony
    # druga próba stworzyłaby drugą szkołę i drugie DT.
    payload = {
        "handlowiec": H,
        "klucz_zapisu": "test-klucz-abc123",
        "placowka": {"nazwa": "SP 7 Zerwane Polaczenie", "miejscowosc": M},
        "mail_rodzice": "01. Tak",
        "dt": {"data": dni(18), "godz_od": "11:00", "trener": T,
               "ilosc_klas": "2", "ilosc_dzieci": "40"},
    }
    kod1, o1 = post("/api/formularz", payload)
    kod2, o2 = post("/api/formularz", payload)          # to samo, drugi raz
    sprawdz("pierwsza wysyłka przechodzi", kod1 == 200)
    sprawdz("ponowienie też odpowiada 200", kod2 == 200)
    sprawdz("ponowienie zwraca TEN SAM lead",
            (o1 or {}).get("lead_id") == (o2 or {}).get("lead_id"))
    sprawdz("ponowienie oznaczone jako powtórka", (o2 or {}).get("powtorka") is True)

    conn = db.get_conn()
    ile = conn.execute("SELECT COUNT(*) c FROM placowki WHERE nazwa=?",
                       ("SP 7 Zerwane Polaczenie",)).fetchone()["c"]
    sprawdz("powstała DOKŁADNIE JEDNA placówka, nie dwie", ile == 1, "jest %d" % ile)
    ile_dt = conn.execute("SELECT COUNT(*) c FROM eventy WHERE lead_id=? AND typ='DT'",
                          ((o1 or {}).get("lead_id"),)).fetchone()["c"]
    sprawdz("powstało DOKŁADNIE JEDNO DT, nie dwa", ile_dt == 1, "jest %d" % ile_dt)
    conn.close()

    # bez klucza (stary klient / ponowne kliknięcie) dubel powstaje — to celowe,
    # bo nie mamy jak odróżnić powtórki od świadomego drugiego wpisu
    bez = dict(payload); bez.pop("klucz_zapisu")
    bez["placowka"] = {"nazwa": "SP 8 Bez Klucza", "miejscowosc": M}
    kod3, o3 = post("/api/formularz", bez)
    kod4, o4 = post("/api/formularz", bez)
    sprawdz("bez klucza zapisu obie próby tworzą osobne leady",
            kod3 == 200 and kod4 == 200
            and (o3 or {}).get("lead_id") != (o4 or {}).get("lead_id"))

    print("\nA2 — pełny ekran i wyjście przez „Zakończ”")
    for adres, znacznik in (("/formularz/kroki", "v1"), ("/formularz/ciagly", "v2")):
        html = KL.get(adres + "?handlowiec=" + H).get_data(as_text=True)
        sprawdz("%s: brak nawigacji aplikacji" % znacznik,
                'class="nav' not in html and "Kalendarz DT</a>" not in html)
        sprawdz("%s: własny pasek z przyciskiem Zakończ" % znacznik,
                'class="f-pasek"' in html and "Zakończ</a>" in html)
        sprawdz("%s: body oznaczone jako pełny ekran" % znacznik,
                "f-pelny-ekran" in html)
        sprawdz("%s: dołączony moduł obsługi awarii" % znacznik,
                "formularz_awaria.js" in html)

    print("\nF6 — wyszukiwarka szkół (wariant 1)")
    r = KL.get("/api/placowki/szukaj?q=" + "sp 1")
    poz = r.get_json()["pozycje"]
    sprawdz("wyszukiwarka znajduje po nazwie", any(p["nazwa"] == "SP 1 Nowa" for p in poz))
    r = KL.get("/api/placowki/szukaj?q=" + M[:4] + "&handlowiec=" + H)
    poz = r.get_json()["pozycje"]
    sprawdz("wyszukiwarka znajduje po mieście", len(poz) > 0)
    sprawdz("szkoły handlowca wychodzą przed pozostałymi",
            not poz or poz[0]["moja"] or not any(p["moja"] for p in poz))
    sprawdz("jedna litera nie odpala wyszukiwania",
            KL.get("/api/placowki/szukaj?q=a").get_json()["pozycje"] == [])

    # ======================================================= Z1 — auto-zwrot
    print("\nZ1 — auto-zwrot: co wraca do puli, a co nie")

    conn = db.get_conn()
    conn.execute("DELETE FROM leady")
    conn.execute("DELETE FROM placowki")
    conn.commit()

    # Od 09.08 bez karencji PO terminie (decyzja Przemka za intencją Kasi):
    # lead wraca pierwszego dnia po terminie, a 2 dni to ostrzeżenie PRZED nim.
    K = zwrot.KARENCJA_DNI
    sprawdz("konfiguracja zgodna z decyzją 08.08: karencja 0, ostrzeżenie 2 dni",
            K == 0 and zwrot.OSTRZEZENIE_DNI == 2,
            "K=%d, O=%d" % (K, zwrot.OSTRZEZENIE_DNI))
    l_przetermin = dodaj_lead(conn, "A przeterminowana", M, H, dni(-5))
    l_wczoraj = dodaj_lead(conn, "B termin wczoraj", M, H, dni(-1))
    l_dzis = dodaj_lead(conn, "C termin dziś", M, H, dni(0))
    l_za2 = dodaj_lead(conn, "D2 termin za 2 dni", M, H, dni(2))
    l_przyszly = dodaj_lead(conn, "D termin w przyszłości", M, H, dni(10))
    l_sukces = dodaj_lead(conn, "E po terminie, ale sukces", M, H, dni(-5),
                          "03. DT umówione")
    l_odpadl = dodaj_lead(conn, "F odpadła", M, H, dni(-5),
                          "04. BRAK KONTAKTU ZE SZKOŁĄ")
    l_niczyja = dodaj_lead(conn, "G niczyja", M, None, dni(-5))
    l_bezterminu = dodaj_lead(conn, "H bez terminu", M, H, None)
    # po terminie, ale w kalendarzu wisi DT — sukces po faktach, nie po statusie
    l_ma_dt = dodaj_lead(conn, "I ma DT w kalendarzu", M, H, dni(-5))
    conn.execute("INSERT INTO eventy (lead_id, typ, data, trener) VALUES (?,?,?,?)",
                 (l_ma_dt, "DT", dni(5), T))
    conn.commit()

    lista = zwrot.do_zwrotu(conn)
    sprawdz("wracają leady po terminie — już od pierwszego dnia po nim",
            nazwy(lista) == ["A przeterminowana", "B termin wczoraj"],
            str(nazwy(lista)))
    sprawdz("termin dziś jeszcze nie wraca (wróci jutro)",
            not any(x["id"] == l_dzis for x in lista))
    sprawdz("lead z sukcesem nie wraca nigdy",
            not any(x["id"] == l_sukces for x in lista))
    sprawdz("lead odpadnięty nie wraca", not any(x["id"] == l_odpadl for x in lista))
    sprawdz("lead niczyj nie wraca (nie ma komu odbierać)",
            not any(x["id"] == l_niczyja for x in lista))
    sprawdz("lead bez terminu nie wraca",
            not any(x["id"] == l_bezterminu for x in lista))
    sprawdz("lead z DT w kalendarzu nie wraca mimo braku statusu",
            not any(x["id"] == l_ma_dt for x in lista))
    sprawdz("lead z terminem w przyszłości nie wraca",
            not any(x["id"] == l_przyszly for x in lista))

    # ================================================ Z2 — ostrzeżenia dla handlowca
    print("\nZ2 — ostrzeżenie PRZED terminem, nie po nim")

    zag = zwrot.zagrozone(conn, handlowiec=H)
    nz = nazwy(zag)
    sprawdz("ostrzeżenie pali się już 2 dni PRZED terminem",
            "D2 termin za 2 dni" in nz, str(nz))
    sprawdz("widzi też lead z terminem dziś", "C termin dziś" in nz)
    sprawdz("terminu za 10 dni jeszcze nie pokazujemy (bez szumu)",
            "D termin w przyszłości" not in nz)
    sprawdz("nie ostrzegamy o leadzie z DT", "I ma DT w kalendarzu" not in nz)
    sprawdz("nie ostrzegamy o leadzie z sukcesem", "E po terminie, ale sukces" not in nz)
    c = [x for x in zag if x["placowka"] == "C termin dziś"][0]
    sprawdz("ostrzeżenie mówi, ILE dni zostało (termin dziś → wraca jutro)",
            c["dni_do_zwrotu"] == 1, "dni_do_zwrotu=%s" % c["dni_do_zwrotu"])
    d2 = [x for x in zag if x["placowka"] == "D2 termin za 2 dni"][0]
    sprawdz("ostrzeżenie podaje datę zwrotu (dzień po terminie)",
            d2.get("wraca_dnia") == dni(3), str(d2.get("wraca_dnia")))
    sprawdz("najpilniejsze na górze listy",
            zag == sorted(zag, key=lambda x: x["dni_do_zwrotu"]))
    sprawdz("ostrzeżenia filtrowane po handlowcu",
            zwrot.zagrozone(conn, handlowiec=H2) == [])
    conn.close()

    # ==================================================== Z3 — wykonanie zwrotu
    print("\nZ3 — zwrot oddaje przypisanie, ale nie kasuje pracy")

    conn = db.get_conn()
    conn.execute("UPDATE leady SET uwagi=?, pin_tydzien=? WHERE id=?",
                 ("dyrektor prosił o kontakt we wrześniu", "2026-08-03", l_przetermin))
    conn.commit()
    conn.close()

    kod, j = post("/api/zwrot", {})
    sprawdz("API zwrotu odpowiada 200", kod == 200)
    sprawdz("zwrócono oba leady po terminie", (j or {}).get("n") == 2, str(j)[:120])

    conn = db.get_conn()
    r = dict(conn.execute("SELECT * FROM leady WHERE id=?", (l_przetermin,)).fetchone())
    sprawdz("handlowiec wyczyszczony", not r["handlowiec"])
    sprawdz("termin wyczyszczony (inaczej wisiałby 'po terminie' na zawsze)",
            not r["deadline"])
    sprawdz("przypięcie na tydzień zdjęte", not r["pin_tydzien"])
    sprawdz("status wrócił na nieprzydzielony",
            r["status_realizacji"] == zwrot.STATUS_PO_ZWROCIE, r["status_realizacji"])
    sprawdz("NOTATKI HANDLOWCA ZOSTAŁY", r["uwagi"] == "dyrektor prosił o kontakt we wrześniu")

    wpis = conn.execute("SELECT * FROM log WHERE lead_id=? AND co LIKE 'auto-zwrot%'",
                        (l_przetermin,)).fetchone()
    sprawdz("w historii jest ślad, kto miał lead", wpis is not None and wpis["przed"] == H)
    sprawdz("ślad oznaczony jako działanie systemu, nie handlowca",
            wpis is not None and wpis["kto"] in ("automat", "koordynator"))

    sprawdz("drugie wywołanie nic nie zwraca (nie ma już czego)",
            len(zwrot.wykonaj(conn)) == 0)

    # lead po zwrocie musi być widoczny w puli nieprzydzielonych
    import repo
    f = repo.pusty_filtr(); f["zakres"] = "nieprzydzielone"
    pula = [x["id"] for x in repo.filtruj_leady(conn, f)]
    sprawdz("zwrócony lead jest w puli nieprzydzielonych", l_przetermin in pula)
    conn.close()

    # ==================================================== Z4 — przebieg automatu
    print("\nZ4 — automat sam się pilnuje, bez crona")

    conn = db.get_conn()
    conn.execute("UPDATE leady SET handlowiec=?, deadline=? WHERE id=?",
                 (H, dni(-5), l_przetermin))
    conn.commit()

    teraz = dt.datetime.now()
    db.meta_set(conn, zwrot.META_KLUCZ, (teraz - dt.timedelta(minutes=5)).isoformat())
    conn.commit()
    sprawdz("5 minut po ostatnim przebiegu automat odpuszcza",
            zwrot.przeglad(conn, teraz=teraz) == [])

    db.meta_set(conn, zwrot.META_KLUCZ,
                (teraz - dt.timedelta(minutes=zwrot.CO_ILE_MINUT + 1)).isoformat())
    conn.commit()
    sprawdz("po godzinie automat przelatuje", len(zwrot.przeglad(conn, teraz=teraz)) == 1)
    sprawdz("znacznik przebiegu zapisany", bool(db.meta_get(conn, zwrot.META_KLUCZ)))

    db.meta_set(conn, zwrot.META_KLUCZ, "to nie jest data")
    conn.commit()
    zwrot.przeglad(conn, teraz=teraz)
    sprawdz("zepsuty znacznik nie wywala automatu",
            db.meta_get(conn, zwrot.META_KLUCZ) != "to nie jest data")
    conn.close()

    kod, j = KL.get("/api/zwrot/podglad").status_code, KL.get("/api/zwrot/podglad").get_json()
    sprawdz("podgląd automatu odpowiada 200", kod == 200)
    sprawdz("podgląd podaje karencję", (j or {}).get("karencja") == zwrot.KARENCJA_DNI)

    # ============================== Z5 — „świeci się, że wróciła" (Kasia, 08.08)
    # Po Z4 lead wrócił automatem, więc jego OSTATNI wpis w historii to auto-zwrot
    # — dokładnie wtedy plakietka na /baza ma się palić.
    print("\nZ5 — zwrócona szkoła świeci na /baza, dopóki nikt jej nie ruszy")
    html = KL.get("/baza").get_data(as_text=True)
    sprawdz("na /baza jest plakietka zwrotu", "tag-zwrot" in html)
    sprawdz("plakietka dotyczy zwróconego leada", '"%d"' % l_przetermin in html)

    # pierwszy ruch człowieka (ponowne przypisanie) ma zgasić plakietkę sam z siebie;
    # przypisujemy OBA zwrócone leady — bez karencji w Z3 wróciły A i B
    post("/api/przypisz", {"ids": [l_przetermin, l_wczoraj],
                           "handlowiec": H, "deadline": dni(10)})
    html = KL.get("/baza").get_data(as_text=True)
    sprawdz("po przypisaniu plakietka gaśnie", "tag-zwrot" not in html)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
