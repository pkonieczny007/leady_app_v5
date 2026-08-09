# Baza szkół z RSPO — propozycja rozwiązania

**Data:** 08.08.2026. **Dla kogo:** Wojtek (decyzja), Kasia (rejony), zespół.
**Cel:** pełna, aktualna baza placówek oświatowych w rejonach działania, która
sama się odświeża, a zmiana nazwy szkoły w rejestrze nie rozwala naszych danych.

---

## 1. Co już mamy w aplikacji (stan faktyczny, nie plan)

Sprawdzone w kodzie 08.08 — fundament pod RSPO **już stoi**:

| Element | Gdzie | Co robi |
|---|---|---|
| Kolumna `rspo` na placówce | `db.py` (unikalny indeks) | numer RSPO to klucz rekordu |
| Import pliku RSPO | `importer.py → importuj_rspo()` | wgrywa wykaz placówek z xlsx/csv (nazwa, miejscowość, adres, telefon, mail, nr RSPO) |
| Dopasowanie po numerze RSPO | `importer.py → _klucz_placowki()` | gdy numer jest, szkoła łączy się po numerze — **zmiana nazwy tylko aktualizuje pole**, leady i historia zostają przy tej samej placówce |
| Dopasowanie awaryjne | tamże | bez numeru: znormalizowana nazwa krótka + miejscowość (parser zna pełne nazwy RSPO, skróty „MSP 1", „sp1" itd.) |
| Tryby importu | ekran `↑ Import` | `dopisz` (bezpieczny) / `replace`; przed importem automatyczna kopia bazy |

Czyli: **nie budujemy nowego modułu — dokładamy źródło danych i dwie drobne
rzeczy do interfejsu.**

## 2. Skąd brać dane — trzy ścieżki, sprawdzone 08–09.08

| Ścieżka | Stan | Werdykt |
|---|---|---|
| **Plik CSV z `rspo.gov.pl`** | mamy go: `rspo_2026_08_08.csv`, **56 190 placówek z całej Polski**, w tym **6116 czynnych w śląskim**. Kolumny: numer RSPO, typ, nazwa, województwo/powiat/gmina/miejscowość, ulica, telefon, e-mail, dyrektor, liczba uczniów | **ŹRÓDŁO PODSTAWOWE** — obsłużone narzędziem `narzedzia/rspo.py` (niżej) |
| **Oficjalne API** `api.rspo.gov.pl` | działa, ale wymaga **wniosku**: e-mail na `rspo@cie.gov.pl` (dane firmy, NIP/REGON, opis wykorzystania), rozpatrzenie **do 14 dni** | **dodatek na później** — decyzja z 09.08: nie blokujemy wtorku; wniosek złożymy, ale plan działa bez niego |
| Otwarte dane `dane.gov.pl` (zbiór 839) | wykazy z lat 2013–2017 | martwe, odpada |

**Jak było do tej pory:** Kasia pobierała CSV ze strony i **ręcznie przepisywała**
interesujące szkoły do arkusza. To ta praca znika.

## 3. Co już działa — `narzedzia/rspo.py` (zbudowane 09.08)

Trzy komendy. Nic nie zapisuje do bazy samo z siebie — wynikiem są pliki
do obejrzenia i zaimportowania świadomym ruchem.

```powershell
# 1. Podgląd: ile placówek wchodzi z naszych rejonów (nic nie zapisuje)
python narzedzia/rspo.py rejony --csv "rspo_2026_08_08.csv"

# 2. Wykaz do importu — plik gotowy pod „↑ Import → źródło RSPO”
python narzedzia/rspo.py wykaz  --csv "rspo_2026_08_08.csv" --do wykaz.xlsx

# 3. Raport: które nasze placówki to które rekordy RSPO
python narzedzia/rspo.py dopasuj --profil test --csv "rspo_2026_08_08.csv" --do dopasowanie.xlsx
```

**Wynik na realnych danych (09.08):**

| | liczba |
|---|---|
| placówki w województwie śląskim (czynne) | 6116 |
| w rejonach z listy Kasi | 2552 |
| **w wykazie** (podstawówki, przedszkola, punkty przedszkolne, zespoły, MDK) | **1573** |
| odrzucone przez typ (licea, technika, poradnie, bursy…) | 979 |

Rejony i typy placówek to dwie listy na górze `narzedzia/rspo.py` — wejście
w nowy teren to dopisanie jednej linijki, nie zmiana logiki.

