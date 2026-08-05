# -*- coding: utf-8 -*-
"""
Dostępność trenerów — ekran, którego w `PH Nowy` brakuje, a w zeszłorocznym
pliku był POŁOWĄ treści kalendarza DT i jedynym wejściem do umawiania
(`'DOSTĘPNA 8 - 12:00'`, `'DOSTĘPNA CAŁY DZIEŃ'`, `'XXX'` = niedostępny).

Cztery jawne stany komórki (w arkuszu wszystkie mieszały się w jednym tekście):

  brak wpisu    dostępność NIEZNANA — to nie to samo co niedostępny
  niedostepny   arkuszowe 'XXX'
  okno          'DOSTĘPNA 8 - 12:00' → godz_od + godz_do
  caly          wpis bez godzin = dostępny cały dzień (przyjmujemy 8:00–18:00)

Najważniejsza różnica wobec arkusza: komórka pokazuje WOLNE OKNA, czyli
deklarację pomniejszoną o to, co już wisi w kalendarzu (DT + rozwinięte cykle
z wyjątkami). W arkuszu trenerki dopisywały zajętość ręcznie w nawiasach —
tu liczy się sama, więc nie może się rozjechać.
"""
import calendar as _cal
import datetime as dt

from calendar_view import (_mins, events_for_month, roster_trenerow,
                           month_label, DNI, DNI_SKR)
from db import trener_colors
from filtry import pasuje, POLA_WSZYSTKO

# „cały dzień" na potrzeby liczenia wolnych okien
DZIEN_OD = 8 * 60          # 08:00
DZIEN_DO = 18 * 60         # 18:00
# okna krótsze niż to pomijamy — nie zmieści się w nich ani DT, ani cykl
MIN_OKNO = 45


