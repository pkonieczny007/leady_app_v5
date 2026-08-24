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

import secrets

from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, abort, send_file, flash, session)

import calendar_view as cv
import dostepnosc_view as dv
import filtry as fl
import obszary
import przydzial as pz
import repo
import uzytkownicy as uz
import zwrot
from db import (get_conn, wszystkie_slowniki, slownik, slownik_values, trener_colors,
                zapisz_log, LEAD_FIELDS, JULIA_FIELDS, EVENT_FIELDS, PLACOWKA_FIELDS,
                LEAD_KEYS, EVENT_KEYS, PLACOWKA_KEYS, SLOWNIK_RODZAJE, SLOWNIK_KLUCZE,
                INT_KEYS, STATUS_SUKCES_PREFIX, kolor_z_nazwy, opis_profilu, pl_fold,
                TYPY_CYKLICZNE)
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

app.permanent_session_lifetime = dt.timedelta(days=uz.DNI_SESJI)
# Ciastko sesji: niedostępne dla JS i nieprzesyłane przy żądaniach z obcych stron.
# Secure włączamy dopiero za HTTPS — na localhost bez tego sesja by nie działała.
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=bool(os.environ.get("HTTPS")))

# ------------------------------------------------------------------ dostęp
#
# Ekrany dostępne BEZ logowania — wyłącznie samo logowanie i pliki statyczne.
# Wszystko inne wymaga konta, bo w bazie są telefony i maile dyrektorów szkół.
JAWNE = {"logowanie", "api_logowanie", "static"}

# Ekrany i akcje wyłącznie dla koordynatora. Handlowiec ma formularz i swoje
# szkoły — reszta to praca koordynatorki, a przypadkowe kliknięcie w „Import"
# albo w słowniki potrafi narobić bałaganu w danych wszystkich naraz.
TYLKO_KOORDYNATOR = {
    "baza", "zbiorczy", "niewykorzystane", "slowniki_view", "import_view",
    "export_xlsx", "pulpit", "rejony", "obszary_view", "uzytkownicy_view",
    "api_przypisz", "api_odbierz", "api_przedluz", "api_slownik_add", "api_slownik_patch",
    "api_slownik_del", "api_alias_add", "api_alias_del", "api_demo",
    "api_zwrot", "api_zwrot_podglad", "api_rejon_set", "api_rejon_podpowiedz",
    "api_lead_delete", "api_uzytkownik", "api_uzytkownik_pin",
    "api_dostepnosc_demo",
    # Kasowanie spotkania BEZ ŚLADU — decyzja z 20.08: „handlowiec może odwołać,
    # a koordynator może odwołać i skasować". Odwołanie zostawia powód i osobę,
    # więc wolno je szerzej; kasowanie zabiera dowód, że temat w ogóle był.
    "api_event_delete",
}

# Zmiana dostępności. Handlowiec jej NIE robi — widzi grafik (bez tego nie umówi
# DT), ale zmiana cudzego wpisu to decyzja koordynatorki. Trener wolno mu zmieniać
# WYŁĄCZNIE własny wiersz; pilnuje tego `_wolno_edytowac_dostepnosc`.
EDYCJA_DOSTEPNOSCI = {"api_dostepnosc_set", "api_dostepnosc_del",
                      "api_dostepnosc_zakres", "api_dostepnosc_dni"}

# Trener ma najwęższy dostęp: swoja dostępność i kalendarz. Leadów i danych
# kontaktowych szkół nie widzi wcale — do swojej pracy ich nie potrzebuje,
# a im mniej osób ma wgląd w telefony dyrektorów, tym lepiej.
DOZWOLONE_TRENER = {"index", "logowanie", "api_logowanie", "wyloguj",
                    "dostepnosc", "kalendarz"} | EDYCJA_DOSTEPNOSCI


def _wolno_edytowac_dostepnosc(trener):
    """Czy zalogowany może ruszyć wiersz tego trenera."""
    u = uz.zalogowany()
    if not u:
        return False
    if u["rola"] == "koordynator":
        return True
    if u["rola"] == "trener":
        return (trener or "").strip() == u["osoba"]
    return False                       # handlowiec: tylko podgląd


# Pola, których handlowiec nie rusza NIGDY — nawet na własnym leadzie.
# `handlowiec` to przypisanie szkoły, a to robi koordynator (ustalenie z 08.08:
# „przypisuje wyłącznie koordynator"). `deadline` to dzień, po którym szkoła
# wraca do puli. Zostawione do swobodnej edycji znaczyły, że handlowiec sam
# sobie przypisuje cudzą szkołę i sam sobie przedłuża termin — a w historii
# zmian wygląda to jak zwykła praca na rekordzie, więc nikt tego nie wyłapie.
POLA_TYLKO_KOORDYNATOR = {"handlowiec", "deadline"}


def _wolno_pisac_do_leada(conn, lead_id):
    """
    Czy zalogowany może ZAPISAĆ coś na tym leadzie.
    Zwraca `None`, gdy wolno, albo parę (komunikat, kod HTTP).

    Zgłoszenie Kasi z 20.08: „Zablokuj PH możliwość edycji danych innego PH, bo
    teraz mogą zmienić dosłownie wszystko". Blokada w interfejsie owszem była —
    i to jest dokładnie ten poziom, który niczego nie blokuje, bo zapis idzie
    zwykłym `fetch`, a adres leada widać w pasku przeglądarki.

    PODGLĄD cudzych rekordów zostaje. Kasia chce widzieć, kto miał szkołę
    wcześniej i co z nią zrobił — odbieramy zapis, nie widok.

    Szkoła niczyja też jest zablokowana: „chcę wziąć tę szkołę" wypadło
    z zakresu 08.08, bo przydziela wyłącznie koordynator.
    """
    u = uz.zalogowany()
    if not u:
        return ("Sesja wygasła — zaloguj się ponownie", 401)
    if u["rola"] != "handlowiec":
        return None                    # koordynator; trener tu nie dojdzie
    row = conn.execute("SELECT handlowiec FROM leady WHERE id=?", (lead_id,)).fetchone()
    if not row:
        return ("Nie ma takiego leada", 404)
    wlasciciel = (row["handlowiec"] or "").strip()
    if not wlasciciel:
        return ("Ta szkoła nie jest jeszcze przypisana — przydziela koordynator", 403)
    if wlasciciel != u["osoba"]:
        return ("Tę szkołę prowadzi %s. Zmiany na cudzej szkole robi koordynator."
                % wlasciciel, 403)
    return None


def _wolno_pisac_do_eventu(conn, event_id):
    """To samo co wyżej, tylko wejściem jest wpis w kalendarzu.

    Osobno, bo bez tego handlowiec mógł skasować cudze DT jednym żądaniem —
    endpoint kasujący istnieje od dawna, tylko nie było go w menu.
    """
    row = conn.execute("SELECT lead_id FROM eventy WHERE id=?", (event_id,)).fetchone()
    if not row:
        return ("Nie ma takiego wpisu", 404)
    return _wolno_pisac_do_leada(conn, row["lead_id"])


def _po_zalogowaniu(rola):
    """Dokąd trafia człowiek zaraz po zalogowaniu — tam, gdzie ma pracować."""
    if rola == "handlowiec":
        return url_for("formularz")
    if rola == "trener":
        return url_for("dostepnosc")
    return url_for("pulpit")


@app.before_request
def _kontrola_dostepu():
    if request.endpoint in JAWNE or request.path.startswith("/static/"):
        return
    u = uz.zalogowany()
    if not u:
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Sesja wygasła — zaloguj się ponownie"), 401
        return redirect(url_for("logowanie", dalej=request.full_path))
    if request.endpoint in TYLKO_KOORDYNATOR and u["rola"] != "koordynator":
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Brak uprawnień"), 403
        flash("Ten ekran prowadzi koordynator.", "err")
        return redirect(_po_zalogowaniu(u["rola"]))
    if u["rola"] == "trener" and request.endpoint not in DOZWOLONE_TRENER:
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Brak uprawnień"), 403
        flash("Konto trenera obejmuje dostępność i kalendarz.", "err")
        return redirect(url_for("dostepnosc"))
    if request.endpoint in EDYCJA_DOSTEPNOSCI and u["rola"] == "handlowiec":
        return jsonify(ok=False,
                       error="Dostępność trenerów zmienia koordynator"), 403


# ------------------------------------------------------------------ CSRF
#
# Zapisy idą przez `fetch`, więc bez tokenu wystarczyłaby obca strona z jednym
# skryptem, żeby zalogowanym handlowcem zmienić dane. Token siedzi w sesji,
# szablony wstawiają go w <meta>, a app.js dokleja do każdego żądania zapisu.

def token_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


@app.before_request
def _kontrola_csrf():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.endpoint in ("api_logowanie", "logowanie"):
        return                     # logowanie samo ustanawia sesję
    podany = request.headers.get("X-CSRF") or (request.form.get("csrf") or "")
    if not podany or not secrets.compare_digest(podany, session.get("csrf", "")):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Nieaktualna sesja — odśwież stronę"), 403
        abort(403)


def dzis():
    return dt.date.today().isoformat()


def poniedzialek(d=None):
    d = d or dt.date.today()
    return (d - dt.timedelta(days=d.weekday())).isoformat()


# Widełki lat dla ekranów kalendarzowych.
#
# Zgłoszone 09.08: w polu „skocz do daty" wystarczyło pomylić się przy wpisywaniu
# roku (`0002` zamiast `2026`) i kalendarz przenosił się do roku 2 naszej ery —
# a że lista miesięcy zawiera tylko te z danymi, nie było czym wrócić. Pole daty
# w przeglądarce przyjmuje cztery cyfry bez zająknięcia, więc sama walidacja
# formatu tu nie wystarcza; potrzebny jest ZAKRES.
#
# Pilnujemy go w OBU miejscach: w polu (min/max — przeglądarka nie da wpisać)
# i na serwerze (adres da się wpisać ręcznie albo wkleić ze starej zakładki).
ROK_MIN, ROK_MAX = 2025, 2035
DATA_MIN = "%d-01-01" % ROK_MIN
DATA_MAX = "%d-12-31" % ROK_MAX


