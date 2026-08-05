# -*- coding: utf-8 -*-
"""
test_parsers.py — testy modułu ``parsers`` dla leady_app_v3.

Uruchomienie:  ``python test_parsers.py``   (albo ``python -m unittest -v test_parsers``)
Bez żadnych zależności zewnętrznych.

WSZYSTKIE przypadki testowe pochodzą z REALNYCH danych klienta, nie są wymyślone.
Źródła (oznaczone w komentarzach):
  [PH]  = ``PH Nowy  Nad którym pracuję jako główny  .xlsx``
          zakładki: BAZA, Sacawa, Olszewska, Zbiorczy, Kalendarz * DT
  [DT]  = ``DT 2025-2026 NOWY PIĘKNY PLIK.xlsx``
          zakładki: "DT 2025-2026 dograne", "Kasia/Zuza/Chytry BRUDNOPIS",
          "Chytry dograne"
  [WAL] = listy walidacji (data validation) z [PH], patrz docs/FAZA2_PH_Nowy.md
"""

import datetime as dt
import unittest

import parsers as P


# ===========================================================================
class TestParseDate(unittest.TestCase):
    """``parse_date`` — kolumny D 'death line' i M 'Data DT'."""

    def test_datetime_i_date(self):
        # [PH] BAZA/Sacawa: openpyxl zwraca WYŁĄCZNIE datetime w D i M (13 + 45 komórek)
        self.assertEqual(P.parse_date(dt.datetime(2026, 7, 3, 0, 0)), dt.date(2026, 7, 3))
        self.assertEqual(P.parse_date(dt.datetime(2026, 9, 10, 0, 0)), dt.date(2026, 9, 10))
        self.assertEqual(P.parse_date(dt.date(2026, 8, 28)), dt.date(2026, 8, 28))
        # [DT] "Chytry BRUDNOPIS"!E — datetime z godziną w środku
        self.assertEqual(P.parse_date(dt.datetime(2025, 9, 15, 8, 0)), dt.date(2025, 9, 15))

    def test_iso_tekstowe(self):
        self.assertEqual(P.parse_date("2026-09-10"), dt.date(2026, 9, 10))
        self.assertEqual(P.parse_date("2026/09/10"), dt.date(2026, 9, 10))

    def test_dzien_pierwszy(self):
        # [DT] "Chytry BRUDNOPIS"!E — wszystkie realne warianty separatorów
        self.assertEqual(P.parse_date("10.09.2025 8:00-10:34"), dt.date(2025, 9, 10))
        self.assertEqual(P.parse_date("5-09-2025 8:00-9:35"), dt.date(2025, 9, 5))
        self.assertEqual(P.parse_date("08.09.2025 od 8:00-9:10"), dt.date(2025, 9, 8))
        self.assertEqual(P.parse_date("26.11.2025 8:00-11:00"), dt.date(2025, 11, 26))
        self.assertEqual(P.parse_date("20.01.2026r. 9:30-13:00"), dt.date(2026, 1, 20))
        self.assertEqual(P.parse_date("11-09-2025 8:00-10:00"), dt.date(2025, 9, 11))
        self.assertEqual(P.parse_date("22.09.2025  8:00- 10:30"), dt.date(2025, 9, 22))

    def test_data_zanurzona_w_tekscie(self):
        # [DT] data NIE na początku komórki
        self.assertEqual(P.parse_date("9:00 2025-10-21"), dt.date(2025, 10, 21))
        self.assertEqual(P.parse_date("2025-10-30 godzina 10:45"), dt.date(2025, 10, 30))
        self.assertEqual(P.parse_date("2025-10-06 godz.9:50"), dt.date(2025, 10, 6))
        self.assertEqual(P.parse_date("2025-09-08 08:00-11"), dt.date(2025, 9, 8))
        # dwie daty w komórce -> pierwsza
        self.assertEqual(
            P.parse_date("7.10.2025 (4 klasy)   09.10.2025 (3 klasy)"), dt.date(2025, 10, 7)
        )

    def test_dziwne_separatory(self):
        # [DT] "Chytry BRUDNOPIS"!E — przecinek zamiast kropki i spacja przed kropką
        self.assertEqual(P.parse_date("24,04,2026 9:30-11:00"), dt.date(2026, 4, 24))
        self.assertEqual(P.parse_date("10:00 16 .10.2025"), dt.date(2025, 10, 16))

    def test_rok_dwucyfrowy(self):
        self.assertEqual(P.parse_date("10.09.26"), dt.date(2026, 9, 10))

    def test_serial_excela(self):
        self.assertEqual(P.parse_date(45910), dt.date(2025, 9, 10))
        self.assertEqual(P.parse_date(45910.375), dt.date(2025, 9, 10))
        self.assertEqual(P.parse_date("45910"), dt.date(2025, 9, 10))

    def test_smieci_i_braki(self):
        for v in (None, "", "   ", "."):
            self.assertIsNone(P.parse_date(v), f"parse_date({v!r})")
        # [DT] realne śmieci w kolumnie daty
        self.assertIsNone(P.parse_date("usuwam natali z kalendarza"))
        self.assertIsNone(P.parse_date("DT Data i godz"))
        self.assertIsNone(P.parse_date("Data i godzina DT"))

    def test_data_bez_roku_jest_odrzucana(self):
        # świadoma decyzja: bez roku nie zgadujemy (mogłoby wpaść w zły rok szkolny)
        self.assertIsNone(P.parse_date("24.09 8:00 - 10:00"))
        self.assertIsNone(P.parse_date("od 29.09 do 3.10 nie mozna"))
        self.assertIsNone(P.parse_date("23.05"))

    def test_zakres_godzin_to_nie_data(self):
        # regresja: "12.35-13.35" nie może dać miesiąca 35
        for v in ("12:30-14:30", "9.30-13.30", "13:30-14:30, 14:40-15:40", "12.35-13.35"):
            self.assertIsNone(P.parse_date(v), f"parse_date({v!r})")

    def test_male_liczby_nie_sa_datami(self):
        # "8 klas" / liczba porządkowa nie może zamienić się w 1900-01-08
        self.assertIsNone(P.parse_date(8))
        self.assertIsNone(P.parse_date(200))
        self.assertIsNone(P.parse_date(True))  # bool to nie liczba serialna


