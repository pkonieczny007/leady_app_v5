# -*- coding: utf-8 -*-
"""
Zapytania o leady w jednym miejscu.

Kluczowy powód istnienia tego pliku: klient wprost poprosił, żeby „gdy wyfiltruje
wartości, mieć możliwość pobrania wyfiltrowanego do Excela". Jeśli widok i eksport
budują zapytanie osobno, to zawsze się rozjadą. Tutaj jest JEDNA funkcja filtrująca,
z której korzysta i ekran, i eksporter.
"""
import datetime as dt

from db import STATUS_SUKCES_PREFIX, STATUS_ODPADL_PREFIX

# Pola, po których wolno sortować — biała lista, bo nazwa kolumny wchodzi do SQL.
SORT_POLA = {
    "handlowiec": "l.handlowiec",
    "status": "l.status_realizacji",
    "deadline": "l.deadline",
    "miasto": "p.miejscowosc",
    "placowka": "p.nazwa",
    "typ": "p.typ",
    "data_dt": "dt_data",
    "aktywnosc": "l.ostatnia_aktywnosc",
}

BAZOWY_SELECT = """
SELECT l.*,
       p.id   AS placowka_id,
       p.rspo, p.nazwa AS placowka, p.typ AS typ_placowki,
       -- `nazwa` i `typ` pod własnymi nazwami też, bo karta leada edytuje pola
       -- placówki po ich kluczach z PLACOWKA_FIELDS (aliasy służą listom)
       p.nazwa AS nazwa, p.typ AS typ,
       p.miejscowosc, p.adres, p.osoba_kontakt, p.telefon, p.mail,
       (SELECT MIN(e.data) FROM eventy e
          WHERE e.lead_id = l.id AND e.typ='DT' AND e.data IS NOT NULL AND e.data<>''
       ) AS dt_data,
       (SELECT e.godz_od FROM eventy e
          WHERE e.lead_id = l.id AND e.typ='DT' AND e.data IS NOT NULL AND e.data<>''
          ORDER BY e.data LIMIT 1
       ) AS dt_godz_od,
       (SELECT e.godz_do FROM eventy e
          WHERE e.lead_id = l.id AND e.typ='DT' AND e.data IS NOT NULL AND e.data<>''
          ORDER BY e.data LIMIT 1
       ) AS dt_godz_do,
       (SELECT e.trener FROM eventy e
          WHERE e.lead_id = l.id AND e.typ='DT' AND e.data IS NOT NULL AND e.data<>''
          ORDER BY e.data LIMIT 1
       ) AS dt_trener,
       (SELECT e.numer_sali FROM eventy e
          WHERE e.lead_id = l.id AND e.typ='DT' AND e.data IS NOT NULL AND e.data<>''
          ORDER BY e.data LIMIT 1
       ) AS dt_sala,
       (SELECT e.ilosc_klas FROM eventy e
          WHERE e.lead_id = l.id AND e.typ='DT' ORDER BY e.data LIMIT 1
       ) AS dt_klas,
       (SELECT e.ilosc_dzieci FROM eventy e
          WHERE e.lead_id = l.id AND e.typ='DT' ORDER BY e.data LIMIT 1
       ) AS dt_dzieci,
       (SELECT COUNT(*) FROM eventy e WHERE e.lead_id = l.id AND e.typ='DT') AS n_dt,
       (SELECT COUNT(*) FROM eventy e WHERE e.lead_id = l.id AND e.typ='CYKLICZNE') AS n_cykl
FROM leady l
JOIN placowki p ON p.id = l.placowka_id
"""


def pusty_filtr():
    return {"handlowiec": "", "miasto": "", "status": "", "status_szkoly": "",
            "typ": "", "dt": "", "q": "", "zakres": "", "sort": "", "kier": ""}


def czytaj_filtr(args):
    """Filtry z query stringa. Jedno miejsce, żeby widok i eksport rozumiały to samo."""
    f = pusty_filtr()
    for k in f:
        f[k] = (args.get(k) or "").strip()
    return f


