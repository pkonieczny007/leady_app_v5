# -*- coding: utf-8 -*-
"""
Testy lustra rejestru RSPO (M1) i obszarów działania (M2).

Na syntetycznym pliku CSV, nie na realnym eksporcie — test ma pilnować REGUŁ
(pancerz Excela, gmina bije powiat, bezpiecznik zniknięć, oznaczanie zamiast
kasowania), a nie liczb konkretnego miesiąca. Liczby kontrolne realnego pliku
sprawdza `narzedzia/migracja_rspo.py obszary` przy każdym wgraniu.
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["PROFIL"] = "test"

import db                      # noqa: E402
import rejestr_rspo            # noqa: E402
import obszary                 # noqa: E402

WYNIKI = []


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek)))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


NAGLOWKI = ("Numer RSPO;Nazwa;Typ;REGON;NIP;Województwo;Powiat;Gmina;"
            "Miejscowość;Rodzaj miejscowości;Kod terytorialny gmina;Ulica;"
            "Numer budynku;Numer lokalu;Kod pocztowy;Poczta;Telefon;Faks;"
            "E-mail;Strona www;Imię i nazwisko dyrektora;Publiczność status;"
            "Kategoria uczniów;Specyfika placówki;Liczba uczniów;"
            "Języki nauczane;Typ organu prowadzącego;Nazwa organu prowadzącego;"
            "REGON organu prowadzącego;Miejsce w strukturze;"
            "RSPO podmiotu nadrzędnego;Nazwa podmiotu nadrzędnego;"
            "Data założenia;Data likwidacji")


def _wiersz(rspo, nazwa, typ, powiat, gmina, miejscowosc, telefon="", woj="ŚLĄSKIE"):
    pola = [""] * 34
    pola[0] = str(rspo); pola[1] = nazwa; pola[2] = typ
    pola[5] = woj; pola[6] = powiat; pola[7] = gmina; pola[8] = miejscowosc
    pola[16] = telefon
    return ";".join(pola)


_licznik_csv = [0]


def _zapisz_csv(wiersze):
    # Każdy zapis pod NOWĄ ścieżką. Ta sama nazwa pliku sprawiła, że „plik
    # pierwotny" w R4 miał już treść drugiego wgrania — test przechodził albo
    # padał zależnie od kolejności, czyli nie testował niczego.
    _licznik_csv[0] += 1
    p = os.path.join(os.environ["DATA_DIR"], "rejestr_%d.csv" % _licznik_csv[0])
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        f.write(NAGLOWKI + "\n")
        for w in wiersze:
            f.write(w + "\n")
    return p


def main():
    conn = db.get_conn()
    # Tabele robocze zakłada normalnie aplikacja przy starcie — tu robimy to
    # wprost, żeby R6 mógł sprawdzić, że lustro ich NIE dotyka.
    db.init_db(conn)

    print("\nR1 — wgranie do lustra: pancerz Excela, filtr województwa, klucz")
    plik = _zapisz_csv([
        _wiersz(100, "SP NR 1 W KNUROWIE", "Szkoła podstawowa",
                "gliwicki", "Knurów", "Knurów", telefon='="0321234567"'),
        _wiersz(200, "SP NR 2 W PYSKOWICACH", "Szkoła podstawowa",
                "gliwicki", "Pyskowice", "Pyskowice"),
        _wiersz(300, "SP W RYBNIKU", "Szkoła podstawowa",
                "Rybnik", "Rybnik", "Rybnik"),
        _wiersz(400, "SP W CZERWIONCE", "Szkoła podstawowa",
                "rybnicki", "Czerwionka-Leszczyny", "Czerwionka-Leszczyny"),
        _wiersz(500, "PRZEDSZKOLE NR 5 W KATOWICACH", "Przedszkole",
                "Katowice", "Katowice", "Katowice"),
        _wiersz(600, "SP W WARSZAWIE", "Szkoła podstawowa",
                "Warszawa", "Warszawa", "Warszawa", woj="MAZOWIECKIE"),
        _wiersz(100, "SP NR 1 W KNUROWIE (POWTÓRKA)", "Szkoła podstawowa",
                "gliwicki", "Knurów", "Knurów"),
    ])
    ok, brak, _ = rejestr_rspo.sprawdz_naglowki(plik)
    sprawdz("nagłówki rozpoznane", ok, str(brak))
    r = rejestr_rspo.wgraj(conn, plik)
    sprawdz("mazowieckie odfiltrowane", r["w_zakresie"] == 5,
            "w zakresie: %d" % r["w_zakresie"])
    sprawdz("powtórka numeru wzięta raz", r["nowych"] == 5
            and any("powtarzało" in u for u in r["uwagi"]))
    tel = conn.execute("SELECT telefon FROM rspo_rejestr WHERE rspo=100").fetchone()[0]
    sprawdz("pancerz Excela zdjęty, zero wiodące zostało", tel == "0321234567", tel)

    print("\nR2 — obszary: gmina bije powiat, rybnicki nie wchodzi")
    obszary.zasiej(conn)
    n = obszary.przelicz(conn)
    sprawdz("przypisane: Knurów, Rybnik-miasto, Katowice", n == 3, "n=%d" % n)
    przez = conn.execute("SELECT przez FROM rspo_obszar WHERE rspo=100").fetchone()[0]
    sprawdz("Knurów wszedł przez GMINĘ, nie przez powiat gliwicki",
            przez == "gmina:Knurów", przez)
    sprawdz("reszta powiatu gliwickiego NIE weszła", conn.execute(
        "SELECT COUNT(*) FROM rspo_obszar WHERE rspo=200").fetchone()[0] == 0)
    sprawdz("Rybnik-miasto wszedł", conn.execute(
        "SELECT przez FROM rspo_obszar WHERE rspo=300").fetchone()[0] == "powiat:Rybnik")
    sprawdz("powiat rybnicki NIE wszedł", conn.execute(
        "SELECT COUNT(*) FROM rspo_obszar WHERE rspo=400").fetchone()[0] == 0)
    sprawdz("zasiew do niepustej tabeli nic nie dopisuje",
            obszary.zasiej(conn) == 0)

    print("\nR3 — drugie wgranie: zmiana w dzienniku, zniknięcie oznaczone")
    plik2 = _zapisz_csv([
        _wiersz(100, "SP NR 1 IM. POWSTAŃCÓW W KNUROWIE", "Szkoła podstawowa",
                "gliwicki", "Knurów", "Knurów", telefon='="0321234567"'),
        _wiersz(200, "SP NR 2 W PYSKOWICACH", "Szkoła podstawowa",
                "gliwicki", "Pyskowice", "Pyskowice"),
        _wiersz(300, "SP W RYBNIKU", "Szkoła podstawowa",
                "Rybnik", "Rybnik", "Rybnik"),
        _wiersz(400, "SP W CZERWIONCE", "Szkoła podstawowa",
                "rybnicki", "Czerwionka-Leszczyny", "Czerwionka-Leszczyny"),
        # 500 zniknęło z rejestru
    ])
    r2 = rejestr_rspo.wgraj(conn, plik2)
    sprawdz("zmiana nazwy policzona", r2["zmienionych"] == 1 and r2["nowych"] == 0,
            "zmienionych=%d" % r2["zmienionych"])
    zm = rejestr_rspo.zmiany_importu(conn, r2["import_id"])
    sprawdz("dziennik mówi, co dokładnie się zmieniło",
            any(z["pole"] == "nazwa" and "POWSTAŃCÓW" in z["jest"] for z in zm))
    nieobecna = conn.execute(
        "SELECT nieobecna_od FROM rspo_rejestr WHERE rspo=500").fetchone()
    sprawdz("zniknięta OZNACZONA, nie skasowana",
            nieobecna is not None and nieobecna[0],
            str(nieobecna and nieobecna[0]))
    sprawdz("wiersz zniknietej dalej jest w lustrze", conn.execute(
        "SELECT COUNT(*) FROM rspo_rejestr").fetchone()[0] == 5)

    print("\nR4 — powrót do rejestru zdejmuje oznaczenie")
    r3 = rejestr_rspo.wgraj(conn, plik)     # plik pierwotny, 500 wraca
    sprawdz("powrót policzony", r3["wrocilo"] == 1, "wrocilo=%d" % r3["wrocilo"])
    sprawdz("oznaczenie zdjęte", conn.execute(
        "SELECT nieobecna_od FROM rspo_rejestr WHERE rspo=500").fetchone()[0] is None)

    print("\nR5 — bezpiecznik: plik-wycinek nie oznacza zniknięć")
    # 30 placówek w lustrze, potem plik z samymi 2 — ubytek 28 > MIN_ZNIKNIEC
    # i > 20%, więc oznaczanie ma się WSTRZYMAĆ.
    duzo = [_wiersz(1000 + i, "SP TESTOWA %d" % i, "Szkoła podstawowa",
                    "Katowice", "Katowice", "Katowice") for i in range(30)]
    rejestr_rspo.wgraj(conn, _zapisz_csv(duzo))
    r4 = rejestr_rspo.wgraj(conn, _zapisz_csv(duzo[:2]))
    sprawdz("bezpiecznik wstrzymał oznaczanie", r4["zniknelo"] == 0
            and any("Wstrzymano" in u for u in r4["uwagi"]),
            (r4["uwagi"] or ["brak uwag"])[0][:70])

    print("\nR6 — tabele lustra nie dotykają tabel roboczych")
    sprawdz("placowki puste jak były", conn.execute(
        "SELECT COUNT(*) FROM placowki").fetchone()[0] == 0)
    sprawdz("leady puste jak były", conn.execute(
        "SELECT COUNT(*) FROM leady").fetchone()[0] == 0)

    conn.close()
    ok = sum(1 for _, w in WYNIKI if w)
    zle = [n for n, w in WYNIKI if not w]
    print("\n" + "=" * 62)
    print("== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    if zle:
        print("NIEUDANE:")
        for n in zle:
            print("  - %s" % n)
    return 1 if zle else 0


if __name__ == "__main__":
    sys.exit(main())
