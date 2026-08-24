# -*- coding: utf-8 -*-
"""
Dołożenie brakujących placówek z lustra rejestru do bazy roboczej — etap M7
projektu `docs/poprawka 23.08.2026/PROJEKT_BAZY_RSPO.md`.

CO TO ROZWIĄZUJE
Baza handlowców ma 545 rekordów: 539 szkół podstawowych i 6 pozycji „Inna".
PRZEDSZKOLI NIE MA ANI JEDNEGO — a firma prowadzi w nich zajęcia (typ wpisu
`CYKLICZNE-PRZEDSZKOLE` istnieje od sierpnia). W rejestrze, w obszarach
działania firmy, siedzi ich 710 plus 23 punkty przedszkolne. Ten moduł
przenosi je do bazy roboczej.

DLACZEGO PRZEDSZKOLA MOŻNA DOŁOŻYĆ PRZED NADANIEM NUMERÓW ISTNIEJĄCYM (M3)
Bo nie mają z czym się zdublować: w bazie nie ma ani jednego przedszkola.
Cały problem dubli — i cała zależność od decyzji koordynatorki — dotyczy
szkół podstawowych, gdzie rekord z rejestru może być drugą kopią szkoły,
którą handlowiec już obrabia. Stąd podział na grupy typów: przedszkola idą
teraz, podstawówki po M3.

GEOGRAFIA NOWEGO REKORDU: WPROST Z REJESTRU
Powiat, gmina i miejscowość idą do bazy takie, jakie są w rejestrze — bo od
etapu M6 osią filtrowania jest POWIAT, a miejscowość przestała być pozycją
słownika.

Do 24.08 było inaczej i warto wiedzieć dlaczego, żeby nie wrócić do tamtego
rozwiązania: dopóki filtry chodziły po słowniku `miasto` z prefiksami
(`08. Katowice`), nowy rekord z czystym „Katowice" nie wpadłby w żaden filtr,
a jego karty NIE DAŁOBY SIĘ ZAPISAĆ — walidacja odbija wartości spoza słownika
(ta sama pułapka, co brakujący `CYKLICZNE-PRZEDSZKOLE` w słowniku produkcji).
Dlatego wsie spoza słownika lądowały wtedy w workach powiatowych. Po
przełączeniu na powiat ta sama zasada zaczęła szkodzić: każde dołożenie
wymagało PÓŹNIEJSZEGO przebiegu czyszczącego, a zapomnienie o nim na produkcji
zapisałoby Siewierz jako „15. Będzin".
"""
import re

import db
import rejestr_rspo

# Grupy typów rejestru. „Zespół szkół i placówek oświatowych" NIE wchodzi do
# żadnej grupy: rekord roboczy powstaje dla jednostki SKŁADOWEJ (szkoła,
# przedszkole), bo to ona ma typ, liczbę dzieci i własny proces sprzedażowy.
# Jeden rekord „ZSP nr 23" nie pomieściłby DT w podstawówce i osobnych cykli
# w dwóch przedszkolach tego samego zespołu.
GRUPY_TYPOW = {
    "przedszkola": ("Przedszkole", "Punkt przedszkolny",
                    "Zespół wychowania przedszkolnego"),
    "szkoly": ("Szkoła podstawowa",),
    # Placówki pozaszkolne prowadzące zajęcia dla dzieci — dom kultury, ognisko,
    # ośrodek. Dla handlowca to ten sam produkt co w szkole, tylko inny
    # rozmówca; w rejestrze mają osobne typy, bo tak dzieli je prawo oświatowe.
    "pozaszkolne": ("Młodzieżowy dom kultury",
                    "Ognisko pracy pozaszkolnej",
                    "Placówki artystyczne (ognisko artystyczne)",
                    "Międzyszkolny ośrodek sportowy",
                    "Młodzieżowy Ośrodek Socjoterapii ze szkołami"),
    # ZESPOŁY STOJĄ OSOBNO I ŚWIADOMIE NIE WCHODZĄ DO „wszystkie".
    # Rejestr rozbija zespół na wiersze: sam zespół + jego składowe (szkoła,
    # przedszkola). Rekord roboczy robimy dla SKŁADOWEJ, bo to ona ma typ,
    # liczbę dzieci i własny proces — jeden wiersz „ZSP nr 23" nie pomieściłby
    # DT w podstawówce i osobnych cykli w dwóch przedszkolach tego zespołu.
    # Dołożenie zespołów postawiłoby je OBOK ich własnych składowych, czyli
    # trzy rekordy pod jednym adresem. Dlatego trzeba o nie poprosić wprost.
    "zespoly": ("Zespół szkół i placówek oświatowych",),
}
GRUPY_TYPOW["wszystkie"] = (GRUPY_TYPOW["przedszkola"] + GRUPY_TYPOW["szkoly"]
                            + GRUPY_TYPOW["pozaszkolne"])

