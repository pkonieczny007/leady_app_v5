# -*- coding: utf-8 -*-
"""
Scenariusze akceptacyjne — przejście przez to, o co klient poprosił, przez API aplikacji.

Uruchomienie:  python test_scenariusze.py
Test działa na WŁASNEJ, tymczasowej bazie (nie rusza `data/leady_v3.db`).

Każdy scenariusz jest nazwany językiem klienta, a nie technicznym, żeby dało się
je przeklikać razem z nim i zapytać „czy o to chodziło?".
"""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

# konsola Windows domyślnie cp1250 — bez tego polskie znaki wysypują wydruk
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# własna baza na czas testu — zanim zaimportujemy moduły aplikacji
TMP = tempfile.mkdtemp(prefix="leady_v3_test_")
os.environ["DATA_DIR"] = TMP

import app as A                      # noqa: E402
import calendar_view as cv           # noqa: E402
import db                            # noqa: E402
import repo                          # noqa: E402
from seed import bootstrap           # noqa: E402

KL = A.app.test_client()
WYNIKI = []


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    znak = "OK  " if warunek else "BLAD"
    print("  [%s] %s%s" % (znak, nazwa, (" — " + opis) if opis else ""))
    return bool(warunek)


def patch_lead(lead_id, field, value):
    r = KL.patch("/api/lead/%d" % lead_id,
                 data=json.dumps({"field": field, "value": value}),
                 content_type="application/json")
    return r.status_code, r.get_json()


def post(url, payload):
    r = KL.post(url, data=json.dumps(payload), content_type="application/json")
    return r.status_code, r.get_json()


def leady(**filtry):
    conn = db.get_conn()
    f = repo.pusty_filtr()
    f.update(filtry)
    rows = repo.filtruj_leady(conn, f)
    conn.close()
    return rows


def nowa_szkola(nazwa, miasto="08. Katowice", typ="01. Szkoła podstawowa"):
    kod, dane = post("/api/lead", {"nazwa": nazwa, "miejscowosc": miasto, "typ": typ})
    assert kod == 200 and dane.get("ok"), (kod, dane)
    return dane["id"]


# =====================================================================

