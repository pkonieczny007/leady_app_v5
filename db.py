# -*- coding: utf-8 -*-
"""
Warstwa bazy — SQLite, bez ORM (projekt ma być lekki i czytelny dla kogoś, kto go przejmie).

MODEL DANYCH — trzy tabele operacyjne, każda odpowiada na konkretny ból klienta:

  placowki  1 wiersz = 1 szkoła/przedszkole/instytucja kultury (baza „RSPO")
            → rozwiązuje: „ta sama szkoła zapisana na 4 sposoby w 4 zakładkach"

  leady     1 wiersz = przypisanie placówki handlowcowi + proces sprzedażowy
            → rozwiązuje: „lead znika z bazy głównej" (to zmiana statusu, nie kopiowanie)
                          „niewykorzystane rekordy" (to filtr, nie osobna zakładka)

  eventy    1 wiersz = JEDNO spotkanie (DT albo zajęcia cykliczne)
            → rozwiązuje ZGŁOSZONY BUG: trener z 2–3 DT w jednym dniu to po prostu
              2–3 wiersze pod tą samą datą. Kalendarz jest widokiem z tej tabeli,
              a nie ręcznie malowaną planszą, więc nic się nie gubi.

  slowniki  jedno źródło wszystkich list rozwijanych
  aliasy    literówki i warianty zapisu → wartość kanoniczna
            → rozwiązuje: „02. Olaszewska", „ZUZA"/„ZUZANNA"/„ZUZIA OLSZEWSKA",
              trzy różne listy miejscowości
  log       ślad zmian (do kontroli „czy handlowiec ruszył lead przed terminem")
"""
import os
import sqlite3

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
DB_PATH = os.path.join(DATA_DIR, "leady_v3.db")

# --------------------------------------------------------------------------
# Definicje pól — JEDNO źródło prawdy dla: schematu, UI, importu i eksportu.
# (etykieta dla użytkownika, klucz w bazie, typ dla UI, nagłówek z arkusza klienta)
# typ: text | date | time | int | bool_td (Tak/Do ustalenia) | slownik:<rodzaj>
# --------------------------------------------------------------------------

PLACOWKA_FIELDS = [
    ("Nr RSPO",        "rspo",          "text",             None),
    ("Nazwa placówki", "nazwa",         "text",             "Numer placówki"),
    ("Typ",            "typ",           "slownik:typ_placowki", None),
    ("Miejscowość",    "miejscowosc",   "slownik:miasto",   "Miejscowość"),
    ("Adres",          "adres",         "text",             "Adres placówki"),
    ("Osoba kontaktowa", "osoba_kontakt", "text",           "Osoby decyzyjne i kontakt"),
    ("Telefon",        "telefon",       "text",             "numer telefonu"),
    ("Mail",           "mail",          "text",             "mail"),
]

LEAD_FIELDS = [
    ("Handlowiec",        "handlowiec",        "slownik:handlowiec",        "Handlowiec"),
    ("Status szkoły",     "status_szkoly",     "slownik:status_szkoly",     "Status szkoły"),
    ("Status realizacji", "status_realizacji", "slownik:status_realizacji", "Status realizacji"),
    ("Termin ostateczny", "deadline",          "date",                      "death line"),
    ("DT",                "dt",                "slownik:dt",                "DT"),
    ("Cykle",             "cykle",             "slownik:tak_nie",           "Cykle"),
    # najczęściej używane pole handlowca w ich brudnopisach („Kasia notatki!G — do zrobienia")
    ("Do zrobienia",      "do_zrobienia",      "text",                      "do zrobienia"),
    ("Uwagi",             "uwagi",             "text",                      "Uwagi"),
    ("Mail propozycja/ustalenie DT", "mail_dt", "slownik:mail_dt",          "mail propozycja lub ustalenie DT"),
    ("Mail do rodziców (dziennik)",  "mail_rodzice", "slownik:tak_nie",     "Mail do rodziców na dziennik elektroniczny"),
    ("Mail z wnioskiem o wynajem sali", "mail_wynajem", "slownik:tak_nie",  "Mail z wnioskiem o wynajem sali"),
]