def _hhmm(minuty):
    return "%02d:%02d" % (minuty // 60, minuty % 60)


def _przedzial_eventu(e):
    """(od, do) w minutach albo None. Brak godziny końca → 60 minut,
    spójnie z tym, jak liczymy kolizje."""
    a = _mins(e.get("godz_od"))
    if a is None:
        return None
    b = _mins(e.get("godz_do"))
    if b is None or b <= a:
        b = a + 60
    return (a, b)


def okno_wpisu(wpis):
    """(od, do) w minutach dla wpisu dostępności; None gdy niedostępny/brak."""
    if not wpis or wpis.get("niedostepny"):
        return None
    a = _mins(wpis.get("godz_od"))
    b = _mins(wpis.get("godz_do"))
    if a is None:
        return (DZIEN_OD, DZIEN_DO)
    if b is None or b <= a:
        b = DZIEN_DO if a < DZIEN_DO else a + 60
    return (a, b)


def wolne_okna(wpis, eventy):
    """
    Deklaracja minus zajęte przedziały → lista wolnych okien ['08:00–09:40', ...].
    Zwraca [] też wtedy, gdy trener jest niedostępny albo nie ma wpisu.
    """
    okno = okno_wpisu(wpis)
    if not okno:
        return []
    zajete = sorted(p for p in (_przedzial_eventu(e) for e in eventy) if p)
    wolne = []
    kursor, koniec = okno
    for a, b in zajete:
        if a > kursor:
            wolne.append((kursor, min(a, koniec)))
        kursor = max(kursor, b)
        if kursor >= koniec:
            break
    if kursor < koniec:
        wolne.append((kursor, koniec))
    return ["%s–%s" % (_hhmm(a), _hhmm(b)) for a, b in wolne if b - a >= MIN_OKNO]


def _wpisy_miesiaca(conn, month):
    rows = conn.execute(
        "SELECT * FROM dostepnosc WHERE substr(data,1,7)=?", (month,)).fetchall()
    return {(r["trener"], r["data"]): dict(r) for r in rows}


def _widoczni_trenerzy(trenerzy, wpisy, evs, chipy, tryb):
    """
    Którzy trenerzy zostają na siatce po filtrze.

    Filtrujemy WIERSZE, nie komórki: ekran odpowiada na pytanie „kiedy ta osoba
    może", więc pokazanie jej dnia w kawałkach byłoby kłamstwem — wolne okna
    liczą się z całego dnia. Rozstrzygamy raz na miesiąc, a nie w pętli tygodni,
    żeby siatka nie zrobiła się poszarpana (w jednym tygodniu wiersz jest,
    w drugim go nie ma).

    Zakres „nazwisko" patrzy tylko na nazwisko trenera. Zakres „wszystko"
    obejmuje dodatkowo jego uwagi z deklaracji i szkoły, do których w tym
    miesiącu jeździ — dzięki temu „Knurów" pokazuje tych, którzy tam bywają.
    """
    if not [c for c in chipy if not c.get("wylaczony")]:
        return trenerzy
    po_trenerze = {}
    for e in evs:
        if e.get("trener"):
            po_trenerze.setdefault(e["trener"], []).append(e)
    uwagi = {}
    for (tr, _data), w in wpisy.items():
        if w.get("uwagi"):
            uwagi.setdefault(tr, []).append(str(w["uwagi"]))

    def pola(tr):
        """`pobierz_pole` dla jednego trenera; „wszystko" składamy leniwie."""
        pamiec = {}

        def pobierz(zakres):
            if zakres == "n":
                return tr
            if "w" not in pamiec:
                czesci = [tr] + uwagi.get(tr, [])
                for e in po_trenerze.get(tr, []):
                    czesci += [str(e.get(k) or "") for k in POLA_WSZYSTKO]
                pamiec["w"] = " ".join(czesci)
            return pamiec["w"]
        return pobierz

    return [tr for tr in trenerzy if pasuje(chipy, tryb, pola(tr))]


def build_dostepnosc(conn, month, weekend=False, chipy=(), tryb="lub"):
    """
    Siatka trener × dzień w blokach tygodniowych — ten sam układ co macierz
    Kalendarza DT, żeby niczego nie trzeba było się uczyć na nowo.

    Komórka: {'wpis', 'status', 'okno', 'zajete', 'wolne', 'iso'}.
    """
    y, m = [int(x) for x in month.split("-")]
    ile_dni = 7 if weekend else 5

    wpisy = _wpisy_miesiaca(conn, month)
    evs = events_for_month(conn, month)
    zajetosc = {}
    for e in evs:
        if e.get("trener"):
            zajetosc.setdefault((e["trener"], e["data"]), []).append(e)

    wszyscy = roster_trenerow(conn, evs)
    trenerzy = _widoczni_trenerzy(wszyscy, wpisy, evs, chipy, tryb)
    kolory = trener_colors(conn)

    tygodnie = []
    for tydz in _cal.Calendar(firstweekday=0).monthdatescalendar(y, m):
        tydz = tydz[:ile_dni]
        dni = [{"iso": d.isoformat(), "day": d.day, "dow": DNI[d.weekday()],
                "dow_skr": DNI_SKR[d.weekday()], "weekend": d.weekday() >= 5,
                "in_month": d.month == m, "dzis": d == dt.date.today()} for d in tydz]
        wiersze = []
        for tr in trenerzy:
            cells = []
            n_wpisow = 0
            for d in dni:
                wpis = wpisy.get((tr, d["iso"]))
                ev = sorted(zajetosc.get((tr, d["iso"]), []),
                            key=lambda e: e.get("godz_od") or "99:99")
                if not wpis:
                    status = "brak"
                elif wpis.get("niedostepny"):
                    status = "niedostepny"
                elif wpis.get("godz_od") and wpis.get("godz_do"):
                    status = "okno"
                else:
                    status = "caly"
                if wpis:
                    n_wpisow += 1
                cells.append({
                    "iso": d["iso"], "wpis": wpis, "status": status,
                    "okno": ("%s–%s" % (wpis["godz_od"], wpis["godz_do"])
                             if status == "okno" else
                             "cały dzień" if status == "caly" else ""),
                    "zajete": ev,
                    "wolne": wolne_okna(wpis, ev),
                })
            wiersze.append({"trener": tr, "kolor": kolory.get(tr, "#9b9797"),
                            "cells": cells, "n_wpisow": n_wpisow,
                            "n_zajec": sum(len(c["zajete"]) for c in cells)})
        pierwszy, ostatni = tydz[0], tydz[-1]
        tygodnie.append({
            "dni": dni, "wiersze": wiersze,
            "label": "%d.%02d – %d.%02d" % (pierwszy.day, pierwszy.month,
                                            ostatni.day, ostatni.month),
        })

    # liczniki w nagłówku dotyczą TEGO, co widać — po zawężeniu do jednej osoby
    # „1700 deklaracji" byłoby liczbą znikąd
    widoczni = set(trenerzy)
    n_wpisow = sum(1 for (tr, data) in wpisy
                   if tr in widoczni and data[:7] == month)
    n_niedost = sum(1 for (tr, _d), w in wpisy.items()
                    if tr in widoczni and w.get("niedostepny"))
    return {"tygodnie": tygodnie, "trenerzy": trenerzy, "kolory": kolory,
            "n_wpisow": n_wpisow, "n_niedostepnych": n_niedost,
            "n_trenerow": len(trenerzy), "n_trenerow_all": len(wszyscy),
            "month": month, "month_label": month_label(month)}


def sprawdz_dostepnosc(conn, trener, data, godz_od, godz_do):
    """
    Ostrzeżenie (string) albo None — używane przy zapisie spotkania.
    Brak deklaracji → cisza: nieznana dostępność to nie zakaz.
    Jak przy kolizjach: ostrzegamy, NIGDY nie blokujemy.
    """
    if not trener or not data:
        return None
    w = conn.execute("SELECT * FROM dostepnosc WHERE trener=? AND data=?",
                     (trener, data)).fetchone()
    if not w:
        return None
    w = dict(w)
    if w.get("niedostepny"):
        return ("Trener %s jest oznaczony jako NIEDOSTĘPNY w dniu %s%s"
                % (trener, data, " (%s)" % w["uwagi"] if w.get("uwagi") else ""))
    # ostrzegamy tylko przy jawnym oknie godzin — „cały dzień" niczego nie zabrania
    if not (w.get("godz_od") and w.get("godz_do")):
        return None
    a, b = _mins(w["godz_od"]), _mins(w["godz_do"])
    e_od = _mins(godz_od)
    if a is None or b is None or e_od is None:
        return None
    e_do = _mins(godz_do)
    if e_do is None or e_do <= e_od:
        e_do = e_od + 60
    if e_od < a or e_do > b:
        return ("Spotkanie %s–%s wypada poza dostępnością trenera %s (%s–%s) w dniu %s"
                % (_hhmm(e_od), _hhmm(e_do), trener, w["godz_od"], w["godz_do"], data))
    return None