# Rejestr → słownik `typ_placowki`. Przedszkole publiczne i prywatne to dla
# handlowca dwie różne rozmowy (inny decydent, inne pieniądze), dlatego
# rozstrzyga kolumna „Publiczność status", a nie sam typ.
TYP_SP = "01. Szkoła podstawowa"
TYP_PRZEDSZKOLE_PUB = "02. Przedszkole miejskie (PM)"
TYP_PRZEDSZKOLE_NIEPUB = "03. Przedszkole prywatne (PP)"
TYP_ZESPOL = "04. Zespół szkolno-przedszkolny (ZSP)"
# Dom kultury, ognisko i ośrodek trafiają do pozycji, którą klient sam założył
# na takie miejsca. NIE dokładamy nowych pozycji słownika: dokładny typ
# z rejestru siedzi w lustrze pod tym samym numerem RSPO i widać go na karcie,
# a wartość słownika raz wpuszczona na produkcję zostaje tam na zawsze.
# Gdyby Kasia chciała je rozróżniać na filtrach — to jedna linia w słowniku.
TYP_POZASZKOLNA = "05. Instytucja kultury"

MAPA_TYPOW = {
    "Szkoła podstawowa": TYP_SP,
    "Zespół szkół i placówek oświatowych": TYP_ZESPOL,
    "Młodzieżowy dom kultury": TYP_POZASZKOLNA,
    "Ognisko pracy pozaszkolnej": TYP_POZASZKOLNA,
    "Placówki artystyczne (ognisko artystyczne)": TYP_POZASZKOLNA,
    "Międzyszkolny ośrodek sportowy": TYP_POZASZKOLNA,
    "Młodzieżowy Ośrodek Socjoterapii ze szkołami": TYP_POZASZKOLNA,
    # Przedszkolne rozstrzyga publiczność — patrz `typ_roboczy`.
    "Przedszkole": None,
    "Punkt przedszkolny": None,
    "Zespół wychowania przedszkolnego": None,
}

STATUS_NOWEGO = "00. Nieprzydzielony"
STATUS_SZKOLY_NOWA = "01. Nowa szkoła"
ZRODLO = "rspo"
LOG_CO = "migracja-rspo: dołożenie"

# Słowa, które w nazwie placówki nie identyfikują NICZEGO — każde przedszkole
# w Polsce ma w nazwie „przedszkole". Do wykrywania „czy to przypadkiem nie ta
# sama placówka, którą już mamy pod inną nazwą".
SLOWA_PUSTE = {
    "szkola", "podstawowa", "przedszkole", "punkt", "przedszkolny",
    "publiczne", "publiczna", "niepubliczne", "niepubliczna", "miejskie",
    "samorzadowe", "zespol", "szkolno", "placowek", "oswiatowych",
    "integracyjne", "sportowa", "specjalna", "imienia",
}


def _fold(s):
    """Do porównań: bez ogonków, bez wielkości liter, bez interpunkcji."""
    s = (s or "").lower()
    s = s.translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _slowa_znaczace(nazwa, miejscowosc=None):
    """
    Słowa, które NAPRAWDĘ identyfikują placówkę. Poza listą słów pustych
    odpada też nazwa miejscowości w dowolnej odmianie: „SZKOŁA PODSTAWOWA
    NR 16 W KATOWICACH" niesie jako jedyne „znaczące" słowo `katowicach`,
    które pasuje do połowy rejestru. Porównujemy wspólny początek (7 znaków),
    bo odmiana zmienia końcówkę, nie rdzeń.
    """
    rdzen = _fold(_bez_prefiksu(miejscowosc))[:7]
    out = set()
    for w in _fold(nazwa).split():
        if len(w) < 4 or w in SLOWA_PUSTE:
            continue
        if rdzen and len(rdzen) >= 5 and w.startswith(rdzen):
            continue
        out.add(w)
    return out


def _bez_prefiksu(wartosc):
    return re.sub(r"^\d+[a-z]?\.\s*", "", wartosc or "").strip()


# ---------------------------------------------------------------------------
# Warunki wstępne — sprawdzamy PRZED zapisem, nie w jego trakcie
# ---------------------------------------------------------------------------

