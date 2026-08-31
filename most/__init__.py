# -*- coding: utf-8 -*-
"""
Most: wystawianie grafiku zajęć aplikacji partnerskiej (Akademia Silesia3D).

CO TO JEST
Katalog na serwerze, w którym leży zawsze aktualny grafik naszych zajęć —
`zajecia.json` (do maszyny), `zajecia.xlsx` (do człowieka), `zmiany.jsonl`
(co się zmieniło od poprzedniej migawki) i `stan.json` (czy most żyje).
Odbiorca czyta te pliki, kiedy chce; my nie wiemy kiedy i nie musimy wiedzieć.

DLACZEGO PLIK, A NIE ZAPIS WPROST DO ICH BAZY
Ich aplikacja to statyczny front z bazą w chmurze — nie ma żadnego mechanizmu
przyjmowania danych z zewnątrz i nie mamy do tej bazy konta ani potwierdzenia
reguł dostępu. Plik jest jedynym końcem, który możemy zbudować i sprawdzić sami,
bez czekania na cudzą decyzję. Gdy konto się pojawi, format zostaje bez zmiany,
a dochodzi tylko strona wpisująca.

DLACZEGO NA RUCHU, A NIE Z CRONA
Ten sam powód, dla którego automat zwrotu leadów wisi na `before_request`:
cron na VPS potrafi cicho przestać działać i nikt nie zauważa przez tydzień,
a wątek w tle ginie przy restarcie gunicorna. Tutaj wystarczy, żeby ktokolwiek
otworzył ekran — a handlowiec, który właśnie zapisał zajęcia, otwiera ekran
zawsze, bo zapis kończy się przeładowaniem.

DWA ZEGARY, NIE JEDEN
  • zmiana → przepisujemy po `MIN_ODSTEP_SEK`. To jest „aktualizuje się, jak PH
    coś wpisze". Odstęp chroni przed przepisywaniem pliku po kilka razy w trakcie
    jednego zapisu formularza (a ten zapisuje wszystko jednym żądaniem).
  • cisza → przepisujemy i tak co `CO_ILE_MINUT`. Bez tego zamarły znacznik
    w `stan.json` wygląda identycznie jak „nic się nie zmieniło" i awaria mostu
    wychodzi dopiero, gdy ktoś zapyta, czemu nie ma nowych zajęć.

UŻYCIE
    import most
    most.przeglad(conn)          # hak na ruchu, sam pilnuje częstotliwości
    most.zapisz(conn)            # przepisz teraz, bez pytania o zegar
    python -m most --stan        # z linii poleceń
"""
import datetime as dt
import os

from db import meta_get, meta_set, MOST_BRUDNY

from . import arkusz, dane, pliki

META_OSTATNI = "most_ostatni"

# Najkrótszy odstęp między przepisaniem plików po zmianie w bazie.
MIN_ODSTEP_SEK = int(os.environ.get("MOST_ODSTEP_SEK", "20"))
# Co ile minut przepisujemy nawet bez żadnej zmiany — bicie serca.
CO_ILE_MINUT = int(os.environ.get("MOST_CO_ILE_MINUT", "60"))
# Wyłącznik awaryjny. Gdyby most zaczął ciążyć żądaniom, wystarczy zmienna
# środowiskowa i restart — bez cofania wdrożenia.
WLACZONY = (os.environ.get("MOST", "1").strip().lower() not in ("0", "nie", "off"))

PLIK_SKROTY = ".skroty.json"


def oznacz_zmiane(conn):
    """
    „W bazie coś się ruszyło". Woła to `db.zapisz_log`, czyli JEDNO miejsce,
    przez które przechodzi każdy zapis eventu i leada — endpointów piszących po
    kalendarzu jest osiem i dziewiąty powstanie bez przypomnienia.

    Świadomie bez `commit()`: siedzimy w transakcji wywołującego. Gdyby ta
    transakcja się wycofała, znacznik ma się wycofać razem z nią.
    """
    meta_set(conn, MOST_BRUDNY, "1")