def _sensowna_data(iso):
    """Data w widełkach albo pusty string. Do parametrów z adresu."""
    try:
        d = dt.date.fromisoformat((iso or "").strip())
    except ValueError:
        return ""
    return d.isoformat() if ROK_MIN <= d.year <= ROK_MAX else ""


def _sensowny_miesiac(rrmm):
    """„2026-08" w widełkach albo pusty string."""
    s = (rrmm or "").strip()
    if len(s) != 7 or s[4] != "-":
        return ""
    return s if _sensowna_data(s + "-01") else ""


def _miesiac_ekranu(args, miesiace):
    """
    Który miesiąc pokazać na kalendarzu i dostępności.

    Zgłoszone 09.08: trener ustawia wrzesień w kalendarzu, przechodzi na
    dostępność i widzi październik, a po powrocie kalendarz też skacze na
    październik. Powód: linki w nawigacji nie niosą `m`, więc każdy ekran
    zaczynał od ostatniego miesiąca, w którym cokolwiek jest w bazie.

    Wybór ZAPAMIĘTUJEMY W SESJI i traktujemy jak domyślny na obu ekranach —
    tak samo jak filtr „moje szkoły": jawny wybór człowieka wygrywa z tym,
    co aplikacja uznałaby sama, i przeżywa przejście na sąsiedni ekran.
    Adres z `?m=` dalej wygrywa, bo to świadome wskazanie konkretnego miesiąca.
    """
    z_adresu = _sensowny_miesiac(args.get("m"))
    if z_adresu:
        session["miesiac"] = z_adresu
        return z_adresu
    domyslny = _miesiac_domyslny(miesiace)
    zapamietany = _sensowny_miesiac(session.get("miesiac"))
    # P05 (zgłoszenie K11 Kasi, 20.08): „kalendarz ustawia się na czerwiec na
    # starcie a nie na wrzesień". Zapamiętany wybór nie ma daty ważności, a sesja
    # żyje 30 dni — jedno zajrzenie do minionego miesiąca i człowiek zostaje
    # w nim na tygodnie, na każdym wejściu, bez pojęcia dlaczego. Wybór z
    # PRZESZŁOŚCI przestaje więc wygrywać i pamięć się kasuje; miesiąc przyszły
    # dalej przeżywa przejście na sąsiedni ekran, bo o to chodziło 09.08.
    if zapamietany and zapamietany >= dzis()[:7]:
        return zapamietany
    if zapamietany:
        session["miesiac"] = domyslny
    return domyslny


def _miesiac_domyslny(miesiace):
    """
    Na czym otwiera się kalendarz, gdy nikt nic nie wybrał.

    Bieżący miesiąc, a jeśli nic w nim nie ma — NAJBLIŻSZY PRZYSZŁY z wpisami.
    Poprzednio był to `miesiace[-1]`, czyli miesiąc najdalszy w przyszłość:
    przy zajęciach cyklicznych sięgających pół roku do przodu kalendarz otwierał
    się tam, gdzie nikt nie pracuje. Pusty bieżący miesiąc też jest złą
    odpowiedzią — w sierpniu praca dzieje się we wrześniu.
    """
    teraz = dzis()[:7]
    if not miesiace:
        return teraz
    if teraz in miesiace:
        return teraz
    przyszle = [m for m in miesiace if m >= teraz]
    return przyszle[0] if przyszle else miesiace[-1]


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


# ================================================================== LOGOWANIE

@app.route("/logowanie")
def logowanie():
    u = uz.zalogowany()
    if u:
        return redirect(_po_zalogowaniu(u["rola"]))
    conn = get_conn()
    osoby = uz.do_logowania(conn)
    conn.close()
    return render_template("logowanie.html", osoby=osoby, today=dzis(),
                           serwis=uz.serwis_wlaczony(),
                           dalej=(request.args.get("dalej") or "").strip())


@app.route("/api/logowanie", methods=["POST"])
def api_logowanie():
    d = request.get_json(silent=True) or {}
    osoba = (d.get("osoba") or "").strip()
    pin = (d.get("pin") or "").strip()

    # Bez wskazanej osoby próbujemy PIN-u serwisowego — to jedyna droga wejścia
    # „samym hasłem". Zwykłe konta zawsze wymagają wyboru nazwiska.
    if not osoba:
        u, blad = uz.zaloguj_serwisowo(pin)
        if blad:
            return jsonify(ok=False, error=blad), 401
        conn = get_conn()
        zapisz_log(conn, kto=u["osoba"], co="logowanie serwisowe",
                   po=request.remote_addr or "")
        conn.commit()
        conn.close()
        uz.zapisz_sesje(u)
        session.pop("csrf", None)
        return jsonify(ok=True, osoba=u["osoba"], rola=u["rola"], serwis=True,
                       dalej=url_for("pulpit"))

    conn = get_conn()
    u, blad = uz.zaloguj(conn, osoba, pin)
    conn.close()
    if blad:
        return jsonify(ok=False, error=blad), 401
    uz.zapisz_sesje(u)
    session.pop("csrf", None)          # nowa sesja → nowy token
    return jsonify(ok=True, osoba=u["osoba"], rola=u["rola"],
                   dalej=_po_zalogowaniu(u["rola"]))


@app.route("/wyloguj")
def wyloguj():
    uz.wyczysc_sesje()
    session.pop("csrf", None)
    return redirect(url_for("logowanie"))


@app.route("/uzytkownicy")
def uzytkownicy_view():
    """Panel koordynatora: kto ma konto, kto ma PIN, reset jednym kliknięciem."""
    conn = get_conn()
    konta = uz.lista(conn)
    handlowcy = slownik_values(conn, "handlowiec")
    trenerzy = slownik_values(conn, "trener")
    ostrzezenie = uz.pin_startowy_niezmieniony(conn)
    conn.close()
    # „Bez konta" z OBU słowników osób, z rolą wg słownika. Do 08.08 lista czytała
    # tylko handlowców — trener dopisany w Słownikach nie pojawiał się tu wcale
    # i wyglądało to na zgubiony rekord (zgłoszenie użytkownika).
    maja = {k["osoba"] for k in konta}
    bez_konta = ([{"osoba": o, "rola": "handlowiec"} for o in handlowcy if o not in maja]
                 + [{"osoba": o, "rola": "trener"} for o in trenerzy if o not in maja])
    return render_template("uzytkownicy.html", konta=konta, bez_konta=bez_konta,
                           role=uz.ROLE, pin_startowy=ostrzezenie,
                           max_prob=uz.MAX_PROB, today=dzis())


@app.route("/api/uzytkownik", methods=["POST", "PATCH", "DELETE"])
def api_uzytkownik():
    d = request.get_json(silent=True) or {}
    osoba = (d.get("osoba") or "").strip()
    if not osoba:
        return jsonify(ok=False, error="Podaj osobę"), 400
    conn = get_conn()
    try:
        if request.method == "POST":
            if uz.znajdz(conn, osoba):
                return jsonify(ok=False, error="Takie konto już istnieje"), 400
            pin = uz.losowy_pin()
            uz.utworz(conn, osoba, d.get("rola") or "handlowiec", pin)
            return jsonify(ok=True, osoba=osoba, pin=pin)

        if request.method == "DELETE":
            if osoba == uz.zalogowany()["osoba"]:
                return jsonify(ok=False, error="Nie usuwaj konta, na którym pracujesz"), 400
            uz.usun(conn, osoba)
            return jsonify(ok=True)

        if "rola" in d:
            # Ostatni koordynator nie może zejść do handlowca — zostalibyśmy
            # bez nikogo, kto potrafi nadać PIN i odblokować konto.
            if d["rola"] != "koordynator":
                ilu = conn.execute("SELECT COUNT(*) c FROM uzytkownicy "
                                   "WHERE rola='koordynator' AND aktywny=1").fetchone()["c"]
                obecny = uz.znajdz(conn, osoba)
                if ilu <= 1 and obecny and obecny["rola"] == "koordynator":
                    return jsonify(ok=False,
                                   error="To jedyny koordynator — najpierw ustanów innego"), 400
            uz.ustaw_role(conn, osoba, d["rola"])
        if "aktywny" in d:
            uz.ustaw_aktywny(conn, osoba, d["aktywny"])
        return jsonify(ok=True)
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    finally:
        conn.close()


@app.route("/api/uzytkownik/pin", methods=["POST"])
def api_uzytkownik_pin():
    """
    Nadanie albo reset PIN-u. PIN generuje serwer i zwraca go RAZ, do przekazania
    człowiekowi — nie da się go potem odczytać, w bazie jest tylko hash.
    Koordynator może też podać własny, gdy handlowiec woli zapamiętać coś swojego.
    """
    d = request.get_json(silent=True) or {}
    osoba = (d.get("osoba") or "").strip()
    pin = (d.get("pin") or "").strip() or uz.losowy_pin()
    conn = get_conn()
    try:
        if not uz.znajdz(conn, osoba):
            return jsonify(ok=False, error="Nie ma takiego konta"), 404
        uz.ustaw_pin(conn, osoba, pin)
        zapisz_log(conn, kto=uz.zalogowany()["osoba"], co="nadanie PIN-u", pole=osoba)
        conn.commit()
        return jsonify(ok=True, osoba=osoba, pin=pin)
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    finally:
        conn.close()


# ================================================================== EKRANY

@app.route("/")
def index():
    u = uz.zalogowany()
    return redirect(_po_zalogowaniu(u["rola"]) if u else url_for("logowanie"))


