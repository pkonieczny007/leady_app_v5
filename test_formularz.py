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
import geografia                     # noqa: E402
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

    # MIEJSCOWOŚĆ NIE JEST JUŻ POZYCJĄ SŁOWNIKA (etap M6: osią filtrowania został
    # powiat). Nowa nazwa PRZECHODZI — bo w terenie trafiają się przysiółki,
    # których słownik nie zna, a odmowa zapisu znaczy notatkę na kartce.
    # Zaporą nie jest teraz lista, tylko widoczność: nazwa nieznana rejestrowi
    # nie dostaje powiatu i placówka ląduje na liście „bez powiatu” do wyjaśnienia,
    # zamiast po cichu wpaść w przypadkowy.
    kod, j = post("/api/formularz", {
        "handlowiec": H,
        "placowka": {"nazwa": "SP 2", "miejscowosc": "Zmyślone Miasto"}})
    conn = db.get_conn()
    nowa = conn.execute("SELECT miejscowosc, powiat FROM placowki WHERE nazwa='SP 2'"
                        ).fetchone()
    conn.close()
    sprawdz("nieznana miejscowość przechodzi, ale bez powiatu",
            kod == 200 and nowa["miejscowosc"] == "Zmyślone Miasto"
            and not nowa["powiat"], str(dict(nowa)) if nowa else "brak rekordu")

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
            and "/formularz/v3" in html and "/formularz/cykliczne" in html
            and "/formularz/v5" in html)
    # Wersaliki „FORMULARZ v1" wyglądały jak wyróżnienie jednego wariantu
    # przy trzech pisanych normalnie — stąd jednolita pisownia (prośba 17.08).
    sprawdz("nazwy wariantów jak ustalone",
            "Formularz v1" in html and "Formularz v2" in html
            and "Formularz v3" in html and "Formularz CYKLICZNE" in html
            and "FORMULARZ v1" not in html)
    sprawdz("v3 opisany jako rekomendowany", "Rekomendowany" in html)
    sprawdz("wariant cykliczny opisany jako testowy",
            "testowy: CYKLICZNE-PRZEDSZKOLE" in html)
    # Piąty kafelek MUSI być opisany jako testowy — kto wejdzie z ciekawości,
    # ma wiedzieć, na czym stoi. To był warunek decyzji „v5 obok, nie zamiast".
    sprawdz("piąty wariant jest i jest opisany jako testowy",
            "Formularz v5" in html and "testowy: kaskada" in html)
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
    # Trzy sekcje z makiety klienta + „Wynik wizyty" dołożony 20.08 (P22).
    # Makieta zakładała, że wizyta zawsze kończy się umówieniem DT — Kasia po
    # dwóch tygodniach pracy poprosiła o miejsce na pozostałe zakończenia.
    sprawdz("sekcje makiety plus wynik wizyty, jedna pod drugą",
            html.count('class="f2-sekcja"') == 4)
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
    sprawdz("v3 ma układ v2 — te same cztery sekcje",
            html3.count('class="f2-sekcja"') == 4)
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

    # --- zakładanie placówki wypadło z WSZYSTKICH wariantów (Kasia, 24.08) ---
    #
    # „usuń tę możliwość, bo to powoduje, że PH wpisują coś z ręki sami i będą
    # się dublować rzeczy, a wpisują nazwy jak popadnie".
    #
    # Sprawdzamy komplet pięciu, a nie tego jednego, którego akurat używają:
    # gdyby furtka została w jednym wariancie, handlowiec zakładałby placówki
    # tamtym, a porównanie wariantów przestałoby dotyczyć układu. Zapora jest
    # w interfejsie i przy zapisie (`test_uprawnienia.py`) — sam brak przycisku
    # niczego nie zamyka, bo zapis idzie zwykłym `fetch`.
    print("\n-- placówki zakłada koordynator: żaden wariant już nie proponuje --")
    for w, pliki in (("v1", ("formularz.js", "formularz.html")),
                     ("v2", ("formularz2.js", "formularz2.html")),
                     ("v3", ("formularz3.js", "formularz3.html")),
                     ("v4", ("formularz4.js", "formularz4.html")),
                     ("v5", ("formularz5.js", "formularz5.html"))):
        js = open("static/%s" % pliki[0], encoding="utf-8").read()
        html = open("templates/%s" % pliki[1], encoding="utf-8").read()
        sprawdz("%s: nie ma przycisku „dodaj nową placówkę”" % w,
                "nowa-otworz" not in html and "nowa-otworz" not in js)
        sprawdz("%s: nie ma pól nowej placówki" % w, "nowa-nazwa" not in html)
        sprawdz("%s: nie wysyła bloku `placowka` do API" % w,
                "d.placowka =" not in js and "payload.placowka =" not in js)
        sprawdz("%s: placówkę bez leada wysyła jako `placowka_id`" % w,
                "placowka_id = stan.wybrana.placowka_id" in js
                or "placowka_id = stan.placowka.placowka_id" in js)
        # OSTRZEŻENIE PRZY WYJŚCIU MUSI GASNĄĆ PO ZAPISIE.
        #
        # Zgłoszenie Pawła 24.08: „w v5 przy zapisie zacina się" — i nie było
        # w tym nic losowego. `FxAwaria.pilnujWyjscia` wiesza na oknie
        # `beforeunload`, a udany zapis kończy się `location.reload()`, czyli
        # WYJŚCIEM ze strony. Bez flagi „już zapisane" przeglądarka blokuje
        # przeładowanie własnym okienkiem, a ekran stoi z napisem „Zapisuję…",
        # bo przycisk się nie odblokowuje. Zapis DOCHODZI do bazy; zacina się
        # powrót — czyli najgorszy rodzaj usterki, bo wygląda na utratę pracy.
        #
        # Warianty 1–4 mają tę flagę od czerwca, v5 jej nie przejął. Sprawdzamy
        # komplet, bo to jest dokładnie ta klasa różnic między wariantami,
        # która ma nie istnieć.
        sprawdz("%s: ostrzeżenie przy wyjściu gaśnie po udanym zapisie" % w,
                "if (zapisano) return false;" in js and "zapisano = true" in js)

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

    # --- P23: szkoła schodzi z „Planu na dziś" (zgłoszenie Zuzi) -------------
    #
    # „dodam jej że byłam i dt ustalone to ona z tej listy nie znika, słabo bo
    # nadal widzę ze mam do zrobienia 12 na ten tydzień" — Zuzia, 20.08.
    #
    # Do teraz „zrobione" brało się WYŁĄCZNIE z datowanego wpisu DT, więc szkoła
    # domknięta samym statusem wisiała jako zadanie na zawsze, a licznik liczył
    # robotę już wykonaną.
    print("\n-- P23: co znika z listy zadań --")
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO placowki (nazwa, miejscowosc, zrodlo) "
                       "VALUES ('SP 200 zadanie', ?, 'test')", (M,))
    l_zad = conn.execute(
        "INSERT INTO leady (placowka_id, handlowiec, deadline, status_realizacji) "
        "VALUES (?,?,?,?)",
        (cur.lastrowid, H, "2026-12-01", "01. Próba kontaktu (Brak konkretów)")).lastrowid
    conn.commit()

    def pozycja_planu(lead_id):
        c2 = db.get_conn()
        kontekst = A._kontekst_formularza(c2, H)
        c2.close()
        for p in kontekst["moje"]:
            if p["lead_id"] == lead_id:
                return p
        return None

    conn.close()
    p = pozycja_planu(l_zad)
    sprawdz("szkoła bez DT i bez sukcesu jest zadaniem",
            p is not None and not p["zrobione"], str(p and p["zrobione"]))

    # 1) domknięcie SAMYM STATUSEM, bez terminu DT — to jest sedno zgłoszenia
    conn = db.get_conn()
    conn.execute("UPDATE leady SET status_realizacji='03. DT umówione' WHERE id=?",
                 (l_zad,))
    conn.commit()
    conn.close()
    p = pozycja_planu(l_zad)
    sprawdz("status sukcesu wystarczy, żeby zeszła z zadań",
            p is not None and p["zrobione"])
    sprawdz("ale nadal wiadomo, że nie ma terminu DT",
            p is not None and not p["ma_dt"])

    # 2) druga droga: datowane DT bez zmiany statusu
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO placowki (nazwa, miejscowosc, zrodlo) "
                       "VALUES ('SP 201 z terminem', ?, 'test')", (M,))
    l_dt = conn.execute(
        "INSERT INTO leady (placowka_id, handlowiec, deadline, status_realizacji) "
        "VALUES (?,?,?,?)",
        (cur.lastrowid, H, "2026-12-01", "01. Próba kontaktu (Brak konkretów)")).lastrowid
    conn.execute("INSERT INTO eventy (lead_id, typ, data, godz_od) "
                 "VALUES (?, 'DT', '2026-12-15', '09:00')", (l_dt,))
    conn.commit()
    conn.close()
    p = pozycja_planu(l_dt)
    sprawdz("datowane DT też zdejmuje z zadań", p is not None and p["zrobione"])

    plan = open("static/fx_plan.js", encoding="utf-8").read()
    sprawdz("lista zadań pyta o `zrobione`, nie o sam termin DT",
            "function zrobione(p)" in plan and "!zrobione(p)" in plan)
    sprawdz("zrobiona szkoła bez DT nie kłamie napisem „DT umówione”",
            "function opisZrobionego(p)" in plan)
    sprawdz("jest wejście do odświeżenia listy bez przeładowania",
            "window.FX_PLAN_ZROBIONE" in plan)
    for w in ("formularz", "formularz2", "formularz3", "formularz4"):
        kod = open("static/%s.js" % w, encoding="utf-8").read()
        sprawdz("%s: po zapisie zdejmuje szkołę z listy od razu" % w,
                "FX_PLAN_ZROBIONE(j.lead_id)" in kod)

    # --- P22: zapis wizyty BEZ terminu DT (zgłoszenie Kasi) -----------------
    #
    # „musza byc opcje w formularzu ze bez daty dt można wprowadzić szkołę
    # i wybrać z listy rozwijanej opcje (…) I pole uwagi do wpisania notatki".
    #
    # Do 20.08 formularz wymagał kompletu sześciu pól DT, więc „byłam, dyrektor
    # się zastanawia" nie dawało się zapisać w ogóle.
    print("\n-- P22: wizyta bez terminu DT --")
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO placowki (nazwa, miejscowosc, zrodlo) "
                       "VALUES ('SP 300 bez DT', ?, 'test')", (M,))
    l_bez = conn.execute("INSERT INTO leady (placowka_id, handlowiec) VALUES (?,?)",
                         (cur.lastrowid, H)).lastrowid
    conn.commit()
    conn.close()

    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_bez,
        "status_realizacji": "02. Próba kontaktu (czekam na termin)",
        "uwagi": "Dyrektor wraca z urlopu 5.09, dzwonić po 10:00.",
    })
    sprawdz("zapis bez bloku DT i bez cyklu przechodzi", kod == 200, str(j)[:110])

    conn = db.get_conn()
    row = conn.execute("SELECT status_realizacji, uwagi FROM leady WHERE id=?",
                       (l_bez,)).fetchone()
    ile_ev = conn.execute("SELECT COUNT(*) c FROM eventy WHERE lead_id=?",
                          (l_bez,)).fetchone()["c"]
    conn.close()
    sprawdz("wynik wizyty zapisany na leadzie",
            row["status_realizacji"] == "02. Próba kontaktu (czekam na termin)",
            str(row["status_realizacji"]))
    sprawdz("notatka zapisana", "Dyrektor wraca" in (row["uwagi"] or ""))
    sprawdz("NIE powstało żadne spotkanie", ile_ev == 0, "eventów: %d" % ile_ev)

    # Szkoła z takim wynikiem dalej JEST zadaniem — trzeba do niej wrócić.
    # To odróżnia „czekam na termin" od „DT umówione" i pilnuje, żeby P23
    # nie zdjęło z listy czegoś, co jeszcze wymaga ruchu.
    p = pozycja_planu(l_bez)
    sprawdz("„czekam na termin” nie zdejmuje szkoły z zadań",
            p is not None and not p["zrobione"])

    # Pusty wybór nie kasuje tego, co już zapisano — formularz wysyła pola
    # zawsze, także gdy człowiek ich nie ruszył.
    post("/api/formularz", {"handlowiec": H, "lead_id": l_bez,
                            "status_realizacji": "", "uwagi": ""})
    conn = db.get_conn()
    row = conn.execute("SELECT status_realizacji, uwagi FROM leady WHERE id=?",
                       (l_bez,)).fetchone()
    conn.close()
    sprawdz("pusty wynik nie kasuje zapisanego statusu",
            row["status_realizacji"] == "02. Próba kontaktu (czekam na termin)")
    sprawdz("pusta notatka nie kasuje zapisanej", "Dyrektor wraca" in (row["uwagi"] or ""))

    kod, j = post("/api/formularz", {"handlowiec": H, "lead_id": l_bez,
                                     "status_realizacji": "Wymyślony status"})
    sprawdz("status spoza słownika odrzucony", kod == 400, str(j)[:90])

    for w in ("formularz2", "formularz3", "formularz4"):
        html = open("templates/%s.html" % w, encoding="utf-8").read()
        sprawdz("%s: sekcja „Wynik wizyty” jest w szablonie" % w,
                'id="f2-wynik"' in html and 'id="f2-uwagi"' in html)
        sprawdz("%s: stany techniczne „00.” nie trafiają do terenu" % w,
                "not v.startswith('00.')" in html)
        kod_js = open("static/%s.js" % w, encoding="utf-8").read()
        sprawdz("%s: wynik i notatka jadą w zapisie" % w,
                "d.status_realizacji = $(\"f2-wynik\").value;" in kod_js
                and "d.uwagi = $(\"f2-uwagi\").value.trim();" in kod_js)
        sprawdz("%s: pola DT wymagane tylko przy umawianiu DT" % w,
                "zaczetyDT" in kod_js or "czyDT()" in kod_js)
        sprawdz("%s: szkic pamięta wynik i notatkę" % w,
                '"f2-wynik", "f2-uwagi"' in kod_js)

    # --- P27: DT wolno zapisać niekompletny (zgłoszenie Zuzi, p. 2) ---------
    #
    # „Możemy ustalić, że szkoła chce DT, ale dokładna godzina, liczba klas czy
    # liczba dzieci zostanie podana później." Przez wymóg kompletu nie dało się
    # wprowadzić prawie całego jej tygodnia w terenie.
    print("\n-- P27: DT bez kompletu danych --")
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO placowki (nazwa, miejscowosc, zrodlo) "
                       "VALUES ('SP 301 niepelny DT', ?, 'test')", (M,))
    l_nie = conn.execute("INSERT INTO leady (placowka_id, handlowiec) VALUES (?,?)",
                         (cur.lastrowid, H)).lastrowid
    conn.commit()
    conn.close()

    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_nie,
        "dt": {"data": "2026-12-15"},          # sama data — reszta „będzie później"
    })
    sprawdz("DT z samą datą przechodzi", kod == 200, str(j)[:110])
    conn = db.get_conn()
    ev = conn.execute("SELECT data, godz_od, trener, ilosc_klas, ilosc_dzieci "
                      "FROM eventy WHERE lead_id=?", (l_nie,)).fetchone()
    conn.close()
    sprawdz("spotkanie powstało z datą", ev and ev["data"] == "2026-12-15")
    sprawdz("i bez reszty pól — nikt ich nie zmyślił",
            ev and not ev["godz_od"] and not ev["ilosc_klas"] and not ev["ilosc_dzieci"])

    # Druga połowa P27 (P30): skoro zapis wolno zostawić niepełny, kalendarz
    # MUSI o tym mówić. Bez tego „zapisane" znaczyłoby „gotowe".
    import calendar_view as _cv
    conn = db.get_conn()
    braki = [e["braki"] for e in _cv.events_for_month(conn, "2026-12")
             if e["lead_id"] == l_nie]
    conn.close()
    sprawdz("kalendarz nazywa braki po imieniu",
            braki and braki[0] == ["godzina", "liczba klas", "liczba dzieci"],
            str(braki))

    # Data zostaje twarda: bez niej serwer pomija cały blok DT, więc godzina
    # i liczby wpisane obok przepadłyby po cichu.
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_nie,
        "status_realizacji": "02c. Czekam na decyzję",
        "dt": {"godz_od": "09:00", "ilosc_klas": 3},
    })
    conn = db.get_conn()
    ile = conn.execute("SELECT COUNT(*) c FROM eventy WHERE lead_id=?",
                       (l_nie,)).fetchone()["c"]
    conn.close()
    sprawdz("blok DT bez daty nie tworzy spotkania-widma", ile == 1,
            "eventów: %d" % ile)

    for w in ("formularz2", "formularz3", "formularz4"):
        kod_js = open("static/%s.js" % w, encoding="utf-8").read()
        sprawdz("%s: z pól DT twarda jest tylko data" % w,
                "POLA_DT" in kod_js and "wpisaneDT(POLA_DT[0])" in kod_js
                and "Podaj godzinę DT." not in kod_js)
        sprawdz("%s: braki są mówione, nie milczane" % w,
                "do uzupełnienia" in kod_js)
        # Toast podmienia treść, więc dwa wywołania obok siebie zjadają się
        # nawzajem — ostrzeżenia muszą iść jednym komunikatem.
        sprawdz("%s: ostrzeżenia zbierane w jedno" % w,
                "var ostrz = []" in kod_js)

    # ==================================================== F7 — wariant 5 (kaskada)
    print("\nF7 — wariant 5: kaskada od placówki")
    r5 = KL.get("/formularz/v5")
    sprawdz("/formularz/v5 zwraca 200", r5.status_code == 200)
    html5 = KL.get("/formularz/v5?handlowiec=" + H).get_data(as_text=True)
    sprawdz("cztery kroki kaskady", html5.count('class="f2-sekcja f5-krok"') == 4)
    sprawdz("kroki 2–4 zwinięte do czasu wyboru placówki",
            html5.count('data-krok="2" id="f5-sek-kontakt" hidden') == 1)
    sprawdz("dołącza własny arkusz stylów", "formularz5.css" in html5)
    # Chipy rodzajów mają iść ze SŁOWNIKA — inaczej dołożenie rodzaju zajęć
    # wymagałoby zmiany w kodzie, a klient dokłada pozycje sam.
    sprawdz("chipy rodzajów z tego, co jest w słowniku",
            'data-typ="DT"' in html5 and 'data-typ="FESTYN"' in html5)
    sprawdz("START nie jest chipem — nie wpisuje go handlowiec w terenie",
            'data-typ="START"' not in html5)
    sprawdz("przedszkolny typ cyklu nie jest osobnym chipem",
            'data-typ="CYKLICZNE-PRZEDSZKOLE"' not in html5)

    geo = KL.get("/api/formularz/geografia").get_json()
    sprawdz("geografia oddaje osie: powiat, potem miejscowość",
            geo["ok"] and [o["poziom"] for o in geo["osie"]] == ["powiat", "miejscowosc"],
            str([o["poziom"] for o in geo.get("osie", [])]))
    # Druga oś zawęża się pierwszą — pod powiatem ma być kilka miejscowości,
    # nie cała lista województwa. To jest kaskada, o którą prosiła Kasia:
    # powiat będziński → Psary → szkoła.
    # Własny rekord, nie „SP 2" z F2 — testy auto-zwrotu czyszczą po drodze
    # `placowki`, więc opieranie się na cudzym rekordzie dawałoby wynik zależny
    # od kolejności bloków. Test, który zależy od kolejności, nie testuje.
    conn = db.get_conn()
    conn.execute("INSERT INTO placowki (nazwa, miejscowosc, powiat, zrodlo) "
                 "VALUES (?,?,?,?)", ("SP W PSARACH", "Psary", "będziński", "test"))
    # Lustro rejestru zna w tym powiecie także Czeladź, w której NIE MAMY
    # jeszcze ani jednej placówki — i to jest przypadek, o który tu chodzi.
    import rejestr_rspo
    rejestr_rspo.zaloz_tabele(conn)
    for rspo, nazwa, miejsc in ((8001, "SP W PSARACH", "Psary"),
                                (8002, "SP W CZELADZI", "Czeladź")):
        conn.execute("INSERT OR REPLACE INTO rspo_rejestr "
                     "(rspo, nazwa, typ, wojewodztwo, powiat, gmina, miejscowosc) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (rspo, nazwa, "Szkoła podstawowa", "ŚLĄSKIE", "będziński",
                      miejsc, miejsc))
    conn.commit()
    conn.close()
    sprawdz("bez powiatu lista miejscowości jest PUSTA, nie „wszystkie”",
            geo["osie"][1]["wartosci"] == [],
            str(geo["osie"][1]["wartosci"])[:60])

    zawezone = KL.get("/api/formularz/geografia?powiat=będziński").get_json()
    miejsc = zawezone["osie"][1]["wartosci"]
    sprawdz("miejscowości zawężone wybranym powiatem",
            "Psary" in miejsc and "Katowice" not in miejsc, str(miejsc))
    # Miejscowość z rejestru, w której NIE MAMY jeszcze placówki, musi być
    # do wyboru — bo to właśnie tam handlowiec zakłada nową.
    sprawdz("w formularzu są też miejscowości bez naszych placówek",
            "Czeladź" in miejsc, str(miejsc))
    conn = db.get_conn()
    sprawdz("...ale filtr na listach ich nie proponuje (pusta tabela)",
            "Czeladź" not in geografia.miasta(conn, "będziński"),
            str(geografia.miasta(conn, "będziński")))
    conn.close()

    # Placówka BEZ leada — powstaje przy dokładaniu bazy z rejestru RSPO.
    # Stary `/api/placowki` robi JOIN z `leady` i takiej nie pokazuje wcale.
    conn = db.get_conn()
    p_bez = conn.execute("INSERT INTO placowki (nazwa, miejscowosc, typ, zrodlo)"
                         " VALUES (?,?,?,?)",
                         ("PRZEDSZKOLE 99", "01. Orzesze", "02. Przedszkole miejskie (PM)",
                          "rspo")).lastrowid
    conn.commit()
    conn.close()
    lista = KL.get("/api/formularz/placowki?miejscowosc=01.%20Orzesze").get_json()
    sprawdz("placówka bez leada JEST na liście v5",
            any(p["placowka_id"] == p_bez for p in lista["pozycje"]))
    stara = KL.get("/api/placowki?miejscowosc=01.%20Orzesze").get_json()
    sprawdz("stary endpoint jej nie pokazuje — dlatego v5 ma własny",
            not any(p["placowka_id"] == p_bez for p in stara["pozycje"]))
    tylko_p = KL.get("/api/formularz/placowki?miejscowosc=01.%20Orzesze"
                     "&rodzaj=przedszkola").get_json()
    sprawdz("filtr rodzaju zawęża listę",
            all(p["typ"].startswith(("02.", "03.")) for p in tylko_p["pozycje"])
            and len(tylko_p["pozycje"]) >= 1)

    # ...i musi dać się na niej ZAPISAĆ, nie tylko ją zobaczyć. Do 24.08 v5
    # wysyłał w tym miejscu blok `placowka` z nazwą przepisaną z rekordu,
    # w przekonaniu, że serwer rozpozna placówkę po nazwie. Nie rozpoznawał —
    # wstawiał drugi wiersz. Dubel z tego samego rekordu, czyli dokładnie to,
    # o czym Kasia pisała, że robią ludzie, tyle że robiony przez aplikację.
    conn = db.get_conn()
    ile_przed = conn.execute("SELECT COUNT(*) c FROM placowki").fetchone()["c"]
    conn.close()
    kod, j = post("/api/formularz", {"handlowiec": H, "placowka_id": p_bez,
                                     "kontakt": {"telefon": "600700800"}})
    conn = db.get_conn()
    ile_po = conn.execute("SELECT COUNT(*) c FROM placowki").fetchone()["c"]
    leady_p = conn.execute("SELECT COUNT(*) c FROM leady WHERE placowka_id=?",
                           (p_bez,)).fetchone()["c"]
    tel = conn.execute("SELECT telefon FROM placowki WHERE id=?", (p_bez,)).fetchone()["telefon"]
    conn.close()
    sprawdz("zapis na placówce bez leada przechodzi", kod == 200, str(j)[:100])
    sprawdz("NIE powstał drugi wiersz placówki", ile_po == ile_przed,
            "%d → %d" % (ile_przed, ile_po))
    sprawdz("powstał dokładnie jeden lead do tego rekordu", leady_p == 1, "jest %d" % leady_p)
    sprawdz("kontakt wylądował przy istniejącej placówce", tel == "600700800", str(tel))

    # Drugie wejście na tę samą placówkę ma trafić w ZAŁOŻONY lead, nie zrobić
    # kolejnego — inaczej dubel wróciłby piętro niżej, w tabeli leadów.
    kod, _ = post("/api/formularz", {"handlowiec": H, "placowka_id": p_bez,
                                     "kontakt": {"telefon": "600700801"}})
    conn = db.get_conn()
    leady_p2 = conn.execute("SELECT COUNT(*) c FROM leady WHERE placowka_id=?",
                            (p_bez,)).fetchone()["c"]
    conn.close()
    sprawdz("drugi zapis nie mnoży leadów", kod == 200 and leady_p2 == 1,
            "jest %d" % leady_p2)

    kod, j = post("/api/formularz", {"handlowiec": H, "placowka_id": 999999})
    sprawdz("nieistniejąca placówka odrzucona", kod == 404, "kod %s" % kod)

    # KONTAKT NALEŻY DO PLACÓWKI — zgłoszenie wróciło trzeci raz.
    #
    # Kasia (o wariantach 2–4): „wprowadziłam dane typu osoba do kontaktu,
    # a potem zmieniłam szkołę, to osoba się nie zmieniła". Paweł dwa razy
    # 24.08 o v5, drugi raz słowami „dalej źle wpisuje dane, gdy wybiorę
    # z listy szkołę, i potem chcę inną wybrać".
    #
    # Pierwsza poprawka v5 chroniła to, co wpisał człowiek (reguła P04), i przez
    # to przenosiła dyrektorkę jednego przedszkola do karty drugiego. Nie ma tu
    # czego chronić: sekcja kontaktu jest ZAKRYTA, dopóki nie wybrano placówki,
    # więc każda wartość w niej dotyczy POPRZEDNIEJ szkoły.
    js5 = open("static/formularz5.js", encoding="utf-8").read()
    cialo5 = js5[js5.index("function podstawKontakt("):
                 js5.index("root.addEventListener", js5.index("function podstawKontakt("))]
    sprawdz("v5: podstawienie kontaktu nie zależy już od zawartości pola",
            "if (!el.value" not in cialo5 and "kontaktAuto" not in js5)
    sprawdz("v5: pusta wartość ze szkoły CZYŚCI pole", "el.value = zrodla[id];" in cialo5)
    sprawdz("v5: mówi o podmianie zamiast robić ją po cichu",
            "Kontakt podmieniony" in cialo5)

    # KAŻDY rodzaj zajęć musi dać się przypisać PROWADZĄCEMU — bez tego wpis nie
    # ma jak trafić do grafiku trenera, czyli do jedynego miejsca, dla którego
    # kalendarz w ogóle istnieje.
    #
    # Zgłoszenie Pawła 24.08: „w formularzu nie ma wyboru prowadzącego". Sekcja
    # cykliczna rysowała sam harmonogram, więc `polaRodzaju()` dla cyklu — z
    # prowadzącym, godzinami, sprzętem i uwagami — było MARTWYM kodem, choć
    # wyglądało na kompletne. Pilnujemy więc nie tekstu, tylko struktury:
    # ma być JEDNA ścieżka rysująca pola rodzaju, wspólna dla obu gałęzi.
    sprawdz("v5: pola rodzaju rysuje jedna funkcja dla obu gałęzi",
            js5.count("function polaHtml(") == 1
            and js5.count("polaRodzaju(typ).map(") == 1)
    sprawdz("v5: sekcja cykliczna dokłada wspólne pola do harmonogramu",
            "sekcjaCyklu(typ) + polaHtml(typ)" in js5)
    sprawdz("v5: prowadzący jest w definicji każdego rodzaju",
            js5.count("POLE_TRENER") == 4)          # 1 definicja + 3 rodzaje

    # --- panel dostępności prowadzących: v5 dostaje to samo co v3 ------------
    #
    # Zgłoszenie Pawła 24.08: „brakuje w v5 dostępności prowadzącego jak w v3".
    # Sam select niesie pełny słownik 40 trenerów, więc bez panelu „niedostępny"
    # przechodzi bez słowa aż do ekranu sukcesu.
    #
    # Jedyna różnica wobec v3 wynika z kaskady: v3 umawia JEDNO spotkanie, więc
    # ma jeden panel na ekran; v5 umawia kilka rzeczy naraz, każdą z własną datą
    # i osobą, więc panel siedzi PRZY SEKCJI. Jeden wspólny pokazywałby
    # dostępność na termin, którego akurat nie wypełniasz — czyli kłamałby.
    sprawdz("v5 wczytuje ten sam arkusz panelu co v3, bez kopii stylu",
            "formularz3.css" in html5)
    sprawdz("v5: panel dostępności doklejany do KAŻDEJ sekcji",
            "sekcjaDostepnosci(typ)" in js5)
    sprawdz("v5: panele rozróżniane typem zajęć, nie jednym id",
            'data-dost="' in js5 and 'data-status="' in js5 and 'data-dzien="' in js5)
    sprawdz("v5: kandydat trafia do sekcji, z której go kliknięto",
            "el.dataset.dla" in js5 and 'data-dla="' in js5)
    sprawdz("v5: zmiana daty albo godzin przelicza dostępność",
            '["data", "godz_od", "godz_do"].indexOf(el.dataset.pole)' in js5)
    # `rysujSekcje()` przerysowuje wszystkie sekcje przy każdym kliknięciu chipa.
    # Bez bufora każde takie przerysowanie wysyłałoby żądanie na sekcję — w
    # terenie, po LTE.
    sprawdz("v5: odpowiedź buforowana kluczem termin+miasto",
            "function kluczDostepnosci(" in js5 and "buf.klucz === klucz" in js5)
    # Cykl trwa miesiącami, a API odpowiada o JEDEN dzień. Panel ma to mówić,
    # zamiast pozwolić handlowcowi uznać, że sprawdziliśmy całą serię.
    sprawdz("v5: przy cyklu panel mówi, że sprawdza PIERWSZE zajęcia",
            "dalszych tygodni nie sprawdzamy" in js5)
    # Bez godziny startu serwer nie liczy kolizji (`przydzial._zakres_spotkania`),
    # więc ranking udawałby pełną wiedzę.
    sprawdz("v5: bez godziny startu panel ostrzega, że nie liczy kolizji",
            "żeby sprawdzić kolizje" in js5)

    # --- zapis listą `zajecia`: kilka rodzajów jednym żądaniem ---------------
    l_v5 = dodaj_lead(db.get_conn(), "SP V5", "08. Katowice", handlowiec=H)
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_v5,
        "zajecia": [
            {"typ": "DT", "data": dni(7), "godz_od": "09:00", "ilosc_klas": 3},
            {"typ": "FESTYN", "data": dni(20), "grupa": "cała szkoła"},
            {"typ": "CYKLICZNE", "cykl_dzien": "wtorek", "co_ile_tygodni": 1},
        ],
    })
    sprawdz("trzy rodzaje zajęć w jednym żądaniu", kod == 200 and len(j["eventy"]) == 3,
            str(j)[:120])
    conn = db.get_conn()
    typy = [r["typ"] for r in conn.execute(
        "SELECT typ FROM eventy WHERE lead_id=? ORDER BY typ", (l_v5,))]
    conn.close()
    sprawdz("każdy z osobnym typem", typy == ["CYKLICZNE", "DT", "FESTYN"], str(typy))

    # PROWADZĄCY PRZY CYKLU: do wpisania, ale NIEOBOWIĄZKOWY (decyzja Pawła,
    # 24.08). Zgodne z zasadą projektu — ostrzegamy, nie blokujemy: w terenie
    # cykl umawia się często zanim wiadomo, kto go poprowadzi, a odmowa zapisu
    # znaczy notatkę na kartce. Wpis bez prowadzącego ma w kalendarzu własny,
    # bursztynowy wiersz „— bez prowadzącego —" (S17), więc nie ginie.
    conn = db.get_conn()
    cykl_bez = conn.execute("SELECT trener FROM eventy WHERE lead_id=? AND typ='CYKLICZNE'",
                            (l_v5,)).fetchone()["trener"]
    conn.close()
    sprawdz("cykl zapisuje się BEZ prowadzącego", not cykl_bez, "jest %r" % cykl_bez)

    l_cyk = dodaj_lead(db.get_conn(), "SP CYKL Z TRENEREM", "08. Katowice", handlowiec=H)
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_cyk,
        "zajecia": [{"typ": "CYKLICZNE", "cykl_dzien": "środa", "godz_od": "14:00",
                     "trener": T, "sprzet": sprzet[0], "grupa": "kl. 3a"}],
    })
    conn = db.get_conn()
    ev_c = dict(conn.execute("SELECT * FROM eventy WHERE lead_id=?", (l_cyk,)).fetchone())
    conn.close()
    sprawdz("...a wpisany prowadzący przy cyklu naprawdę zapada w bazę",
            kod == 200 and ev_c["trener"] == T, str(ev_c.get("trener")))
    sprawdz("razem z godziną, sprzętem i grupą — reszta pól cyklu też działa",
            ev_c["godz_od"] == "14:00" and ev_c["sprzet"] == sprzet[0]
            and ev_c["grupa"] == "kl. 3a",
            "%s %s %s" % (ev_c["godz_od"], ev_c["sprzet"], ev_c["grupa"]))

    # Wpis, którego kalendarz nie pokazuje, jest gorszy niż odmowa (10.08).
    import calendar_view as _cv5
    conn = db.get_conn()
    widoczne = [e["typ"] for e in _cv5.events_for_month(conn, dni(7)[:7])
                if e["lead_id"] == l_v5]
    conn.close()
    sprawdz("zapisane rodzaje są widoczne w kalendarzu", "DT" in widoczne,
            str(widoczne))

    # Status „03. DT umówione" ma stawiać WYŁĄCZNIE DT. Gdyby festyn albo VR
    # go stawiały, raport „ile DT" kłamałby w jedyną stronę, która boli.
    l_fest = dodaj_lead(db.get_conn(), "SP FESTYN", "08. Katowice", handlowiec=H,
                        status="01. Próba kontaktu (Brak konkretów)")
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_fest,
        "zajecia": [{"typ": "FESTYN", "data": dni(9)}],
    })
    conn = db.get_conn()
    st = conn.execute("SELECT status_realizacji FROM leady WHERE id=?",
                      (l_fest,)).fetchone()["status_realizacji"]
    conn.close()
    sprawdz("sam festyn NIE ustawia „DT umówione”",
            kod == 200 and not st.startswith("03."), st)

    # Rodzaj spoza słownika TEGO profilu — twarda blokada w obie strony.
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_v5,
        "zajecia": [{"typ": "PIKNIK-WYMYSLONY", "data": dni(3)}],
    })
    sprawdz("rodzaj spoza słownika odrzucony", kod == 400 and "Nieznany rodzaj" in j["error"],
            str(j)[:80])

    # Zajęcie bez daty pomijamy zamiast tworzyć wpis-widmo (niewidoczny
    # w kalendarzu, a wyglądający na zrobiony).
    conn = db.get_conn()
    przed = conn.execute("SELECT COUNT(*) c FROM eventy WHERE lead_id=?",
                         (l_fest,)).fetchone()["c"]
    conn.close()
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_fest,
        "zajecia": [{"typ": "VR", "godz_od": "10:00"}],
    })
    conn = db.get_conn()
    po = conn.execute("SELECT COUNT(*) c FROM eventy WHERE lead_id=?",
                      (l_fest,)).fetchone()["c"]
    conn.close()
    sprawdz("zajęcie bez daty nie tworzy wpisu-widma", kod == 200 and po == przed,
            "%d → %d" % (przed, po))

    # --- ZAPORA: stare warianty mają tego nie zauważyć ----------------------
    # Cztery warianty istnieją po to, żeby klient porównywał UKŁAD. Gdyby v5
    # zmienił kontrakt API, porównanie przestałoby cokolwiek znaczyć.
    l_stary = dodaj_lead(db.get_conn(), "SP STARE API", "08. Katowice", handlowiec=H)
    kod, j = post("/api/formularz", {
        "handlowiec": H, "lead_id": l_stary,
        "dt": {"data": dni(5), "godz_od": "08:00", "ilosc_klas": 2, "ilosc_dzieci": 40},
        "cykl": {"typ": "CYKLICZNE", "cykl_dzien": "środa", "co_ile_tygodni": 1},
    })
    conn = db.get_conn()
    stare_typy = [r["typ"] for r in conn.execute(
        "SELECT typ FROM eventy WHERE lead_id=? ORDER BY typ", (l_stary,))]
    st_stary = conn.execute("SELECT status_realizacji FROM leady WHERE id=?",
                            (l_stary,)).fetchone()["status_realizacji"]
    conn.close()
    sprawdz("payload sprzed v5 przechodzi bez zmian",
            kod == 200 and stare_typy == ["CYKLICZNE", "DT"]
            and st_stary == "03. DT umówione", str(stare_typy))
    for w in ("formularz", "formularz2", "formularz3", "formularz4"):
        kod_js = open("static/%s.js" % w, encoding="utf-8").read()
        sprawdz("%s nie wysyła listy zajęć — kontrakt bez zmian" % w,
                "zajecia" not in kod_js)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