## 3b. Nazwy szkół — problem zgłoszony przez Kasię, zmierzony 09.08

Kasia: *„w naszej bazie ogólnej jest jak w rejestrze, a gotowe leady, które mają
już DT umówione, mają inne nazwy szkół"*. Sprawdziliśmy na ich pliku — tak jest:
w zakładkach handlowców szkoły figurują jako `MSP 1`, `sp32`, `Sp 13`,
`ZS 3 Rybnik`, a w zakładce z bazą pod pełnymi nazwami z rejestru.

**Skala (profil `test`, 545 placówek):**

| Dopasowanie do rejestru | liczba |
|---|---|
| **pewne** (nazwa i miejscowość zgadzają się po normalizacji) | 466 |
| **po numerze** (np. `MSP 6` + Knurów → MIEJSKA SZKOŁA PODSTAWOWA NR 6, jeden kandydat) | 10 |
| **niepewne** (kilku kandydatów — wybiera człowiek) | 0 |
| **brak** (nazwy potoczne: „Piasek”, „Książenice”, „EduHub”, „29.0”) | 69 |

**Odkrycie przy okazji: 18 rekordów to 9 szkół wpisanych dwa razy** — raz pełną
nazwą z rejestru, raz skrótem handlowca (np. `MSP 1` obok `MIEJSKA SZKOŁA
PODSTAWOWA NR 1 IM. POWSTAŃCÓW ŚLĄSKICH W KNUROWIE`, oba w Knurowie). Widać to
dopiero, gdy oba rekordy wskażą ten sam numer RSPO. Raport oznacza takie pary
kolumną „Zdublowane?" i sortuje je na górę.

**Scalenia nie robi automat** — na jednym z pary wisi już historia kontaktów
i umówione DT, a sklejenie w złą stronę byłoby nieodwracalne po tygodniu pracy
handlowców. Decyzja Kasi przy tych 9 parach zajmie 10 minut.

### Rytm aktualizacji — raz na miesiąc, ręką koordynatora

Decyzja z 09.08: **koordynator/admin raz na miesiąc pobiera CSV ze strony
i przepuszcza przez `rspo.py`, potem import w trybie `dopisz`.** Dopasowanie po
numerze RSPO sprawia, że ponowny import **niczego nie dubluje** — aktualizuje
istniejące wpisy i dokłada nowe szkoły. To nie jest prowizorka w oczekiwaniu na
API: to ten sam tor danych, tylko z człowiekiem zamiast klucza dostępu.
Szkoły nie zmieniają się z dnia na dzień, więc miesiąc jest w sam raz.

### Mikroaplikacja / moduł „szkoły RSPO" — do decyzji we wtorek

`narzedzia/rspo.py` jest już zalążkiem takiej mikroaplikacji (wybór rejonów,
filtr typów, wykaz, raport dopasowań) — tyle że z linii poleceń, czyli dla
mnie, nie dla Kasi. Dwie drogi rozwoju:

| | mikroaplikacja obok | moduł w aplikacji |
|---|---|---|
| Kto uruchamia | Przemek (linia poleceń) albo osobne okno | koordynator, z menu |
| Przenoszenie danych | plik między programami | brak — jedna baza |
| Flaga „objęta działaniem" | trzeba by dublować | ten sam mechanizm co filtry |
| Koszt | zerowy (już jest) | ~1 dzień |

**Rekomendacja:** zostawić `rspo.py` jako narzędzie na wtorek, a po wtorku
przenieść do aplikacji jako ekran koordynatora — bo wtedy Kasia robi wszystko
sama, bez pliku wędrującego między programami, i widzi raport zmian w tym
samym miejscu, w którym rozdaje szkoły.

### Etap B — automat na API (po otrzymaniu dostępu, priorytet PO wtorku)

1. `narzedzia/rspo.py` — pobiera z API placówki wskazanych gmin/powiatów
   (konfiguracja = lista Kasi w jednym miejscu).
2. Przycisk **„Odśwież z RSPO"** w panelu koordynatora — nie cron: automat na
   serwerze umiera po cichu, przycisk z datą ostatniego odświeżenia widać
   (ta sama zasada, co przy auto-zwrocie leadów).
3. Po odświeżeniu **raport**: N nowych placówek, M zmienionych nazw/adresów,
   K zniknęło z rejestru. Zniknięte **oznaczamy, nie kasujemy** — mogły się
   przekształcić, a wiszą na nich leady i historia.
