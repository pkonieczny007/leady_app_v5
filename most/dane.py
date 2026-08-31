# -*- coding: utf-8 -*-
"""
Budowa migawki dla aplikacji partnerskiej (Akademia Silesia3D).

CO TU JEST DECYZJĄ, A NIE ZAPISEM

1. NAZWY PÓL SĄ ICH, NIE NASZE. `school`, `weekday`, `start_time`, `starts_on` —
   tak nazywają się kolumny w tabeli, do której te dane mają trafić. Gdybyśmy
   wysłali `placowka`, `cykl_dzien`, `godz_od`, po drugiej stronie ktoś musiałby
   napisać tłumacza i utrzymywać go w nieskończoność. Tak import jest
   przepisaniem pola w pole, a rozbieżność widać gołym okiem.

2. WYSYŁAMY POLICZONE DATY, NIE REGUŁĘ. Cykl u nas bywa listą konkretnych dat
   (`terminy_cyklu` wygrywa nad regułą „co N tygodni") i miewa wyjątki
   (`wyjatki_cyklu` — odwołany albo przesunięty pojedynczy termin). Wysłanie
   samego „co wtorek od 2 października" zgubiłoby jedno i drugie, a odbiorca
   liczyłby wystąpienia własnym kodem — czyli po pół roku firma miałaby dwa
   różne kalendarze tych samych zajęć. Liczymy `calendar_view`, tym samym
   kodem, co nasz własny kalendarz.

3. ODWOŁANE TEŻ WYSYŁAMY. Zajęcia zdjęte z grafiku muszą dojechać do odbiorcy,
   inaczej zostaną u niego na zawsze jako duch — a on nie ma skąd wiedzieć, że
   ich już nie ma. Odwołany cykl jedzie ze `stan: "odwolany"`, odwołany
   pojedynczy termin siedzi w `cancelled_occurrences`.

4. TRENERA PODAJEMY NAZWISKIEM, NIE IDENTYFIKATOREM. Nie mamy ich identyfikatorów
   i nie chcemy ich mieć — to byłaby druga baza ludzi do utrzymania. Przypisanie
   obsady i tak należy do nich („on sobie przyporządkuje resztę").

5. DANE KONTAKTOWE NIE WYCHODZĄ. Telefon, mail, osoba kontaktowa i notatki
   handlowca zostają u nas. Most przekracza granicę zespołu handlowego, a pytanie
   „czy w pliku mają być telefony do szkół" postawione w sierpniu nie doczekało
   się odpowiedzi. Brak odpowiedzi znaczy „nie wysyłamy" — dane raz wysłane
   wracają tylko w teorii. Pilnuje tego test szukający po WARTOŚCIACH, nie po
   nazwach pól, więc samo przemianowanie kolumny go nie oszuka.
"""
import datetime as dt
import hashlib
import json
import sqlite3

import calendar_view as cv
import db

WERSJA_FORMATU = "leady_app_v5 most v1"

# Prefiks klucza zewnętrznego. Odbiorca potrzebuje czegoś stabilnego, po czym
# rozpozna, że to TEN SAM cykl co poprzednio — inaczej każdy import mnoży wiersze.
# Nazwa aplikacji w kluczu, bo w ich bazie mogą kiedyś stanąć dwa źródła.
PREFIKS_ID = "leady-v5"

# Notatki NIE wychodzą. To pole wolnego tekstu, a w wolnym tekście lądują
# nazwiska dyrektorek, numery telefonów i ustalenia handlowe — czyli dokładnie
# to, czego most nie ma wynosić. Gdyby klient świadomie zdecydował inaczej,
# to jest jedno miejsce do przestawienia (i jeden test do poprawienia).
WYSYLAJ_UWAGI = False

# Jak nazywamy ich typy zajęć. Ich formularz domyślnie proponuje „Projektowanie 3D";
# my mówimy, co to jest u nas, żeby dało się jedno z drugim zestawić.
TYTULY = {
    "CYKLICZNE": "Zajęcia cykliczne",
    "CYKLICZNE-PRZEDSZKOLE": "Zajęcia cykliczne — przedszkole",
    "DT": "Dzień technologiczny",
    "START": "Start grupy",
}