# ===========================================================================
class TestParseTime(unittest.TestCase):
    """``parse_time`` — kolumna N 'Godzina DT' i W 'Numer sali cykle'."""

    def test_typy_z_openpyxl(self):
        # [PH] Sacawa!N: realnie time x9 ORAZ timedelta x1 w tej samej kolumnie
        self.assertEqual(P.parse_time(dt.time(8, 55)), dt.time(8, 55))
        self.assertEqual(P.parse_time(dt.time(10, 45)), dt.time(10, 45))
        self.assertEqual(P.parse_time(dt.datetime(2026, 9, 10, 7, 45)), dt.time(7, 45))
        # timedelta(seconds=31800) == 8:50 — to jest ta jedna odstająca komórka
        self.assertEqual(P.parse_time(dt.timedelta(seconds=31800)), dt.time(8, 50))
        # [PH] Sacawa!W (kolumna "Numer sali cykle") zawiera GODZINĘ 13:30
        self.assertEqual(P.parse_time(dt.time(13, 30)), dt.time(13, 30))

    def test_timedelta_ponad_24h_zawija(self):
        self.assertEqual(P.parse_time(dt.timedelta(days=1, seconds=31800)), dt.time(8, 50))
        self.assertIsNone(P.parse_time(dt.timedelta(seconds=-10)))

    def test_float_excela(self):
        self.assertEqual(P.parse_time(0.375), dt.time(9, 0))
        self.assertEqual(P.parse_time(0.0), dt.time(0, 0))
        self.assertEqual(P.parse_time(45910.375), dt.time(9, 0))
        self.assertEqual(P.parse_time(8.0), dt.time(8, 0))

    def test_tekst(self):
        # [DT] kol. 12 "GODZINA rozpoczęcia i zakończenia"
        self.assertEqual(P.parse_time("8:00"), dt.time(8, 0))
        self.assertEqual(P.parse_time("08:55"), dt.time(8, 55))
        self.assertEqual(P.parse_time("9:30:00"), dt.time(9, 30))
        # klient miesza kropkę z dwukropkiem
        self.assertEqual(P.parse_time("8.00"), dt.time(8, 0))
        self.assertEqual(P.parse_time("13.30"), dt.time(13, 30))
        self.assertEqual(P.parse_time("godz 9:40"), dt.time(9, 40))
        # sama godzina bez minut — [DT] "Wt 15-16"
        self.assertEqual(P.parse_time("15"), dt.time(15, 0))
        # z zakresu bierze pierwszą godzinę
        self.assertEqual(P.parse_time("8:00-11:30"), dt.time(8, 0))
        self.assertEqual(P.parse_time("08:00- 9.50"), dt.time(8, 0))
        # [DT] literówka klienta: dwukropek zamiast myślnika
        self.assertEqual(P.parse_time("15:00:15:45"), dt.time(15, 0))

    def test_smieci(self):
        for v in (None, "", "  ", "330", "Są cykliczne", "do ustalenia w sekretariacie",
                  "Szkolna 24", "xxx", "BRAK DOSTĘPNOŚCI", True):
            self.assertIsNone(P.parse_time(v), f"parse_time({v!r})")


# ===========================================================================
class TestParseTimeRange(unittest.TestCase):
    """``parse_time_range`` / ``parse_time_ranges`` — kolumny X i 'GODZINA rozp-zak'."""

    def test_prosty_zakres(self):
        # [DT] realne wartości
        self.assertEqual(P.parse_time_range("08:00-12:30"), (dt.time(8, 0), dt.time(12, 30)))
        self.assertEqual(P.parse_time_range("8:00-11:30"), (dt.time(8, 0), dt.time(11, 30)))
        self.assertEqual(P.parse_time_range("8:55 - 12:45"), (dt.time(8, 55), dt.time(12, 45)))
        self.assertEqual(P.parse_time_range("09:50-12:55"), (dt.time(9, 50), dt.time(12, 55)))
        self.assertEqual(P.parse_time_range("13.30-14.30"), (dt.time(13, 30), dt.time(14, 30)))
        self.assertEqual(P.parse_time_range("8:00 -11:30"), (dt.time(8, 0), dt.time(11, 30)))

    def test_godzina_bez_minut_w_zakresie(self):
        # [DT] "Wt 15-16", "8-9:35"
        self.assertEqual(P.parse_time_range("8-9:35"), (dt.time(8, 0), dt.time(9, 35)))
        self.assertEqual(P.parse_time_range("15-16"), (dt.time(15, 0), dt.time(16, 0)))

    def test_dwa_zakresy_pierwszy_plus_reszta(self):
        # [DT] kol. 15 "CYKLICZNE godzina" — najczęstsza wartość (x5)
        s, k = P.parse_time_range("12:30-14:30, 14:40-15:40")
        self.assertEqual((s, k), (dt.time(12, 30), dt.time(14, 30)))
        s, k, reszta = P.parse_time_range("12:30-14:30, 14:40-15:40", ze_reszta=True)
        self.assertEqual(reszta, "14:40-15:40")
        s, k, reszta = P.parse_time_range("13:30-14:30, 14:40-15:40", ze_reszta=True)
        self.assertEqual((s, k), (dt.time(13, 30), dt.time(14, 30)))
        self.assertEqual(reszta, "14:40-15:40")

    def test_wszystkie_zakresy(self):
        zakresy, _ = P.parse_time_ranges("9:40-10:40, 12:30-13:30, 13:30-14:30")
        self.assertEqual(
            zakresy,
            [
                (dt.time(9, 40), dt.time(10, 40)),
                (dt.time(12, 30), dt.time(13, 30)),
                (dt.time(13, 30), dt.time(14, 30)),
            ],
        )
        # [DT] separatory: przecinek, "i", nowa linia, sama spacja
        for v, n in [
            ("12:45-13.45 i 13:55-14:55", 2),
            ("13:45-14:45\n14:50-15:50", 2),
            ("15:20-16:20 16:30-17:30", 2),
            ("14:40-15:40 i 15:50- 16:50", 2),
            ("14:25-15:25  15:35-16:35", 2),
        ]:
            self.assertEqual(len(P.parse_time_ranges(v)[0]), n, f"parse_time_ranges({v!r})")

    def test_reszta_zachowuje_kontekst(self):
        # [DT] "PN. 12:25-13:25, 13:35-14:35\nPT. 11:25-12:25" — dni MUSZĄ zostać w reszcie
        zakresy, reszta = P.parse_time_ranges("PN. 12:25-13:25, 13:35-14:35\nPT. 11:25-12:25")
        self.assertEqual(len(zakresy), 3)
        self.assertIn("PN", " ".join(reszta))
        self.assertIn("PT", " ".join(reszta))
        # [DT] cykl miesięczny z listą dat
        zakresy, reszta = P.parse_time_ranges(
            "2gi Piątek miesiąca : 13.30-14:15, daty:10.10, 14.11, 05.12"
        )
        self.assertEqual(zakresy[0], (dt.time(13, 30), dt.time(14, 15)))
        self.assertIn("10.10", " ".join(reszta))

    def test_jedna_godzina_bez_konca(self):
        self.assertEqual(P.parse_time_range("08:00"), (dt.time(8, 0), None))
        self.assertEqual(P.parse_time_range(dt.time(14, 0)), (dt.time(14, 0), None))

    def test_brak_zakresu(self):
        self.assertEqual(P.parse_time_range(""), (None, None))
        self.assertEqual(P.parse_time_range(None), (None, None))
        # [DT] realny tekst bez godzin
        self.assertEqual(
            P.parse_time_range("Chcą nas co miesiąć - nie mają konkretnych dat"), (None, None)
        )


