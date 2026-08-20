# Stan pracy — runda poprawek 20.08.2026

Plik do odczytania na starcie następnej sesji. Zawiera to, czego **nie da się
odtworzyć z kodu ani z historii gita**: ustalenia, ślepe uliczki, których nie
warto przechodzić drugi raz, i rzeczy czekające na ludzi.

Aktualizować przy każdym domknięciu paczki.

---

## 1. Gdzie stoimy — jednym spojrzeniem

| | |
|---|---|
| Gałąź robocza | `poprawki-2026-08`, wypchnięta na origin |
| Ostatni commit gałęzi | `3aa24b0` (P08 zrobione) |
| `main` | `b6cf84f` — kod produkcji + dokumentacja + `narzedzia/odswiez_demo.sh` |
| Punkt powrotu | tag `przed-poprawkami-2026-08-20` (na `b6cf84f`), wypchnięty |
| **Produkcja** | `6a3e181` — **NIETKNIĘTA**, żadna poprawka tam nie poszła |
| Demo | osobny katalog, zasiane kopią produkcji (545 placówek / 544 leady) |
| Testy | **861 sprawdzeń w Pythonie + 17 w node**, komplet przechodzi |

### Zrobione na gałęzi (10 poprawek)

| ID | Co | Commit |
|---|---|---|
| P01, P02 | właściciel rekordu przy zapisie; `handlowiec` i `deadline` tylko koordynator | `af345c3` |
| P04 | zmiana szkoły podmienia dane kontaktowe | `eddb17f` |
| P05 | kalendarz nie zostaje w minionym miesiącu | `eddb17f` |
| P06 | znikł dopisek „(twoje: 12)"; lista mówi, że jest cała | `0a2919e` |
| P07 | filtrowanie listy szkół z klawiatury | `0a2919e` |
| P24 | filtr „bez prowadzącego" w kalendarzu | `e8fe068` |
| P23 | zrobiona szkoła schodzi z planu dnia | `68029c6` |
| P22 | formularz przyjmuje wizytę bez terminu DT | `cc2c306` |
| P08 | odwołanie DT ze śladem wprost z grafiku | `3aa24b0` |

Szczegóły i uzasadnienia — w treści commitów. Rejestr stanu:
`REJESTR_POPRAWEK_2026-08.md`. Projekt całości: `PROJEKT_PRAC_2026-08-20.md`.

---

## 2. Serwer — co gdzie stoi

```
/home/ubuntu/apps/ph.silesia3d.site/       gałąź main, commit 6a3e181  → 127.0.0.1:5301
/home/ubuntu/apps/demo-ph.silesia3d.site/  gałąź poprawki-2026-08      → 127.0.0.1:5302
```

- Projekt compose produkcji: **`phsilesia3dsite`**, wolumen `phsilesia3dsite_leady_v5_data`.
- Projekt compose demo: **`demo-phsilesia3dsite`**, wolumen `demo-phsilesia3dsite_leady_v5_demo_data`.
- **`phsilesia3dsite_leady_v5_demo_data` to SIEROTA** po starym demo — jedyna kopia
  jego danych z 17.08. **Żadnego `docker volume prune` przez najbliższe tygodnie.**
- nginx: bez zmian, porty te same.
- Repo jest **publiczne** — dlatego `git pull` na VPS działa bez poświadczeń.
  Decyzja użytkownika: zostaje otwarte na czas rundy poprawek. Przełączenie na
  prywatne **położy `wdroz.sh` w obu katalogach**, dopóki nie założymy klucza
  wdrożeniowego read-only i nie przestawimy remote na SSH.
- `git push` z serwera **nie zadziała** — nie ma tam żadnych poświadczeń.

**Dostęp do serwera:** użytkownik loguje się **hasłem przez VS Code Remote**.
Asystent nie ma jak wejść na VPS — wszystkie polecenia serwerowe podajemy do
wklejenia, a wynik wraca do czatu.

Wdrożenie demo:
```bash
cd /home/ubuntu/apps/demo-ph.silesia3d.site && git fetch origin && ./wdroz.sh demo
```
Odświeżenie danych demo kopią produkcji: `./narzedzia/odswiez_demo.sh`.

---

## 3. Ustalenia, które kosztowały czas — nie odkrywać drugi raz

