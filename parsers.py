# -*- coding: utf-8 -*-
"""
parsers.py — czyste funkcje parsujące dane wejściowe klienta (SILESIA 3D, leady_app_v3).

Zasady:
  * ZERO zależności zewnętrznych (tylko stdlib) i ZERO zależności od Flask / DB /
    openpyxl. Funkcje przyjmują to, co openpyxl zwraca z komórki (``cell.value``)
    albo tekst z formularza HTML.
  * Każda funkcja jest TOLERANCYJNA: śmieci zwracają ``None`` / puste, nigdy wyjątek.
    Dzięki temu import realnego pliku nie wysypuje się na jednej komórce.
  * Nic nie jest po cichu gubione: funkcje normalizujące słowniki zwracają
    oczyszczoną wartość wejściową, gdy nie potrafią jej rozpoznać — wywołujący
    ma wtedy szansę ją zaraportować.

Skąd wzięte przypadki testowe:
  * ``PH Nowy  Nad którym pracuję jako główny  .xlsx``  (stan aktualny)
  * ``DT 2025-2026 NOWY PIĘKNY PLIK.xlsx``              (poprzedni sezon, dużo
    bardziej "brudny" — stamtąd pochodzą zakresy godzin i wielodniowe cykle)

Spis funkcji publicznych:
  parse_date(v)                     -> datetime.date | None
  parse_time(v)                     -> datetime.time | None
  parse_time_range(v, ze_reszta)    -> (time|None, time|None) [+ reszta gdy ze_reszta]
  parse_time_ranges(v)              -> (list[(time, time)], list[str])
  parse_int_loose(v)                -> int | None
  parse_phone(v)                    -> str | None
  parse_dni_tygodnia(v)             -> list[str]
  strip_prefix(v)                   -> (str|None, str)
  norm_slownik(v, rodzaj, aliasy)   -> str | None
  norm_placowka(v)                  -> (str, str)

Dane (a nie kod):
  SLOWNIKI  — kanoniczne listy wartości per rodzaj słownika
  ALIASY    — mapowania literówek i wariantów klienta -> wartość kanoniczna
  DNI_TYGODNIA / TYPY_PLACOWKI
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata

__all__ = [
    "parse_date",
    "parse_time",
    "parse_time_range",
    "parse_time_ranges",
    "parse_int_loose",
    "parse_phone",
    "parse_dni_tygodnia",
    "strip_prefix",
    "norm_slownik",
    "norm_placowka",
    "SLOWNIKI",
    "ALIASY",
    "DNI_TYGODNIA",
    "TYPY_PLACOWKI",
    "RODZAJE_SLOWNIKOW",
]

# ---------------------------------------------------------------------------
# DANE: dni tygodnia
# ---------------------------------------------------------------------------

DNI_TYGODNIA = [
    "poniedziałek",
    "wtorek",
    "środa",
    "czwartek",
    "piątek",
    "sobota",
    "niedziela",
]

#: wzorce rozpoznające dzień tygodnia w tekście (pełne nazwy, odmiany, skróty
#: używane przez klienta w kolumnach "CYKLICZNE dzień tygodnia" i "Cykliczne / sala")
#: ``_KON`` = koniec skrótu: kolejnym znakiem nie może być litera, ALE może być
#: cyfra — klient realnie pisze "Pon12:40-13:40" bez spacji.
_KON = r"(?![a-ząćęłńóśźż])"
_WZORCE_DNI: list[tuple[str, str]] = [
    ("poniedziałek", rf"poniedzia[łl]\w*|\bpon\.?{_KON}|\bpn\.?{_KON}"),
    ("wtorek", rf"wtork\w*|wtorek|\bwt\.?{_KON}"),
    ("środa", rf"[śs]rod\w*|[śs]roda|[śs]rod[eę]|\b[śs]r\.?{_KON}"),
    ("czwartek", rf"czwart\w*|\bczw\.?{_KON}|\bcz\.?{_KON}"),
    ("piątek", rf"pi[ąa]tk\w*|pi[ąa]tek|\bpt\.?{_KON}"),
    ("sobota", rf"sobot\w*|\bsob\.?{_KON}|\bsb\.?{_KON}"),
    ("niedziela", rf"niedziel\w*|\bnd\.?{_KON}|\bndz\.?{_KON}"),
]

# ---------------------------------------------------------------------------
# DANE: typy placówek
# ---------------------------------------------------------------------------

TYPY_PLACOWKI = ("szkoła", "przedszkole", "instytucja kultury", "nieznany")

#: kody skrótowe używane przez klienta (legenda z ich własnego pliku:
#: "PP - prywatne przedszkole, PM - publiczne (miejskie)")
_KODY_PRZEDSZKOLE = ("PP", "PM", "PS")
_KODY_SZKOLA = ("MSP", "ZSP", "ZPO", "SP", "ZS")

_RE_KULTURA = re.compile(
    r"\b(MDK|MOK|DOM\s+KULTURY|OŚRODEK\s+KULTURY|OSRODEK\s+KULTURY|"
    r"CENTRUM\s+KULTURY|BIBLIOTEK\w*|ŚWIETLIC\w*|SWIETLIC\w*|MUZEUM)\b",
    re.IGNORECASE,
)
#: UWAGA na granicę słowa: bez ``\b`` wzorzec "SZKO[ŁL]" trafiał w środek słowa
#: "PRZEDSZKOLE" i klasyfikował przedszkola jako szkoły.
_RE_PRZEDSZKOLE = re.compile(r"\bPRZEDSZKOL\w*", re.IGNORECASE)
_RE_SZKOLA_SLOWO = re.compile(
    r"\bSZKO[ŁL]\w*|\bLICE\w*|\bGIMNAZJ\w*|\bZESP[ÓO][ŁL]\s+SZK", re.IGNORECASE
)
#: kod skrótowy BEZ numeru ("Niepubliczna SP MARANATHA", "PP Mundo Marino")
_RE_KOD_SAM = re.compile(r"\b(MSP|ZSP|ZPO|SP|ZS|PP|PM|PS)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# DANE: słowniki kanoniczne
#
# UWAGA — kluczowe ustalenie z audytu danych:
# prefiks numeryczny ("01. ", "24. ") u klienta NIE JEST identyfikatorem.
# Ten sam numer oznacza w dwóch listach dwie różne osoby (np. "18. Bitner"
# w kolumnie Y vs "18. Młynarczyk Adam" w kolumnie O; "20. Sacawa" vs
# "20. Trener 1"). Dlatego:
#   - TOŻSAMOŚCIĄ jest część nazwowa (po prefiksie),
#   - prefiks jest tylko podpowiedzią sortowania i MOŻE się powtarzać
#     w liście kanonicznej (patrz "21. Trener 2" i "21. Trener 3").
# ---------------------------------------------------------------------------

SLOWNIKI: dict[str, list[str]] = {
    # kolumna A
    "handlowiec": [
        "01. Sacawa",
        "02. Olszewska",
        "03. Małolepsza",
        "04. Chytry",
        "05. Młynarczyk",
        "Bitner",  # w BAZA!A występuje bez prefiksu — świadomie zachowane
    ],
    # kolumna B
    "status_szkoly": [
        "01. Nowa szkoła",
        "02. Kontynuacja",
    ],
    # kolumna C
    "status_realizacji": [
        "01. Próba kontaktu (Brak konkretów)",
        "02. Próba kontaktu (czekam na termin)",
        "03. DT umówione",
        "04. BRAK KONTAKTU ZE SZKOŁĄ",
    ],
    # kolumna L
    "dt": [
        "01. Tak",
        "02. Do ustalenia",
    ],
    # kolumny T, U, Z..AG
    "tak_nie": [
        "01. Tak",
        "02. Nie",
    ],
    # kolumna Q
    "mail_propozycja": [
        "01. Podsumowanie DT",
        "02. Propozycja DT",
    ],
    # kolumna V
    "dzien_tygodnia": list(DNI_TYGODNIA[:6]),  # klient nie używa niedzieli
    # kolumna E — numeracja z BAZA (LISTA 5), nazwy oczyszczone
    # (bez "powiat", z polskimi znakami). 21-25 dołożone z listy Sacawy.
    "miejscowosc": [
        "01. Orzesze",
        "02. Mikołów",
        "03. Łaziska Górne",
        "04. Tychy",
        "05. Knurów",
        "06. Rybnik",
        "07. Żory",
        "08. Katowice",
        "09. Pszczyna",
        "10. Piekary Śląskie",
        "11. Siemianowice Śląskie",
        "12. Świętochłowice",
        "13. Sosnowiec",
        "14. Dąbrowa Górnicza",
        "15. Będzin",
        "16. Chorzów",
        "18. Jaworzno",
        "19. Zabrze",
        "20. Ruda Śląska",
        "21. Strzyżowice",
        "22. Ornontowice",
        "23. Wyry",
        "24. Gostyń",
        "25. Katowice Południe",
    ],
    # kolumny O i Y — JEDNA lista scalona z dwóch list klienta
    "trener": [
        "01. Małolepsza",
        "02. Olszewska",
        "03. Majewska",
        "04. Zemela",
        "05. Polakowska",
        "06. Jankowska",
        "07. Krzysztofik",
        "08. Brzozowska",
        "09. Bochniarz",
        "10. Łukaszek",
        "11. Białas (Pszczyna)",
        "12. Jasińska Nina",
        "13. Cebula",
        "14. Swoboda",
        "15. Gawron",
        "16. Król",
        "17. Paziewski",
        "18. Bitner",
        "18. Młynarczyk Adam",  # prefiks 18 zdublowany u klienta (lista O vs Y)
        "19. Leśniak",
        "20. Sacawa",
        "20. Trener 1",  # prefiks 20 zdublowany u klienta
        "21. Płaszczymąka",
        "21. Trener 2",
        "21. Trener 3",
        "22. Kopczyński",
        "22. Trener 4",
        "23. Bednarek",
        "24. Palus",
        "24. Trener 5",
        "25. Adamczyk",
        "26. Miękina",
        "27. Bąk-Kopaniarz",
        "28. Musiał",
        "29. Cichoń",
        "30. Jeziorczak",
        # dodatkowo trenerzy występujący u klienta tylko z imieniem
        "01. Olszewska Zuza",
        "02. Sacawa Dominika",
        "03. Zemela Paulina",
    ],
}

RODZAJE_SLOWNIKOW = tuple(SLOWNIKI.keys())

# ---------------------------------------------------------------------------
# DANE: aliasy — literówki i warianty klienta -> wartość kanoniczna
#
# To są DANE, nie kod. Każda pozycja ma udokumentowane źródło w pliku klienta.
# ---------------------------------------------------------------------------

ALIASY: dict[str, dict[str, str]] = {
    "handlowiec": {
        # walidacja Sacawa!A20:A200 i Olszewska!A29:A340 — literówka w nazwisku
        "02. Olaszewska": "02. Olszewska",
        "02. Olszewsak": "02. Olszewska",
        # BAZA!A — jedna komórka bez prefiksu
        "bitner": "Bitner",
        "18. Bitner": "Bitner",
    },
    "trener": {
        # Kalendarz *!A13 vs walidacja Y — podwójne "s"
        "11. Białass (Pszczyna)": "11. Białas (Pszczyna)",
        "11. Bialas (Pszczyna)": "11. Białas (Pszczyna)",
        # Kalendarz *!A25 "23. Trenner 5" vs walidacja O "24. Trener 5"
        "23. Trenner 5": "24. Trener 5",
        "23. Trener 5": "24. Trener 5",
        # walidacja O "22. Trene 3" vs Kalendarz *!A23 "21. Trener 3"
        "22. Trene 3": "21. Trener 3",
        "22. Trener 3": "21. Trener 3",
        # walidacja O "23. Trener 4" vs Kalendarz *!A24 "22. Trener 4"
        "23. Trener 4": "22. Trener 4",
        # kolizja prefiksów list O/Y — obie formy prowadzą do tej samej osoby
        "18. Młynarczyk Adam": "18. Młynarczyk Adam",
        "18. Mlynarczyk Adam": "18. Młynarczyk Adam",
        # puste pozycje 31.-40. z walidacji Y — świadomie odrzucane
        "31.": "",
        "32.": "",
        "33.": "",
        "34.": "",
        "35.": "",
        "36.": "",
        "37.": "",
        "38.": "",
        "39.": "",
        "40.": "",
    },
    "miejscowosc": {
        # BAZA ma "powiat", handlowcy nie — scalamy do formy bez "powiat"
        "09. Pszczyna powiat": "09. Pszczyna",
        "15. Będzin powiat": "15. Będzin",
        "15. Bedzin powiat": "15. Będzin",
        # lista Sacawy (LISTA 11) ma inną numerację i literówkę
        "19. Chorzow": "16. Chorzów",
        "10. Katowice": "08. Katowice",
        "08. Katowice Południe": "25. Katowice Południe",
        "11. Zabrze": "19. Zabrze",
        "12. Ruda Śląska": "20. Ruda Śląska",
        "13. Świętochłowice": "12. Świętochłowice",
        "14. Siemianowice Śląskie": "11. Siemianowice Śląskie",
        "15. Piekary Śląskie": "10. Piekary Śląskie",
        "16. Dąbrowa Górnicza": "14. Dąbrowa Górnicza",
        "17. Sosnowiec": "13. Sosnowiec",
        "20. Ornontowice": "22. Ornontowice",
        "21. Wyry": "23. Wyry",
        "22. Gostyń": "24. Gostyń",
        # dublet w tej samej liście walidacji (14 i 17 = to samo miasto)
        "17. Dąbrowa Górnicza": "14. Dąbrowa Górnicza",
        # literówka w LISTA 12
        "21. Strzyzowice": "21. Strzyżowice",
    },
    "status_realizacji": {
        # status z notatek ze spotkania 24.07, którego jeszcze nie ma w walidacji
        "DT w trakcie umawiania": "02. Próba kontaktu (czekam na termin)",
    },
    "status_szkoly": {},
    "dt": {},
    "tak_nie": {
        "tak": "01. Tak",
        "nie": "02. Nie",
        "TAK": "01. Tak",
        "NIE": "02. Nie",
    },
    "mail_propozycja": {},
    "dzien_tygodnia": {},
}


# ---------------------------------------------------------------------------
# Pomocnicze (prywatne)
# ---------------------------------------------------------------------------


#: błędy formuł przenoszone przez openpyxl jako zwykły tekst. NIE NIOSĄ DANYCH.
#: Realnie występują w `Zbiorczy` i `Niewykorzystane rekordy` (arkusze liczone
#: formułami `VSTACK`/`QUERY` przeniesionymi z Google Sheets).
_BLEDY_EXCEL = frozenset(
    {
        "#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NULL!", "#NUM!",
        "#SPILL!", "#CALC!", "#ERROR!", "#GETTING_DATA", "N/A", "#NIE_DOTYCZY",
    }
)

#: formuła zwracająca stały tekst — tak wygląda `BAZA!I4` = `="601290441"`
_RE_FORMULA_TEKST = re.compile(r'^\s*=\s*"(.*)"\s*$', re.DOTALL)

#: znacznik formuły przeniesionej z Google Sheets przez eksport do XLSX.
#: Postać: ``=IFERROR(__xludf.DUMMYFUNCTION("""ORYGINALNA FORMUŁA"""), <ostatnio
#: policzona wartość>)`` — OSTATNI literał tekstowy zawiera realną wartość.
#: Dzięki temu import v3 przetrwa plik bez cache'a wartości (to był realny
#: sposób, w jaki importer v1 wczytywał 0 rekordów i meldował sukces).
_XLUDF = "__xludf.DUMMYFUNCTION"
_RE_LITERAL = re.compile(r'"([^"]*)"')


def _txt(v) -> str:
    """Zamienia dowolną wartość na tekst; zwija białe znaki. ``None`` -> ''.

    Dodatkowo — jedno miejsce, które chroni WSZYSTKIE parsery:
      * błąd formuły (``#N/A``, ``#REF!`` …) -> ``''`` (brak danych, nie tekst)
      * formuła zwracająca stały tekst (``="601290441"``) -> jej treść
      * formuła z eksportu Google Sheets
        (``=IFERROR(__xludf.DUMMYFUNCTION(<oryginał>),"32 235 27 15")``)
        -> ostatnia policzona wartość z argumentu awaryjnego
      * każda inna formuła (``=B2+1``, ``=XLOOKUP(...)``) -> ``''``
    """
    if v is None:
        return ""
    s = v if isinstance(v, str) else str(v)
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""
    if s.upper() in _BLEDY_EXCEL:
        return ""
    if s.startswith("="):
        m = _RE_FORMULA_TEKST.match(s)
        if m:
            return _txt(m.group(1))
        if _XLUDF in s:
            for lit in reversed(_RE_LITERAL.findall(s)):
                lit = lit.strip()
                if lit and lit != "COMPUTED_VALUE":
                    return _txt(lit)
        return ""
    return s


def _fold(s: str) -> str:
    """Składa tekst do postaci porównywalnej: bez diakrytyków, małe litery,
    bez znaków interpunkcyjnych, zwinięte spacje.

    >>> _fold("11. Białass (Pszczyna)")
    '11. bialass (pszczyna)'
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # polskie ł nie rozkłada się przez NFKD
    s = s.replace("ł", "l").replace("Ł", "L")
    return re.sub(r"\s+", " ", s).strip().lower()


def _lev_max1(a: str, b: str) -> bool:
    """Czy odległość Levenshteina między ``a`` i ``b`` wynosi co najwyżej 1.

    Świadomie prosta implementacja z wczesnym wyjściem — porównujemy krótkie
    nazwiska, więc wydajność nie ma znaczenia, a czytelność ma.
    """
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:  # jedno podstawienie
        diff = sum(1 for x, y in zip(a, b) if x != y)
        return diff <= 1
    # jedno wstawienie / usunięcie
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def _is_bool(v) -> bool:
    return isinstance(v, bool)


# ---------------------------------------------------------------------------
# DATY
# ---------------------------------------------------------------------------

#: kolejność ma znaczenie: najpierw ISO, potem dzień-pierwszy z 4-cyfrowym rokiem,
#: na końcu dzień-pierwszy z 2-cyfrowym rokiem (tylko z kropkami, żeby nie łapać
#: fragmentów zakresów godzin typu "12.35-13.35").
_RE_DATY = (
    ("ymd", re.compile(r"(?<!\d)(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})(?!\d)")),
    # separator może być też przecinkiem ("24,04,2026") i mieć spacje ("16 .10.2025")
    ("dmy4", re.compile(r"(?<!\d)(\d{1,2})\s*[-/.,]\s*(\d{1,2})\s*[-/.,]\s*(\d{4})(?!\d)")),
    ("dmy2", re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{2})(?!\d)")),
)

#: najmniejszy akceptowany numer serialny Excela (1000 == 1902-09-26).
#: Chroni przed zamianą liczby porządkowej / liczby klas w datę 1900-01-08.
_MIN_SERIAL_EXCEL = 1000
_MAX_SERIAL_EXCEL = 2958465  # 9999-12-31


def _serial_excel_na_date(n: float) -> _dt.date | None:
    """Zamienia numer serialny Excela (system 1900, z jego pluskwą 29.02.1900)
    na ``datetime.date``. Zwraca ``None`` poza sensownym zakresem.
    """
    if n < _MIN_SERIAL_EXCEL or n > _MAX_SERIAL_EXCEL:
        return None
    dni = int(n)
    baza = _dt.date(1899, 12, 30) if dni >= 60 else _dt.date(1899, 12, 31)
    try:
        return baza + _dt.timedelta(days=dni)
    except (OverflowError, ValueError):
        return None


def parse_date(v) -> _dt.date | None:
    """Parsuje datę z dowolnej wartości spotykanej w plikach klienta.

    Obsługuje:
      * ``datetime.datetime`` / ``datetime.date`` — bierze część dzienną
      * ``"2026-09-10"``, ``"2026/09/10"`` (ISO)
      * ``"10.09.2026"``, ``"5-09-2025"``, ``"10/09/2026"`` (dzień pierwszy)
      * ``"10.09.26"`` (rok dwucyfrowy -> 20xx)
      * datę ZANURZONĄ w tekście: ``"26.11.2025 8:00-11:00"``,
        ``"9:00 2025-10-21"``, ``"20.01.2026r. 9:30-13:00"``,
        ``"2025-10-30 godzina 10:45"`` — bierze PIERWSZĄ poprawną datę
      * liczbę serialną Excela (``45910`` -> 2025-09-08); liczby < 1000
        są odrzucane, żeby "8 klas" nie zamieniło się w 1900-01-08

    Zwraca ``None`` dla: ``None``, pustego tekstu, ``"."``, dat bez roku
    (``"24.09 8:00"``, ``"od 29.09 do 3.10"``), tekstu bez daty
    (``"usuwam natali z kalendarza"``), wartości logicznych.

    >>> parse_date("26.11.2025 8:00-11:00")
    datetime.date(2025, 11, 26)
    >>> parse_date("5-09-2025 8:00-9:35")
    datetime.date(2025, 9, 5)
    >>> parse_date("24.09 8:00 - 10:00") is None
    True
    """
    if v is None or _is_bool(v):
        return None
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, _dt.date):
        return v
    if isinstance(v, (int, float)):
        return _serial_excel_na_date(float(v))

    s = _txt(v)
    if not s:
        return None

    for tryb, rx in _RE_DATY:
        for m in rx.finditer(s):
            a, b, c = (int(x) for x in m.groups())
            if tryb == "ymd":
                y, mo, d = a, b, c
            elif tryb == "dmy4":
                d, mo, y = a, b, c
            else:  # dmy2
                d, mo, y = a, b, 2000 + c
            try:
                return _dt.date(y, mo, d)
            except ValueError:
                continue  # np. "12.35-13.35" -> miesiąc 35, szukamy dalej

    # ostatnia szansa: sam tekst jest liczbą serialną ("45910")
    if re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return _serial_excel_na_date(float(s.replace(",", ".")))
    return None


