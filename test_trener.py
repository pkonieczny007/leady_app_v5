# -*- coding: utf-8 -*-
"""
Testy roli TRENER i zawężenia uprawnień handlowca do dostępności.

Ustalenia z 07.08:
  trener      — sprawdza i EDYTUJE swoją dostępność, widzi kalendarz
  handlowiec  — dostępność trenerów tylko PODGLĄDA, nie zmienia
  koordynator — pełny dostęp

Uruchomienie:  python test_trener.py
"""
import datetime as dt
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

TMP = tempfile.mkdtemp(prefix="leady_v5_trener_test_")
os.environ["DATA_DIR"] = TMP
os.environ["PIN_KOORDYNATORA"] = "5150"
os.environ.pop("PIN_SERWISOWY", None)

import app as A                      # noqa: E402
import db                            # noqa: E402
import uzytkownicy as uz             # noqa: E402
from seed import bootstrap           # noqa: E402

WYNIKI = []
DZIS = dt.date.today()


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


def zaloguj(osoba, pin):
    kl = A.app.test_client()
    r = kl.post("/api/logowanie", json={"osoba": osoba, "pin": pin})
    if r.status_code == 200:
        with kl.session_transaction() as s:
            s["csrf"] = "t"
        kl.environ_base["HTTP_X_CSRF"] = "t"
    return kl, r.status_code, r.get_json()


def dni(n):
    return (DZIS + dt.timedelta(days=n)).isoformat()