**K04 i K06 to był JEDEN błąd i nie było go w bazie.** Kasia prosiła, „żeby nie
było tego słowa w nawiasie" przy Katowicach, Zabrzu i Piekarach — brzmiało to
jak migracja słownika miast, czyli tabeli, na której wiszą przypisania całej
bazy. W bazie **nie ma ani jednej miejscowości z nawiasem**. Nawias dopisywał
JavaScript: `o.textContent + "  (twoje: 12)"`. Słowo w nawiasie to „twoje".
To samo tłumaczyło drugie zgłoszenie („widzę tylko 12 szkół") — lista **nigdy**
nie była zawężona. Naprawione w P06 jedną linią.

**K01 była szersza, niż Kasia zgłosiła.** Poza `PATCH /api/lead` bez sprawdzenia
właściciela były też `/api/pin`, `/api/lead` POST i wszystkie trzy endpointy
eventów. A `handlowiec` i `deadline` są na liście pól edytowalnych — czyli
handlowiec mógł przypisać sobie cudzą szkołę i przedłużyć sobie termin,
wyłączając auto-zwrot jednym żądaniem, ze śladem w historii nieodróżnialnym
od zwykłej pracy.

**Trzy zgłoszenia z wieczora 20.08 miały jedną przyczynę.** Formularz przyjmował
dokładnie jeden wynik wizyty („DT umówione" z kompletem sześciu pól), więc każda
inna praca w terenie musiała iść obok niego i nie zostawiała śladu tam, gdzie
się ją wykonuje. Stąd i prośba Kasi o statusy, i to, że szkoły nie schodziły
Zuzi z listy zadań, i to, że w raporcie nie da się policzyć „ile odpuściliśmy
celowo".

**Kasowanie spotkania ISTNIEJE — tylko nie w kalendarzu.** Przycisk `✕` jest na
karcie leada (`templates/lead.html`, obsługa w `static/app.js` ~307). Kasia ma
rację co do miejsca, nie co do funkcji.

**`Nr RSPO` jest pusty dla WSZYSTKICH 545 placówek.** Import z rejestru nie ma po
czym rozpoznać duplikatu — dopasowanie musi iść po nazwie i miejscowości,
z raportem do ręcznego przejrzenia. To największe ryzyko paczki bazy.

**W bazie nie ma ANI JEDNEGO przedszkola** (539 szkół podstawowych + 6 „Inna"),
choć firma prowadzi w nich zajęcia.

**Gliwic, Mysłowic i Bytomia nie ma czego kasować** — są w słowniku miast, ale
mają zero placówek. K07 to trzy wiersze w słowniku, nie migracja.

---

## 4. Czeka na ludzi

### Na Kasię — `PYTANIA_DO_KASI_2026-08-20.md`

Pytania blokujące: **1, 2, 4, 8, 9**. Pytanie 3 jest **nieaktualne** (sami
znaleźliśmy przyczynę). Do doprecyzowania: 5, 6, 7, 10–13.

Najważniejsze z nich:
- **pytanie 1** — „wolny trener ×3": wolne miejsca na zajęciach czy konta?
  Blokuje drugą połowę K13. Do tego: trener bierze wiążąco czy koordynator
  potwierdza (to samo pytanie wisi od 10.08).
- **pytanie 4** — załącznik **`POPRAWKA BAZY.xlsx`**, kolumny ✎ są **puste**
  (0 z 545 wierszy, 0 z 34 miast). Bez tego nie ruszamy paczki bazy.
- **pytanie 7** — kto może odwołać DT i co się dzieje ze szkołą po odwołaniu.
- **„muszę mieć takie 2 kolumny"** — jedyne zdanie Kasi, którego nie umiemy
  przełożyć na robotę.
- **P25** — w słowniku `status_realizacji` brakuje „brak próby". Reszta jej
  listy już jest. Nie dopisujemy za nią: to jej słownik i jej nazewnictwo.

### Do sprawdzenia na produkcji

**Zuzi nie ma wśród 50 kont.** Skoro pracuje w aplikacji, to na wspólnym koncie
`Koordynator` — bezimiennym, z pełnymi uprawnieniami. W historii zmian zostaje
wtedy „Koordynator", a nie człowiek, co podkopuje właśnie te uprawnienia, które
domyka P01. **Zapytać Kasię, kto używa tego konta i czy ma zostać.**

Stan kont (produkcja, 20.08): 5 handlowców, 5 koordynatorów, 40 trenerów.
Wielorolowość: Małolepsza ma 3 konta, Sacawa 3 (plus osobna osoba o tym samym
nazwisku). Koordynatorzy: Sacawa, Małolepsza, Młynarczyk, Przemek, `Koordynator`.
Kasia chce zostawić siebie i Julię — czyli zdjąć Weronikę, a o Przemka
i o konto wspólne dopytać (pytania 8 i 9).

---

## 5. Co dalej, w kolejności

1. ~~P08~~ — **ZROBIONE** (`3aa24b0`). Projekt i decyzje zostawione niżej jako
   zapis tego, co zostało rozstrzygnięte i dlaczego.
2. **P09** — sprzątnięcie DT „Paziewski" i innych wpisów z prezentacji 06.08;
   **najpierw lista do potwierdzenia przez Kasię**, potem usunięcie. Zależy od P08.
3. **Paczka A na produkcję osobno** — P01+P02 to dziura w uprawnieniach, nie ma
   powodu, żeby czekała na resztę listy. `git cherry-pick af345c3` na `main`,
   komplet testów, `wdroz.sh prod`, potem `git rebase main` na gałęzi poprawek.
4. **Paczka D — baza** (P12–P16). Czeka na `POPRAWKA BAZY.xlsx` od Kasi.
   Materiały leżą w `POPRAWKI 20.08.2026-work\POPRAWKA BAZY\`, jest tam też
   `POPRAWKA BAZY - RSPO dopasowane.xlsx` i `ANALIZA_BAZY_2026-08-20.html`,
   których jeszcze nie czytaliśmy — użytkownik prosił, żeby bazę zostawić na koniec.
5. **Paczka E — konta** (P17–P19). Czeka na decyzje o rolach i na tabelę
   mapowania od Kasi.
6. **Paczka F — raport** (P20). Po paczce D.

### Projekt P08 (do wykonania)

- **Odwołanie ze śladem, nie kasowanie.** Status „odwołane" + powód + kto i kiedy.
  Wpis znika z grafiku, zostaje w historii i w raporcie „ile się nie udało".
- **Uprawnienia — decyzja użytkownika z 20.08:**
  **handlowiec może ODWOŁAĆ, koordynator może ODWOŁAĆ I SKASOWAĆ.**
  Odwołanie zostawia ślad, więc wolno je szerzej; kasowanie zabiera dowód, że
  coś w ogóle było, więc zostaje przy jednej osobie. Handlowca dodatkowo
  ogranicza P01 — tylko na własnej szkole.
- **Wystawić to w kalendarzu**, nie tylko na karcie leada. **Nie prawym
  przyciskiem** — na telefonie prawego przycisku nie ma, a Kasia i handlowcy
  pracują z telefonu.
- Do czasu odpowiedzi Kasi (druga połowa pytania 7): lead po odwołaniu
  **zostaje przy handlowcu**, status wraca do „w toku", termin bez zmian.

---

## 6. Rzeczy techniczne, na których łatwo się przewrócić

**Warianty formularza mają być IDENTYCZNE co do funkcji.** v2, v3 i v4 mają
bloki wyboru szkoły i podstawiania kontaktu **byte-in-byte takie same** —
pilnują tego testy w `test_formularz.py` (`blok_wyboru`, `helper`). Zmiana
w jednym bez pozostałych wywali testy i o to chodzi. v1 (`formularz.js`) ma
własny układ i nie podpowiada kontaktu — tam tych bloków nie ma.

**Podmiana bloków w wielu plikach naraz: uważać na końce linii.** Skrypt
pythonowy czytający `io.open(..., newline="")` dostaje `\r\n` i literał ze
zwykłym `\n` **nie trafi** — `str.replace` nie zgłosi błędu, po prostu nic nie
zrobi. Albo czytać bez `newline=""`, albo asertować liczbę trafień
(`assert k.count(szukaj) == 1`). Zapisywać z `newline="\n"`.

**`.gitattributes` pilnuje `*.sh text eol=lf`** — skrypty powłoki idą na Linuksa
z LF mimo `core.autocrlf=true`. Nowy `.sh` dodawać z bitem wykonywalności:
`git update-index --chmod=+x plik.sh`.

**Testy to zwykłe skrypty**, każdy z `sprawdz(nazwa, warunek, opis)` i podsumowaniem
`N/N`. Nowy plik w tej rundzie: `test_uprawnienia.py`. Komplet uruchamia się tak:

```powershell
python test_parsers.py; python test_scenariusze.py; python test_dostepnosc.py
python test_przydzial.py; python test_filtr_osob.py; python test_formularz.py
python test_logowanie.py; python test_serwis.py; python test_trener.py
python test_uprawnienia.py
node test_cykl.js
```

**Front-end testujemy też na poziomie ŹRÓDŁA** (czy blok jest, czy wszystkie
warianty mają go tak samo) — to jedyny sposób, żeby zachowanie czystego JS-a
bez wywołania serwera nie rozjechało się po cichu.

**Lokalnie pracujemy na `PROFIL=test`.** `data/prod` to lokalna atrapa z 10.08,
nie jest w gicie (`data/` w `.gitignore`) i **nie jest produkcją**.
