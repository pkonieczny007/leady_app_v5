# -*- coding: utf-8 -*-
"""
Testy v5: formularz terenowy + auto-zwrot przeterminowanych leadów.

Uruchomienie:  python test_formularz.py
Działa na WŁASNEJ, tymczasowej bazie (nie rusza żadnego profilu z `data/`).
"""
import datetime as dt
import json
import os
import re
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
    sprawdz("pokazuje linki, nie kafelki", html.count("fw-link") >= 4)
    sprawdz("linki prowadzą do wszystkich wariantów",
            "/formularz/kroki" in html and "/formularz/ciagly" in html
            and "/formularz/v3" in html and "/formularz/cykliczne" in html)
    # Wersaliki „FORMULARZ v1" wyglądały jak wyróżnienie jednego wariantu
    # przy trzech pisanych normalnie — stąd jednolita pisownia (prośba 17.08).
    sprawdz("nazwy wariantów jak ustalone",
            "Formularz v1" in html and "Formularz v2" in html
            and "Formularz v3" in html and "Formularz CYKLICZNE" in html
            and "FORMULARZ v1" not in html)
    sprawdz("v3 opisany jako rekomendowany", "Rekomendowany" in html)
    sprawdz("wariant cykliczny opisany jako testowy",
            "testowy: CYKLICZNE-PRZEDSZKOLE" in html)
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

    # ====================================== F5b — wariant 3 (v2 + żywa dostępność)
    # Z uwag po teście na telefonie 09.08: w v2 dało się wybrać trenera
    # niedostępnego i dowiedzieć się o tym dopiero po zapisie.
    print("\nF5b — wariant 3: podpowiedź prowadzącego")
    r3 = KL.get("/formularz/v3")
    sprawdz("/formularz/v3 zwraca 200", r3.status_code == 200)
    html3 = KL.get("/formularz/v3?handlowiec=" + H).get_data(as_text=True)
    sprawdz("v3 ma układ v2 — te same trzy sekcje",
            html3.count('class="f2-sekcja"') == 3)
    sprawdz("plakietka statusu wybranego prowadzącego",
            'id="f3-status"' in html3)
    sprawdz("plakietka startuje ukryta (nie ma czego pokazywać bez daty)",
            'id="f3-status" hidden' in html3.replace('"\n', '" '))
    sprawdz("podgląd dnia całej firmy", 'id="f3-dzien"' in html3)
    sprawdz("własny arkusz stylów obok stylów v2",
            "formularz3.css" in html3 and "formularz2.css" in html3)
    sprawdz("własny skrypt, nie skrypt v2",
            "formularz3.js" in html3 and "formularz2.js" not in html3)
    sprawdz("v3 mówi wprost, że rejon nie ukrywa nikogo",
            "nikogo nie ukrywa" in html3)

    # v3 MUSI zapisywać tym samym API co v1 i v2 — inaczej klient wybierałby
    # między funkcjami zamiast między układem.
    sprawdz("v3 nie ma własnego adresu zapisu",
            "/api/formularz" in open("static/formularz3.js", encoding="utf-8").read())

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
    for adres, znacznik in (("/formularz/kroki", "v1"), ("/formularz/ciagly", "v2"),
                            ("/formularz/v3", "v3")):
        html = KL.get(adres + "?handlowiec=" + H).get_data(as_text=True)
        sprawdz("%s: brak nawigacji aplikacji" % znacznik,
                'class="nav' not in html and "Kalendarz DT</a>" not in html)
        sprawdz("%s: własny pasek z przyciskiem Zakończ" % znacznik,
                'class="f-pasek"' in html and "Zakończ</a>" in html)
        sprawdz("%s: body oznaczone jako pełny ekran" % znacznik,
                "f-pelny-ekran" in html)
        sprawdz("%s: dołączony moduł obsługi awarii" % znacznik,
                "formularz_awaria.js" in html)

    # ================================ F5c — „Plan na dziś" wspólny dla wariantów
    # Ze spotkania: koordynator w weekend wybiera szkoły z terminem, handlowiec
    # w terenie na nich pracuje. Do 09.08 termin docierał do przeglądarki
    # (moje[].deadline) i nie był nigdzie pokazywany — ścieżka urywała się
    # w formularzu.
    print("\nF5c — plan od koordynatora we wszystkich trzech wariantach")
    for adres, znacznik in (("/formularz/kroki", "v1"), ("/formularz/ciagly", "v2"),
                            ("/formularz/v3", "v3")):
        h = KL.get(adres + "?handlowiec=" + H).get_data(as_text=True)
        sprawdz("%s: sekcja planu jest" % znacznik, 'id="fx-plan"' in h)
        sprawdz("%s: wspólny skrypt planu" % znacznik, "fx_plan.js" in h)
        sprawdz("%s: dane szkół z terminami" % znacznik, "FX_MOJE" in h)
    sprawdz("wszystkie warianty używają JEDNEGO fragmentu szablonu",
            "_plan_dnia.html" in open("templates/formularz.html", encoding="utf-8").read()
            and "_plan_dnia.html" in open("templates/formularz2.html", encoding="utf-8").read()
            and "_plan_dnia.html" in open("templates/formularz3.html", encoding="utf-8").read())

    # pozycja planu musi nieść to, czego potrzebuje lista: termin, stan, gwiazdkę
    r = KL.get("/formularz/v3?handlowiec=" + H)
    h = r.get_data(as_text=True)
    sprawdz("dane niosą termin", '"deadline"' in h)
    sprawdz("dane niosą informację o umówionym DT", '"ma_dt"' in h)
    sprawdz("dane niosą gwiazdkę planu tygodnia", '"pin"' in h)
    sprawdz("dane niosą właściciela (dla cudzych przypiętych)", '"wlasciciel"' in h)

    # Gwiazdka na CUDZEJ szkole: handlowiec bywa w terenie „przy okazji" pod
    # szkołą kolegi i przypina ją sobie na tydzień. Ma się pojawić w planie,
    # ale z jawnym właścicielem — przypisanie ma swojego gospodarza.
    conn = db.get_conn()
    pid_c = conn.execute("INSERT INTO placowki (nazwa, miejscowosc) VALUES (?,?)",
                         ("SP Kolegi Przypieta", M)).lastrowid
    lid_c = conn.execute("INSERT INTO leady (placowka_id, handlowiec, status_realizacji) "
                         "VALUES (?,?,?)", (pid_c, H2, "01. Próba")).lastrowid
    conn.commit(); conn.close()
    # Przypięcie robimy „ręką handlowca H": w tym pliku klient testowy jest
    # zalogowany jako koordynator, a o tym, czyja to gwiazdka, rozstrzyga autor
    # wpisu w historii (kolumna `pin_tydzien` niesie samą datę).
    post("/api/pin", {"id": lid_c, "pin": True})
    conn = db.get_conn()
    conn.execute("UPDATE log SET kto=? WHERE lead_id=? AND co='plan tygodnia'",
                 (H, lid_c))
    conn.commit(); conn.close()
    h = KL.get("/formularz/v3?handlowiec=" + H).get_data(as_text=True)
    sprawdz("cudza szkoła przypięta gwiazdką wchodzi do planu",
            "SP Kolegi Przypieta" in h)
    sprawdz("i niesie nazwisko właściciela do ostrzeżenia", H2 in h)

    # cudza szkoła przypięta przez KOGOŚ INNEGO nie ma prawa się pojawić —
    # inaczej plan zapełniłby się gwiazdkami całego zespołu
    conn = db.get_conn()
    conn.execute("UPDATE log SET kto=? WHERE lead_id=? AND co='plan tygodnia'",
                 (H2, lid_c))
    conn.commit(); conn.close()
    h = KL.get("/formularz/v3?handlowiec=" + H).get_data(as_text=True)
    sprawdz("cudza gwiazdka kolegi NIE wchodzi do mojego planu",
            "SP Kolegi Przypieta" not in h)

    conn = db.get_conn()
    conn.execute("UPDATE log SET kto=? WHERE lead_id=? AND co='plan tygodnia'",
                 (H, lid_c))
    conn.commit(); conn.close()
    post("/api/pin", {"id": lid_c, "pin": False})
    h = KL.get("/formularz/v3?handlowiec=" + H).get_data(as_text=True)
    sprawdz("po zdjęciu gwiazdki cudza szkoła znika z planu",
            "SP Kolegi Przypieta" not in h)

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

    # ================================ FC — wariant CYKLICZNE i pakiety terminów
    #
    # Sedno: zajęcia umówione na KONKRETNE daty mają pojawić się w kalendarzu
    # dokładnie tyle razy, ile ich uzgodniono. Reguła „co wtorek" rozwija się
    # do horyzontu 40 tygodni — pakiet pięciu spotkań ma się skończyć na piątym.
    print("\nFC — wariant CYKLICZNE: pakiet konkretnych terminów")
    import calendar_view as cv

    r = KL.get("/formularz/cykliczne")
    sprawdz("/formularz/cykliczne zwraca 200", r.status_code == 200)
    html = r.get_data(as_text=True)
    sprawdz("ma wybór rodzaju zajęć",
            'value="CYKLICZNE-PRZEDSZKOLE"' in html and 'name="f4-typ"' in html)
    sprawdz("ma wybór sposobu ustalania terminów",
            'value="daty"' in html and 'value="regula"' in html)
    sprawdz("ma pola startu i ilości zajęć",
            'id="f4-start"' in html and 'id="f4-ile"' in html)
    sprawdz("niesie sekcję DT z v3 (nie jest okrojony)", 'id="f3-status"' in html)

    conn = db.get_conn()
    pid = conn.execute("INSERT INTO placowki (nazwa, miejscowosc) VALUES (?,?)",
                       ("Przedszkole Testowe", M)).lastrowid
    l_cykl = conn.execute("INSERT INTO leady (placowka_id) VALUES (?)", (pid,)).lastrowid
    conn.commit()
    conn.close()

    # wtorki: 18.08, 25.08, 01.09, 08.09, 15.09 — przykład wprost z ustaleń
    PAKIET = ["2026-08-18", "2026-08-25", "2026-09-01", "2026-09-08", "2026-09-15"]
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_cykl,
        "cykl": {"typ": "CYKLICZNE-PRZEDSZKOLE", "godz_od": "09:30",
                 "cykl_dzien": "wtorek", "numer_sali": "żółta",
                 "terminy": [{"data": d, "godz_od": "09:30"} for d in PAKIET]}})
    sprawdz("pakiet zapisuje się jednym żądaniem", kod == 200)
    sprawdz("odpowiedź podaje, ile terminów zapisano",
            bool(j) and j["eventy"] and j["eventy"][0].get("terminy") == 5)

    conn = db.get_conn()
    ev = conn.execute("SELECT * FROM eventy WHERE lead_id=?", (l_cykl,)).fetchone()
    sprawdz("powstał JEDEN event, nie pięć",
            conn.execute("SELECT COUNT(*) c FROM eventy WHERE lead_id=?",
                         (l_cykl,)).fetchone()["c"] == 1)
    sprawdz("event ma typ przedszkolny", ev["typ"] == "CYKLICZNE-PRZEDSZKOLE")
    # `data` eventu to pierwszy termin — na tej kolumnie stoją sortowania,
    # statystyki i warunek `WHERE e.data IS NOT NULL` w kalendarzu
    sprawdz("data eventu = pierwsze zajęcia", ev["data"] == PAKIET[0])
    terminy = conn.execute("SELECT * FROM terminy_cyklu WHERE event_id=? ORDER BY nr",
                           (ev["id"],)).fetchall()
    sprawdz("zapisano wszystkie pięć terminów", len(terminy) == 5)
    sprawdz("terminy ponumerowane po dacie",
            [t["data"] for t in terminy] == PAKIET and
            [t["nr"] for t in terminy] == [1, 2, 3, 4, 5])

    sierpien = cv.events_for_month(conn, "2026-08", typy=["CYKLICZNE-PRZEDSZKOLE"])
    wrzesien = cv.events_for_month(conn, "2026-09", typy=["CYKLICZNE-PRZEDSZKOLE"])
    pazdziernik = cv.events_for_month(conn, "2026-10", typy=["CYKLICZNE-PRZEDSZKOLE"])
    sprawdz("kalendarz pokazuje 2 zajęcia w sierpniu", len(sierpien) == 2)
    sprawdz("kalendarz pokazuje 3 zajęcia we wrześniu", len(wrzesien) == 3)
    # TO JEST TEN TEST. Reguła „co wtorek" dołożyłaby cztery zajęcia
    # w październiku, których nikt nie umawiał — pakiet kończy się na piątym.
    sprawdz("pakiet NIE ciągnie się dalej niż umówiono", len(pazdziernik) == 0)
    sprawdz("wystąpienia niosą numer zajęć w pakiecie",
            [e["_cykl_nr"] for e in wrzesien] == [3, 4, 5])

    # Filtr „tylko cykliczne" ma łapać OBA warianty — koordynatorka szukająca
    # zajęć cyklicznych nie ma wiedzieć, że istnieją dwa typy w bazie.
    oba = cv.events_for_month(conn, "2026-09", typy=list(db.TYPY_CYKLICZNE))
    sprawdz("filtr cykliczny łapie wariant przedszkolny", len(oba) >= 3)
    sprawdz("miesiąc pakietu jest w wyborze miesięcy",
            "2026-09" in cv.available_months(conn))
    conn.close()

    # Karta szkoły musi pokazać CAŁY pakiet. Bez tego widać jedną datę
    # (pierwszą), a pozostałe cztery istnieją wyłącznie w kalendarzu.
    html = KL.get("/lead/%d" % l_cykl).get_data(as_text=True)
    sprawdz("karta szkoły wymienia terminy pakietu", "Terminy pakietu" in html)
    sprawdz("karta pokazuje ostatni termin pakietu", "15.09" in html or PAKIET[-1] in html)

    # --- odsiewanie śmieci -------------------------------------------------
    conn = db.get_conn()
    l_smiec = conn.execute("INSERT INTO leady (placowka_id) VALUES (?)", (pid,)).lastrowid
    conn.commit()
    conn.close()
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_smiec,
        "cykl": {"typ": "CYKLICZNE-PRZEDSZKOLE", "godz_od": "10:00",
                 "terminy": [{"data": "2026-09-01"}, {"data": "2026-09-01"},
                             {"data": ""}, {"data": "2026-13-45"},
                             {"data": "2026-08-25"}]}})
    sprawdz("dubel i śmieć w datach nie wywracają zapisu", kod == 200)
    sprawdz("zostają dwie sensowne daty, posortowane",
            bool(j) and j["eventy"][0].get("terminy") == 2)
    conn = db.get_conn()
    porz = [t["data"] for t in conn.execute(
        "SELECT t.data FROM terminy_cyklu t JOIN eventy e ON e.id=t.event_id "
        "WHERE e.lead_id=? ORDER BY t.nr", (l_smiec,)).fetchall()]
    sprawdz("pierwszy termin to najwcześniejsza data", porz == ["2026-08-25", "2026-09-01"])
    conn.close()

    # --- typ spoza słownika ------------------------------------------------
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_smiec,
        "cykl": {"typ": "CYKLICZNE-ZLOBEK", "terminy": [{"data": "2026-09-02"}]}})
    sprawdz("typ zajęć spoza słownika ODRZUCONY, nie zapisany po cichu", kod == 400)

    # --- reguła „co wtorek" działa jak dotąd -------------------------------
    conn = db.get_conn()
    l_regula = conn.execute("INSERT INTO leady (placowka_id) VALUES (?)", (pid,)).lastrowid
    conn.commit()
    conn.close()
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_regula,
        "cykl": {"typ": "CYKLICZNE", "cykl_dzien": "wtorek", "godz_od": "12:00",
                 "data": "2026-08-18", "co_ile_tygodni": 1}})
    sprawdz("stary sposób (reguła) zapisuje się bez zmian", kod == 200)
    conn = db.get_conn()
    eid = conn.execute("SELECT id FROM eventy WHERE lead_id=?", (l_regula,)).fetchone()["id"]
    sprawdz("reguła nie zakłada listy terminów",
            conn.execute("SELECT COUNT(*) c FROM terminy_cyklu WHERE event_id=?",
                         (eid,)).fetchone()["c"] == 0)
    pazdz = [e for e in cv.events_for_month(conn, "2026-10", typy=["CYKLICZNE"])
             if e["lead_id"] == l_regula]
    sprawdz("reguła nadal ciągnie się w kolejne miesiące", len(pazdz) >= 4)
    conn.close()

    # ============================== FD — zajęcia cykliczne BEZ Dnia Technologii
    #
    # Cykl umawia się często bez świeżego DT: albo już był (i siedzi w bazie),
    # albo placówka wchodzi w cykl bez dnia pokazowego. Zapis samego pakietu
    # nie ma tworzyć zmyślonego DT — wymyślony DT ląduje na grafiku trenera
    # i ktoś na niego pojedzie.
    print("\nFD — pakiet zajęć bez Dnia Technologii")
    html = KL.get("/formularz/cykliczne").get_data(as_text=True)
    sprawdz("formularz ma wyłącznik DT", 'id="f4-dt-wl"' in html)
    sprawdz("wyłącznik domyślnie włączony",
            re.search(r'id="f4-dt-wl"[^>]*checked', html) is not None)
    sprawdz("wyłączona sekcja tłumaczy, co się stanie", 'id="f4-dt-brak"' in html)

    conn = db.get_conn()
    l_bezdt = conn.execute("INSERT INTO leady (placowka_id, status_realizacji) "
                           "VALUES (?,?)", (pid, "01. Próba kontaktu (Brak konkretów)")).lastrowid
    conn.commit()
    conn.close()

    # tak wygląda żądanie z wyłączonym DT: bloku `dt` po prostu nie ma
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_bezdt,
        "cykle": "01. Tak",
        "cykl": {"typ": "CYKLICZNE-PRZEDSZKOLE", "godz_od": "09:00",
                 "terminy": [{"data": "2026-09-07"}, {"data": "2026-09-14"},
                             {"data": "2026-09-21"}]}})
    sprawdz("zapis bez bloku DT przechodzi", kod == 200)
    sprawdz("powstały same zajęcia cykliczne",
            bool(j) and len(j["eventy"]) == 1 and j["eventy"][0]["terminy"] == 3)

    conn = db.get_conn()
    sprawdz("NIE powstało żadne DT",
            conn.execute("SELECT COUNT(*) c FROM eventy WHERE lead_id=? AND typ='DT'",
                         (l_bezdt,)).fetchone()["c"] == 0)
    # Status „03. DT umówione" ustawia się WYŁĄCZNIE przy tworzeniu DT. Gdyby
    # skakał też przy samym cyklu, lista „umówione DT" liczyłaby szkoły,
    # w których nikt DT nie umawiał — a to jest miara pracy handlowców.
    st = conn.execute("SELECT status_realizacji, dt FROM leady WHERE id=?",
                      (l_bezdt,)).fetchone()
    sprawdz("status leada nie skoczył na „DT umówione”",
            not (st["status_realizacji"] or "").startswith("03. DT"))
    sprawdz("znacznik DT leada nietknięty", not st["dt"])
    conn.close()

    # Kalendarz ma pokazać zajęcia mimo braku DT — to jest cały sens zapisu.
    conn = db.get_conn()
    wrzesien = [e for e in cv.events_for_month(conn, "2026-09") if e["lead_id"] == l_bezdt]
    sprawdz("zajęcia bez DT są widoczne w kalendarzu", len(wrzesien) == 3)
    conn.close()

    # --- P04: zmiana szkoły podmienia dane kontaktowe (zgłoszenie K09) -------
    #
    # „wybrałam z listy rozwijanej szkołę, uzupełniły się dane typu osoba do
    # kontaktu, a potem zmieniłam szkołę, to osoba się nie zmieniła, została
    # z poprzedniego wyboru" — Kasia, 20.08.
    #
    # Sprawdzamy w ŹRÓDLE, a nie przez przeglądarkę, bo to zachowanie czystego
    # JS-a bez wywołania serwera. Ważniejsze i tak jest to, że wszystkie trzy
    # warianty robią to TAK SAMO: gdyby się rozjechały, klient wybierałby między
    # funkcjami, a nie między układem.
    print("\n-- P04: dane kontaktowe przy zmianie szkoły --")
    zrodla = {}
    for w in ("formularz2", "formularz3", "formularz4"):
        zrodla[w] = open("static/%s.js" % w, encoding="utf-8").read()

    for w, kod in zrodla.items():
        sprawdz("%s: nie ma już warunku „wpisz tylko, gdy pusto”" % w,
                'if (!$("f2-osoba").value)' not in kod)
        sprawdz("%s: podstawia kontakt jedną funkcją" % w,
                "function podstawKontakt(" in kod and "podstawKontakt(stan.wybrana)" in kod)
        # Pusta wartość MUSI czyścić pole — inaczej szkoła bez kontaktu
        # dziedziczy dane poprzedniej, czyli dokładnie zgłoszony błąd.
        sprawdz("%s: pusta wartość ze szkoły czyści pole" % w,
                'var nowa = (szkola && szkola[mapa[i][1]]) || "";' in kod
                and "pole.value = nowa;" in kod)
        sprawdz("%s: mówi o podmianie zamiast robić ją po cichu" % w,
                "Dane kontaktowe podmienione" in kod)

    def helper(kod):
        a = kod.index("function podstawKontakt(")
        return kod[a:kod.index("selSzkola.addEventListener", a)].strip()

    sprawdz("wszystkie trzy warianty podstawiają kontakt IDENTYCZNIE",
            helper(zrodla["formularz2"]) == helper(zrodla["formularz3"])
            == helper(zrodla["formularz4"]))

    # --- P06: lista szkół to CAŁA baza miejscowości (zgłoszenie K04) ---------
    #
    # „na liście miast przy wpisywaniu DT katoice pojawiają się tylko jako moje
    # 12 szkół, nie ma całej listy plaówek" — Kasia, PILNE.
    #
    # Lista nigdy nie była zawężona: myliło ją „(twoje: 12)" doklejone do nazwy
    # miasta, czytane jako liczba szkół w Katowicach. Ten test pilnuje obu stron:
    # że serwer naprawdę oddaje wszystko i że dopisek nie wrócił.
    print("\n-- P06: lista szkół nie jest zawężona do własnych --")
    conn = db.get_conn()
    for nazwa, wlasciciel in (("SP 100 cudza", None), ("SP 101 cudza", None),
                              ("SP 102 moja", H)):
        cur = conn.execute("INSERT INTO placowki (nazwa, miejscowosc, zrodlo) "
                           "VALUES (?,?,'test')", (nazwa, M))
        conn.execute("INSERT INTO leady (placowka_id, handlowiec) VALUES (?,?)",
                     (cur.lastrowid, wlasciciel))
    conn.commit()
    # Liczymy przez to samo złączenie co endpoint: lista wyboru pokazuje LEADY,
    # a placówka z dwoma leadami wchodzi na nią dwa razy. To osobna sprawa
    # (w produkcji jest 1:1) i nie mieszamy jej do sprawdzenia zawężania.
    wszystkich = conn.execute(
        "SELECT COUNT(*) c FROM leady l JOIN placowki p ON p.id = l.placowka_id "
        "WHERE p.miejscowosc=?", (M,)).fetchone()["c"]
    conn.close()

    r = KL.get("/api/placowki?miejscowosc=" + M + "&handlowiec=" + H)
    poz = (r.get_json() or {}).get("pozycje") or []
    sprawdz("serwer oddaje WSZYSTKIE szkoły miejscowości, nie tylko moje",
            len(poz) == wszystkich, "%d z %d" % (len(poz), wszystkich))
    sprawdz("wśród nich są cudze", any(not p["moja"] for p in poz))
    sprawdz("własne są oznaczone", any(p["moja"] for p in poz))

    for w, kod in zrodla.items():
        sprawdz("%s: nie dokleja już „(twoje: N)” do nazwy miasta" % w,
                '"  (twoje: " + licz[o.value]' not in kod)
        sprawdz("%s: miasto z własnymi szkołami znaczone gwiazdką" % w,
                'o.textContent = "★ " + o.textContent' in kod)
        sprawdz("%s: mówi wprost, że to cała baza miejscowości" % w,
                "cała baza" in kod)

    # --- P07: filtrowanie listy szkół z klawiatury (zgłoszenie K08) ---------
    #
    # „jedno pole jest potrzebne w wyszukiwaniu sam numer szkoły jak wpiszę
    # miasto i numer że mi przefiltruje a nie szukam na liscie" — Kasia.
    print("\n-- P07: filtr listy szkół --")
    for w in ("formularz2", "formularz3", "formularz4"):
        html = open("templates/%s.html" % w, encoding="utf-8").read()
        sprawdz("%s: szablon ma pole filtrowania" % w,
                'id="f2-szkola-szukaj"' in html)
        sprawdz("%s: pole startuje ukryte" % w,
                'autocomplete="off" hidden' in html)
        sprawdz("%s: filtruje bez pytania serwera" % w,
                "function rysujSzkoly(" in zrodla[w] and "function pasuje(" in zrodla[w])
        sprawdz("%s: ogonki nie przeszkadzają w szukaniu" % w,
                "function bezOgonkow(" in zrodla[w])
        sprawdz("%s: wybrana szkoła nie znika przy filtrowaniu" % w,
                "lista = [indeks[bylo]].concat(lista);" in zrodla[w])

    def blok_wyboru(kod):
        a = kod.index("  /* P07 (zgłoszenie K08 Kasi")
        return kod[a:kod.index("if (poWczytaniu) poWczytaniu();", a)]

    sprawdz("wszystkie trzy warianty filtrują IDENTYCZNIE",
            blok_wyboru(zrodla["formularz2"]) == blok_wyboru(zrodla["formularz3"])
            == blok_wyboru(zrodla["formularz4"]))

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
