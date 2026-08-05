# -*- coding: utf-8 -*-
"""
Przydzielanie trenerów — odpowiedź na pytanie „kogo wysłać na to DT?".

W arkuszu tej odpowiedzi nie było: koordynatorka patrzyła na zakładkę
`DOSTĘPNOŚĆ NA DT - TRENERZY`, wypatrywała wolne okno i przepisywała nazwisko
do kalendarza — z pamięci pilnując, kto jeździ w którą stronę województwa
i kto ma już za dużo zajęć. Tu te trzy rzeczy (dostępność, kolizje, rejon)
schodzą się w jedną listę, posortowaną tak, że najlepszy kandydat jest u góry.

Cztery kategorie, w tej kolejności:

  wolny        deklaracja pokrywa godziny spotkania i nic się nie nakłada
  nieznany     brak deklaracji dostępności — NIE zakaz, po prostu nie wiadomo
  zastrzezenie kolizja godzin albo spotkanie poza zadeklarowanym oknem
  niedostepny  arkuszowe „XXX" na ten dzień

Zgodnie z zasadą całego projektu: **ostrzegamy, nigdy nie blokujemy.**
Każdego kandydata da się przydzielić — także tego z ostatniej kategorii.
Lista sortuje i uzasadnia, decyzję podejmuje człowiek.
"""
import datetime as dt

from calendar_view import _mins, events_for_month, month_label
from db import slownik_values, trener_colors
from dostepnosc_view import okno_wpisu, wolne_okna, _hhmm

# Kolejność kategorii na liście = kolejność w tej krotce.
KATEGORIE = ("wolny", "nieznany", "zastrzezenie", "niedostepny")

ETYKIETY = {
    "wolny": "Wolni",
    "nieznany": "Bez deklaracji dostępności",
    "zastrzezenie": "Z zastrzeżeniem",
    "niedostepny": "Niedostępni",
}


# ------------------------------------------------------------------- rejony

def rejony_map(conn):
    """Mapa trener → lista miast, po których jeździ."""
    out = {}
    for r in conn.execute("SELECT trener, miasto FROM rejony ORDER BY trener, miasto"):
        out.setdefault(r["trener"], []).append(r["miasto"])
    return out


def ustaw_rejon(conn, trener, miasta):
    """
    Podmienia cały rejon trenera (prościej i pewniej niż dokładanie po jednym).
    Zwraca liczbę zapisanych miast.
    """
    conn.execute("DELETE FROM rejony WHERE trener=?", (trener,))
    for m in sorted(set(m for m in miasta if m)):
        conn.execute("INSERT OR IGNORE INTO rejony (trener, miasto) VALUES (?,?)",
                     (trener, m))
    return conn.execute("SELECT COUNT(*) c FROM rejony WHERE trener=?",
                        (trener,)).fetchone()["c"]


# --------------------------------------------------------------- kandydaci

def _eventy_dnia(evs, trener, data, pomin_key=None):
    """Zajęcia trenera w danym dniu (z rozwiniętymi cyklami), bez edytowanego wpisu."""
    out = []
    for e in evs:
        if e.get("trener") != trener or e.get("data") != data:
            continue
        if pomin_key and str(e.get("_key", e.get("id"))).split("@")[0] == str(pomin_key):
            continue
        out.append(e)
    return sorted(out, key=lambda e: e.get("godz_od") or "99:99")


def _naklada(a1, a2, b1, b2):
    return a1 < b2 and b1 < a2


def _zakres_spotkania(godz_od, godz_do):
    """(od, do) w minutach albo None gdy nie podano godziny startu.
    Brak końca → 60 minut, spójnie z resztą systemu."""
    a = _mins(godz_od)
    if a is None:
        return None
    b = _mins(godz_do)
    if b is None or b <= a:
        b = a + 60
    return (a, b)