# ---------------------------------------------------------------------------
# GODZINY
# ---------------------------------------------------------------------------

#: godzina zapisana jako "8:00", "08:55", "8.00", "9:30:00"
_RE_GODZINA = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)(?!\d)")
#: sama godzina bez minut ("8", "15") — dopuszczalna tylko gdy to CAŁA wartość
_RE_GODZINA_SAMA = re.compile(r"^(?:godz\.?|g\.?|od)?\s*([01]?\d|2[0-3])\s*$", re.IGNORECASE)


def _time_z_sekund(sek: float) -> _dt.time | None:
    """Sekundy od północy -> ``datetime.time`` (z zawinięciem modulo 24 h)."""
    if sek < 0:
        return None
    sek = int(round(sek)) % 86400
    return _dt.time(sek // 3600, (sek % 3600) // 60, sek % 60)


def parse_time(v) -> _dt.time | None:
    """Parsuje godzinę z dowolnej wartości spotykanej w plikach klienta.

    Obsługuje:
      * ``datetime.time`` — zwraca bez zmian
      * ``datetime.datetime`` — zwraca część godzinową
      * ``datetime.timedelta`` — realnie występuje w ``N Godzina DT``
        (``timedelta(seconds=31800)`` -> 08:50); zawija modulo 24 h
      * ``float`` 0..1 — część dnia w formacie Excela (``0.375`` -> 09:00)
      * ``float`` >= 1 — bierze część ułamkową serialu (``45910.375`` -> 09:00),
        a dla liczby całkowitej 0..23 traktuje ją jako godzinę (``8.0`` -> 08:00)
      * ``str`` — ``"8:00"``, ``"08:55"``, ``"8.00"``, ``"9:30:00"``,
        ``"godz 9:40"``, ``"15"``; z tekstu wielogodzinowego
        (``"8:00-11:30"``) bierze PIERWSZĄ godzinę

    Zwraca ``None`` dla śmieci (``"do ustalenia w sekretariacie"``, ``"330"``,
    ``"Są cykliczne"``) i dla wartości logicznych.

    >>> parse_time(_dt.timedelta(seconds=31800))
    datetime.time(8, 50)
    >>> parse_time("8.00")
    datetime.time(8, 0)
    >>> parse_time("330") is None
    True
    """
    if v is None or _is_bool(v):
        return None
    if isinstance(v, _dt.time):
        return v
    if isinstance(v, _dt.datetime):
        return v.time()
    if isinstance(v, _dt.timedelta):
        return _time_z_sekund(v.total_seconds())
    if isinstance(v, (int, float)):
        f = float(v)
        if f < 0:
            return None
        if 0 <= f < 1:
            return _time_z_sekund(f * 86400)
        frac = f - int(f)
        if frac > 1e-9:
            return _time_z_sekund(frac * 86400)
        return _dt.time(int(f), 0) if 0 <= f <= 23 else None

    s = _txt(v)
    if not s:
        return None
    m = _RE_GODZINA.search(s)
    if m:
        return _dt.time(int(m.group(1)), int(m.group(2)))
    m = _RE_GODZINA_SAMA.match(s)
    if m:
        return _dt.time(int(m.group(1)), 0)
    return None


#: separator zakresu: "-", "–", "—", " do ", ":" (klient pisze "15:00:15:45")
_RE_ZAKRES = re.compile(
    r"((?:[01]?\d|2[0-3])\s*[:.]\s*[0-5]\d|(?<!\d)(?:[01]?\d|2[0-3])(?!\s*[:.]?\d))"
    r"\s*(?:-|–|—|do)\s*"
    r"((?:[01]?\d|2[0-3])\s*[:.]\s*[0-5]\d|(?<!\d)(?:[01]?\d|2[0-3])(?!\s*[:.]?\d))"
)


def parse_time_ranges(v) -> tuple[list[tuple[_dt.time, _dt.time]], list[str]]:
    """Wyciąga WSZYSTKIE zakresy godzin z komórki oraz resztę tekstu.

    Realne wartości kolumny ``X Zajecia cykliczne (godzina)``:
      ``"13:30-14:30, 14:40-15:40"``, ``"12:55-13:55\\n13:55-14:55"``,
      ``"12:45-13.45 i 13:55-14:55"``, ``"Wt 15-16"``,
      ``"15:20-16:20 16:30-17:30"``,
      ``"2gi Piątek miesiąca : 13.30-14:15, daty:10.10, 14.11, ..."``

    Zwraca ``(zakresy, reszta)``:
      * ``zakresy`` — lista par ``(start, koniec)`` w kolejności wystąpienia
      * ``reszta`` — lista niepustych fragmentów tekstu, które NIE były
        zakresem (dni tygodnia, daty cykli, komentarze). Nic nie ginie.

    >>> zakresy, reszta = parse_time_ranges("Wt 15:00-16:00 ŚR. 15:00-16:00")
    >>> len(zakresy)
    2
    """
    s = _txt(v) if not isinstance(v, (_dt.time, _dt.datetime, _dt.timedelta)) else ""
    if not s:
        t = parse_time(v)
        return ([], []) if t is None else ([], [])
    zakresy: list[tuple[_dt.time, _dt.time]] = []
    reszta: list[str] = []
    poz = 0
    for m in _RE_ZAKRES.finditer(s):
        a = parse_time(m.group(1))
        b = parse_time(m.group(2))
        if a is None or b is None:
            continue
        przed = s[poz : m.start()].strip(" ,;.:/|\n\t")
        if przed:
            reszta.append(przed)
        zakresy.append((a, b))
        poz = m.end()
    ogon = s[poz:].strip(" ,;.:/|\n\t")
    if ogon:
        reszta.append(ogon)
    return zakresy, reszta


def parse_time_range(v, ze_reszta: bool = False):
    """Zwraca PIERWSZY zakres godzin z komórki.

    * ``parse_time_range(v)`` -> ``(start|None, koniec|None)``
    * ``parse_time_range(v, ze_reszta=True)`` -> ``(start, koniec, reszta)``,
      gdzie ``reszta`` to tekst po pierwszym zakresie plus pozostałe zakresy
      w formie surowej (żeby nic nie zginęło przy imporcie).

    Gdy w komórce jest tylko jedna godzina (``time(8, 0)`` albo ``"08:00"``),
    zwraca ``(start, None)`` — koniec nie jest zgadywany.

    >>> parse_time_range("08:00-12:30")
    (datetime.time(8, 0), datetime.time(12, 30))
    >>> parse_time_range("8-9:35")
    (datetime.time(8, 0), datetime.time(9, 35))
    >>> parse_time_range("12:30-14:30, 14:40-15:40", ze_reszta=True)[2]
    '14:40-15:40'
    """
    zakresy, reszta = parse_time_ranges(v)
    if zakresy:
        start, koniec = zakresy[0]
        if ze_reszta:
            ogon: list[str] = []
            for a, b in zakresy[1:]:
                ogon.append(f"{a.strftime('%H:%M')}-{b.strftime('%H:%M')}")
            ogon.extend(reszta)
            return start, koniec, ", ".join(ogon)
        return start, koniec
    start = parse_time(v)
    if ze_reszta:
        return start, None, ", ".join(reszta)
    return start, None


# ---------------------------------------------------------------------------
# LICZBY
# ---------------------------------------------------------------------------

_RE_PIERWSZA_LICZBA = re.compile(r"(?<![\d.,])(\d{1,6})(?![\d]*[.,]\d)")


def parse_int_loose(v) -> int | None:
    """Wyciąga pierwszą liczbę całkowitą z "brudnej" wartości.

    Realne wartości kolumn ``R Ilość klas 1-4`` i ``S Ilość dzieci w klasach``
    (oraz ``DT ilość klas/dzieci`` z pliku poprzedniego sezonu):
      ``"10 klas"`` -> 10, ``"około 200"`` -> 200, ``330`` -> 330,
      ``"ok. 240"`` -> 240, ``"8/200"`` -> 8, ``"2 klasy 43 dzieci"`` -> 2,
      ``"13?"`` -> 13, ``"/9"`` -> 9, ``""`` -> ``None``

    ``datetime`` -> ``None`` (w kolumnie "ilość klas/dzieci" realnie trafiła się
    data ``2025-07-30`` — nie wolno jej zamienić na liczbę).

    >>> parse_int_loose("10 klas"), parse_int_loose("około 200"), parse_int_loose(330)
    (10, 200, 330)
    >>> parse_int_loose("") is None
    True
    """
    if v is None or _is_bool(v):
        return None
    if isinstance(v, (_dt.date, _dt.datetime, _dt.time, _dt.timedelta)):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))
    s = _txt(v)
    if not s:
        return None
    m = _RE_PIERWSZA_LICZBA.search(s)
    if m:
        return int(m.group(1))
    # np. "1 000" albo "12,5"
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