_SQL_BAZA = """
SELECT e.id, e.lead_id, e.typ, e.data, e.godz_od, e.godz_do,
       e.trener, e.trener2, e.zastepstwo, e.drukarz,
       e.numer_sali, e.grupa, e.sprzet, e.ilosc_klas, e.ilosc_dzieci,
       e.cykl_dzien, e.co_ile_tygodni, e.kod_tinkercad, e.link_tinkercad,
       e.uwagi, e.odwolane, e.powod_odwolania, e.odwolal, e.updated_at,
       l.handlowiec, l.status_realizacji,
       p.nazwa AS placowka, p.miejscowosc, p.adres, p.typ AS typ_placowki, p.rspo
       {geo}
FROM eventy e
JOIN leady l ON l.id = e.lead_id
JOIN placowki p ON p.id = l.placowka_id
WHERE e.data IS NOT NULL AND e.data <> ''
ORDER BY e.data, e.id
"""


def _wiersze(conn):
    """
    Bazowe wiersze eventów. Kolumny geograficzne dochodzą migracją, więc na bazie
    sprzed niej (choćby przywróconej kopii) zapytanie musi się wykonać bez nich —
    inaczej most wywraca się na starych danych zamiast wystawić plik bez powiatu.
    """
    try:
        return conn.execute(_SQL_BAZA.format(geo=", p.powiat, p.gmina")).fetchall()
    except sqlite3.OperationalError:
        return conn.execute(_SQL_BAZA.format(geo="")).fetchall()


def _pole(r, nazwa, domyslnie=None):
    return r[nazwa] if nazwa in r.keys() else domyslnie


def _tekst(v):
    s = "" if v is None else str(v).strip()
    return s or None


def _godzina(v):
    """„14:00:00" i „14:00" sprowadzone do „HH:MM" — po drugiej stronie pole jest `time`."""
    s = _tekst(v)
    return s[:5] if s else None


def _data(v):
    """Obcięcie do 10 znaków: w bazie potrafi siedzieć pełny znacznik czasu."""
    s = _tekst(v)
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        return None


def wystapienia(conn):
    """
    {event_id: (żywe daty, odwołane terminy)} — policzone kalendarzem, nie regułą.

    Przelatujemy wszystkie miesiące dwa razy: raz po grafik żywy, raz po odwołane
    terminy. To jest droższe niż jedno zapytanie, ale liczy DOKŁADNIE to samo,
    co widzi koordynator na ekranie — a rozjazd między tym, co widzi klient,
    a tym, co wysyłamy partnerowi, byłby najgorszym możliwym rodzajem błędu:
    niewidocznym dla obu stron do pierwszej awantury o nieodbyte zajęcia.
    """
    zywe, odwolane = {}, {}
    for m in cv.available_months(conn):
        for e in cv.events_for_month(conn, m):
            zywe.setdefault(e["id"], set()).add(e["data"])
        for e in cv.events_for_month(conn, m, odwolane=True):
            # `odwolane` (bez „i") to odwołanie POJEDYNCZEGO wystąpienia z
            # `wyjatki_cyklu`. Odwołanie całego spotkania siedzi w `odwolanie`
            # i obsługujemy je wyżej, na poziomie rekordu — te dwie nazwy mylą
            # się do siebie i raz już zjadły znacznik na kaflu kalendarza.
            if not e.get("odwolane"):
                continue
            slad = e.get("odwolanie_terminu") or {}
            odwolane.setdefault(e["id"], {})[e["data"]] = {
                "date": e["data"],
                "reason": _tekst(slad.get("powod")),
                "cancelled_at": _tekst(slad.get("kiedy")),
            }
    return zywe, odwolane


