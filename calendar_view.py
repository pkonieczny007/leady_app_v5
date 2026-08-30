# -*- coding: utf-8 -*-
"""
Kalendarze jako WIDOKI z tabeli `eventy` — nigdy jako ręcznie malowana plansza.

Trzy widoki tych samych danych (nazwy zgodne z design handoffem):

  MACIERZ  trener × dzień, bloki tygodniowe jak w arkuszu klienta.
           W komórce jest LISTA eventów, nie jeden — i tu znika zgłoszony bug.
  AGENDA   dzień po dniu, spotkania posortowane po godzinie. Czytelne przy dużym
           wolumenie cyklicznych (w realnych danych ~30 zajęć dziennie).
  STARTY   plansza całej firmy w kartach — odwzorowanie zakładki „STARTY CZERWIEC".

DLACZEGO TO NAPRAWIA ICH BUG
W arkuszu komórka kalendarza to `XLOOKUP(data||trener, ...)`, a XLOOKUP zwraca
PIERWSZE trafienie — drugie i trzecie DT tego samego trenera w tym samym dniu
było niewidoczne. Tutaj komórka to lista rekordów spod klucza (trener, data),
więc wszystkie są widoczne bez żadnej sztuczki. Dodatkowo, ponieważ godziny są
osobnymi polami czasu (a nie tekstem „08:00-12:30"), umiemy wykryć KOLIZJĘ.

Zajęcia cykliczne trzymamy jako JEDEN rekord z regułą (dzień tygodnia + godziny,
data = pierwsze zajęcia), a wystąpienia rozwijamy dopiero na potrzeby widoku
danego miesiąca. Dzięki temu przesunięcie godziny cyklu to jedna edycja,
a nie poprawianie kilkudziesięciu wierszy.
"""
import calendar as _cal
import datetime as dt
import re

from db import (trener_colors, slownik_values,
                TYPY_CYKLICZNE, SQL_TYPY_CYKLICZNE)
from filtry import filtruj_eventy

DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
DNI_SKR = ["pon", "wt", "śr", "czw", "pt", "sob", "niedz"]
MIESIACE = ["", "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec",
            "sierpień", "wrzesień", "październik", "listopad", "grudzień"]
MIESIACE_D = ["", "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
              "sierpnia", "września", "października", "listopada", "grudnia"]

# ile tygodni w przód rozwijać cykl, gdy nie znamy daty końcowej
CYKL_HORYZONT_TYGODNI = 40


# ------------------------------------------------------------------ pomocnicze

def month_label(month):
    y, m = month.split("-")
    return "%s %s" % (MIESIACE[int(m)].capitalize(), y)