4. Flaga **„objęta działaniem"** na placówce — zaznacza koordynator. Formularz
   i `/baza` domyślnie pokazują objęte; pełna baza dostępna po zdjęciu filtra
   (dokładnie ten sam wzorzec, co filtr „moje szkoły" u handlowca).

## 4. Odpowiedź na „chcę mieć całą bazę" (Wojtek)

Liczby są znane, więc to nie jest spór o wyobrażenia:

| Zakres | Placówek | Nasza ocena |
|---|---|---|
| rejony z listy Kasi, typy „nasze" | **1573** | **rekomendacja** — tyle realnie obdzwonią |
| rejony z listy Kasi, wszystkie typy | 2552 | dokłada licea, technika, poradnie, bursy |
| całe województwo śląskie, wszystkie typy | 6116 | „cała baza" w sensie Wojtka — technicznie bez problemu |
| cała Polska | 56 190 | bez sensu: firma działa na Śląsku |

Wszystkie trzy pierwsze warianty SQLite udźwignie bez mrugnięcia (mówimy
o tysiącach wierszy, nie milionach) — to jest decyzja **biznesowa, nie
techniczna**. Jedyny realny koszt większego zakresu to dłuższe listy
podpowiedzi u handlowca w terenie i „ile z tego jest naprawdę nasze".
Dlatego proponujemy trzymać całe śląskie w bazie, ale z **flagą „objęta
działaniem"** (pkt 3, etap B): Wojtek ma pełną bazę, a Kasia i handlowcy
domyślnie widzą 1573 placówki, po których faktycznie jeżdżą.
Przełącznik jednym kliknięciem, ten sam wzorzec co filtr „moje szkoły".

Wejście w nowy rejon = dopisanie gminy do listy w `narzedzia/rspo.py`
i ponowny import. Bez zmian w kodzie.

## 5. Dlaczego zmiana nazwy szkoły niczego nie zepsuje

Tożsamość placówki niesie **numer RSPO**, nie nazwa. Rejestr zmienia nazwę
(„SP nr 12" → „SP nr 12 im. Jana Pawła II") → odświeżenie podmienia tylko pole
nazwy w tym samym rekordzie. Leady, notatki, historia kontaktów, przydział
handlowca — wszystko wisi na `placowka_id`, którego nikt nie dotyka. Duplikat
nie może powstać, bo indeks na `rspo` jest unikalny.

## 6. Co trzeba zrobić i kiedy

| Kiedy | Co | Kto | Stan |
|---|---|---|---|
| nd 09.08 | `narzedzia/rspo.py`: rejony / wykaz / dopasuj | Przemek | **✅** |
| nd 09.08 | próba na realnych danych: 1573 do wykazu, 476/545 dopasowane, 9 par duplikatów | Przemek | **✅** |
| wtorek | **pokazać Kasi raport dopasowania** — 9 par do scalenia i 69 nazw potocznych | Przemek + Kasia | ⬜ |
| wtorek | decyzja Wojtka o zakresie (1573 / 2552 / 6116) — pkt 4 | Wojtek | ⬜ |
| po wtorku | import wykazu do `prod` + flaga „objęta działaniem" | Przemek | ⬜ |
| po wtorku | wniosek o API (zegar 14 dni) — **nie blokuje niczego** | Przemek / biuro | ⬜ |
| po wtorku | przeniesienie `rspo.py` do aplikacji jako ekran koordynatora (~1 dzień) | Przemek | ⬜ |

## 7. Pytania otwarte

1. **Wojtek:** który zakres — 1573 (nasze rejony i typy), 2552 (rejony,
   wszystkie typy) czy 6116 (całe śląskie)? Rekomendacja: 6116 w bazie
   + flaga „objęta działaniem" pokazująca domyślnie 1573.
2. **Kasia:** 9 par zdublowanych szkół — który rekord zostaje? (ten z historią
   DT, czy ten z pełną nazwą? my proponujemy: zostaje rekord z historią,
   a nazwa i dane kontaktowe nadpisują się z rejestru)
3. **Kasia:** 69 placówek z nazwami potocznymi („Piasek", „Książenice",
   „EduHub", „Nasza Szkoła”) — czy dopisać im numery RSPO ręcznie, czy zostawić
   jako lokalne wpisy bez powiązania z rejestrem?
4. Czy „objęte działaniem" to też przedszkola i domy kultury, czy same szkoły?
   (dziś wykaz bierze podstawówki, przedszkola, punkty przedszkolne, zespoły i MDK)