def cykle_z_lista(conn):
    """
    Identyfikatory cykli, które mają UZGODNIONĄ listę dat, a nie samą regułę.

    Rozróżnienie jest ważne dla odbiorcy, nie dla nas: cykl z listy ma prawdziwy
    koniec (ostatnie zajęcia z pakietu), a cykl z reguły ciągnie się bezterminowo
    i jego „ostatnia data" to wyłącznie nasz horyzont liczenia. Wysłanie horyzontu
    jako `ends_on` powiedziałoby, że zajęcia się wtedy kończą — a one się nie kończą,
    tylko przestaliśmy je liczyć.
    """
    try:
        rows = conn.execute("SELECT DISTINCT event_id FROM terminy_cyklu").fetchall()
    except sqlite3.OperationalError:
        return set()
    return {r["event_id"] for r in rows}


def _wspolne(r):
    """Pola opisujące MIEJSCE i obsadę — te same dla cyklu i dla DT."""
    return {
        "school": _tekst(r["placowka"]),
        "address": _tekst(r["adres"]),
        "city": _tekst(r["miejscowosc"]),
        # `region` po ich stronie służy dobieraniu zastępstw i porównuje się go
        # z rejonem trenera. Powiat jest u nas osią filtrowania od migracji na
        # rejestr RSPO; miejscowość zostaje awaryjnie, bo kilkanaście rekordów
        # powiatu nie ma i pusty region byłby tam gorszy niż przybliżony.
        "region": _tekst(_pole(r, "powiat")) or _tekst(r["miejscowosc"]),
        "county": _tekst(_pole(r, "powiat")),
        "commune": _tekst(_pole(r, "gmina")),
        "school_type": _tekst(r["typ_placowki"]),
        "rspo": _tekst(r["rspo"]),
        "trainer_name": _tekst(r["trener"]),
        "second_trainer_name": _tekst(r["trener2"]),
        "printer_name": _tekst(r["drukarz"]),
        "room": _tekst(r["numer_sali"]),
        "equipment": _tekst(r["sprzet"]),
        "classes": r["ilosc_klas"],
        "children": r["ilosc_dzieci"],
        "salesperson": _tekst(r["handlowiec"]),
        "updated_at": _tekst(r["updated_at"]),
    }


def _braki(rec, wymagane):
    """
    Czego brakuje, żeby odbiorca mógł ten rekord w ogóle wstawić.

    Ich formularz ma pola wymagane (trener, godziny, data początku), a nasza
    aplikacja świadomie NIE blokuje zapisu przy brakach — od poprawek z sierpnia
    handlowiec zapisuje to, co ustalił, a brak jest WIDOCZNY, nie zakazany.
    Te dwie zasady spotykają się tutaj: wysyłamy rekord razem z listą braków,
    żeby odbiorca odłożył go na bok, zamiast wywalić się na `NOT NULL` albo —
    gorzej — wstawić wiersz z podstawionymi wartościami.
    """
    return [k for k in wymagane if not rec.get(k)]


