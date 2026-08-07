# -*- coding: utf-8 -*-
"""
Konta, PIN-y i role.

Ze spotkania 06.08: „handlowiec żeby miał swój profil i admin żeby miał swój".
Do v4 aplikacja nie miała logowania w ogóle — każdy z linkiem widział i edytował
wszystko, w tym telefony i maile dyrektorów szkół. Do pokazu na spotkaniu to było
bez znaczenia; od wtorku aplikacja idzie do internetu, więc przestaje być.

DLACZEGO PIN, A NIE HASŁO
Handlowiec loguje się na telefonie, na stojąco, w szkolnym korytarzu. Hasło
z wielką literą i znakiem specjalnym wpisywane kciukiem to gwarancja, że po
tygodniu wszyscy będą mieli zapisane w notatniku „Haslo123!" albo poproszą
o wyłączenie logowania. Cztery cyfry + sesja na 30 dni to kompromis, który
ludzie realnie utrzymają.

Czym to NIE jest: PIN nie chroni przed kimś, kto ma dostęp do odblokowanego
telefonu handlowca. Chroni przed przypadkowym wejściem z linku i rozdziela
role — i tyle ma robić. Właściwą granicą jest HTTPS i to, że adres nie krąży
po internecie.

DWIE ROLE, bo tyle wynika z ich pracy:
  koordynator  rozdaje szkoły, pilnuje terminów, prowadzi słowniki i import
  handlowiec   wypełnia formularz i pracuje na swoich szkołach
"""
import hashlib
import hmac
import os
import secrets

from flask import session

ROLE = ("koordynator", "handlowiec")

# Iteracje PBKDF2. 200k to sensowny kompromis dla czterocyfrowego PIN-u:
# przy takiej przestrzeni (10 000 kombinacji) i tak jedyną realną obroną jest
# limit prób, ale wolne hashowanie znacząco podnosi koszt ataku na wykradziony
# plik bazy — a baza wisi na VPS w wolumenie dockera.
ITERACJE = 200_000

MAX_PROB = 5              # po tylu nieudanych próbach konto się blokuje
DNI_SESJI = 30            # handlowiec nie ma logować się co rano w terenie


def zahashuj(pin, sol=None):
    """(sól, hash) — sól losowa na konto, żeby dwa te same PIN-y dały różne hashe."""
    sol = sol or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", str(pin).encode("utf-8"),
                            sol.encode("utf-8"), ITERACJE)
    return sol, h.hex()


def sprawdz_pin(pin, sol, hash_zapisany):
    _, h = zahashuj(pin, sol)
    # compare_digest zamiast == : porównanie stałoczasowe, żeby czas odpowiedzi
    # nie zdradzał, ile początkowych znaków się zgadza
    return hmac.compare_digest(h, hash_zapisany or "")


def poprawny_format(pin):
    p = str(pin or "").strip()
    return len(p) == 4 and p.isdigit()


# ------------------------------------------------------------------ schemat

