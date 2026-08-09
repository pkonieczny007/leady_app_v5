# -*- coding: utf-8 -*-
"""
Auto-zwrot przeterminowanych leadów do puli nieprzydzielonych.

Ze spotkania 06.08: „koordynator przydziela 10 szkół z terminem do 2 tygodni;
wybrane szkoły, gdy skończy się termin, automatycznie mają wracać do
nieprzydzielonych". Do v4 tego nie było wcale — był tylko filtr „po terminie"
na pulpicie i ręczne „odbierz handlowcowi".

TRZY DECYZJE PROJEKTOWE, bez których automat robiłby ludziom krzywdę:

1. BEZ KARENCJI PO TERMINIE — decyzja Przemka z 08.08 (późny wieczór), zgodnie
   z intencją Kasi („najlepiej jak automatycznie wróci"): lead wraca PIERWSZEGO
   dnia po terminie. Wcześniejsze 2 dni karencji (nasza propozycja z 07.08,
   klient nigdy jej nie potwierdził) przenieśliśmy w całości na stronę
   ostrzeżenia — patrz pkt 2. `KARENCJA_DNI` zostaje jako zmienna (domyślnie 0),
   bo to decyzja klienta, nie architektury — może wrócić jedną linijką konfiguracji.

2. OSTRZEŻENIE ZAMIAST ZASKOCZENIA. Na `OSTRZEZENIE_DNI` (domyślnie 2) PRZED
   terminem lead trafia na listę `zagrozone()` — handlowiec widzi „ta szkoła
   wraca do puli za 2 dni" i ma czas zareagować, ZANIM termin minie. Automat,
   który po cichu zabiera pracę, zostanie znienawidzony i obejdą go przez
   wpisywanie byle czego, żeby „odświeżyć" rekord.

3. ZWROT NIE KASUJE PRACY. Wraca WYŁĄCZNIE przypisanie (handlowiec, termin,
   przypięcie na tydzień). Notatki, kontakty, ustalenia i historia zostają przy
   placówce, a w `log` ląduje wpis kto miał lead i kiedy go stracił — więc
   koordynator zawsze odtworzy, co się działo.

CZEGO AUTOMAT NIE RUSZA:
  - leadów z umówionym DT (`03.`) — sukces jest sukcesem, nawet po terminie,
  - leadów, które mają w kalendarzu jakiekolwiek DT z datą — to samo, tyle że
    sprawdzane po faktach, a nie po statusie (status bywa nieaktualny),
  - leadów już odpadniętych (`04.`) — one nie są u nikogo,
  - leadów bez terminu ostatecznego — skoro nikt nie ustawił terminu, nie ma
    czego egzekwować.
"""
import datetime as dt
import os

from db import (STATUS_SUKCES_PREFIX, STATUS_ODPADL_PREFIX, meta_get, meta_set,
                zapisz_log)

KARENCJA_DNI = int(os.environ.get("KARENCJA_DNI", "0"))
OSTRZEZENIE_DNI = int(os.environ.get("OSTRZEZENIE_DNI", "2"))

# Co ile minut najwyżej przelatuje automat przy okazji ruchu w aplikacji.
# Nie potrzeba tu crona: 60 minut w zupełności wystarcza dla zjawiska mierzonego
# w dniach, a jedno zapytanie na godzinę nie waży nic.
CO_ILE_MINUT = 60

STATUS_PO_ZWROCIE = "00. Nieprzydzielony"
META_KLUCZ = "ostatni_zwrot"

# Lead „żywy u handlowca": ma właściciela, nie jest sukcesem ani odpadnięciem
# i nie ma w kalendarzu żadnego DT z datą.
_ZYWY = """
  l.handlowiec IS NOT NULL AND l.handlowiec <> ''
  AND l.deadline IS NOT NULL AND l.deadline <> ''
  AND (l.status_realizacji IS NULL OR (l.status_realizacji NOT LIKE ?
                                       AND l.status_realizacji NOT LIKE ?))
  AND NOT EXISTS (SELECT 1 FROM eventy e WHERE e.lead_id = l.id
                  AND e.typ = 'DT' AND e.data IS NOT NULL AND e.data <> '')
"""
_ZYWY_PARAMY = (STATUS_SUKCES_PREFIX + "%", STATUS_ODPADL_PREFIX + "%")

_SELECT = """
SELECT l.id, l.handlowiec, l.deadline, l.status_realizacji,
       p.nazwa AS placowka, p.miejscowosc
FROM leady l JOIN placowki p ON p.id = l.placowka_id
"""


def _dzis(dzis=None):
    return dzis or dt.date.today().isoformat()


def _minus_dni(data_iso, dni):
    return (dt.date.fromisoformat(data_iso) - dt.timedelta(days=dni)).isoformat()


def _plus_dni(data_iso, dni):
    return (dt.date.fromisoformat(data_iso) + dt.timedelta(days=dni)).isoformat()


# ------------------------------------------------------------------ podgląd