def _warunki(f, dzis):
    """
    Buduje WHERE + parametry. `zakres` to filtr „gotowych zestawów", które
    odpowiadają zakładkom z arkusza klienta:
      nieprzydzielone  → to, co koordynator ma jeszcze rozdać (BAZA)
      przydzielone     → już u handlowca
      umowione         → status 03. (zakładka „Szkoły z DT")
      niewykorzystane  → status 04. (zakładka „Niewykorzystane rekordy")
      po_terminie      → deadline minął, a nie ma sukcesu
      cykle            → placówka ma zajęcia cykliczne („Szkoły z cyklami")
      pin              → przypięte na plan tygodnia
    """
    w, p = [], []
    if f["handlowiec"]:
        w.append("l.handlowiec = ?"); p.append(f["handlowiec"])
    if f["miasto"]:
        w.append("p.miejscowosc = ?"); p.append(f["miasto"])
    if f["status"]:
        w.append("l.status_realizacji = ?"); p.append(f["status"])
    if f["status_szkoly"]:
        w.append("l.status_szkoly = ?"); p.append(f["status_szkoly"])
    if f["typ"]:
        w.append("p.typ = ?"); p.append(f["typ"])
    if f["dt"]:
        w.append("l.dt = ?"); p.append(f["dt"])
    if f["q"]:
        like = "%" + f["q"] + "%"
        w.append("(p.nazwa LIKE ? OR p.miejscowosc LIKE ? OR p.adres LIKE ? "
                 "OR p.mail LIKE ? OR p.telefon LIKE ? OR p.osoba_kontakt LIKE ? "
                 "OR l.uwagi LIKE ? OR p.rspo LIKE ?)")
        p += [like] * 8

    z = f["zakres"]
    if z in ("", "wszystkie"):
        pass                      # jawna gałąź: „pokaż wszystko", bez dodatkowych warunków
    elif z == "nieprzydzielone":
        w.append("(l.handlowiec IS NULL OR l.handlowiec = '')")
    elif z == "przydzielone":
        w.append("(l.handlowiec IS NOT NULL AND l.handlowiec <> '')")
        w.append("(l.status_realizacji IS NULL OR l.status_realizacji NOT LIKE ?)")
        p.append(STATUS_ODPADL_PREFIX + "%")
    elif z == "umowione":
        w.append("l.status_realizacji LIKE ?"); p.append(STATUS_SUKCES_PREFIX + "%")
    elif z == "niewykorzystane":
        w.append("l.status_realizacji LIKE ?"); p.append(STATUS_ODPADL_PREFIX + "%")
    elif z == "po_terminie":
        w.append("l.deadline IS NOT NULL AND l.deadline <> '' AND l.deadline < ?")
        p.append(dzis)
        w.append("(l.status_realizacji IS NULL OR l.status_realizacji NOT LIKE ?)")
        p.append(STATUS_SUKCES_PREFIX + "%")
    elif z == "cykle":
        w.append("(SELECT COUNT(*) FROM eventy e WHERE e.lead_id=l.id "
                 "AND e.typ='CYKLICZNE') > 0")
    elif z == "pin":
        w.append("l.pin_tydzien IS NOT NULL AND l.pin_tydzien <> ''")
    return w, p


def _order_by(f):
    """
    Domyślne sortowanie: przypięte na tydzień NA GÓRZE (wprost z notatek ze spotkania:
    „wybrane szkoły na tydzień do góry"), potem po terminie, potem alfabetycznie.
    """
    if f["sort"] in SORT_POLA:
        kier = "DESC" if f["kier"] == "desc" else "ASC"
        return "ORDER BY %s %s, p.nazwa ASC" % (SORT_POLA[f["sort"]], kier)
    return ("ORDER BY CASE WHEN l.pin_tydzien IS NOT NULL AND l.pin_tydzien <> '' "
            "THEN 0 ELSE 1 END, "
            "CASE WHEN l.deadline IS NULL OR l.deadline='' THEN 1 ELSE 0 END, "
            "l.deadline ASC, l.handlowiec ASC, p.miejscowosc ASC, p.nazwa ASC")


def filtruj_leady(conn, f, limit=None, offset=0, dzis=None):
    """
    Lista leadów wg filtrów. Zwraca listę dictów (gotowe dla szablonu i eksportu).
    `limit`/`offset` służą stronicowaniu ekranów; EKSPORT woła bez limitu,
    żeby plik zawierał cały wyfiltrowany zbiór, nie tylko widoczną stronę.
    """
    dzis = dzis or dt.date.today().isoformat()
    w, p = _warunki(f, dzis)
    sql = BAZOWY_SELECT
    if w:
        sql += " WHERE " + " AND ".join(w)
    sql += " " + _order_by(f)
    if limit:
        sql += " LIMIT %d OFFSET %d" % (int(limit), int(offset or 0))
    rows = [dict(r) for r in conn.execute(sql, p).fetchall()]
    for r in rows:
        r["po_terminie"] = czy_po_terminie(r, dzis)
    return rows


def policz_leady(conn, f, dzis=None):
    dzis = dzis or dt.date.today().isoformat()
    w, p = _warunki(f, dzis)
    sql = ("SELECT COUNT(*) c FROM leady l JOIN placowki p ON p.id=l.placowka_id")
    if w:
        sql += " WHERE " + " AND ".join(w)
    return conn.execute(sql, p).fetchone()["c"]


