# Stan sesji — niedziela 23.08.2026, wieczór

Plik do przeczytania NA STARCIE następnej sesji. Skrót: co zrobione, co czeka,
gdzie leżą decyzje i o co się potknęliśmy.

| | |
|---|---|
| Gałąź | `poprawki-2026-08`, ostatni commit **`b72a1f8`** |
| Produkcja | nietknięta, `main` = `6a3e181`; cofnięcie: tag `przed-poprawkami-2026-08-20` |
| Demo | **stoi na `main`** — klient NIE WIDZI żadnej poprawki |
| Testy | 11 plików, **912 sprawdzeń** + 93 (`test_parsers`) + 17 (node), komplet OK |
| Profil `test` | ma lustro RSPO (6 116) i 17 obszarów; `prod` nie ma |

---

## 1. Rzecz najważniejsza: nic z tego nie jest u klienta

Trzy dni pracy siedzą na gałęzi. **Dopóki demo nie zostanie wdrożone, Kasia
i Zuzia widzą aplikację z 10.08** i zgłaszają rzeczy, które są już naprawione.
Tak się stało z sekcją „Wynik wizyty" — Paweł pytał, czemu jej nie ma w v3,
a ona tam była od 20.08, tylko nie na demo.

```bash
cd /home/ubuntu/apps/demo-ph.silesia3d.site
git fetch origin
git checkout poprawki-2026-08 2>/dev/null || git checkout -b poprawki-2026-08 origin/poprawki-2026-08
./wdroz.sh demo
docker compose exec leady_v5_demo python narzedzia/statusy.py --zapisz
docker compose exec leady_v5_demo python narzedzia/slowniki_kontrola.py --zapisz
```

Dwie ostatnie komendy są konieczne, bo **słowniki to dane, nie kod** — nie
przyjeżdżają z `git pull` i `odswiez_demo.sh` je zeciera przy każdym odświeżeniu
demo kopią produkcji.

---

## 2. Commity tej rundy (od `42b1296`)

| commit | co |
|---|---|
| `f54c667` | P27/P30/P31 — formularz przyjmuje niedokończone DT, kalendarz o tym mówi, lista odwołanych |
| `6ef607e` | `statusy.py` odmawia pracy na nie tej bazie |
| `23fffbc` | projekt migracji bazy na RSPO |
| `e67405f` | **M1+M2** — lustro rejestru i obszary działania |
| `45c11a2` | telefon przestaje jeździć w bok |
| `bb0c164` | plan zakładek baz PH |
| `a85a6ff` | plan formularza v5 |
| `009496a` | E0 — brakujący `CYKLICZNE-PRZEDSZKOLE` w słowniku produkcji |
| `b72a1f8` | ekran `/obszary` (podgląd) |

---

## 3. Co zrobione w kodzie

**Formularz i kalendarz (P27/P30/P31).** Twarda została sama data DT; godzina,
prowadzący, klasy i dzieci są opcjonalne. Braki widać w kalendarzu jako
„⚠ do uzupełnienia" (klikalny licznik + filtr), odwołane mają własny tryb
z powodem i przywracaniem. Statusy pośrednie z listy Zuzi dodane narzędziem.

**Migracja RSPO, etapy M1 i M2** (profil `test`, oba addytywne, odwracalne
`DROP TABLE`):
- `rejestr_rspo.py` — lustro `rspo_rejestr` + `rspo_importy` + `rspo_zmiany`;
  6 116 placówek śląskich, wgranie 1,2 s; zniknięcia OZNACZANE, nie kasowane;
  bezpiecznik odmawia przy pliku wyglądającym na wycinek
- `obszary.py` — `obszary_dzialania` + `obszar_zakres` + `rspo_obszar`;
  17 obszarów z listy Kasi; **gmina bije powiat** (jedno zapytanie w `przelicz()`)
- `narzedzia/migracja_rspo.py` — `lustro` / `obszary` / `stan`
- ekran `/obszary` — podgląd z rozbiciem na typy, bez możliwości edycji

