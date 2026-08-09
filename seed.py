# -*- coding: utf-8 -*-
"""
Wypełnienie słowników i aliasów wartościami WZIĘTYMI Z ARKUSZA KLIENTA.

Zasada: nic nie wymyślamy. Listy poniżej to dokładnie te, które klient ma w walidacjach
w `PH Nowy`, scalone do jednej kanonicznej wersji tam, gdzie miał kilka rozjechanych.
Aliasy odwzorowują jego realne literówki i warianty zapisu — dzięki nim import z jego
pliku nie wymaga ręcznego czyszczenia, a „02. Olaszewska" i „02. Olszewska" to jedna osoba.
"""
from db import (get_conn, init_db, slownik_values, SLOWNIK_KLUCZE, kolor_z_nazwy)

# ---------------------------------------------------------------- słowniki

HANDLOWCY = [
    "01. Sacawa", "02. Olszewska", "03. Małolepsza", "04. Chytry", "05. Młynarczyk",
]

# Lista 40-pozycyjna z kolumny Y (Trener cykli) — pełna, po usunięciu pustych „31.".„40."
# scalona z 24-pozycyjną z kolumny O (Prowadzący DT).
TRENERZY = [
    "01. Małolepsza", "02. Olszewska", "03. Majewska", "04. Zemela", "05. Polakowska",
    "06. Jankowska", "07. Krzysztofik", "08. Brzozowska", "09. Bochniarz", "10. Łukaszek",
    "11. Białas (Pszczyna)", "12. Jasińska Nina", "13. Cebula", "14. Swoboda",
    "15. Gawron", "16. Król", "17. Paziewski", "18. Bitner", "19. Leśniak",
    "20. Sacawa", "21. Płaszczymąka", "22. Kopczyński", "23. Bednarek", "24. Palus",
    "25. Adamczyk", "26. Miękina", "27. Bąk-Kopaniarz", "28. Musiał", "29. Cichoń",
    "30. Jeziorczak", "31. Młynarczyk Adam", "32. Pustelnik", "33. Starzomska",
    "34. Wesołowska", "35. Łaczak",
    # osoby, które REALNIE prowadziły zajęcia w zeszłym roku, a wypadły z jego listy
    # (w `PH Nowy` na ich miejscach są puste pozycje „31."–„40." i „Trener 1–5")
    "36. Sacawa Kasia", "37. Gajkiewicz", "38. Tatoj", "39. Kocoń", "40. Biesyga",
]

# Kolory trenerów ODTWORZONE Z ICH PLIKU (zeszłoroczne plansze STARTY, 3942 karty —
# mapa kolor→trener z udziałem ≥90%). Bierzemy dominujący odcień na osobę: w arkuszu
# jedna osoba miała do 6 różnych odcieni, bo kolory dobierano „na oko" co miesiąc.
# Tu kolor jest DANĄ w słowniku — zmiana w jednym miejscu przemalowuje całą planszę.
TRENER_KOLORY = {
    "02. Olszewska": "#ff9900",          # 348 kart
    "22. Kopczyński": "#6d9eeb",         # 270
    "14. Swoboda": "#ff1361",            # 229
    "17. Paziewski": "#ea9999",          # 223
    "04. Zemela": "#9900ff",             # 216
    "16. Król": "#22b06a",               # 168 (oryginał #2BFF97 przyciemniony)
    "09. Bochniarz": "#c9a800",          # 127 (oryginał #FFFF00 przyciemniony)
    "11. Białas (Pszczyna)": "#8f7fd6",  # 125 (oryginał #DDD0FF przyciemniony)
    "21. Płaszczymąka": "#8e6223",       # 120
    "20. Sacawa": "#351c75",             # 81
    "08. Brzozowska": "#741b47",         # 71
    "32. Pustelnik": "#777777",          # 64
    "05. Polakowska": "#f1c232",         # 62
    "06. Jankowska": "#45818e",          # 52
    "24. Palus": "#d99a6c",              # 52 (oryginał #F9CB9C przyciemniony)
    "01. Małolepsza": "#ff00ff",         # 48
    "18. Bitner": "#666666",             # 46
    "03. Majewska": "#7cae68",           # 42 (oryginał #B6D7A8 przyciemniony)
    "33. Starzomska": "#7fa8d0",         # 40 (oryginał #CFE2F3 przyciemniony)
    "34. Wesołowska": "#a61c00",         # 32
    "15. Gawron": "#d98cbe",             # 22 (oryginał #FFDBF2 przyciemniony)
    "10. Łukaszek": "#a43aaa",           # 20
    "07. Krzysztofik": "#4a9fc4",        # 16 (oryginał #B0E7FF przyciemniony)
    "35. Łaczak": "#0f8a5f",             # theme9
    "13. Cebula": "#3fae24",             # 8 (oryginał #54CD2F przyciemniony)
    "19. Leśniak": "#8a8a8a",
    "23. Bednarek": "#a08247",           # #C7B270 — kolor współdzielony w arkuszu
    "26. Miękina": "#c76a00",
    "31. Młynarczyk Adam": "#2d6fd1",
}