# ---------------------------------------------------------------------------
# TELEFONY
# ---------------------------------------------------------------------------

#: dwucyfrowe strefy numeracyjne w Polsce (numery stacjonarne).
#: Rozłączne z prefiksami komórkowymi (45,50,51,53,57,60,66,69,72,73,78,79,88),
#: więc rozpoznanie po dwóch pierwszych cyfrach jest bezpieczne.
_STREFY_PL = {
    "12", "13", "14", "15", "16", "17", "18", "22", "23", "24", "25", "29",
    "32", "33", "34", "41", "42", "43", "44", "46", "48", "52", "54", "55",
    "56", "58", "59", "61", "62", "63", "65", "67", "68", "71", "74", "75",
    "76", "77", "81", "82", "83", "84", "85", "86", "87", "89", "91", "94", "95",
}

def _format_tel_pl(cyfry: str) -> str | None:
    """9 cyfr -> czytelny format PL. Stacjonarny: ``32 235 27 15``,
    komórkowy: ``601 290 441``. Inna długość -> ``None``.
    """
    if len(cyfry) != 9:
        return None
    if cyfry[:2] in _STREFY_PL:
        return f"{cyfry[:2]} {cyfry[2:5]} {cyfry[5:7]} {cyfry[7:9]}"
    return f"{cyfry[:3]} {cyfry[3:6]} {cyfry[6:9]}"