Kontrola wyjścia M2 zgodna co do sztuki: **1 259 szkół i przedszkoli**
(1 560 z zespołami i punktami), Knurów **44 przez gminę**, rybnicki **0**.

**Telefon** — `.topbar-right` miał w wersji mobilnej zakaz kurczenia się przy
zawartości ~370 px; `.seg` ucinał zakładki bez możliwości dojechania; karta
szkoły miała siatki szersze niż ekran. Wszystko naprawione.

**E0** — `narzedzia/slowniki_kontrola.py` + sprawdzenie w S0.

---

## 4. Ustalenia, które zmieniają sposób myślenia o bazie

**Import urwał słowo „powiat".** W pliku klienta były wartości
`09. Pszczyna powiat` i `15. Będzin powiat`; w aplikacji zostało `09. Pszczyna`
i `15. Będzin`. Pod Będzinem siedzi **17 miejscowości** (w tym Czeladź 3), pod
Pszczyną **27**. To jest odpowiedź na „nie ma szkół z Czeladzi". Ornontowice
również nie były naszym wymysłem — u klienta siedziały pod `01. Orzesze`.

**Zakres firmy nie leży na jednym poziomie administracyjnym.** Rybnik jako
miasto, ale nie powiat rybnicki (191 vs 62 placówki). Knurów jako gmina, ale nie
reszta powiatu gliwickiego (44 z 136). Dlatego obszar to LISTA ZAKRESÓW, nie
kolumna. W rejestrze rozróżnia je sama nazwa: miasto na prawach powiatu gołą
nazwą (`Katowice`), powiat ziemski małą literą (`mikołowski`).

**Lustro musi być osobną tabelą.** Rejestr i baza robocza mają sprzeczne
polityki nadpisywania: w lustrze wygrywa rejestr, w bazie roboczej człowiek
(telefon wpisany przez handlowca jest cenniejszy niż z rejestru). W jednej
tabeli jedna z nich musiałaby po cichu przegrywać.

**Zamknięcia szkoły nie da się odczytać z pliku.** `Data likwidacji` jest pusta
we wszystkich 56 190 wierszach — widać je tylko jako różnicę między wgraniami.
Stąd bezpiecznik wycinka jest obowiązkowy, nie ozdobny.

**Stan bazy przed migracją:** 409 placówek niesie realną pracę, **136 jest
nietkniętych** (wolno wymienić). **18 par dubli** w bloku id 517–545; w 16 z nich
jedyne DT wisi na rekordzie SKRÓCONYM, a telefon i pełna nazwa na PEŁNYM —
scalanie musi przepiąć eventy PRZED wszystkim innym. Historia zmian ma 13
wierszy i **ani jednego wpisu od człowieka** (11 to auto-zwrot z jednej sekundy),
więc migracja chroni `leady` i `eventy`, nie `log`.

**Adres nie pomoże przy dopasowaniu** — 504 z 536 to sama nazwa ulicy bez numeru,
zero kodów pocztowych. Jedynym nośnikiem miasta jest `placowki.miejscowosc`.

**Punkty 7–10 listy Zuzi nie były błędem kodu.** Te operacje od początku były
zamknięte dla handlowca; ona pracuje na wspólnym koncie `Koordynator`.

---

## 5. Dokumenty projektowe (wszystkie w `docs/poprawka 23.08.2026/`)

| plik | co zawiera |
|---|---|
| `PROJEKT_BAZY_RSPO.md` | model docelowy, etapy M0–M9, scalanie dubli, 9 pytań |
| `PLAN_FORMULARZA.md` | v5 obok czterech starych, kaskada, chipy zajęć, E0–E8, 10 pytań |
| `PLAN_BAZY_PH.md` | 6 zakładek Kasi, „po terminie z historią" przez `log`, 8 pytań |
| `dopasowanie_prod_2026-08-23.xlsx` | 466 pewnych / 10 po numerze / 69 braków / 9 par dubli |

