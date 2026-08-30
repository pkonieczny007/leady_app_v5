# -*- coding: utf-8 -*-
"""
Filtr na chipach — wspólny dla list leadów, kalendarza i dostępności.

Powód istnienia: klient zgłosił dwa razy to samo. Najpierw „nie mogę filtrować
po pracownikach — rozsuwane listy z trenerami wyglądają jak filtr, ale to są
wypełnij", potem „w kalendarz i dostęp potrzebuję filtrów po pracowniku i filtr
ogólny; wpisujemy i filtruje wszystko i jego można przypiąć; dodatkowo można
zmienić na nazwisko i wtedy po nazwisku".

Sedno w obu przypadkach jest jedno: WPISAĆ kawałek tekstu, mieć kilka takich
wpisów naraz, móc jeden chwilowo zgasić i móc któryś przypiąć, żeby przetrwał
sprzątanie filtrów. Zamiast robić to trzy razy, jest tu jeden parser, jeden
zapis w URL i jedno dopasowanie — a ekrany różnią się tylko listą ZAKRESÓW,
które mają sens na danym ekranie.

Zapis w URL — chipy rozdzielone „|", każdy w postaci [flagi][zakres:]tekst:
    flagi   -  wpis wyłączony (widać go, ale nie zawęża)
            #  wpis przypięty (przeżywa „Wyczyść")
    zakres  jedna litera z ZAKRESY, patrz niżej
Przykład:  osoby=#n:Zemela|-w:Knurów|w:przedszkole

Wpisujemy FRAGMENT, nie całą wartość — w danych klienta ta sama osoba występuje
jako „18. Bitner" i „Bitner", a prefiksy 01./02. zostają w wartościach.
"""
from db import pl_fold

# zakres → (znak na chipie, krótka nazwa, wyjaśnienie w dymku)
ZAKRESY = {
    "o": ("◇", "dowolna osoba", "handlowiec albo ktokolwiek na spotkaniu"),
    "h": ("H", "handlowiec", "tylko handlowiec"),
    "t": ("T", "prowadzący", "trener, drugi prowadzący, zastępstwo, drukarz"),
    "w": ("∗", "wszystko", "dowolne pole wpisu: szkoła, miasto, osoba, sala, uwagi…"),
    "n": ("N", "nazwisko", "tylko osoba: prowadzący, zastępstwo, drukarz, handlowiec"),
}

# zestawy zakresów per ekran — to jedyne, czym ekrany się różnią
ZAKRESY_LEADY = ("o", "h", "t")          # listy leadów: pytanie brzmi „czyj to lead"
ZAKRESY_GRAFIK = ("w", "n")              # dostępność: „wszystko" albo „nazwisko"
# Kalendarz dostał „h" 30.08 (pkt 3 Kasi: „filtr w kalendarzu po PH — nie ma
# takiej możliwości"). To OSOBNY zakres, nie powrót handlowca do „nazwiska" —
# poprawka z Olszewską (patrz POLA_NA_MIEJSCU) zostaje w mocy: „n" dalej pyta
# „kto tam będzie", a „H" jawnie pyta „czyja to szkoła". Dostępność „h" NIE
# dostaje: jej wiersze to trenerzy, chip bez czego szukać dawałby pustą siatkę
# — `parsuj` sprowadzi tam takie chipy do „wszystko" zamiast gubić wpis.
ZAKRESY_KALENDARZ = ("w", "n", "h")

MAX_CHIPOW = 12                          # granica zdrowego rozsądku, nie techniczna