def main():
    print("Baza testowa:", TMP)
    bootstrap()
    conn = db.get_conn()
    handlowcy = db.slownik_values(conn, "handlowiec")
    trenerzy = db.slownik_values(conn, "trener")
    uz.bootstrap_konta(conn, handlowcy, trenerzy)
    H = handlowcy[0]
    T1, T2 = trenerzy[0], trenerzy[1]
    uz.ustaw_pin(conn, H, "1111")
    uz.ustaw_pin(conn, T1, "2222")
    uz.ustaw_pin(conn, T2, "3333")
    conn.close()

    # ==================================================== T1 — konta trenerów
    print("\nT1 — konta trenerów zakładają się ze słownika")
    conn = db.get_conn()
    konta = {k["osoba"]: k for k in uz.lista(conn)}
    conn.close()
    sprawdz("każdy trener ze słownika ma konto",
            all(t in konta for t in trenerzy),
            "%d/%d" % (sum(1 for t in trenerzy if t in konta), len(trenerzy)))
    sprawdz("dostają rolę 'trener'", konta[T1]["rola"] == "trener")
    sprawdz("'trener' jest znaną rolą", "trener" in uz.ROLE)

    # Osoby figurujące i jako handlowiec, i jako trener mają JEDNO konto —
    # nie nadpisujemy im szerszej roli tą węższą.
    wspolni = set(handlowcy) & set(trenerzy)
    if wspolni:
        w = sorted(wspolni)[0]
        sprawdz("osoba w obu słownikach zachowuje rolę handlowca",
                konta[w]["rola"] == "handlowiec", "%s -> %s" % (w, konta[w]["rola"]))
    else:
        sprawdz("brak osób w obu słownikach — nic do rozstrzygania", True)

    kl_t, kod, j = zaloguj(T1, "2222")
    sprawdz("trener się loguje", kod == 200)
    sprawdz("ląduje na swojej dostępności", (j or {}).get("dalej") == "/dostepnosc")

    # ============================================ T2 — co trener widzi
    print("\nT2 — trener: dostępność i kalendarz, nic więcej")
    sprawdz("wchodzi na /dostepnosc", kl_t.get("/dostepnosc").status_code == 200)
    sprawdz("wchodzi na /kalendarz", kl_t.get("/kalendarz").status_code == 200)

    for sciezka in ("/leady", "/formularz", "/formularz/kroki", "/tydzien",
                    "/baza", "/zbiorczy", "/pulpit", "/slowniki", "/rejony",
                    "/uzytkownicy", "/niewykorzystane"):
        r = kl_t.get(sciezka)
        sprawdz("trener NIE wchodzi na %s" % sciezka, r.status_code == 302,
                "status %d" % r.status_code)

    r = kl_t.post("/api/formularz", json={"placowka": {"nazwa": "X"}})
    sprawdz("trener nie zapisze formularza", r.status_code == 403)
    r = kl_t.post("/api/przypisz", json={"ids": [1]})
    sprawdz("trener nie przypisze szkoły", r.status_code == 403)

    html = kl_t.get("/dostepnosc").get_data(as_text=True)
    sprawdz("nawigacja trenera ma 'Moja dostępność'", "Moja dostępność" in html)
    sprawdz("nawigacja trenera nie ma formularza", "Formularz</a>" not in html)
    sprawdz("nawigacja trenera nie ma leadów", "Moje szkoły</a>" not in html)

    # ==================================== T3 — trener edytuje TYLKO swój wiersz
    print("\nT3 — trener edytuje wyłącznie swój wiersz")
    r = kl_t.post("/api/dostepnosc", json={"trener": T1, "data": dni(3),
                                           "godz_od": "08:00", "godz_do": "14:00"})
    sprawdz("swoją dostępność zapisuje", r.status_code == 200, str(r.get_json())[:80])
    conn = db.get_conn()
    w = conn.execute("SELECT * FROM dostepnosc WHERE trener=? AND data=?",
                     (T1, dni(3))).fetchone()
    conn.close()
    sprawdz("wpis wylądował w bazie", w is not None and w["godz_od"] == "08:00")

    r = kl_t.post("/api/dostepnosc", json={"trener": T2, "data": dni(3),
                                           "godz_od": "08:00"})
    sprawdz("CUDZEJ dostępności nie zapisze", r.status_code == 403,
            "status %d" % r.status_code)
    sprawdz("komunikat mówi wprost dlaczego",
            "swoją" in (r.get_json() or {}).get("error", ""),
            (r.get_json() or {}).get("error", "")[:60])

    conn = db.get_conn()
    cudzy = conn.execute("SELECT COUNT(*) c FROM dostepnosc WHERE trener=?",
                         (T2,)).fetchone()["c"]
    conn.close()
    sprawdz("cudzy wiersz nietknięty", cudzy == 0)

    r = kl_t.delete("/api/dostepnosc", json={"trener": T2, "data": dni(3)})
    sprawdz("cudzego wpisu nie skasuje", r.status_code == 403)
    r = kl_t.post("/api/dostepnosc/zakres", json={"trener": T2, "od": dni(1),
                                                   "do": dni(5), "godz_od": "08:00"})
    sprawdz("cudzego zakresu nie wypełni", r.status_code == 403)

    r = kl_t.delete("/api/dostepnosc", json={"trener": T1, "data": dni(3)})
    sprawdz("swój wpis kasuje bez przeszkód", r.status_code == 200)

    # ================================= T4 — handlowiec tylko podgląda
    print("\nT4 — handlowiec widzi grafik, ale go nie zmienia")
    kl_h, kod, _ = zaloguj(H, "1111")
    sprawdz("handlowiec się loguje", kod == 200)
    sprawdz("wchodzi na /dostepnosc (bez tego nie umówi DT)",
            kl_h.get("/dostepnosc").status_code == 200)

    r = kl_h.post("/api/dostepnosc", json={"trener": T1, "data": dni(4),
                                            "godz_od": "09:00"})
    sprawdz("ale NIE zapisze dostępności trenera", r.status_code == 403,
            "status %d" % r.status_code)
    sprawdz("komunikat wskazuje koordynatora",
            "koordynator" in (r.get_json() or {}).get("error", "").lower(),
            (r.get_json() or {}).get("error", "")[:60])
    r = kl_h.delete("/api/dostepnosc", json={"trener": T1, "data": dni(4)})
    sprawdz("nie skasuje cudzego wpisu", r.status_code == 403)
    r = kl_h.post("/api/dostepnosc/zakres", json={"trener": T1, "od": dni(1),
                                                   "do": dni(5), "godz_od": "08:00"})
    sprawdz("nie wypełni zakresu", r.status_code == 403)

    html = kl_h.get("/dostepnosc").get_data(as_text=True)
    sprawdz("wszystkie komórki oznaczone jako podgląd",
            "av-tylko-podglad" in html and "kliknij, żeby edytować" not in html)

    # ==================================== T5 — koordynator dalej może wszystko
    print("\nT5 — koordynator bez zmian")
    kl_k, kod, _ = zaloguj("Koordynator", "5150")
    sprawdz("koordynator się loguje", kod == 200)
    r = kl_k.post("/api/dostepnosc", json={"trener": T2, "data": dni(6),
                                            "godz_od": "10:00", "godz_do": "15:00"})
    sprawdz("zapisuje CUDZĄ dostępność", r.status_code == 200, str(r.get_json())[:70])
    r = kl_k.post("/api/dostepnosc/zakres", json={"trener": T2, "od": dni(7),
                                                   "do": dni(9), "godz_od": "08:00"})
    sprawdz("wypełnia zakres dowolnemu trenerowi", r.status_code == 200)
    r = kl_k.delete("/api/dostepnosc", json={"trener": T2, "data": dni(6)})
    sprawdz("kasuje dowolny wpis", r.status_code == 200)

    html = kl_k.get("/dostepnosc").get_data(as_text=True)
    sprawdz("u koordynatora komórki są klikalne",
            "kliknij, żeby edytować" in html and "av-tylko-podglad" not in html)

    # ============================= T6 — widok trenera: własny wiersz wyróżniony
    print("\nT6 — trener widzi, który wiersz jest jego")
    html = kl_t.get("/dostepnosc").get_data(as_text=True)
    sprawdz("własny wiersz oznaczony", "av-moj-wiersz" in html)
    sprawdz("z plakietką 'to Ty'", "to Ty" in html)
    sprawdz("cudze komórki są tylko do podglądu", "av-tylko-podglad" in html)
    sprawdz("własne komórki pozostają klikalne", "kliknij, żeby edytować" in html)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
