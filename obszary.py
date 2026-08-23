# -*- coding: utf-8 -*-
"""
Obszary działania firmy — po jakich powiatach i gminach jeździ SILESIA 3D.

NAZEWNICTWO: „OBSZAR", NIE „REJON" — TO NIE JEST PEDANTERIA
W tej aplikacji `rejony` już istnieją i znaczą co innego: (trener, miasto),
czyli „kto po czym jeździ" (obsługuje `przydzial.py`). Obszar działania to
geografia FIRMY, nie człowieka. Dwa pojęcia pod jedną nazwą to gwarancja, że
za miesiąc ktoś poprawi nie tę tabelę. Zasada: „obszar" = geografia firmy,
„rejon" = zawsze czyjś.

DLACZEGO LISTA OBSZARÓW, A NIE KOLUMNA NA PLACÓWCE
Zakres firmy nie pokrywa się z żadnym jednym poziomem administracyjnym:
Rybnik bierzemy jako miasto (powiat grodzki), ale NIE powiat rybnicki;
Knurów bierzemy jako gminę, ale NIE resztę powiatu gliwickiego. Kolumna
„powiat" na placówce tego nie wyrazi — lista obszarów (powiat albo gmina)
z regułą „gmina bije powiat" wyraża to jednym mechanizmem.

Rozróżnienie miasto/powiat ziemski niesie SAM REJESTR: powiat grodzki ma
nazwę miasta („Katowice", „Rybnik"), ziemski jest z małej litery
(„mikołowski", „rybnicki"). Nie dopisujemy własnych oznaczeń.

Kod przejęty z `rspo_app/rejony.py` (etap M2 projektu PROJEKT_BAZY_RSPO.md);
zmienione nazwy tabel i podpięcie pod lustro `rspo_rejestr`.
"""

# Lista startowa = zakres od Kasi (powiaty.png + „mikołowski, pszczyński,
# będziński" + uwaga o Rybniku, 23.08.2026). Sieje się tylko do pustej tabeli.
OBSZARY_STARTOWE = [
    # (nazwa, [(rodzaj, wartość), ...])  — wartość DOSŁOWNIE jak w rejestrze
    ("Katowice",              [("powiat", "Katowice")]),
    ("Sosnowiec",             [("powiat", "Sosnowiec")]),
    ("Zabrze",                [("powiat", "Zabrze")]),
    ("Rybnik",                [("powiat", "Rybnik")]),          # miasto, NIE „rybnicki"
    ("Tychy",                 [("powiat", "Tychy")]),
    ("Dąbrowa Górnicza",      [("powiat", "Dąbrowa Górnicza")]),
    ("Ruda Śląska",           [("powiat", "Ruda Śląska")]),
    ("Chorzów",               [("powiat", "Chorzów")]),
    ("Jaworzno",              [("powiat", "Jaworzno")]),
    ("Żory",                  [("powiat", "Żory")]),
    ("Siemianowice Śląskie",  [("powiat", "Siemianowice Śląskie")]),
    ("Piekary Śląskie",       [("powiat", "Piekary Śląskie")]),
    ("Świętochłowice",        [("powiat", "Świętochłowice")]),
    ("powiat pszczyński",     [("powiat", "pszczyński")]),
    ("powiat będziński",      [("powiat", "będziński")]),
    ("powiat mikołowski",     [("powiat", "mikołowski")]),
    # Kasia: Knurów — jedna gmina z powiatu gliwickiego, reszty nie bierzemy.
    ("Knurów",                [("gmina", "Knurów")]),
]

# Typy placówek z rejestru, w których firma realnie prowadzi zajęcia.
# Filtr domyślny „dołóż do bazy" — nie po to, żeby oszczędzać wiersze
# (6 tysięcy to dla SQLite nic), tylko żeby nie dokładać liceów i burs.
NASZE_TYPY = ("Szkoła podstawowa", "Przedszkole", "Punkt przedszkolny",
              "Zespół szkół i placówek oświatowych")