# Kolory, które w ich arkuszu NIE oznaczały trenera, tylko stan. Trzymamy jako
# osobne znaczenie, żeby nie „przypisać" ich komuś przez pomyłkę przy imporcie.
KOLORY_STANOW = {
    "FFFF0000": "problem / trener do wymiany",
    "FF434343": "brak obsady — szukamy trenera",
    "FFFFFFFF": "nieprzypisane",
}

# Scalona lista miejscowości. Klient miał trzy warianty; bierzemy numerację z BAZY
# (najpełniejsza), warianty „powiat" i literówki idą do aliasów.
MIASTA = [
    "01. Orzesze", "02. Mikołów", "03. Łaziska Górne", "04. Tychy", "05. Knurów",
    "06. Rybnik", "07. Żory", "08. Katowice", "09. Pszczyna", "10. Piekary Śląskie",
    "11. Siemianowice Śląskie", "12. Świętochłowice", "13. Sosnowiec",
    "14. Dąbrowa Górnicza", "15. Będzin", "16. Chorzów", "17. Jaworzno",
    "18. Zabrze", "19. Ruda Śląska", "20. Ornontowice", "21. Wyry", "22. Gostyń",
    "23. Strzyżowice",
    # dołożone: realnie występowały w zeszłorocznym pliku, ale wypadły z jego nowych list
    "24. Czeladź", "25. Psary", "26. Miedźna", "27. Wola", "28. Frydek", "29. Góra",
    "30. Mysłowice", "31. Gliwice", "32. Bytom", "33. Tarnowskie Góry",
]

# Ich typ placówki był zaszyty w prefiksie numeru (SP / MSP / ZSP / PM / PP / KSP),
# a rozliczenia przedszkoli liczyły podział „miejskie vs prywatne" listą adresów
# komórek. Jako pole załatwia to jedno filtrowanie.
TYP_PLACOWKI = [
    "01. Szkoła podstawowa",
    "02. Przedszkole miejskie (PM)",
    "03. Przedszkole prywatne (PP)",
    "04. Zespół szkolno-przedszkolny (ZSP)",
    "05. Instytucja kultury",
    "06. Inna (uczelnia, firma)",
]

STATUS_SZKOLY = ["01. Nowa szkoła", "02. Kontynuacja"]

# Do listy klienta dodany „02b. DT w trakcie umawiania" — wprost z notatek ze spotkania
# 24.07 („Arkusze po statusie: DT w trakcie umawiania"). Numeracja 02b, żeby nie przesuwać
# jego numerów, do których jest przywiązany.
STATUS_REALIZACJI = [
    "00. Nieprzydzielony",
    "00b. Rezerwacja",                       # miękka blokada leada, 5 wariantów zapisu w ich pliku
    "01. Próba kontaktu (Brak konkretów)",
    "02. Próba kontaktu (czekam na termin)",
    "02b. DT w trakcie umawiania",           # wprost z notatek ze spotkania 24.07
    "03. DT umówione",
    "03b. Grupa cykliczna otwarta",           # realny kolejny etap lejka w ich pliku
    "03c. Grupa się nie otworzyła",
    "04. BRAK KONTAKTU ZE SZKOŁĄ",
    # Dwa statusy z „PH PRÓBA Nowy dla handlowców.xlsx" (08.08.2026): szkoła
    # odmówiła DT (4 wystąpienia) i „odpuszczamy ten kontakt" (2). Prefiks 04.
    # celowo ten sam co „brak kontaktu" — dla aplikacji to wszystko jest
    # odpadnięcie (lead wypada z listy roboczej i nie wraca automatem), ale
    # POWÓD zostaje rozróżnialny, bo „nie chcą" to nie to samo co „nie odbierają".
    "04. Brak zgody na DT",
    "04. Odpuścić",
]