def _mins(hhmm):
    """
    '08:55' -> 535. None/śmieci -> None.

    Odporne na to, co realnie siedzi w ich danych: '8.00', '08:55:00',
    a przede wszystkim na PÓŁPAUZĘ w zakresie ('12:25–13:25'). Gdyby taki tekst
    trafił do pola godziny, naiwne parsowanie zwróciłoby None i detekcja kolizji
    wyłączyłaby się po cichu — a to najgorszy rodzaj błędu w tym projekcie.
    """
    if hhmm is None or hhmm == "":
        return None
    s = str(hhmm).strip().replace("–", "-").replace("—", "-")
    s = s.replace(".", ":")
    m = re.search(r"([01]?\d|2[0-3])\s*:\s*([0-5]\d)", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.fullmatch(r"([01]?\d|2[0-3])", s)   # sama godzina, np. '8'
    if m:
        return int(m.group(1)) * 60
    return None


def overlaps(od1, do1, od2, do2):
    """
    Czy dwa przedziały czasu nakładają się.
    Gdy brak godziny końca, przyjmujemy 60 minut — inaczej wpis bez „do" nigdy
    nie kolidowałby, a to jest najczęstszy przypadek w ich danych.
    """
    a1, a2 = _mins(od1), _mins(do1)
    b1, b2 = _mins(od2), _mins(do2)
    if a1 is None or b1 is None:
        return False
    if a2 is None or a2 <= a1:
        a2 = a1 + 60
    if b2 is None or b2 <= b1:
        b2 = b1 + 60
    return a1 < b2 and b1 < a2


def _ile_kolizji(evs, kolizje):
    """
    Ile kolizji WIDAĆ. Wykrywamy je na pełnym komplecie (żeby filtr nie ukrył
    drugiej strony nakładki), ale w nagłówku liczymy tylko to, co zostało po
    filtrze — inaczej „31 spotkań · 12 w kolizji" wskazywałoby na spotkania,
    których na ekranie nie ma.
    """
    return sum(1 for e in evs if e["_key"] in kolizje)


def find_collisions(evs):
    """Zbiór id eventów, które kolidują: ten sam trener, ten sam dzień, zachodzące godziny."""
    kolidujace = set()
    grupy = {}
    for e in evs:
        if not e.get("trener") or not e.get("data"):
            continue
        grupy.setdefault((e["trener"], e["data"]), []).append(e)
    for grupa in grupy.values():
        for i in range(len(grupa)):
            for j in range(i + 1, len(grupa)):
                a, b = grupa[i], grupa[j]
                if overlaps(a.get("godz_od"), a.get("godz_do"),
                            b.get("godz_od"), b.get("godz_do")):
                    kolidujace.add(a["_key"])
                    kolidujace.add(b["_key"])
    return kolidujace


# ------------------------------------------------------------------ pobranie eventów

_SQL_EVENTY = """
SELECT e.id, e.lead_id, e.typ, e.data, e.godz_od, e.godz_do,
       e.trener, e.trener2, e.zastepstwo, e.drukarz,
       e.numer_sali, e.grupa, e.sprzet, e.ilosc_klas, e.ilosc_dzieci,
       e.cykl_dzien, e.co_ile_tygodni, e.kod_tinkercad, e.link_tinkercad, e.uwagi,
       e.odwolane, e.powod_odwolania, e.odwolal,
       l.handlowiec, l.status_realizacji,
       p.nazwa AS placowka, p.miejscowosc, p.adres, p.typ AS typ_placowki
FROM eventy e
JOIN leady l ON l.id = e.lead_id
JOIN placowki p ON p.id = l.placowka_id
WHERE e.data IS NOT NULL AND e.data <> ''
"""

# Odwołane zajęcia zostają w bazie (są dowodem, że temat był), ale znikają
# z grafiku i nie zajmują trenerowi terminu — P08.
_ZYWE = "  AND (e.odwolane IS NULL OR e.odwolane = '')"
# P31 (prośba Pawła z 20.08: „musimy mieć listę odwołanych"). Do 20.08 odwołane
# spotkanie dało się zobaczyć WYŁĄCZNIE na karcie konkretnej szkoły — czyli
# trzeba było wiedzieć, której szukać. To odwraca warunek zamiast go zdejmować:
# lista wymieszana z grafikiem wyglądałaby jak zajęcia, które się odbędą.
_ODWOLANE = "  AND e.odwolane IS NOT NULL AND e.odwolane <> ''"

# tylko te typy się powtarzają; START to jednorazowa inauguracja grupy
TYPY_POWTARZALNE = TYPY_CYKLICZNE


def _row_to_event(r):
    e = {
        "id": r["id"], "lead_id": r["lead_id"], "typ": r["typ"] or "DT",
        "data": r["data"], "godz_od": r["godz_od"], "godz_do": r["godz_do"],
        "trener": r["trener"], "trener2": r["trener2"],
        "zastepstwo": r["zastepstwo"], "drukarz": r["drukarz"],
        "numer_sali": r["numer_sali"], "grupa": r["grupa"], "sprzet": r["sprzet"],
        "ilosc_klas": r["ilosc_klas"], "ilosc_dzieci": r["ilosc_dzieci"],
        "cykl_dzien": r["cykl_dzien"], "co_ile_tygodni": r["co_ile_tygodni"] or 1,
        "kod_tinkercad": r["kod_tinkercad"], "link_tinkercad": r["link_tinkercad"],
        "uwagi": r["uwagi"],
        "handlowiec": r["handlowiec"], "status_realizacji": r["status_realizacji"],
        "placowka": r["placowka"] or "?", "miejscowosc": r["miejscowosc"] or "",
        "adres": r["adres"] or "", "typ_placowki": r["typ_placowki"] or "",
    }
    # UWAGA na nazwę. `odwolane` jest w tym module ZAJĘTE: tak nazywa się flaga
    # odwołanego WYSTĄPIENIA cyklu z `wyjatki_cyklu`, którą `_naloz_wyjatek`
    # ustawia na False przy każdym wpisie bez wyjątku. Odwołanie całego spotkania
    # (P08) to co innego i musi mieć własną nazwę — inaczej jedno kasuje drugie
    # po cichu, co przy pierwszym podejściu zjadło znacznik na kaflu.
    e["odwolanie"] = ({"kiedy": r["odwolane"], "powod": r["powod_odwolania"],
                       "kto": r["odwolal"]} if r["odwolane"] else None)
    # Liczone RAZ, przy wczytaniu — wystąpienia cyklu powstają przez kopię tego
    # słownika, więc lista braków jedzie z nimi i nie trzeba jej liczyć w trzech
    # widokach osobno (a przy trzech miejscach jedno zawsze się rozjeżdża).
    e["braki"] = braki_dt(e)
    return e


def events_for_month(conn, month, typy=None, rozwijaj_cykle=True, odwolane=False):
    """
    Eventy widoczne w danym miesiącu ('YYYY-MM').

    DT           → bierzemy te, których `data` wpada w miesiąc.
    CYKLICZNE    → rekord ma datę PIERWSZYCH zajęć; wystąpienia w tym miesiącu
                   wyliczamy, powtarzając co 7 dni od tej daty (o ile miesiąc
                   nie jest wcześniejszy niż start cyklu).

    Każdy wpis dostaje `_key` — unikalny identyfikator WYSTĄPIENIA
    ('12' dla DT, '12@2026-10-07' dla konkretnego wystąpienia cyklu).
    Kolizje liczymy po `_key`, żeby dwa wystąpienia tego samego cyklu nie
    zgłaszały się jako kolizja same z sobą.
    """
    y, m = [int(x) for x in month.split("-")]
    pierwszy = dt.date(y, m, 1)
    ostatni = dt.date(y, m, _cal.monthrange(y, m)[1])

    wyjatki = _wyjatki(conn)
    terminy = _terminy(conn)
    rows = conn.execute(_SQL_EVENTY + (_ODWOLANE if odwolane else _ZYWE)).fetchall()
    out = []
    for r in rows:
        e = _row_to_event(r)
        if typy and e["typ"] not in typy:
            continue
        try:
            # Obcięcie do 10 znaków jest celowe. W bazie potrafi wylądować pełny
            # znacznik czasu („2026-09-22T00:00:00") — tak zapisywał daty pierwszych
            # zajęć importer, zanim to poprawiono. `date.fromisoformat` odrzuca taki
            # zapis, a `continue` niżej POMIJAŁO wpis bez śladu: zajęcia cykliczne
            # siedziały w bazie i nie pokazywały się w żadnym miesiącu. Kalendarz ma
            # być odporny na to, co już leży w danych, nie tylko na nowe importy.
            d0 = dt.date.fromisoformat(str(e["data"])[:10])
        except (ValueError, TypeError):
            continue

        if e["typ"] not in TYPY_POWTARZALNE or not rozwijaj_cykle:
            if pierwszy <= d0 <= ostatni:
                x = dict(e)
                x["_key"] = str(e["id"])
                x["_cykl_nr"] = None
                _naloz_wyjatek(x, wyjatki.get((e["id"], x["data"])))
                if not x.get("odwolane"):
                    out.append(x)
            continue

        # CYKL Z LISTĄ KONKRETNYCH DAT (przedszkola, pakiety „5 zajęć").
        # Reguła „co wtorek" tu nie obowiązuje: obowiązuje to, co uzgodniono.
        # Sprawdzamy to PRZED rozwinięciem reguły, bo event ma jedno i drugie —
        # `data` to nadal pierwszy termin, żeby wszystkie stare zapytania
        # (`WHERE e.data`, sortowania, statystyki) działały bez zmian.
        moje_terminy = terminy.get(e["id"])
        if moje_terminy:
            for t in moje_terminy:
                try:
                    d = dt.date.fromisoformat(str(t["data"])[:10])
                except (ValueError, TypeError):
                    continue
                if not (pierwszy <= d <= ostatni):
                    continue
                x = dict(e)
                x["data"] = d.isoformat()
                # Godzina z terminu wygrywa nad godziną reguły — w przedszkolu
                # jedne zajęcia bywają o innej porze niż reszta pakietu.
                if t["godz_od"]:
                    x["godz_od"] = t["godz_od"]
                if t["godz_do"]:
                    x["godz_do"] = t["godz_do"]
                x["_key"] = "%d@%s" % (e["id"], d.isoformat())
                x["_cykl_nr"] = t["nr"]
                x["_z_listy"] = True
                _naloz_wyjatek(x, wyjatki.get((e["id"], d.isoformat())))
                if not x.get("odwolane"):
                    out.append(x)
            continue

        # cykl: powtarzamy co `co_ile_tygodni` tygodni od daty pierwszych zajęć
        if d0 > ostatni:
            continue
        co_ile = max(1, int(e.get("co_ile_tygodni") or 1))
        delta = (pierwszy - d0).days
        krok = 0
        if delta > 0:
            krok = -(-delta // (7 * co_ile))          # sufit dzielenia
        nr = krok + 1
        while krok <= CYKL_HORYZONT_TYGODNI:
            d = d0 + dt.timedelta(days=7 * co_ile * krok)
            if d > ostatni:
                break
            if d >= pierwszy:
                x = dict(e)
                x["data"] = d.isoformat()
                x["_key"] = "%d@%s" % (e["id"], d.isoformat())
                x["_cykl_nr"] = nr
                _naloz_wyjatek(x, wyjatki.get((e["id"], d.isoformat())))
                if not x.get("odwolane"):
                    out.append(x)
            krok += 1
            nr += 1

    out.sort(key=lambda e: (e["data"], e["godz_od"] or "99:99", e["trener"] or ""))
    return out


def _terminy(conn):
    """
    {event_id: [wiersze terminów po dacie]} — pakiety zajęć umówione na konkretne
    daty zamiast na regułę „co wtorek".

    Ładujemy WSZYSTKIE naraz, nie po jednym zapytaniu na event: kalendarz
    przelicza się przy każdym otwarciu, a przy ~30 zajęciach dziennie zapytanie
    w pętli po eventach to setki zapytań na jeden ekran.

    `try` wokół zapytania jest z tego samego powodu co przy `wyjatki_cyklu`:
    tabela dochodzi w tej wersji, a kalendarz ma otworzyć się także na bazie
    sprzed aktualizacji (choćby na przywróconej kopii).
    """
    try:
        rows = conn.execute(
            "SELECT event_id, nr, data, godz_od, godz_do FROM terminy_cyklu "
            "ORDER BY event_id, data").fetchall()
    except Exception:
        return {}
    out = {}
    for r in rows:
        out.setdefault(r["event_id"], []).append(dict(r))
    return out


def _wyjatki(conn):
    """{(event_id, data): wiersz} — wyjątki od reguły cyklu na konkretną datę."""
    try:
        rows = conn.execute("SELECT * FROM wyjatki_cyklu").fetchall()
    except Exception:
        return {}
    return {(r["event_id"], r["data"]): dict(r) for r in rows}


def _naloz_wyjatek(ev, w):
    """
    Nadpisuje wystąpienie danymi wyjątku: odwołanie, zastępstwo, zmiana trenera
    lub godzin. Tak klient realnie pracuje — reguła plus poprawka na jedną datę.
    """
    if not w:
        ev["odwolane"] = False
        ev["wyjatek"] = None
        return
    ev["wyjatek"] = w.get("uwagi") or "wyjątek na tę datę"
    ev["odwolane"] = bool(w.get("odwolane"))
    if w.get("trener"):
        ev["trener_planowany"] = ev.get("trener")
        ev["trener"] = w["trener"]
    if w.get("zastepstwo"):
        ev["zastepstwo"] = w["zastepstwo"]
    if w.get("godz_od"):
        ev["godz_od"] = w["godz_od"]
    if w.get("godz_do"):
        ev["godz_do"] = w["godz_do"]


def available_months(conn):
    """
    Miesiące, w których cokolwiek się dzieje — bez sztywnego kodowania nazw zakładek.

    Odwołane spotkania też się liczą (P31). Miesiąc, w którym WSZYSTKO odwołano,
    wypada wtedy w wyborze pusty — ale gdyby go tu nie było, do listy odwołanych
    z tego miesiąca nie dałoby się dojechać żadnym kliknięciem.
    """
    rows = conn.execute(
        "SELECT DISTINCT substr(data,1,7) m FROM eventy "
        "WHERE data IS NOT NULL AND data <> '' ORDER BY m").fetchall()
    mies = [r["m"] for r in rows if r["m"]]
    # Pakiety na konkretne daty: miesiąc bierze się WPROST z terminu, nie
    # z rozwijania reguły. Bez tego ostatnie zajęcia z pakietu wpadające
    # w miesiąc, w którym nie ma nic innego, nie miałyby pozycji w wyborze
    # miesiąca — czyli byłyby w bazie i nie dałoby się do nich dojechać.
    try:
        mies += [r["m"] for r in conn.execute(
            "SELECT DISTINCT substr(data,1,7) m FROM terminy_cyklu "
            "WHERE data IS NOT NULL AND data <> ''").fetchall() if r["m"]]
    except Exception:
        pass
    # cykle „ciągną się" dalej niż data pierwszych zajęć — dolóż kolejne miesiące
    ma_cykle = conn.execute(
        "SELECT MIN(data) a, MAX(data) b FROM eventy WHERE typ IN (%s) "
        "AND data IS NOT NULL AND data <> ''" % SQL_TYPY_CYKLICZNE).fetchone()
    if ma_cykle and ma_cykle["a"]:
        try:
            start = dt.date.fromisoformat(ma_cykle["a"])
        except ValueError:
            start = None
        if start:
            koniec = start + dt.timedelta(weeks=CYKL_HORYZONT_TYGODNI)
            y, m = start.year, start.month
            while (y, m) <= (koniec.year, koniec.month):
                mies.append("%04d-%02d" % (y, m))
                m += 1
                if m > 12:
                    m = 1
                    y += 1
    return sorted(set(mies))


def _podzial_po_dacie(evs, dzis=None):
    """(zrealizowane, umówione) wg daty — wspólne dla trzech widoków."""
    prog = dzis or dt.date.today().isoformat()
    zreal = sum(1 for e in evs if (e.get("data") or "") < prog)
    return zreal, len(evs) - zreal


def liczniki_calosci(conn, dzis=None):
    """
    Zbiorczo przez WSZYSTKIE miesiące z danymi: ile spotkań już się odbyło,
    a ile dopiero przed nami. Pkt 16 z 30.08 (Kasia): „pokazuje miesięcznie
    i to jest fajne, ale potrzebuję obok też zbiorczo ile jest umówionych
    i ile zrealizowanych — to będzie wynikało z daty".

    Liczymy TYM SAMYM kodem co widoki (events_for_month rozwija cykle na
    wystąpienia i pomija odwołane) — osobne zapytanie SQL liczyłoby reguły
    cykli jako 1 zamiast liczby zajęć i wyniki nie zgadzałyby się z ekranem.
    """
    prog = dzis or dt.date.today().isoformat()
    zreal = przyszle = 0
    for m in available_months(conn):
        for e in events_for_month(conn, m):
            if (e.get("data") or "") < prog:
                zreal += 1
            else:
                przyszle += 1
    return {"zrealizowane": zreal, "umowione": przyszle}


def wystapienia_leada(conn, lead_id, od=None, ile=10):
    """
    Najbliższe wystąpienia zajęć CYKLICZNYCH jednej placówki — do karty leada.

    Pkt 19 z 30.08: klientka zobaczyła cykl 11.12 w kalendarzu, otworzyła kartę
    placówki, nie znalazła tej daty i uznała, że „kalendarz się nie
    zaktualizował". Kalendarz liczył dobrze — to karta pokazywała wyłącznie
    REGUŁĘ (datę pierwszych zajęć), nie jej rozwinięcie. Liczymy tym samym
    kodem co grafik (events_for_month: reguła/lista terminów, wyjątki,
    odwołania) — osobna pętla w karcie prędzej czy później skłamałaby inaczej
    niż kalendarz i wracamy do punktu wyjścia.
    """
    prog = od or dt.date.today().isoformat()
    out = []
    for m in available_months(conn):
        if m < prog[:7]:
            continue
        for e in events_for_month(conn, m):
            if (e["lead_id"] == lead_id and e["typ"] in TYPY_POWTARZALNE
                    and (e.get("data") or "") >= prog):
                out.append(e)
        if len(out) >= ile:
            break
    out.sort(key=lambda e: (e["data"], e.get("godz_od") or ""))
    return out[:ile]


# Wiersz macierzy dla zajęć, którym nikt jeszcze nie został przypisany.
# Bez niego takie zajęcia NIE MAJĄ GDZIE SIĘ POKAZAĆ — wiersze to trenerzy —
# więc znikają z widoku domyślnego, a licznik u góry i tak je liczy. Na danych
# klienta było to 5 z 61 wystąpień września: kalendarz twierdził, że pokazuje
# komplet. To ten sam błąd, przed którym kod broni się przy kolizjach:
# najgorsze, co ta aplikacja może zrobić, to schować coś po cichu.
BEZ_TRENERA = "— bez prowadzącego —"


def tylko_bez_obsady(evs):
    """
    Zajęcia, przy których nie ma nikogo prowadzącego (P24, pytanie Zuzi 20.08:
    „czy można już wyszukiwać bez prowadzącego?").

    Osobno od filtra na chipach, bo tamten szuka WPISANEGO TEKSTU w polach —
    a „nikogo tu nie ma" to brak wartości, którego żadnym fragmentem tekstu nie
    da się wyrazić. Licznik w nagłówku pokazywał te zajęcia od 10.08, ale nie
    dało się do nich dojść inaczej niż przewijając cały miesiąc.

    Liczy się WYŁĄCZNIE `trener`, czyli ten, kto prowadzi. Drugi prowadzący,
    zastępstwo i drukarz to obsada dodatkowa — zajęcia z samym drukarzem dalej
    nie mają kto poprowadzić.
    """
    return [e for e in evs if not str(e.get("trener") or "").strip()]


# Czego brakuje w DT, żeby dało się go poprowadzić (P30, prośba Kasi z 20.08:
# „jeśli mam datę DT i wpisało się do kalendarza, a nie mam liczby dzieci albo
# klas, to w kalendarzu ma się to jakoś podświetlić, że brakuje danych").
#
# To druga połowa P27. Formularz przestał żądać kompletu przy zapisie — inaczej
# nie dało się wpisać wizyty, po której szkoła chce DT, ale godzinę poda
# sekretariat. Samo zdjęcie wymogu zamieniłoby jednak problem „nie da się
# zapisać" na gorszy: „zapisane, wygląda na gotowe, nikt tam już nie wróci".
#
# Prowadzący ma własny licznik i własny filtr (P24), więc TUTAJ go nie liczymy:
# dwa liczniki mówiące o tym samym wpisie różne liczby są gorsze niż jeden.
BRAKI_DT = [("godz_od", "godzina"), ("ilosc_klas", "liczba klas"),
            ("ilosc_dzieci", "liczba dzieci")]


def braki_dt(e):
    """Lista brakujących szczegółów DT. Dla zajęć cyklicznych pusta — liczba klas
    nie jest tam informacją, którą ktokolwiek uzupełnia."""
    if (e.get("typ") or "DT") != "DT":
        return []
    return [opis for pole, opis in BRAKI_DT
            if not str(e.get(pole) or "").strip()]


def tylko_do_uzupelnienia(evs):
    """Zajęcia z niekompletnymi danymi — lista roboty, tak samo jak `bez_obsady`."""
    return [e for e in evs if e.get("braki")]


def roster_trenerow(conn, evs):
    """
    Wiersze macierzy: pełna lista trenerów ze słownika (żeby widać było też wolnych —
    klient używa kalendarza do dogrywania szkół, więc puste wiersze są informacją)
    + trenerzy występujący w danych, których w słowniku nie ma.
    """
    ze_slownika = slownik_values(conn, "trener")
    w_danych = {e["trener"] for e in evs if e["trener"]}
    extra = sorted(w_danych - set(ze_slownika))
    return ze_slownika + extra


# ------------------------------------------------------------------ widok MACIERZ

def build_matrix(conn, month, weekend=False, tylko_zajete=False, typy=None,
                 chipy=(), tryb="lub", bez_obsady=False, do_uzupelnienia=False,
                 odwolane=False):
    """
    Bloki tygodniowe jeden pod drugim; każdy blok to tabela trenerzy × dni.
    Tak jak w ich arkuszu, tylko że bloki są POD sobą, a nie obok siebie
    (w przeglądarce przewijanie w dół jest naturalniejsze niż w prawo).

    weekend=False → pon–pt (jak u nich). tylko_zajete=True → pomija puste wiersze.

    KOLIZJE liczymy PRZED filtrem, na pełnym komplecie. Inaczej wyfiltrowanie
    jednej ze szkół chowałoby drugą stronę nakładki i ostrzeżenie znikałoby po
    cichu — a to najgorszy możliwy błąd w tym projekcie.
    """
    y, m = [int(x) for x in month.split("-")]
    ile_dni = 7 if weekend else 5

    evs = events_for_month(conn, month, typy=typy, odwolane=odwolane)
    kolizje = find_collisions(evs)
    evs = filtruj_eventy(evs, chipy, tryb)
    if bez_obsady:
        evs = tylko_bez_obsady(evs)
    if do_uzupelnienia:
        evs = tylko_do_uzupelnienia(evs)
    # przy czynnym filtrze puste wiersze tylko przeszkadzają: skoro pytam „gdzie
    # jest Zemela", nie chcę oglądać 34 pustych wierszy pozostałych trenerów
    if bez_obsady or do_uzupelnienia or (chipy and any(not c.get("wylaczony") for c in chipy)):
        tylko_zajete = True
    komorki = {}
    for e in evs:
        e["kolizja"] = e["_key"] in kolizje
        komorki.setdefault((e["trener"] or BEZ_TRENERA, e["data"]), []).append(e)

    trenerzy = roster_trenerow(conn, evs)
    # Wiersz „bez prowadzącego" tylko wtedy, gdy jest co w nim pokazać, i ZAWSZE
    # na górze: to nie jest jeden z trenerów, tylko lista rzeczy do przypisania.
    n_bez_trenera = sum(1 for e in evs if not e.get("trener"))
    if n_bez_trenera:
        trenerzy = [BEZ_TRENERA] + trenerzy
    kolory = trener_colors(conn)

    tygodnie = []
    for tydz in _cal.Calendar(firstweekday=0).monthdatescalendar(y, m):
        tydz = tydz[:ile_dni]
        dni = [{"iso": d.isoformat(), "day": d.day, "dow": DNI[d.weekday()],
                "dow_skr": DNI_SKR[d.weekday()], "weekend": d.weekday() >= 5,
                "in_month": d.month == m, "dzis": d == dt.date.today()} for d in tydz]
        wiersze = []
        for tr in trenerzy:
            cells = [komorki.get((tr, d["iso"]), []) for d in dni]
            ma = any(cells)
            if tylko_zajete and not ma:
                continue
            wiersze.append({"trener": tr, "kolor": kolory.get(tr, "#9b9797"),
                            "brak_trenera": tr == BEZ_TRENERA,
                            "cells": cells, "ma": ma,
                            "n": sum(len(c) for c in cells)})
        n_ev = sum(w["n"] for w in wiersze)
        pierwszy, ostatni = tydz[0], tydz[-1]
        label = "%d.%02d – %d.%02d" % (pierwszy.day, pierwszy.month,
                                       ostatni.day, ostatni.month)
        tygodnie.append({"dni": dni, "wiersze": wiersze, "label": label,
                         "ma": n_ev > 0, "n": n_ev})

    zreal, umow = _podzial_po_dacie(evs)
    return {"tygodnie": tygodnie, "trenerzy": trenerzy, "kolory": kolory,
            "n_events": len(evs), "n_kolizji": _ile_kolizji(evs, kolizje),
            "n_bez_trenera": n_bez_trenera,
            "n_bez_godziny": sum(1 for e in evs if not e.get("godz_od")),
            "n_do_uzupelnienia": sum(1 for e in evs if e.get("braki")),
            "n_zrealizowane": zreal, "n_umowione": umow,
            "month": month, "month_label": month_label(month)}


# ------------------------------------------------------------------ widok AGENDA

def build_agenda(conn, month, weekend=True, typy=None, chipy=(), tryb="lub",
                 bez_obsady=False, do_uzupelnienia=False, odwolane=False):
    """Dzień po dniu; w dniu spotkania posortowane po godzinie. Puste dni pomijamy."""
    evs = events_for_month(conn, month, typy=typy, odwolane=odwolane)
    kolizje = find_collisions(evs)                # jak w macierzy: przed filtrem
    evs = filtruj_eventy(evs, chipy, tryb)
    if bez_obsady:
        evs = tylko_bez_obsady(evs)
    if do_uzupelnienia:
        evs = tylko_do_uzupelnienia(evs)

    po_dniach = {}
    for e in evs:
        e["kolizja"] = e["_key"] in kolizje
        po_dniach.setdefault(e["data"], []).append(e)

    kolory = trener_colors(conn)
    dni = []
    for iso in sorted(po_dniach):
        d = dt.date.fromisoformat(iso)
        if d.weekday() >= 5 and not weekend:
            continue
        lista = sorted(po_dniach[iso], key=lambda e: (e["godz_od"] or "99:99",
                                                      e["trener"] or ""))
        for e in lista:
            e["kolor"] = kolory.get(e["trener"], "#9b9797")
        dni.append({"iso": iso, "day": d.day, "dow": DNI[d.weekday()],
                    "mies": MIESIACE_D[d.month], "weekend": d.weekday() >= 5,
                    "dzis": d == dt.date.today(), "eventy": lista, "n": len(lista)})

    zreal, umow = _podzial_po_dacie(evs)
    return {"dni": dni, "kolory": kolory, "n_events": sum(d["n"] for d in dni),
            "n_kolizji": _ile_kolizji(evs, kolizje),
            "n_bez_trenera": sum(1 for e in evs if not e.get("trener")),
            "n_bez_godziny": sum(1 for e in evs if not e.get("godz_od")),
            "n_do_uzupelnienia": sum(1 for e in evs if e.get("braki")),
            "n_zrealizowane": zreal, "n_umowione": umow,
            "month": month, "month_label": month_label(month)}


# ------------------------------------------------------------------ widok STARTY

def build_starty(conn, month, weekend=False, chipy=(), tryb="lub", bez_obsady=False,
                 do_uzupelnienia=False, odwolane=False):
    """
    Plansza całej firmy — odwzorowanie zakładki „STARTY <MIESIĄC>".
    Tygodnie jeden pod drugim, w tygodniu kolumny pon–pt, w kolumnie karty zajęć.
    Karta pokazuje to, co realnie potrzebne w terenie: godziny, placówkę, adres,
    grupę, sprzęt, trenera, zastępstwo, drukarza i kod Tinkercad.
    """
    y, m = [int(x) for x in month.split("-")]
    ile_dni = 7 if weekend else 5

    evs = events_for_month(conn, month, odwolane=odwolane)
    kolizje = find_collisions(evs)                # jak w macierzy: przed filtrem
    evs = filtruj_eventy(evs, chipy, tryb)
    if bez_obsady:
        evs = tylko_bez_obsady(evs)
    if do_uzupelnienia:
        evs = tylko_do_uzupelnienia(evs)
    kolory = trener_colors(conn)
    po_dniach = {}
    for e in evs:
        e["kolizja"] = e["_key"] in kolizje
        e["kolor"] = kolory.get(e["trener"], "#9b9797")
        po_dniach.setdefault(e["data"], []).append(e)

    tygodnie = []
    for tydz in _cal.Calendar(firstweekday=0).monthdatescalendar(y, m):
        tydz = tydz[:ile_dni]
        kolumny = []
        for d in tydz:
            lista = sorted(po_dniach.get(d.isoformat(), []),
                           key=lambda e: (e["godz_od"] or "99:99", e["placowka"]))
            kolumny.append({
                "iso": d.isoformat(), "day": d.day, "dow": DNI[d.weekday()],
                "in_month": d.month == m, "dzis": d == dt.date.today(),
                "eventy": lista, "n": len(lista),
            })
        n = sum(k["n"] for k in kolumny)
        if n == 0 and not any(k["in_month"] for k in kolumny):
            continue
        pierwszy, ostatni = tydz[0], tydz[-1]
        tygodnie.append({
            "kolumny": kolumny, "n": n,
            "label": "%d.%02d – %d.%02d" % (pierwszy.day, pierwszy.month,
                                            ostatni.day, ostatni.month),
        })

    zreal, umow = _podzial_po_dacie(evs)
    return {"tygodnie": tygodnie, "kolory": kolory, "n_events": len(evs),
            "n_kolizji": _ile_kolizji(evs, kolizje),
            "n_bez_trenera": sum(1 for e in evs if not e.get("trener")),
            "n_bez_godziny": sum(1 for e in evs if not e.get("godz_od")),
            "n_do_uzupelnienia": sum(1 for e in evs if e.get("braki")),
            "n_zrealizowane": zreal, "n_umowione": umow,
            "month": month, "month_label": month_label(month)}


# ------------------------------------------------------------------ metryki

def obciazenie_trenerow(conn, month):
    """Ile zajęć ma każdy trener w miesiącu — do pulpitu i do dogrywania szkół."""
    evs = events_for_month(conn, month)
    licz = {}
    for e in evs:
        if e["trener"]:
            licz[e["trener"]] = licz.get(e["trener"], 0) + 1
    kolory = trener_colors(conn)
    return sorted(({"trener": t, "n": n, "kolor": kolory.get(t, "#9b9797")}
                   for t, n in licz.items()), key=lambda x: -x["n"])


def lista_kolizji(conn, month=None):
    """Kolizje do pulpitu: pary/grupy nakładających się zajęć jednego trenera."""
    mies = [month] if month else available_months(conn)
    kolory = trener_colors(conn)
    out = []
    for mm in mies:
        evs = events_for_month(conn, mm)
        kol = find_collisions(evs)
        for e in evs:
            if e["_key"] in kol:
                e["kolizja"] = True
                e["kolor"] = kolory.get(e["trener"], "#9b9797")
                out.append(e)
    out.sort(key=lambda e: (e["data"], e["trener"] or "", e["godz_od"] or ""))
    return out
