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
import dokladanie              # noqa: E402

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


def _wiersz(rspo, nazwa, typ, powiat, gmina, miejscowosc, telefon="", woj="ŚLĄSKIE",
            publicznosc="", ulica="", nr_budynku=""):
    pola = [""] * 34
    pola[0] = str(rspo); pola[1] = nazwa; pola[2] = typ
    pola[5] = woj; pola[6] = powiat; pola[7] = gmina; pola[8] = miejscowosc
    pola[11] = ulica; pola[12] = nr_budynku
    pola[16] = telefon
    pola[21] = publicznosc
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


def _slownik(conn, rodzaj, wartosci):
    for i, w in enumerate(wartosci):
        conn.execute("INSERT OR IGNORE INTO slowniki (rodzaj, wartosc, sort_order)"
                     " VALUES (?,?,?)", (rodzaj, w, i))
    conn.commit()


def testy_dokladania(conn):
    """R7–R11: dołożenie brakujących placówek z lustra (M7a)."""
    print("\nR7 — dołożenie: co wchodzi, a co świadomie nie")
    plik = _zapisz_csv([
        _wiersz(2001, "PRZEDSZKOLE MIEJSKIE NR 7 W KATOWICACH", "Przedszkole",
                "Katowice", "Katowice", "Katowice", publicznosc="publiczna",
                ulica="Orla", nr_budynku="6", telefon='="0322223344"'),
        _wiersz(2002, "NIEPUBLICZNE PRZEDSZKOLE TĘCZOWA KRAINA", "Przedszkole",
                "Katowice", "Katowice", "Katowice", publicznosc="niepubliczna"),
        _wiersz(2003, "PUNKT PRZEDSZKOLNY BAJKA W SIEWIERZU", "Punkt przedszkolny",
                "będziński", "Siewierz", "Siewierz", publicznosc="niepubliczna"),
        _wiersz(2004, "ZESPÓŁ SZKOLNO-PRZEDSZKOLNY NR 3 W KATOWICACH",
                "Zespół szkół i placówek oświatowych",
                "Katowice", "Katowice", "Katowice"),
        _wiersz(2005, "SZKOŁA PODSTAWOWA NR 99 W KATOWICACH", "Szkoła podstawowa",
                "Katowice", "Katowice", "Katowice"),
        _wiersz(2006, "PRZEDSZKOLE W PYSKOWICACH", "Przedszkole",
                "gliwicki", "Pyskowice", "Pyskowice", publicznosc="publiczna"),
    ])
    # Zniknięcia wyłączone: to dosypka do lustra, nie obraz całego rejestru.
    rejestr_rspo.wgraj(conn, plik, wykryj_znikniete=False)
    obszary.przelicz(conn)

    _slownik(conn, "miasto", ["08. Katowice", "15. Będzin"])
    _slownik(conn, "status_realizacji", [dokladanie.STATUS_NOWEGO])
    _slownik(conn, "status_szkoly", [dokladanie.STATUS_SZKOLY_NOWA])

    # Najpierw BEZ pozycji przedszkolnych w słowniku typów — to ta sama pułapka,
    # przez którą `CYKLICZNE-PRZEDSZKOLE` dawało się zapisać, ale nie poprawić.
    plan = dokladanie.przygotuj(conn, "przedszkola")
    sprawdz("brak pozycji w słowniku typów wykryty PRZED zapisem",
            any(r == "typ_placowki" for r, _ in plan["braki_slownikow"]))
    odmowa = False
    try:
        dokladanie.zapisz(conn, plan)
    except ValueError:
        odmowa = True
    sprawdz("zapis odmawia, gdy słownik profilu nie zna wartości", odmowa)
    sprawdz("po odmowie baza nietknięta", conn.execute(
        "SELECT COUNT(*) FROM placowki").fetchone()[0] == 0)

    _slownik(conn, "typ_placowki", [dokladanie.TYP_SP,
                                    dokladanie.TYP_PRZEDSZKOLE_PUB,
                                    dokladanie.TYP_PRZEDSZKOLE_NIEPUB])
    plan = dokladanie.przygotuj(conn, "przedszkola")
    numery = {r["rspo"] for r in plan["do_zapisu"]}
    sprawdz("weszły oba przedszkola i punkt", numery == {2001, 2002, 2003},
            str(sorted(numery)))
    sprawdz("zespół szkolno-przedszkolny NIE wchodzi (rekord ma być na składową)",
            2004 not in numery)
    sprawdz("szkoła podstawowa nie wchodzi do grupy „przedszkola”", 2005 not in numery)
    sprawdz("placówka spoza obszarów nie wchodzi", 2006 not in numery)

    wg = {r["rspo"]: r for r in plan["do_zapisu"]}
    sprawdz("publiczne → przedszkole miejskie",
            wg[2001]["typ"] == dokladanie.TYP_PRZEDSZKOLE_PUB)
    sprawdz("niepubliczne → przedszkole prywatne",
            wg[2002]["typ"] == dokladanie.TYP_PRZEDSZKOLE_NIEPUB)
    # Miejscowość wprost z rejestru — od M6 osią filtrowania jest powiat, więc
    # nie ma po co przepisywać nazwy na wartość słownika (i nie ma potem czego
    # czyścić osobnym przebiegiem, o którym łatwo zapomnieć na produkcji).
    sprawdz("miejscowość czysta, prosto z rejestru",
            wg[2001]["miejscowosc"] == "Katowice", wg[2001]["miejscowosc"])
    sprawdz("wieś spoza słownika zachowuje swoją nazwę",
            wg[2003]["miejscowosc"] == "Siewierz", wg[2003]["miejscowosc"])
    sprawdz("powiat wsi zgodny z rejestrem", wg[2003]["powiat"] == "będziński")
    sprawdz("adres sklejony z ulicy i numeru", wg[2001]["adres"] == "Orla 6",
            str(wg[2001]["adres"]))

    dodane = dokladanie.zapisz(conn, plan, kto="test")
    sprawdz("zapisano tyle, ile zapowiadał podgląd", dodane == 3)
    sprawdz("każda placówka ma lead", conn.execute(
        "SELECT COUNT(*) FROM leady").fetchone()[0] == 3)
    bez_handlowca = conn.execute(
        "SELECT COUNT(*) FROM leady WHERE handlowiec IS NULL AND status_realizacji=?",
        (dokladanie.STATUS_NOWEGO,)).fetchone()[0]
    sprawdz("leady nieprzydzielone — niczyja lista „moje szkoły” nie rośnie",
            bez_handlowca == 3)
    sprawdz("geografia z rejestru na placówce", conn.execute(
        "SELECT powiat FROM placowki WHERE rspo='2003'").fetchone()[0] == "będziński")
    sprawdz("obszar wpisany", conn.execute(
        "SELECT obszar FROM placowki WHERE rspo='2003'").fetchone()[0] == "powiat będziński")

    print("\nR7b — typy pozaszkolne i zespoły")
    _slownik(conn, "typ_placowki", [dokladanie.TYP_ZESPOL,
                                    dokladanie.TYP_POZASZKOLNA])
    plik_poza = _zapisz_csv([
        _wiersz(3001, "MŁODZIEŻOWY DOM KULTURY W KATOWICACH", "Młodzieżowy dom kultury",
                "Katowice", "Katowice", "Katowice", publicznosc="publiczna"),
        _wiersz(3002, "OGNISKO PRACY POZASZKOLNEJ NR 1", "Ognisko pracy pozaszkolnej",
                "Katowice", "Katowice", "Katowice", publicznosc="publiczna"),
        _wiersz(3003, "ZESPÓŁ SZKÓŁ NR 7 W KATOWICACH",
                "Zespół szkół i placówek oświatowych",
                "Katowice", "Katowice", "Katowice"),
        _wiersz(3004, "ZESPÓŁ WYCHOWANIA PRZEDSZKOLNEGO",
                "Zespół wychowania przedszkolnego",
                "Katowice", "Katowice", "Katowice", publicznosc="niepubliczna"),
    ])
    rejestr_rspo.wgraj(conn, plik_poza, wykryj_znikniete=False)
    obszary.przelicz(conn)

    poza = dokladanie.przygotuj(conn, "pozaszkolne")
    typy_poza = {r["rspo"]: r["typ"] for r in poza["do_zapisu"]}
    sprawdz("dom kultury i ognisko idą do instytucji kultury",
            typy_poza.get(3001) == dokladanie.TYP_POZASZKOLNA
            and typy_poza.get(3002) == dokladanie.TYP_POZASZKOLNA,
            str(typy_poza))
    sprawdz("zespół NIE wchodzi do grupy pozaszkolnej", 3003 not in typy_poza)

    wszystkie = {r["rspo"] for r in dokladanie.przygotuj(conn, "wszystkie")["do_zapisu"]}
    # Zespół stanąłby OBOK własnych składowych — trzy rekordy pod jednym adresem.
    # Dlatego trzeba o niego poprosić wprost, a nie dostać go przy okazji.
    sprawdz("„wszystkie” świadomie pomija zespoły", 3003 not in wszystkie)
    sprawdz("„wszystkie” obejmuje pozaszkolne i przedszkolne",
            3001 in wszystkie and 3004 in wszystkie, str(sorted(wszystkie)))
    zesp = {r["rspo"]: r["typ"] for r in dokladanie.przygotuj(conn, "zespoly")["do_zapisu"]}
    sprawdz("zespół wchodzi dopiero na wyraźne życzenie",
            zesp.get(3003) == dokladanie.TYP_ZESPOL, str(zesp))
    sprawdz("zespół wychowania przedszkolnego liczy się jak przedszkole",
            {r["rspo"]: r["typ"] for r in dokladanie.przygotuj(conn, "przedszkola")
             ["do_zapisu"]}.get(3004) == dokladanie.TYP_PRZEDSZKOLE_NIEPUB)

    print("\nR8 — powtórzenie nie tworzy dubli")
    plan2 = dokladanie.przygotuj(conn, "przedszkola")
    # Sprawdzamy, że nie wracają rekordy JUŻ ZAPISANE — a nie że lista jest
    # pusta: R7b dosypało do lustra kandydatów, których świadomie nie zapisano.
    sprawdz("zapisane rekordy nie wracają na listę",
            not ({2001, 2002, 2003} & {r["rspo"] for r in plan2["do_zapisu"]}),
            str([r["rspo"] for r in plan2["do_zapisu"]]))
    sprawdz("liczba placówek bez zmian", conn.execute(
        "SELECT COUNT(*) FROM placowki").fetchone()[0] == 3)

    print("\nR9 — kolizja z rekordem handlowca: odkładamy, nie dokładamy")
    conn.execute("INSERT INTO placowki (nazwa, typ, miejscowosc, zrodlo)"
                 " VALUES (?,?,?,?)",
                 ("Tęczowa Kraina", "04. Inna", "Katowice", "reka"))
    # Rekord SZKOŁY o mylnie podobnej nazwie NIE ma odkładać przedszkola:
    # to ten sam operator i dwie różne placówki (289 fałszywych trafień
    # w pierwszym podejściu wzięło się dokładnie stąd).
    conn.execute("INSERT INTO placowki (nazwa, typ, miejscowosc, zrodlo)"
                 " VALUES (?,?,?,?)",
                 ("SZKOŁA PODSTAWOWA BAJKA W KATOWICACH", "01. Szkoła podstawowa",
                  "Katowice", "reka"))
    conn.commit()
    conn.execute("DELETE FROM placowki WHERE rspo='2002'")
    conn.commit()
    plan3 = dokladanie.przygotuj(conn, "przedszkola")
    sprawdz("kandydat pod nazwą, którą już mamy — odłożony",
            [k["rspo"] for k in plan3["kolizje"]] == [2002],
            str([k["rspo"] for k in plan3["kolizje"]]))
    sprawdz("odłożonego nie ma na liście do zapisu",
            2002 not in {r["rspo"] for r in plan3["do_zapisu"]})

    # NUMER SZKOŁY ROZSTRZYGA. „MIEJSKA SZKOŁA PODSTAWOWA NR 7 W KNUROWIE" to
    # same słowa puste plus miejscowość — bez numeru sklejała się i z SP nr 9,
    # i z „NIEPUBLICZNĄ SP »DOBRE MIEJSCE«" w tym samym mieście.
    conn.execute("INSERT INTO placowki (nazwa, typ, miejscowosc, zrodlo) VALUES (?,?,?,?)",
                 ("MIEJSKA SZKOŁA PODSTAWOWA NR 7 W KNUROWIE",
                  "01. Szkoła podstawowa", "Knurów", "reka"))
    conn.commit()
    _slownik(conn, "miasto", ["Knurów"])
    plik_knurow = _zapisz_csv([
        _wiersz(2101, "MIEJSKA SZKOŁA PODSTAWOWA NR 7 W KNUROWIE", "Szkoła podstawowa",
                "gliwicki", "Knurów", "Knurów"),
        _wiersz(2102, "MIEJSKA SZKOŁA PODSTAWOWA NR 9 IM. MARII KONOPNICKIEJ",
                "Szkoła podstawowa", "gliwicki", "Knurów", "Knurów"),
        _wiersz(2103, "NIEPUBLICZNA SZKOŁA PODSTAWOWA DOBRE MIEJSCE",
                "Szkoła podstawowa", "gliwicki", "Knurów", "Knurów"),
    ])
    rejestr_rspo.wgraj(conn, plik_knurow, wykryj_znikniete=False)
    obszary.przelicz(conn)
    plan_sz = dokladanie.przygotuj(conn, "szkoly")
    odlozone_sz = {k["rspo"] for k in plan_sz["kolizje"]}
    dodawane_sz = {r["rspo"] for r in plan_sz["do_zapisu"]}
    sprawdz("ta sama szkoła z tym samym numerem — odłożona", 2101 in odlozone_sz,
            str(sorted(odlozone_sz)))
    sprawdz("szkoła z INNYM numerem wchodzi normalnie", 2102 in dodawane_sz)
    sprawdz("szkoła bez numeru nie skleja się z naszą „nr 7”", 2103 in dodawane_sz)

    plik_bajka = _zapisz_csv([
        _wiersz(2007, "PRZEDSZKOLE BAJKA W KATOWICACH", "Przedszkole",
                "Katowice", "Katowice", "Katowice", publicznosc="publiczna"),
    ])
    rejestr_rspo.wgraj(conn, plik_bajka, wykryj_znikniete=False)
    obszary.przelicz(conn)
    plan4 = dokladanie.przygotuj(conn, "przedszkola")
    sprawdz("szkoła o podobnej nazwie NIE blokuje przedszkola",
            2007 in {r["rspo"] for r in plan4["do_zapisu"]})

    print("\nR10 — cofnięcie kasuje tylko to, czego nikt nie dotknął")
    # Sierot w logu jest już jedna — z ręcznego DELETE w R9. `log` NIE MA klucza
    # obcego celowo (ślad ma przeżyć skasowany rekord), więc mierzymy przyrost,
    # nie wartość bezwzględną: cofnięcie ma po sobie nie zostawiać nic.
    sieroty_przed = conn.execute(
        "SELECT COUNT(*) FROM log WHERE lead_id NOT IN (SELECT id FROM leady)"
    ).fetchone()[0]
    lid = conn.execute("SELECT l.id FROM leady l JOIN placowki p ON p.id=l.placowka_id"
                       " WHERE p.rspo='2001'").fetchone()[0]
    conn.execute("INSERT INTO eventy (lead_id, typ, data) VALUES (?,?,?)",
                 (lid, "DT", "2026-09-01"))
    conn.commit()
    r = dokladanie.cofnij(conn)
    sprawdz("placówka z umówionym DT zostaje", conn.execute(
        "SELECT COUNT(*) FROM placowki WHERE rspo='2001'").fetchone()[0] == 1)
    sprawdz("nietknięta placówka skasowana", conn.execute(
        "SELECT COUNT(*) FROM placowki WHERE rspo='2003'").fetchone()[0] == 0)
    sprawdz("DT przeżyło cofnięcie", conn.execute(
        "SELECT COUNT(*) FROM eventy").fetchone()[0] == 1, str(r))
    sprawdz("cofnięcie nie zostawia sierot w logu", conn.execute(
        "SELECT COUNT(*) FROM log WHERE lead_id NOT IN (SELECT id FROM leady)"
    ).fetchone()[0] == sieroty_przed)
    sprawdz("rekordy handlowca nietknięte", conn.execute(
        "SELECT COUNT(*) FROM placowki WHERE zrodlo='reka'").fetchone()[0] == 3)


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

    testy_dokladania(conn)

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