# ===========================================================================
class TestParseIntLoose(unittest.TestCase):
    """``parse_int_loose`` — kolumny R 'Ilość klas 1-4' i S 'Ilość dzieci'."""

    def test_wymagane_przypadki(self):
        self.assertEqual(P.parse_int_loose("10 klas"), 10)
        self.assertEqual(P.parse_int_loose("około 200"), 200)
        self.assertEqual(P.parse_int_loose(330), 330)
        self.assertEqual(P.parse_int_loose("ok. 240"), 240)
        self.assertIsNone(P.parse_int_loose(""))

    def test_realne_wartosci_kolumny_R(self):
        # [PH] Sacawa!R — wszystkie 5 unikalnych wartości
        for txt, exp in [("8 klas", 8), ("10 klas", 10), ("14 klas", 14),
                         ("12 klas", 12), ("7 klas", 7)]:
            self.assertEqual(P.parse_int_loose(txt), exp)
        # [DT] kol. 7 "ilość dzieci/klas"
        self.assertEqual(P.parse_int_loose("4 klasy"), 4)
        self.assertEqual(P.parse_int_loose("9 klas"), 9)
        self.assertEqual(P.parse_int_loose("3 gr"), 3)

    def test_realne_wartosci_kolumny_S(self):
        # [PH] Sacawa!S — float i str w JEDNEJ kolumnie
        self.assertEqual(P.parse_int_loose("około 240"), 240)
        self.assertEqual(P.parse_int_loose("około 200"), 200)
        self.assertEqual(P.parse_int_loose(190.0), 190)
        self.assertEqual(P.parse_int_loose(330.0), 330)
        self.assertEqual(P.parse_int_loose(340.0), 340)
        self.assertEqual(P.parse_int_loose(170.0), 170)

    def test_zbitki_klasy_dzieci(self):
        # [DT] kol. 11 "DT ilość klas/dzieci" wg wzoru "10/186" — bierzemy pierwszą liczbę
        self.assertEqual(P.parse_int_loose("8/200"), 8)
        self.assertEqual(P.parse_int_loose("13/254"), 13)
        self.assertEqual(P.parse_int_loose("4 / 60"), 4)
        self.assertEqual(P.parse_int_loose("3/"), 3)
        self.assertEqual(P.parse_int_loose("/9"), 9)
        self.assertEqual(P.parse_int_loose("/50 (ogl jest 120)"), 50)
        self.assertEqual(P.parse_int_loose("2 klasy 43 dzieci"), 2)
        self.assertEqual(P.parse_int_loose("8 klas, 80 dzieci,"), 8)
        self.assertEqual(P.parse_int_loose("8 grup 140 dzieci"), 8)
        self.assertEqual(P.parse_int_loose("podzielone na 2:  277 dzieci 13 grup"), 2)

    def test_data_w_kolumnie_liczbowej(self):
        # [DT] kol. 11 realnie zawiera 3 komórki z datą — NIE wolno jej policzyć
        self.assertIsNone(P.parse_int_loose(dt.datetime(2025, 7, 30, 0, 0)))
        self.assertIsNone(P.parse_int_loose(dt.date(2025, 2, 20)))
        self.assertIsNone(P.parse_int_loose(dt.time(8, 0)))

    def test_smieci(self):
        for v in (None, "", "   ", True, False, "brak", "do ustalenia"):
            self.assertIsNone(P.parse_int_loose(v), f"parse_int_loose({v!r})")

    def test_znak_pytania(self):
        # [DT] kol. 17 "Numer sali" = "13?"
        self.assertEqual(P.parse_int_loose("13?"), 13)


