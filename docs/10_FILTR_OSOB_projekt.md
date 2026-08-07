# Filtr wpisywany + rozdzielenie „filtruj" od „wypełnij"

Zgłoszenie klienta (05.08.2026), słowo w słowo:

> „zauważyłem, że nie mogę filtrować po pracownikach… rozsuwane listy z trenerami
> wyglądają jak filtr, ale to są wypełnij. Potrzebuję utworzyć okno gdzie można
> wpisywać nazwisko. Okno filtrowania. Które będzie podstawową funkcję miało
> wpisanie, ale też można filtr zablokować i łączyć kilka wpisów i wyłączać.
> Dodatkowo wypełnij musi się odróżniać, więc tło inne w tym miejscu gdzie mamy funkcje."

Dwa problemy w jednym zdaniu — i oba są prawdziwe.

Tego samego dnia doszła druga tura: **ten sam filtr na kalendarzu
i dostępności**, z zakresami „wszystko" i „nazwisko" (Rozwiązanie 3).

---

## Problem 1: filtrować po ludziach prawie się nie dało

Stan przed zmianą:

| Kto | Czy dało się filtrować | Jak |
|---|---|---|
| handlowiec | tak, ale słabo | jedna wartość z listy rozwijanej, dopasowanie `=` do pełnego zapisu z prefiksem |
| **prowadzący (trener)** | **nie, w ogóle** | na listach leadów nie było takiego filtra |
| zastępstwo, drugi prowadzący, drukarz | nie | j.w. |

Lista rozwijana wymaga wybrania **dokładnie tej** pozycji, która siedzi w słowniku.
W danych klienta ta sama osoba bywa zapisana jako `18. Bitner` i jako `Bitner`,
a prefiksy `01. `, `02. ` zostają w wartościach (klient po nich sortuje). Człowiek,
który chce zobaczyć „co ma Bitner", pamięta nazwisko — nie numer przed nim.

## Problem 2: filtr i pole edycji wyglądały identycznie

`<select>` w pasku filtrów i `<select>` w komórce tabeli miały ten sam biały
prostokąt z tą samą ramką. Różniło je tylko położenie na ekranie — czyli wiedza,
którą trzeba pamiętać. Skutek był gorszy niż estetyczny: **próba zawężenia widoku
przez kliknięcie w listę w komórce nadpisywała dane w bazie**, bo komórki
zapisują się od razu po zmianie.

---

## Rozwiązanie 1 — filtr osób na chipach

Druga linia paska filtrów na wszystkich pięciu listach leadów
(`/baza`, `/leady`, `/zbiorczy`, `/niewykorzystane`, `/tydzien`):

```
OSOBY  (◇ Sacawa 🔓 ✕) (T Zemela 🔒 ✕) (H Chytry 🔓 ✕)   [◇ dowolna osoba ▾] [wpisz nazwisko…] [+ Dodaj]  LUB|ORAZ
```

Cztery rzeczy, o które prosił, i co dokładnie robią:

| Prośba | Realizacja |
|---|---|
| **wpisywanie** | pole tekstowe; szuka **fragmentu**, więc „bitn" trafia i w `18. Bitner`, i w `Bitner`. Lista podpowiedzi (`datalist`) tylko pomaga — nie ogranicza. |
| **łączenie kilku wpisów** | każdy Enter dokłada chip; przełącznik **LUB / ORAZ** decyduje, jak się składają |
| **wyłączanie** | klik w tekst chipa gasi go — chip zostaje przekreślony i szary, ale nie zawęża wyniku. Wraca jednym kliknięciem. |
| **przypięcie (kłódka)** | przypięty chip przeżywa „Wyczyść", zmianę zakładki, zmianę miesiąca i przełączenie widoku; przy próbie usunięcia ✕ pyta o potwierdzenie. Nie przeżywa przejścia linkiem z górnej nawigacji — to celowe, patrz „Czego świadomie nie zrobiono". |

Dodatkowo każdy chip ma **zakres** (klik w kwadracik z lewej przełącza w kółko):

- `◇` dowolna osoba — handlowiec **albo** ktokolwiek na spotkaniu,
- `H` tylko handlowiec,
- `T` tylko prowadzący — i to obejmuje `trener`, `trener2`, `zastepstwo`, `drukarz`,
  bo z punktu widzenia pytania „kto tam pojechał" to jedna rzecz.