DT = ["01. Tak", "02. Do ustalenia"]
TAK_NIE = ["01. Tak", "02. Nie"]
MAIL_DT = ["01. Podsumowanie DT", "02. Propozycja DT"]
DNI_TYG = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"]

# W ich pliku żyje SZEŚĆ rodzajów zdarzeń, każdy w osobnej zakładce.
# Jedna tabela `eventy` z typem zastępuje je wszystkie.
#   DT          — dzień technologiczny (pokazowy) w szkole
#   START       — pierwsze zajęcia nowej grupy cyklicznej (inauguracja), termin jednorazowy
#   CYKLICZNE   — zajęcia powtarzalne (reguła: dzień tygodnia + godziny + co ile tygodni)
TYP_EVENTU = ["DT", "START", "CYKLICZNE", "JEDNORAZÓWKA", "FESTYN", "VR"]

SPRZET = ["01. Sala komputerowa", "02. Nasze laptopy", "03. Chromebooki"]

SLOWNIKI = {
    "handlowiec": HANDLOWCY,
    "trener": TRENERZY,
    "miasto": MIASTA,
    "typ_placowki": TYP_PLACOWKI,
    "status_szkoly": STATUS_SZKOLY,
    "status_realizacji": STATUS_REALIZACJI,
    "dt": DT,
    "tak_nie": TAK_NIE,
    "mail_dt": MAIL_DT,
    "dzien_tyg": DNI_TYG,
    "typ_eventu": TYP_EVENTU,
    "sprzet": SPRZET,
}

# ---------------------------------------------------------------- aliasy
# Lewa strona = to, co realnie występuje w plikach klienta. Prawa = wartość kanoniczna.