def parse_phone(v) -> str | None:
    """Normalizuje numer(y) telefonu do jednego, czytelnego dla człowieka formatu.

    Obsługuje realne warianty z pliku klienta:
      * formuła-tekst ``="601290441"`` (tak wygląda ``BAZA!I4`` przy
        ``data_only=False``) oraz jej wynik ``"601290441"``
      * ``float`` z Excela: ``322672142.0``
      * ``"32 235 27 15"``, ``"32 264-13-00"``, ``"(032) 267-49-96"``,
        ``"32/266-10-02"``, ``"32 2675035"``
      * ``"+48 601 290 441"``, ``"0048601290441"``
      * kilka numerów w jednej komórce: ``"(32) 258-35-66  lub  513 - 065 - 806"``,
        ``"32 762 93 51, 32 762 93 57"``, ``"32 211 62 29\\n693 945 512"``
        -> zwraca wszystkie, rozdzielone ``", "``
      * numer z komentarzem: ``"697989257 (można SMS)"`` -> sam numer

    Zwraca ``None``, gdy nie ma ani jednego numeru o poprawnej długości
    (``"Szkolna 24"``, ``"Są cykliczne"``, ``"2 264 16 66"`` — 8 cyfr).
    Komentarze tekstowe są ODRZUCANE (zostają w kolumnie źródłowej) — funkcja
    zwraca wyłącznie numery.

    >>> parse_phone('="601290441"')
    '601 290 441'
    >>> parse_phone("32 235 27 15")
    '32 235 27 15'
    >>> parse_phone("+48 601 290 441")
    '601 290 441'
    """
    if v is None or _is_bool(v):
        return None
    if isinstance(v, float):
        v = f"{v:.0f}" if v == int(v) else str(v)
    elif isinstance(v, int):
        v = str(v)
    s = _txt(v)  # rozwija też formułę ="601290441"
    if not s:
        return None

    # tniemy na kandydatów: sekwencje cyfr / separatorów wewnątrznumerowych
    kandydaci = re.findall(r"(?:\+?\d[\d\s\-\.\(\)/]{6,}\d)", s)
    wynik: list[str] = []
    for kand in kandydaci:
        cyfry = re.sub(r"\D", "", kand)
        # +48 / 0048 / 48 na początku
        if len(cyfry) == 11 and cyfry.startswith("48"):
            cyfry = cyfry[2:]
        elif len(cyfry) == 13 and cyfry.startswith("0048"):
            cyfry = cyfry[4:]
        elif len(cyfry) == 10 and cyfry.startswith("0"):
            cyfry = cyfry[1:]
        if len(cyfry) == 9:
            sform = _format_tel_pl(cyfry)
            if sform and sform not in wynik:
                wynik.append(sform)
        elif len(cyfry) == 18:  # dwa numery zlepione bez separatora
            for pol in (cyfry[:9], cyfry[9:]):
                sform = _format_tel_pl(pol)
                if sform and sform not in wynik:
                    wynik.append(sform)
    return ", ".join(wynik) if wynik else None