# ===========================================================================
class TestParsePhone(unittest.TestCase):
    """``parse_phone`` — kolumna I 'numer telefonu'."""

    def test_formula_tekstowa(self):
        # [PH] BAZA!I4 przy data_only=False to DOSŁOWNIE ta formuła (535 komórek!)
        self.assertEqual(P.parse_phone('="601290441"'), "601 290 441")
        self.assertEqual(P.parse_phone('="322525199"'), "32 252 51 99")
        # ta sama komórka przy data_only=True
        self.assertEqual(P.parse_phone("601290441"), "601 290 441")
        self.assertEqual(P.parse_phone("322525199"), "32 252 51 99")

    def test_float_z_excela(self):
        # [DT] kol. 10/12 — openpyxl zwraca float dla 8-13 komórek
        self.assertEqual(P.parse_phone(322672142.0), "32 267 21 42")
        self.assertEqual(P.parse_phone(509921071.0), "509 921 071")

    def test_stacjonarne_ze_spacjami(self):
        # [PH] Sacawa!I — wszystkie realne
        for src, exp in [
            ("32 235 27 15", "32 235 27 15"),
            ("32 235 27 27", "32 235 27 27"),
            ("32 330 41 20", "32 330 41 20"),
            (" 32 268 86 02", "32 268 86 02"),
            ("32 2675035", "32 267 50 35"),
            ("32 25715 85", "32 257 15 85"),
        ]:
            self.assertEqual(P.parse_phone(src), exp, f"parse_phone({src!r})")

    def test_inne_separatory(self):
        # [DT] kol. 10 — nawiasy, myślniki, ukośnik, zero przed kierunkowym
        self.assertEqual(P.parse_phone("32 264-13-00"), "32 264 13 00")
        self.assertEqual(P.parse_phone("(032) 267-49-96"), "32 267 49 96")
        self.assertEqual(P.parse_phone("32/266-10-02"), "32 266 10 02")
        self.assertEqual(P.parse_phone("(32) 220 13 78"), "32 220 13 78")
        self.assertEqual(P.parse_phone("693-873-496"), "693 873 496")
        self.assertEqual(P.parse_phone("512-328-878"), "512 328 878")

    def test_prefiks_kraju(self):
        self.assertEqual(P.parse_phone("+48 601 290 441"), "601 290 441")
        self.assertEqual(P.parse_phone("0048601290441"), "601 290 441")
        self.assertEqual(P.parse_phone("+48322352715"), "32 235 27 15")

    def test_kilka_numerow_w_komorce(self):
        # [DT] realne komórki z 2 numerami
        self.assertEqual(
            P.parse_phone("32 762 93 51, 32 762 93 57"), "32 762 93 51, 32 762 93 57"
        )
        self.assertEqual(
            P.parse_phone("(32) 258-35-66  lub  513 - 065 - 806"),
            "32 258 35 66, 513 065 806",
        )
        self.assertEqual(
            P.parse_phone("32 211 62 29 \n693 945 512"), "32 211 62 29, 693 945 512"
        )
        self.assertEqual(
            P.parse_phone("668 514 940 , 32 261 29 30"), "668 514 940, 32 261 29 30"
        )
        self.assertEqual(
            P.parse_phone("32 22 82 053    / 502053084"), "32 228 20 53, 502 053 084"
        )

    def test_numer_z_komentarzem(self):
        # komentarz zostaje w kolumnie źródłowej — parser zwraca wyłącznie numery
        self.assertEqual(P.parse_phone("697989257 (można SMS)"), "697 989 257")
        self.assertEqual(
            P.parse_phone("32 262 69 68 Anna Nauczycielka klas 1-3 tel: 505081686"),
            "32 262 69 68, 505 081 686",
        )
        self.assertEqual(
            P.parse_phone("Jolanta: 604063813, sekretariat: 32 266 75 78"),
            "604 063 813, 32 266 75 78",
        )

    def test_to_nie_jest_telefon(self):
        # [DT] realne śmieci w kolumnie telefonu
        for v in (None, "", "   ", "Szkolna 24", "Są cykliczne", "telefon", "-"):
            self.assertIsNone(P.parse_phone(v), f"parse_phone({v!r})")

    def test_niepelny_numer_odrzucony(self):
        # [DT] "2 264 16 66" = 8 cyfr, brak jednej — świadomie None (raportowane)
        self.assertIsNone(P.parse_phone("2 264 16 66"))


# ===========================================================================
class TestParseDniTygodnia(unittest.TestCase):
    """``parse_dni_tygodnia`` — kolumna V 'Zajecia cykliczne (dzień tygodnia)'."""

    def test_wymagane_przypadki(self):
        self.assertEqual(P.parse_dni_tygodnia("poniedziałek"), ["poniedziałek"])
        self.assertEqual(
            P.parse_dni_tygodnia("Poniedziałek i piątek"), ["poniedziałek", "piątek"]
        )
        self.assertEqual(P.parse_dni_tygodnia("wtorek, środa"), ["wtorek", "środa"])

    def test_lista_walidacji(self):
        # [WAL] LISTA 9 — dokładnie te 6 wartości
        for d in ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"):
            self.assertEqual(P.parse_dni_tygodnia(d), [d], f"dzien {d!r}")

    def test_wielkie_litery(self):
        # [DT] kol. 14 — klient pisze z wielkiej litery
        self.assertEqual(P.parse_dni_tygodnia("Środa"), ["środa"])
        self.assertEqual(P.parse_dni_tygodnia("Czwartek"), ["czwartek"])
        self.assertEqual(P.parse_dni_tygodnia("Wtorek i środa"), ["wtorek", "środa"])

    def test_kolejnosc_tygodniowa(self):
        # wynik zawsze w kolejności tygodnia, niezależnie od kolejności w tekście
        self.assertEqual(
            P.parse_dni_tygodnia("piątek i poniedziałek"), ["poniedziałek", "piątek"]
        )

    def test_skroty_i_odmiany(self):
        # [DT] kol. 8 "Cykliczne / sala" — skróty wplecione w tekst
        self.assertEqual(P.parse_dni_tygodnia("Czw 12:50-13:50 INFORMATYCZNA"), ["czwartek"])
        self.assertEqual(P.parse_dni_tygodnia("Pt 12:55-13:55 INFORMATYCZNA"), ["piątek"])
        self.assertEqual(P.parse_dni_tygodnia("Wt 15:35-16:35 sala 22"), ["wtorek"])
        self.assertEqual(P.parse_dni_tygodnia("Śr 16:15-17:15"), ["środa"])
        self.assertEqual(P.parse_dni_tygodnia("Pon 12:35-13:35"), ["poniedziałek"])
        self.assertEqual(
            P.parse_dni_tygodnia("PN. 12:25-13:25, 13:35-14:35\nPT. 11:25-12:25"),
            ["poniedziałek", "piątek"],
        )
        self.assertEqual(
            P.parse_dni_tygodnia("WT 15:00-16:00\nŚR. 15:00-16:00"), ["wtorek", "środa"]
        )
        # liczba mnoga i cykle miesięczne
        self.assertEqual(P.parse_dni_tygodnia("Poniedziałki gr1: 16:30"), ["poniedziałek"])
        self.assertEqual(
            P.parse_dni_tygodnia("1wsze czwartki miesiąca 15:00-15:45"), ["czwartek"]
        )
        self.assertEqual(P.parse_dni_tygodnia("3cia środa miesiąca 9:30-11:30"), ["środa"])
        self.assertEqual(P.parse_dni_tygodnia('"2gi" Pon miesiąca 15:00:15:45'), ["poniedziałek"])
        self.assertEqual(
            P.parse_dni_tygodnia("wt 13:05 I piątek 13:05"), ["wtorek", "piątek"]
        )
        # [DT] "Grupa 1 (Wtorki, 14:50–15:35)"
        self.assertEqual(P.parse_dni_tygodnia("Grupa 1 (Wtorki, 14:50–15:35)"), ["wtorek"])
        # [DT] skrót BEZ spacji przed godziną — realna komórka
        self.assertEqual(
            P.parse_dni_tygodnia("Pon12:40-13:40 i 13:50-14:50 INFORMATYCZNA"),
            ["poniedziałek"],
        )

    def test_skrot_nie_lapie_zwyklych_slow(self):
        # regresja: skróty nie mogą trafiać w środek/początek innych wyrazów
        for v in ("ponowić kontakt", "wtyczka", "czynne", "srogi", "sobie",
                  "ptaki", "ndzieja", "Nasz sprzęt", "Sala komputerowa"):
            self.assertEqual(P.parse_dni_tygodnia(v), [], f"parse_dni_tygodnia({v!r})")

    def test_brak_dnia(self):
        for v in (None, "", "   ", "brak", "LAPTOPY", "INFORMATYCZNA", "Nasz sprzęt"):
            self.assertEqual(P.parse_dni_tygodnia(v), [], f"parse_dni_tygodnia({v!r})")


