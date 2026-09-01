# -*- coding: utf-8 -*-
"""
Testy filtra osób (v4) — wpisywane nazwiska zamiast list rozwijanych.

Sprawdzamy trzy rzeczy, o które prosił klient wprost:
  1. da się WPISAĆ fragment nazwiska (a nie tylko wybrać z listy),
  2. wpisów może być kilka i da się je łączyć (LUB / ORAZ),
  3. wpis da się wyłączyć bez kasowania i zablokować tak, żeby przeżył „Wyczyść".
Plus to, co z tego wynika: filtr obejmuje trenerów (dotąd niedostępnych w ogóle),
a widok, licznik i eksport XLSX czytają ten sam query string.

Uruchomienie:  python test_filtr_osob.py
Działa na WŁASNEJ, tymczasowej bazie (nie rusza `data/leady_v3.db`).
"""
import json
import re
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

TMP = tempfile.mkdtemp(prefix="leady_v4_osoby_test_")
os.environ["DATA_DIR"] = TMP

import app as A                      # noqa: E402
import calendar_view as cv           # noqa: E402
import db                            # noqa: E402
import dostepnosc_view as dv         # noqa: E402
import filtry as fl                  # noqa: E402
import repo                          # noqa: E402
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


def sprawdz(nazwa, warunek, opis=""):
    WYNIKI.append((nazwa, bool(warunek), opis))
    print("  [%s] %s%s" % ("OK  " if warunek else "BLAD", nazwa,
                           (" — " + opis) if opis else ""))
    return bool(warunek)


def post(url, payload):
    r = KL.post(url, data=json.dumps(payload), content_type="application/json")
    return r.status_code, r.get_json()


def nazwy(osoby, tryb="lub", zakres="przydzielone"):
    """Nazwy placówek, które przechodzą przez filtr — przez tę samą drogę co ekran."""
    conn = db.get_conn()
    f = repo.pusty_filtr()
    f["zakres"] = zakres
    f["osoby"] = osoby
    f["osoby_tryb"] = tryb
    rows = repo.filtruj_leady(conn, f)
    ile = repo.policz_leady(conn, f)
    conn.close()
    return sorted(r["placowka"] for r in rows), ile


def rozlaczne(kandydaci, obce, ile):
    """
    Wybiera `ile` nazwisk, z których żadne nie jest kawałkiem innego ani kawałkiem
    nazwiska z listy `obce`. Bez tego test byłby loteryjny: filtr szuka FRAGMENTU,
    więc „Bitner" trafiłby też w „Bitnerowa", a nazwiska w słownikach klienta
    biorą się z realnego pliku i mogą się zmienić.
    """
    obce_f = [db.pl_fold(A.f_bez_prefiksu(x)) for x in obce]
    wybrane, wybrane_f = [], []
    for k in kandydaci:
        kf = db.pl_fold(A.f_bez_prefiksu(k))
        if not kf:
            continue
        kolizja = any(kf in x or x in kf for x in obce_f + wybrane_f)
        if kolizja:
            continue
        wybrane.append(k)
        wybrane_f.append(kf)
        if len(wybrane) == ile:
            break
    return wybrane


