# -*- coding: utf-8 -*-
"""
Ikony PWA — kafelki na ekran początkowy telefonu, robione z `static/logo.png`.

    python narzedzia/ikony.py            # nadpisuje pliki w static/
    python narzedzia/ikony.py --podglad  # tylko pokazuje, co by zrobił

DLACZEGO TO JEST SKRYPT, A NIE KOD APLIKACJI
Wynikiem są cztery gotowe PNG-i wchodzące do repozytorium. Aplikacja nigdy ich
nie generuje, więc Pillow nie ma czego szukać w `requirements.txt` — dokładnie
ta sama umowa, co z `reportlab` w `karta_dostepu.py`: obraz dockera zostaje
lekki, a narzędzie odpalamy u siebie, kiedy zmieni się logo.
Instalacja u nas: `python -m pip install pillow` (samo `pip` na tej maszynie
celuje w innego Pythona).

DLACZEGO BIAŁY KAFELEK
Tukan z logo jest niemal czarny na przezroczystym tle. Na ekranie początkowym
telefonu tło ikony to tapeta użytkownika — na ciemnej tukan zniknąłby zupełnie,
a przezroczystość w `apple-touch-icon` iOS podkłada CZARNYM. Ten sam problem
rozwiązuje już `.brand-logo` w `style.css` (biały kafelek pod logo na granatowym
pasku) i robimy tu dosłownie to samo, żeby ikona i pasek górny wyglądały jak
jedna rzecz.

CZTERY PLIKI, BO KAŻDY MA INNĄ UMOWĘ Z SYSTEMEM
  ikona-192 / ikona-512      `purpose:any` — zaokrąglone rogi rysujemy sami,
                             bo Android pokazuje taki plik bez maski.
  ikona-maskowalna-512       `purpose:maskable` — system PRZYCINA go do swojego
                             kształtu (koło, kwadrat ze ściętymi rogami…).
                             Pewne jest tylko środkowe 80%, więc tło idzie na
                             cały kwadrat, a logo jest mniejsze. Bez tego
                             wariantu launcher Androida wcisnąłby nasz kafelek
                             w biały krążek — kafelek w kafelku.
  apple-touch-icon           Safari na iPhonie. Kwadrat BEZ przezroczystości
                             i BEZ własnych zaokrągleń: iOS zaokrągla sam,
                             a wszystko, co przezroczyste, zamienia w czerń.
                             180 px to rozmiar dla ekranów @3x (iPhone 11).
"""
import argparse
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Brak Pillow. Zainstaluj u siebie: python -m pip install pillow\n"
             "Do requirements.txt NIE dopisujemy — patrz nagłówek pliku.")

KATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
ZRODLO = os.path.join(KATALOG, "logo.png")

# Kolory wprost z `:root` w style.css — ikona ma być z tej samej palety co
# aplikacja, a nie „mniej więcej biała".
BIALY = (255, 255, 255, 255)          # --panel, czyli tło kafelka .brand-logo

# Promień rogów: .brand-logo ma 10 px przy szerokości 44 px ≈ 23% boku.
PROMIEN = 0.23


def _logo():
    """Logo w oryginale (100×83 px) — jedyne źródło, jakie mamy."""
    return Image.open(ZRODLO).convert("RGBA")


def _powieksz(logo, szer, wys):
    """
    Mamy tylko 100×83 px, a kafelek ma 512 — to ponad pięciokrotne powiększenie,
    przy którym sam LANCZOS rozmydla czarny kontur tukana w szarą mgiełkę.
    Dlatego dwa kroki: NEAREST do CAŁKOWITEJ wielokrotności co najmniej dwa razy
    większej od celu (kontur zostaje twardy, bez wymyślania pikseli, których
    w źródle nie ma), a potem LANCZOS w dół — to on robi wygładzenie schodków.
    Wersja jednokrokowa i wersja z wielokrotnością równą celowi były próbowane:
    pierwsza jest miękka, druga zostawia widoczne schodki na cyfrach „3D".
    """
    krok = max(2, min(-(-szer * 2 // logo.width), 16))
    posrednie = logo.resize((logo.width * krok, logo.height * krok), Image.NEAREST)
    return posrednie.resize((szer, wys), Image.LANCZOS)


def _kafelek(logo, bok, udzial, zaokraglij):
    """
    Biały kwadrat `bok`×`bok` z logo wpisanym w `udzial` szerokości, na środku.

    `zaokraglij=False` zostawia pełny kwadrat — tego chce iOS (patrz nagłówek).
    """
    tlo = Image.new("RGBA", (bok, bok), BIALY)

    szer = int(bok * udzial)
    wys = max(1, round(szer * logo.height / logo.width))
    tlo.alpha_composite(_powieksz(logo, szer, wys),
                        ((bok - szer) // 2, (bok - wys) // 2))

    if not zaokraglij:
        # Bez kanału alfa w ogóle — nie ma czego pomylić. iOS i maski Androida
        # traktują przezroczystość jako czerń, a plik jest przy okazji mniejszy.
        return tlo.convert("RGB")

    maska = Image.new("L", (bok, bok), 0)
    ImageDraw.Draw(maska).rounded_rectangle(
        (0, 0, bok - 1, bok - 1), radius=int(bok * PROMIEN), fill=255)
    tlo.putalpha(maska)
    return tlo


def main():
    p = argparse.ArgumentParser(description="Ikony PWA z static/logo.png")
    p.add_argument("--podglad", action="store_true",
                   help="wypisz plan, nie zapisuj plików")
    args = p.parse_args()

    logo = _logo()

    # Udziały dobrane pod to, co robi z plikiem system:
    #   0.72 — kafelek „any": margines na tyle duży, żeby dziób tukana nie
    #          wchodził w zaokrąglony róg
    #   0.66 — iOS zaokrągla mocniej niż my, więc logo o oczko mniejsze
    #   0.56 — maskowalna: logo musi zmieścić się w kole o średnicy 80% boku,
    #          a przy proporcji logo 100:83 wychodzi z tego najwyżej 0.61 boku;
    #          bierzemy z zapasem, bo przycięty dziób wygląda na błąd
    zadania = [
        ("ikona-192.png", 192, 0.72, True),
        ("ikona-512.png", 512, 0.72, True),
        ("ikona-maskowalna-512.png", 512, 0.56, False),
        ("apple-touch-icon.png", 180, 0.66, False),
    ]

    for nazwa, bok, udzial, zaokraglij in zadania:
        sciezka = os.path.normpath(os.path.join(KATALOG, nazwa))
        if args.podglad:
            print(f"[podgląd] {nazwa}: {bok}×{bok}, logo {int(udzial*100)}% boku, "
                  f"rogi {'zaokrąglone' if zaokraglij else 'pełny kwadrat'}")
            continue
        _kafelek(logo, bok, udzial, zaokraglij).save(sciezka, "PNG", optimize=True)
        print(f"[OK] {nazwa} — {bok}×{bok}")

    if not args.podglad:
        print("\nGotowe. Pliki są w static/ i wchodzą do repozytorium jako zasoby.")


if __name__ == "__main__":
    main()