# ---------------------------------------------------------------------------
# DNI TYGODNIA
# ---------------------------------------------------------------------------


def parse_dni_tygodnia(v) -> list[str]:
    """Rozbija wartość na listę kanonicznych nazw dni tygodnia (małą literą).

    Realne wartości: ``"poniedziałek"``, ``"Środa"``, ``"Wtorek i środa"``,
    ``"Poniedziałek i piątek"``, ``"wtorek, środa"``, a także skróty z kolumny
    "Cykliczne / sala": ``"Czw 12:50-13:50 INFORMATYCZNA"``,
    ``"PN. 12:25-13:25, PT. 11:25-12:25"``, ``"Poniedziałki gr1: 16:30"``,
    ``"1wsze czwartki miesiąca 15:00-15:45"``.

    Zwraca listę BEZ duplikatów, uporządkowaną według kolejności w tygodniu.
    Brak rozpoznanego dnia -> pusta lista.

    >>> parse_dni_tygodnia("Poniedziałek i piątek")
    ['poniedziałek', 'piątek']
    >>> parse_dni_tygodnia("wtorek, środa")
    ['wtorek', 'środa']
    >>> parse_dni_tygodnia("brak")
    []
    """
    s = _txt(v)
    if not s:
        return []
    low = s.lower()
    znalezione: set[str] = set()
    for kanon, wzor in _WZORCE_DNI:
        if re.search(wzor, low, re.IGNORECASE):
            znalezione.add(kanon)
    return [d for d in DNI_TYGODNIA if d in znalezione]


