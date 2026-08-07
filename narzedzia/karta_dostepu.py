# -*- coding: utf-8 -*-
"""
Karta dostępu w PDF — kto ma jakie konto, jaki PIN i co może zrobić.

Do wydrukowania i wręczenia zespołowi przy starcie oraz do rozmowy o rolach.

DLACZEGO NARZĘDZIE NADAJE PIN-Y, A NIE TYLKO JE WYPISUJE
PIN-u nie da się odczytać z bazy — leży tam wyłącznie skrót PBKDF2 z solą.
To celowe: gdyby dało się podejrzeć cudzy PIN, ślad „kto zmienił lead" nie
znaczyłby nic. Kompletna karta wymaga więc NADANIA PIN-ów na nowo; narzędzie
robi jedno i drugie w tym samym ruchu, żeby papier i baza nigdy się nie rozjechały.

    python narzedzia/karta_dostepu.py                      # profil test, nowe PIN-y wszystkim
    python narzedzia/karta_dostepu.py --profil prod
    python narzedzia/karta_dostepu.py --tylko-brakujace    # nie rusza tych, którzy już mają
    python narzedzia/karta_dostepu.py --osoba "01. Sacawa" # jedna kartka dla jednej osoby

Wynik ląduje w `dostepy/` — katalogu wpisanym do .gitignore. To jest plik
z hasłami do systemu z danymi osobowymi dyrektorów szkół: nie wchodzi do
repozytorium, nie idzie mailem, drukuje się i przekazuje z ręki do ręki.
"""
import argparse
import datetime as dt
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

KATALOG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WYJSCIE = os.path.join(KATALOG, "dostepy")
sys.path.insert(0, KATALOG)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, PageBreak)
except ImportError:
    sys.exit("Brakuje biblioteki reportlab. Zainstaluj: python -m pip install reportlab")

# Barwy z logo SILESIA 3D — te same, co w aplikacji, żeby papier i ekran
# wyglądały jak jedna rzecz.
GRANAT = colors.HexColor("#0f2a33")
CYAN = colors.HexColor("#1c9dc4")
CYAN_T = colors.HexColor("#0b6f93")
CYAN_L = colors.HexColor("#e8f7fd")
CZERWIEN = colors.HexColor("#b82812")
CZERWIEN_L = colors.HexColor("#fdece9")
BURSZTYN_L = colors.HexColor("#fff8e8")
BURSZTYN = colors.HexColor("#d68a29")
SZARY = colors.HexColor("#667085")
LINIA = colors.HexColor("#e3e9ee")