**Dlaczego LUB jest domyślne.** Lead ma jednego handlowca, więc „Sacawa I Bitner"
w trybie ORAZ dałoby pustkę i wyglądałoby na zepsuty filtr. Tryb ORAZ zostaje pod
przyciskiem, bo ma sens przy mieszaniu zakresów: `H Sacawa` **oraz** `T Zemela`
= „leady Sacawy, na które jeździ Zemela" (na realnych danych: 165 → 17 rekordów).

### Zapis stanu

Wszystko mieści się w jednym parametrze URL. Chipy rozdziela `|`, każdy ma postać
`[flagi][zakres:]tekst`:

```
?osoby=%23h%3ASacawa|-t%3ABitner|o%3ANowak
        └ #h:Sacawa   └ -t:Bitner   └ o:Nowak
          przypięty     wyłączony     zwykły
```

- `-` wpis wyłączony · `#` wpis przypięty (kolejność flag dowolna)
- listy leadów: `o:` dowolna osoba (domyślnie) · `h:` handlowiec · `t:` prowadzący
- kalendarz i dostępność: `w:` wszystko (domyślnie) · `n:` nazwisko
- zakres z innego ekranu sprowadza się do domyślnego — wpis nigdy nie ginie po cichu

Dzięki temu filtr osób jest **zwykłym parametrem GET**, jak wszystkie pozostałe —
więc stronicowanie, licznik „N rekordów" i „Pobierz XLSX" pokazują to samo,
co tabela. To ta sama zasada, która stoi za istnieniem `repo.py`: widok i eksport
budują zapytanie w jednym miejscu, więc nie mogą się rozjechać.

### Dlaczego filtrowanie zostało po stronie SQL

Kuszące było przefiltrować wiersze w przeglądarce — bez przeładowania, natychmiast.
Byłoby **błędne**: listy są cięte po 150 wierszy, więc filtr w JS zawężałby tylko
widoczną stronę, a licznik i eksport dalej mówiłyby swoje. `filtr_osob.js` nie
filtruje niczego — dokłada chip, przepisuje ukryte pole i wysyła formularz.

### Polskie znaki

SQLite-owe `LIKE` ignoruje wielkość liter **tylko dla ASCII**: `ŁUKASZEK` nie
znalazłby się po wpisaniu `łukaszek`, a `Małolepsza` po `malolepsza`. Dlatego
`db.pl_fold` (małe litery + zdjęte ogonki) jest zarejestrowane jako funkcja SQLite
w `get_conn()` i przepuszczamy przez nią **obie** strony porównania.

---

## Rozwiązanie 2 — kolor mówi, co pole robi

Jedna zasada, wprowadzona konsekwentnie na wszystkich ekranach:

| | Znaczenie | Gdzie |
|---|---|---|
| **zimny błękit** `--filtr` + podpis `FILTR` z lewej | zawężam widok, **danych nie ruszam** | paski filtrów: listy leadów, kalendarz, dostępność |
| **ciepły krem** `--fill` + bursztynowe podkreślenie | **zapis do bazy od razu** po zmianie | komórki tabeli, pola na karcie leada, „Wypełnij zakres" i edytor komórki na Dostępności |

Kolory wchodzą przez zmienne CSS i przez `.filters::before`, więc trzy istniejące
paski filtrów dostały nowy wygląd bez ruszania szablonów. Obie barwy są nazwane
w legendzie pod każdą tabelą — żeby zasada była napisana, a nie tylko widoczna.

Bursztyn na polach „wypełnij" jest ten sam, co przy przypięciu na tydzień
(`--amber` z dzioba tukana) — to kolor „ta rzecz coś zmienia", nie nowy element palety.

---

## Rozwiązanie 3 — ten sam filtr na kalendarzu i dostępności

Druga tura zgłoszenia (05.08.2026):

> „w kalendarz i dostęp potrzebuję filtrów po pracowniku i filtr ogólny.
> Wpisujemy i filtruje wszystko i jego można przypiąć. Dodatkowo można zmienić
> na nazwisko i wtedy po nazwisku."

To ten sam filtr, tylko z innymi **zakresami**. Na listach leadów pytanie brzmi
„czyj to lead" (`◇` dowolna osoba / `H` handlowiec / `T` prowadzący). Na grafiku
brzmi inaczej i klient nazwał to sam:

| Zakres | Znak | Gdzie szuka |
|---|---|---|
| **wszystko** (domyślny) | `∗` | wszystkie pola wpisu: szkoła, miejscowość, adres, **handlowiec**, prowadzący, sala, grupa, sprzęt, uwagi, kod Tinkercad, godziny |
| **nazwisko** | `N` | tylko ci, którzy TAM BĘDĄ: prowadzący, drugi prowadzący, zastępstwo, drukarz |

Chip przełącza się między nimi jednym kliknięciem w kwadracik z lewej — dokładnie
to „dodatkowo można zmienić na nazwisko". Przypinanie, wyłączanie i LUB / ORAZ
działają tak samo jak na listach leadów, bo to ten sam kod (`filtry.py`).

### Co filtr robi na każdym z ekranów

- **Kalendarz, wszystkie trzy widoki** (Macierz, Agenda, Starty) — zawęża
  spotkania. W Macierzy dodatkowo chowa puste wiersze trenerów: skoro pytam
  „gdzie jest Zemela", nie chcę oglądać 34 pustych wierszy reszty zespołu.
- **Dostępność** — zawęża **wiersze**, nie komórki. Ekran odpowiada na pytanie
  „kiedy ta osoba może", a wolne okna liczą się z całego dnia — pokazanie dnia
  w kawałkach byłoby kłamstwem. W zakresie „wszystko" wiersz zostaje, gdy pasuje
  nazwisko trenera, jego uwagi z deklaracji **albo** szkoła/miasto, do których
  w tym miesiącu jeździ. Dzięki temu „Knurów" pokazuje 4 z 40 trenerów.

### Poprawka: „nazwisko" to kto tam BĘDZIE, nie kto sprzedał

Zgłoszenie z pierwszego użycia:

> „zauważyłem że filtrując po 02. Olszewska w kalendarzu pokazuje mi też inne
> pozycje trenerów, ponieważ w tej samej szkole pojawia się ten trener"

Przyczyna była w danych i była realna: **`02. Olszewska` figuruje u nich
jednocześnie jako handlowiec i jako trenerka** (podobnie Olszewska, Małolepsza,
Młynarczyk — nazwiska powtarzają się między słownikiem handlowców i trenerów).
Zakres „nazwisko" przeszukiwał również pole `handlowiec`, więc łapał każde
zajęcia z leada, który ona sprzedała — a jeździł na nie kto inny:

| Trafia przez | Spotkań w czerwcu |
|---|---|
| `trener` — jej własne zajęcia | 46 |
| `drukarz` — jest na miejscu, ale w cudzym wierszu | 5 |
| ~~`handlowiec` — sprzedała lead, nie jedzie tam~~ | ~~117~~ |

**Handlowiec wypadł z zakresu „nazwisko" na grafiku.** Kalendarz i dostępność
odpowiadają na pytanie „kto tam będzie", a handlowiec nie jedzie na zajęcia.
Zostaje wyszukiwalny w zakresie „wszystko" — bo „wszystko" znaczy wszystko.
Na realnych danych: `N Olszewska` → 51 spotkań zamiast 152.

Zostawało jeszcze 5 wpisów, gdzie jest **drukarzem** na cudzych zajęciach — one
lądują w wierszu tamtego trenera i bez wyjaśnienia dalej wyglądają jak pomyłka
filtra. Dlatego taki kafelek dostaje bursztynową etykietę **roli** („drukarz",
„zastępstwo", „2. prowadzący"). Gdy szukana osoba jest prowadzącą, etykiety nie
ma — wpis siedzi w jej własnym wierszu i nie ma czego tłumaczyć.

**Podpowiedź niesie swój zakres.** Zostaje trzecia droga do tego samego błędu:
wpisanie nazwiska przy domyślnym `∗ wszystko`. Dlatego wybranie pozycji z listy
podpowiedzi ustawia zakres tej pozycji — prowadzący daje chip `N`, miejscowość
daje `∗`. Ręczna zmiana listy zakresu ma pierwszeństwo, a nadany zakres widać
od razu na chipie, więc nie jest to ukryta magia — da się go kliknąć i zmienić.

### Dwie rzeczy, które trzeba było zrobić przy okazji