def zbuduj_cykl(r, daty_zywe, daty_odwolane, ma_liste=False):
    typ = r["typ"]
    daty = sorted(daty_zywe)
    odwolane_terminy = [daty_odwolane[d] for d in sorted(daty_odwolane)]
    calosc_odwolana = bool(_tekst(r["odwolane"]))

    pierwsza = daty[0] if daty else _data(r["data"])
    # `ends_on` TYLKO dla pakietu z uzgodnioną listą dat. Cykl z reguły nie ma
    # daty końca — ostatnia policzona data to nasz horyzont (`CYKL_HORYZONT_TYGODNI`),
    # czyli miejsce, w którym przestaliśmy liczyć. Podanie go jako końca zajęć
    # byłoby po prostu nieprawdą, a odbiorca nie miałby jak jej wykryć.
    ostatnia = (daty[-1] if daty else None) if ma_liste else None

    rec = {
        "id": "%s:event:%d" % (PREFIKS_ID, r["id"]),
        "source_event_id": r["id"],
        "kind": "recurring",
        "stan": "odwolany" if calosc_odwolana else "aktywny",
        "title": TYTULY.get(typ, typ),
        "source_type": typ,
        "group": _tekst(r["grupa"]),
        "weekday": None,
        "start_time": _godzina(r["godz_od"]),
        "end_time": _godzina(r["godz_do"]),
        "starts_on": pierwsza,
        "ends_on": ostatnia,
        "every_n_weeks": int(r["co_ile_tygodni"] or 1),
        # Czy `occurrences` to uzgodnione terminy, czy nasze wyliczenie z reguły.
        # Odbiorca musi umieć je odróżnić: pierwsze są ustaleniem ze szkołą,
        # drugie kończą się na horyzoncie i przy kolejnej migawce będą dłuższe.
        "occurrences_agreed": bool(ma_liste),
        "occurrences_horizon_weeks": None if ma_liste else cv.CYKL_HORYZONT_TYGODNI,
        "occurrences": daty,
        "cancelled_occurrences": odwolane_terminy,
        "tinkercad_code": _tekst(r["kod_tinkercad"]),
        "tinkercad_link": _tekst(r["link_tinkercad"]),
    }
    rec.update(_wspolne(r))
    if calosc_odwolana:
        rec["cancelled_reason"] = _tekst(r["powod_odwolania"])
    if WYSYLAJ_UWAGI:
        rec["notes"] = _tekst(r["uwagi"])

    # Dzień tygodnia liczymy z PIERWSZEGO REALNEGO wystąpienia, nie ze słownikowego
    # `cykl_dzien` — ten bywa pusty albo rozjechany z datą, a po ich stronie jest
    # to pole wymagane i steruje dobieraniem zastępstw. Ich tydzień zaczyna się
    # od 1 = poniedziałek, czyli dokładnie tak, jak liczy `isoweekday()`.
    if pierwsza:
        rec["weekday"] = dt.date.fromisoformat(pierwsza).isoweekday()

    rec["missing"] = _braki(rec, ("school", "region", "weekday",
                                  "start_time", "end_time", "starts_on"))
    return rec


def zbuduj_dt(r, odwolany_termin=None):
    data = _data(r["data"])
    godz_od = _godzina(r["godz_od"])
    godz_do = _godzina(r["godz_do"])
    calosc_odwolana = bool(_tekst(r["odwolane"]))

    rec = {
        "id": "%s:event:%d" % (PREFIKS_ID, r["id"]),
        "source_event_id": r["id"],
        "kind": "one_off",
        "activity_type": "school_visit",
        "stan": "odwolany" if calosc_odwolana else "aktywny",
        "status": "cancelled" if calosc_odwolana else "planned",
        "title": "%s — %s" % (TYTULY.get(r["typ"], r["typ"]), _tekst(r["placowka"]) or "?"),
        "source_type": r["typ"],
        "date": data,
        "start_time": godz_od,
        "end_time": godz_do,
        # Czas LOKALNY, bez przesunięcia strefy — świadomie. Ich formularz zbiera
        # `datetime-local` i sam dokleja strefę przeglądarki, więc naiwny znacznik
        # jest tym, czego oczekuje. Doklejenie „+02:00" po naszej stronie
        # wymagałoby bazy stref w obrazie dockera (`python:3.13-slim` jej nie ma)
        # i przy zmianie czasu przesunęłoby zajęcia o godzinę.
        "starts_at": ("%sT%s:00" % (data, godz_od)) if (data and godz_od) else None,
        "ends_at": ("%sT%s:00" % (data, godz_do)) if (data and godz_do) else None,
    }
    rec.update(_wspolne(r))
    if calosc_odwolana:
        rec["cancelled_reason"] = _tekst(r["powod_odwolania"])
    if odwolany_termin:
        rec["status"] = "cancelled"
        rec["cancelled_reason"] = odwolany_termin.get("reason")
    if WYSYLAJ_UWAGI:
        rec["notes"] = _tekst(r["uwagi"])

    rec["missing"] = _braki(rec, ("school", "region", "date", "start_time"))
    return rec