# ---------------------------------------------------------------------------
# PREFIKSY SŁOWNIKOWE
# ---------------------------------------------------------------------------

_RE_PREFIKS = re.compile(r"^(\d{1,3})\s*[.)]\s*(.*)$", re.DOTALL)


def strip_prefix(v) -> tuple[str | None, str]:
    """Rozbija wartość słownikową na ``(prefiks, nazwa)``.

    Klient używa prefiksów ``01. ``, ``02. `` do SORTOWANIA, więc nie wolno ich
    wyrzucać — trzeba je rozumieć. Prefiks zwracany jest jako ``str``, żeby
    zachować wiodące zero.

    Wymagana kropka lub nawias po numerze — inaczej ``"8 klas"`` zostałoby
    zinterpretowane jako prefiks 8.

    >>> strip_prefix("01. Sacawa")
    ('01', 'Sacawa')
    >>> strip_prefix("11. Białas (Pszczyna)")
    ('11', 'Białas (Pszczyna)')
    >>> strip_prefix("Bitner")
    (None, 'Bitner')
    >>> strip_prefix("31. ")
    ('31', '')
    >>> strip_prefix("8 klas")
    (None, '8 klas')
    """
    s = _txt(v)
    if not s:
        return None, ""
    m = _RE_PREFIKS.match(s)
    if m:
        return m.group(1), m.group(2).strip()
    return None, s


