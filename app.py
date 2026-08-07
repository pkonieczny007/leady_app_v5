# -*- coding: utf-8 -*-
"""
System Leadów v3 — aplikacja zastępująca arkusz.

Ekrany odpowiadają zakładkom, których klient realnie używa:
  /baza            → zakładka BAZA (koordynator rozdaje leady)
  /leady           → zakładka handlowca (jego szkoły, filtry, edycja inline)
  /zbiorczy        → arkusz Julki (jej kolumny do odhaczania)
  /niewykorzystane → zakładka „Niewykorzystane rekordy"
  /kalendarz       → Kalendarz DT / cykliczne / plansza STARTY (trzy widoki jednych danych)
  /tydzien         → „wybrane szkoły na tydzień do góry" (plan tygodnia)
  /pulpit          → metryki, kolizje trenerów, po terminie, minimum tygodniowe
  /slowniki        → jedno źródło list rozwijanych

Różnica wobec arkusza: nic się nie kopiuje między ekranami. Jest jedno źródło
(placówka + lead + eventy), a ekrany to filtry i widoki. Dlatego poprawka daty
w jednym miejscu aktualizuje wszystko, a trener z trzema DT w jednym dniu
widzi trzy wpisy, nie jeden.
"""
import datetime as dt
import os

from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, abort, send_file, flash)

import calendar_view as cv
import dostepnosc_view as dv
import filtry as fl
import przydzial as pz
import repo
import zwrot
from db import (get_conn, wszystkie_slowniki, slownik, slownik_values, trener_colors,
                zapisz_log, LEAD_FIELDS, JULIA_FIELDS, EVENT_FIELDS, PLACOWKA_FIELDS,
                LEAD_KEYS, EVENT_KEYS, PLACOWKA_KEYS, SLOWNIK_RODZAJE, SLOWNIK_KLUCZE,
                INT_KEYS, STATUS_SUKCES_PREFIX, kolor_z_nazwy, opis_profilu, pl_fold)
from seed import bootstrap

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "leady-v3-demo")

# Pola wymuszające słownik — {klucz_pola: rodzaj_słownika}
LEAD_SLOWNIKI = {f[1]: f[2].split(":", 1)[1]
                 for f in (LEAD_FIELDS + JULIA_FIELDS) if f[2].startswith("slownik:")}
EVENT_SLOWNIKI = {f[1]: f[2].split(":", 1)[1]
                  for f in EVENT_FIELDS if f[2].startswith("slownik:")}
PLACOWKA_SLOWNIKI = {f[1]: f[2].split(":", 1)[1]
                     for f in PLACOWKA_FIELDS if f[2].startswith("slownik:")}

CEL_TYGODNIOWY = int(os.environ.get("CEL_TYGODNIOWY", "5"))


def dzis():
    return dt.date.today().isoformat()


def poniedzialek(d=None):
    d = d or dt.date.today()
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def _walidacja(conn, field, value, mapa_slownikow, dozwolone_klucze):
    """
    Wspólna walidacja zapisu pola. Zwraca (value, blad).
    Wymuszenie słownika jest tu celowo twarde — to jedyny sposób, żeby nie wróciło
    „02. Olaszewska" obok „02. Olszewska".
    """
    if field not in dozwolone_klucze:
        return None, "Nieznane pole: %s" % field
    if value == "":
        value = None
    if value is not None and field in mapa_slownikow:
        rodzaj = mapa_slownikow[field]
        if value not in slownik_values(conn, rodzaj):
            return None, "Wartość spoza słownika „%s”" % rodzaj
    if value is not None and field in INT_KEYS:
        try:
            value = int(str(value).strip())
        except (TypeError, ValueError):
            return None, "Oczekiwano liczby"
    return value, None


# ================================================================== EKRANY

@app.route("/")
def index():
    return redirect(url_for("pulpit"))


# Ile wierszy na stronę. Bez limitu `/baza` przy 550 leadach generuje ~1,4 MB HTML,
# bo każdy wiersz nosi pełne listy rozwijane (35 trenerów, 23 miejscowości).
NA_STRONE = int(os.environ.get("NA_STRONE", "150"))