def do_zwrotu(conn, dzis=None, karencja=None):
    """
    Leady, którym termin minął o więcej niż karencję — czyli te, które automat
    zwróci przy najbliższym przebiegu. Osobna funkcja od `wykonaj`, żeby dało się
    pokazać listę koordynatorowi PRZED wykonaniem (i przetestować bez skutków).
    """
    dzis = _dzis(dzis)
    karencja = KARENCJA_DNI if karencja is None else karencja
    granica = _minus_dni(dzis, karencja)
    rows = conn.execute(
        _SELECT + " WHERE " + _ZYWY + " AND l.deadline < ? ORDER BY l.deadline, p.nazwa",
        _ZYWY_PARAMY + (granica,)).fetchall()
    return [dict(r) for r in rows]


def zagrozone(conn, dzis=None, handlowiec=None, w_ciagu=None):
    """
    „Ta szkoła wraca do puli za N dni" — ostrzeżenie dla handlowca.

    Bierze leady, którym termin minął, ale karencja jeszcze trwa, ORAZ te,
    którym termin dopiero minie w ciągu `w_ciagu` dni. Do każdego dokłada
    `dni_do_zwrotu` — liczbę, którą handlowiec ma zobaczyć na ekranie.
    """
    dzis = _dzis(dzis)
    w_ciagu = OSTRZEZENIE_DNI if w_ciagu is None else w_ciagu
    # Wraca w dniu `deadline + KARENCJA + 1`. Ostrzegamy, gdy do tego dnia
    # zostało nie więcej niż `w_ciagu`.
    najpozniejszy_deadline = _plus_dni(dzis, w_ciagu)
    sql = _SELECT + " WHERE " + _ZYWY + " AND l.deadline <= ?"
    p = _ZYWY_PARAMY + (najpozniejszy_deadline,)
    if handlowiec:
        sql += " AND l.handlowiec = ?"
        p += (handlowiec,)
    sql += " ORDER BY l.deadline, p.nazwa"

    dzis_d = dt.date.fromisoformat(dzis)
    out = []
    for r in conn.execute(sql, p).fetchall():
        d = dict(r)
        wraca = (dt.date.fromisoformat(d["deadline"])
                 + dt.timedelta(days=KARENCJA_DNI + 1))
        d["wraca_dnia"] = wraca.isoformat()
        d["dni_do_zwrotu"] = (wraca - dzis_d).days
        out.append(d)
    # najpilniejsze na górze; te, które już powinny były wrócić, mają wartość ≤ 0
    out.sort(key=lambda d: d["dni_do_zwrotu"])
    return out


# ------------------------------------------------------------------ wykonanie

def wykonaj(conn, dzis=None, karencja=None, kto="automat"):
    """
    Zwraca przeterminowane leady do puli. Zwraca listę tego, co zwrócono
    (nie samą liczbę — koordynator ma zobaczyć KTÓRE szkoły wróciły).

    Czyścimy `deadline` razem z handlowcem: termin bez właściciela nie znaczy nic,
    a zostawiony trzymałby lead na liście „po terminie" już na zawsze.
    """
    lista = do_zwrotu(conn, dzis=dzis, karencja=karencja)
    for lead in lista:
        conn.execute(
            "UPDATE leady SET handlowiec=NULL, deadline=NULL, pin_tydzien=NULL, "
            "status_realizacji=?, updated_at=datetime('now') WHERE id=?",
            (STATUS_PO_ZWROCIE, lead["id"]))
        # `zapisz_log` odświeża `ostatnia_aktywnosc`, ale to zapis systemowy —
        # kto/co jest jawnie oznaczone, żeby nie wyglądało na ruch handlowca.
        zapisz_log(conn, lead_id=lead["id"], kto=kto, co="auto-zwrot po terminie",
                   pole="handlowiec", przed=lead["handlowiec"], po=None)
    if lista:
        conn.commit()
    return lista


def przeglad(conn, dzis=None, teraz=None):
    """
    Wołane przy zwykłym ruchu w aplikacji: wykonuje zwrot, ale nie częściej
    niż raz na `CO_ILE_MINUT`. Dzięki temu automat działa bez crona i bez wątku
    w tle — czyli bez elementu, który na VPS potrafi cicho umrzeć i nikt nie
    zauważy przez tydzień.

    Zwraca listę zwróconych leadów (pustą, gdy nie była jeszcze pora).
    """
    teraz = teraz or dt.datetime.now()
    ostatni = meta_get(conn, META_KLUCZ)
    if ostatni:
        try:
            if (teraz - dt.datetime.fromisoformat(ostatni)) < dt.timedelta(minutes=CO_ILE_MINUT):
                return []
        except ValueError:
            pass                      # zepsuty znacznik → traktujemy jak brak
    zwrocone = wykonaj(conn, dzis=dzis)
    meta_set(conn, META_KLUCZ, teraz.isoformat(timespec="seconds"))
    conn.commit()
    return zwrocone
