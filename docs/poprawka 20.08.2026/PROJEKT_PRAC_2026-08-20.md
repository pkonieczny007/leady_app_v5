# Projekt prac na gałęzi `poprawki-2026-08` — po testach Kasi

Materiał źródłowy: `POPRAWKI 20.08.2026-work\kontekst\kontekst.txt` (czat 18–20.08),
uporządkowany w `ZGLOSZENIA_KASI_2026-08-20.html` jako pozycje **K01–K22**.
Ten plik zamienia je na **paczki roboczej** z numerami **P01–P21** i kolejnością.

Rejestr do odhaczania: `REJESTR_POPRAWEK_2026-08.md`.
Pytania blokujące: `PYTANIA_DO_KASI_2026-08-20.md`.

---

## 1. Co sprawdziłem w kodzie i w danych, zanim to napisałem

Opis zgłoszeń był w kilku miejscach interpretacją. Poniżej to, co zostało
**potwierdzone w kodzie albo w bazie** — i co przez to zmienia plan.

| Ustalenie | Dowód | Skutek dla planu |
|---|---|---|
| **K01 jest większa, niż wyglądała.** `PATCH /api/lead/<id>` nie ma **żadnego** sprawdzenia właściciela, a wśród pól edytowalnych są `handlowiec` i `deadline` | [app.py:723](../../app.py#L723), `LEAD_KEYS` w [db.py:133](../../db.py#L133) | To nie „edycja cudzych danych", tylko **przejęcie cudzego leada i przedłużenie sobie terminu**. Auto-zwrot da się obejść jednym żądaniem. Idzie pierwsze i osobno na produkcję |
| **K02 najprawdopodobniej NIE jest dziurą w kodzie.** Trener nie wejdzie na `/baza` na dwóch niezależnych poziomach: `baza` jest w `TYLKO_KOORDYNATOR` i endpoint nie jest w `DOZWOLONE_TRENER` | [app.py:69-90](../../app.py#L69-L90) | Zanim ruszymy kod — **sprawdzić rolę konta Zuzy na produkcji**. Jeśli ma rolę handlowca albo koordynatora, to poprawka trwa minutę i jest w danych, nie w kodzie |
| **K09 potwierdzona i zlokalizowana co do linii.** Autouzupełnianie ma warunek „wpisz tylko, jeśli pole puste" | `formularz2.js:154`, `formularz3.js:163`, `formularz4.js:250` | Poprawka jest mała, ale w **trzech plikach** — i to jest dokładnie ten typ błędu, który wraca. Test obowiązkowy |
| **K06 („żeby nie było tego słowa w nawiasie") ROZWIĄZANE — i to nie były dane.** W słowniku miast nie ma żadnej wartości z nawiasem; nawias dopisywał JS: `o.textContent + "  (twoje: 12)"` | `formularz2.js:97`, `formularz3.js:106`, `formularz4.js:193` | Słowo w nawiasie to **„twoje"**. To samo tłumaczy K04 („widzę tylko 12 szkół") — lista **nigdy** nie była zawężona, myliła etykieta. K06 i K04 to jedna poprawka (P06), słownika miast nie ruszamy, pytanie do Kasi odpada |
| **Gliwic, Mysłowic i Bytomia nie ma czego kasować** — są w słowniku miast, ale mają **zero placówek** | zapytanie do `placowki` | K07 to zdjęcie trzech pozycji ze słownika, nie migracja danych. Robota na minuty, nie na dzień |
| **`Nr RSPO` jest pusty dla wszystkich 545 placówek** | arkusz `Szkoły` w `POPRAWKA BAZY.xlsx` | Import z rejestru **nie ma po czym dopasować** istniejących rekordów. Dopasowanie musi iść po nazwie + miejscowości, z raportem do ręcznego przejrzenia. To największe ryzyko całej paczki bazy |
| **W bazie nie ma ani jednego przedszkola** (539 szkół podstawowych + 6 „Inna"), choć firma prowadzi w nich zajęcia | j.w. | Do potwierdzenia z Kasią przy zakresie RSPO — inaczej „poszerzenie bazy" doda szkoły, a przedszkola dalej będą puste |
| **`POPRAWKA BAZY.xlsx` jest pusta w kolumnach ✎** (0 z 545 wierszy, 0 z 34 miast) | j.w. | Paczka bazy **czeka na Kasię**. Nie zaczynamy jej „w międzyczasie" — bez tych odpowiedzi zaimportujemy nie to |
| **Pole `uwagi` już istnieje — ale na leadzie, nie na placówce** | `LEAD_KEYS` | K14 to nie „dodaj pole uwag", tylko „uwagi **trwałe przy placówce**, przeżywające zwrot leada do puli" |
| **Kalendarz przy pustej sesji wchodzi na `miesiace[-1]`** — ostatni miesiąc, w którym cokolwiek jest | [app.py:225](../../app.py#L225) | To **nie tłumaczy czerwca** (czerwiec jest w przeszłości). Podejrzenie: zapamiętany `session["miesiac"]` z wcześniejszego kliknięcia. Do odtworzenia **na demo**, na kopii produkcji — teraz mamy na czym |

Dwie rzeczy, których w materiale **nie ma i trzeba je dobrać**: zrzuty ekranu,
które Kasia załączała (`image_2026-08-18_13-39-36.png`, `image.png`) — bez nich
K06 i K18 („w karcie też coś dziwnego") zostają zgadywaniem.

---

## 2. Zasada podziału na paczki

Jedna wielka gałąź ze wszystkim naraz to najprostszy sposób na utopienie tygodnia:
poprawka literówki utknie za przebudową kont. Dlatego:

- **Każda paczka to osobna, krótka gałąź** odbita od `poprawki-2026-08`,
  scalana z powrotem `--no-ff` po testach.
- **Paczka A idzie na produkcję nie czekając na resztę** (cherry-pick), bo to
  dziura w uprawnieniach, a nie niewygoda.
- **Paczki D i E nie zaczynają się, dopóki nie wróci odpowiedź od Kasi.**
  Czekanie jest tańsze niż zaimportowanie nie tych danych do bazy, w której
  pracuje pięcioro ludzi.
- Po każdej paczce: komplet testów → `git push` → `wdroz.sh demo` → wiadomość
  do Kasi z **numerami P i nazwą ekranu**, nie „wrzuciłem poprawki".

---

## 3. Paczka A — uprawnienia (BLOKER, idzie pierwsza i osobno)

Gałąź: `poprawki/A-uprawnienia`

### P01 · Właściciel przy zapisie leada i placówki (K01)

Dziś każdy zalogowany handlowiec może zmienić dowolne pole dowolnego leada
i dowolnej placówki — sprawdzenia właściciela nie ma w ogóle. Blokada istnieje
wyłącznie w interfejsie, czyli na tym poziomie, który nic nie blokuje.

Do zrobienia w `api_lead_update`:
- handlowiec zapisuje **wyłącznie na leadzie, którego jest właścicielem**;
  na cudzym dostaje 403 z czytelnym komunikatem (nie „Brak uprawnień", tylko
  „Ten lead prowadzi <nazwisko> — poproś koordynatora o przepisanie");
- koordynator bez zmian;
- **podgląd zostaje** — Kasia chce widzieć, „kto miał wcześniej leada" (K14),
  więc odbieramy zapis, nie widok.

### P02 · `handlowiec` i `deadline` tylko dla koordynatora (K01)

Osobno od P01, bo to inna klasa problemu: te dwa pola są na liście edytowalnych,
więc handlowiec może **przypisać sobie cudzą szkołę** i **przedłużyć sobie termin**.
Drugie kasuje sens auto-zwrotu, który jest jednym z filarów całej aplikacji, i robi
to bez śladu odróżnialnego od zwykłej pracy.

Do zrobienia: obie zmiany wyłącznie ścieżką koordynatora (`api_przypisz`,
`api_przedluz`), a w `api_lead_update` twarda odmowa dla nie-koordynatora.

### P03 · Rola konta Zuzy na produkcji (K02) — *sprawdzenie, nie kod*

Najpierw `SELECT osoba, rola FROM uzytkownicy` na produkcji. Jeśli Zuza ma rolę
handlowca albo koordynatora — to jest cała przyczyna i poprawka trwa minutę.
Dopiero gdyby miała rolę trenera, zaczynamy szukać w kodzie.

Przy okazji: przejrzeć **wszystkie 49 kont** pod kątem ról i dać Kasi listę
do potwierdzenia (wchodzi w P17).

**Testy paczki A:** `test_logowanie.py`, `test_serwis.py`, `test_trener.py`,
`test_filtr_osob.py` + **nowe sprawdzenia**: handlowiec PATCH-uje cudzy lead → 403;
handlowiec PATCH-uje pole `handlowiec` → 403; handlowiec PATCH-uje `deadline` → 403.
Bez tych trzech testów poprawka wróci przy pierwszej refaktoryzacji.

---

## 4. Paczka B — błędy widoczne przy każdym użyciu

Gałąź: `poprawki/B-drobne`. Wszystkie cztery są małe, wszystkie rzucają się
w oczy przy każdym wejściu do aplikacji.

### P04 · Zmiana szkoły zostawia dane kontaktowe poprzedniej (K09)

Skutek jest gorszy niż pusta rubryka: do bazy wchodzi **cudzy mail przy dobrej
szkole** i nikt tego nie zauważy. Warunek `if (!pole.value)` znika, ale zgodnie
z zasadą „ostrzegamy, nie blokujemy": nadpisujemy i pokazujemy informację
„dane kontaktowe podmienione na te ze szkoły X". Trzy pliki: `formularz2.js`,
`formularz3.js`, `formularz4.js` — plus sprawdzenie, czy v1 (`formularz.js`)
ma ten sam wzorzec.

### P05 · Kalendarz otwiera się na złym miesiącu (K11)

Najpierw **odtworzyć na demo** (mamy kopię produkcji): czy to zapamiętany
`session["miesiac"]`, czy `miesiace[-1]`. Reguła docelowa do ustalenia z Kasią
(pytanie 6), ale domyślnie: bieżący miesiąc, a jeśli nic w nim nie ma —
najbliższy przyszły z wpisami. Zapamiętany wybór przestaje wygrywać, gdy
wskazuje **miesiąc w przeszłości**.

### P06 · Filtr „moje szkoły" ma być widoczny, nie domyślany (K04)

Mechanizm działa zgodnie z projektem — i mimo to zgłoszenie jest trafne.
W `CLAUDE.md` stoi wprost: „ukryty filtr wygląda jak brakujące dane i po dwóch
dniach ktoś zgłasza, że aplikacja pogubiła rekordy". Stało się to u samej
koordynatorki, czyli plakietki albo nie ma na tym ekranie, albo jest niewidoczna.

Do zrobienia: przy **samej liście szkół** (nie w rogu ekranu) jawny komunikat
„widzisz 12 z 545 — filtr: moje szkoły · [pokaż wszystkie]".
Osobno do rozstrzygnięcia: czy koordynator ma ten filtr włączony domyślnie —
handlowiec tak, ale koordynatorka z definicji pracuje na całości (pytanie 5).

### P07 · Wyszukiwanie po numerze szkoły (K08)

„SP 12 Katowice" wpisane z klawiatury zamiast przewijania listy. Numer siedzi
w nazwie („Szkoła Podstawowa nr 12"), więc wpisanie samego „12" musi trafiać —
dopasowanie po fragmencie nazwy **i** po mieście naraz.

**Testy paczki B:** `test_formularz.py` (P04 — obowiązkowo, po jednym sprawdzeniu
na wariant), `test_scenariusze.py` (P05), `test_filtr_osob.py` (P06).

---

## 5. Paczka C — kalendarz i obsada DT

Gałąź: `poprawki/C-kalendarz`. **P10 i P11 czekają na odpowiedź Kasi** (pytania
1 i 2) — P08 i P09 można robić od razu.

### P08 · Odwołanie DT ze śladem (K12)

Dziś nie da się usunąć wpisu z kalendarza, więc odwołany DT albo wisi martwy,
albo ktoś go przestawia „na lewo", żeby zniknął z widoku.

Robimy **odwołanie, nie kasowanie**: status „odwołane" + powód + kto i kiedy.
Wpis znika z grafiku, zostaje w historii i w raporcie z P20 („ile się nie udało").
Twarde kasowanie zostaje **wyłącznie dla koordynatora** i wyłącznie dla wpisów
oczywiście błędnych (P09).

### P09 · Sprzątnięcie śmieci po prezentacji (K18) — *dane*

DT „Paziewski" wpisany przy testach 06.08 wisi na produkcji. Przy okazji:
przejrzeć wpisy z dnia prezentacji i **dać Kasi listę do potwierdzenia**, zanim
cokolwiek zniknie. Zależy od P08 (dziś nie ma czym usunąć).

Możliwy związek z P05: jeden zabłąkany wpis w martwym miesiącu potrafi
przeciągnąć domyślny widok kalendarza.

### P10 · Wolne miejsca na DT (K13) — *czeka na odpowiedź*

Kasia opisała sytuację, nie rozwiązanie: „zrób WOLNEGO TRENERA i to nawet 3 razy".
Moja propozycja: **nie konta** (kolejne PIN-y to dokładnie to, na co narzeka
w K16), tylko **N nieobsadzonych miejsc na evencie**, każde widoczne osobno
w grafiku, a trener klika „biorę". Dzisiejszy jeden wiersz „— bez prowadzącego —"
zlewa wszystkie takie zajęcia w jedną kupę.

### P11 · Drugi trener: prowadzący praktyki + praktykant (K10) — *czeka*

Ten sam kawałek kodu co P10 (macierz grafiku, gdzie wiersz = trener, a event ma
dziś jednego prowadzącego), dlatego **robimy je razem albo wcale**. Wpis ma być
widoczny w kalendarzu **obu** trenerów.

---

## 6. Paczka D — baza szkół, powiaty, RSPO (czeka na Kasię)

Gałąź: `poprawki/D-baza`. **Nie zaczynamy, dopóki nie wróci `POPRAWKA BAZY.xlsx`.**
To najgrubsza rzecz na liście i wchodzi w drogę wszystkiemu innemu.

Kolejność wewnątrz paczki jest wymuszona, nie estetyczna:

1. **P14 · zdjąć Gliwice, Mysłowice, Bytom ze słownika miast** (K07) — zero
   placówek, więc to trzy wiersze w słowniku. Robi się pierwsze, bo zmniejsza
   zakres importu.
2. **P13 · kolumna `powiat` na placówce + filtr** (K05) — dokładanie kolumny jest
   tanie (`db.migruj()` robi to przy starcie). Wartości: dla nowych z rejestru
   RSPO za darmo, dla obecnych 545 — z arkusza `Miasta` (kolumna „POWIAT
   (propozycja)" jest już wypełniona, czeka na potwierdzenie Kasi).
   Filtr powiatu wchodzi na „Bazę", „Moje szkoły" i do formularza.
3. **P12 · import brakujących gmin z RSPO** (K03) — Czeladź, Miedźna, Frydek,
   Góra, Wyry, Gostyń, Ornontowice + ewentualnie Tarnowskie Góry.
   **Uwaga krytyczna:** `Nr RSPO` jest pusty dla wszystkich 545 obecnych
   placówek, więc import nie ma po czym rozpoznać duplikatu. Dopasowanie idzie
   po nazwie + miejscowości, a **raport dopasowania trzeba przejrzeć ręcznie
   przed zapisem**. Próba generalna na demo ze świeżą kopią produkcji, liczby
   przed/po, dopiero potem produkcja.
4. **P16 · uwagi trwałe przy placówce + „kto miał leada wcześniej"** (K14).
   Pole `uwagi` istnieje, ale **na leadzie** — czyli znika z pola widzenia, gdy
   lead wraca do puli. Kasia chce czegoś odwrotnego: adnotacji, która przeżywa
   zwrot („dlaczego odpuszczamy w tym roku"). Do tego przy plakietce „wróciła do
   puli" dopisać „ostatnio: <nazwisko>, zwrot <data>" — te dane **już są**
   w historii zmian, brakuje ich tylko na ekranie.
5. **P15 · „słowo w nawiasie"** (K06) — dopóki nie wiemy, o co chodzi, nie
   dotykamy słownika miast.

**Kontrola przed wyjściem na produkcję:** czy 545 obecnych placówek się nie
zdublowało, czy przypisania handlowców i terminy DT przetrwały, czy „Baza"
i „Moje szkoły" są jeszcze użyteczne przy nowej skali (handlowiec ma dziś 159
przypisanych szkół — po poszerzeniu może mieć wielokrotnie więcej).

---

## 7. Paczka E — konta i role (przebudowa, na końcu)

Gałąź: `poprawki/E-konta`.

### P17 · Administrator to tylko Kasia i Julia (K17) — *dane, szybkie*

Zmienia ustalenie z 08.08 („koordynatorki Kasia + Weronika"). Weronika ma być
zdjęta z uprawnień administracyjnych — ale **co jej zostaje, nie wiadomo**
(prowadzi szkolenie trenerów z DT, więc kalendarza potrzebuje). O Przemku Kasia
nie wspomina, a on ma konto koordynatora — milczenie to nie to samo co „usunąć".
Pytania 8 i 9.

### P18 · Jeden PIN, przełączanie roli w środku (K16) — *przebudowa*

Punkt 8 z podsumowania Kasi („przelogowanie PH jako trener") i ta pozycja to
**jedno zadanie**. To zmiana modelu, nie poprawka: dziś **tożsamość = konto = rola**,
a Kasia chce **tożsamość → wiele ról**.

Czego to wymaga, zanim padnie pierwsza linia kodu:
- tabeli mapowania **stare konto → nowa tożsamość + role**, wypełnionej
  i zatwierdzonej przez Kasię (49 kont);
- rozstrzygnięcia, **czyje nazwisko ląduje w historii zmian** — dziś właściciel
  wpisu bierze się z sesji i to jest podstawa kontroli „kto ruszył lead przed
  terminem" (a po P01 także podstawa uprawnień);
- decyzji o PIN-ach: **PIN-ów nie da się odczytać** (PBKDF2 z solą), więc przy
  scaleniu trzech kont w jedno dwa PIN-y przestają działać i te osoby dostają
  nową kartę dostępu.

Testy: `test_logowanie.py`, `test_serwis.py`, `test_trener.py`, `test_filtr_osob.py`
w komplecie — uprawnienia siedzą w **trzech warstwach**, ukrycie przycisku
nie jest zmianą uprawnień.

### P19 · Wymiana PIN-u koordynatora (K22) — *higiena*

PIN koordynatora do produkcji przeszedł czatem i wisi w historii rozmowy, którą
teraz kopiujemy po plikach roboczych. Do wymiany w `/uzytkownicy`. Najlepiej
razem z P18 — i tak część osób dostanie nowe PIN-y, więc jeden druk kart zamiast
dwóch.

---

## 8. Paczka F — raport wykonania (po paczce D)

### P20 · Raport wykonania każdego handlowca (K15)

Siedem liczb, z czego **trzy nie dadzą się policzyć przed paczką D**:
„ile szkół w danych terenach" potrzebuje powiatu (P13) i pełnej bazy (P12),
„ile odpuściliśmy celowo" potrzebuje pola uwag/statusu odpuszczenia (P16).

Raport zrobiony wcześniej pokaże liczby, które za tydzień będą znaczyć co innego —
a raporty ogląda się raz i zapamiętuje. Dlatego **po D, nie przed**.

---

## 9. Poza aplikacją PH

### P21 · Eksport DT dla appki Zuzi (K19)

Lista pól jest gotowa (nazwa szkoły, godzina, adres, telefon, obsada, rodzaj sali).
Dwie rzeczy do sprawdzenia przed obietnicą terminu:
- czy pole **„sala komputerowa czy nasze laptopy"** w ogóle jest w bazie
  (jest słownik `sprzet` z trzema pozycjami — trzeba sprawdzić, czy event go używa).
  Jeśli nie, to nowa kolumna **i nowe pytanie w formularzu**, czyli osobna poprawka;
- czy w pliku mają być **telefony do szkół** — to dane osobowe wychodzące poza PH.

Ustalenie na dziś: **Paweł wyciąga ręcznie do folderu**, to jednorazowy eksport,
nie integracja. Trzymamy to jako świadomą decyzję, żeby nie rozrosło się w API
„przy okazji".

**K20 (moduł zastępstw) i K21 (kalendarz DT u Zuzi) nie są naszą robotą** —
zapisane, żeby przy P10 i P11 nikt nie zaczął budować zastępstw u nas. To
naturalny odruch, bo grafik trenerów już tu stoi.

Jedyny **zewnętrzny termin** na całej liście to szkolenie trenerów, na którym
Weronika ma pokazać kalendarz DT. Bez daty tego szkolenia nie da się sensownie
ułożyć priorytetów reszty (pytanie 10).

---

## 10. Kolejność i co kiedy ląduje na demo

| Krok | Paczka | Zależy od | Na demo |
|---|---|---|---|
| 1 | A — uprawnienia | — | od razu, **i osobno na produkcję** |
| 2 | B — drobne błędy | — | razem z A albo zaraz po |
| 3 | C — P08, P09 (odwołanie DT, śmieci) | — | po B |
| 4 | **pytania do Kasi** | — | *wysłane równolegle z krokiem 1* |
| 5 | D — baza | odpowiedzi + `POPRAWKA BAZY.xlsx` | po odpowiedziach |
| 6 | C — P10, P11 (obsada DT) | odpowiedź na pytanie 1 i 2 | po odpowiedziach |
| 7 | E — konta | tabela mapowania od Kasi | na końcu |
| 8 | F — raport | paczka D | na samym końcu |

Przed każdą rundą testów Kasi na demo: **`./narzedzia/odswiez_demo.sh`** —
demo starzeje się od pierwszej minuty, a ona ma testować na tym, co widzi
u siebie w pracy.

---

## 11. Czego w tej rundzie świadomie NIE robimy

| Nie robimy | Dlaczego |
|---|---|
| Przebudowy kont w tej samej gałęzi co reszta | to zmiana modelu; utknie na niej wszystko inne |
| Importu RSPO przed odpowiedzią Kasi | `Nr RSPO` jest pusty w bazie — bez ręcznej kontroli dopasowania zdublujemy placówki |
| Kasowania placówek z Gliwic/Mysłowic/Bytomia | nie ma czego kasować, są tylko w słowniku |
| Raportu przed paczką bazy | pokaże liczby, które za tydzień znaczą co innego |
| Modułu zastępstw | ustalone: to appka Zuzi |
| Twardego kasowania wpisów kalendarza dla wszystkich | odwołanie ze śladem, kasowanie tylko koordynator — inaczej znika historia potrzebna do raportu |
| Zmian w `data/prod` lokalnie | to nieaktualna atrapa z 10.08; pracujemy na `PROFIL=test` zasianym kopią produkcji |