def _czcionki():
    """Ogonki muszą działać — bez własnego kroju reportlab wypisze „Ma?olepsza”."""
    kandydaci = [
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        (r"C:\Windows\Fonts\DejaVuSans.ttf", r"C:\Windows\Fonts\DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for zwykly, gruby in kandydaci:
        if os.path.exists(zwykly) and os.path.exists(gruby):
            pdfmetrics.registerFont(TTFont("PL", zwykly))
            pdfmetrics.registerFont(TTFont("PL-B", gruby))
            return "PL", "PL-B"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_B = _czcionki()

# PIN musi być czytelny przy przepisywaniu — monospace, żeby 0 i O oraz 1 i l
# dało się rozróżnić.
MONO = "Courier-Bold"


def styl(nazwa, rozmiar, **kw):
    kw.setdefault("fontName", FONT)
    kw.setdefault("leading", rozmiar * 1.45)
    return ParagraphStyle(nazwa, fontSize=rozmiar, **kw)


S_TYTUL = styl("t", 20, fontName=FONT_B, textColor=GRANAT, spaceAfter=2)
S_PODTYTUL = styl("pt", 10.5, textColor=SZARY, spaceAfter=14)
S_NAGL = styl("n", 13, fontName=FONT_B, textColor=CYAN_T, spaceBefore=14, spaceAfter=6)
S_TEKST = styl("z", 9.5, textColor=colors.HexColor("#1f2937"))
S_MALY = styl("m", 8.5, textColor=SZARY)
S_KOM = styl("k", 9.5, textColor=colors.HexColor("#374151"), leading=14)


def _stopka(canvas, doc, profil, kiedy):
    canvas.saveState()
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(SZARY)
    canvas.drawString(18 * mm, 12 * mm,
                      "System Leadów v5 · profil %s · wygenerowano %s" % (profil, kiedy))
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, "strona %d" % doc.page)
    canvas.setStrokeColor(LINIA)
    canvas.line(18 * mm, 16 * mm, A4[0] - 18 * mm, 16 * mm)
    canvas.restoreState()


def _ramka(tresc, tlo, obwodka, szer=None):
    """Kolorowy blok z tekstem — ostrzeżenia i uwagi."""
    t = Table([[Paragraph(tresc, S_KOM)]], colWidths=[szer or 174 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tlo),
        ("BOX", (0, 0), (-1, -1), 0.9, obwodka),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


UPRAWNIENIA = [
    ("Formularz ustaleń (v1 i v2)", True, True),
    ("Moje szkoły / lista leadów", "tylko swoje\n(da się zdjąć filtr)", "wszystkich"),
    ("Karta szkoły — edycja, spotkania", True, True),
    ("Plan tygodnia", True, True),
    ("Kalendarz DT", True, True),
    ("Dostępność trenerów", "podgląd", "edycja"),
    ("Pulpit — liczby, kolizje, terminy", False, True),
    ("Baza placówek — rozdawanie szkół", False, True),
    ("Zbiorczy (umowy, dokumenty)", False, True),
    ("Niewykorzystane rekordy", False, True),
    ("Rejony trenerów", False, True),
    ("Słowniki i aliasy", False, True),
    ("Import z Excela", False, True),
    ("Eksport do Excela", False, True),
    ("Konta i PIN-y", False, True),
    ("Ręczny zwrot szkół do puli", False, True),
]


def _tabela_uprawnien():
    def znak(v):
        if v is True:
            return Paragraph('<font color="#1d9350"><b>TAK</b></font>', S_TEKST)
        if v is False:
            return Paragraph('<font color="#b82812">nie</font>', S_TEKST)
        return Paragraph('<font color="#8a6516">%s</font>' % v.replace("\n", "<br/>"), S_MALY)

    dane = [[Paragraph("<b>Co można zrobić</b>", S_TEKST),
             Paragraph("<b>Handlowiec</b>", S_TEKST),
             Paragraph("<b>Koordynator</b>", S_TEKST)]]
    for nazwa, h, k in UPRAWNIENIA:
        dane.append([Paragraph(nazwa, S_TEKST), znak(h), znak(k)])

    t = Table(dane, colWidths=[104 * mm, 35 * mm, 35 * mm], repeatRows=1)
    styl_t = [
        ("BACKGROUND", (0, 0), (-1, 0), GRANAT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINIA),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(dane)):
        if i % 2 == 0:
            styl_t.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7fafc")))
    t.setStyle(TableStyle(styl_t))
    return t


def _tabela_kont(konta):
    dane = [[Paragraph("<b>Osoba</b>", S_TEKST),
             Paragraph("<b>Rola</b>", S_TEKST),
             Paragraph("<b>PIN</b>", S_TEKST)]]
    for k in konta:
        pin = k.get("pin")
        dane.append([
            Paragraph(k["osoba"], S_TEKST),
            Paragraph("koordynator" if k["rola"] == "koordynator" else "handlowiec", S_TEKST),
            Paragraph('<font face="%s" size="14">%s</font>' % (MONO, pin) if pin
                      else '<font color="#667085">bez zmian</font>', S_TEKST),
        ])
    t = Table(dane, colWidths=[94 * mm, 40 * mm, 40 * mm], repeatRows=1)
    styl_t = [
        ("BACKGROUND", (0, 0), (-1, 0), GRANAT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINIA),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, k in enumerate(konta, start=1):
        if k["rola"] == "koordynator":
            styl_t.append(("BACKGROUND", (0, i), (-1, i), CYAN_L))
        elif i % 2 == 0:
            styl_t.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7fafc")))
    t.setStyle(TableStyle(styl_t))
    return t


def _kartka_osobista(k, adres):
    """Pasek do wycięcia — jedna osoba, jej PIN i adres. Do wręczenia z ręki."""
    tresc = [
        [Paragraph("<b>%s</b>" % k["osoba"], styl("x", 13, fontName=FONT_B,
                                                  textColor=GRANAT)),
         Paragraph('<font face="%s" size="22" color="#0f2a33">%s</font>'
                   % (MONO, k.get("pin") or "—"), S_TEKST)],
        [Paragraph("rola: %s<br/>adres: <b>%s</b>"
                   % ("koordynator" if k["rola"] == "koordynator" else "handlowiec", adres),
                   S_MALY),
         Paragraph("Twój PIN", S_MALY)],
    ]
    t = Table(tresc, colWidths=[118 * mm, 56 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, LINIA),
        ("LINEBELOW", (0, 0), (-1, 0), 0.3, LINIA),
        ("BACKGROUND", (1, 0), (1, -1), CYAN_L),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def buduj(sciezka, konta, profil, adres, ile_zmienionych):
    kiedy = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    doc = SimpleDocTemplate(
        sciezka, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm,
        title="Karta dostępu — System Leadów v5", author="SILESIA 3D")

    el = []
    el.append(Paragraph("Karta dostępu — System Leadów", S_TYTUL))
    el.append(Paragraph(
        "Profil bazy: <b>%s</b> &nbsp;·&nbsp; adres: <b>%s</b> &nbsp;·&nbsp; %s"
        % (profil.upper(), adres, kiedy), S_PODTYTUL))

    el.append(_ramka(
        "<b>Ten dokument zawiera PIN-y do systemu z danymi osobowymi.</b><br/>"
        "Nie wysyłaj go mailem ani komunikatorem. Wydrukuj, rozetnij dolne paski "
        "i wręcz każdemu jego własny, a plik skasuj. PIN-u nie da się odczytać "
        "z systemu — jeśli ktoś zgubi swój, koordynator nadaje nowy w panelu „Konta”.",
        CZERWIEN_L, CZERWIEN))

    if ile_zmienionych:
        el.append(Spacer(1, 8))
        el.append(_ramka(
            "Nadano <b>%d</b> nowych PIN-ów. Poprzednie przestały działać "
            "w chwili wygenerowania tego pliku." % ile_zmienionych,
            BURSZTYN_L, BURSZTYN))

    el.append(Paragraph("Konta i PIN-y", S_NAGL))
    el.append(_tabela_kont(konta))

    el.append(Paragraph("Jak się zalogować", S_NAGL))
    el.append(Paragraph(
        "1. Wejdź na <b>%s</b> — telefonem, tabletem albo komputerem.<br/>"
        "2. Wybierz swoje nazwisko z listy.<br/>"
        "3. Wystukaj cztery cyfry PIN-u — logowanie odpali się samo.<br/>"
        "4. Urządzenie zapamięta Cię na <b>30 dni</b>, więc w terenie logujesz się raz."
        % adres, S_KOM))
    el.append(Spacer(1, 8))
    el.append(_ramka(
        "Po <b>5 błędnych próbach</b> konto blokuje się samo. Odblokowuje je "
        "koordynator, nadając nowy PIN — trwa to kilkanaście sekund. "
        "Nie da się „odzyskać” starego PIN-u, bo system go nie przechowuje.",
        BURSZTYN_L, BURSZTYN))

    el.append(PageBreak())

    el.append(Paragraph("Co może kto", S_TYTUL))
    el.append(Paragraph("Dwie role — reszta wynika z nich automatycznie.", S_PODTYTUL))
    el.append(_tabela_uprawnien())

    el.append(Paragraph("Dlaczego handlowiec nie widzi wszystkiego", S_NAGL))
    el.append(Paragraph(
        "Nie chodzi o zaufanie, tylko o to, żeby jednym kliknięciem nie dało się "
        "naruszyć pracy całego zespołu. Import z Excela w trybie „zastąp” potrafi "
        "wyczyścić bazę, a zmiana słownika przestawia listy na wszystkich ekranach "
        "naraz. Te rzeczy robi jedna osoba, świadomie.<br/><br/>"
        "<b>Lista leadów działa inaczej:</b> handlowiec domyślnie widzi swoje szkoły, "
        "ale filtr jest jawny i można go zdjąć jednym kliknięciem — po przejściu na "
        "inny ekran wraca sam. Nikt nikomu nic nie ukrywa; chodzi o to, żeby "
        "po wejściu od razu widzieć swoją robotę, a nie 550 cudzych wierszy.", S_KOM))

    el.append(Paragraph("Co system zapisuje", S_NAGL))
    el.append(Paragraph(
        "Każda zmiana leada trafia do historii razem z nazwiskiem osoby, która ją "
        "wprowadziła, i godziną. To jest podstawa odpowiedzi na pytanie „czy ktoś "
        "ruszył ten lead przed terminem”. Dlatego <b>nie pożyczamy sobie PIN-ów</b> — "
        "wpis podpisany cudzym nazwiskiem psuje jedyny ślad, jaki mamy.", S_KOM))

    el.append(PageBreak())

    el.append(Paragraph("Paski do rozcięcia", S_TYTUL))
    el.append(Paragraph(
        "Rozetnij wzdłuż ramek i wręcz każdemu jego własny pasek. "
        "Reszty dokumentu nie zostawiaj na biurku.", S_PODTYTUL))
    for k in konta:
        el.append(_kartka_osobista(k, adres))
        el.append(Spacer(1, 5))

    stopka = lambda c, d: _stopka(c, d, profil, kiedy)
    doc.build(el, onFirstPage=stopka, onLaterPages=stopka)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profil", default="test", choices=["prod", "test", "pusta"])
    ap.add_argument("--adres", default=os.environ.get("ADRES_APLIKACJI",
                                                      "http://192.168.13.192:5301"))
    ap.add_argument("--osoba", action="append",
                    help="tylko te osoby (można podać kilka razy)")
    ap.add_argument("--tylko-brakujace", dest="tylko_brakujace", action="store_true",
                    help="nie ruszaj PIN-ów tych, którzy już je mają")
    args = ap.parse_args()

    os.environ["PROFIL"] = args.profil
    import db                                    # noqa: E402 — po ustawieniu PROFIL
    import uzytkownicy as uz                     # noqa: E402

    conn = db.get_conn()
    uz.init(conn)
    konta = uz.lista(conn)
    if args.osoba:
        chciane = set(args.osoba)
        konta = [k for k in konta if k["osoba"] in chciane]
        brak = chciane - {k["osoba"] for k in konta}
        if brak:
            conn.close()
            sys.exit("Nie ma takich kont: %s" % ", ".join(sorted(brak)))
    if not konta:
        conn.close()
        sys.exit("Profil %r nie ma jeszcze żadnych kont. Uruchom aplikację raz, "
                 "żeby się utworzyły." % args.profil)

    zmienione = 0
    for k in konta:
        if args.tylko_brakujace and k["ma_pin"]:
            k["pin"] = None                      # zostaje stary, nie znamy go
            continue
        k["pin"] = uz.losowy_pin()
        uz.ustaw_pin(conn, k["osoba"], k["pin"])
        zmienione += 1
    conn.close()

    os.makedirs(WYJSCIE, exist_ok=True)
    nazwa = "karta_dostepu_%s_%s.pdf" % (args.profil,
                                         dt.datetime.now().strftime("%Y-%m-%d_%H%M"))
    sciezka = os.path.join(WYJSCIE, nazwa)
    buduj(sciezka, konta, args.profil, args.adres, zmienione)

    print("PDF: %s" % sciezka)
    print("kont: %d | nowych PIN-ów: %d" % (len(konta), zmienione))
    print()
    print("%-26s %-13s %s" % ("OSOBA", "ROLA", "PIN"))
    print("-" * 52)
    for k in konta:
        print("%-26s %-13s %s" % (k["osoba"], k["rola"], k.get("pin") or "(bez zmian)"))
    print()
    print("UWAGA: plik zawiera PIN-y. Katalog `dostepy/` jest poza gitem —")
    print("wydrukuj, rozetnij paski, rozdaj i skasuj plik.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