def _czas_ostatniego(conn):
    s = meta_get(conn, META_OSTATNI)
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None               # zepsuty znacznik → traktujemy jak brak


def czy_pora(conn, teraz=None):
    """(bool, powód) — rozdzielone od `przeglad`, żeby dało się to przetestować i pokazać."""
    teraz = teraz or dt.datetime.now()
    ostatni = _czas_ostatniego(conn)
    if ostatni is None:
        return True, "pierwsze uruchomienie"
    minelo = teraz - ostatni
    brudne = bool(meta_get(conn, MOST_BRUDNY))
    if brudne and minelo >= dt.timedelta(seconds=MIN_ODSTEP_SEK):
        return True, "zmiana w bazie"
    if minelo >= dt.timedelta(minutes=CO_ILE_MINUT):
        return True, "odświeżenie okresowe"
    return False, "za wcześnie"


def zapisz(conn, teraz=None):
    """
    Przepisuje komplet plików. Zwraca podsumowanie (to samo, co ląduje w `stan.json`).

    KOLEJNOŚĆ JEST CELOWA: najpierw dane, potem dziennik, na końcu skróty.
    Gdyby coś padło w połowie, przy następnym przebiegu różnice policzą się
    jeszcze raz od starych skrótów — czyli najwyżej powtórzymy wpis w dzienniku.
    Odwrotna kolejność gubiłaby zmianę bezpowrotnie, a to jest jedyny rodzaj
    błędu, którego odbiorca nie ma jak zauważyć.
    """
    teraz = teraz or dt.datetime.now()
    migawka = dane.zbuduj(conn, teraz=teraz)

    pliki.zapisz_json(pliki.PLIK_DANE, migawka)
    pliki.zapisz_atomowo(pliki.PLIK_XLSX, arkusz.zbuduj(migawka), binarnie=True)
    # Dziennik ma ISTNIEĆ od pierwszego przebiegu, także pusty. Odbiorca, który
    # go odpytuje, ma dostać zero linii, a nie „nie ma takiego pliku" — to dwie
    # różne wiadomości i tylko jedna z nich jest prawdziwa.
    pliki.utworz_dziennik()

    stare = pliki.czytaj_json(PLIK_SKROTY, {})
    nowe = dane.skroty(migawka)
    zmiany = dane.roznice(stare, nowe, migawka, teraz=teraz)
    for wpis in zmiany:
        pliki.dopisz_zmiane(wpis)
    pliki.zapisz_json(PLIK_SKROTY, nowe)
    pliki.sprzatnij_dzienniki()

    stan = {
        "format": migawka["format"],
        "wygenerowano": migawka["wygenerowano"],
        "profil": migawka["profil"],
        "katalog": pliki.KATALOG,
        "liczby": migawka["liczby"],
        "zmian_w_tym_przebiegu": len(zmiany),
        "pliki": {"dane": pliki.PLIK_DANE, "arkusz": pliki.PLIK_XLSX,
                  "dziennik": pliki.PLIK_ZMIANY},
    }
    pliki.zapisz_json(pliki.PLIK_STAN, stan)

    meta_set(conn, META_OSTATNI, teraz.isoformat(timespec="seconds"))
    meta_set(conn, MOST_BRUDNY, "")
    conn.commit()
    return stan


def przeglad(conn, teraz=None):
    """
    Wołane przy zwykłym ruchu w aplikacji. Zwraca `stan` albo `None`, gdy nie było pory.

    Cały wyjątek łapiemy tutaj, nie u wywołującego: most jest DODATKIEM.
    Handlowiec stojący na szkolnym korytarzu ma zapisać wizytę także wtedy, gdy
    katalog wymiany zniknął, dysk się zapełnił albo partner odmontował wolumen.
    """
    if not WLACZONY:
        return None
    try:
        pora, _powod = czy_pora(conn, teraz=teraz)
        if not pora:
            return None
        return zapisz(conn, teraz=teraz)
    except Exception as e:                       # noqa: BLE001 — celowo szeroko
        import logging
        logging.getLogger("most").warning("most nie zapisał plików: %s", e)
        return None