def zbuduj(conn, teraz=None):
    """Pełna migawka. Zwraca gotowy słownik do zapisania jako `zajecia.json`."""
    teraz = teraz or dt.datetime.now()
    zywe, odwolane = wystapienia(conn)
    z_lista = cykle_z_lista(conn)

    cykle, dt_lista = [], []
    for r in _wiersze(conn):
        if r["typ"] in db.TYPY_CYKLICZNE:
            cykle.append(zbuduj_cykl(r, zywe.get(r["id"], set()),
                                     odwolane.get(r["id"], {}),
                                     ma_liste=r["id"] in z_lista))
        elif r["typ"] == "DT":
            # DT nie ma wystąpień, ale może mieć odwołany termin — wtedy w słowniku
            # odwołanych siedzi jeden wpis na jego własną datę.
            odw = (odwolane.get(r["id"]) or {}).get(_data(r["data"]))
            dt_lista.append(zbuduj_dt(r, odw))
        # START i inne typy zostają u nas: po ich stronie nie ma dla nich miejsca,
        # a wysyłanie „na zapas" zamienia most w drugi eksport wszystkiego.

    profil = db.opis_profilu()
    return {
        "format": WERSJA_FORMATU,
        "wygenerowano": teraz.isoformat(timespec="seconds"),
        "profil": profil["klucz"],
        "profil_etykieta": profil["etykieta"],
        "strefa": "Europe/Warsaw (czas lokalny, znaczniki bez przesunięcia)",
        "liczby": {
            "cykle": len(cykle),
            "cykle_aktywne": sum(1 for c in cykle if c["stan"] == "aktywny"),
            "dt": len(dt_lista),
            "dt_aktywne": sum(1 for d in dt_lista if d["stan"] == "aktywny"),
            "niekompletne": sum(1 for x in cykle + dt_lista if x["missing"]),
        },
        "cykle": cykle,
        "dt": dt_lista,
    }


# ------------------------------------------------------------------ różnice

def skroty(migawka):
    """
    {id rekordu: skrót treści} — po tym poznajemy, co się zmieniło między migawkami.

    Liczymy różnicę porównując migawki, a nie podpinając się pod każdy endpoint
    zapisu. Powód jest ten sam, dla którego znacznik „brudne" siedzi w jednym
    miejscu: endpointów piszących po eventach jest osiem i dziewiąty powstanie
    bez przypomnienia. Porównanie migawek nie ma jak przeoczyć zmiany, bo patrzy
    na wynik, a nie na drogę do niego.
    """
    out = {}
    for rec in migawka["cykle"] + migawka["dt"]:
        tresc = json.dumps(rec, ensure_ascii=False, sort_keys=True)
        out[rec["id"]] = hashlib.sha1(tresc.encode("utf-8")).hexdigest()[:16]
    return out


def roznice(stare, nowe, migawka, teraz=None):
    """Lista wpisów do dziennika: co doszło, co się zmieniło, co zniknęło."""
    teraz = (teraz or dt.datetime.now()).isoformat(timespec="seconds")
    po_id = {r["id"]: r for r in migawka["cykle"] + migawka["dt"]}
    out = []

    for rid, skrot in sorted(nowe.items()):
        rec = po_id[rid]
        if rid not in stare:
            co = "dodane"
        elif stare[rid] != skrot:
            co = "zmienione"
        else:
            continue
        out.append({"kiedy": teraz, "co": co, "id": rid, "kind": rec["kind"],
                    "school": rec.get("school"), "stan": rec.get("stan")})

    for rid in sorted(set(stare) - set(nowe)):
        # Rekord zniknął z migawki: skasowany u nas albo przestał spełniać warunki
        # (np. stracił datę). Odbiorca ma go u siebie WYŁĄCZYĆ, nie skasować —
        # przy jego zajęciach mogą już wisieć zastępstwa i wpisy rozliczeniowe.
        out.append({"kiedy": teraz, "co": "zniknelo", "id": rid})

    return out