# ===========================================================================
class TestStripPrefix(unittest.TestCase):
    """``strip_prefix`` — prefiksy '01. ' służą klientowi do sortowania."""

    def test_wymagany_przypadek(self):
        self.assertEqual(P.strip_prefix("01. Sacawa"), ("01", "Sacawa"))

    def test_realne_wartosci(self):
        self.assertEqual(P.strip_prefix("02. Olszewska"), ("02", "Olszewska"))
        self.assertEqual(P.strip_prefix("11. Białas (Pszczyna)"), ("11", "Białas (Pszczyna)"))
        self.assertEqual(P.strip_prefix("04. BRAK KONTAKTU ZE SZKOŁĄ"),
                         ("04", "BRAK KONTAKTU ZE SZKOŁĄ"))
        self.assertEqual(P.strip_prefix("09. Pszczyna powiat"), ("09", "Pszczyna powiat"))
        self.assertEqual(P.strip_prefix("18. Młynarczyk Adam"), ("18", "Młynarczyk Adam"))
        self.assertEqual(P.strip_prefix("01. Próba kontaktu (Brak konkretów)"),
                         ("01", "Próba kontaktu (Brak konkretów)"))

    def test_zachowanie_wiodacego_zera(self):
        prefiks, _ = P.strip_prefix("01. Sacawa")
        self.assertIsInstance(prefiks, str)
        self.assertEqual(prefiks, "01")

    def test_bez_prefiksu(self):
        # [PH] BAZA!A zawiera "Bitner" bez prefiksu
        self.assertEqual(P.strip_prefix("Bitner"), (None, "Bitner"))
        self.assertEqual(P.strip_prefix("poniedziałek"), (None, "poniedziałek"))
        self.assertEqual(P.strip_prefix(""), (None, ""))
        self.assertEqual(P.strip_prefix(None), (None, ""))

    def test_puste_pozycje_listy_trenerow(self):
        # [WAL] LISTA 6 ma pozycje "31. ", "32.", ... "40."
        self.assertEqual(P.strip_prefix("31. "), ("31", ""))
        self.assertEqual(P.strip_prefix("32."), ("32", ""))
        self.assertEqual(P.strip_prefix("40."), ("40", ""))

    def test_liczba_ze_slowem_to_nie_prefiks(self):
        # regresja: "8 klas" nie może zostać zinterpretowane jako prefiks 8
        self.assertEqual(P.strip_prefix("8 klas"), (None, "8 klas"))
        self.assertEqual(P.strip_prefix("12 klas"), (None, "12 klas"))