def kandydaci(conn, data, godz_od=None, godz_do=None, miasto=None, event_id=None):
    """
    Ranking trenerów na spotkanie (data + godziny + miasto placówki).

    Zwraca listę słowników posortowaną: kategoria → rejon → obciążenie → nazwisko.
    Trener z rejonu wychodzi przed trenera spoza rejonu, ale spoza rejonu NIE
    znika z listy — na zastępstwo albo w wakacje jeździ się wszędzie.
    """
    if not data:
        return []
    month = data[:7]
    evs = events_for_month(conn, month)
    zakres = _zakres_spotkania(godz_od, godz_do)

    wpisy = {r["trener"]: dict(r) for r in conn.execute(
        "SELECT * FROM dostepnosc WHERE data=?", (data,))}

    obciazenie = {}
    for e in evs:
        if e.get("trener"):
            obciazenie[e["trener"]] = obciazenie.get(e["trener"], 0) + 1

    rejony = rejony_map(conn)
    kolory = trener_colors(conn)

    out = []
    for trener in slownik_values(conn, "trener"):
        wpis = wpisy.get(trener)
        zajete = _eventy_dnia(evs, trener, data, pomin_key=event_id)

        kolizje = []
        if zakres:
            for e in zajete:
                z = _zakres_spotkania(e.get("godz_od"), e.get("godz_do"))
                if z and _naklada(zakres[0], zakres[1], z[0], z[1]):
                    kolizje.append(e)

        okno = okno_wpisu(wpis)
        poza_oknem = bool(zakres and okno and
                          (zakres[0] < okno[0] or zakres[1] > okno[1]))

        if wpis and wpis.get("niedostepny"):
            kategoria = "niedostepny"
            powod = "oznaczony jako niedostępny" + (
                " (%s)" % wpis["uwagi"] if wpis.get("uwagi") else "")
        elif kolizje:
            kategoria = "zastrzezenie"
            e = kolizje[0]
            powod = "kolizja %s–%s" % (e.get("godz_od") or "?", e.get("godz_do") or "?")
            if len(kolizje) > 1:
                powod += " i %d inn." % (len(kolizje) - 1)
        elif poza_oknem:
            kategoria = "zastrzezenie"
            powod = "poza deklaracją (%s–%s)" % (_hhmm(okno[0]), _hhmm(okno[1]))
        elif not wpis:
            kategoria = "nieznany"
            powod = "brak deklaracji na ten dzień"
        else:
            kategoria = "wolny"
            powod = ("cały dzień" if not wpis.get("godz_od")
                     else "deklaracja %s–%s" % (wpis["godz_od"], wpis["godz_do"]))

        w_rejonie = bool(miasto and miasto in rejony.get(trener, []))
        out.append({
            "trener": trener,
            "kolor": kolory.get(trener, "#9b9797"),
            "kategoria": kategoria,
            "powod": powod,
            "wolne": wolne_okna(wpis, zajete),
            "zajete": [{"godz_od": e.get("godz_od"), "godz_do": e.get("godz_do"),
                        "typ": e.get("typ"), "szkola": e.get("placowka") or "",
                        "miasto": e.get("miejscowosc") or ""} for e in zajete],
            "n_zajec_dnia": len(zajete),
            "obciazenie": obciazenie.get(trener, 0),
            "rejon": w_rejonie,
            "rejon_miasta": rejony.get(trener, []),
        })

    out.sort(key=lambda k: (KATEGORIE.index(k["kategoria"]), not k["rejon"],
                            k["obciazenie"], k["trener"]))
    return out


def pogrupuj(lista):
    """Kandydaci w grupach do wyświetlenia — puste kategorie pomijamy."""
    grupy = []
    for kat in KATEGORIE:
        poz = [k for k in lista if k["kategoria"] == kat]
        if poz:
            grupy.append({"kategoria": kat, "etykieta": ETYKIETY[kat],
                          "n": len(poz), "pozycje": poz})
    return grupy


def kontekst_eventu(conn, event_id):
    """Dane spotkania potrzebne do rankingu: data, godziny, miasto placówki."""
    r = conn.execute(
        "SELECT e.id, e.data, e.godz_od, e.godz_do, e.trener, e.typ, "
        "       p.miejscowosc, p.nazwa "
        "FROM eventy e JOIN leady l ON l.id=e.lead_id "
        "JOIN placowki p ON p.id=l.placowka_id WHERE e.id=?", (event_id,)).fetchone()
    return dict(r) if r else None


# ------------------------------------------------------ ekran obsady rejonów

def stan_rejonow(conn):
    """Do ekranu /rejony: każdy trener z listą swoich miast i licznikiem zajęć."""
    rejony = rejony_map(conn)
    kolory = trener_colors(conn)
    licz = {r["trener"]: r["n"] for r in conn.execute(
        "SELECT trener, COUNT(*) n FROM eventy WHERE trener IS NOT NULL "
        "AND trener<>'' GROUP BY trener")}
    out = []
    for t in slownik_values(conn, "trener"):
        out.append({"trener": t, "kolor": kolory.get(t, "#9b9797"),
                    "miasta": rejony.get(t, []), "n_zajec": licz.get(t, 0)})
    return out


def podpowiedz_rejonu(conn, trener):
    """
    Miasta, w których trener FAKTYCZNIE uczył (z historii zajęć) — gotowa
    propozycja rejonu do zaakceptowania jednym kliknięciem, zamiast klikania
    33 miast z listy. Rejon w danych jest, tylko nikt go nigdy nie zapisał.
    """
    rows = conn.execute(
        "SELECT p.miejscowosc m, COUNT(*) n FROM eventy e "
        "JOIN leady l ON l.id=e.lead_id JOIN placowki p ON p.id=l.placowka_id "
        "WHERE e.trener=? AND p.miejscowosc IS NOT NULL AND p.miejscowosc<>'' "
        "GROUP BY p.miejscowosc ORDER BY n DESC", (trener,)).fetchall()
    return [{"miasto": r["m"], "n": r["n"]} for r in rows]