def brakujace_pozycje_slownikow(conn, typy):
    """
    Wartości, które ten moduł wpisze, a których w słownikach TEGO profilu
    nie ma. Słownik to dane osobne dla każdej bazy — kod, który zna stałą,
    nie gwarantuje, że produkcja zna pozycję (lekcja z `CYKLICZNE-PRZEDSZKOLE`).
    Bez tego sprawdzenia dołożylibyśmy 733 rekordy, których kart nie da się
    zapisać — i wyszłoby to dopiero, gdy handlowiec spróbuje coś poprawić.
    """
    potrzebne = [("status_realizacji", STATUS_NOWEGO),
                 ("status_szkoly", STATUS_SZKOLY_NOWA)]
    if set(typy) & set(GRUPY_TYPOW["przedszkola"]):
        potrzebne += [("typ_placowki", TYP_PRZEDSZKOLE_PUB),
                      ("typ_placowki", TYP_PRZEDSZKOLE_NIEPUB)]
    for t in typy:
        docelowy = MAPA_TYPOW.get(t)
        if docelowy:
            potrzebne.append(("typ_placowki", docelowy))
    brak = []
    for rodzaj, wartosc in dict.fromkeys(potrzebne):
        jest = conn.execute(
            "SELECT 1 FROM slowniki WHERE rodzaj=? AND wartosc=?",
            (rodzaj, wartosc)).fetchone()
        if not jest:
            brak.append((rodzaj, wartosc))
    return brak


def typ_roboczy(rekord):
    stały = MAPA_TYPOW.get(rekord["typ"], None)
    if stały:
        return stały
    publiczna = (rekord["publicznosc"] or "").lower().startswith("publiczn")
    return TYP_PRZEDSZKOLE_PUB if publiczna else TYP_PRZEDSZKOLE_NIEPUB


def miejscowosc_robocza(rekord, mapa_miast=None):
    """
    (wartość do wpisania, skąd się wzięła). Wprost z rejestru — bo od etapu M6
    osią filtrowania jest POWIAT, a miejscowość przestała być pozycją słownika.

    Do 24.08 ta funkcja robiła coś innego: mapowała nazwę na wartość słownika
    (`Katowice` → `08. Katowice`), a wsie spoza słownika wrzucała do worka
    powiatowego. Miało to sens dokładnie tak długo, jak długo filtry chodziły
    po słowniku — inaczej nowy rekord nie wpadłby w żaden z nich. Po
    przełączeniu na powiat ta sama zasada zaczęła szkodzić: każde dołożenie
    wymagało PÓŹNIEJSZEGO przebiegu czyszczącego, a kto by o nim zapomniał na
    produkcji, dostałby Siewierz zapisany jako „15. Będzin".

    `mapa_miast` zostaje w sygnaturze i jest ignorowana — wołający nie muszą
    wiedzieć, że reguła się zmieniła.
    """
    nazwa = (rekord["miejscowosc"] or "").strip()
    if nazwa:
        return nazwa, "rejestr"
    return None, "rejestr nie podaje miejscowości"


# ---------------------------------------------------------------------------
# Kandydaci i podobieństwa
# ---------------------------------------------------------------------------

def kandydaci(conn, typy):
    """
    Wiersze lustra do dołożenia: w obszarach działania, w podanych typach,
    obecne w ostatnim wgraniu rejestru i BEZ rekordu roboczego o tym numerze.

    Odsianie po numerze RSPO to pierwsza z dwóch zapór przed dublem; druga
    siedzi w samej bazie (częściowy UNIQUE na `placowki.rspo`).
    """
    sql = """
        SELECT r.*, o.nazwa AS obszar
          FROM rspo_obszar ro
          JOIN rspo_rejestr r ON r.rspo = ro.rspo
          JOIN obszary_dzialania o ON o.id = ro.obszar_id
         WHERE r.typ IN (%s)
           AND r.nieobecna_od IS NULL
           AND NOT EXISTS (SELECT 1 FROM placowki p
                            WHERE p.rspo IS NOT NULL AND p.rspo <> ''
                              AND CAST(p.rspo AS INTEGER) = r.rspo)
         ORDER BY o.kolejnosc, r.miejscowosc, r.nazwa
    """ % ",".join("?" * len(typy))
    return [dict(w) for w in conn.execute(sql, tuple(typy))]