def main():
    print("Baza testowa:", TMP)
    bootstrap()
    _zaloguj_testowo()
    conn = db.get_conn()
    handlowcy = db.slownik_values(conn, "handlowiec")
    trenerzy = db.slownik_values(conn, "trener")
    miasta = db.slownik_values(conn, "miasto")
    conn.close()
    # Ta sama osoba bywa i handlowcem, i trenerem (Olszewska, Małolepsza…), więc
    # do testu bierzemy pięć nazwisk, które nie mieszczą się w sobie nawzajem.
    # Baza po `bootstrap()` nie ma żadnych leadów, więc w danych wystąpią tylko te.
    H1, H2 = rozlaczne(handlowcy, [], 2)
    T1, T2, T3 = rozlaczne(trenerzy, [H1, H2], 3)
    M1 = miasta[0]
    DATA = "2026-09-15"
    print("  handlowcy: %s | %s" % (H1, H2))
    print("  trenerzy:  %s | %s | %s" % (T1, T2, T3))

    print("\nO1 — parsowanie zapisu z URL")
    c = repo.parsuj_osoby("Sacawa")
    sprawdz("goły tekst = wpis czynny, zakres „dowolna osoba”",
            len(c) == 1 and c[0] == {"tekst": "Sacawa", "zakres": "o",
                                     "wylaczony": False, "zablokowany": False}, str(c))
    c = repo.parsuj_osoby("#h:Sacawa|-t:Bitner|o:Nowak")
    sprawdz("flagi i zakresy czytane poprawnie",
            [(x["tekst"], x["zakres"], x["wylaczony"], x["zablokowany"]) for x in c]
            == [("Sacawa", "h", False, True), ("Bitner", "t", True, False),
                ("Nowak", "o", False, False)], str(c))
    sprawdz("flagi w odwrotnej kolejności też działają",
            repo.parsuj_osoby("#-t:X") == repo.parsuj_osoby("-#t:X"))
    sprawdz("puste kawałki i same flagi wypadają",
            repo.parsuj_osoby("||  |-#|h:|Kowal") ==
            [{"tekst": "Kowal", "zakres": "o", "wylaczony": False, "zablokowany": False}],
            str(repo.parsuj_osoby("||  |-#|h:|Kowal")))
    sprawdz("ten sam wpis dwa razy = jeden chip",
            len(repo.parsuj_osoby("h:Zemeła|h:zemela")) == 1)
    sprawdz("ten sam tekst w innym zakresie to osobny chip",
            len(repo.parsuj_osoby("h:Kowal|t:Kowal")) == 2)
    sprawdz("liczba wpisów obcięta do %d" % repo.MAX_OSOB,
            len(repo.parsuj_osoby("|".join("nazwisko%d" % i for i in range(30))))
            == repo.MAX_OSOB)
    sprawdz("dwukropek w nazwisku nie jest brany za zakres",
            repo.parsuj_osoby("x:Kowal")[0]["tekst"] == "x:Kowal")
    sprawdz("zapis i odczyt się domykają",
            repo.zapisz_osoby(repo.parsuj_osoby("#h:Sacawa|-t:Bitner"))
            == "#h:Sacawa|-t:Bitner",
            repo.zapisz_osoby(repo.parsuj_osoby("#h:Sacawa|-t:Bitner")))

    print("\nO2 — czytanie filtra z query stringa")
    with A.app.test_request_context("/leady?osoby=%23h%3ASacawa%7CNowak"):
        f = repo.czytaj_filtr(A.request.args)
    sprawdz("chipy trafiają do `osoby_lista`", len(f["osoby_lista"]) == 2)
    sprawdz("`osoby` wraca w postaci znormalizowanej",
            f["osoby"] == "#h:Sacawa|o:Nowak", f["osoby"])
    sprawdz("`osoby_zablokowane` niesie tylko wpis z kłódką",
            f["osoby_zablokowane"] == "#h:Sacawa", f["osoby_zablokowane"])
    sprawdz("domyślny tryb łączenia to LUB", f["osoby_tryb"] == "lub")
    with A.app.test_request_context("/leady?osoby=-Nowak&osoby_tryb=oraz"):
        f2 = repo.czytaj_filtr(A.request.args)
    sprawdz("tryb ORAZ czytany z URL", f2["osoby_tryb"] == "oraz")
    sprawdz("wyłączony wpis nie liczy się jako czynny", f2["osoby_czynne"] == 0)

    # ---------------------------------------------------------------- dane
    # Trzy placówki: każda u innego handlowca, każda z innym prowadzącym DT.
    print("\nO3 — filtrowanie po fragmencie nazwiska")
    plac = {}
    for nazwa, h, t in [("SP Alfa", H1, T1), ("SP Beta", H2, T2),
                        ("SP Gamma", H1, T2)]:
        kod, d = post("/api/lead", {"nazwa": nazwa, "miejscowosc": M1,
                                    "typ": None, "handlowiec": h})
        sprawdz("dane testowe: %s dodane" % nazwa, kod == 200 and d.get("ok"), str(d))
        plac[nazwa] = d["id"]
        post("/api/event", {"lead_id": d["id"], "typ": "DT", "data": DATA,
                            "godz_od": "09:00", "godz_do": "11:00", "trener": t})
    # „SP Beta" ma drugie DT z T3 jako ZASTĘPSTWEM — szukanie osoby ma je widzieć
    post("/api/event", {"lead_id": plac["SP Beta"], "typ": "DT", "data": "2026-09-16",
                        "godz_od": "09:00", "godz_do": "11:00", "zastepstwo": T3})

    # nazwisko bez prefiksu „01. " to już FRAGMENT wartości trzymanej w bazie —
    # dokładnie ten przypadek, którego lista rozwijana nie obsługiwała
    frag_h1 = A.f_bez_prefiksu(H1)
    frag_t1 = A.f_bez_prefiksu(T1)
    frag_t2 = A.f_bez_prefiksu(T2)
    frag_t3 = A.f_bez_prefiksu(T3)

    lista, ile = nazwy(frag_h1)
    sprawdz("fragment nazwiska handlowca wystarczy",
            "SP Alfa" in lista and "SP Gamma" in lista and "SP Beta" not in lista,
            "%s → %s" % (frag_h1, lista))
    sprawdz("licznik rekordów zgadza się z listą", ile == len(lista))
    lista, _ = nazwy(frag_h1.upper())
    sprawdz("wielkość liter bez znaczenia", "SP Alfa" in lista)
    lista, _ = nazwy(db.pl_fold(frag_h1))
    sprawdz("polskie ogonki bez znaczenia (pl_fold po obu stronach)",
            "SP Alfa" in lista, db.pl_fold(frag_h1))
    lista, _ = nazwy("t:" + frag_t2)
    sprawdz("filtr po PROWADZĄCYM — czego wcześniej nie dało się zrobić wcale",
            lista == ["SP Beta", "SP Gamma"], str(lista))
    lista, _ = nazwy("t:" + frag_t3)
    sprawdz("zastępstwo i drugi prowadzący też się liczą jako „osoba na spotkaniu”",
            lista == ["SP Beta"], str(lista))
    lista, _ = nazwy("h:" + frag_t2)
    sprawdz("zakres „h” nie zagląda do prowadzących", lista == [], str(lista))
    lista, _ = nazwy("nazwisko-ktorego-nie-ma")
    sprawdz("brak trafień = pusta lista, nie błąd", lista == [])

    print("\nO4 — łączenie i wyłączanie wpisów")
    lista, _ = nazwy("h:%s|t:%s" % (frag_h1, frag_t2))
    sprawdz("LUB składa wyniki (handlowiec ALBO prowadzący)",
            lista == ["SP Alfa", "SP Beta", "SP Gamma"], str(lista))
    lista, _ = nazwy("h:%s|t:%s" % (frag_h1, frag_t2), tryb="oraz")
    sprawdz("ORAZ zawęża do części wspólnej", lista == ["SP Gamma"], str(lista))
    lista, _ = nazwy("h:%s|-t:%s" % (frag_h1, frag_t2), tryb="oraz")
    sprawdz("wyłączony wpis nie zawęża, choć zostaje w filtrze",
            lista == ["SP Alfa", "SP Gamma"], str(lista))
    lista, _ = nazwy("-h:%s|-t:%s" % (frag_h1, frag_t2))
    bez_filtra, _ = nazwy("")
    sprawdz("same wyłączone wpisy = filtr nieaktywny", lista == bez_filtra)
    lista, _ = nazwy("#h:%s" % frag_h1)
    sprawdz("blokada nie zmienia wyniku, tylko trwałość wpisu",
            lista == ["SP Alfa", "SP Gamma"], str(lista))

    print("\nO5 — filtr osób a reszta paska")
    conn = db.get_conn()
    f = repo.pusty_filtr()
    f["zakres"] = "przydzielone"
    f["osoby"] = "t:" + frag_t2
    f["handlowiec"] = H2
    rows = repo.filtruj_leady(conn, f)
    conn.close()
    sprawdz("filtr osób łączy się ze starymi filtrami przez I",
            sorted(r["placowka"] for r in rows) == ["SP Beta"],
            str([r["placowka"] for r in rows]))

    print("\nO6 — ekrany, linki i eksport")
    url = "/leady?osoby=%%23h%%3A%s%%7C-t%%3A%s" % (frag_h1, frag_t2)
    r = KL.get(url)
    html = r.get_data(as_text=True)
    sprawdz("lista leadów z filtrem osób zwraca 200", r.status_code == 200)
    sprawdz("pole tekstowe do wpisywania jest na ekranie", 'id="osoby-wpis"' in html)
    sprawdz("na ekranie są dokładnie dwa chipy",
            html.count('data-akcja="usun"') == 2, str(html.count('data-akcja="usun"')))
    sprawdz("wyłączony chip ma swój wygląd", "chip-off" in html)
    sprawdz("zablokowany chip ma swój wygląd", "chip-zamk" in html)
    sprawdz("„Wyczyść” zostawia wpisy z kłódką",
            "osoby=%23h%3A" + frag_h1 in html.replace("&amp;", "&"))
    for ekran in ("/baza", "/zbiorczy", "/niewykorzystane", "/tydzien"):
        sprawdz("%s przyjmuje filtr osób" % ekran,
                KL.get(ekran + "?osoby=" + frag_h1).status_code == 200)
    r = KL.get("/export.xlsx?zakres=przydzielone&osoby=h:" + frag_h1)
    sprawdz("eksport XLSX przyjmuje ten sam parametr",
            r.status_code == 200 and len(r.get_data()) > 0, str(r.status_code))

    # ---------------------------------------------------------------- grafik
    # Kalendarz i dostępność mają INNE zakresy: „wszystko" i „nazwisko".
    # Filtrują się w Pythonie, nie w SQL — bo cykle rozwijają się na wystąpienia,
    # a wyjątki podmieniają trenera już po wyjściu z bazy.
    print("\nG1 — zakresy grafiku: wszystko / nazwisko")
    ch = fl.parsuj("Zemela", fl.ZAKRESY_GRAFIK)
    sprawdz("goły tekst na grafiku = zakres „wszystko”",
            ch[0]["zakres"] == "w", str(ch))
    ch = fl.parsuj("n:Zemela|w:Knurów", fl.ZAKRESY_GRAFIK)
    sprawdz("„n:” i „w:” czytane na grafiku",
            [c["zakres"] for c in ch] == ["n", "w"], str(ch))
    ch = fl.parsuj("h:Sacawa", fl.ZAKRESY_GRAFIK)
    sprawdz("zakres z innego ekranu sprowadzony do domyślnego, wpis NIE ginie",
            len(ch) == 1 and ch[0]["zakres"] == "w" and ch[0]["tekst"] == "Sacawa",
            str(ch))
    ch = fl.parsuj("n:Zemela", repo.ZAKRESY_OSOB)
    sprawdz("i odwrotnie: „n:” na liście leadów staje się „o:”",
            ch[0]["zakres"] == "o" and ch[0]["tekst"] == "Zemela", str(ch))

    print("\nG2 — kalendarz")
    MIES = DATA[:7]

    def kal(osoby, tryb="lub"):
        conn = db.get_conn()
        c = fl.parsuj(osoby, fl.ZAKRESY_GRAFIK)
        wyn = tuple(b(conn, MIES, chipy=c, tryb=tryb)["n_events"]
                    for b in (cv.build_matrix, cv.build_agenda, cv.build_starty))
        conn.close()
        return wyn

    wszystkie = kal("")
    sprawdz("bez filtra widać wszystkie spotkania miesiąca",
            wszystkie[0] == 4 and len(set(wszystkie)) == 1, str(wszystkie))
    sprawdz("filtr ogólny łapie nazwę szkoły", kal("Alfa") == (1, 1, 1), str(kal("Alfa")))
    sprawdz("filtr ogólny łapie miejscowość",
            kal(A.f_bez_prefiksu(M1)) == wszystkie, str(kal(A.f_bez_prefiksu(M1))))
    sprawdz("filtr ogólny łapie nazwisko prowadzącego",
            kal(frag_t2) == (2, 2, 2), str(kal(frag_t2)))
    sprawdz("przełączony na „nazwisko” NIE łapie nazwy szkoły",
            kal("n:Alfa") == (0, 0, 0), str(kal("n:Alfa")))
    sprawdz("„nazwisko” łapie prowadzącego", kal("n:" + frag_t2) == (2, 2, 2))
    sprawdz("„nazwisko” łapie zastępstwo wpisane na spotkaniu",
            kal("n:" + frag_t3) == (1, 1, 1), str(kal("n:" + frag_t3)))
    sprawdz("działa w każdym z trzech widoków tak samo",
            len(set(kal("n:" + frag_t2))) == 1)
    sprawdz("LUB składa wyniki",
            kal("n:%s|w:Alfa" % frag_t2) == (3, 3, 3), str(kal("n:%s|w:Alfa" % frag_t2)))
    sprawdz("ORAZ zawęża",
            kal("n:%s|w:Beta" % frag_t2, "oraz") == (1, 1, 1),
            str(kal("n:%s|w:Beta" % frag_t2, "oraz")))
    sprawdz("wyłączony wpis nie zawęża",
            kal("n:%s|-w:Beta" % frag_t2, "oraz") == (2, 2, 2))
    sprawdz("brak trafień = pusty kalendarz, nie błąd", kal("xyzzy") == (0, 0, 0))

    conn = db.get_conn()
    peln = cv.build_matrix(conn, MIES)
    waski = cv.build_matrix(conn, MIES, chipy=fl.parsuj("Alfa", fl.ZAKRESY_GRAFIK))
    conn.close()
    sprawdz("filtr chowa puste wiersze trenerów",
            all(w["ma"] for t in waski["tygodnie"] for w in t["wiersze"]))
    sprawdz("bez filtra wiersze wszystkich trenerów zostają",
            len(peln["trenerzy"]) >= len(trenerzy))

    # Zgłoszenie: „filtrując po 02. Olszewska w kalendarzu pokazuje mi też inne
    # pozycje trenerów". Przyczyna: ta sama osoba jest u nich handlowcem I trenerką,
    # a zakres „nazwisko" przeszukiwał także `handlowiec`. Na realnych danych
    # 117 ze 152 trafień brało się ze sprzedanych leadów, na które jeździł kto inny.
    print("\nG2b — „nazwisko” na grafiku to KTO TAM BĘDZIE, nie kto sprzedał")
    sprawdz("handlowiec NIE wpada w zakres „nazwisko” na kalendarzu",
            kal("n:" + frag_h1) == (0, 0, 0), str(kal("n:" + frag_h1)))
    sprawdz("ale „wszystko” dalej go znajduje — bo to znaczy wszystko",
            kal("w:" + frag_h1) == (2, 2, 2), str(kal("w:" + frag_h1)))
    sprawdz("handlowiec nie siedzi w polach osób na miejscu",
            "handlowiec" not in fl.POLA_OSOBY and "handlowiec" in fl.POLA_WSZYSTKO)

    # ta sama osoba jako handlowiec i jako prowadząca — dokładnie przypadek Olszewskiej.
    # T4 jedzie tu jako DRUKARZ na zajęcia T1 — to druga połowa zgłoszenia:
    # wpis ląduje w wierszu T1 i bez podpisu wygląda na pomyłkę filtra.
    T4 = rozlaczne(trenerzy, [H1, H2, T1, T2, T3], 1)[0]
    frag_drukarz = A.f_bez_prefiksu(T4)
    kod, d = post("/api/lead", {"nazwa": "SP Delta", "miejscowosc": M1,
                                "typ": None, "handlowiec": H1})
    post("/api/event", {"lead_id": d["id"], "typ": "DT", "data": DATA,
                        "godz_od": "13:00", "godz_do": "15:00",
                        "trener": T1, "drukarz": T4})
    sprawdz("dwie role tej samej osoby się nie mieszają: „nazwisko” daje tylko zajęcia",
            kal("n:" + frag_t1) == (2, 2, 2), str(kal("n:" + frag_t1)))
    sprawdz("…a „wszystko” daje też szkoły, które sprzedała",
            kal("w:" + frag_h1) == (3, 3, 3), str(kal("w:" + frag_h1)))

    # Od 30.08 kalendarz ma OSOBNY zakres „H" (pkt 3 Kasi: „filtr w kalendarzu
    # po PH — nie ma takiej możliwości"). „H" pyta „czyja to szkoła" i nie rusza
    # poprawki z Olszewską: „n" dalej nie zagląda w pole handlowca.
    print("\nG2c — chip „H handlowiec” na kalendarzu (30.08)")

    def kal_h(osoby, tryb="lub"):
        conn = db.get_conn()
        c = fl.parsuj(osoby, fl.ZAKRESY_KALENDARZ)
        wyn = tuple(b(conn, MIES, chipy=c, tryb=tryb)["n_events"]
                    for b in (cv.build_matrix, cv.build_agenda, cv.build_starty))
        conn.close()
        return wyn

    ch = fl.parsuj("h:" + frag_h1, fl.ZAKRESY_KALENDARZ)
    sprawdz("kalendarz zna zakres „h”", ch and ch[0]["zakres"] == "h", str(ch))
    sprawdz("chip „H” daje spotkania ze szkół sprzedanych przez handlowca",
            kal_h("h:" + frag_h1) == (3, 3, 3), str(kal_h("h:" + frag_h1)))
    sprawdz("chip „H” NIE łapie po prowadzącym",
            kal_h("h:" + frag_t2) == (0, 0, 0), str(kal_h("h:" + frag_t2)))
    sprawdz("ekran kalendarza przyjmuje chip „H”",
            KL.get("/kalendarz?m=%s&osoby=h%%3A%s" % (MIES, frag_h1)).status_code == 200)
    sprawdz("dostępność „h” nie dostaje — chip spada do „wszystko”, wpis zostaje",
            fl.parsuj("h:Iks", fl.ZAKRESY_GRAFIK)[0]["zakres"] == "w")

    def role(osoby):
        conn = db.get_conn()
        evs = cv.build_agenda(conn, MIES,
                              chipy=fl.parsuj(osoby, fl.ZAKRESY_GRAFIK))["dni"]
        conn.close()
        return sorted(e.get("_rola") or "" for d in evs for e in d["eventy"])

    sprawdz("trafienie przez prowadzącego NIE dostaje etykiety roli",
            role("n:" + frag_t1) == ["", ""], str(role("n:" + frag_t1)))
    sprawdz("trafienie przez zastępstwo dostaje etykietę „zastępstwo”",
            role("n:" + frag_t3) == ["zastępstwo"], str(role("n:" + frag_t3)))
    # Agenda, nie macierz: wpis z samym zastępstwem nie ma `trener`, więc w siatce
    # trener × dzień nie ma dla niego wiersza (tak działa od początku).
    sprawdz("etykieta roli dojeżdża do szablonu",
            KL.get("/kalendarz?m=%s&widok=agenda&osoby=n%%3A%s" % (MIES, frag_t3))
            .get_data(as_text=True).count("tag-rola") == 1)
    sprawdz("w macierzy etykieta wisi na spotkaniu prowadzonym przez kogo innego",
            KL.get("/kalendarz?m=%s&osoby=n%%3A%s" % (MIES, frag_drukarz))
            .get_data(as_text=True).count("tag-rola") == 1)

    print("\nG3 — dostępność")

    def av(osoby, tryb="lub"):
        conn = db.get_conn()
        g = dv.build_dostepnosc(conn, MIES,
                                chipy=fl.parsuj(osoby, fl.ZAKRESY_GRAFIK), tryb=tryb)
        conn.close()
        return g

    g = av("")
    sprawdz("bez filtra siatka pokazuje wszystkich trenerów",
            g["n_trenerow"] == g["n_trenerow_all"] == len(trenerzy),
            "%d / %d" % (g["n_trenerow"], g["n_trenerow_all"]))
    g = av("n:" + frag_t2)
    sprawdz("filtr po nazwisku zostawia jeden wiersz", g["n_trenerow"] == 1,
            str(g["n_trenerow"]))
    sprawdz("wiersz jest ten właściwy", g["trenerzy"] == [T2], str(g["trenerzy"]))
    g = av("w:Alfa")
    sprawdz("filtr ogólny zostawia trenerów jeżdżących do tej szkoły",
            g["trenerzy"] == [T1], str(g["trenerzy"]))
    sprawdz("licznik trenerów mówi „ilu z ilu”",
            g["n_trenerow"] == 1 and g["n_trenerow_all"] == len(trenerzy))
    sprawdz("siatka nie robi się poszarpana — wiersz jest w każdym tygodniu",
            len({len(t["wiersze"]) for t in g["tygodnie"]}) == 1,
            str([len(t["wiersze"]) for t in g["tygodnie"]]))
    sprawdz("brak trafień = pusta siatka, nie błąd", av("xyzzy")["n_trenerow"] == 0)

    print("\nG4 — ekrany grafiku")
    for u, ile in [("/kalendarz?m=%s&osoby=Alfa" % MIES, 1),
                   ("/kalendarz?m=%s&osoby=n%%3A%s&widok=agenda" % (MIES, frag_t2), 1),
                   ("/kalendarz?m=%s&osoby=%%23w%%3AAlfa%%7C-n%%3AX&widok=starty" % MIES, 2),
                   ("/dostepnosc?m=%s&osoby=n%%3A%s" % (MIES, frag_t2), 1)]:
        r = KL.get(u)
        html_g = r.get_data(as_text=True)
        sprawdz("200 + %d chip(ów): %s" % (ile, u.split("?")[0]),
                r.status_code == 200 and html_g.count('data-akcja="usun"') == ile,
                "%s / %d" % (r.status_code, html_g.count('data-akcja="usun"')))
    r = KL.get("/kalendarz?m=%s&trener=%s" % (MIES, T2))
    html_g = r.get_data(as_text=True)
    sprawdz("stary link „?trener=” wjeżdża jako chip nazwiska",
            r.status_code == 200 and 'value="n:%s"' % T2 in html_g)
    sprawdz("listy „— wszyscy trenerzy —” już nie ma",
            "wszyscy trenerzy" not in html_g)
    # przełączenie Macierz/Agenda/Starty nie może gubić wpisanego filtra
    linki = re.findall(r'class="seg-opt[^"]*"\s+href="([^"]*)"',
                       KL.get("/kalendarz?m=%s&osoby=n%%3A%s" % (MIES, frag_t2))
                       .get_data(as_text=True))
    sprawdz("przełącznik widoku niesie filtr",
            len(linki) == 3 and all("osoby=n:" in x for x in linki),
            "%d linków: %s" % (len(linki), linki[:1]))
    czysc = re.findall(r'href="([^"]*)"[^>]*>Wyczyść<',
                       KL.get("/kalendarz?m=%s&osoby=%%23n%%3A%s%%7CAlfa" % (MIES, frag_t2))
                       .get_data(as_text=True))
    sprawdz("„Wyczyść” na kalendarzu zostawia wpis przypięty, kasuje resztę",
            len(czysc) == 1 and "osoby=%23n:" in czysc[0] and "Alfa" not in czysc[0],
            str(czysc))

    print("\nO7 — „wypełnij” odróżnia się od filtra")
    css = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "static", "style.css"), encoding="utf-8").read()
    sprawdz("komórka „wypełnij” ma własne, ciepłe tło",
            ".lead-cell{" in css.replace("\n", "") and "--fill:" in css)
    sprawdz("pasek filtrów ma własne, zimne tło", "--filtr:" in css
            and "background:var(--filtr)" in css)
    sprawdz("legenda nazywa oba języki pola",
            "sq-filtr" in html and "sq-fill" in html)

    # Blok NA KOŃCU celowo: dokłada placówkę i spotkanie, a wcześniejsze
    # sprawdzenia liczą wystąpienia. Wstawiony w środku psuł test etykiet roli
    # („trafienie przez prowadzącego” dostawało trzy wpisy zamiast dwóch) —
    # czyli test przechodził albo padał zależnie od kolejności, a to już raz
    # kosztowało nas fałszywie zielone R4 w test_obszary.
    print("\nO8 — chip „M miasto” na kalendarzu (pkt 4 Kasi, 31.08)")
    ch = fl.parsuj("m:Cokolwiek", fl.ZAKRESY_KALENDARZ)
    sprawdz("kalendarz zna zakres „m”", ch and ch[0]["zakres"] == "m", str(ch))
    sprawdz("zakres ma etykietę i opis w słowniku zakresów",
            fl.ZAKRESY["m"][1] == "miasto" and "miejscowość" in fl.ZAKRESY["m"][2])
    sprawdz("dostępność „m” nie dostaje — chip spada do „wszystko”, wpis zostaje",
            fl.parsuj("m:Iks", fl.ZAKRESY_GRAFIK)[0]["zakres"] == "w")

    conn = db.get_conn()
    M2 = next((m for m in db.slownik_values(conn, "miasto") if m != M1), None)
    conn.close()
    if not M2:
        sprawdz("słownik miast ma co najmniej dwie pozycje", False,
                "bez drugiego miasta filtr po mieście nie ma czego rozróżnić")
    else:
        # Placówka w DRUGIM mieście — bez niej filtr po mieście nic nie dowodzi,
        # bo wszystkie dotychczasowe rekordy siedzą w tym samym.
        kod, d = post("/api/lead", {"nazwa": "SP Epsilon", "miejscowosc": M2,
                                    "typ": None, "handlowiec": H2})
        sprawdz("dane testowe: placówka w drugim mieście", kod == 200 and d.get("ok"))
        post("/api/event", {"lead_id": d["id"], "typ": "DT", "data": DATA,
                            "godz_od": "09:00", "godz_do": "11:00", "trener": T1})

        def kal_m(osoby):
            conn = db.get_conn()
            c = fl.parsuj(osoby, fl.ZAKRESY_KALENDARZ)
            wyn = tuple(b(conn, MIES, chipy=c)["n_events"]
                        for b in (cv.build_matrix, cv.build_agenda, cv.build_starty))
            conn.close()
            return wyn

        frag_m2 = A.f_bez_prefiksu(M2)
        sprawdz("chip „M” zawęża do jednego miasta",
                kal_m("m:" + frag_m2) == (1, 1, 1), str(kal_m("m:" + frag_m2)))
        sprawdz("i zostawia resztę w mieście sąsiednim",
                kal_m("m:" + A.f_bez_prefiksu(M1))[1] >= 4,
                str(kal_m("m:" + A.f_bez_prefiksu(M1))))
        # SEDNO osobnego zakresu: „wszystko” trafia też w NAZWĘ szkoły i w uwagi,
        # więc szukanie tam miasta oddaje rekordy, których w tym mieście nie ma.
        # Dlatego to nie jest to samo pytanie i dlatego „M” musi istnieć osobno.
        sprawdz("chip „M” NIE trafia w nazwę placówki",
                kal_m("m:Epsilon") == (0, 0, 0), str(kal_m("m:Epsilon")))
        sprawdz("…a „wszystko” trafia — stąd potrzeba osobnego zakresu",
                kal_m("w:Epsilon")[1] >= 1, str(kal_m("w:Epsilon")))
        sprawdz("ekran kalendarza przyjmuje chip „M”",
                KL.get("/kalendarz?m=%s&osoby=m%%3A%s" % (MIES, frag_m2)).status_code == 200)

    ok = sum(1 for _, w, _ in WYNIKI if w)
    print("\n== %d/%d sprawdzeń OK ==" % (ok, len(WYNIKI)))
    return 0 if ok == len(WYNIKI) else 1


if __name__ == "__main__":
    sys.exit(main())