def init(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS uzytkownicy (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          osoba TEXT NOT NULL UNIQUE,   -- wartość ze słownika `handlowiec`, np. „01. Sacawa”
          rola TEXT NOT NULL,
          sol TEXT,
          pin_hash TEXT,
          aktywny INTEGER DEFAULT 1,
          nieudane INTEGER DEFAULT 0,   -- licznik błędnych PIN-ów pod rząd
          ostatnie_logowanie TEXT,
          created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()


# ------------------------------------------------------------------ konta

def lista(conn):
    return [dict(r) for r in conn.execute(
        "SELECT id, osoba, rola, aktywny, nieudane, ostatnie_logowanie, "
        "       CASE WHEN pin_hash IS NULL OR pin_hash='' THEN 0 ELSE 1 END AS ma_pin "
        "FROM uzytkownicy ORDER BY rola DESC, osoba")]


def znajdz(conn, osoba):
    r = conn.execute("SELECT * FROM uzytkownicy WHERE osoba=?", (osoba,)).fetchone()
    return dict(r) if r else None


def do_logowania(conn):
    """Osoby, które mogą się zalogować — do listy na ekranie logowania.
    Konta bez ustawionego PIN-u pomijamy: wybranie ich prowadziłoby donikąd."""
    return [r["osoba"] for r in conn.execute(
        "SELECT osoba FROM uzytkownicy WHERE aktywny=1 "
        "AND pin_hash IS NOT NULL AND pin_hash<>'' ORDER BY rola DESC, osoba")]


def utworz(conn, osoba, rola, pin=None):
    if rola not in ROLE:
        raise ValueError("Nieznana rola: %s" % rola)
    sol = pin_hash = None
    if pin is not None:
        if not poprawny_format(pin):
            raise ValueError("PIN musi mieć dokładnie 4 cyfry")
        sol, pin_hash = zahashuj(pin)
    conn.execute(
        "INSERT INTO uzytkownicy (osoba, rola, sol, pin_hash) VALUES (?,?,?,?)",
        (osoba, rola, sol, pin_hash))
    conn.commit()
    return znajdz(conn, osoba)


def ustaw_pin(conn, osoba, pin):
    """Ustawienie/reset PIN-u odblokowuje też konto — koordynator robi jedno i drugie
    tym samym ruchem, bo w praktyce zawsze idą razem („zapomniałem, zablokowało")."""
    if not poprawny_format(pin):
        raise ValueError("PIN musi mieć dokładnie 4 cyfry")
    sol, h = zahashuj(pin)
    conn.execute("UPDATE uzytkownicy SET sol=?, pin_hash=?, nieudane=0, aktywny=1 "
                 "WHERE osoba=?", (sol, h, osoba))
    conn.commit()


def ustaw_role(conn, osoba, rola):
    if rola not in ROLE:
        raise ValueError("Nieznana rola: %s" % rola)
    conn.execute("UPDATE uzytkownicy SET rola=? WHERE osoba=?", (rola, osoba))
    conn.commit()


def ustaw_aktywny(conn, osoba, aktywny):
    conn.execute("UPDATE uzytkownicy SET aktywny=?, nieudane=0 WHERE osoba=?",
                 (1 if aktywny else 0, osoba))
    conn.commit()


def usun(conn, osoba):
    conn.execute("DELETE FROM uzytkownicy WHERE osoba=?", (osoba,))
    conn.commit()


def losowy_pin():
    """Cztery cyfry, ale nie takie, które ktoś wpisze odruchowo."""
    zle = {"0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777",
           "8888", "9999", "1234", "4321", "1212", "0123"}
    while True:
        p = "%04d" % secrets.randbelow(10000)
        if p not in zle:
            return p


# ------------------------------------------------------------------ logowanie

def zaloguj(conn, osoba, pin):
    """
    Zwraca (uzytkownik, blad). Komunikaty są celowo ogólne — nie mówimy
    „nie ma takiej osoby" ani „zły PIN", bo to podpowiedź dla kogoś, kto zgaduje.
    Wyjątkiem jest blokada: o niej trzeba powiedzieć wprost, inaczej handlowiec
    w terenie będzie próbował w nieskończoność.
    """
    u = znajdz(conn, osoba)
    if not u or not u["aktywny"]:
        return None, "Nieprawidłowa osoba lub PIN"
    if u["nieudane"] >= MAX_PROB:
        return None, ("Konto zablokowane po %d nieudanych próbach — "
                      "poproś koordynatora o reset PIN-u" % MAX_PROB)
    if not u["pin_hash"] or not sprawdz_pin(pin, u["sol"], u["pin_hash"]):
        conn.execute("UPDATE uzytkownicy SET nieudane=nieudane+1 WHERE id=?", (u["id"],))
        conn.commit()
        zostalo = MAX_PROB - (u["nieudane"] + 1)
        if zostalo <= 2:
            return None, ("Nieprawidłowa osoba lub PIN — zostały %d próby" % zostalo
                          if zostalo > 0 else
                          "Konto zablokowane — poproś koordynatora o reset PIN-u")
        return None, "Nieprawidłowa osoba lub PIN"

    conn.execute("UPDATE uzytkownicy SET nieudane=0, "
                 "ostatnie_logowanie=datetime('now') WHERE id=?", (u["id"],))
    conn.commit()
    return znajdz(conn, osoba), None


# ------------------------------------------------------- sesja (warstwa Flask)

def zapisz_sesje(u):
    session.permanent = True
    session["osoba"] = u["osoba"]
    session["rola"] = u["rola"]


def wyczysc_sesje():
    session.pop("osoba", None)
    session.pop("rola", None)


def zalogowany():
    """Dane zalogowanego albo None. Czytane z sesji, bez pytania bazy —
    sesja jest podpisana kluczem serwera, więc nie da się jej podrobić."""
    if not session.get("osoba"):
        return None
    return {"osoba": session["osoba"], "rola": session.get("rola", "handlowiec")}


def jest_koordynatorem():
    u = zalogowany()
    return bool(u and u["rola"] == "koordynator")


# ------------------------------------------------------------------ pierwszy start

def bootstrap_konta(conn, slownik_handlowcow):
    """
    Pierwsze uruchomienie: zakłada konta dla wszystkich handlowców ze słownika
    (bez PIN-u — nadaje go koordynator) i JEDNO konto koordynatora z PIN-em
    startowym, żeby w ogóle dało się wejść.

    PIN startowy bierze się ze zmiennej `PIN_KOORDYNATORA`. Dopóki nie zostanie
    zmieniony, panel kont krzyczy o tym czerwoną ramką — świeżo postawiona
    aplikacja z PIN-em „0000" w internecie to zaproszenie.
    """
    init(conn)
    utworzone = {"koordynator": None, "handlowcy": 0}

    if not conn.execute("SELECT 1 FROM uzytkownicy WHERE rola='koordynator'").fetchone():
        pin = os.environ.get("PIN_KOORDYNATORA", "0000")
        if not poprawny_format(pin):
            pin = "0000"
        utworz(conn, "Koordynator", "koordynator", pin)
        utworzone["koordynator"] = pin

    for osoba in slownik_handlowcow:
        if not znajdz(conn, osoba):
            utworz(conn, osoba, "handlowiec", None)     # PIN nada koordynator
            utworzone["handlowcy"] += 1

    return utworzone


def pin_startowy_niezmieniony(conn):
    """Czy konto koordynatora nadal ma PIN startowy — do ostrzeżenia w panelu."""
    u = znajdz(conn, "Koordynator")
    if not u or not u["pin_hash"]:
        return False
    return sprawdz_pin(os.environ.get("PIN_KOORDYNATORA", "0000"),
                       u["sol"], u["pin_hash"])