def podobne_istniejace(conn, grupa):
    """
    Rekordy robocze, z którymi kandydat MOŻE być tą samą placówką.

    Dwa zawężenia, oba wzięte z rozjechanego pierwszego podejścia (289 trafień
    zamiast kilku):

    1. Odpada wszystko, co ma numer RSPO — to już odsiało zapytanie o kandydatów.
    2. Odpadają rekordy typu z DRUGIEJ grupy. Baza to dziś 539 szkół
       podstawowych; „AACADEMY NIEPUBLICZNA SPECJALNA SZKOŁA PODSTAWOWA"
       i „AACADEMY NIEPUBLICZNE PRZEDSZKOLE SPECJALNE" to ten sam operator
       i DWIE RÓŻNE placówki — dokładnie ta druga jest tym, po co tu jesteśmy.
       Przy dokładaniu przedszkoli porównujemy się więc wyłącznie z rekordami,
       które przedszkolem być mogą (typ „Inna", pusty albo przedszkolny).
    """
    # Typy robocze, które ta grupa może wyprodukować — i tylko z nimi się
    # porównujemy. Rekordy o typie spoza tej listy (np. klienckie `04. Inna`)
    # zostają w porównaniu ZAWSZE, bo pod taką etykietą może siedzieć cokolwiek
    # — i faktycznie siedziało: „Zając Poziomka" okazała się przedszkolem.
    moje_typy = {TYP_PRZEDSZKOLE_PUB, TYP_PRZEDSZKOLE_NIEPUB} \
        if set(GRUPY_TYPOW["przedszkola"]) & set(GRUPY_TYPOW.get(grupa, ())) else set()
    for t in GRUPY_TYPOW.get(grupa, ()):
        if MAPA_TYPOW.get(t):
            moje_typy.add(MAPA_TYPOW[t])
    wszystkie_robocze = {TYP_SP, TYP_PRZEDSZKOLE_PUB, TYP_PRZEDSZKOLE_NIEPUB,
                         TYP_ZESPOL, TYP_POZASZKOLNA}
    wykluczone = sorted(wszystkie_robocze - moje_typy)
    sql = "SELECT id, nazwa, miejscowosc FROM placowki WHERE (rspo IS NULL OR rspo='')"
    if wykluczone:
        sql += " AND COALESCE(typ,'') NOT IN (%s)" % ",".join("?" * len(wykluczone))
    out = []
    for r in conn.execute(sql, tuple(wykluczone)):
        slowa = _slowa_znaczace(r["nazwa"], r["miejscowosc"])
        if slowa:
            out.append((r["id"], r["nazwa"], r["miejscowosc"], slowa))
    return out


def _kolizja(kandydat_nazwa, miejscowosc, istniejace):
    """
    Czy kandydat wygląda na placówkę, którą już mamy pod skrótem handlowca.
    Warunek celowo ostry: WSZYSTKIE znaczące słowa naszego rekordu muszą
    siedzieć w nazwie z rejestru, i to w tej samej miejscowości. „Zając
    Poziomka" złapie „Niepubliczne Przedszkole Zając Poziomka", ale dwa
    różne przedszkola miejskie w jednym mieście się nie sklejają.
    """
    slowa_kandydata = set(_fold(kandydat_nazwa).split())
    for pid, nazwa, miejsc, slowa in istniejace:
        if miejsc != miejscowosc:
            continue
        if slowa <= slowa_kandydata:
            return {"id": pid, "nazwa": nazwa}
    return None


# ---------------------------------------------------------------------------
# Podgląd i zapis
# ---------------------------------------------------------------------------

def przygotuj(conn, grupa="przedszkola"):
    """
    Wspólne jądro podglądu i zapisu — jedna decyzja per kandydat, policzona
    raz. Podgląd, który liczyłby inaczej niż zapis, byłby gorszy niż jego brak.
    """
    typy = GRUPY_TYPOW[grupa]
    braki = brakujace_pozycje_slownikow(conn, typy)
    istniejace = podobne_istniejace(conn, grupa)

    do_zapisu, odlozone, kolizje = [], [], []
    for k in kandydaci(conn, typy):
        miejsc, skad = miejscowosc_robocza(k)
        if miejsc is None:
            odlozone.append({"rspo": k["rspo"], "nazwa": k["nazwa"],
                             "miejscowosc": k["miejscowosc"], "powod": skad})
            continue
        zderzenie = _kolizja(k["nazwa"], miejsc, istniejace)
        if zderzenie:
            kolizje.append({"rspo": k["rspo"], "nazwa": k["nazwa"],
                            "miejscowosc": miejsc, "nasz": zderzenie})
            continue
        do_zapisu.append({
            "rspo": k["rspo"],
            "nazwa": k["nazwa"],
            "typ": typ_roboczy(k),
            "miejscowosc": miejsc,
            "miejscowosc_skad": skad,
            "miejscowosc_rejestr": k["miejscowosc"],
            "adres": rejestr_rspo.adres(k) or None,
            "telefon": k["telefon"],
            "mail": k["email"],
            "powiat": k["powiat"],
            "gmina": k["gmina"],
            "obszar": k["obszar"],
        })
    return {"grupa": grupa, "typy": list(typy), "braki_slownikow": braki,
            "do_zapisu": do_zapisu, "odlozone": odlozone, "kolizje": kolizje}