Razem **27 pytań** do Kasi i Wojtka. Najważniejsze trzy: czy zespół
szkolno-przedszkolny to jeden rekord czy kilka, czy wchodzi 691 przedszkoli,
czy przyjmujemy pełne nazwy z rejestru zamiast skrótów handlowców.

---

## 6. Co dalej, w kolejności

1. **Wdrożenie na demo** — blokuje wszystko inne (patrz pkt 1)
2. **Konto handlowca dla Zuzi** — bez tego jej zgłoszenia będą wracać
3. Odpowiedzi Kasi → **M3** (numery RSPO, plik decyzyjny) i **M4** (scalanie)
4. Szybkie zadania z `PLAN_BAZY_PH.md`: chipy „DT umówione"/„Z cyklami"
   na `/baza`, zakres „w pracy", plakietka filtra na `/baza`
5. **P29** „zgłoś do usunięcia" — jedyny punkt z listy Zuzi bez rozwiązania
6. **P28** placówka 532 „SP 5" bez miejscowości (jedyna taka, nieosiągalna
   z formularza — stąd „brakuje szkół w mojej bazie")

**Czego NIE zaczynać przed poniedziałkiem** (za `PLAN_FORMULARZA.md`): etapów
**E2 i E3** — dotykają „Twoich szkół", czyli ekranu, na którym handlowcy
w poniedziałek pracują.

**Nowy formularz można robić kiedykolwiek — decyzja Pawła z 23.08 wieczorem.**
Powstaje jako **piąty przycisk** na ekranie wyboru `/formularz`, obok czterech
istniejących. Rozgrzebany v5 niczego nie blokuje, bo handlowiec dalej klika
swój v3; w najgorszym razie piąty kafelek prowadzi do ekranu, który nie robi
jeszcze wszystkiego. Dwa warunki, żeby to zostało prawdą: **E5 ma być
addytywne** (lista `zajecia:[…]` obok bloków `dt`/`cykl`, stare payloady bez
zmian — test „v1–v4 nietknięte" jest tu zaporą, nie formalnością) i **piąty
kafelek ma być opisany jako testowy**, tak jak dziś v4.

---

## 7. Grabie z tej rundy — nie powtarzać

**`git add <katalog>` zgarnia pliki klienta.** Dwa razy w tej rundzie; za drugim
razem `Kopia Julia Młynarczyk.xlsx` — miesięczne rozliczenia trenerów ze
stawkami — do PUBLICZNEGO repo. Złapane przed `push`. Arkusze klienta są teraz
w `.gitignore`. **`git status` czytać PRZED commitem.**

**`odwolane` w `calendar_view.py` było zajęte** — znaczy „odwołane WYSTĄPIENIE
cyklu" i `_naloz_wyjatek()` zeruje je przy każdym wpisie bez wyjątku. Odwołanie
całego spotkania dostało własną nazwę `odwolanie`.

**Heredoc Basha z Pythonem czyta polskie znaki w cp1250** — wzorce przestają
pasować, `replace` nie robi nic i wygląda to na wykonaną pracę. Używać Edit
albo `\uXXXX`. **Zawsze asercja `s.count(wzorzec) == 1`.**

**`app.py` jest CRLF, `calendar_view.py` LF** — skrypt podmieniający tekst
działa na jednym, na drugim cicho nie trafia.

**Test pisał pliki pod jedną ścieżkę** — sprawdzenie przechodziło zależnie od
kolejności. Test, który nie testuje, jest gorszy niż jego brak.

**Słownik to dane osobne dla każdego profilu.** `CYKLICZNE-PRZEDSZKOLE` był
w kodzie i na `test`, ale nie na `prod` — wpis dawało się utworzyć, a nie
poprawić (edycja odbija się od twardej blokady słownika).

**Serwer na 5301 może już chodzić** — Windows pozwoli uruchomić drugi na tym
samym porcie i oba będą odpowiadać na przemian. Sprawdzać `netstat -ano`.