def parsuj(s, dozwolone=ZAKRESY_LEADY, domyslny=None):
    """
    Tekst z URL → lista chipów. Odporna na śmieci: co się nie parsuje, wypada.

    Zakres spoza `dozwolone` (ręcznie sklejony link, chip przeniesiony z innego
    ekranu) sprowadzamy do domyślnego, zamiast wywalać wpis — filtr, który po
    cichu gubi to, co widać w pasku adresu, jest gorszy niż filtr zbyt szeroki.
    """
    domyslny = domyslny or dozwolone[0]
    out, widziane = [], set()
    for kawalek in (s or "").split("|"):
        t = kawalek.strip()
        wylaczony = zablokowany = False
        while t and t[0] in "-#":
            if t[0] == "-":
                wylaczony = True
            else:
                zablokowany = True
            t = t[1:]
        zakres = domyslny
        # `>= 2`, nie `> 2`: samo „n:" ma być rozpoznane jako zakres z pustym
        # tekstem i wypaść niżej, a nie wylądować w chipie jako nazwisko „n:"
        if len(t) >= 2 and t[1] == ":" and t[0] in ZAKRESY:
            if t[0] in dozwolone:
                zakres = t[0]
            t = t[2:]
        t = t.strip()
        if not t:
            continue
        klucz = (zakres, pl_fold(t))
        if klucz in widziane:              # ten sam wpis dwa razy nic nie wnosi
            continue
        widziane.add(klucz)
        out.append({"tekst": t, "zakres": zakres,
                    "wylaczony": wylaczony, "zablokowany": zablokowany})
        if len(out) >= MAX_CHIPOW:
            break
    return out


def zapisz(chipy):
    """Lista chipów → tekst do URL. Odwrotność `parsuj`."""
    return "|".join(
        (("-" if c.get("wylaczony") else "") + ("#" if c.get("zablokowany") else "")
         + (c.get("zakres") or "o") + ":" + c["tekst"])
        for c in chipy)


def czytaj(args, dozwolone=ZAKRESY_LEADY, domyslny=None, klucz="osoby"):
    """
    Chipy z query stringa + wszystko, czego potrzebuje szablon.

    `tekst` jest znormalizowany (przepuszczony przez parsuj+zapisz), żeby ukryte
    pole formularza i linki niosły dokładnie to, co widać na ekranie jako chipy.
    """
    lista = parsuj(args.get(klucz), dozwolone, domyslny)
    tryb = "oraz" if (args.get(klucz + "_tryb") or "") == "oraz" else "lub"
    return {
        "lista": lista,
        "tekst": zapisz(lista),
        "zablokowane": zapisz([c for c in lista if c["zablokowany"]]),
        "tryb": tryb,
        "czynne": sum(1 for c in lista if not c["wylaczony"]),
        "dozwolone": list(dozwolone),
        "domyslny": domyslny or dozwolone[0],
    }


# ------------------------------------------------------------------ dopasowanie
#
# Listy leadów filtrują się w SQL (repo._warunek_osob), bo tam liczy się też
# stronicowanie i eksport. Kalendarz i dostępność filtrują się TUTAJ, w Pythonie,
# bo ich dane i tak powstają w Pythonie: cykle rozwijają się na wystąpienia,
# a wyjątki (zastępstwo na jedną datę) nadpisują trenera już po wyjściu z SQL.
# Filtrowanie w SQL zgubiłoby zastępstwo wpisane jako wyjątek cyklu.

def pasuje(chipy, tryb, pobierz_pole):
    """
    Czy rekord przechodzi przez filtr. `pobierz_pole(zakres)` ma zwrócić tekst,
    w którym szukamy dla danego zakresu (wołane tylko dla zakresów, które
    realnie wystąpiły w chipach).

    Brak czynnych chipów = przechodzi wszystko. Wyłączony chip nie liczy się
    wcale — o to właśnie chodzi w „wyłączaniu bez kasowania".
    """
    czynne = [c for c in chipy if not c.get("wylaczony")]
    if not czynne:
        return True
    trafienia = (pl_fold(c["tekst"]) in pl_fold(pobierz_pole(c["zakres"]))
                 for c in czynne)
    return all(trafienia) if tryb == "oraz" else any(trafienia)