def main():
    print("Baza testowa:", TMP)
    bootstrap()

    print("\nS0 — start: pusta baza, gotowe słowniki")
    conn = db.get_conn()
    sprawdz("słownik handlowców niepusty", len(db.slownik_values(conn, "handlowiec")) >= 5)
    sprawdz("słownik trenerów niepusty", len(db.slownik_values(conn, "trener")) >= 30)
    m0 = repo.metryki(conn)
    conn.close()
    sprawdz("zero leadów na starcie", m0["leady"] == 0)

    # -----------------------------------------------------------------
    print("\nS1 — Koordynator przypisuje szkołę handlowcowi i daje termin")
    lead_id = nowa_szkola("SP 11 Będzin", miasto="15. Będzin")
    sprawdz("szkoła jest na liście do rozdania",
            any(r["id"] == lead_id for r in leady(zakres="nieprzydzielone")))
    kod, _ = post("/api/przypisz", {"ids": [lead_id], "handlowiec": "04. Chytry",
                                    "deadline": "2026-09-30"})
    sprawdz("przypisanie się udało", kod == 200)
    sprawdz("zniknęła z listy do rozdania",
            not any(r["id"] == lead_id for r in leady(zakres="nieprzydzielone")),
            "to filtr, nie usunięcie wiersza")
    u_chytrego = leady(handlowiec="04. Chytry")
    sprawdz("jest u Chytrego", any(r["id"] == lead_id for r in u_chytrego))
    sprawdz("ma wpisany termin ostateczny",
            u_chytrego[0]["deadline"] == "2026-09-30")

    # -----------------------------------------------------------------
    print("\nS2 — Handlowiec umawia DT: trafia do Zbiorczego i do kalendarza")
    kod, dane = post("/api/event", {
        "lead_id": lead_id, "typ": "DT", "data": "2026-09-16",
        "godz_od": "08:00", "godz_do": "09:35", "trener": "01. Małolepsza",
        "ilosc_klas": 10, "ilosc_dzieci": 186, "numer_sali": "12"})
    sprawdz("DT dodane", kod == 200 and dane.get("ok"))
    sprawdz("brak ostrzeżenia o kolizji przy pierwszym DT", dane.get("kolizja") is None)
    row = [r for r in leady() if r["id"] == lead_id][0]
    sprawdz("status sam przeszedł na „DT umówione”",
            row["status_realizacji"] == "03. DT umówione", row["status_realizacji"])
    sprawdz("jest w Zbiorczym (widok „umówione”)",
            any(r["id"] == lead_id for r in leady(zakres="umowione")))
    conn = db.get_conn()
    mx = cv.build_matrix(conn, "2026-09")
    conn.close()
    komorki = [c for t in mx["tygodnie"] for w in t["wiersze"]
               if w["trener"] == "01. Małolepsza" for c in w["cells"] if c]
    sprawdz("widać wpis w kalendarzu wrześniowym", len(komorki) == 1)

    # -----------------------------------------------------------------
    print("\nS3 — DWA DT jednego trenera w jednym dniu (ZGLOSZONY BUG)")
    lead2 = nowa_szkola("SP 8 Będzin", miasto="15. Będzin")
    post("/api/przypisz", {"ids": [lead2], "handlowiec": "02. Olszewska",
                           "deadline": "2026-09-30"})
    kod, dane2 = post("/api/event", {
        "lead_id": lead2, "typ": "DT", "data": "2026-09-16",
        "godz_od": "11:00", "godz_do": "12:30", "trener": "01. Małolepsza"})
    sprawdz("drugie DT tego samego dnia przyjęte", kod == 200 and dane2.get("ok"),
            "zapisu NIE blokujemy")
    sprawdz("brak ostrzeżenia — godziny się nie nakładają", dane2.get("kolizja") is None)
    conn = db.get_conn()
    mx = cv.build_matrix(conn, "2026-09")
    conn.close()
    komorka = None
    for t in mx["tygodnie"]:
        for w in t["wiersze"]:
            if w["trener"] != "01. Małolepsza":
                continue
            for i, c in enumerate(w["cells"]):
                if t["dni"][i]["iso"] == "2026-09-16":
                    komorka = c
    sprawdz("W JEDNEJ KOMÓRCE KALENDARZA SĄ DWA WPISY",
            komorka is not None and len(komorka) == 2,
            "w arkuszu XLOOKUP pokazywał tylko pierwszy")
    if komorka:
        godziny = sorted(e["godz_od"] for e in komorka)
        sprawdz("oba wpisy z właściwymi godzinami", godziny == ["08:00", "11:00"],
                " / ".join(godziny))

    # -----------------------------------------------------------------
    print("\nS4 — Trzecie DT NAKŁADA się godzinami: ostrzeżenie, ale zapis przechodzi")
    lead3 = nowa_szkola("SP 20 Sosnowiec", miasto="13. Sosnowiec")
    post("/api/przypisz", {"ids": [lead3], "handlowiec": "04. Chytry",
                           "deadline": "2026-09-15"})
    kod, dane3 = post("/api/event", {
        "lead_id": lead3, "typ": "DT", "data": "2026-09-16",
        "godz_od": "09:00", "godz_do": "10:00", "trener": "01. Małolepsza"})
    sprawdz("zapis przeszedł", kod == 200 and dane3.get("ok"))
    sprawdz("aplikacja OSTRZEGŁA o nakładaniu", bool(dane3.get("kolizja")),
            dane3.get("kolizja") or "")
    conn = db.get_conn()
    kol = cv.lista_kolizji(conn, "2026-09")
    conn.close()
    sprawdz("kolizja widoczna na pulpicie", len(kol) == 2,
            "dwa nakładające się wpisy: 08:00–09:35 i 09:00–10:00")

    # -----------------------------------------------------------------
    print("\nS5 — Przesunięcie terminu: poprawiam w jednym miejscu")
    conn = db.get_conn()
    ev = conn.execute("SELECT id FROM eventy WHERE lead_id=? AND typ='DT'",
                      (lead_id,)).fetchone()["id"]
    conn.close()
    r = KL.patch("/api/event/%d" % ev,
                 data=json.dumps({"field": "data", "value": "2026-09-23"}),
                 content_type="application/json")
    sprawdz("data zmieniona", r.status_code == 200)
    conn = db.get_conn()
    mx = cv.build_matrix(conn, "2026-09")
    conn.close()
    znalezione = {}
    for t in mx["tygodnie"]:
        for w in t["wiersze"]:
            if w["trener"] != "01. Małolepsza":
                continue
            for i, c in enumerate(w["cells"]):
                if c:
                    znalezione[t["dni"][i]["iso"]] = len(c)
    sprawdz("wpis przeskoczył na 23.09", znalezione.get("2026-09-23") == 1, str(znalezione))
    sprawdz("pod 16.09 zostały dwa", znalezione.get("2026-09-16") == 2)
    sprawdz("kolizja zniknęła sama", len(cv.lista_kolizji(db.get_conn(), "2026-09")) == 0)

    # -----------------------------------------------------------------
    print("\nS6 — Nowy miesiąc tworzy się sam (bez konfigurowania zakładki)")
    conn = db.get_conn()
    przed = cv.available_months(conn)
    conn.close()
    sprawdz("listopada jeszcze nie ma", "2026-11" not in przed, str(przed))
    post("/api/event", {"lead_id": lead3, "typ": "DT", "data": "2026-11-03",
                        "godz_od": "08:00", "godz_do": "09:35",
                        "trener": "04. Zemela"})
    conn = db.get_conn()
    po = cv.available_months(conn)
    mx11 = cv.build_matrix(conn, "2026-11")
    conn.close()
    sprawdz("listopad pojawił się sam", "2026-11" in po)
    sprawdz("i ma w sobie wpis", mx11["n_events"] == 1)

    # -----------------------------------------------------------------
    print("\nS7 — Odebranie leada: wraca do puli, nic nie ginie")
    kod, _ = post("/api/odbierz", {"ids": [lead3]})
    sprawdz("odebranie się udało", kod == 200)
    niew = leady(zakres="niewykorzystane")
    sprawdz("lead jest w „Niewykorzystane rekordy”",
            any(r["id"] == lead3 for r in niew))
    row3 = [r for r in leady() if r["id"] == lead3][0]
    sprawdz("nie ma już handlowca", not row3["handlowiec"])
    sprawdz("dane placówki nietknięte", row3["placowka"] == "SP 20 Sosnowiec")
    kod, _ = post("/api/przypisz", {"ids": [lead3], "handlowiec": "02. Olszewska",
                                    "deadline": "2026-10-15"})
    row3 = [r for r in leady() if r["id"] == lead3][0]
    sprawdz("przydzielony innemu handlowcowi", row3["handlowiec"] == "02. Olszewska")
    sprawdz("wypadł z puli zwrotnej",
            not any(r["id"] == lead3 for r in leady(zakres="niewykorzystane")))

    # -----------------------------------------------------------------
    print("\nS8 — Lista rozwijana wymuszona: koniec z „02. Olaszewska”")
    kod, dane = patch_lead(lead_id, "handlowiec", "02. Olaszewska")
    sprawdz("literówka ODRZUCONA", kod == 400 and not dane.get("ok"),
            dane.get("error", ""))
    kod, _ = patch_lead(lead_id, "handlowiec", "02. Olszewska")
    sprawdz("poprawna wartość przyjęta", kod == 200)
    kod, dane = patch_lead(lead_id, "status_realizacji", "cokolwiek")
    sprawdz("status spoza listy odrzucony", kod == 400)

    # -----------------------------------------------------------------
    print("\nS9 — „Wybrane szkoły na tydzień do góry”")
    kod, dane = post("/api/pin", {"id": lead2, "pin": True})
    sprawdz("przypięcie zapisane", kod == 200 and dane.get("pin"))
    przypiete = leady(zakres="pin")
    sprawdz("jest na planie tygodnia", any(r["id"] == lead2 for r in przypiete))
    wszystkie = leady()
    sprawdz("przypięty jest NA GÓRZE listy", wszystkie[0]["id"] == lead2,
            "sortowanie stawia przypięte pierwsze")
    r = KL.get("/tydzien")
    sprawdz("ekran „Tydzień” się otwiera", r.status_code == 200)

    # -----------------------------------------------------------------
    print("\nS10 — Zajęcia cykliczne: jedna reguła, wiele wystąpień")
    kod, dane = post("/api/event", {
        "lead_id": lead2, "typ": "CYKLICZNE", "data": "2026-10-05",
        "godz_od": "12:30", "godz_do": "13:30", "trener": "14. Swoboda",
        "cykl_dzien": "poniedziałek", "co_ile_tygodni": 1, "grupa": "1",
        "sprzet": "01. Sala komputerowa", "kod_tinkercad": "BMR DKP QHW"})
    sprawdz("cykl dodany jako JEDEN rekord", kod == 200 and dane.get("ok"))
    conn = db.get_conn()
    ile_rekordow = conn.execute("SELECT COUNT(*) c FROM eventy "
                                "WHERE typ='CYKLICZNE'").fetchone()["c"]
    ag = cv.build_agenda(conn, "2026-10", typy=["CYKLICZNE"])
    conn.close()
    sprawdz("w bazie jest 1 rekord", ile_rekordow == 1)
    sprawdz("a w październiku widać 4 wystąpienia", ag["n_events"] == 4,
            "%d wystąpień" % ag["n_events"])

    print("\nS11 — Zastępstwo na jednej dacie = wyjątek, nie kopiowanie tygodnia")
    conn = db.get_conn()
    eid = conn.execute("SELECT id FROM eventy WHERE typ='CYKLICZNE'").fetchone()["id"]
    conn.execute("INSERT INTO wyjatki_cyklu (event_id, data, zastepstwo, uwagi) "
                 "VALUES (?,?,?,?)", (eid, "2026-10-19", "09. Bochniarz", "zastępstwo"))
    conn.commit()
    ag = cv.build_agenda(conn, "2026-10", typy=["CYKLICZNE"])
    conn.close()
    dzien19 = [d for d in ag["dni"] if d["iso"] == "2026-10-19"]
    sprawdz("19.10 nadal ma zajęcia", bool(dzien19))
    if dzien19:
        e = dzien19[0]["eventy"][0]
        sprawdz("na tej dacie jest zastępstwo", e.get("zastepstwo") == "09. Bochniarz")
        sprawdz("prowadzący reguły bez zmian", e.get("trener") == "14. Swoboda")

    print("\nS12 — Odwołane zajęcia znikają tylko z tej jednej daty")
    conn = db.get_conn()
    conn.execute("INSERT INTO wyjatki_cyklu (event_id, data, odwolane, uwagi) "
                 "VALUES (?,?,1,?)", (eid, "2026-10-26", "odwołane"))
    conn.commit()
    ag = cv.build_agenda(conn, "2026-10", typy=["CYKLICZNE"])
    conn.close()
    sprawdz("zostały 3 wystąpienia z 4", ag["n_events"] == 3)
    sprawdz("26.10 nie ma zajęć",
            not any(d["iso"] == "2026-10-26" for d in ag["dni"]))

    # -----------------------------------------------------------------
    print("\nS13 — Eksport oddaje DOKŁADNIE to, co widać po filtrach")
    from exporter import build_workbook
    import openpyxl
    conn = db.get_conn()
    f = repo.pusty_filtr(); f["zakres"] = "umowione"
    rows_f = repo.filtruj_leady(conn, f)
    bio = build_workbook(conn, rows_f, f)
    conn.close()
    wb = openpyxl.load_workbook(bio)
    ws = wb["Leady"]
    sprawdz("arkusze zgodne z zapowiedzią",
            set(["Leady", "Spotkania", "Kolizje", "Filtr"]).issubset(set(wb.sheetnames)),
            ", ".join(wb.sheetnames))
    sprawdz("liczba wierszy = liczba wyfiltrowanych",
            ws.max_row - 1 == len(rows_f), "%d w pliku / %d na ekranie"
            % (ws.max_row - 1, len(rows_f)))
    sprawdz("nagłówki w języku klienta", ws.cell(1, 1).value == "Handlowiec")
    r = KL.get("/export.xlsx?zakres=umowione")
    sprawdz("pobranie przez przeglądarkę działa", r.status_code == 200)

    # -----------------------------------------------------------------
    print("\nS14 — Historia zmian przy leadzie (kontrola aktywności)")
    conn = db.get_conn()
    lead = repo.lead_szczegoly(conn, lead_id)
    conn.close()
    sprawdz("log zapisał zmiany", len(lead["log"]) >= 3, "%d wpisów" % len(lead["log"]))
    sprawdz("jest ślad przypisania",
            any(w["co"] == "przypisanie" for w in lead["log"]))
    sprawdz("zapisana ostatnia aktywność", bool(lead["ostatnia_aktywnosc"]))

    print("\nS15 — Wszystkie ekrany otwierają się na tych danych")
    for s in ["/pulpit", "/baza", "/leady", "/zbiorczy", "/niewykorzystane",
              "/tydzien", "/slowniki", "/import", "/kalendarz",
              "/kalendarz?widok=agenda", "/kalendarz?widok=starty",
              "/lead/%d" % lead_id]:
        sprawdz("otwiera się %s" % s, KL.get(s).status_code == 200)

    # -----------------------------------------------------------------
    ok = sum(1 for _, w, _ in WYNIKI if w)
    zle = [n for n, w, _ in WYNIKI if not w]
    print("\n" + "=" * 62)
    print("WYNIK: %d/%d sprawdzeń OK" % (ok, len(WYNIKI)))
    if zle:
        print("NIEUDANE:")
        for n in zle:
            print("  -", n)
    print("=" * 62)
    return 0 if not zle else 1


if __name__ == "__main__":
    try:
        kod = main()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(kod)