# Kolumny, które w arkuszu miały dopisek „WYPEŁNIA JULIA" — osobna grupa,
# bo to inny użytkownik i inny ekran (Zbiorczy), a nie inny rekord.
JULIA_FIELDS = [
    ("Dane do umowy",            "julia_dane_umowy",  "slownik:tak_nie", "Dane do umowy WYPEŁNIA JULIA"),
    ("Standardy ochrony małoletnich", "julia_standardy", "slownik:tak_nie", "Standardy ochrony maloletnich WYPEŁNIA JULIA"),
    ("Oświadczenia trenerów",    "julia_oswiadczenia", "slownik:tak_nie", "Oświadczenia trenerów do standardów WYPEŁNIA JULIA"),
    ("Zaświadczenie o niekaralności", "julia_niekaralnosc", "slownik:tak_nie", "Zaświadczenie o niekaralności WYPEŁNIA JULIA"),
    ("Podanie o wynajem sali",   "julia_podanie_sala", "slownik:tak_nie", "Podanie o wynajem sali WYPEŁNIA JULIA"),
    ("Umowa podpisana",          "julia_umowa",       "slownik:tak_nie", "Umowa podpisana WYPEŁNIA JULIA"),
    ("Librus",                   "julia_librus",      "slownik:tak_nie", "Librus WYPEŁNIA JULIA"),
]

EVENT_FIELDS = [
    ("Typ",            "typ",             "slownik:typ_eventu", None),
    ("Data",           "data",            "date",               "Data DT"),
    ("Godz. od",       "godz_od",         "time",               "Godzina DT"),
    ("Godz. do",       "godz_do",         "time",               None),
    ("Prowadzący",     "trener",          "slownik:trener",     "Prowadzący DT"),
    ("Drugi prowadzący", "trener2",       "slownik:trener",     None),
    ("Zastępstwo",     "zastepstwo",      "slownik:trener",     None),
    ("Drukarz",        "drukarz",         "slownik:trener",     None),
    ("Nr sali",        "numer_sali",      "text",               "Numer sali DT"),
    ("Grupa",          "grupa",           "text",               None),
    ("Sprzęt",         "sprzet",          "slownik:sprzet",     "Zajecia cykliczne (sala komputerowa/chromebooki)"),
    ("Ilość klas",     "ilosc_klas",      "int",                "Ilość klas 1-4"),
    ("Ilość dzieci",   "ilosc_dzieci",    "int",                "Ilość dzieci w klasach"),
    ("Dzień tygodnia (cykl)", "cykl_dzien", "slownik:dzien_tyg", "Zajecia cykliczne (dzień tygodnia)"),
    # „CO 2 TYGODNIE" i „2gi Pon miesiąca" realnie występują w ich planszach —
    # samo „co tydzień" nie wystarcza
    ("Co ile tygodni", "co_ile_tygodni",  "int",                None),
    ("Kod Tinkercad",  "kod_tinkercad",   "text",               None),
    ("Link Tinkercad", "link_tinkercad",  "text",               None),
    ("Uwagi",          "uwagi",           "text",               None),
]

PLACOWKA_KEYS = [f[1] for f in PLACOWKA_FIELDS]
LEAD_KEYS = [f[1] for f in LEAD_FIELDS] + [f[1] for f in JULIA_FIELDS]
EVENT_KEYS = [f[1] for f in EVENT_FIELDS]

INT_KEYS = {"ilosc_klas", "ilosc_dzieci", "co_ile_tygodni"}

# Rodzaje słowników (klucz, etykieta, czy pozycje mają kolor)
SLOWNIK_RODZAJE = [
    ("handlowiec",        "Handlowcy",          False),
    ("trener",            "Trenerzy",           True),
    ("miasto",            "Miejscowości",       False),
    ("typ_placowki",      "Typ placówki",       False),
    ("status_szkoly",     "Status szkoły",      False),
    ("status_realizacji", "Status realizacji",  False),
    ("dt",                "DT",                 False),
    ("tak_nie",           "Tak / Nie",          False),
    ("mail_dt",           "Mail DT",            False),
    ("dzien_tyg",         "Dni tygodnia",       False),
    ("typ_eventu",        "Typ wpisu",          False),
    ("sprzet",            "Sprzęt",             False),
]

SLOWNIK_KLUCZE = [r[0] for r in SLOWNIK_RODZAJE]

# Status oznaczający sukces (DT umówione). Trzymany w jednym miejscu, bo pojawia się
# w kilku zapytaniach — klient może zmienić nazwę, wtedy poprawiamy tutaj.
STATUS_SUKCES_PREFIX = "03."
STATUS_ODPADL_PREFIX = "04."


# Ogonki → litery bez ogonków. SQLite-owe LIKE ignoruje wielkość liter TYLKO
# dla ASCII, więc „ŁUKASZ" nie znalazłby się po wpisaniu „łukasz", a „Zemeła"
# po „zemela". Filtr osób (wpisywanie nazwisk) ma działać tak, jak człowiek
# oczekuje, dlatego obie strony porównania przepuszczamy przez `pl_fold`.
_OGONKI = str.maketrans("ąćęłńóśźż", "acelnoszz")


def pl_fold(s):
    """„02. Żmuda-Trzebiatowski" → „02. zmuda-trzebiatowski". Do porównań, nie do wyświetlania."""
    if s is None:
        return ""
    return str(s).lower().translate(_OGONKI)