def _klucz_slownikowy(s: str) -> str:
    """Klucz porównawczy dla wartości słownikowej: część nazwowa, złożona
    (bez diakrytyków / wielkości liter), z usuniętym słowem ``powiat``.
    """
    _, nazwa = strip_prefix(s)
    k = _fold(nazwa)
    k = re.sub(r"\bpowiat\w*\b", "", k).strip()
    k = re.sub(r"[.,;]+$", "", k).strip()
    return k


def norm_slownik(v, rodzaj: str, aliasy: dict | None = None) -> str | None:
    """Zwraca kanoniczną wartość słownika dla ``rodzaj``.

    Kolejność rozstrzygania (od najbardziej do najmniej pewnej):
      1. pusta wartość -> ``None``
      2. jawny ALIAS (dane w ``ALIASY[rodzaj]``) — naprawia znane literówki
         klienta: ``02. Olaszewska`` -> ``02. Olszewska``,
         ``11. Białass (Pszczyna)`` -> ``11. Białas (Pszczyna)``,
         ``23. Trenner 5`` -> ``24. Trener 5``, ``22. Trene 3`` -> ``21. Trener 3``
      3. dokładne trafienie w liście kanonicznej
      4. trafienie po CZĘŚCI NAZWOWEJ (prefiks ignorowany) — rozwiązuje
         rozjazdy numeracji: ``10. Katowice`` -> ``08. Katowice``,
         ``09. Pszczyna powiat`` -> ``09. Pszczyna``,
         ``17. Dąbrowa Górnicza`` -> ``14. Dąbrowa Górnicza``
      5. dopasowanie rozmyte (odległość Levenshteina <= 1 po złożeniu tekstu),
         wyłącznie gdy zwycięzca jest JEDYNY — ``19. Chorzow`` -> ``16. Chorzów``,
         ``21. Strzyzowice`` -> ``21. Strzyżowice``

    Gdy nic nie pasuje, zwraca wartość OCZYSZCZONĄ (zwinięte spacje), nigdy
    ``None`` — dzięki temu import nie gubi danych, a raport widzi wartość
    nierozpoznaną. Alias na pusty string oznacza świadome odrzucenie
    (puste pozycje ``31.``–``40.`` z listy trenerów) i daje ``None``.

    ``rodzaj`` poza ``RODZAJE_SLOWNIKOW`` -> zwraca samą oczyszczoną wartość.
    """
    s = _txt(v)
    if not s:
        return None

    mapa = (aliasy if aliasy is not None else ALIASY).get(rodzaj, {})
    kanon = SLOWNIKI.get(rodzaj)

    # 2. alias — po dokładnym tekście, potem po złożonym kluczu
    if s in mapa:
        return mapa[s] or None
    fs = _fold(s)
    for k, w in mapa.items():
        if _fold(k) == fs:
            return w or None

    if not kanon:
        return s

    # 3. dokładne trafienie
    if s in kanon:
        return s
    for c in kanon:
        if _fold(c) == fs:
            return c

    # 4. po części nazwowej
    klucz = _klucz_slownikowy(s)
    if klucz:
        trafienia = [c for c in kanon if _klucz_slownikowy(c) == klucz]
        if trafienia:
            return trafienia[0]

        # 5. rozmyte, tylko jednoznaczne
        blisko = [c for c in kanon if _lev_max1(_klucz_slownikowy(c), klucz)]
        unikalne = {_klucz_slownikowy(c) for c in blisko}
        if len(unikalne) == 1:
            return blisko[0]

    return s