def zaloz_tabele(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS obszary_dzialania (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazwa TEXT UNIQUE NOT NULL,
            kolejnosc INTEGER DEFAULT 0
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS obszar_zakres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obszar_id INTEGER NOT NULL,
            rodzaj TEXT NOT NULL CHECK (rodzaj IN ('powiat', 'gmina')),
            wartosc TEXT NOT NULL,
            UNIQUE (rodzaj, wartosc)
        )""")
    # Wyliczane przypisanie lustro→obszar. `przez` mówi, która reguła
    # przypisała („powiat:Katowice" / „gmina:Knurów") — bez tego nie da się
    # odpowiedzieć „czemu ta szkoła jest w tym obszarze".
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rspo_obszar (
            rspo INTEGER PRIMARY KEY,
            obszar_id INTEGER NOT NULL,
            przez TEXT
        )""")


def zasiej(conn):
    """
    Zakłada obszary startowe, jeśli tabela jest PUSTA. Świadomie nie dopisuje
    do bazy, w której ktoś już obszary poustawiał — inaczej po każdym
    restarcie wracałyby skasowane i nikt by nie rozumiał czemu.
    """
    zaloz_tabele(conn)
    if conn.execute("SELECT COUNT(*) FROM obszary_dzialania").fetchone()[0]:
        return 0
    for i, (nazwa, zakresy) in enumerate(OBSZARY_STARTOWE):
        cur = conn.execute(
            "INSERT INTO obszary_dzialania (nazwa, kolejnosc) VALUES (?,?)",
            (nazwa, i))
        for rodzaj, wartosc in zakresy:
            conn.execute(
                "INSERT OR IGNORE INTO obszar_zakres (obszar_id, rodzaj, wartosc)"
                " VALUES (?,?,?)", (cur.lastrowid, rodzaj, wartosc))
    conn.commit()
    return len(OBSZARY_STARTOWE)


def przelicz(conn):
    """
    Odbudowuje `rspo_obszar` z lustra. Wołane po wgraniu rejestru i po każdej
    zmianie obszarów.

    Kolejność INSERT-ów niesie regułę pierwszeństwa: najpierw powiaty, potem
    gminy z `INSERT OR REPLACE` — gmina nadpisuje powiat. To JEDYNE miejsce,
    w którym ta reguła żyje; dzięki niej Knurów wchodzi bez reszty powiatu
    gliwickiego, a dopisanie gminy do obszaru nigdy nie wymaga zmiany kodu.
    """
    zaloz_tabele(conn)
    conn.execute("DELETE FROM rspo_obszar")
    for rodzaj in ("powiat", "gmina"):
        conn.execute("""
            INSERT OR REPLACE INTO rspo_obszar (rspo, obszar_id, przez)
            SELECT r.rspo, o.obszar_id, ? || ':' || o.wartosc
              FROM rspo_rejestr r
              JOIN obszar_zakres o
                ON o.rodzaj = ?
               AND lower(o.wartosc) = lower(r.%s)
        """ % rodzaj, (rodzaj, rodzaj))
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM rspo_obszar").fetchone()[0]


def lista(conn):
    """Obszary z zakresami i licznikiem placówek lustra — do ekranu i raportów."""
    zaloz_tabele(conn)
    out = []
    for o in conn.execute("SELECT * FROM obszary_dzialania ORDER BY kolejnosc, nazwa"):
        zakresy = [dict(z) for z in conn.execute(
            "SELECT rodzaj, wartosc FROM obszar_zakres WHERE obszar_id=? "
            "ORDER BY rodzaj, wartosc", (o["id"],))]
        n = conn.execute("SELECT COUNT(*) FROM rspo_obszar WHERE obszar_id=?",
                         (o["id"],)).fetchone()[0]
        out.append({"id": o["id"], "nazwa": o["nazwa"], "zakresy": zakresy,
                    "placowek_w_lustrze": n})
    return out


def w_zakresie_liczby(conn, tylko_nasze_typy=True):
    """
    Ile placówek lustra wpada w obszary — liczba kontrolna etapu M2.
    Na danych z 23.08 dla typów klienta ma wyjść 1 259 (+23 punkty przedszkolne
    = 1 282); inna liczba znaczy, że coś się rozjechało i NIE idziemy dalej.
    """
    sql = """SELECT COUNT(*) FROM rspo_obszar ro
             JOIN rspo_rejestr r ON r.rspo = ro.rspo"""
    if tylko_nasze_typy:
        sql += " WHERE r.typ IN (%s)" % ",".join("?" * len(NASZE_TYPY))
        return conn.execute(sql, NASZE_TYPY).fetchone()[0]
    return conn.execute(sql).fetchone()[0]