def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # `pl_fold` w SQL — używa go filtr osób w repo.py
    conn.create_function("pl_fold", 1, pl_fold)
    return conn


def _cols(keys):
    return ",\n          ".join(
        "%s %s" % (k, "INTEGER" if k in INT_KEYS else "TEXT") for k in keys)


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS placowki (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          %(placowka)s,
          zrodlo TEXT,                -- skąd rekord: rspo | arkusz:<zakładka> | reka
          created_at TEXT DEFAULT (datetime('now')),
          updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ix_placowki_rspo
          ON placowki(rspo) WHERE rspo IS NOT NULL AND rspo <> '';
        CREATE INDEX IF NOT EXISTS ix_placowki_miasto ON placowki(miejscowosc);

        CREATE TABLE IF NOT EXISTS leady (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          placowka_id INTEGER NOT NULL REFERENCES placowki(id) ON DELETE CASCADE,
          %(lead)s,
          pin_tydzien TEXT,           -- data poniedziałku tygodnia, na który lead przypięty
          ostatnia_aktywnosc TEXT,    -- ostatnia zmiana merytoryczna (kontrola deadline)
          created_at TEXT DEFAULT (datetime('now')),
          updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ix_leady_handlowiec ON leady(handlowiec);
        CREATE INDEX IF NOT EXISTS ix_leady_status ON leady(status_realizacji);
        CREATE INDEX IF NOT EXISTS ix_leady_placowka ON leady(placowka_id);

        CREATE TABLE IF NOT EXISTS eventy (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          lead_id INTEGER NOT NULL REFERENCES leady(id) ON DELETE CASCADE,
          %(event)s,
          created_at TEXT DEFAULT (datetime('now')),
          updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ix_eventy_data ON eventy(data);
        CREATE INDEX IF NOT EXISTS ix_eventy_trener ON eventy(trener);
        CREATE INDEX IF NOT EXISTS ix_eventy_lead ON eventy(lead_id);
        CREATE INDEX IF NOT EXISTS ix_eventy_typ ON eventy(typ);

        -- Wyjątki od reguły cyklu: zastępstwo albo odwołane zajęcia na KONKRETNĄ datę.
        -- W arkuszu klienta tydzień 2 to w 149/155 komórek kopia tygodnia 1, a różnice
        -- to dokładnie takie wyjątki. Dzięki tej tabeli nowy tydzień powstaje sam,
        -- a zastępstwo dopisuje się w jednym miejscu — bez kopiowania 150 komórek.
        CREATE TABLE IF NOT EXISTS wyjatki_cyklu (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_id INTEGER NOT NULL REFERENCES eventy(id) ON DELETE CASCADE,
          data TEXT NOT NULL,
          odwolane INTEGER DEFAULT 0,
          trener TEXT,                -- zmiana prowadzącego na ten jeden termin
          zastepstwo TEXT,
          godz_od TEXT,
          godz_do TEXT,
          uwagi TEXT,
          UNIQUE(event_id, data)
        );

        -- Dostępność trenera. W ich kalendarzu DT jedna komórka trzymała jednocześnie
        -- „DOSTĘPNA 8–12:00" i rezerwację DT — i to jest jedyne wejście do umawiania DT.
        -- Rozdzielenie tych dwóch rzeczy jest warunkiem sensownego planowania.
        CREATE TABLE IF NOT EXISTS dostepnosc (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          trener TEXT NOT NULL,
          data TEXT NOT NULL,
          godz_od TEXT,
          godz_do TEXT,
          niedostepny INTEGER DEFAULT 0,
          uwagi TEXT,
          UNIQUE(trener, data)
        );
        CREATE INDEX IF NOT EXISTS ix_dostepnosc_data ON dostepnosc(data);

        -- Rejon trenera: miasta, po których jeździ. W arkuszu tego nie było wcale —
        -- koordynatorka trzymała to w głowie, przez co podpowiedź „kogo wysłać"
        -- była niemożliwa do zrobienia maszynowo. Wiele miast na trenera, bo część
        -- osób obsługuje dwa obszary.
        CREATE TABLE IF NOT EXISTS rejony (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          trener TEXT NOT NULL,
          miasto TEXT NOT NULL,
          UNIQUE(trener, miasto)
        );
        CREATE INDEX IF NOT EXISTS ix_rejony_trener ON rejony(trener);

        CREATE TABLE IF NOT EXISTS slowniki (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          rodzaj TEXT NOT NULL,
          wartosc TEXT NOT NULL,
          kolor TEXT,
          sort_order INTEGER DEFAULT 0,
          aktywny INTEGER DEFAULT 1,
          UNIQUE(rodzaj, wartosc)
        );

        CREATE TABLE IF NOT EXISTS aliasy (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          rodzaj TEXT NOT NULL,
          alias TEXT NOT NULL,
          wartosc TEXT NOT NULL,
          UNIQUE(rodzaj, alias)
        );

        CREATE TABLE IF NOT EXISTS log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          lead_id INTEGER,
          event_id INTEGER,
          kto TEXT,
          co TEXT,                    -- np. 'zmiana pola', 'przypisanie', 'import'
          pole TEXT,
          przed TEXT,
          po TEXT,
          kiedy TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS ix_log_lead ON log(lead_id);
        """ % {"placowka": _cols(PLACOWKA_KEYS),
               "lead": _cols(LEAD_KEYS),
               "event": _cols(EVENT_KEYS)}
    )
    migruj(conn)
    conn.commit()


def migruj(conn):
    """
    Dokłada kolumny, które pojawiły się po utworzeniu bazy.
    `CREATE TABLE IF NOT EXISTS` nie zmienia istniejącej tabeli, więc bez tego
    baza z wcześniejszego uruchomienia zostałaby bez nowych pól.
    """
    tabele = {"placowki": PLACOWKA_KEYS, "leady": LEAD_KEYS, "eventy": EVENT_KEYS}
    for tabela, klucze in tabele.items():
        istniejace = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % tabela)}
        if not istniejace:
            continue
        for k in klucze:
            if k not in istniejace:
                typ = "INTEGER" if k in INT_KEYS else "TEXT"
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tabela, k, typ))


# ------------------------------------------------------------------ słowniki

def slownik(conn, rodzaj):
    rows = conn.execute(
        "SELECT id, wartosc, kolor, sort_order FROM slowniki "
        "WHERE rodzaj=? AND aktywny=1 ORDER BY sort_order, wartosc", (rodzaj,)).fetchall()
    return [dict(r) for r in rows]


def slownik_values(conn, rodzaj):
    return [r["wartosc"] for r in slownik(conn, rodzaj)]


def wszystkie_slowniki(conn):
    """Wszystkie listy naraz — szablony dostają je do selectów bez N zapytań."""
    out = {r: [] for r in SLOWNIK_KLUCZE}
    for row in conn.execute(
            "SELECT rodzaj, wartosc FROM slowniki WHERE aktywny=1 "
            "ORDER BY rodzaj, sort_order, wartosc").fetchall():
        out.setdefault(row["rodzaj"], []).append(row["wartosc"])
    return out


def trener_colors(conn):
    """Mapa trener → kolor. Brakującym dokładamy kolor deterministycznie z nazwy,
    żeby każdy trener miał swój odcień od pierwszego uruchomienia."""
    out = {}
    for r in slownik(conn, "trener"):
        out[r["wartosc"]] = r["kolor"] or kolor_z_nazwy(r["wartosc"])
    return out


# Paleta zapasowa — odcienie rozłożone po kole barw, czytelne na papierowym tle.
_PALETA = [
    "#0088b0", "#d6006c", "#7a5cc6", "#0f8a5f", "#c76a00", "#b3123c",
    "#2d6fd1", "#8a7500", "#00867d", "#a03bb0", "#5b8c00", "#c2410c",
    "#1e6091", "#9d174d", "#4338ca", "#065f46", "#92400e", "#7c2d12",
]


def kolor_z_nazwy(nazwa):
    """Deterministyczny kolor z nazwy — ten sam trener zawsze dostaje ten sam odcień."""
    if not nazwa:
        return "#9b9797"
    h = 0
    for ch in nazwa:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return _PALETA[h % len(_PALETA)]


def alias_map(conn, rodzaj=None):
    """Mapa (rodzaj, alias) → wartość kanoniczna. Używana przy imporcie."""
    if rodzaj:
        rows = conn.execute("SELECT alias, wartosc FROM aliasy WHERE rodzaj=?", (rodzaj,))
        return {r["alias"]: r["wartosc"] for r in rows}
    rows = conn.execute("SELECT rodzaj, alias, wartosc FROM aliasy")
    out = {}
    for r in rows:
        out.setdefault(r["rodzaj"], {})[r["alias"]] = r["wartosc"]
    return out


# ------------------------------------------------------------------ log

def zapisz_log(conn, *, lead_id=None, event_id=None, kto="demo", co="", pole=None,
               przed=None, po=None):
    conn.execute(
        "INSERT INTO log (lead_id, event_id, kto, co, pole, przed, po) "
        "VALUES (?,?,?,?,?,?,?)",
        (lead_id, event_id, kto, co, pole,
         None if przed is None else str(przed),
         None if po is None else str(po)))
    if lead_id:
        conn.execute("UPDATE leady SET ostatnia_aktywnosc=datetime('now'), "
                     "updated_at=datetime('now') WHERE id=?", (lead_id,))