# ===========================================================================
class TestNormSlownik(unittest.TestCase):
    """``norm_slownik`` — naprawia UDOKUMENTOWANE literówki i rozjazdy klienta."""

    def test_wymagane_literowki(self):
        self.assertEqual(P.norm_slownik("02. Olaszewska", "handlowiec"), "02. Olszewska")
        self.assertEqual(
            P.norm_slownik("11. Białass (Pszczyna)", "trener"), "11. Białas (Pszczyna)"
        )
        self.assertEqual(P.norm_slownik("23. Trenner 5", "trener"), "24. Trener 5")
        self.assertEqual(P.norm_slownik("22. Trene 3", "trener"), "21. Trener 3")

    def test_wymagane_scalenia_miejscowosci(self):
        self.assertEqual(P.norm_slownik("09. Pszczyna powiat", "miejscowosc"), "09. Pszczyna")
        self.assertEqual(P.norm_slownik("09. Pszczyna", "miejscowosc"), "09. Pszczyna")
        self.assertEqual(P.norm_slownik("15. Będzin powiat", "miejscowosc"), "15. Będzin")
        self.assertEqual(P.norm_slownik("15. Będzin", "miejscowosc"), "15. Będzin")
        self.assertEqual(P.norm_slownik("19. Chorzow", "miejscowosc"), "16. Chorzów")
        self.assertEqual(P.norm_slownik("16. Chorzów", "miejscowosc"), "16. Chorzów")

    def test_pozostale_rozjazdy_numeracji(self):
        # [WAL] LISTA 11 (Sacawa!E14:E200) ma zupełnie inną numerację niż BAZA
        self.assertEqual(P.norm_slownik("10. Katowice", "miejscowosc"), "08. Katowice")
        self.assertEqual(P.norm_slownik("11. Zabrze", "miejscowosc"), "19. Zabrze")
        self.assertEqual(P.norm_slownik("12. Ruda Śląska", "miejscowosc"), "20. Ruda Śląska")
        self.assertEqual(P.norm_slownik("17. Sosnowiec", "miejscowosc"), "13. Sosnowiec")
        self.assertEqual(
            P.norm_slownik("15. Piekary Śląskie", "miejscowosc"), "10. Piekary Śląskie"
        )
        # dublet w JEDNEJ liście: 14 i 17 to to samo miasto
        self.assertEqual(
            P.norm_slownik("17. Dąbrowa Górnicza", "miejscowosc"), "14. Dąbrowa Górnicza"
        )
        self.assertEqual(
            P.norm_slownik("14. Dąbrowa Górnicza", "miejscowosc"), "14. Dąbrowa Górnicza"
        )
        # literówka bez ż
        self.assertEqual(P.norm_slownik("21. Strzyzowice", "miejscowosc"), "21. Strzyżowice")

    def test_rozjazd_numeracji_trenerow(self):
        # [WAL] LISTA 8 "23. Trener 4" vs Kalendarz!A24 "22. Trener 4"
        self.assertEqual(P.norm_slownik("23. Trener 4", "trener"), "22. Trener 4")
        self.assertEqual(P.norm_slownik("22. Trener 4", "trener"), "22. Trener 4")
        # osoby o tym samym prefiksie w dwóch listach zostają rozdzielone po nazwie
        self.assertEqual(P.norm_slownik("18. Bitner", "trener"), "18. Bitner")
        self.assertEqual(
            P.norm_slownik("18. Młynarczyk Adam", "trener"), "18. Młynarczyk Adam"
        )
        self.assertEqual(P.norm_slownik("20. Sacawa", "trener"), "20. Sacawa")
        self.assertEqual(P.norm_slownik("20. Trener 1", "trener"), "20. Trener 1")

    def test_wartosci_ktore_maja_zostac_bez_zmian(self):
        for v, r in [
            ("01. Sacawa", "handlowiec"),
            ("02. Olszewska", "handlowiec"),
            ("03. Małolepsza", "handlowiec"),
            ("04. Chytry", "handlowiec"),
            ("01. Nowa szkoła", "status_szkoly"),
            ("02. Kontynuacja", "status_szkoly"),
            ("03. DT umówione", "status_realizacji"),
            ("04. BRAK KONTAKTU ZE SZKOŁĄ", "status_realizacji"),
            ("01. Tak", "dt"),
            ("02. Do ustalenia", "dt"),
            ("01. Podsumowanie DT", "mail_propozycja"),
            ("04. Zemela", "trener"),
            ("03. Majewska", "trener"),
            ("08. Katowice", "miejscowosc"),
        ]:
            self.assertEqual(P.norm_slownik(v, r), v, f"norm_slownik({v!r}, {r!r})")

    def test_handlowiec_bez_prefiksu(self):
        # [PH] BAZA!A ma jedną komórkę "Bitner"
        self.assertEqual(P.norm_slownik("Bitner", "handlowiec"), "Bitner")

    def test_puste_pozycje_listy_trenerow_odrzucone(self):
        for v in ("31.", "31. ", "32.", "40."):
            self.assertIsNone(P.norm_slownik(v, "trener"), f"norm_slownik({v!r}, 'trener')")

    def test_pusta_wartosc(self):
        for v in (None, "", "   "):
            self.assertIsNone(P.norm_slownik(v, "miejscowosc"))

    def test_nieznana_wartosc_nie_ginie(self):
        # nie znamy jej -> zwracamy oczyszczoną, żeby import mógł ją zaraportować
        self.assertEqual(P.norm_slownik("Nieznane  Miasto", "miejscowosc"), "Nieznane Miasto")
        self.assertEqual(P.norm_slownik("99. Ktoś Nowy", "trener"), "99. Ktoś Nowy")

    def test_niejednoznaczne_rozmyte_odrzucone(self):
        # "trener 6" jest w odległości 1 od Trener 1..5 -> ŻADNEGO nie wybieramy
        self.assertEqual(P.norm_slownik("trener 6", "trener"), "trener 6")

    def test_wlasny_slownik_aliasow(self):
        wlasne = {"miejscowosc": {"09. Pszczyna powiat": "99. TEST"}}
        self.assertEqual(
            P.norm_slownik("09. Pszczyna powiat", "miejscowosc", wlasne), "99. TEST"
        )

    def test_nieznany_rodzaj(self):
        self.assertEqual(P.norm_slownik("cokolwiek", "nie_ma_takiego"), "cokolwiek")

    def test_tak_nie_z_recznego_wpisu(self):
        self.assertEqual(P.norm_slownik("tak", "tak_nie"), "01. Tak")
        self.assertEqual(P.norm_slownik("NIE", "tak_nie"), "02. Nie")

    def test_slowniki_maja_unikalne_nazwy(self):
        # niezmiennik: prefiks może się dublować, NAZWA nie może
        for rodzaj, lista in P.SLOWNIKI.items():
            nazwy = [P.strip_prefix(v)[1].lower() for v in lista]
            self.assertEqual(
                len(nazwy), len(set(nazwy)), f"zdublowana nazwa w słowniku {rodzaj!r}"
            )

    def test_slowniki_sa_stabilne(self):
        # każda wartość kanoniczna musi normalizować się do siebie samej
        for rodzaj, lista in P.SLOWNIKI.items():
            for v in lista:
                self.assertEqual(
                    P.norm_slownik(v, rodzaj), v, f"niestabilne: {rodzaj}/{v!r}"
                )

    def test_aliasy_wskazuja_na_istniejace_wartosci(self):
        for rodzaj, mapa in P.ALIASY.items():
            kanon = P.SLOWNIKI.get(rodzaj, [])
            for zle, dobre in mapa.items():
                if dobre == "":
                    continue
                self.assertIn(dobre, kanon, f"alias {rodzaj}/{zle!r} -> {dobre!r} poza słownikiem")