def _ekran_leadow(template, zakres_domyslny="", tytul="", kicker="", **extra):
    conn = get_conn()
    f = repo.czytaj_filtr(request.args)
    if not f["zakres"] and zakres_domyslny:
        f["zakres"] = zakres_domyslny
    try:
        strona = max(1, int(request.args.get("strona", "1")))
    except ValueError:
        strona = 1
    ile = policz = repo.policz_leady(conn, f)
    rows = repo.filtruj_leady(conn, f, limit=NA_STRONE,
                              offset=(strona - 1) * NA_STRONE)
    stron = max(1, -(-ile // NA_STRONE))
    ctx = {
        "rows": rows, "f": f, "total": policz, "pokazano": len(rows),
        "strona": strona, "stron": stron, "na_strone": NA_STRONE,
        "slowniki": wszystkie_slowniki(conn),
        "kolory": trener_colors(conn),
        "lead_fields": LEAD_FIELDS, "julia_fields": JULIA_FIELDS,
        "placowka_fields": PLACOWKA_FIELDS,
        "today": dzis(), "poniedzialek": poniedzialek(),
        "tytul": tytul, "kicker": kicker,
        "zakres_domyslny": zakres_domyslny,
        "query": request.query_string.decode("utf-8"),
    }
    ctx.update(extra)
    conn.close()
    return render_template(template, **ctx)


@app.route("/baza")
def baza():
    """Baza główna — to, co koordynator ma do rozdania. Domyślnie nieprzydzielone."""
    return _ekran_leadow("baza.html", zakres_domyslny="nieprzydzielone",
                         tytul="Baza placówek", kicker="Koordynator · rozdawanie leadów")


@app.route("/leady")
def leady():
    """Widok handlowca. Bez wybranego handlowca pokazuje wszystkie przydzielone."""
    return _ekran_leadow("leady.html", zakres_domyslny="przydzielone",
                         tytul="Leady handlowca", kicker="Praca bieżąca")


@app.route("/zbiorczy")
def zbiorczy():
    """Arkusz Julki — te same dane, jej kolumny do odhaczania."""
    return _ekran_leadow("zbiorczy.html", zakres_domyslny="umowione",
                         tytul="Zbiorczy", kicker="Julia · dokumenty i umowy")


@app.route("/niewykorzystane")
def niewykorzystane():
    """Pula zwrotna — stąd koordynator przydziela lead innemu handlowcowi."""
    return _ekran_leadow("niewykorzystane.html", zakres_domyslny="niewykorzystane",
                         tytul="Niewykorzystane rekordy",
                         kicker="Pula zwrotna · do ponownego przydzielenia")


@app.route("/tydzien")
def tydzien():
    """„Wybrane szkoły na tydzień do góry" — plan tygodnia handlowca."""
    return _ekran_leadow("tydzien.html", zakres_domyslny="pin",
                         tytul="Plan tygodnia", kicker="Przypięte · %s" % poniedzialek())


@app.route("/lead/<int:lead_id>")
def lead_detail(lead_id):
    conn = get_conn()
    lead = repo.lead_szczegoly(conn, lead_id)
    if not lead:
        conn.close()
        abort(404)
    ctx = {
        "lead": lead, "slowniki": wszystkie_slowniki(conn),
        "kolory": trener_colors(conn),
        "lead_fields": LEAD_FIELDS, "julia_fields": JULIA_FIELDS,
        "event_fields": EVENT_FIELDS, "placowka_fields": PLACOWKA_FIELDS,
        "today": dzis(),
    }
    conn.close()
    return render_template("lead.html", **ctx)


def _chipy_grafiku(args):
    """
    Filtr na chipach dla kalendarza i dostępności: zakresy „wszystko" i „nazwisko".

    Stary parametr `trener=` (jedna wartość z listy rozwijanej) przepuszczamy
    jako chip „nazwisko". Lista rozwijana zniknęła — działała tylko w widoku
    Agenda, a w Macierzy i Startach udawała filtr, nie robiąc nic — ale stare
    zakładki i linki mają dalej działać, tyle że teraz we wszystkich widokach.
    """
    ch = fl.czytaj(args, fl.ZAKRESY_GRAFIK)
    stary = (args.get("trener") or "").strip()
    if stary and not ch["lista"]:
        ch = fl.czytaj({"osoby": "n:" + stary,
                        "osoby_tryb": args.get("osoby_tryb") or ""},
                       fl.ZAKRESY_GRAFIK)
    return ch


@app.route("/kalendarz")
def kalendarz():
    conn = get_conn()
    miesiace = cv.available_months(conn)
    month = request.args.get("m") or (miesiace[-1] if miesiace else dzis()[:7])
    widok = request.args.get("widok", "macierz")
    weekend = request.args.get("weekend") == "1"
    tylko_zajete = request.args.get("zajete", "1") == "1"
    typ = request.args.get("typ", "")          # '' | DT | CYKLICZNE
    typy = [typ] if typ in ("DT", "CYKLICZNE") else None
    ch = _chipy_grafiku(request.args)

    if widok == "agenda":
        cal = cv.build_agenda(conn, month, weekend=True, typy=typy,
                              chipy=ch["lista"], tryb=ch["tryb"])
    elif widok == "starty":
        cal = cv.build_starty(conn, month, weekend=weekend,
                              chipy=ch["lista"], tryb=ch["tryb"])
    else:
        widok = "macierz"
        cal = cv.build_matrix(conn, month, weekend=weekend,
                              tylko_zajete=tylko_zajete, typy=typy,
                              chipy=ch["lista"], tryb=ch["tryb"])

    ctx = {
        "cal": cal, "widok": widok, "month": month, "miesiace": miesiace,
        "weekend": weekend, "tylko_zajete": tylko_zajete, "typ": typ,
        "ch": ch, "slowniki": wszystkie_slowniki(conn),
        "obciazenie": cv.obciazenie_trenerow(conn, month),
        "today": dzis(),
    }
    conn.close()
    return render_template("kalendarz.html", **ctx)


@app.route("/dostepnosc")
def dostepnosc():
    """
    Dostępność trenerów — w zeszłorocznym pliku POŁOWA treści kalendarza DT
    i jedyne wejście do umawiania ('DOSTĘPNA 8 - 12:00', 'XXX'); w PH Nowy
    zniknęła całkiem. Komórka pokazuje deklarację ORAZ wyliczone wolne okna
    (deklaracja minus to, co już wisi w kalendarzu).
    """
    conn = get_conn()
    miesiace = cv.available_months(conn)
    month = request.args.get("m") or (miesiace[-1] if miesiace else dzis()[:7])
    weekend = request.args.get("weekend") == "1"
    ch = _chipy_grafiku(request.args)
    grid = dv.build_dostepnosc(conn, month, weekend=weekend,
                               chipy=ch["lista"], tryb=ch["tryb"])
    ctx = {
        "grid": grid, "month": month, "miesiace": miesiace, "weekend": weekend,
        "ch": ch, "slowniki": wszystkie_slowniki(conn), "today": dzis(),
    }
    conn.close()
    return render_template("dostepnosc.html", **ctx)


@app.route("/rejony")
def rejony():
    """
    Rejony trenerów — kto po jakich miastach jeździ. Bez tego ranking kandydatów
    nie odróżnia trenera z Knurowa od trenera z Pszczyny. Ekran podpowiada rejon
    z historii zajęć, więc uzupełnienie to zwykle jedno kliknięcie na osobę.
    """
    conn = get_conn()
    ctx = {
        "trenerzy": pz.stan_rejonow(conn),
        "miasta": slownik_values(conn, "miasto"),
        "slowniki": wszystkie_slowniki(conn),
    }
    conn.close()
    return render_template("rejony.html", **ctx)


@app.route("/pulpit")
def pulpit():
    conn = get_conn()
    m = repo.metryki(conn)
    per_h, pon = repo.per_handlowiec(conn, CEL_TYGODNIOWY)
    f_over = repo.pusty_filtr(); f_over["zakres"] = "po_terminie"
    overdue = repo.filtruj_leady(conn, f_over, limit=40)
    miesiace = cv.available_months(conn)
    month = request.args.get("m") or (miesiace[-1] if miesiace else dzis()[:7])
    kolizje = cv.lista_kolizji(conn, month)
    ctx = {
        "m": m, "per_h": per_h, "poniedzialek": pon, "overdue": overdue,
        "kolizje": kolizje, "kolory": trener_colors(conn),
        "obciazenie": cv.obciazenie_trenerow(conn, month),
        "month": month, "month_label": cv.month_label(month), "miesiace": miesiace,
        "cel": CEL_TYGODNIOWY, "today": dzis(),
        # automat zwrotu — koordynator ma widzieć, co WRÓCI, zanim wróci
        "zagrozone": zwrot.zagrozone(conn, w_ciagu=7),
        "do_zwrotu": zwrot.do_zwrotu(conn),
        "karencja": zwrot.KARENCJA_DNI,
    }
    conn.close()
    return render_template("pulpit.html", **ctx)


@app.route("/slowniki")
def slowniki_view():
    conn = get_conn()
    data = {r[0]: slownik(conn, r[0]) for r in SLOWNIK_RODZAJE}
    aliasy = {}
    for row in conn.execute("SELECT id, rodzaj, alias, wartosc FROM aliasy "
                            "ORDER BY rodzaj, alias").fetchall():
        aliasy.setdefault(row["rodzaj"], []).append(dict(row))
    conn.close()
    return render_template("slowniki.html", data=data, rodzaje=SLOWNIK_RODZAJE,
                           aliasy=aliasy, today=dzis())


# ================================================================== API

@app.route("/api/lead/<int:lead_id>", methods=["PATCH"])
def api_lead_update(lead_id):
    d = request.get_json(force=True)
    field, value = d.get("field"), d.get("value")
    conn = get_conn()

    # pola placówki edytujemy z tego samego widoku — rozpoznajemy po nazwie
    if field in PLACOWKA_KEYS:
        value, blad = _walidacja(conn, field, value, PLACOWKA_SLOWNIKI, PLACOWKA_KEYS)
        if blad:
            conn.close(); return jsonify(ok=False, error=blad), 400
        row = conn.execute("SELECT placowka_id FROM leady WHERE id=?", (lead_id,)).fetchone()
        if not row:
            conn.close(); return jsonify(ok=False, error="Nie ma takiego leada"), 404
        przed = conn.execute("SELECT %s v FROM placowki WHERE id=?" % field,
                             (row["placowka_id"],)).fetchone()["v"]
        conn.execute("UPDATE placowki SET %s=?, updated_at=datetime('now') WHERE id=?"
                     % field, (value, row["placowka_id"]))
        zapisz_log(conn, lead_id=lead_id, co="zmiana placówki", pole=field,
                   przed=przed, po=value)
        conn.commit()
        conn.close()
        return jsonify(ok=True)

    value, blad = _walidacja(conn, field, value, LEAD_SLOWNIKI, LEAD_KEYS + ["pin_tydzien"])
    if blad:
        conn.close(); return jsonify(ok=False, error=blad), 400
    stary = conn.execute("SELECT * FROM leady WHERE id=?", (lead_id,)).fetchone()
    if not stary:
        conn.close(); return jsonify(ok=False, error="Nie ma takiego leada"), 404
    conn.execute("UPDATE leady SET %s=?, updated_at=datetime('now') WHERE id=?" % field,
                 (value, lead_id))
    zapisz_log(conn, lead_id=lead_id, co="zmiana pola", pole=field,
               przed=stary[field], po=value)
    conn.commit()
    row = dict(conn.execute(repo.BAZOWY_SELECT + " WHERE l.id=?", (lead_id,)).fetchone())
    conn.close()
    return jsonify(ok=True, po_terminie=repo.czy_po_terminie(row),
                   sukces=(row.get("status_realizacji") or "").startswith(STATUS_SUKCES_PREFIX))


@app.route("/api/przypisz", methods=["POST"])
def api_przypisz():
    """
    Przypisanie leada handlowcowi + termin ostateczny.
    To jest cały „transfer" z opisu klienta: żaden wiersz nie jest kopiowany
    ani usuwany — zmienia się właściciel i status, a widoki same się przestawiają.
    """
    d = request.get_json(force=True)
    ids = d.get("ids") or []
    handlowiec = (d.get("handlowiec") or "").strip()
    deadline = (d.get("deadline") or "").strip() or None
    if not ids:
        return jsonify(ok=False, error="Nie wybrano rekordów"), 400
    conn = get_conn()
    if handlowiec and handlowiec not in slownik_values(conn, "handlowiec"):
        conn.close(); return jsonify(ok=False, error="Nieznany handlowiec"), 400
    n = 0
    for lead_id in ids:
        stary = conn.execute("SELECT handlowiec, status_realizacji FROM leady WHERE id=?",
                             (lead_id,)).fetchone()
        if not stary:
            continue
        nowy_status = "01. Próba kontaktu (Brak konkretów)"
        st = stary["status_realizacji"] or ""
        # nie cofamy statusu, jeśli lead już był dalej w procesie
        if st and not st.startswith("00.") and not st.startswith("04."):
            nowy_status = st
        conn.execute("UPDATE leady SET handlowiec=?, deadline=COALESCE(?, deadline), "
                     "status_realizacji=?, updated_at=datetime('now') WHERE id=?",
                     (handlowiec or None, deadline, nowy_status, lead_id))
        zapisz_log(conn, lead_id=lead_id, co="przypisanie", pole="handlowiec",
                   przed=stary["handlowiec"], po=handlowiec)
        n += 1
    conn.commit()
    conn.close()
    return jsonify(ok=True, n=n)


@app.route("/api/odbierz", methods=["POST"])
def api_odbierz():
    """
    „Koordynator odbiera dostęp" — lead wraca do puli.
    Nie usuwamy i nie przenosimy wiersza: ustawiamy status 04., przez co lead
    wypada z listy roboczej handlowca i pojawia się w „Niewykorzystane rekordy".
    """
    d = request.get_json(force=True)
    ids = d.get("ids") or []
    conn = get_conn()
    n = 0
    for lead_id in ids:
        stary = conn.execute("SELECT handlowiec, status_realizacji FROM leady WHERE id=?",
                             (lead_id,)).fetchone()
        if not stary:
            continue
        conn.execute("UPDATE leady SET status_realizacji=?, handlowiec=NULL, "
                     "pin_tydzien=NULL, updated_at=datetime('now') WHERE id=?",
                     ("04. BRAK KONTAKTU ZE SZKOŁĄ", lead_id))
        zapisz_log(conn, lead_id=lead_id, co="odebranie leada", pole="handlowiec",
                   przed=stary["handlowiec"], po=None)
        n += 1
    conn.commit()
    conn.close()
    return jsonify(ok=True, n=n)


@app.route("/api/pin", methods=["POST"])
def api_pin():
    """Przypięcie leada na plan tygodnia („wybrane szkoły na tydzień do góry")."""
    d = request.get_json(force=True)
    lead_id = d.get("id")
    wlacz = bool(d.get("pin"))
    conn = get_conn()
    val = poniedzialek() if wlacz else None
    conn.execute("UPDATE leady SET pin_tydzien=?, updated_at=datetime('now') WHERE id=?",
                 (val, lead_id))
    zapisz_log(conn, lead_id=lead_id, co="plan tygodnia", pole="pin_tydzien",
               przed=None, po=val)
    conn.commit()
    conn.close()
    return jsonify(ok=True, pin=val)


@app.route("/api/lead", methods=["POST"])
def api_lead_create():
    """Nowa placówka + lead. Prototyp: minimalny zestaw pól, resztę uzupełnia się inline."""
    d = request.get_json(silent=True) or {}
    nazwa = (d.get("nazwa") or "").strip() or "(nowa placówka)"
    conn = get_conn()
    # Wymuszamy słownik TAK SAMO jak przy edycji — inaczej tworzeniem nowego leada
    # dałoby się wprowadzić wartość spoza listy i bałagan wróciłby tą furtką.
    for pole, mapa in (("typ", PLACOWKA_SLOWNIKI), ("miejscowosc", PLACOWKA_SLOWNIKI),
                       ("handlowiec", LEAD_SLOWNIKI)):
        v, blad = _walidacja(conn, pole, d.get(pole), mapa,
                             PLACOWKA_KEYS + LEAD_KEYS)
        if blad:
            conn.close(); return jsonify(ok=False, error="%s: %s" % (pole, blad)), 400
        d[pole] = v
    cur = conn.execute(
        "INSERT INTO placowki (nazwa, typ, miejscowosc, zrodlo) VALUES (?,?,?,?)",
        (nazwa, d.get("typ"), d.get("miejscowosc"), "reka"))
    pid = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO leady (placowka_id, handlowiec, status_realizacji) VALUES (?,?,?)",
        (pid, d.get("handlowiec"), "00. Nieprzydzielony"))
    lid = cur.lastrowid
    zapisz_log(conn, lead_id=lid, co="utworzenie leada", po=nazwa)
    conn.commit()
    conn.close()
    return jsonify(ok=True, id=lid, placowka_id=pid)


@app.route("/api/lead/<int:lead_id>", methods=["DELETE"])
def api_lead_delete(lead_id):
    conn = get_conn()
    conn.execute("DELETE FROM leady WHERE id=?", (lead_id,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ---------------------------------------------------------------- eventy

@app.route("/api/event", methods=["POST"])
def api_event_create():
    """
    Dodanie spotkania. Można dodać DRUGIE i TRZECIE DT temu samemu trenerowi
    w tym samym dniu — to jest wprost odpowiedź na zgłoszony bug.
    Kolizję godzin sygnalizujemy, ale NIE blokujemy: klient chce widzieć,
    że coś się nakłada, a nie mieć zablokowany zapis.
    """
    d = request.get_json(force=True)
    lead_id = d.get("lead_id")
    conn = get_conn()
    if not conn.execute("SELECT 1 FROM leady WHERE id=?", (lead_id,)).fetchone():
        conn.close(); return jsonify(ok=False, error="Nie ma takiego leada"), 404

    dane = {"typ": d.get("typ") or "DT"}
    for k in EVENT_KEYS:
        if k in d and k != "typ":
            v, blad = _walidacja(conn, k, d.get(k), EVENT_SLOWNIKI, EVENT_KEYS)
            if blad:
                conn.close(); return jsonify(ok=False, error=blad), 400
            dane[k] = v
    if dane["typ"] not in slownik_values(conn, "typ_eventu"):
        conn.close(); return jsonify(ok=False, error="Nieznany typ wpisu"), 400

    kolumny = ", ".join(["lead_id"] + list(dane.keys()))
    znaki = ", ".join(["?"] * (len(dane) + 1))
    cur = conn.execute("INSERT INTO eventy (%s) VALUES (%s)" % (kolumny, znaki),
                       [lead_id] + list(dane.values()))
    eid = cur.lastrowid
    zapisz_log(conn, lead_id=lead_id, event_id=eid, co="dodanie spotkania",
               pole=dane["typ"], po="%s %s" % (dane.get("data"), dane.get("godz_od")))
    # gdy dodano DT z datą — status leada idzie na sukces (to jest ich „DT umówione")
    if dane["typ"] == "DT" and dane.get("data"):
        conn.execute("UPDATE leady SET status_realizacji=?, dt=?, "
                     "updated_at=datetime('now') WHERE id=?",
                     ("03. DT umówione", "01. Tak", lead_id))
    conn.commit()

    ostrzezenie = _ostrzezenie_kolizji(conn, eid)
    conn.close()
    return jsonify(ok=True, id=eid, kolizja=ostrzezenie)


@app.route("/api/event/<int:event_id>", methods=["PATCH"])
def api_event_update(event_id):
    d = request.get_json(force=True)
    field, value = d.get("field"), d.get("value")
    conn = get_conn()
    value, blad = _walidacja(conn, field, value, EVENT_SLOWNIKI, EVENT_KEYS)
    if blad:
        conn.close(); return jsonify(ok=False, error=blad), 400
    stary = conn.execute("SELECT * FROM eventy WHERE id=?", (event_id,)).fetchone()
    if not stary:
        conn.close(); return jsonify(ok=False, error="Nie ma takiego wpisu"), 404
    conn.execute("UPDATE eventy SET %s=?, updated_at=datetime('now') WHERE id=?" % field,
                 (value, event_id))
    zapisz_log(conn, lead_id=stary["lead_id"], event_id=event_id, co="zmiana spotkania",
               pole=field, przed=stary[field], po=value)
    conn.commit()
    ostrzezenie = _ostrzezenie_kolizji(conn, event_id)
    conn.close()
    return jsonify(ok=True, kolizja=ostrzezenie)


@app.route("/api/event/<int:event_id>", methods=["DELETE"])
def api_event_delete(event_id):
    conn = get_conn()
    row = conn.execute("SELECT lead_id FROM eventy WHERE id=?", (event_id,)).fetchone()
    conn.execute("DELETE FROM eventy WHERE id=?", (event_id,))
    if row:
        zapisz_log(conn, lead_id=row["lead_id"], co="usunięcie spotkania")
    conn.commit()
    conn.close()
    return jsonify(ok=True)


def _ostrzezenie_kolizji(conn, event_id):
    """Czy dodany/zmieniony wpis nakłada się z innym u tego samego trenera
    albo wypada poza jego zadeklarowaną dostępność. Ostrzeżenie, nie blokada."""
    e = conn.execute("SELECT data, trener, godz_od, godz_do FROM eventy WHERE id=?",
                     (event_id,)).fetchone()
    if not e or not e["data"] or not e["trener"]:
        return None
    inne = conn.execute(
        "SELECT id, godz_od, godz_do FROM eventy "
        "WHERE id<>? AND data=? AND trener=?", (event_id, e["data"], e["trener"])
    ).fetchall()
    for o in inne:
        if cv.overlaps(e["godz_od"], e["godz_do"], o["godz_od"], o["godz_do"]):
            return "Trener %s ma już zajęcia %s w godzinach %s–%s" % (
                e["trener"], e["data"], o["godz_od"] or "?", o["godz_do"] or "?")
    return dv.sprawdz_dostepnosc(conn, e["trener"], e["data"],
                                 e["godz_od"], e["godz_do"])


# ---------------------------------------------------------------- dostępność

def _waliduj_trenera(conn, trener):
    if not trener or trener not in slownik_values(conn, "trener"):
        return "Nieznany trener — wybierz ze słownika"
    return None


def _waliduj_date(data):
    try:
        dt.date.fromisoformat(data or "")
        return None
    except ValueError:
        return "Zła data (oczekiwano RRRR-MM-DD)"


@app.route("/api/dostepnosc", methods=["POST"])
def api_dostepnosc_set():
    """
    Upsert jednej komórki (trener, data). Trzy sensowne kształty wpisu:
    niedostepny=1 · godziny od–do · bez godzin = dostępny cały dzień.
    """
    d = request.get_json(force=True)
    trener, data = d.get("trener"), (d.get("data") or "").strip()
    conn = get_conn()
    blad = _waliduj_trenera(conn, trener) or _waliduj_date(data)
    if blad:
        conn.close(); return jsonify(ok=False, error=blad), 400
    niedostepny = 1 if d.get("niedostepny") else 0
    godz_od = (d.get("godz_od") or "").strip() or None
    godz_do = (d.get("godz_do") or "").strip() or None
    if niedostepny:
        godz_od = godz_do = None
    conn.execute(
        "INSERT INTO dostepnosc (trener, data, godz_od, godz_do, niedostepny, uwagi) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(trener, data) DO UPDATE SET "
        "godz_od=excluded.godz_od, godz_do=excluded.godz_do, "
        "niedostepny=excluded.niedostepny, uwagi=excluded.uwagi",
        (trener, data, godz_od, godz_do, niedostepny,
         (d.get("uwagi") or "").strip() or None))
    zapisz_log(conn, co="dostępność", pole=trener, przed=None,
               po="%s: %s" % (data, "niedostępny" if niedostepny
                              else "%s–%s" % (godz_od or "?", godz_do or "?")
                              if godz_od else "cały dzień"))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@app.route("/api/dostepnosc", methods=["DELETE"])
def api_dostepnosc_del():
    d = request.get_json(force=True)
    conn = get_conn()
    conn.execute("DELETE FROM dostepnosc WHERE trener=? AND data=?",
                 (d.get("trener"), d.get("data")))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@app.route("/api/dostepnosc/zakres", methods=["POST"])
def api_dostepnosc_zakres():
    """
    Wypełnienie zakresu dat naraz — tak realnie wpisywali dostępność: całymi
    tygodniami. NIE nadpisuje istniejących wpisów (chroni ręczne korekty);
    pojedynczą komórkę zawsze można poprawić kliknięciem.
    """
    d = request.get_json(force=True)
    trener = d.get("trener")
    conn = get_conn()
    blad = (_waliduj_trenera(conn, trener) or _waliduj_date(d.get("od"))
            or _waliduj_date(d.get("do")))
    if blad:
        conn.close(); return jsonify(ok=False, error=blad), 400
    od = dt.date.fromisoformat(d["od"])
    do = dt.date.fromisoformat(d["do"])
    if do < od or (do - od).days > 92:
        conn.close(); return jsonify(ok=False, error="Zakres maks. 3 miesiące"), 400
    dni = set(d.get("dni") or [0, 1, 2, 3, 4])     # domyślnie pon–pt
    niedostepny = 1 if d.get("niedostepny") else 0
    godz_od = (d.get("godz_od") or "").strip() or None
    godz_do = (d.get("godz_do") or "").strip() or None
    if niedostepny:
        godz_od = godz_do = None
    n = 0
    dzien = od
    while dzien <= do:
        if dzien.weekday() in dni:
            cur = conn.execute(
                "INSERT OR IGNORE INTO dostepnosc "
                "(trener, data, godz_od, godz_do, niedostepny, uwagi) "
                "VALUES (?,?,?,?,?,?)",
                (trener, dzien.isoformat(), godz_od, godz_do, niedostepny,
                 (d.get("uwagi") or "").strip() or None))
            n += cur.rowcount
        dzien += dt.timedelta(days=1)
    zapisz_log(conn, co="dostępność — zakres", pole=trener,
               po="%s → %s: %d dni" % (d["od"], d["do"], n))
    conn.commit()
    conn.close()
    return jsonify(ok=True, n=n)


@app.route("/api/dostepnosc/demo", methods=["POST"])
def api_dostepnosc_demo():
    """
    PRZYKŁADOWE deklaracje na wybrany miesiąc — wyłącznie do pokazania, jak ekran
    działa. Deterministyczny wzór (bez losowości), oznaczony w uwagach jako demo.
    """
    d = request.get_json(silent=True) or {}
    month = d.get("m") or dzis()[:7]
    conn = get_conn()
    trenerzy = slownik_values(conn, "trener")
    y, m = [int(x) for x in month.split("-")]
    ile = _cal_dni_w_miesiacu(y, m)
    wzory = [("08:00", "16:00", 0), ("08:00", "12:00", 0),
             ("12:00", "18:00", 0), (None, None, 0), (None, None, 1)]
    n = 0
    for i, tr in enumerate(trenerzy):
        for dzien in range(1, ile + 1):
            data = dt.date(y, m, dzien)
            if data.weekday() >= 5:
                continue
            g_od, g_do, nied = wzory[(i + dzien) % len(wzory)]
            cur = conn.execute(
                "INSERT OR IGNORE INTO dostepnosc "
                "(trener, data, godz_od, godz_do, niedostepny, uwagi) "
                "VALUES (?,?,?,?,?,?)",
                (tr, data.isoformat(), g_od, g_do, nied, "demo"))
            n += cur.rowcount
    conn.commit()
    conn.close()
    return jsonify(ok=True, n=n)


def _cal_dni_w_miesiacu(y, m):
    import calendar as _c
    return _c.monthrange(y, m)[1]


# -------------------------------------------------- przydzielanie trenerów

@app.route("/api/kandydaci")
def api_kandydaci():
    """
    Ranking trenerów na spotkanie — „kogo wysłać?".

    Albo dla istniejącego wpisu (`event_id`, kontekst bierzemy z bazy), albo dla
    spotkania, którego jeszcze nie ma (`data`, `godz_od`, `godz_do`, `miasto`) —
    dzięki temu ten sam panel działa przy dodawaniu i przy zmianie obsady.
    """
    conn = get_conn()
    event_id = request.args.get("event_id", type=int)
    kontekst = None
    if event_id:
        kontekst = pz.kontekst_eventu(conn, event_id)
        if not kontekst:
            conn.close(); return jsonify(ok=False, error="Nie ma takiego wpisu"), 404
        data = kontekst["data"]
        godz_od, godz_do = kontekst["godz_od"], kontekst["godz_do"]
        miasto = kontekst["miejscowosc"]
    else:
        data = (request.args.get("data") or "").strip()
        godz_od = request.args.get("godz_od") or None
        godz_do = request.args.get("godz_do") or None
        miasto = request.args.get("miasto") or None
        if _waliduj_date(data):
            conn.close(); return jsonify(ok=False, error="Podaj datę spotkania"), 400

    lista = pz.kandydaci(conn, data, godz_od, godz_do, miasto, event_id)
    grupy = pz.pogrupuj(lista)
    conn.close()
    return jsonify(ok=True, grupy=grupy, kontekst=kontekst, miasto=miasto,
                   data=data, godz_od=godz_od, godz_do=godz_do,
                   n=len(lista), n_wolnych=sum(1 for k in lista
                                               if k["kategoria"] == "wolny"))


# ------------------------------------------------ formularz terenowy (v5)

@app.route("/formularz")
def formularz():
    """
    Ekran dla handlowca w terenie — telefon, tablet, jedna kolumna, cztery kroki.

    Świadomie NIE jest to wariant `/lead/<id>`: tam jest gęsta karta do pracy
    przy biurku, tu ma być formularz, który da się wypełnić stojąc na korytarzu
    z dyrektorem obok. Zapis idzie jednym żądaniem na końcu, a nie polem po polu,
    bo w terenie połączenie potrafi zniknąć w połowie.
    """
    conn = get_conn()
    sl = wszystkie_slowniki(conn)
    handlowiec = (request.args.get("handlowiec") or "").strip()
    moje = []
    if handlowiec:
        f = repo.pusty_filtr()
        f["handlowiec"] = handlowiec
        f["zakres"] = "przydzielone"
        moje = [{"lead_id": r["id"], "placowka_id": r["placowka_id"],
                 "nazwa": r["placowka"], "miejscowosc": r["miejscowosc"] or "",
                 "typ": r["typ_placowki"] or "", "adres": r["adres"] or "",
                 "osoba_kontakt": r["osoba_kontakt"] or "", "telefon": r["telefon"] or "",
                 "mail": r["mail"] or "", "moja": True, "deadline": r["deadline"] or "",
                 "ma_dt": bool(r["dt_data"])}
                for r in repo.filtruj_leady(conn, f, limit=300)]
    ostrzezenia = zwrot.zagrozone(conn, handlowiec=handlowiec) if handlowiec else []
    conn.close()
    return render_template("formularz.html", slowniki=sl, handlowiec=handlowiec,
                           moje=moje, ostrzezenia=ostrzezenia, today=dzis(),
                           dzis_iso=dzis())


@app.route("/api/placowki/szukaj")
def api_placowki_szukaj():
    """
    Podpowiedzi do pola „szukaj szkoły". Wpisanie fragmentu nazwy ALBO miasta
    ma wystarczyć — handlowiec nie ma przewijać listy kilkuset szkół kciukiem.

    Szkoły przydzielone temu handlowcowi wychodzą PRZED pozostałymi, bo w 90%
    przypadków wypełnia formularz właśnie dla jednej z nich.
    """
    q = (request.args.get("q") or "").strip()
    handlowiec = (request.args.get("handlowiec") or "").strip()
    if len(q) < 2:
        return jsonify(ok=True, pozycje=[])
    conn = get_conn()
    like = "%" + pl_fold(q) + "%"
    rows = conn.execute(
        """
        SELECT l.id AS lead_id, l.handlowiec, l.deadline,
               p.id AS placowka_id, p.nazwa, p.miejscowosc, p.typ, p.adres,
               p.osoba_kontakt, p.telefon, p.mail,
               (SELECT COUNT(*) FROM eventy e WHERE e.lead_id=l.id
                AND e.typ='DT' AND e.data IS NOT NULL AND e.data<>'') AS n_dt
        FROM leady l JOIN placowki p ON p.id = l.placowka_id
        WHERE pl_fold(p.nazwa) LIKE ? OR pl_fold(p.miejscowosc) LIKE ?
              OR pl_fold(p.adres) LIKE ?
        ORDER BY p.nazwa LIMIT 60
        """, (like, like, like)).fetchall()
    conn.close()
    poz = []
    for r in rows:
        d = dict(r)
        d["moja"] = bool(handlowiec and d["handlowiec"] == handlowiec)
        d["ma_dt"] = bool(d.pop("n_dt"))
        poz.append(d)
    # moje szkoły na górze, reszta alfabetycznie — sortowanie po stronie serwera,
    # żeby kolejność była ta sama co w liście „moje szkoły" pod polem
    poz.sort(key=lambda d: (not d["moja"], pl_fold(d["nazwa"])))
    return jsonify(ok=True, pozycje=poz[:25])


def _int_lub_none(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


@app.route("/api/formularz", methods=["POST"])
def api_formularz():
    """
    Zapis całego formularza terenowego JEDNYM żądaniem.

    Powód, dla którego to nie jest ciąg wywołań `/api/lead` + `/api/event`:
    w terenie połączenie zrywa się w środku. Albo zapisuje się całość, albo nic —
    inaczej powstaje lead bez DT albo DT bez cyklu i handlowiec nie wie, co ma
    poprawić. Wszystko idzie w jednej transakcji.
    """
    d = request.get_json(silent=True) or {}
    conn = get_conn()

    def blad(msg, kod=400):
        conn.rollback()
        conn.close()
        return jsonify(ok=False, error=msg), kod

    handlowiec = (d.get("handlowiec") or "").strip()
    if handlowiec and handlowiec not in slownik_values(conn, "handlowiec"):
        return blad("Nieznany handlowiec: %s" % handlowiec)

    # --- 1. placówka i lead: istniejąca z listy albo zupełnie nowa -----------
    lead_id = d.get("lead_id")
    nowa = d.get("placowka") or {}
    if lead_id:
        row = conn.execute("SELECT id, placowka_id, handlowiec FROM leady WHERE id=?",
                           (lead_id,)).fetchone()
        if not row:
            return blad("Nie ma takiego leada", 404)
        placowka_id = row["placowka_id"]
        # Formularz nie odbiera szkoły innemu handlowcowi po cichu — właściciela
        # ustawiamy tylko wtedy, gdy szkoła jest niczyja.
        if handlowiec and not (row["handlowiec"] or "").strip():
            conn.execute("UPDATE leady SET handlowiec=? WHERE id=?", (handlowiec, lead_id))
            zapisz_log(conn, lead_id=lead_id, kto=handlowiec, co="przypisanie z formularza",
                       pole="handlowiec", przed=None, po=handlowiec)
    else:
        nazwa = (nowa.get("nazwa") or "").strip()
        if not nazwa:
            return blad("Podaj nazwę placówki")
        pola = {}
        for k in ("typ", "miejscowosc"):
            v, e = _walidacja(conn, k, nowa.get(k), PLACOWKA_SLOWNIKI, PLACOWKA_KEYS)
            if e:
                return blad("%s: %s" % (k, e))
            pola[k] = v
        for k in ("adres", "osoba_kontakt", "telefon", "mail"):
            pola[k] = (nowa.get(k) or "").strip() or None
        cur = conn.execute(
            "INSERT INTO placowki (nazwa, typ, miejscowosc, adres, osoba_kontakt, "
            "telefon, mail, zrodlo) VALUES (?,?,?,?,?,?,?,?)",
            (nazwa, pola["typ"], pola["miejscowosc"], pola["adres"],
             pola["osoba_kontakt"], pola["telefon"], pola["mail"], "formularz"))
        placowka_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO leady (placowka_id, handlowiec, status_realizacji) VALUES (?,?,?)",
            (placowka_id, handlowiec or None, "01. Próba kontaktu (Brak konkretów)"))
        lead_id = cur.lastrowid
        zapisz_log(conn, lead_id=lead_id, kto=handlowiec or "formularz",
                   co="nowa placówka z formularza", po=nazwa)

    # dane kontaktowe da się uzupełnić także dla istniejącej szkoły — handlowiec
    # często dopiero w terenie dowiaduje się, kto tak naprawdę decyduje
    for k in ("osoba_kontakt", "telefon", "mail"):
        v = (d.get("kontakt") or {}).get(k)
        if v and str(v).strip():
            conn.execute("UPDATE placowki SET %s=?, updated_at=datetime('now') "
                         "WHERE id=?" % k, (str(v).strip(), placowka_id))

    miasto = conn.execute("SELECT miejscowosc FROM placowki WHERE id=?",
                          (placowka_id,)).fetchone()["miejscowosc"]

    # --- 2. pola leada ------------------------------------------------------
    for k in ("uwagi", "do_zrobienia", "mail_rodzice", "mail_wynajem", "status_szkoly"):
        if k not in d:
            continue
        v, e = _walidacja(conn, k, d.get(k), LEAD_SLOWNIKI, LEAD_KEYS)
        if e:
            return blad("%s: %s" % (k, e))
        if v:
            conn.execute("UPDATE leady SET %s=?, updated_at=datetime('now') WHERE id=?"
                         % k, (v, lead_id))

    # --- 3. spotkania: DT i cykl -------------------------------------------
    utworzone, kolizja = [], None
    for typ, klucz in (("DT", "dt"), ("CYKLICZNE", "cykl")):
        blok = d.get(klucz) or {}
        if not blok:
            continue
        # DT bez daty nie ma sensu; cykl bez dnia tygodnia też nie
        if typ == "DT" and not (blok.get("data") or "").strip():
            continue
        if typ == "CYKLICZNE" and not (blok.get("cykl_dzien") or "").strip():
            continue

        dane = {"typ": typ}
        for k in EVENT_KEYS:
            if k == "typ" or k not in blok:
                continue
            v, e = _walidacja(conn, k, blok.get(k), EVENT_SLOWNIKI, EVENT_KEYS)
            if e:
                return blad("%s: %s" % (k, e))
            if k in INT_KEYS:
                v = _int_lub_none(v)
            if v not in (None, ""):
                dane[k] = v

        kolumny = ", ".join(["lead_id"] + list(dane.keys()))
        znaki = ", ".join(["?"] * (len(dane) + 1))
        cur = conn.execute("INSERT INTO eventy (%s) VALUES (%s)" % (kolumny, znaki),
                           [lead_id] + list(dane.values()))
        eid = cur.lastrowid
        utworzone.append({"id": eid, "typ": typ})
        zapisz_log(conn, lead_id=lead_id, event_id=eid, kto=handlowiec or "formularz",
                   co="formularz terenowy", pole=typ,
                   po="%s %s" % (dane.get("data") or dane.get("cykl_dzien") or "",
                                 dane.get("godz_od") or ""))
        if typ == "DT":
            conn.execute("UPDATE leady SET status_realizacji=?, dt=?, "
                         "updated_at=datetime('now') WHERE id=?",
                         ("03. DT umówione", "01. Tak", lead_id))

    conn.commit()

    # kolizję liczymy PO commicie — to ostrzeżenie dla człowieka, nie warunek zapisu
    for e in utworzone:
        if e["typ"] == "DT":
            kolizja = _ostrzezenie_kolizji(conn, e["id"])

    nazwa = conn.execute("SELECT nazwa FROM placowki WHERE id=?",
                         (placowka_id,)).fetchone()["nazwa"]
    conn.close()
    return jsonify(ok=True, lead_id=lead_id, placowka_id=placowka_id,
                   placowka=nazwa, miasto=miasto, eventy=utworzone, kolizja=kolizja)


# ------------------------------------------------ auto-zwrot po terminie (v5)

@app.route("/api/zwrot", methods=["POST"])
def api_zwrot():
    """Ręczne uruchomienie automatu — koordynator nie musi czekać na przebieg."""
    conn = get_conn()
    zwrocone = zwrot.wykonaj(conn, kto="koordynator")
    conn.close()
    return jsonify(ok=True, n=len(zwrocone), zwrocone=zwrocone)


@app.route("/api/zwrot/podglad")
def api_zwrot_podglad():
    """Co automat zwróci przy najbliższym przebiegu — do pokazania PRZED wykonaniem."""
    conn = get_conn()
    out = jsonify(ok=True, do_zwrotu=zwrot.do_zwrotu(conn),
                  zagrozone=zwrot.zagrozone(conn),
                  karencja=zwrot.KARENCJA_DNI)
    conn.close()
    return out


@app.route("/api/rejon", methods=["POST"])
def api_rejon_set():
    """Podmiana rejonu trenera: {trener, miasta:[...]}. Miasta walidowane słownikiem."""
    d = request.get_json(force=True)
    trener = d.get("trener")
    conn = get_conn()
    blad = _waliduj_trenera(conn, trener)
    if blad:
        conn.close(); return jsonify(ok=False, error=blad), 400
    znane = set(slownik_values(conn, "miasto"))
    miasta = [m for m in (d.get("miasta") or [])]
    obce = [m for m in miasta if m not in znane]
    if obce:
        conn.close()
        return jsonify(ok=False, error="Nieznane miasto: %s" % ", ".join(obce[:3])), 400
    stare = pz.rejony_map(conn).get(trener, [])
    n = pz.ustaw_rejon(conn, trener, miasta)
    zapisz_log(conn, co="rejon trenera", pole=trener,
               przed=", ".join(stare) or None, po=", ".join(sorted(miasta)) or None)
    conn.commit()
    conn.close()
    return jsonify(ok=True, n=n)


@app.route("/api/rejon/podpowiedz")
def api_rejon_podpowiedz():
    """Miasta z historii zajęć trenera — propozycja rejonu do zaakceptowania."""
    conn = get_conn()
    trener = request.args.get("trener", "")
    blad = _waliduj_trenera(conn, trener)
    if blad:
        conn.close(); return jsonify(ok=False, error=blad), 400
    out = pz.podpowiedz_rejonu(conn, trener)
    conn.close()
    return jsonify(ok=True, miasta=out)


# ---------------------------------------------------------------- słowniki

@app.route("/api/slownik", methods=["POST"])
def api_slownik_add():
    d = request.get_json(force=True)
    rodzaj = d.get("rodzaj")
    wartosc = (d.get("wartosc") or "").strip()
    if not wartosc or rodzaj not in SLOWNIK_KLUCZE:
        return jsonify(ok=False, error="Podaj rodzaj i wartość"), 400
    conn = get_conn()
    kolor = d.get("kolor") or (kolor_z_nazwy(wartosc) if rodzaj == "trener" else None)
    nast = conn.execute("SELECT COALESCE(MAX(sort_order),0)+1 n FROM slowniki "
                        "WHERE rodzaj=?", (rodzaj,)).fetchone()["n"]
    conn.execute("INSERT OR IGNORE INTO slowniki (rodzaj, wartosc, kolor, sort_order) "
                 "VALUES (?,?,?,?)", (rodzaj, wartosc, kolor, nast))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@app.route("/api/slownik/<int:sid>", methods=["PATCH"])
def api_slownik_patch(sid):
    d = request.get_json(force=True)
    conn = get_conn()
    if "kolor" in d:
        conn.execute("UPDATE slowniki SET kolor=? WHERE id=?", (d.get("kolor"), sid))
    if "wartosc" in d and (d.get("wartosc") or "").strip():
        conn.execute("UPDATE slowniki SET wartosc=? WHERE id=?",
                     (d["wartosc"].strip(), sid))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@app.route("/api/slownik/<int:sid>", methods=["DELETE"])
def api_slownik_del(sid):
    """
    Nie pozwalamy usunąć pozycji, która jest w użyciu — inaczej w bazie zostałyby
    wartości spoza słownika i wróciłby ten sam bałagan, który naprawiamy.
    """
    conn = get_conn()
    row = conn.execute("SELECT rodzaj, wartosc FROM slowniki WHERE id=?", (sid,)).fetchone()
    if not row:
        conn.close(); return jsonify(ok=False, error="Nie ma takiej pozycji"), 404
    uzycia = _policz_uzycia(conn, row["rodzaj"], row["wartosc"])
    if uzycia:
        conn.close()
        return jsonify(ok=False, error="Pozycja jest użyta w %d miejscach — "
                                       "najpierw zmień te wpisy" % uzycia), 409
    conn.execute("DELETE FROM slowniki WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


def _policz_uzycia(conn, rodzaj, wartosc):
    n = 0
    for pole, rdz in LEAD_SLOWNIKI.items():
        if rdz == rodzaj:
            n += conn.execute("SELECT COUNT(*) c FROM leady WHERE %s=?" % pole,
                              (wartosc,)).fetchone()["c"]
    for pole, rdz in EVENT_SLOWNIKI.items():
        if rdz == rodzaj:
            n += conn.execute("SELECT COUNT(*) c FROM eventy WHERE %s=?" % pole,
                              (wartosc,)).fetchone()["c"]
    for pole, rdz in PLACOWKA_SLOWNIKI.items():
        if rdz == rodzaj:
            n += conn.execute("SELECT COUNT(*) c FROM placowki WHERE %s=?" % pole,
                              (wartosc,)).fetchone()["c"]
    return n


@app.route("/api/alias", methods=["POST"])
def api_alias_add():
    d = request.get_json(force=True)
    rodzaj = d.get("rodzaj")
    alias = (d.get("alias") or "").strip()
    wartosc = (d.get("wartosc") or "").strip()
    if rodzaj not in SLOWNIK_KLUCZE or not alias or not wartosc:
        return jsonify(ok=False, error="Podaj rodzaj, alias i wartość"), 400
    conn = get_conn()
    if wartosc not in slownik_values(conn, rodzaj):
        conn.close(); return jsonify(ok=False, error="Wartość musi być w słowniku"), 400
    conn.execute("INSERT OR REPLACE INTO aliasy (rodzaj, alias, wartosc) VALUES (?,?,?)",
                 (rodzaj, alias, wartosc))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


@app.route("/api/alias/<int:aid>", methods=["DELETE"])
def api_alias_del(aid):
    conn = get_conn()
    conn.execute("DELETE FROM aliasy WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    return jsonify(ok=True)


# ================================================================== import / eksport

@app.route("/export.xlsx")
def export_xlsx():
    """
    Eksport DOKŁADNIE tego, co widać po filtrach — wprost zgłoszone życzenie klienta.
    Filtry przychodzą tym samym query stringiem, którego użył widok.
    """
    from exporter import build_workbook
    conn = get_conn()
    f = repo.czytaj_filtr(request.args)
    rows = repo.filtruj_leady(conn, f)
    bio = build_workbook(conn, rows, f)
    conn.close()
    nazwa = "leady_%s%s.xlsx" % (dt.date.today().isoformat(),
                                 "_" + f["zakres"] if f["zakres"] else "")
    return send_file(bio, as_attachment=True, download_name=nazwa,
                     mimetype="application/vnd.openxmlformats-officedocument."
                              "spreadsheetml.sheet")


@app.route("/import", methods=["GET", "POST"])
def import_view():
    if request.method == "GET":
        conn = get_conn()
        m = repo.metryki(conn)
        conn.close()
        return render_template("import.html", m=m, today=dzis())

    plik = request.files.get("plik")
    tryb = request.form.get("tryb", "merge")
    zrodlo = request.form.get("zrodlo", "ph_nowy")
    if not plik or not plik.filename.lower().endswith((".xlsx", ".xlsm")):
        flash("Wgraj plik .xlsx", "err")
        return redirect(url_for("import_view"))

    from db import DATA_DIR
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = os.path.join(DATA_DIR, "_upload.xlsx")
    plik.save(tmp)
    try:
        from importer import importuj_ph_nowy, importuj_rspo
        conn = get_conn()
        if zrodlo == "rspo":
            raport = importuj_rspo(conn, tmp, replace=(tryb == "replace"))
        else:
            raport = importuj_ph_nowy(conn, tmp, replace=(tryb == "replace"))
        conn.close()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    flash("Zaimportowano: %d placówek, %d leadów, %d spotkań. Pominięto: %d."
          % (raport.get("placowki", 0), raport.get("leady", 0),
             raport.get("eventy", 0), raport.get("pominiete", 0)), "ok")
    return render_template("import.html", raport=raport, today=dzis(),
                           m=repo.metryki(get_conn()))


@app.route("/api/demo", methods=["POST"])
def api_demo():
    """Wczytanie danych demo (realny arkusz klienta + plansza STARTY) jednym kliknięciem."""
    from importer import wczytaj_demo
    conn = get_conn()
    raport = wczytaj_demo(conn)
    conn.close()
    return jsonify(ok=True, raport=raport)


# ================================================================== wspólne

@app.template_filter("pl_data")
def f_pl_data(v):
    """ISO → dd.mm.rrrr (klient tak czyta daty)."""
    if not v:
        return ""
    try:
        return dt.date.fromisoformat(str(v)[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return v


@app.template_filter("krotka")
def f_krotka(v, n=42):
    s = "" if v is None else str(v)
    return s if len(s) <= n else s[:n - 1] + "…"


@app.template_filter("bez_prefiksu")
def f_bez_prefiksu(v):
    """„04. Zemela" → „Zemela". Prefiks zostaje w danych (klient sortuje po nim),
    ale w ciasnych miejscach UI pokazujemy samą nazwę."""
    if not v:
        return ""
    s = str(v)
    if len(s) > 3 and s[:2].isdigit() and s[2] == "." :
        return s[3:].strip()
    if len(s) > 4 and s[:2].isdigit() and s[2] == "b" and s[3] == ".":
        return s[4:].strip()
    return s


@app.before_request
def _automat_zwrotu():
    """
    Automat zwracający przeterminowane leady wisi na zwykłym ruchu w aplikacji,
    a nie na cronie ani na wątku w tle. Powód praktyczny: cron na VPS potrafi
    cicho przestać działać i nikt nie zauważa tego przez tydzień, a wątek ginie
    przy restarcie gunicorna. Tutaj wystarczy, że ktokolwiek otworzy ekran.

    Sam `przeglad()` pilnuje, żeby realnie przelecieć najwyżej raz na godzinę —
    tu zostaje jedno tanie zapytanie o znacznik czasu.
    """
    if request.endpoint in (None, "static") or request.path.startswith("/static/"):
        return
    conn = get_conn()
    try:
        zwrot.przeglad(conn)
    finally:
        conn.close()


@app.context_processor
def inject_nav():
    # ZAKRESY — opisy chipów filtra (znak, nazwa, dymek); rysuje je makro `pasek_chipow`
    return {"nav_active": request.endpoint, "q_all": request.args.to_dict(),
            "ZAKRESY": fl.ZAKRESY, "profil": opis_profilu()}


bootstrap()

# Własny port, nie 5000. Powód praktyczny: na 5000 startuje domyślnie każda apka
# Flaska i inne narzędzia — przy kilku uruchomionych naraz nowy proces cicho nie
# zajmuje portu, a przeglądarka pokazuje STARĄ aplikację. Godzina szukania błędu
# w kodzie, którego tam nie ma.
PORT_DOMYSLNY = "5301"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", PORT_DOMYSLNY))
    p = opis_profilu()
    print("=" * 62)
    print("  System Leadów v5   ·   profil: %s" % p["etykieta"])
    print("  baza:   %s" % p["sciezka"])
    print("  lokalnie:  http://127.0.0.1:%d/formularz" % port)
    print("  z telefonu w tej samej sieci: http://<IP-komputera>:%d/formularz" % port)
    print("=" * 62)
    app.run(host="0.0.0.0", port=port, debug=True)