ALIASY = {
    "handlowiec": {
        "02. Olaszewska": "02. Olszewska",      # literówka w Sacawa!A20:A200 i Olszewska!A29:A340
        "Bitner": "05. Młynarczyk",             # w BAZA!A jako 5. handlowiec — do potwierdzenia
        "Sacawa": "01. Sacawa",
        "Olszewska": "02. Olszewska",
        "Małolepsza": "03. Małolepsza",
        "Chytry": "04. Chytry",
        "Młynarczyk": "05. Młynarczyk",
        # w pliku z 08.08 jeden lead podpisany samym imieniem — w firmie jest
        # jedna Julia (Młynarczyk, zakładka „Młynarczyk" w tym samym pliku)
        "Julia": "05. Młynarczyk",
    },
    "trener": {
        # literówki z arkusza
        "11. Białass (Pszczyna)": "11. Białas (Pszczyna)",
        "22. Trene 3": "31. Młynarczyk Adam",   # placeholdery „Trener N" z kolumny O
        "23. Trenner 5": "31. Młynarczyk Adam",
        "18. Młynarczyk Adam": "31. Młynarczyk Adam",
        "20. Trener 1": "32. Pustelnik",
        "21. Trener 2": "33. Starzomska",
        "21. Trener 3": "34. Wesołowska",
        "23. Trener 4": "35. Łaczak",
        "24. Trener 5": "03. Majewska",
        # własna lista Olszewskiej (Olszewska!Y4:Y340)
        "01. Olszewska Zuza": "02. Olszewska",
        "02. Sacawa Dominika": "20. Sacawa",
        "03. Zemela Paulina": "04. Zemela",
        # zapisy IMIĘ NAZWISKO z planszy STARTY (49 wariantów → osoby)
        "WERONIKA MAŁOLEPSZA": "01. Małolepsza",
        "weronika małolepsza": "01. Małolepsza",
        # „MAJKA"/„MAJA" to Maja Majewska (legenda kolorów w ich pliku: A2 = 'MAJA',
        # kolor #B6D7A8 = Majewska Maja) — NIE Małolepsza
        "MAJKA": "03. Majewska",
        "MAJA": "03. Majewska",
        "Majewska Maja": "03. Majewska",
        "Małolesza": "01. Małolepsza",
        "Miekina": "26. Miękina",
        "ZUZANNA OLSZEWSKA": "02. Olszewska",
        "ZUZIA OLSZEWSKA": "02. Olszewska",
        "ZUZANNA": "02. Olszewska",
        "ZUZA": "02. Olszewska",
        "PAULINA ZEMELA": "04. Zemela",
        "Paulina Zemela": "04. Zemela",
        "KLAUDIA POLAKOWSKA": "05. Polakowska",
        "ELA JANKOWSKA": "06. Jankowska",
        "KAROLINA BRZOZOWSKA": "08. Brzozowska",
        "MARTYNA BOCHNIARZ": "09. Bochniarz",
        "Martyna Bochniarz": "09. Bochniarz",
        "Martyna bochniarz": "09. Bochniarz",
        "martyna bochniarz": "09. Bochniarz",
        "LIWIA ŁUKASZEK": "10. Łukaszek",
        "NOEMI BIAŁAS": "11. Białas (Pszczyna)",
        "noemi białas": "11. Białas (Pszczyna)",
        "NINA JASIŃSKA": "12. Jasińska Nina",
        "ANIELA CEBULA": "13. Cebula",
        "ANIEL CEBULA": "13. Cebula",
        "MONIKA SWOBODA": "14. Swoboda",
        "GAWRON KORNELIA": "15. Gawron",
        "KINGA KRÓL": "16. Król",
        "kinga": "16. Król",
        "DAMIAN PAZIEWSKI": "17. Paziewski",
        "Damian Paziewski": "17. Paziewski",
        "AGATA BITTNER": "18. Bitner",
        "MATEUSZ LEŚNIAK": "19. Leśniak",
        "DOMINIKA SACAWA": "20. Sacawa",
        "MICHAŁ PŁASZCZYMĄKA": "21. Płaszczymąka",
        "ROBERT KOPCZYŃSKI": "22. Kopczyński",
        "ROBERT": "22. Kopczyński",
        "PATRYK BEDNAREK": "23. Bednarek",
        "PATRYK PALUS": "24. Palus",
        "PATRYK PALSU": "24. Palus",
        "natalia miękina": "26. Miękina",
        "MATEUSZ PUSTELNIK": "32. Pustelnik",
        "MATI PUSTELNIK": "32. Pustelnik",
        "mateusz pustelnik": "32. Pustelnik",
        "NATALIA STARZOMSKA": "33. Starzomska",
        "NATALIA STARZOSMKA": "33. Starzomska",
        "JULIA WESOŁOWSKA": "34. Wesołowska",
        "JULA WESOŁOWSKA": "34. Wesołowska",
        "JULA WESOŁOWKSA": "34. Wesołowska",
        "EWA ŁACZAK": "35. Łaczak",
        # zapisy „po imieniu" — tak podpisywano kolumnę DRUKARZ w planszy STARTY
        "DOMINIKA": "20. Sacawa",
        "MONIKA": "14. Swoboda",
        "ZUZIA": "02. Olszewska",
        "damian": "17. Paziewski",
        "DAMIAN": "17. Paziewski",
        "MICHAŁ": "21. Płaszczymąka",
        "PAULINA Z": "04. Zemela",
        "PAULINA": "04. Zemela",
        "NOEMI": "11. Białas (Pszczyna)",
        "MARTYNA": "09. Bochniarz",
        "KAROLINA": "08. Brzozowska",
        "LIWIA": "10. Łukaszek",
        "NINA": "12. Jasińska Nina",
        "ELA": "06. Jankowska",
        "AGATA": "18. Bitner",
        "KLAUDIA": "05. Polakowska",
        "JULA": "34. Wesołowska",
        "JULIA": "34. Wesołowska",
        # „NATALIA M" = Miękina (druga Natalia to Starzomska, zapisywana pełnym nazwiskiem)
        "NATALIA M": "26. Miękina",
        "NATALIA": "33. Starzomska",
        "SYLWIA ADAMCZYK": "25. Adamczyk",
        "damian paziewski": "17. Paziewski",
        "SARA": "27. Bąk-Kopaniarz",
        "BĄK-KOPANIARZ SARA": "27. Bąk-Kopaniarz",
        "KASIA": "36. Sacawa Kasia",
        "Kasia Sacawa": "36. Sacawa Kasia",
        "SACAWA KASIA": "36. Sacawa Kasia",
        "JULA GAJKIEWICZ": "37. Gajkiewicz",
        "GAJKIEWICZ JULIA": "37. Gajkiewicz",
        "KRYSTIAN TATOJ": "38. Tatoj",
        "TATOJ KRYSTIAN": "38. Tatoj",
        "PAULINA KOCOŃ": "39. Kocoń",
        "KOCOŃ PAULINA": "39. Kocoń",
        "JACEK BIESYGA": "40. Biesyga",
        "BIESYGA JACEK": "40. Biesyga",
        "MARTA KRZYSZTOFIK": "07. Krzysztofik",
        "PAULA ZEMELA": "04. Zemela",
        "kornelia gawron (1)": "15. Gawron",
        # „MATEUSZ L" = Leśniak (drugi Mateusz to Pustelnik, zapisywany pełnym nazwiskiem)
        "MATEUSZ L": "19. Leśniak",
        "KUBA CICHOŃ": "29. Cichoń",
        # NIE mapujemy świadomie (do potwierdzenia z klientem — patrz docs/07_PYTANIA):
        #   'MATEUSZ' / 'METEUSZ' — dwóch Mateuszów (Leśniak, Pustelnik)
        #   'Natalia Jasińska'    — nazwisko wskazuje Jasińską, ale ona ma na imię Nina
    },
    "miasto": {
        "09. Pszczyna powiat": "09. Pszczyna",
        "15. Będzin powiat": "15. Będzin",
        "17. Dąbrowa Górnicza": "14. Dąbrowa Górnicza",   # dublet w tej samej liście
        "18. Jaworzno": "17. Jaworzno",
        "19. Zabrze": "18. Zabrze",
        "20. Ruda Śląska": "19. Ruda Śląska",
        "19. Chorzow": "16. Chorzów",
        "08. Katowice Południe": "08. Katowice",
        "10. Katowice": "08. Katowice",
        "11. Zabrze": "18. Zabrze",
        "12. Ruda Śląska": "19. Ruda Śląska",
        "13. Świętochłowice": "12. Świętochłowice",
        "14. Siemianowice Śląskie": "11. Siemianowice Śląskie",
        "15. Piekary Śląskie": "10. Piekary Śląskie",
        "16. Dąbrowa Górnicza": "14. Dąbrowa Górnicza",
        "17. Sosnowiec": "13. Sosnowiec",
        "21. Strzyzowice": "23. Strzyżowice",
        "Dabrowa Gornicza": "14. Dąbrowa Górnicza",
        "Dabrowa Górnicza": "14. Dąbrowa Górnicza",
        "Czeladz": "24. Czeladź",
        "Myslowice": "30. Mysłowice",
    },
    "typ_placowki": {
        "SP": "01. Szkoła podstawowa",
        "MSP": "01. Szkoła podstawowa",
        "KSP": "01. Szkoła podstawowa",
        "szkoła": "01. Szkoła podstawowa",
        "PM": "02. Przedszkole miejskie (PM)",
        "PP": "03. Przedszkole prywatne (PP)",
        "przedszkole": "02. Przedszkole miejskie (PM)",
        "ZSP": "04. Zespół szkolno-przedszkolny (ZSP)",
        "ZPO": "04. Zespół szkolno-przedszkolny (ZSP)",
        "instytucja kultury": "05. Instytucja kultury",
        "MDK": "05. Instytucja kultury",
        "nieznany": "06. Inna (uczelnia, firma)",
    },
    "sprzet": {
        "Sala komputerowa": "01. Sala komputerowa",
        "Nasze laptopy": "02. Nasze laptopy",
        "sala komputerowa": "01. Sala komputerowa",
        "chromebooki": "03. Chromebooki",
    },
    "status_realizacji": {
        "DT umówione": "03. DT umówione",
        "BRAK KONTAKTU ZE SZKOŁĄ": "04. BRAK KONTAKTU ZE SZKOŁĄ",
        "DT w trakcie umawiania": "02b. DT w trakcie umawiania",
        # „rezerwacja" — 5 wariantów zapisu w 4 zakładkach ich pliku
        "Rezerwacja Werka": "00b. Rezerwacja",
        "Rez Wera": "00b. Rezerwacja",
        "Rez Werka": "00b. Rezerwacja",
        "zuza rezerwacja": "00b. Rezerwacja",
        "zuza - rezerwacja": "00b. Rezerwacja",
        "Zuza - rezerwacja": "00b. Rezerwacja",
        "REZERWACJA WERKA": "00b. Rezerwacja",
        "BYŁO DT ALE NIE MA ZAJĘĆ - NIE OTWORZYŁA SIĘ GRUPA": "03c. Grupa się nie otworzyła",
        "GOTOWE :) - jest umowa, są zajęcia": "03b. Grupa cykliczna otwarta",
        # wersalikami w pliku z 08.08 — u nas wartość kanoniczna ma normalną pisownię
        "BRAK ZGODY NA DT": "04. Brak zgody na DT",
        "ODPUŚCIĆ": "04. Odpuścić",
    },
    "typ_eventu": {
        "cykliczne": "CYKLICZNE",
        "start": "START",
        "dt": "DT",
        "jednorazówka": "JEDNORAZÓWKA",
        "festyn": "FESTYN",
        "vr": "VR",
    },
    "dzien_tyg": {
        "Poniedziałek": "poniedziałek", "Wtorek": "wtorek", "Środa": "środa",
        "Czwartek": "czwartek", "Piątek": "piątek", "Sobota": "sobota",
        "PONIEDZIAŁEK": "poniedziałek", "WTOREK": "wtorek", "ŚRODA": "środa",
        "CZWARTEK": "czwartek", "PIĄTEK": "piątek",
    },
}


