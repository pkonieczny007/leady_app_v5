# Wdrożenie na produkcję — przygotowanie

**Demo działa** (24.08 wieczorem, potwierdzone przez Pawła). Ten plik opisuje
to samo dla produkcji: `https://ph.silesia3d.site`, katalog
`/home/ubuntu/apps/ph.silesia3d.site`, usługa `leady_v5`, port 5301.

Ścieżka jest **przećwiczona na kopii produkcji z 24.08, godz. 08:24** — czyli
na realnej pracy handlowców, nie na starym zrzucie.

---

## 1. Liczby z próby

| | przed | po |
|---|---|---|
| placówki | 555 | **1614** |
| leady | 554 | 1613 |
| **eventy** | **87** (86 DT + 1 cykliczne) | **87 — bez zmian** |
| leady przydzielone handlowcom | 438 | **438 — bez zmian** |
| konta z PIN-ami | 49 | **49 — bez zmian** |
| z numerem RSPO | 0 | 1587 (27 bez numeru) |
| bez powiatu | 555 | 1 (znane P28: „SP 5", brak miejscowości) |

Kontrola po migracji: **mikołowski 88** (tyle co w rejestrze), **Czeladź 18**.

Typy po migracji: SP 575 · PM 462 · PP 266 · ZSP 278 · Instytucja kultury 29 ·
Inna 4.

**Eventy to liczba, na którą się patrzy.** Migracja dokłada placówki i nadaje
geografię — nie ma prawa dotknąć kalendarza. Skrypt sam porównuje ją przed i po
i kończy się błędem, jeśli się rozjedzie.

---

## 2. Czym produkcja różni się od demo

**Jest tam czyjaś praca.** Kopia jest obowiązkowa i idzie razem z eksportem do
`.xlsx` — plik, który da się otworzyć bez tej aplikacji. Kopia bazy służy do
odtworzenia, arkusz jest na wypadek, gdyby odtwarzanie nie wystarczyło.

**Ludzie pracują w trakcie.** Skrypt **zatrzymuje usługę** na czas migracji
(~2 minuty) zamiast liczyć, że nikt akurat nie kliknie. Handlowiec, który
trafi w środek, zobaczy błąd połączenia i spróbuje ponownie — zamiast bazy
w połowie przerobionej. Formularz i tak trzyma szkic w telefonie.
**Robić wieczorem.**

**Osobny plik skryptu, nie przełącznik.** `migracja_na_demo.sh` świadomie nie
przyjmuje `--profil prod`: inaczej produkcję dałoby się ruszyć poleceniem
wklejonym z pamięci, z jedną zmienioną literą. Tu trzeba wpisać inną nazwę
pliku i potwierdzić słowem `PRODUKCJA`.

---

## 3. Kroki

Plik rejestru musi być na serwerze (`~/rspo_2026_08_13.csv`) — ten sam, którego
użyłeś na demo.

```bash
cd /home/ubuntu/apps/ph.silesia3d.site
git fetch origin
git checkout poprawki-2026-08
./wdroz.sh prod
```

`wdroz.sh prod` sam robi kopię bazy PRZED aktualizacją. Sprawdź w przeglądarce,
że `https://ph.silesia3d.site` wpuszcza i że na `/formularz` jest pięć kafelków.

Dopiero potem:

```bash
./narzedzia/migracja_na_produkcje.sh ~/rspo_2026_08_13.csv
```

Potwierdzenie: wpisz `PRODUKCJA`. Na końcu skrypt sam sprawdzi liczbę eventów
i odpowiedź aplikacji, i wypisze polecenie cofające.

---

## 4. Co sprawdzić zaraz po

1. **Zaloguj się jako handlowiec** (nie koordynator) — jego szkoły mają być te
   same co przed migracją. 438 przydzielonych leadów nie drgnęło w próbie.
2. **Kalendarz** — 87 wpisów, w tym 86 DT. Ta liczba jest ostateczna.
3. **`/formularz/v3` → wybierz miejscowość** — lista szkół musi się wypełnić.
   To jest ten moment, w którym ujawniłaby się usterka z 24.08 (miejscowości
   ze słownika przestały trafiać w bazę po wyczyszczeniu nazw).
4. **`/baza`** — filtr Powiat przed Miejscowością, powiat mikołowski = 88.
5. **Czeladź** — 18 placówek.

---

## 5. Czego NIE robić po migracji

**Nie uruchamiać `narzedzia/odswiez_demo.sh`** dopóki demo i produkcja mają
różne bazy. Po migracji produkcji ten skrypt znów ma sens — ale dopiero wtedy.

---

## 6. Co zostaje do zrobienia PO migracji

Migracja nie zależy od tych rzeczy, ale one dalej czekają:

- **27 placówek bez numeru RSPO** — plik decyzyjny dla Kasi
  (`do_sprawdzenia_recznego/`). Numery wchodzą przez
  `dopasuj --decyzje <plik> --zapisz`.
- **M4 — scalanie par dubli.** 18 par w bloku id 517–545, w 16 z nich jedyne DT
  wisi na rekordzie SKRÓCONYM. Narzędzia jeszcze NIE MA. Kolejność w nim jest
  krytyczna: eventy i log przepinamy PRZED skasowaniem rekordu, bo
  `ON DELETE CASCADE` zabiera DT bez śladu.
- **P28** — „SP 5" (id 532) bez miejscowości, jedyny rekord bez powiatu.
- **Konto handlowca dla Zuzi** — pracuje na wspólnym `Koordynator`, przez co
  historia zmian zapisuje konto zamiast człowieka.
- **10 placówek dopisanych ręcznie przez handlowców** między 10.08 a 24.08
  (555 wobec 545 z wdrożenia). Zakładanie z formularza jest już zamknięte,
  ale te rekordy warto obejrzeć — to one były argumentem Kasi.
