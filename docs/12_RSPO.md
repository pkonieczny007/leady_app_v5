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

## 2. Skąd brać dane — trzy ścieżki, sprawdzone 08.08

| Ścieżka | Stan | Werdykt |
|---|---|---|
| **Oficjalne API** `api.rspo.gov.pl` | działa, ale wymaga **wniosku o dostęp**: e-mail na `rspo@cie.gov.pl` („Wniosek o dostęp do API [nazwa podmiotu]": dane firmy, NIP/REGON, opis wykorzystania, szacowana liczba zapytań). Rozpatrzenie **do 14 dni**, potem dostajemy dane uwierzytelniające | **docelowe źródło** — wniosek wysłać od razu (SILESIA 3D), bo zegar 14 dni tyka |
| **Wyszukiwarka** `rspo.gov.pl` | publiczna; **eksport do CSV potwierdzony klikiem 08.08** (plik ze wszystkimi placówkami) | **pomost na już** — plik wchodzi w istniejący `importuj_rspo()` bez pisania czegokolwiek |
| Otwarte dane `dane.gov.pl` (zbiór 839) | wykazy z lat 2013–2017 | martwe, odpada |

## 3. Proponowane rozwiązanie — dwa etapy

### Etap A — działa od wtorku (zero nowego kodu)

1. Z wyszukiwarki RSPO pobieramy wykazy dla rejonów z listy Kasi (Rybnik, Żory,
   Knurów, Orzesze, pow. mikołowski, Tychy, Katowice, Jaworzno, Sosnowiec,
   Dąbrowa Górnicza, Będzin z powiatem, Świętochłowice, Ruda Śląska, Zabrze,
   Siemianowice, Chorzów, pow. pszczyński, Piekary Śląskie).
2. Plik(i) wgrywamy przez istniejący ekran `↑ Import` (źródło: RSPO, tryb `dopisz`).
3. Numery RSPO siedzą w bazie od pierwszego dnia — **wszystko, co potem
   zbudujemy, trafi na gotowe klucze.** To jest powód, żeby etap A zrobić teraz,
   a nie „kiedyś razem z API".

### Plan B — gdy API nie przyjdzie: ręczny CSV jako stały rytm

Decyzja z 08.08 (Przemek): jeśli wniosek o API utknie, koordynator **cyklicznie
pobiera CSV z wyszukiwarki i wgrywa przez ekran Import** (tryb `dopisz`,
dopasowanie po numerze RSPO robi resztę). To nie jest prowizorka — to ten sam
tor danych co przy API, tylko z człowiekiem zamiast klucza. Częstotliwość do
ustalenia we wtorek (szkoły nie zmieniają się z dnia na dzień; raz na miesiąc
prawdopodobnie wystarczy).

Pomysł do omówienia we wtorek: **mikroaplikacja / moduł „szkoły RSPO"** —
zarządzanie surowym wykazem (zaznaczanie rejonów, podgląd zmian) i tworzenie
specjalnego wykazu, który trafia do bazy aplikacji. Może żyć jako osobne
narzędzie w `narzedzia/` albo jako moduł koordynatora w samej aplikacji;
argument za modułem: jedna baza, zero przenoszenia plików między programami,
i flaga „objęta działaniem" z pkt Etap B jest wtedy tym samym mechanizmem.

### Etap B — automat na API (po otrzymaniu dostępu, ~2 tyg.)

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

Trzymamy **wszystkie placówki z rejonów działania** — to rząd **kilku tysięcy**
rekordów. SQLite i wyszukiwarka w formularzu nie zauważą różnicy, więc tu nie
ma kompromisu. Nie ładujemy natomiast całej Polski (~60 tys.), bo:

- nikt po niej nie będzie chodził, a każda lista podpowiedzi by ją dźwigała,
- „aktualność" znaczy wtedy odświeżanie 60 tys. rekordów po to, żeby używać 5%.

Jeśli firma wejdzie w nowy rejon — dopisujemy gminę do konfiguracji i klikamy
„Odśwież". To jest ta sama „cała baza", tylko rosnąca razem z firmą, a nie
na zapas. Gdyby Wojtek mimo to chciał całe województwo od razu: śląskie w
całości to też jest do udźwignięcia (ok. 5–6 tys. placówek) — decyzja czysto
biznesowa, technicznie obie wersje są tanie.

## 5. Dlaczego zmiana nazwy szkoły niczego nie zepsuje

Tożsamość placówki niesie **numer RSPO**, nie nazwa. Rejestr zmienia nazwę
(„SP nr 12" → „SP nr 12 im. Jana Pawła II") → odświeżenie podmienia tylko pole
nazwy w tym samym rekordzie. Leady, notatki, historia kontaktów, przydział
handlowca — wszystko wisi na `placowka_id`, którego nikt nie dotyka. Duplikat
nie może powstać, bo indeks na `rspo` jest unikalny.

## 6. Co trzeba zrobić i kiedy

| Kiedy | Co | Kto |
|---|---|---|
| poniedziałek | **wysłać wniosek o dostęp do API** (e-mail wg pkt 2) — zegar 14 dni | Przemek / biuro |
| poniedziałek | sprawdzić klikiem eksport z wyszukiwarki rspo.gov.pl; jeśli jest — pobrać rejony Kasi i wgrać do `test` na próbę | Przemek |
| wtorek | etap A na produkcji (import przez istniejący ekran) | Przemek |
| po dostępie do API (~2 tyg.) | etap B: `narzedzia/rspo.py`, przycisk „Odśwież", raport, flaga „objęta działaniem" — ~1 dzień pracy | Przemek |

## 7. Pytania otwarte

1. Wojtek: wystarczą rejony z listy Kasi rosnące z firmą, czy od razu całe
   województwo? (obie opcje tanie — pkt 4)
2. Kto formalnie składa wniosek o API (dane firmy, NIP/REGON — SILESIA 3D)?
3. Czy do „objętych działaniem" wchodzą też przedszkola i instytucje kultury,
   czy tylko szkoły? (rejestr ma wszystkie typy)