# ===========================================================================
class TestNormPlacowka(unittest.TestCase):
    """``norm_placowka`` — typ placówki (dziś NIE ISTNIEJE u klienta jako pole)."""

    def test_typy_dozwolone(self):
        for v in ("SP 1", "PM 5", "MDK", "cokolwiek", ""):
            self.assertIn(P.norm_placowka(v)[0], P.TYPY_PLACOWKI)

    def test_szkoly_skrotowe(self):
        # [PH] Sacawa!F i Olszewska!F — ten sam obiekt zapisany trzema sposobami
        self.assertEqual(P.norm_placowka("MSP 1"), ("szkoła", "MSP 1"))
        self.assertEqual(P.norm_placowka("sp1"), ("szkoła", "SP 1"))
        self.assertEqual(P.norm_placowka("SP 1"), ("szkoła", "SP 1"))
        self.assertEqual(P.norm_placowka("SP17"), ("szkoła", "SP 17"))
        self.assertEqual(P.norm_placowka("Sp 21"), ("szkoła", "SP 21"))
        self.assertEqual(P.norm_placowka("MSP7"), ("szkoła", "MSP 7"))
        self.assertEqual(P.norm_placowka("ZSP 5"), ("szkoła", "ZSP 5"))
        self.assertEqual(P.norm_placowka("ZS 3 Rybnik"), ("szkoła", "ZS 3"))
        self.assertEqual(P.norm_placowka("sp42"), ("szkoła", "SP 42"))

    def test_normalizacja_scala_warianty(self):
        # to jest sens tej funkcji: 'sp1' i 'SP 1' to jedna placówka
        self.assertEqual(P.norm_placowka("sp1")[1], P.norm_placowka("SP 1")[1])
        self.assertEqual(P.norm_placowka("SP17")[1], P.norm_placowka("Sp 17")[1])

    def test_pelne_nazwy_rspo(self):
        # [PH] BAZA!F — 544 komórki pełnych nazw z rejestru
        self.assertEqual(
            P.norm_placowka("SZKOŁA PODSTAWOWA NR 24 IM. POWSTAŃCÓW ŚLĄSKICH"),
            ("szkoła", "SP 24"),
        )
        self.assertEqual(
            P.norm_placowka("SZKOŁA PODSTAWOWA NR 7 SPECJALNA"), ("szkoła", "SP 7")
        )
        self.assertEqual(
            P.norm_placowka("SZKOŁA PODSTAWOWA NR 10 IM. GUSTAWA MORCINKA"),
            ("szkoła", "SP 10"),
        )
        typ, nazwa = P.norm_placowka("SZKOŁA PODSTAWOWA DLA DOROSŁYCH")
        self.assertEqual(typ, "szkoła")
        self.assertEqual(nazwa, "SZKOŁA PODSTAWOWA DLA DOROSŁYCH")
        self.assertEqual(
            P.norm_placowka("NIEPUBLICZNA SZKOŁA PODSTAWOWA \"NASZA SZKOŁA\"")[0], "szkoła"
        )
        self.assertEqual(
            P.norm_placowka("OGÓLNOKSZTAŁCĄCA SZKOŁA MUZYCZNA I STOPNIA")[0], "szkoła"
        )
        self.assertEqual(P.norm_placowka("Niepubliczna SP MARANATHA")[0], "szkoła")

    def test_przedszkola(self):
        # [PH] BAZA!F zawiera 49 przedszkoli — a klient NIE MA pola typu
        # [DT] legenda klienta: "PP - prywatne przedszkole, PM - publiczne (miejskie)"
        self.assertEqual(P.norm_placowka("PM20"), ("przedszkole", "PM 20"))
        self.assertEqual(P.norm_placowka("PM 21"), ("przedszkole", "PM 21"))
        self.assertEqual(P.norm_placowka("PM5 Sosnowiec"), ("przedszkole", "PM 5"))
        self.assertEqual(
            P.norm_placowka("PP Mundo Marino Prywatne Katowice")[0], "przedszkole"
        )
        self.assertEqual(
            P.norm_placowka("PRZEDSZKOLE MIEJSKIE NR 5"), ("przedszkole", "PM 5")
        )
        self.assertEqual(
            P.norm_placowka("PRZEDSZKOLE MIEJSKIE NR 11 W DĄBROWIE GÓRNICZEJ"),
            ("przedszkole", "PM 11"),
        )
        self.assertEqual(
            P.norm_placowka("NIEPUBLICZNE PRZEDSZKOLE SŁONECZKO")[0], "przedszkole"
        )

    def test_regresja_przedszkole_nie_jest_szkola(self):
        # słowo "PRZEDSZKOLE" zawiera w sobie "SZKOL" — to był realny bug
        self.assertEqual(P.norm_placowka("PRZEDSZKOLE NR 30")[0], "przedszkole")

    def test_zespol_szkolno_przedszkolny_to_szkola(self):
        # świadoma decyzja: w ZSP klient prowadzi DT dla klas 1-4
        self.assertEqual(P.norm_placowka("ZESPÓŁ SZKOLNO-PRZEDSZKOLNY NR 1")[0], "szkoła")
        self.assertEqual(P.norm_placowka("ZSP 5")[0], "szkoła")

    def test_instytucje_kultury(self):
        # notatki ze spotkania 24.07: RSPO ma dać też instytucje kultury
        for v in ("MDK Knurów", "MŁODZIEŻOWY DOM KULTURY", "Dom Kultury Chorzów",
                  "Miejska Biblioteka Publiczna", "Centrum Kultury Katowice"):
            self.assertEqual(
                P.norm_placowka(v)[0], "instytucja kultury", f"norm_placowka({v!r})"
            )

    def test_nieznany_typ(self):
        # [PH] Sacawa!F — realne wartości bez żadnego kodu typu
        for v in ("Książenice", "EduHub", "korczakowska", "Piasek"):
            self.assertEqual(P.norm_placowka(v)[0], "nieznany", f"norm_placowka({v!r})")
        self.assertEqual(P.norm_placowka(""), ("nieznany", ""))
        self.assertEqual(P.norm_placowka(None), ("nieznany", ""))