# Kto JEST na spotkaniu — (kolumna, jak to nazwać na kafelku).
#
# HANDLOWCA TU NIE MA i to jest sedno poprawki. Zgłoszenie: „filtrując po
# 02. Olszewska w kalendarzu pokazuje mi też inne pozycje trenerów, ponieważ
# w tej samej szkole pojawia się ten trener". Przyczyna: `02. Olszewska` jest
# w ich danych JEDNOCZEŚNIE handlowcem i trenerką, a zakres „nazwisko"
# przeszukiwał również pole `handlowiec`. Na 152 trafienia w czerwcu 117 brało
# się z tego, że sprzedała lead — a na te zajęcia jeździł kto inny.
# Kalendarz odpowiada na pytanie „kto tam BĘDZIE", nie „kto to sprzedał".
# Handlowiec zostaje wyszukiwalny w zakresie „wszystko" — bo to znaczy wszystko.
POLA_NA_MIEJSCU = (("trener", "prowadzący"),
                   ("trener2", "2. prowadzący"),
                   ("zastepstwo", "zastępstwo"),
                   ("drukarz", "drukarz"),
                   ("trener_planowany", "planowany prowadzący"))

POLA_OSOBY = tuple(k for k, _ in POLA_NA_MIEJSCU)
POLA_WSZYSTKO = POLA_OSOBY + (
    "handlowiec", "placowka", "miejscowosc", "adres", "typ_placowki", "typ",
    "numer_sali", "grupa", "sprzet", "uwagi", "kod_tinkercad",
    "data", "godz_od", "godz_do", "status_realizacji", "wyjatek")


def _sklej(rekord, pola):
    return " ".join(str(rekord.get(k) or "") for k in pola)


def pola_eventu(e):
    """
    `pobierz_pole` dla jednego spotkania — z pamięcią, bo chipów bywa kilka.
    Zakresy grafiku: „n" (kto tam będzie), „h" (czyja to szkoła), „w" (wszystko).
    """
    pamiec = {}

    def pobierz(zakres):
        if zakres not in pamiec:
            if zakres == "n":
                pola = POLA_OSOBY
            elif zakres == "h":
                pola = ("handlowiec",)
            else:
                pola = POLA_WSZYSTKO
            pamiec[zakres] = _sklej(e, pola)
        return pamiec[zakres]
    return pobierz


def rola_trafienia(e, chipy):
    """
    W JAKIEJ ROLI szukana osoba jest na tym spotkaniu — pusty tekst, gdy jest
    prowadzącą (czyli gdy wpis siedzi w jej własnym wierszu macierzy).

    Bez tego zostaje druga połowa tego samego zgłoszenia: Olszewska bywa
    DRUKARZEM na zajęciach Gawrona, więc jej spotkanie ląduje w wierszu Gawrona.
    To prawda — ona tam jest — ale bez podpisu wygląda na pomyłkę filtra.
    Dlatego kafelek dostaje etykietę „drukarz" zamiast milczeć.
    """
    role = []
    for c in chipy:
        if c.get("wylaczony") or c.get("zakres") != "n":
            continue
        igla = pl_fold(c["tekst"])
        for klucz, etykieta in POLA_NA_MIEJSCU:
            if igla and igla in pl_fold(e.get(klucz) or "") and etykieta not in role:
                role.append(etykieta)
    if not role or "prowadzący" in role:
        return ""                     # to jej wiersz — nie ma czego tłumaczyć
    return ", ".join(role)


def filtruj_eventy(evs, chipy, tryb):
    """
    Spotkania przechodzące przez filtr. Pusta lista chipów → lista bez zmian.
    Przy okazji dopisuje `_rola` — dlaczego wpis przeszedł, gdy to nie jego wiersz.
    """
    if not [c for c in chipy if not c.get("wylaczony")]:
        return evs
    out = []
    for e in evs:
        if pasuje(chipy, tryb, pola_eventu(e)):
            e["_rola"] = rola_trafienia(e, chipy)
            out.append(e)
    return out