def zapisz(conn, plan, kto="migracja"):
    """
    Wstawia placówki i nieprzydzielone leady. Lead z `00. Nieprzydzielony`
    i bez handlowca to warunek, żeby dołożenie 733 rekordów NIE zmieniło
    ani jednej liście „moje szkoły" i ani jednego planu dnia.
    """
    if plan["braki_slownikow"]:
        raise ValueError(
            "Słownik tego profilu nie zna wartości: %s — najpierw uzupełnij "
            "słowniki, inaczej powstaną rekordy, których nie da się zapisać."
            % ", ".join("%s/%s" % b for b in plan["braki_slownikow"]))

    kolumny = ["rspo", "nazwa", "typ", "miejscowosc", "adres", "telefon",
               "mail", "powiat", "gmina", "obszar", "zrodlo"]
    dodane = 0
    for r in plan["do_zapisu"]:
        cur = conn.execute(
            "INSERT INTO placowki (%s) VALUES (%s)"
            % (", ".join(kolumny), ", ".join("?" * len(kolumny))),
            [str(r["rspo"]), r["nazwa"], r["typ"], r["miejscowosc"], r["adres"],
             r["telefon"], r["mail"], r["powiat"], r["gmina"], r["obszar"],
             ZRODLO])
        pid = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO leady (placowka_id, status_szkoly, status_realizacji)"
            " VALUES (?,?,?)", (pid, STATUS_SZKOLY_NOWA, STATUS_NOWEGO))
        # Ślad per lead, nie jeden zbiorczy: `log` wisi na leadzie i to on
        # odpowiada na pytanie „skąd się tu wziął ten rekord".
        db.zapisz_log(conn, lead_id=cur.lastrowid, kto=kto, co=LOG_CO,
                      pole="rspo", po=str(r["rspo"]))
        dodane += 1
    conn.commit()
    return dodane


def cofnij(conn, kto="migracja"):
    """
    Odwrotność dołożenia — kasuje WYŁĄCZNIE rekordy bez śladu pracy:
    źródło `rspo`, lead nieprzydzielony w statusie startowym, zero spotkań
    i zero wpisów w logu poza samym dołożeniem.

    To samo ostre kryterium, którym policzono 136 nietkniętych placówek przed
    migracją. Rekord, którego ktoś dotknął, zostaje — nawet gdyby cofanie
    miało przez to zostawić bałagan; bałagan da się posprzątać, skasowanego
    DT nie da się odzyskać.
    """
    kandydaci_do_kasacji = [(r["id"], r["lid"]) for r in conn.execute("""
        SELECT p.id, l.id AS lid
          FROM placowki p
          JOIN leady l ON l.placowka_id = p.id
         WHERE p.zrodlo = ?
           AND (l.handlowiec IS NULL OR l.handlowiec = '')
           AND COALESCE(l.status_realizacji,'') = ?
           AND NOT EXISTS (SELECT 1 FROM eventy e WHERE e.lead_id = l.id)
           AND NOT EXISTS (SELECT 1 FROM log g WHERE g.lead_id = l.id AND g.co <> ?)
    """, (ZRODLO, STATUS_NOWEGO, LOG_CO))]
    for pid, lid in kandydaci_do_kasacji:
        # `log` nie ma klucza obcego (ślad ma przeżyć skasowany rekord), więc
        # kasujemy go tu z ręki — inaczej po cofnięciu zostałyby wpisy
        # wskazujące na nieistniejące leady i każdy raport z historii
        # pokazywałby puste wiersze.
        conn.execute("DELETE FROM log WHERE lead_id=?", (lid,))
        conn.execute("DELETE FROM placowki WHERE id=?", (pid,))
    conn.commit()
    wszystkie = conn.execute(
        "SELECT COUNT(*) FROM placowki WHERE zrodlo=?", (ZRODLO,)).fetchone()[0]
    return {"skasowane": len(kandydaci_do_kasacji), "zostalo_z_rspo": wszystkie}
