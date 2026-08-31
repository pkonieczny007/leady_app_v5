# -*- coding: utf-8 -*-
"""
Warstwa plikowa mostu: gdzie piszemy, jak piszemy i co po sobie sprzątamy.

DWIE ZASADY, KTÓRE TU RZĄDZĄ WSZYSTKIM

1. ZAPIS ATOMOWY. Odbiorca czyta te pliki w losowym momencie — my nie wiemy
   kiedy i nie mamy jak się z nim umówić. Zapis wprost do `zajecia.json`
   znaczyłby, że prędzej czy później ktoś przeczyta plik w połowie i dostanie
   błąd parsowania albo, gorzej, obcięty grafik wyglądający na kompletny.
   Piszemy więc do `.tmp` obok i podmieniamy przez `os.replace()`, które na
   jednym systemie plików jest atomowe: odbiorca widzi albo starą całość,
   albo nową całość, nigdy stanu pośredniego.

2. KATALOG NA PROFIL, NIE WSPÓLNY. `MOST_DIR` ustawia docker-compose osobno dla
   demo i produkcji — z tego samego powodu, dla którego te dwie usługi mają
   osobne wolumeny. Wspólny katalog znaczyłby, że dane z bazy testowej trafiają
   do partnera jako produkcyjne, a nikt by tego nie zauważył, bo plik nazywa się
   tak samo. Dla pewności `profil` jedzie też W ŚRODKU każdego pliku.

Poza kontenerem (uruchomienie z Windows, testy) domyślny katalog to `most_dane/`
w repozytorium — jest w `.gitignore`, bo niesie nazwy i adresy placówek.
"""
import datetime as dt
import json
import os
import tempfile

import db

# MOST_DIR wygrywa (ustawia go docker-compose), potem katalog danych profilu,
# na końcu katalog w repozytorium. Ta sama kolejność co przy kopiach w
# `narzedzia/baza.py` — kto raz zrozumiał tamto, rozumie i to.
KATALOG = (os.environ.get("MOST_DIR")
           or (os.path.join(db.DATA_DIR, "most") if os.environ.get("DATA_DIR")
               else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "most_dane")))

PLIK_DANE = "zajecia.json"
PLIK_XLSX = "zajecia.xlsx"
PLIK_STAN = "stan.json"
PLIK_ZMIANY = "zmiany.jsonl"

# Ile miesięcznych dzienników zostawiamy. Dziennik jest pomocniczy — pełną
# prawdę niesie `zajecia.json` — więc trzymanie go w nieskończoność tylko
# zajmowałoby miejsce na wolumenie.
ROTACJA_MIESIECY = 6


def sciezka(nazwa):
    return os.path.join(KATALOG, nazwa)


def przygotuj_katalog():
    os.makedirs(KATALOG, exist_ok=True)
    return KATALOG


def zapisz_atomowo(nazwa, dane, binarnie=False):
    """
    Podmienia plik w jednym kroku. `dane` to `str` albo `bytes`.

    Plik tymczasowy powstaje W TYM SAMYM katalogu, nie w systemowym `temp` —
    `os.replace()` przez granicę systemów plików nie jest atomowe i na
    dockerowym wolumenie wywaliłoby się błędem „cross-device link".
    """
    przygotuj_katalog()
    cel = sciezka(nazwa)
    tryb, kodowanie = ("wb", None) if binarnie else ("w", "utf-8")
    fd, tmp = tempfile.mkstemp(dir=KATALOG, prefix=".tmp_", suffix="_" + nazwa)
    os.close(fd)
    try:
        with open(tmp, tryb, encoding=kodowanie, newline="" if not binarnie else None) as f:
            f.write(dane)
        os.replace(tmp, cel)
    except Exception:
        # Nieudany zapis nie może zostawić śmiecia, który przy następnym
        # uruchomieniu wygląda jak kompletny plik.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return cel


def zapisz_json(nazwa, obiekt):
    # `ensure_ascii=False` — po drugiej stronie stoi człowiek, który ma w tym
    # rozpoznać nazwę swojej szkoły, a nie ciąg łą.
    return zapisz_atomowo(nazwa, json.dumps(obiekt, ensure_ascii=False, indent=2) + "\n")


def utworz_dziennik():
    """Zakłada pusty dziennik, jeśli go nie ma. Nie rusza istniejącego."""
    przygotuj_katalog()
    p = sciezka(PLIK_ZMIANY)
    if not os.path.exists(p):
        open(p, "a", encoding="utf-8").close()
    return p


def dopisz_zmiane(wpis):
    """
    Dziennik zmian: jedna linia JSON na zdarzenie, dopisywana na koniec.

    Dlaczego dopisywanie, a nie przepisanie całości: odbiorca, który już raz
    wciągnął migawkę, potrzebuje wiedzieć CO SIĘ ZMIENIŁO od tamtej pory —
    inaczej przy każdym imporcie musi porównywać cały grafik z całym grafikiem.
    Plik przyrostowy jest tu tańszy dla obu stron.

    Dopisanie nie jest atomowe i celowo nie próbujemy tego udawać: linia jest
    krótka, zapisuje się jednym `write`, a odbiorca czytający w połowie zgubi
    najwyżej ostatnią pozycję dziennika — nigdy migawkę, która jest źródłem prawdy.
    """
    przygotuj_katalog()
    nazwa = "zmiany-%s.jsonl" % dt.date.today().strftime("%Y-%m")
    linia = json.dumps(wpis, ensure_ascii=False) + "\n"
    for cel in (nazwa, PLIK_ZMIANY):
        with open(sciezka(cel), "a", encoding="utf-8") as f:
            f.write(linia)
    return sciezka(nazwa)


def sprzatnij_dzienniki(trzymaj=None):
    """Zostawia `trzymaj` ostatnich dzienników miesięcznych, resztę kasuje."""
    trzymaj = ROTACJA_MIESIECY if trzymaj is None else trzymaj
    if not os.path.isdir(KATALOG):
        return []
    stare = sorted(n for n in os.listdir(KATALOG)
                   if n.startswith("zmiany-") and n.endswith(".jsonl"))
    do_kasacji = stare[:-trzymaj] if trzymaj > 0 else stare
    for n in do_kasacji:
        try:
            os.unlink(sciezka(n))
        except OSError:
            pass
    return do_kasacji


def czytaj_json(nazwa, domyslnie=None):
    """
    Zawartość pliku albo wartość domyślna.

    Uszkodzony plik traktujemy jak brak, a nie jak błąd. To jest świadome:
    pojedynczy zepsuty plik pomocniczy (np. skróty do liczenia różnic) ma
    najwyżej spowodować, że dziennik zmian powtórzy jeden wpis — nie ma prawa
    zatrzymać wystawiania grafiku.
    """
    try:
        with open(sciezka(nazwa), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if domyslnie is None else domyslnie


def czytaj_stan():
    """Zawartość `stan.json`. Do sprawdzenia „czy most żyje"."""
    return czytaj_json(PLIK_STAN, {})