def wypelnij_slowniki(conn):
    """Idempotentne — można wołać przy każdym starcie."""
    n = 0
    for rodzaj, wartosci in SLOWNIKI.items():
        for i, w in enumerate(wartosci, 1):
            kolor = TRENER_KOLORY.get(w) if rodzaj == "trener" else None
            if rodzaj == "trener" and not kolor:
                kolor = kolor_z_nazwy(w)
            cur = conn.execute(
                "INSERT OR IGNORE INTO slowniki (rodzaj, wartosc, kolor, sort_order) "
                "VALUES (?,?,?,?)", (rodzaj, w, kolor, i))
            n += cur.rowcount
    conn.commit()
    return n


def wypelnij_aliasy(conn):
    n = 0
    for rodzaj, mapa in ALIASY.items():
        for alias, wartosc in mapa.items():
            cur = conn.execute(
                "INSERT OR IGNORE INTO aliasy (rodzaj, alias, wartosc) VALUES (?,?,?)",
                (rodzaj, alias, wartosc))
            n += cur.rowcount
    conn.commit()
    return n


def sprawdz_spojnosc(conn):
    """
    Kontrola, że każdy alias wskazuje na ISTNIEJĄCĄ wartość słownika.
    Bez tego cichy literówka w seedzie zamieniłaby jeden bałagan na drugi.
    Zwraca listę problemów (pusta = OK).
    """
    problemy = []
    for rodzaj in ALIASY:
        dozwolone = set(slownik_values(conn, rodzaj))
        for alias, wartosc in ALIASY[rodzaj].items():
            if wartosc not in dozwolone:
                problemy.append("alias %s:%r -> %r nie ma w słowniku" % (rodzaj, alias, wartosc))
            if alias in dozwolone:
                problemy.append("alias %s:%r jest jednocześnie wartością kanoniczną" % (rodzaj, alias))
    for rodzaj in SLOWNIKI:
        if rodzaj not in SLOWNIK_KLUCZE:
            problemy.append("słownik %r nie jest zarejestrowany w SLOWNIK_RODZAJE" % rodzaj)
    return problemy


def bootstrap():
    """Wołane przy starcie aplikacji: schemat + słowniki + aliasy."""
    conn = get_conn()
    init_db(conn)
    ns = wypelnij_slowniki(conn)
    na = wypelnij_aliasy(conn)
    problemy = sprawdz_spojnosc(conn)
    conn.close()
    return {"slowniki": ns, "aliasy": na, "problemy": problemy}


if __name__ == "__main__":
    info = bootstrap()
    print("dodane pozycje słowników:", info["slowniki"])
    print("dodane aliasy:", info["aliasy"])
    if info["problemy"]:
        print("PROBLEMY SPÓJNOŚCI:")
        for p in info["problemy"]:
            print("  -", p)
    else:
        print("spójność aliasów: OK")