def czy_po_terminie(row, dzis=None):
    """Termin minął i nie ma sukcesu. Świadomie NIE usuwamy takiego leada —
    ma tylko trafić na listę kandydatów do odebrania handlowcowi."""
    dzis = dzis or dt.date.today().isoformat()
    dl = row.get("deadline")
    st = row.get("status_realizacji") or ""
    return bool(dl and dl < dzis and not st.startswith(STATUS_SUKCES_PREFIX))


def lead_szczegoly(conn, lead_id):
    row = conn.execute(BAZOWY_SELECT + " WHERE l.id = ?", (lead_id,)).fetchone()
    if not row:
        return None
    lead = dict(row)
    lead["po_terminie"] = czy_po_terminie(lead)
    lead["eventy"] = [dict(r) for r in conn.execute(
        "SELECT * FROM eventy WHERE lead_id=? ORDER BY typ, data, godz_od",
        (lead_id,)).fetchall()]
    lead["log"] = [dict(r) for r in conn.execute(
        "SELECT * FROM log WHERE lead_id=? ORDER BY kiedy DESC LIMIT 40",
        (lead_id,)).fetchall()]
    return lead


# ------------------------------------------------------------------ metryki

def metryki(conn, dzis=None):
    dzis = dzis or dt.date.today().isoformat()
    q = lambda sql, p=(): conn.execute(sql, p).fetchone()[0]
    return {
        "placowki": q("SELECT COUNT(*) FROM placowki"),
        "leady": q("SELECT COUNT(*) FROM leady"),
        "nieprzydzielone": q("SELECT COUNT(*) FROM leady "
                             "WHERE handlowiec IS NULL OR handlowiec=''"),
        "umowione": q("SELECT COUNT(*) FROM leady WHERE status_realizacji LIKE ?",
                      (STATUS_SUKCES_PREFIX + "%",)),
        "niewykorzystane": q("SELECT COUNT(*) FROM leady WHERE status_realizacji LIKE ?",
                             (STATUS_ODPADL_PREFIX + "%",)),
        "po_terminie": q("SELECT COUNT(*) FROM leady WHERE deadline IS NOT NULL "
                         "AND deadline<>'' AND deadline<? "
                         "AND (status_realizacji IS NULL OR status_realizacji NOT LIKE ?)",
                         (dzis, STATUS_SUKCES_PREFIX + "%")),
        "eventy_dt": q("SELECT COUNT(*) FROM eventy WHERE typ='DT'"),
        "eventy_cykl": q("SELECT COUNT(*) FROM eventy WHERE typ='CYKLICZNE'"),
    }


def per_handlowiec(conn, cel_tygodniowy=5, dzis=None):
    """
    Rozkład per handlowiec + realizacja celu tygodniowego.
    „STATUS — minimum na tydzień" z notatek ze spotkania: ile DT umówił w tym tygodniu
    względem minimum. Tydzień liczymy od poniedziałku.
    """
    dzis_d = dt.date.fromisoformat(dzis) if dzis else dt.date.today()
    poniedzialek = (dzis_d - dt.timedelta(days=dzis_d.weekday())).isoformat()
    rows = conn.execute(
        """
        SELECT l.handlowiec,
               COUNT(*) AS leadow,
               SUM(CASE WHEN l.status_realizacji LIKE ? THEN 1 ELSE 0 END) AS umowione,
               SUM(CASE WHEN l.status_realizacji LIKE ?
                         AND l.ostatnia_aktywnosc IS NOT NULL
                         AND substr(l.ostatnia_aktywnosc,1,10) >= ?
                        THEN 1 ELSE 0 END) AS w_tygodniu,
               SUM(CASE WHEN l.pin_tydzien IS NOT NULL AND l.pin_tydzien<>''
                        THEN 1 ELSE 0 END) AS przypietych
        FROM leady l
        WHERE l.handlowiec IS NOT NULL AND l.handlowiec <> ''
        GROUP BY l.handlowiec
        ORDER BY leadow DESC
        """, (STATUS_SUKCES_PREFIX + "%", STATUS_SUKCES_PREFIX + "%", poniedzialek)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["cel"] = cel_tygodniowy
        d["cel_ok"] = d["w_tygodniu"] >= cel_tygodniowy
        d["cel_proc"] = min(100, round(100.0 * d["w_tygodniu"] / cel_tygodniowy)) \
            if cel_tygodniowy else 0
        d["proc"] = round(100.0 * d["umowione"] / d["leadow"]) if d["leadow"] else 0
        out.append(d)
    return out, poniedzialek