**Kolizje liczymy przed filtrem, pokazujemy po.** Nakładka godzin to zawsze
para spotkań. Gdyby filtr działał przed wykrywaniem, wyfiltrowanie jednej ze
szkół chowałoby drugą stronę nakładki i ostrzeżenie **znikałoby po cichu** —
najgorszy możliwy błąd w tym projekcie. Wykrywanie idzie więc na pełnym
komplecie miesiąca, a licznik w nagłówku zlicza tylko to, co widać (inaczej
„31 spotkań · 30 w kolizji" wskazywałoby na spotkania, których nie ma na ekranie).

**Zniknęła lista `— wszyscy trenerzy —`.** Działała **tylko w widoku Agenda** —
w Macierzy i Startach parametr `trener` był czytany, ale nigdzie nie używany, więc
lista wyglądała jak filtr i nie robiła nic. Zastąpił ją filtr wpisywany, który
działa we wszystkich trzech widokach. Stare linki z `?trener=…` dalej działają:
parametr wjeżdża jako chip „nazwisko".

### Filtrowanie tutaj jest w Pythonie, nie w SQL

Odwrotnie niż na listach leadów — i celowo. Dane kalendarza i tak powstają
w Pythonie: cykle rozwijają się z jednego rekordu na wystąpienia, a wyjątki
(`zastępstwo na jedną datę`) podmieniają trenera **już po wyjściu z bazy**.
Filtr w SQL nie zobaczyłby zastępstwa wpisanego jako wyjątek cyklu. Nie ma tu
też stronicowania ani eksportu, więc powód, dla którego listy leadów filtrują
się w SQL, tutaj nie występuje.

---

## Czego świadomie nie zrobiono

- **Zapamiętywania filtra w sesji.** Przypięcie (kłódka) załatwia to jawnie,
  decyzją człowieka, i jest cały czas widoczne jako bursztynowy chip. Ciche
  pamiętanie filtra między wejściami to najprostszy sposób, żeby ktoś zobaczył
  17 rekordów zamiast 551 i uznał, że zginęły mu dane.
- **Przenoszenia przypiętych chipów przez górną nawigację.** Chip trwa w obrębie
  ekranu (zmiana miesiąca, widoku, zakładki, „Wyczyść"). Wejście z menu na inny
  ekran to świadome „zaczynam co innego" — i tam zakresy i tak są inne.
- **Filtrowania po osobie kontaktowej ze szkoły.** To nie „pracownik" — i jest
  już w polu `szukaj:` obok.
- **Podpowiedzi z liczbą trafień przy nazwisku.** Wymagałaby zapytania na każde
  wciśnięcie klawisza; przy 551 leadach niepotrzebne.

---

## Pliki

| Plik | Zmiana |
|---|---|
| `filtry.py` | **nowy** — parser chipów, zapis w URL, zakresy, dopasowanie w Pythonie |
| `repo.py` | `_warunek_osob` (chipy → WHERE), `osoby` i `osoby_tryb` w filtrze; parser wzięty z `filtry.py` |
| `db.py` | `pl_fold` + rejestracja jako funkcja SQLite w `get_conn()` |
| `calendar_view.py` | filtr w `build_matrix` / `build_agenda` / `build_starty`, `_ile_kolizji` |
| `dostepnosc_view.py` | `_widoczni_trenerzy`, liczniki liczone po widocznych |
| `app.py` | `_chipy_grafiku` (+ zgodność ze starym `?trener=`), `ZAKRESY` w kontekście szablonów |
| `templates/_makra.html` | makra `pasek_chipow`, `pasek_osob`, `href_zakres`; legenda |
| `templates/kalendarz.html`, `dostepnosc.html` | pasek chipów, „Wyczyść", zdjęta lista trenerów, etykieta roli na kafelku |
| `templates/baza.html`, `leady.html`, `zbiorczy.html` | zakładki niosą filtr |
| `static/filtr_osob.js` | **nowy** — dodawanie/wyłączanie/przypinanie chipów; zakresy z `data-*` |
| `static/style.css` | zmienne `--filtr` / `--fill`, pasek filtrów, chipy, komórki „wypełnij" |
| `templates/base.html` | podpięcie `filtr_osob.js` |
| `test_filtr_osob.py` | **nowy** — 88 sprawdzeń (O1–O7 listy leadów, G1–G4 grafik) |

Testy: `python test_filtr_osob.py`. Pozostałe cztery zestawy (93 + 67 + 24 + 30)
przechodzą bez zmian.