# ===========================================================================
class TestBledyFormul(unittest.TestCase):
    """Błąd formuły i formuła NIE SĄ danymi — jedno zabezpieczenie dla wszystkich
    parserów. Realnie ``Zbiorczy`` i ``Niewykorzystane rekordy`` zawierają
    ``#N/A`` w 3 + 1 wierszach (arkusze liczone ``VSTACK``/``QUERY``
    przeniesionym z Google Sheets)."""

    BLEDY = ["#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NUM!"]

    def test_bledy_traktowane_jako_brak(self):
        for e in self.BLEDY:
            with self.subTest(e=e):
                self.assertIsNone(P.parse_date(e))
                self.assertIsNone(P.parse_time(e))
                self.assertIsNone(P.parse_int_loose(e))
                self.assertIsNone(P.parse_phone(e))
                self.assertEqual(P.parse_dni_tygodnia(e), [])
                self.assertEqual(P.parse_time_range(e), (None, None))
                self.assertIsNone(P.norm_slownik(e, "handlowiec"))
                self.assertIsNone(P.norm_slownik(e, "tak_nie"))
                self.assertEqual(P.norm_placowka(e), ("nieznany", ""))
                self.assertEqual(P.strip_prefix(e), (None, ""))

    def test_formula_zwracajaca_tekst_jest_rozwijana(self):
        # [PH] BAZA!I4 — 535 komórek tej postaci
        self.assertEqual(P.parse_phone('="601290441"'), "601 290 441")
        self.assertEqual(P.norm_slownik('="01. Sacawa"', "handlowiec"), "01. Sacawa")

    def test_formula_google_sheets_oddaje_ostatnia_wartosc(self):
        # [PH] Zbiorczy!I i "Szkoły z DT"!I przy data_only=False — 14 komórek.
        # Ostatni literał w IFERROR to ostatnio policzona wartość.
        self.assertEqual(
            P.parse_phone(
                '=IFERROR(__xludf.DUMMYFUNCTION("""COMPUTED_VALUE"""),"32 235 27 15")'
            ),
            "32 235 27 15",
        )
        self.assertEqual(
            P.norm_slownik(
                '=IFERROR(__xludf.DUMMYFUNCTION("""VSTACK( FILTER(Sacawa!A2:Y1075))"""),'
                '"01. Sacawa")',
                "handlowiec",
            ),
            "01. Sacawa",
        )
        # gdy wartością awaryjną jest błąd, nadal nie ma danych
        f = '=IFERROR(__xludf.DUMMYFUNCTION("""COMPUTED_VALUE"""),"#N/A")'
        self.assertIsNone(P.parse_phone(f))
        self.assertIsNone(P.norm_slownik(f, "handlowiec"))

    def test_inna_formula_to_brak_danych(self):
        # [PH] Kalendarz WRZESIEŃ DT!B2 i B3 — zwykłe formuły arkusza
        self.assertIsNone(P.parse_date("=B2+1"))
        self.assertIsNone(P.parse_int_loose("=M2&\"-\"&O2"))
        kal = ('=IFERROR(XLOOKUP(TEXT(B$2, "dd.mm.yyyy") & "||" & $A3, '
               'Zbiorczy!$AI$2:$AI$1100, Zbiorczy!$AG$2:$AG$1100), "")')
        self.assertIsNone(P.parse_date(kal))
        self.assertIsNone(P.norm_slownik(kal, "trener"))
        self.assertEqual(P.norm_placowka(kal), ("nieznany", ""))


class TestOdpornoscOgolna(unittest.TestCase):
    """Żadna funkcja nie może rzucić wyjątku na dowolnym śmieciu."""

    SMIECI = [
        None, "", "   ", 0, 1, -1, 0.0, 1e9, True, False,
        "\n\n", "\t", "???", "-", "x" * 500, "😀", "NULL", "#N/A", "#REF!",
        dt.date(2026, 1, 1), dt.datetime(2026, 1, 1, 12, 0), dt.time(0, 0),
        dt.timedelta(0), dt.timedelta(days=400), [], {}, (),
    ]

    def test_nic_nie_wybucha(self):
        for v in self.SMIECI:
            with self.subTest(v=repr(v)):
                P.parse_date(v)
                P.parse_time(v)
                P.parse_time_range(v)
                P.parse_time_range(v, ze_reszta=True)
                P.parse_time_ranges(v)
                P.parse_int_loose(v)
                P.parse_phone(v)
                P.parse_dni_tygodnia(v)
                P.strip_prefix(v)
                P.norm_placowka(v)
                for rodzaj in P.RODZAJE_SLOWNIKOW:
                    P.norm_slownik(v, rodzaj)

    def test_typy_zwracane(self):
        self.assertIsInstance(P.parse_date("2026-09-10"), dt.date)
        self.assertIsInstance(P.parse_time("8:00"), dt.time)
        self.assertIsInstance(P.parse_int_loose("8 klas"), int)
        self.assertIsInstance(P.parse_phone("32 235 27 15"), str)
        self.assertIsInstance(P.parse_dni_tygodnia("środa"), list)
        self.assertIsInstance(P.strip_prefix("01. X"), tuple)
        self.assertIsInstance(P.norm_placowka("SP 1"), tuple)
        self.assertEqual(len(P.parse_time_range("8:00-9:00")), 2)
        self.assertEqual(len(P.parse_time_range("8:00-9:00", ze_reszta=True)), 3)


# ===========================================================================
def _dodaj_doctesty(suite):
    import doctest

    suite.addTests(doctest.DocTestSuite(P))
    return suite


def load_tests(loader, tests, ignore):  # noqa: D401  (protokół unittest)
    """Dokłada doctesty z ``parsers`` do zestawu testów."""
    return _dodaj_doctesty(tests)


if __name__ == "__main__":
    unittest.main(verbosity=2)
