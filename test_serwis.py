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


def _wczytaj_baze(**srodowisko):
    """
    `narzedzia/baza.py` z zadanym środowiskiem.

    Ścieżki liczy przy imporcie, więc żeby sprawdzić zachowanie w kontenerze
    i poza nim, moduł trzeba wczytać dwa razy — stąd importlib zamiast
    zwykłego `import`. Środowisko przywracamy, bo reszta testów działa
    na własnym DATA_DIR.
    """
    import importlib.util
    klucze = ("DATA_DIR", "PROFIL", "KOPIE_DIR")
    stare = {k: os.environ.get(k) for k in klucze}
    try:
        for k in klucze:
            os.environ.pop(k, None)
        os.environ.update(srodowisko)
        sciezka = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "narzedzia", "baza.py")
        spec = importlib.util.spec_from_file_location("_baza_test", sciezka)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in stare.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


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

    # ============================ S7 — kopie zapasowe w kontenerze
    #
    # Nie dotyczy trybu serwisowego, ale tej samej rodziny błędów: coś, co
    # zależy WYŁĄCZNIE od zmiennych środowiskowych i psuje się cicho.
    # `narzedzia/baza.py` szukał bazy w data/<profil>, a kontener trzyma ją
    # wprost w DATA_DIR — nocny cron kopii co rano meldowałby „nie ma bazy
    # profilu 'prod'" do logu, którego nikt nie czyta. Brak kopii wyszedłby
    # dopiero przy awarii, czyli w najgorszym możliwym momencie.
    print("\nS7 — narzedzia/baza.py w kontenerze (DATA_DIR)")
    b = _wczytaj_baze(DATA_DIR="/data", PROFIL="prod")
    sprawdz("baza czytana z DATA_DIR, nie z data/<profil>",
            b.sciezka_db("prod") == os.path.join("/data", "leady_v3.db"),
            b.sciezka_db("prod"))
    sprawdz("kopie lądują na wolumenie (/app/kopie znika przy przebudowie)",
            b.KOPIE == os.path.join("/data", "kopie"), b.KOPIE)
    sprawdz("własny profil przechodzi", b._obcy_profil("prod") is None)
    obcy = b._obcy_profil("test")
    sprawdz("obcy profil ODMAWIA zamiast ruszyć nie tę bazę", bool(obcy))
    sprawdz("i mówi wprost którego profilu dotyczy", bool(obcy) and "'test'" in obcy)

    b = _wczytaj_baze(KOPIE_DIR="/gdzie/indziej", DATA_DIR="/data", PROFIL="test")
    sprawdz("KOPIE_DIR ma pierwszeństwo", b.KOPIE == "/gdzie/indziej", b.KOPIE)

    b = _wczytaj_baze()
    sprawdz("bez DATA_DIR (praca na Windows) — ścieżka jak dawniej",
            b.sciezka_db("prod").endswith(os.path.join("data", "prod", "leady_v3.db")),
            b.sciezka_db("prod"))
    sprawdz("bez DATA_DIR wszystkie profile dostępne",
            b._obcy_profil("prod", "test", "pusta") is None)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
