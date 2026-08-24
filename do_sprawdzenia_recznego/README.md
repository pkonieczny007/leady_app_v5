# Do sprawdzenia ręcznego

Rzeczy, których automat **świadomie nie ruszył**, bo pomyłka kosztowałaby
więcej niż ręczna robota. Każdy plik ma kolumny do wypełnienia i da się go
wczytać z powrotem — nic nie przepisujemy z ekranu.

⚠️ **Ten katalog nie idzie do gita.** Pliki niosą nazwy, adresy i telefony
placówek klienta, a repozytorium jest publiczne (`.gitignore`).

---

## `BEZ_RSPO_2026-08-24.xlsx` — 25 placówek bez numeru RSPO

Baza ma 1618 placówek i **pokrywa rejestr co do wiersza** — nie brakuje niczego.
Te 25 to rekordy klienta, których nie udało się jednoznacznie powiązać
z rejestrem. Prawie każdy z nich to **skrót handlowca zapisany obok pełnej
nazwy z rejestru** („MSP 1" i „MIEJSKA SZKOŁA PODSTAWOWA NR 1 W PIEKARACH
ŚLĄSKICH"), czyli ta sama szkoła w bazie dwa razy.

### Jak czytać

| kolumna | co mówi |
|---|---|
| **Werdykt automatu** | dlaczego nie wpisaliśmy numeru sami |
| **Spotkań** | ile umówionych DT/cykli wisi na tym rekordzie |
| **BLIŹNIAK w bazie** | rekord z pełną nazwą i numerem RSPO — kandydat, z którym ten wiersz należy scalić |
| **DECYZJA — numer RSPO** | wpisz numer, jeśli rekord ma zostać samodzielny |
| **DECYZJA — scalić z id** | wpisz id bliźniaka, jeśli to ta sama placówka |

**Żółte wiersze mają umówione spotkania.** Przy scalaniu to z nich nic nie może
zginąć — kalendarz i historia idą do rekordu docelowego PRZED skasowaniem
czegokolwiek.

### Werdykty

- **numer zajęty** (12) — numer z rejestru ma już inny rekord w bazie.
  To niemal na pewno dubel: „EduHub" obok „NIEPUBLICZNA SZKOŁA PODSTAWOWA
  EDUHUB W KATOWICACH". Wypełnij *scalić z id*.
- **niepewne** (7) — kilku kandydatów albo dopasowanie tylko po podpowiedzi
  (nazwa wsi ukryta w nazwie szkoły: „Sp Góra", „Sp Miedźna"). Kandydaci są
  wypisani w kolumnie „Kandydaci / uwagi".
- **brak** (6) — nic sensownego w rejestrze: `SP 5` bez miejscowości, `29.0`,
  „Zsp", „Sp", „Nasza Szkoła", „Książenice". Część to prawdopodobnie pomyłki
  przy imporcie z arkusza; **skasować wolno tylko te bez spotkań i bez wpisów
  w historii**.

### Co dalej

```powershell
# po wypełnieniu kolumny „DECYZJA — numer RSPO”
python narzedzia/migracja_rspo.py dopasuj --profil test `
       --decyzje "do_sprawdzenia_recznego\BEZ_RSPO_2026-08-24.xlsx" --zapisz
```

Scalanie par (kolumna *scalić z id*) to etap **M4** — osobne narzędzie, bo
kolejność jest tam krytyczna: eventy i historia przepinają się PRZED
skasowaniem rekordu, inaczej `ON DELETE CASCADE` zabiera DT bez śladu.

Odtworzenie pliku w każdej chwili:

```powershell
python narzedzia/migracja_rspo.py dopasuj --profil test `
       --xlsx "do_sprawdzenia_recznego\BEZ_RSPO_2026-08-24.xlsx"
```
