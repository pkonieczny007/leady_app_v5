# -*- coding: utf-8 -*-
"""
Testy trybu serwisowego — jednego PIN-u wpuszczającego bez wyboru osoby.

To jest KLUCZ UNIWERSALNY, więc testy sprawdzają nie tyle „czy działa", ile
„czy nie da się go zostawić włączonego przez przypadek".

Uruchomienie:  python test_serwis.py
"""
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

TMP = tempfile.mkdtemp(prefix="leady_v5_serwis_test_")
os.environ["DATA_DIR"] = TMP
os.environ["PIN_KOORDYNATORA"] = "6134"
os.environ.pop("PIN_SERWISOWY", None)
os.environ.pop("PIN_SERWISOWY_PROD", None)

import app as A                      # noqa: E402
import db                            # noqa: E402
import uzytkownicy as uz             # noqa: E402
from seed import bootstrap           # noqa: E402

WYNIKI = []


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


def wejdz(pin, osoba=""):
    kl = A.app.test_client()
    r = kl.post("/api/logowanie", json={"osoba": osoba, "pin": pin})
    return kl, r.status_code, r.get_json()


def main():
    print("Baza testowa:", TMP)
    bootstrap()
    conn = db.get_conn()
    uz.bootstrap_konta(conn, db.slownik_values(conn, "handlowiec"))
    conn.close()

    # ============================ S1 — domyślnie wyłączony
    print("\nS1 — bez zmiennej środowiskowej trybu nie ma")
    sprawdz("tryb wyłączony, gdy PIN_SERWISOWY nie ustawiony",
            not uz.serwis_wlaczony())
    _, kod, j = wejdz("7777")
    sprawdz("logowanie samym PIN-em odrzucone", kod == 401)
    sprawdz("komunikat mówi wprost, że tryb wyłączony",
            "wyłączony" in (j or {}).get("error", ""), (j or {}).get("error"))
    sprawdz("ekran logowania nie wspomina o trybie",
            "serwisowy" not in A.app.test_client().get("/logowanie").get_data(as_text=True))

    # ============================ S2 — włączony zmienną
    print("\nS2 — włączony przez PIN_SERWISOWY")
    os.environ["PIN_SERWISOWY"] = "7777"
    sprawdz("tryb widoczny jako włączony", uz.serwis_wlaczony())

    kl, kod, j = wejdz("7777")
    sprawdz("wejście samym PIN-em działa", kod == 200, str(j)[:80])
    sprawdz("bez podawania osoby", (j or {}).get("serwis") is True)
    sprawdz("dostaje uprawnienia koordynatora", (j or {}).get("rola") == "koordynator")
    sprawdz("konto podpisane jako serwisowe",
            (j or {}).get("osoba") == uz.OSOBA_SERWISOWA)

    sprawdz("wchodzi na ekrany koordynatora", kl.get("/pulpit").status_code == 200)
    sprawdz("wchodzi na panel kont", kl.get("/uzytkownicy").status_code == 200)
    html = kl.get("/pulpit").get_data(as_text=True)
    sprawdz("na ekranie wisi ostrzegawczy pasek", "pasek-serwis" in html)
    sprawdz("ekran logowania podpowiada tryb",
            'data-serwis="1"' in A.app.test_client().get("/logowanie").get_data(as_text=True))

    _, kod, j = wejdz("1234")
    sprawdz("inny PIN nie wchodzi", kod == 401)

    conn = db.get_conn()
    wpis = conn.execute("SELECT * FROM log WHERE co='logowanie serwisowe' "
                        "ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    sprawdz("każde wejście zostawia ślad w historii", wpis is not None)
    sprawdz("ślad podpisany kontem serwisowym",
            wpis is not None and wpis["kto"] == uz.OSOBA_SERWISOWA)

    # ============================ S3 — nie da się zostawić na produkcji
    print("\nS3 — profil prod wymaga drugiego, jawnego potwierdzenia")
    os.environ["PROFIL"] = "prod"
    sprawdz("sam PIN na profilu prod NIE włącza trybu", not uz.serwis_wlaczony())
    _, kod, _ = wejdz("7777")
    sprawdz("i logowanie samym PIN-em nie przechodzi", kod == 401)

    os.environ["PIN_SERWISOWY_PROD"] = "tak"
    sprawdz("dopiero PIN_SERWISOWY_PROD=tak włącza go na produkcji",
            uz.serwis_wlaczony())
    os.environ.pop("PIN_SERWISOWY_PROD")
    os.environ["PROFIL"] = "test"

    # ============================ S4 — wyłączenie unieważnia sesje
    print("\nS4 — wyłączenie trybu wyrzuca zalogowanych")
    kl2, kod, _ = wejdz("7777")
    sprawdz("sesja serwisowa czynna", kl2.get("/pulpit").status_code == 200)
    os.environ.pop("PIN_SERWISOWY")
    sprawdz("po zdjęciu zmiennej stara sesja przestaje działać",
            kl2.get("/pulpit").status_code == 302,
            "inaczej ciastko żyłoby jeszcze 30 dni")
    sprawdz("tryb znów wyłączony", not uz.serwis_wlaczony())

    # ============================ S5 — zły format PIN-u
    print("\nS5 — PIN serwisowy musi mieć cztery cyfry")
    for zly in ("777", "77777", "abcd", "", "  "):
        os.environ["PIN_SERWISOWY"] = zly
        sprawdz("PIN %r nie włącza trybu" % zly, not uz.serwis_wlaczony())
    os.environ.pop("PIN_SERWISOWY")

    # ============================ S6 — zwykłe konta działają dalej
    print("\nS6 — tryb serwisowy niczego nie psuje w zwykłym logowaniu")
    _, kod, j = wejdz("6134", "Koordynator")
    sprawdz("koordynator loguje się normalnie", kod == 200)
    sprawdz("i nie jest oznaczony jako serwis", not (j or {}).get("serwis"))
    _, kod, _ = wejdz("0000", "Koordynator")
    sprawdz("zły PIN nadal odrzucany", kod == 401)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