# Ile wierszy na stronę. Bez limitu `/baza` przy 550 leadach generuje ~1,4 MB HTML,
# bo każdy wiersz nosi pełne listy rozwijane (35 trenerów, 23 miejscowości).
NA_STRONE = int(os.environ.get("NA_STRONE", "150"))


def _ekran_leadow(template, zakres_domyslny="", tytul="", kicker="", **extra):
    conn = get_conn()
    f = repo.czytaj_filtr(request.args)
    if not f["zakres"] and zakres_domyslny:
        f["zakres"] = zakres_domyslny

    # FILTR PRZYPIĘTY, ALE ZMIENIALNY — wprost z ustaleń: „konkretny handlowiec
    # żeby domyślnie miał wyfiltrowane swoje dane, przyczepione, ale z możliwością
    # zmiany, które wracają do stanu domyślnego".
    #
    # Rozstrzyga OBECNOŚĆ parametru w adresie, nie jego wartość:
    #   brak `handlowiec` w URL  → wchodzi domyślny (moje szkoły)
    #   `handlowiec=` (puste)    → człowiek świadomie zdjął filtr, szanujemy to
    # Dzięki temu „Wyczyść" i przejście na inny ekran same wracają do domyślnego,
    # a podejrzenie cudzych leadów wymaga jednego kliknięcia i nie jest ukryte.
    ja = uz.zalogowany()
    moj_filtr = False
    if ja and ja["rola"] == "handlowiec" and "handlowiec" not in request.args:
        f["handlowiec"] = ja["osoba"]
        moj_filtr = True
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
        "moj_filtr": moj_filtr,
    }
    ctx.update(extra)
    conn.close()
    return render_template(template, **ctx)


@app.route("/baza")
def baza():
    """Baza główna — to, co koordynator ma do rozdania. Domyślnie nieprzydzielone."""
    # „Może się świecić, że wróciło" (Kasia, 08.08): szkoła zwrócona przez automat
    # ma być widoczna na tle reszty puli. Świeci, dopóki OSTATNI wpis w historii
    # leada to auto-zwrot — pierwszy ruch człowieka (przypisanie, notatka) staje
    # się nowszym wpisem i plakietka gaśnie sama, bez sprzątania.
    conn = get_conn()
    zwroty = {r["lead_id"]: (r["kiedy"] or "")[:10] for r in conn.execute(
        """SELECT l1.lead_id, l1.kiedy FROM log l1
           JOIN (SELECT lead_id, MAX(id) mid FROM log
                 WHERE lead_id IS NOT NULL GROUP BY lead_id) ost
             ON ost.lead_id = l1.lead_id AND ost.mid = l1.id
           WHERE l1.co = 'auto-zwrot po terminie'""")}
    conn.close()
    return _ekran_leadow("baza.html", zakres_domyslny="nieprzydzielone",
                         tytul="Baza placówek", kicker="Koordynator · rozdawanie leadów",
                         zwroty=zwroty)


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

    # TRENER: własne nazwisko wchodzi jako chip PRZYPIĘTY (kłódka), tak samo jak
    # handlowiec dostaje domyślnie swoje szkoły. Trener otwiera grafik po to,
    # żeby zobaczyć SIEBIE — nie 39 osób, wśród których musi się wyszukać.
    #
    # Rozstrzyga OBECNOŚĆ parametru `osoby` w adresie, nie jego wartość:
    #   brak w URL     → wchodzi domyślny, przypięty chip
    #   `osoby=` puste → człowiek świadomie go odpiął, szanujemy to
    # Kłódka sprawia, że chip przeżywa „Wyczyść" i zmianę miesiąca; zdjąć ją
    # można jednym kliknięciem, a wtedy widać cały zespół.
    u = uz.zalogowany()
    ch["moj_filtr"] = False
    if u and u["rola"] == "trener" and "osoby" not in args:
        ch = fl.czytaj({"osoby": "#n:" + u["osoba"]}, fl.ZAKRESY_GRAFIK)
        ch["moj_filtr"] = True
    return ch


# --------------------------------------------------------- filtr typu w kalendarzu
#
# JEDNO źródło dla adresu i dla listy na ekranie. Wcześniej lista pozycji siedziała
# w szablonie, a rozpoznawanie wartości w tej funkcji — dołożenie typu wymagało
# pamiętania o obu miejscach, a rozjechanie się ich znaczyło pozycję na liście,
# która nic nie filtruje (albo wręcz odwrotnie: filtruje na pusto).
#
# Rozdzielamy PRZECINKIEM, nie plusem. W adresie `+` to zakodowana spacja, więc
# `typ=DT+CYKLICZNE` wpisane z palca albo wklejone z notatki przyszłoby jako
# „DT CYKLICZNE" i cicho wpadło w gałąź „nieznana wartość" — czyli filtr
# przestawałby działać dokładnie wtedy, gdy ktoś podaje link dalej.
#
# Kolejność: najpierw wszystko, potem pojedyncze typy, na końcu pary. Lista,
# w której pary i pojedyncze wartości się przeplatają, wymaga czytania całej,
# żeby znaleźć swoją pozycję.
FILTRY_TYPU = [
    ("",                         "— wszystko —",                 None),
    ("DT",                       "tylko DT",                     ("DT",)),
    ("CYKLICZNE",                "tylko CYKLICZNE",              ("CYKLICZNE",)),
    ("CYKLICZNE-PRZEDSZKOLE",    "tylko CYKLICZNE-PRZEDSZKOLE",  ("CYKLICZNE-PRZEDSZKOLE",)),
    ("DT,CYKLICZNE",             "DT i CYKLICZNE",               ("DT", "CYKLICZNE")),
    ("DT,CYKLICZNE-PRZEDSZKOLE", "DT i CYKLICZNE-PRZEDSZKOLE",   ("DT", "CYKLICZNE-PRZEDSZKOLE")),
]
FILTRY_TYPU_MAPA = {klucz: typy for klucz, _, typy in FILTRY_TYPU}


def _typy_kalendarza(args):
    """
    (klucz filtra, lista typów albo None) z parametru `typ`.

    Wartość spoza listy traktujemy jak „wszystko" — stara zakładka z czasów,
    gdy `CYKLICZNE` znaczyło oba warianty cyklu, ma dalej otwierać kalendarz,
    a nie pusty ekran.
    """
    klucz = (args.get("typ") or "").strip()
    if klucz not in FILTRY_TYPU_MAPA:
        klucz = ""
    typy = FILTRY_TYPU_MAPA[klucz]
    return klucz, (list(typy) if typy else None)