# ---------------------------------------------------------------------------
# PLACÓWKI
# ---------------------------------------------------------------------------

_RE_KOD_NUMER = re.compile(
    r"\b(MSP|ZSP|ZPO|SP|ZS|PP|PM|PS)\s*\.?\s*(\d{1,3})\b", re.IGNORECASE
)
_RE_SP_NR = re.compile(
    r"SZKO[ŁL]A\s+PODSTAWOWA(?:\s+\w+)*?\s+NR\s*(\d{1,3})", re.IGNORECASE
)
_RE_PRZEDSZKOLE_NR = re.compile(r"PRZEDSZKOL\w*(?:\s+\w+)*?\s+NR\s*(\d{1,3})", re.IGNORECASE)


def norm_placowka(v) -> tuple[str, str]:
    """Rozpoznaje typ placówki i buduje krótką, porównywalną nazwę.

    Zwraca ``(typ, nazwa_krotka)``, gdzie ``typ`` należy do
    ``TYPY_PLACOWKI`` = ``("szkoła", "przedszkole", "instytucja kultury", "nieznany")``.

    Rozpoznawanie typu (kolejność ma znaczenie):
      * instytucja kultury — ``MDK``, ``MOK``, ``DOM KULTURY``,
        ``OŚRODEK/CENTRUM KULTURY``, ``BIBLIOTEKA``, ``MUZEUM``
      * przedszkole — ``PRZEDSZKOLE``, ``PP`` (prywatne), ``PM`` (miejskie)
        — skróty według legendy z pliku klienta
      * szkoła — ``SP``, ``MSP``, ``ZSP``, ``ZPO``, ``ZS``,
        ``SZKOŁA PODSTAWOWA``, ``SZKOŁA``, ``LICEUM``
      * ``ZSP`` (zespół szkolno-przedszkolny) jest traktowany jako **szkoła**
        — klient prowadzi w nim DT dla klas 1-4

    Nazwa krótka:
      * z kodu i numeru: ``"sp1"`` -> ``"SP 1"``, ``"MSP7"`` -> ``"MSP 7"``,
        ``"Sp 21"`` -> ``"SP 21"``, ``"SP17"`` -> ``"SP 17"``
      * z pełnej nazwy RSPO:
        ``"SZKOŁA PODSTAWOWA NR 24 IM. POWSTAŃCÓW ŚLĄSKICH"`` -> ``"SP 24"``,
        ``"PRZEDSZKOLE MIEJSKIE NR 5"`` -> ``"PM 5"``
      * gdy nie ma numeru, zwracana jest nazwa oryginalna ze zwiniętymi
        spacjami (``"Książenice"``, ``"SZKOŁA PODSTAWOWA DLA DOROSŁYCH"``)

    >>> norm_placowka("MSP 1")
    ('szkoła', 'MSP 1')
    >>> norm_placowka("sp1")
    ('szkoła', 'SP 1')
    >>> norm_placowka("SZKOŁA PODSTAWOWA NR 24 IM. POWSTAŃCÓW ŚLĄSKICH")
    ('szkoła', 'SP 24')
    >>> norm_placowka("PM20")
    ('przedszkole', 'PM 20')
    >>> norm_placowka("MDK Knurów")[0]
    'instytucja kultury'
    >>> norm_placowka("")
    ('nieznany', '')
    """
    s = _txt(v)
    if not s:
        return "nieznany", ""

    up = s.upper()
    m_kod = _RE_KOD_NUMER.search(s)
    kod = m_kod.group(1).upper() if m_kod else None
    if kod is None:
        m_sam = _RE_KOD_SAM.search(s)
        kod = m_sam.group(1).upper() if m_sam else None

    # --- typ ---
    if _RE_KULTURA.search(s):
        typ = "instytucja kultury"
    elif kod in _KODY_SZKOLA or _RE_SZKOLA_SLOWO.search(s):
        # ZSP / zespół szkolno-przedszkolny -> szkoła (świadoma decyzja)
        typ = "szkoła"
    elif kod in _KODY_PRZEDSZKOLE or _RE_PRZEDSZKOLE.search(s):
        typ = "przedszkole"
    else:
        typ = "nieznany"

    # --- nazwa krótka ---
    if m_kod:
        nazwa = f"{kod} {int(m_kod.group(2))}"
    elif typ == "szkoła":
        m = _RE_SP_NR.search(up)
        nazwa = f"SP {int(m.group(1))}" if m else s
    elif typ == "przedszkole":
        m = _RE_PRZEDSZKOLE_NR.search(up)
        nazwa = f"PM {int(m.group(1))}" if m else s
    else:
        nazwa = s

    return typ, nazwa


if __name__ == "__main__":  # pragma: no cover
    import doctest

    print(doctest.testmod())