@app.route("/kalendarz")
def kalendarz():
    conn = get_conn()
    miesiace = cv.available_months(conn)
    # Skok do konkretnej daty (prośba z 08.08): handlowiec przy dyrektorze
    # wpisuje datę i ma widok tygodnia, w którym ona leży. Data wygrywa
    # z wyborem miesiąca — formularz wysyła oba pola, ale to data jest gestem
    # „zawieź mnie tam", a select miesiąca tylko stał obok.
    #
    # Data spoza widełek (literówka w roku, stara zakładka) jest ignorowana,
    # a nie przenosi kalendarza w rok 2 bez drogi powrotnej — patrz `_sensowna_data`.
    dzien = _sensowna_data(request.args.get("d"))
    month = dzien[:7] if dzien else _miesiac_ekranu(request.args, miesiace)
    if dzien:
        session["miesiac"] = month      # skok do daty też jest wyborem miesiąca
    widok = request.args.get("widok", "macierz")
    weekend = request.args.get("weekend") == "1"
    tylko_zajete = request.args.get("zajete", "1") == "1"
    # P24 (pytanie Zuzi 20.08): „czy można już wyszukiwać bez prowadzącego?".
    # Osobny przełącznik, a nie chip — chipy szukają wpisanego tekstu w polach,
    # a tu chodzi o BRAK wartości, którego żadnym fragmentem nie da się wpisać.
    bez_obsady = request.args.get("bez_obsady") == "1"
    # P30 (Kasia, 20.08) — druga połowa P27. Formularz przestał żądać kompletu
    # danych DT przy zapisie, więc musi być gdzie zobaczyć, czego brakuje.
    do_uzupelnienia = request.args.get("braki") == "1"
    # P31 (Paweł, 20.08): odwołane spotkania widać było TYLKO na karcie
    # konkretnej szkoły. Osobny tryb, nie kolejny filtr obok — pokazane razem
    # z grafikiem wyglądałyby jak zajęcia, które się odbędą.
    odwolane = request.args.get("odwolane") == "1"
    typ, typy = _typy_kalendarza(request.args)
    ch = _chipy_grafiku(request.args)

    if widok == "agenda":
        cal = cv.build_agenda(conn, month, weekend=True, typy=typy,
                              chipy=ch["lista"], tryb=ch["tryb"],
                              bez_obsady=bez_obsady,
                              do_uzupelnienia=do_uzupelnienia, odwolane=odwolane)
    elif widok == "starty":
        cal = cv.build_starty(conn, month, weekend=weekend,
                              chipy=ch["lista"], tryb=ch["tryb"],
                              bez_obsady=bez_obsady,
                              do_uzupelnienia=do_uzupelnienia, odwolane=odwolane)
    else:
        widok = "macierz"
        cal = cv.build_matrix(conn, month, weekend=weekend,
                              tylko_zajete=tylko_zajete, typy=typy,
                              chipy=ch["lista"], tryb=ch["tryb"],
                              bez_obsady=bez_obsady,
                              do_uzupelnienia=do_uzupelnienia, odwolane=odwolane)

    ctx = {
        "cal": cal, "widok": widok, "month": month, "miesiace": miesiace,
        "weekend": weekend, "tylko_zajete": tylko_zajete, "typ": typ,
        "bez_obsady": bez_obsady, "do_uzupelnienia": do_uzupelnienia,
        "odwolane": odwolane,
        "filtry_typu": [(k, e) for k, e, _ in FILTRY_TYPU],
        "ch": ch, "slowniki": wszystkie_slowniki(conn),
        "obciazenie": cv.obciazenie_trenerow(conn, month),
        "today": dzis(), "dzien": dzien,
        "data_min": DATA_MIN, "data_max": DATA_MAX,
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
    # ten sam bezpiecznik i ta sama pamięć wyboru co w kalendarzu — przejście
    # między grafikiem a dostępnością nie ma przestawiać miesiąca
    month = _miesiac_ekranu(request.args, miesiace)
    weekend = request.args.get("weekend") == "1"
    ch = _chipy_grafiku(request.args)
    grid = dv.build_dostepnosc(conn, month, weekend=weekend,
                               chipy=ch["lista"], tryb=ch["tryb"])
    # Kto może co ruszyć: koordynator wszystko, trener wyłącznie swój wiersz,
    # handlowiec nic (widzi grafik, bo bez tego nie umówi DT).
    ja = uz.zalogowany() or {}
    ctx = {
        "grid": grid, "month": month, "miesiace": miesiace, "weekend": weekend,
        "ch": ch, "slowniki": wszystkie_slowniki(conn), "today": dzis(),
        "edycja_wszystkich": ja.get("rola") == "koordynator",
        "moj_wiersz": ja["osoba"] if ja.get("rola") == "trener" else None,
    }
    conn.close()
    return render_template("dostepnosc.html", **ctx)


@app.route("/obszary")
def obszary_view():
    """
    Obszary działania firmy — PODGLĄD zakresu wg rejestru RSPO (M2 migracji).

    Osobno od `/rejony`, bo to dwa różne pojęcia pod podobną nazwą: rejon jest
    CZYJŚ (trener jeździ po miastach), obszar jest FIRMY (gdzie w ogóle
    pracujemy). Ekran tylko pokazuje — obszary zmienia się narzędziem, dopóki
    migracja nie dojdzie do M9. Pomyłka w obszarze przestawia, KTÓRE placówki
    są nasze, więc nie ma powodu dopuszczać do niej klikania przed czasem.
    """
    conn = get_conn()
    ctx = {"lustro": 0, "w_obszarach": 0, "nasze_typy": 0, "obszary": [],
           "suma": {"sp": 0, "przedszkola": 0, "punkty": 0, "zespoly": 0},
           "placowek_roboczych": 0, "z_numerem": 0, "nav_active": "obszary"}
    try:
        ctx["lustro"] = conn.execute(
            "SELECT COUNT(*) FROM rspo_rejestr").fetchone()[0]
    except Exception:
        # Lustra jeszcze nie ma (M1 nieuruchomiony) — ekran ma o tym powiedzieć,
        # a nie wywalić się pięćsetką.
        conn.close()
        return render_template("obszary.html", **ctx)

    ctx["placowek_roboczych"] = conn.execute(
        "SELECT COUNT(*) FROM placowki").fetchone()[0]
    ctx["z_numerem"] = conn.execute(
        "SELECT COUNT(*) FROM placowki WHERE rspo IS NOT NULL AND rspo <> ''"
    ).fetchone()[0]

    TYPY = [("sp", "Szkoła podstawowa"), ("przedszkola", "Przedszkole"),
            ("punkty", "Punkt przedszkolny"),
            ("zespoly", "Zespół szkół i placówek oświatowych")]
    for o in obszary.lista(conn):
        w = {"nazwa": o["nazwa"], "zakresy": o["zakresy"],
             "wszystko": o["placowek_w_lustrze"], "nasze": 0}
        for klucz, typ in TYPY:
            n = conn.execute(
                "SELECT COUNT(*) FROM rspo_obszar ro JOIN rspo_rejestr r "
                "ON r.rspo = ro.rspo WHERE ro.obszar_id = ("
                "SELECT id FROM obszary_dzialania WHERE nazwa = ?) AND r.typ = ?",
                (o["nazwa"], typ)).fetchone()[0]
            w[klucz] = n
            w["nasze"] += n
            ctx["suma"][klucz] += n
        ctx["obszary"].append(w)
        ctx["w_obszarach"] += w["wszystko"]
    ctx["nasze_typy"] = sum(ctx["suma"].values())
    conn.close()
    return render_template("obszary.html", **ctx)


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

    # Właściciel PRZED walidacją pola: cudzego rekordu nie komentujemy nawet
    # komunikatem o błędnej wartości — to też jest informacja o cudzych danych.
    odmowa = _wolno_pisac_do_leada(conn, lead_id)
    if odmowa:
        conn.close(); return jsonify(ok=False, error=odmowa[0]), odmowa[1]
    if field in POLA_TYLKO_KOORDYNATOR and (uz.zalogowany() or {}).get("rola") != "koordynator":
        conn.close()
        return jsonify(ok=False, error="Przypisanie szkoły i termin zwrotu "
                                       "ustala koordynator"), 403

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


@app.route("/api/przedluz", methods=["POST"])
def api_przedluz():
    """
    Masowe przedłużenie terminu ostatecznego o N dni (domyślnie 14 — Kasia
    rozdaje szkoły „na 2 tygodnie", ale liczbę dni można zmienić w pasku).

    Liczymy od terminu, który jeszcze biegnie; dla leada już po terminie —
    od dziś. Inaczej „przedłuż o 14" na szkole przeterminowanej od miesiąca
    dawałoby datę nadal w przeszłości i automat zabrałby ją przy najbliższym
    przebiegu, czyli przycisk wyglądałby na zepsuty.
    """
    d = request.get_json(force=True)
    ids = d.get("ids") or []
    if not ids:
        return jsonify(ok=False, error="Nie wybrano rekordów"), 400
    try:
        dni = int(d.get("dni", 14))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Podaj liczbę dni"), 400
    if not 1 <= dni <= 365:
        return jsonify(ok=False, error="Liczba dni musi być między 1 a 365"), 400
    conn = get_conn()
    n = 0
    for lead_id in ids:
        stary = conn.execute("SELECT deadline FROM leady WHERE id=?",
                             (lead_id,)).fetchone()
        if not stary:
            continue
        start = stary["deadline"] or ""
        if not start or start < dzis():
            start = dzis()
        try:
            nowy = (dt.date.fromisoformat(start) + dt.timedelta(days=dni)).isoformat()
        except ValueError:
            # termin wpisany ręcznie w nieczytelnym formacie — liczymy od dziś,
            # zamiast wysypać całą paczkę zaznaczonych rekordów
            nowy = (dt.date.today() + dt.timedelta(days=dni)).isoformat()
        conn.execute("UPDATE leady SET deadline=?, updated_at=datetime('now') "
                     "WHERE id=?", (nowy, lead_id))
        zapisz_log(conn, lead_id=lead_id, co="przedłużenie terminu", pole="deadline",
                   przed=stary["deadline"], po=nowy)
        n += 1
    conn.commit()
    conn.close()
    return jsonify(ok=True, n=n, dni=dni)


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
    # Plan tygodnia jest własny, ale zapis idzie do wspólnego rekordu — bez tego
    # handlowiec przypinał sobie cudzą szkołę i zostawiał na niej ślad w historii.
    odmowa = _wolno_pisac_do_leada(conn, lead_id)
    if odmowa:
        conn.close(); return jsonify(ok=False, error=odmowa[0]), odmowa[1]
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
    # Właściciel z SESJI, nie z ciała żądania. Ta zasada obowiązuje w całym
    # projekcie (formularz tak robi od początku), ale ten endpoint ją omijał:
    # dało się utworzyć szkołę od razu podpisaną cudzym nazwiskiem.
    ja = uz.zalogowany() or {}
    if ja.get("rola") == "handlowiec":
        d["handlowiec"] = ja["osoba"]
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
    odmowa = _wolno_pisac_do_leada(conn, lead_id)
    if odmowa:
        conn.close(); return jsonify(ok=False, error=odmowa[0]), odmowa[1]

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
    odmowa = _wolno_pisac_do_eventu(conn, event_id)
    if odmowa:
        conn.close(); return jsonify(ok=False, error=odmowa[0]), odmowa[1]
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


@app.route("/api/event/<int:event_id>/odwolaj", methods=["POST"])
def api_event_odwolaj(event_id):
    """
    Odwołanie spotkania ZE ŚLADEM — zamiast kasowania (P08, zgłoszenie K12).

    Kasia, 20.08: „nie widzę też możliwości wykasowania czegoś z kalendarza,
    w razie jakby np. szkoła w ostatnim momencie odmówiła współpracy".

    Kasowanie zabiera dowód, że temat w ogóle był — a to jest dokładnie ta
    informacja, której Kasia szuka w raporcie wykonania („ile się nie udało").
    Dlatego wpis zostaje w bazie, tylko znika z grafiku i przestaje zajmować
    trenerowi termin.

    Kto: koordynator zawsze, handlowiec na SWOJEJ szkole (decyzja z 20.08:
    „handlowiec może odwołać, a koordynator może odwołać i skasować").

    Powód jest wymagany. To trzecia twarda blokada w tym projekcie obok
    słowników i uprawnień, i ma uzasadnienie: odwołanie bez powodu nie różni
    się niczym od pomyłki, a po miesiącu nikt już nie odtworzy, czy szkoła
    odmówiła, czy ktoś kliknął nie w ten wiersz.
    """
    d = request.get_json(silent=True) or {}
    conn = get_conn()
    odmowa = _wolno_pisac_do_eventu(conn, event_id)
    if odmowa:
        conn.close(); return jsonify(ok=False, error=odmowa[0]), odmowa[1]

    e = conn.execute("SELECT lead_id, typ, data, odwolane FROM eventy WHERE id=?",
                     (event_id,)).fetchone()
    ja = uz.zalogowany() or {}
    cofnij = bool(d.get("cofnij"))

    if cofnij:
        if not e["odwolane"]:
            conn.close(); return jsonify(ok=False, error="To spotkanie nie jest odwołane"), 400
        conn.execute("UPDATE eventy SET odwolane=NULL, powod_odwolania=NULL, "
                     "odwolal=NULL, updated_at=datetime('now') WHERE id=?", (event_id,))
        zapisz_log(conn, lead_id=e["lead_id"], event_id=event_id,
                   co="cofnięcie odwołania", przed=e["odwolane"], po=None)
        conn.commit()
        conn.close()
        return jsonify(ok=True, odwolane=False)

    powod = (d.get("powod") or "").strip()
    if not powod:
        conn.close()
        return jsonify(ok=False, error="Napisz, dlaczego odwołujemy — bez tego "
                                       "za miesiąc nikt tego nie odtworzy"), 400
    if e["odwolane"]:
        conn.close(); return jsonify(ok=False, error="To spotkanie jest już odwołane"), 400

    conn.execute("UPDATE eventy SET odwolane=datetime('now'), powod_odwolania=?, "
                 "odwolal=?, updated_at=datetime('now') WHERE id=?",
                 (powod, ja.get("osoba") or "", event_id))
    zapisz_log(conn, lead_id=e["lead_id"], event_id=event_id, co="odwołanie spotkania",
               pole=e["typ"], przed=e["data"], po=powod)

    # Lead ze statusem sukcesu, któremu odwołano OSTATNI aktywny DT, przestaje
    # być domknięty — inaczej szkoła zostałaby zdjęta z listy zadań (P23) mimo
    # tego, że nie ma już żadnego terminu. Wraca do „w trakcie umawiania", bo
    # rozmowa była; do puli nie wraca i handlowca nie traci.
    wrocil = False
    zostalo = conn.execute(
        "SELECT COUNT(*) c FROM eventy WHERE lead_id=? AND typ='DT' "
        "AND data IS NOT NULL AND data<>'' AND (odwolane IS NULL OR odwolane='')",
        (e["lead_id"],)).fetchone()["c"]
    if not zostalo:
        lead = conn.execute("SELECT status_realizacji FROM leady WHERE id=?",
                            (e["lead_id"],)).fetchone()
        stary = lead["status_realizacji"] or ""
        if stary.startswith(STATUS_SUKCES_PREFIX):
            nowy = "02b. DT w trakcie umawiania"
            if nowy in slownik_values(conn, "status_realizacji"):
                conn.execute("UPDATE leady SET status_realizacji=?, dt=NULL, "
                             "updated_at=datetime('now') WHERE id=?",
                             (nowy, e["lead_id"]))
                zapisz_log(conn, lead_id=e["lead_id"], co="status po odwołaniu DT",
                           pole="status_realizacji", przed=stary, po=nowy)
                wrocil = True

    conn.commit()
    conn.close()
    return jsonify(ok=True, odwolane=True, wrocil_do_umawiania=wrocil)


@app.route("/api/event/<int:event_id>", methods=["DELETE"])
def api_event_delete(event_id):
    # Kasowanie bez śladu zostaje przy koordynatorze (jest w TYLKO_KOORDYNATOR).
    # Handlowiec ma odwołanie, które zostawia powód — patrz `api_event_odwolaj`.
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
        "WHERE id<>? AND data=? AND trener=? "
        # odwołane zajęcia nie zajmują terminu — inaczej trener po odwołaniu
        # dalej wyglądałby na zajętego i nikt by go tam nie wysłał (P08)
        "AND (odwolane IS NULL OR odwolane = '')",
        (event_id, e["data"], e["trener"])
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
    if not _wolno_edytowac_dostepnosc(trener):
        conn.close()
        return jsonify(ok=False, error="Trener zmienia wyłącznie swoją dostępność"), 403

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
    trener = d.get("trener")
    conn = get_conn()
    if not _wolno_edytowac_dostepnosc(trener):
        conn.close()
        return jsonify(ok=False, error="Trener zmienia wyłącznie swoją dostępność"), 403
    conn.execute("DELETE FROM dostepnosc WHERE trener=? AND data=?",
                 (trener, d.get("data")))
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
    if not _wolno_edytowac_dostepnosc(trener):
        conn.close()
        return jsonify(ok=False, error="Trener zmienia wyłącznie swoją dostępność"), 403

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


@app.route("/api/dostepnosc/dni", methods=["POST"])
def api_dostepnosc_dni():
    """
    Zapis dostępności dla ZAZNACZONYCH dni — jedna paczka, jedno żądanie.

    Powstało z uwagi trenera po teście z telefonu (09.08): „wypełnianie jest
    nieintuicyjne". Do tej pory były dwie drogi i obie krzywe — klik w komórkę
    (jeden dzień, przeładowanie strony po każdym) albo formularz zakresu nad
    siatką, oderwany od kalendarza i wymagający wpisania dat z klawiatury.
    Trener myśli „w tym tygodniu jestem rano, w przyszłym mnie nie ma", więc
    zaznacza dni palcem i nadaje im wszystkim jedną deklarację.

    Różnica wobec `/zakres`: TU NADPISUJEMY. Zakres świadomie nie rusza
    istniejących wpisów, bo wypełnia hurtem naprzód; tutaj człowiek wskazał
    konkretne dni palcem i oczekuje, że stanie się dokładnie to, co wybrał.

    Tryb `usun` kasuje deklarację (dzień wraca do stanu „nie wiadomo"), co jest
    czymś innym niż `nie` — „niedostępny" to informacja, brak wpisu to jej brak.
    """
    d = request.get_json(force=True)
    trener = d.get("trener")
    conn = get_conn()
    if not _wolno_edytowac_dostepnosc(trener):
        conn.close()
        return jsonify(ok=False, error="Trener zmienia wyłącznie swoją dostępność"), 403
    blad = _waliduj_trenera(conn, trener)
    if blad:
        conn.close(); return jsonify(ok=False, error=blad), 400

    dni = [str(x).strip() for x in (d.get("dni") or []) if str(x).strip()]
    if not dni:
        conn.close(); return jsonify(ok=False, error="Nie zaznaczono dni"), 400
    if len(dni) > 200:
        conn.close(); return jsonify(ok=False, error="Za dużo dni naraz (maks. 200)"), 400
    for data in dni:
        blad = _waliduj_date(data)
        if blad:
            conn.close(); return jsonify(ok=False, error=blad), 400

    tryb = (d.get("tryb") or "caly").strip()
    if tryb not in ("caly", "okno", "nie", "usun"):
        conn.close(); return jsonify(ok=False, error="Nieznany tryb"), 400

    if tryb == "usun":
        for data in dni:
            conn.execute("DELETE FROM dostepnosc WHERE trener=? AND data=?",
                         (trener, data))
        zapisz_log(conn, co="dostępność — usunięcie", pole=trener,
                   po="%d dni" % len(dni))
        conn.commit(); conn.close()
        return jsonify(ok=True, n=len(dni), tryb=tryb)

    godz_od = godz_do = None
    if tryb == "okno":
        godz_od = (d.get("godz_od") or "").strip() or None
        godz_do = (d.get("godz_do") or "").strip() or None
        if not godz_od:
            conn.close()
            return jsonify(ok=False, error="Podaj godzinę początku okna"), 400
        if godz_do and godz_do <= godz_od:
            conn.close()
            return jsonify(ok=False, error="Godzina końca musi być późniejsza"), 400
    niedostepny = 1 if tryb == "nie" else 0
    uwagi = (d.get("uwagi") or "").strip() or None

    for data in dni:
        conn.execute(
            "INSERT INTO dostepnosc (trener, data, godz_od, godz_do, niedostepny, uwagi) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(trener, data) DO UPDATE SET "
            "  godz_od=excluded.godz_od, godz_do=excluded.godz_do, "
            "  niedostepny=excluded.niedostepny, uwagi=excluded.uwagi",
            (trener, data, godz_od, godz_do, niedostepny, uwagi))
    zapisz_log(conn, co="dostępność — zaznaczone dni", pole=trener,
               po="%d dni, tryb %s" % (len(dni), tryb))
    conn.commit()
    conn.close()
    return jsonify(ok=True, n=len(dni), tryb=tryb)


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

def _kto_wypelnia():
    """
    Czyj jest formularz. Handlowiec — zawsze swój, bez pytania i bez możliwości
    podmiany w adresie. Koordynator może wypełnić za kogoś (zdarza się, że dzwoni
    szkoła, a handlowiec jest w terenie), więc jemu wolno wskazać osobę w URL.
    """
    ja = uz.zalogowany()
    if not ja:
        return ""
    if ja["rola"] == "handlowiec":
        return ja["osoba"]
    return (request.args.get("handlowiec") or "").strip()


def _kontekst_formularza(conn, handlowiec):
    """
    Wspólne dane obu wariantów formularza: słowniki, szkoły handlowca
    i ostrzeżenia o zbliżającym się zwrocie do puli.

    Warianty różnią się WYŁĄCZNIE sposobem podania — dane, walidacja i zapis
    są te same. Gdyby się rozjechały, porównanie na spotkaniu nic by nie znaczyło.
    """
    moje = []
    if handlowiec:
        f = repo.pusty_filtr()
        f["handlowiec"] = handlowiec
        f["zakres"] = "przydzielone"
        moje = [_pozycja_planu(r, moja=True) for r in
                repo.filtruj_leady(conn, f, limit=300)]

        # SZKOŁY PRZYPIĘTE GWIAZDKĄ, KTÓRE NALEŻĄ DO KOGO INNEGO.
        # Handlowiec bywa w terenie „przy okazji" pod cudzą szkołą i przypina ją
        # sobie na tydzień. Do 09.08 taka szkoła znikała z formularza, bo lista
        # brała wyłącznie przypisane do niego — czyli gwiazdka działała na
        # `/tydzien`, a w miejscu, gdzie realnie się pracuje, nie znaczyła nic.
        #
        # Kogo przypięcie? Sama kolumna `pin_tydzien` niesie tylko datę, więc
        # autora czytamy z historii zmian (tam `kto` bierze się z sesji).
        # Cudzą szkołę pokazujemy z OSTRZEŻENIEM, a nie po cichu: przypisanie
        # ma swojego właściciela i to on odpowiada za termin.
        mam = {p["lead_id"] for p in moje}
        for r in repo.filtruj_leady(conn, _filtr_pin(), limit=100):
            if r["id"] in mam or not (r["handlowiec"] or "").strip():
                continue
            kto = conn.execute(
                "SELECT kto FROM log WHERE lead_id=? AND co='plan tygodnia' "
                "ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
            if not kto or kto["kto"] != handlowiec:
                continue                      # przypiął ktoś inny — nie moja sprawa
            poz = _pozycja_planu(r, moja=False)
            poz["wlasciciel"] = r["handlowiec"]
            moje.append(poz)
    return {
        "slowniki": wszystkie_slowniki(conn),
        "handlowiec": handlowiec,
        "moje": moje,
        "ostrzezenia": zwrot.zagrozone(conn, handlowiec=handlowiec) if handlowiec else [],
        "today": dzis(),
        "dzis_iso": dzis(),
    }


def _filtr_pin():
    f = repo.pusty_filtr()
    f["zakres"] = "pin"
    return f


def _pozycja_planu(r, moja):
    """Jedna szkoła na liście „Plan na dziś" — wspólna dla wszystkich wariantów."""
    status = r["status_realizacji"] or ""
    return {
        "lead_id": r["id"], "placowka_id": r["placowka_id"],
        "nazwa": r["placowka"], "miejscowosc": r["miejscowosc"] or "",
        "typ": r["typ_placowki"] or "", "adres": r["adres"] or "",
        "osoba_kontakt": r["osoba_kontakt"] or "", "telefon": r["telefon"] or "",
        "mail": r["mail"] or "", "moja": moja,
        "deadline": r["deadline"] or "", "ma_dt": bool(r["dt_data"]),
        "status": status,
        # P23 (zgłoszenie Zuzi 20.08): „dodam jej że byłam i dt ustalone, to ona
        # z tej listy nie znika, słabo bo nadal widzę że mam do zrobienia 12".
        #
        # Do 20.08 „zrobione" brało się WYŁĄCZNIE z datowanego wpisu DT. Kto
        # domknął szkołę samym statusem na karcie leada — a formularz wymagał
        # kompletu sześciu pól, więc zdarzało się to często — zostawał z nią na
        # liście zadań na zawsze. Licznik „12 do zrobienia" liczył wtedy robotę
        # już wykonaną, czyli kłamał w jedyną stronę, która boli.
        "zrobione": bool(r["dt_data"]) or status.startswith(STATUS_SUKCES_PREFIX),
        "pin": bool(r["pin_tydzien"]), "wlasciciel": "",
    }


@app.route("/formularz")
def formularz():
    """
    Wybór wariantu formularza — dwa kafelki do pokazania klientowi.

    Powód istnienia tego ekranu: na spotkaniu przysłali makietę jednego długiego
    formularza, a my uważamy, że w terenie lepiej sprawdzi się podział na kroki.
    Zamiast się o to spierać na słowa, pokazujemy OBA na ich własnych danych
    i niech wybiorą. Oba zapisują tak samo, więc wybór jest odwracalny.
    """
    conn = get_conn()
    sl = wszystkie_slowniki(conn)
    conn.close()
    return render_template("formularz_wybor.html", slowniki=sl,
                           handlowiec=_kto_wypelnia(), today=dzis())


@app.route("/formularz/kroki")
def formularz_kroki():
    """
    WARIANT 1 — cztery kroki, jedna kolumna, telefon.

    Świadomie NIE jest to wariant `/lead/<id>`: tam jest gęsta karta do pracy
    przy biurku, tu ma być formularz, który da się wypełnić stojąc na korytarzu
    z dyrektorem obok. Zapis idzie jednym żądaniem na końcu, a nie polem po polu,
    bo w terenie połączenie potrafi zniknąć w połowie.
    """
    conn = get_conn()
    ctx = _kontekst_formularza(conn, _kto_wypelnia())
    conn.close()
    return render_template("formularz.html", **ctx)


@app.route("/formularz/ciagly")
def formularz_ciagly():
    """
    WARIANT 2 — jeden ciągły formularz przewijany w dół, wierny makiecie klienta
    (`ChatGPT Image 6 sie 2026, 16_33_49.png`): te same sekcje, ta sama kolejność,
    ikony w kółkach, para list „Miejscowość → Placówka".

    Różnice wobec makiety są wyłącznie takie, bez których nie dałoby się tego
    używać na telefonie: dwie kolumny zwijają się do jednej poniżej 700 px,
    a lista placówek zawęża się po wyborze miejscowości (przy 551 szkołach
    niezawężona lista to przewijanie kciukiem przez pół województwa).
    """
    conn = get_conn()
    ctx = _kontekst_formularza(conn, _kto_wypelnia())
    conn.close()
    return render_template("formularz2.html", **ctx)


@app.route("/formularz/v3")
def formularz_v3():
    """
    WARIANT 3 — układ wariantu 2, mocniejsza podpowiedź prowadzącego.

    Powstał z uwag po teście na telefonie (09.08): w v2 dało się wybrać z listy
    trenera niedostępnego albo mającego tego dnia inne zajęcia i dowiedzieć się
    o tym dopiero po zapisie, bo lista rozwijana niosła cały słownik i nie była
    w żaden sposób związana z wynikiem sprawdzenia dostępności.

    Serwer liczył te dane od dawna (`przydzial.kandydaci` zwraca kategorię,
    powód, wolne okna, zajęcia dnia, obciążenie i rejon) — v2 zużywał z tego
    jakąś trzecią część. Tu nie dokładamy zapytań ani nowego API: pokazujemy
    to, co i tak przychodzi w odpowiedzi.

    Zapis, walidacja i ochrona przed dublem są WSPÓLNE z v1 i v2.
    """
    conn = get_conn()
    ctx = _kontekst_formularza(conn, _kto_wypelnia())
    conn.close()
    return render_template("formularz3.html", **ctx)


@app.route("/formularz/cykliczne")
def formularz_cykliczne():
    """
    WARIANT CYKLICZNY — v3 plus realne planowanie zajęć powtarzalnych.

    Powód: do tej pory cykl zapisywał się WYŁĄCZNIE jako reguła „co wtorek,
    od pierwszych zajęć, w nieskończoność". Dla szkoły to działa — grupa idzie
    do czerwca. Dla przedszkola nie: tam umawia się PAKIET, np. pięć spotkań,
    a daty wypadają jak wypadają, bo w międzyczasie jest przerwa świąteczna,
    bal karnawałowy i wyjazd grupy.

    Stąd dwa sposoby wpisania cyklu w jednym formularzu:
      · REGUŁA   — dzień tygodnia + co ile tygodni (jak dotąd, nic nie zmieniamy),
      · TERMINY  — data pierwszych zajęć + ilość, a aplikacja proponuje resztę
                   i pozwala każdą datę poprawić z kalendarza.

    Wybór typu (CYKLICZNE / CYKLICZNE-PRZEDSZKOLE) tylko USTAWIA DOMYŚLNY sposób,
    nie zabiera drugiego. Przedszkole zaczyna od terminów, szkoła od reguły —
    ale przedszkole, które faktycznie ma „co wtorek do czerwca", nie musi
    wyklikiwać trzydziestu dat.
    """
    conn = get_conn()
    ctx = _kontekst_formularza(conn, _kto_wypelnia())
    conn.close()
    return render_template("formularz4.html", **ctx)


@app.route("/formularz/v5")
def formularz_v5():
    """
    WARIANT 5 — kaskada od placówki. Piąty kafelek na ekranie wyboru.

    Klient chce docelowo JEDEN formularz, w którym mieści się wszystko: szkoły
    i przedszkola, DT, cykle, jednorazówki, festyny, VR i sama wizyta bez
    umówienia czegokolwiek. Cztery istniejące warianty są zbudowane wokół
    stałej kolejności sekcji z wyłącznikiem DT — dołożenie do nich sześciu
    rodzajów zajęć dałoby trzecią warstwę przełączników na dwóch istniejących.
    Tutaj sterowanie jest odwrócone: najpierw placówka, potem CO z nią ustalono,
    a sekcje rozsuwają się dopiero po zaznaczeniu.

    DLACZEGO OSOBNY WARIANT, A NIE PRZEBUDOWA v4
    v4 jest właśnie przedmiotem testu u klienta; przebudowa w miejscu
    zniszczyłaby punkt odniesienia w połowie porównania. Piąty przycisk to
    ścieżka, w którą nikt nie wchodzi przypadkiem — handlowiec dalej klika v3,
    a rozgrzebany v5 nikomu nie blokuje pracy.

    Zapis idzie tym samym `POST /api/formularz`, tym samym `klucz_zapisu`
    i tą samą walidacją co v1–v4 — rozszerzonymi ADDYTYWNIE o listę `zajecia`.
    """
    conn = get_conn()
    ctx = _kontekst_formularza(conn, _kto_wypelnia())
    conn.close()
    # Chipy rodzajów biorą się ze SŁOWNIKA, nie z listy wpisanej w HTML —
    # inaczej dołożenie rodzaju zajęć wymagałoby zmiany w kodzie, a klient
    # dodaje pozycje słownika sam, ekranem „Słowniki".
    ctx["chipy"] = [t for t in ctx["slowniki"].get("typ_eventu", [])
                    if t not in CHIPY_POMIJANE]
    return render_template("formularz5.html", **ctx)


# Rodzaje zajęć, których NIE pokazujemy jako chipa w kaskadzie v5.
#   START               — inauguracja grupy; powstaje u koordynatora i z importu,
#                         handlowiec w terenie tego nie wpisuje
#   CYKLICZNE-PRZEDSZKOLE — to nie osobny wybór dla człowieka, tylko ten sam chip
#                         „Cykliczne" przy placówce typu przedszkole (patrz
#                         `typCyklu` w formularz5.js). Handlowiec nie musi
#                         wiedzieć, że w bazie to dwa typy
CHIPY_POMIJANE = ("START", "CYKLICZNE-PRZEDSZKOLE")


@app.route("/api/formularz/geografia")
def api_formularz_geografia():
    """
    Osie geograficzne kaskady v5 — ADAPTER, którego zadaniem jest przeżyć
    migrację na RSPO bez zmiany choćby linijki w przeglądarce.

    Dziś zwraca JEDNĄ oś (miejscowość ze słownika — to samo, co v2–v4 mają
    dziś w `<select id="f2-miasto">`). Po etapach M5/M6 migracji zwróci dwie
    (powiat → miejscowość) i JS narysuje dwa selecty, bo rysuje tyle, ile
    dostał — nie zna nazw kolumn ani liczby poziomów.

    Bez adaptera v5 byłby piątym ekranem do przerobienia przy przełączeniu
    geografii; z nim jest pierwszym, który jest na nie gotowy.
    """
    conn = get_conn()
    # Wartości ze SŁOWNIKA, nie `SELECT DISTINCT` z placówek: słownik trzyma
    # kolejność klienta (prefiksy `01. `–`33. `, po których sortuje), a lista
    # z danych gubi miejscowości, w których akurat nie ma jeszcze ani jednej
    # placówki — czyli dokładnie te, do których dopiero wchodzimy.
    wartosci = slownik_values(conn, "miasto")
    conn.close()
    return jsonify(ok=True, osie=[{
        "poziom": "miejscowosc",
        "etykieta": "Miejscowość",
        "wartosci": wartosci,
    }])


@app.route("/api/formularz/placowki")
def api_formularz_placowki():
    """
    Lista placówek do kaskady v5 — własna, bo `/api/placowki` ma dwa defekty,
    których NIE naprawiamy tam, żeby nie ruszać ekranów będących w teście:

      · robi JOIN z `leady`, więc placówka bez leada jest niewidoczna,
        a placówka z dwoma leadami pokazuje się dwa razy;
      · `/api/placowki/szukaj` tnie LIMIT-em przed wyniesieniem „moich" na górę.

    Tutaj: LEFT JOIN po leadzie (placówka istnieje niezależnie od procesu
    sprzedażowego) i filtr typu, bo po dołożeniu przedszkoli w Katowicach jest
    ich 150 obok 82 szkół — bez filtru lista przestaje być listą.
    """
    os1 = (request.args.get("miejscowosc") or "").strip()
    rodzaj = (request.args.get("rodzaj") or "").strip()     # szkoly | przedszkola | ""
    handlowiec = (request.args.get("handlowiec") or "").strip()
    if not os1:
        return jsonify(ok=True, pozycje=[])

    warunki = ["p.miejscowosc = ?"]
    param = [os1]
    if rodzaj == "szkoly":
        warunki.append("COALESCE(p.typ,'') LIKE '01.%'")
    elif rodzaj == "przedszkola":
        warunki.append("(COALESCE(p.typ,'') LIKE '02.%' OR COALESCE(p.typ,'') LIKE '03.%')")

    conn = get_conn()
    rows = conn.execute("""
        SELECT p.id AS placowka_id, p.nazwa, p.miejscowosc, p.typ, p.adres,
               p.osoba_kontakt, p.telefon, p.mail,
               (SELECT l.id FROM leady l WHERE l.placowka_id = p.id
                 ORDER BY l.id LIMIT 1) AS lead_id,
               (SELECT l.handlowiec FROM leady l WHERE l.placowka_id = p.id
                 ORDER BY l.id LIMIT 1) AS handlowiec
          FROM placowki p
         WHERE %s
         ORDER BY p.nazwa
    """ % " AND ".join(warunki), param).fetchall()
    conn.close()

    poz = []
    for r in rows:
        d = dict(r)
        d["moja"] = bool(handlowiec and d["handlowiec"] == handlowiec)
        poz.append(d)
    # „Moje" na górze — w terenie handlowiec w 9 przypadkach na 10 wypełnia
    # formularz dla własnej szkoły (P06). Sortowanie po WYBRANIU wszystkich,
    # nie przez LIMIT w zapytaniu — to był defekt starego szukania.
    poz.sort(key=lambda x: (not x["moja"], x["nazwa"] or ""))
    return jsonify(ok=True, pozycje=poz)


@app.route("/api/placowki")
def api_placowki():
    """
    Placówki w danej miejscowości — do pary list „Miejscowość → Placówka"
    z wariantu 2. Bez zawężenia lista miałaby 551 pozycji.
    """
    miasto = (request.args.get("miejscowosc") or "").strip()
    handlowiec = (request.args.get("handlowiec") or "").strip()
    if not miasto:
        return jsonify(ok=True, pozycje=[])
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT l.id AS lead_id, l.handlowiec,
               p.id AS placowka_id, p.nazwa, p.miejscowosc, p.typ, p.adres,
               p.osoba_kontakt, p.telefon, p.mail
        FROM leady l JOIN placowki p ON p.id = l.placowka_id
        WHERE p.miejscowosc = ? ORDER BY p.nazwa
        """, (miasto,)).fetchall()
    conn.close()
    poz = []
    for r in rows:
        d = dict(r)
        d["moja"] = bool(handlowiec and d["handlowiec"] == handlowiec)
        poz.append(d)
    return jsonify(ok=True, pozycje=poz)


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


#: ile najwyżej terminów przyjmiemy w jednym pakiecie. Nie jest to ograniczenie
#: dziedziny (przedszkola umawiają 4–10), tylko bezpiecznik: pole „ilość zajęć"
#: przyjmuje liczbę od człowieka, a wpisane 500 zrobiłoby 500 wierszy i kalendarz
#: nie do przewinięcia. Powyżej tej wartości ODMAWIAMY zamiast obciąć po cichu —
#: cicha obcinka wygląda jak zapisane, a nie jest.
MAX_TERMINOW_CYKLU = 60


def _terminy_cyklu(blok):
    """
    Lista konkretnych dat zajęć z formularza → wiersze do `terminy_cyklu`.

    Odsiewamy puste i zdublowane daty. Duble biorą się z realnego zachowania:
    handlowiec zmienia trzeci termin na datę czwartego i chwilę ma dwa te same.
    Zapis dwóch zajęć tego samego dnia o tej samej godzinie byłby fałszem
    w kalendarzu, więc zostaje pierwsze wystąpienie.

    Kolejność (`nr`) liczymy PO posortowaniu dat, a nie z kolejności pól —
    „zajęcia nr 3" mają znaczyć trzecie w czasie, bo tak je liczy i rodzic,
    i koordynatorka rozliczająca pakiet.
    """
    surowe = blok.get("terminy")
    if not isinstance(surowe, list):
        return []
    widziane, czyste = set(), []
    for poz in surowe[:MAX_TERMINOW_CYKLU + 2]:
        if not isinstance(poz, dict):
            continue
        data = (poz.get("data") or "").strip()[:10]
        if not data or data in widziane:
            continue
        try:
            dt.date.fromisoformat(data)
        except ValueError:
            continue                       # literówka w dacie nie wywraca zapisu
        widziane.add(data)
        czyste.append({"data": data,
                       "godz_od": (poz.get("godz_od") or "").strip() or None,
                       "godz_do": (poz.get("godz_do") or "").strip() or None})
    czyste.sort(key=lambda t: t["data"])
    for i, t in enumerate(czyste, 1):
        t["nr"] = i
    return czyste


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

    # --- 0. ochrona przed dublem po zerwanym połączeniu ---------------------
    # Scenariusz: zapis doszedł, ale odpowiedź nie wróciła. Formularz uznaje to
    # za błąd i proponuje „Ponów wysyłkę". Bez tego druga próba tworzyłaby drugą
    # szkołę i drugie DT. Klucz nadaje przeglądarka — jeden na próbę wysyłki.
    klucz_zapisu = (d.get("klucz_zapisu") or "").strip()
    if klucz_zapisu:
        byl = conn.execute("SELECT odpowiedz FROM zapisy_formularza WHERE klucz=?",
                           (klucz_zapisu,)).fetchone()
        if byl:
            conn.close()
            import json as _json
            odp = _json.loads(byl["odpowiedz"])
            odp["powtorka"] = True          # dla formularza: „to już było zapisane"
            return jsonify(odp)

    # Właściciel wpisu bierze się z SESJI. Gdyby szedł z ciała żądania, każdy
    # zalogowany mógłby podpisać się cudzym nazwiskiem.
    handlowiec = _kto_wypelnia() or (d.get("handlowiec") or "").strip()
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
    # `status_realizacji` doszedł 20.08 (P22, zgłoszenie Kasi): formularz musi
    # umieć zapisać wizytę, która NIE skończyła się umówieniem DT. Wartość idzie
    # przez słownik jak każda inna, więc nie da się tędy wstawić czegoś spoza
    # listy. Sekcja 3 (spotkania) wykonuje się PÓŹNIEJ i przy realnym DT
    # nadpisze to na „03. DT umówione" — i tak ma być: termin bije deklarację.
    for k in ("uwagi", "do_zrobienia", "mail_rodzice", "mail_wynajem",
          "status_szkoly", "cykle", "status_realizacji"):
        if k not in d:
            continue
        v, e = _walidacja(conn, k, d.get(k), LEAD_SLOWNIKI, LEAD_KEYS)
        if e:
            return blad("%s: %s" % (k, e))
        if v:
            conn.execute("UPDATE leady SET %s=?, updated_at=datetime('now') WHERE id=?"
                         % k, (v, lead_id))

    # --- 3. spotkania: DT, cykl i (v5) lista zajęć ---------------------------
    #
    # ROZSZERZENIE JEST ADDYTYWNE — TO WARUNEK, NIE STYL
    # v5 umawia w jednym wyjściu w teren kilka rzeczy naraz (DT + festyn, cykl
    # w dwóch grupach), więc wysyła listę `zajecia`. Stare warianty wysyłają
    # dwa bloki `dt`/`cykl` jak dotąd i mają tego NIE ZAUWAŻYĆ: cztery warianty
    # istnieją po to, żeby klient porównywał UKŁAD, a nie funkcje. Gdyby v5
    # zmienił kontrakt, porównanie przestałoby cokolwiek znaczyć.
    zajecia_v5 = []
    for z in (d.get("zajecia") or []):
        if isinstance(z, dict) and (z.get("typ") or "").strip():
            zajecia_v5.append(((z.get("typ") or "").strip(), z))

    utworzone, kolizja = [], None
    for typ, blok in ([("DT", d.get("dt") or {}), ("CYKLICZNE", d.get("cykl") or {})]
                      + zajecia_v5):
        if not blok:
            continue

        # Wariant cyklu wybiera formularz („zwykły" albo przedszkolny). Bierzemy
        # go z bloku, ale przez słownik `typ_eventu` — inaczej wystarczyłaby
        # literówka w JS, żeby do bazy wjechał typ, którego kalendarz nie zna,
        # a wpis zniknąłby po cichu.
        if typ == "CYKLICZNE":
            zadany = (blok.get("typ") or "").strip()
            if zadany:
                if zadany not in TYPY_CYKLICZNE:
                    return blad("Nieznany typ zajęć cyklicznych: %s" % zadany)
                typ = zadany
        elif typ != "DT":
            # Rodzaj z chipa v5. Twarda blokada po słowniku TEGO profilu, nie po
            # stałej w kodzie: `CYKLICZNE-PRZEDSZKOLE" dawało się kiedyś zapisać
            # (walidacja szła po stałej), ale nie poprawić — bo słownik produkcji
            # go nie znał. Jedna blokada w obie strony zamyka tę klasę usterek.
            if typ not in slownik_values(conn, "typ_eventu"):
                return blad("Nieznany rodzaj zajęć: %s" % typ)

        # Terminy z listy — pakiet konkretnych dat zamiast reguły „co wtorek".
        terminy = _terminy_cyklu(blok) if typ in TYPY_CYKLICZNE else []
        if len(terminy) > MAX_TERMINOW_CYKLU:
            return blad("Za dużo terminów w pakiecie (%d, najwyżej %d). "
                        "Podziel zajęcia na dwa wpisy."
                        % (len(terminy), MAX_TERMINOW_CYKLU))

        # Wpis bez daty jest wpisem NIEWIDOCZNYM w kalendarzu — a taki jest
        # gorszy niż jego brak, bo wygląda na zrobiony (lekcja z 10.08). Cykl
        # ma dwie drogi do daty: regułę „co wtorek" albo listę terminów.
        if typ in TYPY_CYKLICZNE:
            if not (blok.get("cykl_dzien") or "").strip() and not terminy:
                continue
        elif not (blok.get("data") or "").strip():
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

        # Pierwszy termin z listy jest jednocześnie `data` eventu. Nie jest to
        # duplikat dla wygody: cała reszta aplikacji (kalendarz, sortowania,
        # statystyki, `WHERE e.data IS NOT NULL`) opiera się na tej kolumnie
        # i pakiet bez niej byłby wpisem bez daty — czyli niewidocznym.
        if terminy and not (dane.get("data") or "").strip():
            dane["data"] = terminy[0]["data"]

        kolumny = ", ".join(["lead_id"] + list(dane.keys()))
        znaki = ", ".join(["?"] * (len(dane) + 1))
        cur = conn.execute("INSERT INTO eventy (%s) VALUES (%s)" % (kolumny, znaki),
                           [lead_id] + list(dane.values()))
        eid = cur.lastrowid
        for t in terminy:
            conn.execute("INSERT OR REPLACE INTO terminy_cyklu "
                         "(event_id, nr, data, godz_od, godz_do) VALUES (?,?,?,?,?)",
                         (eid, t["nr"], t["data"], t["godz_od"], t["godz_do"]))
        utworzone.append({"id": eid, "typ": typ, "terminy": len(terminy)})
        zapisz_log(conn, lead_id=lead_id, event_id=eid, kto=handlowiec or "formularz",
                   co="formularz terenowy", pole=typ,
                   po="%s %s%s" % (dane.get("data") or dane.get("cykl_dzien") or "",
                                   dane.get("godz_od") or "",
                                   " · %d terminów z listy" % len(terminy) if terminy else ""))
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

    odpowiedz = {"ok": True, "lead_id": lead_id, "placowka_id": placowka_id,
                 "placowka": nazwa, "miasto": miasto, "eventy": utworzone,
                 "kolizja": kolizja}
    if klucz_zapisu:
        import json as _json
        conn.execute("INSERT OR REPLACE INTO zapisy_formularza "
                     "(klucz, lead_id, odpowiedz) VALUES (?,?,?)",
                     (klucz_zapisu, lead_id, _json.dumps(odpowiedz)))
        conn.commit()
    conn.close()
    return jsonify(odpowiedz)


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
    # Osoba dopisana do słownika dostaje konto OD RAZU — bez PIN-u, więc jeszcze
    # się nie zaloguje (PIN nadaje koordynator w Kontach, jak przy bootstrapie).
    # Do 08.08 konta powstawały tylko przy pierwszym starcie profilu i trener
    # dodany później w Słownikach nie istniał w Kontach — nikt nie wiedział czemu.
    if rodzaj in ("handlowiec", "trener") and not uz.znajdz(conn, wartosc):
        uz.utworz(conn, wartosc, rodzaj)
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
            "ZAKRESY": fl.ZAKRESY, "profil": opis_profilu(),
            "ja": uz.zalogowany(), "csrf": token_csrf(),
            # Szablony sprawdzają „czy to cykl" w kilku miejscach (kafel, plansza
            # STARTY, plakietka „cykl #n"). Wpisany na sztywno napis 'CYKLICZNE'
            # pomijałby wariant przedszkolny — a pominięcie w kalendarzu wygląda
            # jak brak danych, nie jak brak obsługi.
            "TYPY_CYKLICZNE": TYPY_CYKLICZNE,
            "serwis_wlaczony": uz.serwis_wlaczony()}


bootstrap()

# Konta: handlowcy ze słownika (bez PIN-u — nada go koordynator) plus jedno
# konto koordynatora z PIN-em startowym, żeby dało się w ogóle wejść.
with app.app_context():
    _c = get_conn()
    _info = uz.bootstrap_konta(_c, slownik_values(_c, "handlowiec"),
                               slownik_values(_c, "trener"))
    _c.close()
    if _info["koordynator"]:
        print("UWAGA: utworzono konto 'Koordynator' z PIN-em startowym %s — "
              "zmień go w panelu /uzytkownicy" % _info["koordynator"])
    if uz.serwis_wlaczony():
        print("!" * 62)
        print("  TRYB SERWISOWY WŁĄCZONY — jeden PIN wpuszcza bez wyboru osoby,")
        print("  na uprawnienia koordynatora. Wyłącz przed wdrożeniem: usuń")
        print("  zmienną PIN_SERWISOWY i zrestartuj aplikację.")
        print("!" * 62)

# Własny port, nie 5000. Powód praktyczny: na 5000 startuje domyślnie każda apka
# Flaska i inne narzędzia — przy kilku uruchomionych naraz nowy proces cicho nie
# zajmuje portu, a przeglądarka pokazuje STARĄ aplikację. Godzina szukania błędu
# w kodzie, którego tam nie ma.
PORT_DOMYSLNY = "5301"

def _port_zajety(port):
    """
    Czy ktoś już nasłuchuje na tym porcie.

    Windows pozwala DWÓM procesom podpiąć się pod ten sam port, bo Werkzeug
    ustawia SO_REUSEADDR. Skutek jest paskudny: stary i nowy serwer działają
    naraz, a to, który odpowie, jest losowe — zmiana w kodzie „raz działa,
    raz nie". Lepiej odmówić startu z czytelnym komunikatem.
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    port = int(os.environ.get("PORT", PORT_DOMYSLNY))
    # Reloader Flaska uruchamia aplikację drugi raz w procesie potomnym
    # (`WERKZEUG_RUN_MAIN`). Wtedy port trzyma już nasz własny rodzic i sprawdzanie
    # go zakończyłoby się odmową startu przy każdym przeładowaniu kodu.
    if not os.environ.get("WERKZEUG_RUN_MAIN") and _port_zajety(port):
        raise SystemExit(
            "Port %d jest już zajęty — najpewniej działa starsza kopia aplikacji.\n"
            "Zatrzymaj ją, zanim uruchomisz nową (Windows pozwala obu nasłuchiwać\n"
            "naraz i wtedy nie wiadomo, która odpowiada):\n"
            "  PowerShell:  Get-Process python* | Stop-Process -Force\n"
            "  albo uruchom na innym porcie:  $env:PORT=\"5302\"; python app.py" % port)
    p = opis_profilu()
    print("=" * 62)
    print("  System Leadów v5   ·   profil: %s" % p["etykieta"])
    print("  baza:   %s" % p["sciezka"])
    print("  lokalnie:  http://127.0.0.1:%d/formularz" % port)
    print("  z telefonu w tej samej sieci: http://<IP-komputera>:%d/formularz" % port)
    print("=" * 62)
    app.run(host="0.0.0.0", port=port, debug=True)
