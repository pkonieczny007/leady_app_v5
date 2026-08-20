/* =============================================================================
   WARIANT CYKLICZNY formularza — cały v3 plus planowanie zajęć powtarzalnych.

   Obsługa placówki i Dnia Technologii jest identyczna jak w v3 (podpowiedź
   prowadzącego, cztery kategorie, podgląd dnia). Zapisuje przez to samo API
   (`/api/formularz`), tą samą walidacją i z tą samą ochroną przed dublem.

   NOWE JEST TO, CO NIŻEJ — SEKCJA TERMINÓW

   Cykl dawało się dotąd zapisać wyłącznie regułą „co wtorek, w nieskończoność".
   Przedszkola umawiają inaczej: pakiet konkretnych spotkań, których daty
   wypadają jak wypadają. Stąd drugi sposób — lista dat.

   ZASADA PRZELICZANIA (całe sedno tej sekcji)

     Zmiana terminu na TEN SAM dzień tygodnia  → przeliczamy wszystkie następne.
       Znaczenie: przesunął się CAŁY cykl („zacznijmy tydzień później").
     Zmiana terminu na INNY dzień tygodnia     → następne zostają bez ruchu.
       Znaczenie: wyjątek na JEDNO spotkanie („w ten wtorek mamy
       przedstawienie, zróbmy w środę") — reszta pakietu trzyma swój rytm.

   Bez tego rozróżnienia poprawka jednej daty albo rozwalała resztę pakietu,
   albo kazała poprawiać ręcznie wszystkie kolejne. Zgadywanie, o którą
   z dwóch rzeczy chodzi, jest tutaj tanie i trafne, bo dzień tygodnia niesie
   dokładnie tę informację.

   PROPOZYCJA TO NIE USTALENIE. Daty wyliczone przez aplikację są oznaczone
   i podpisane jako propozycje. Wypełnione pole daty wygląda jak uzgodnione
   z placówką, a nie jest — dopóki handlowiec go nie potwierdzi.

   OSTRZEGAMY, NIE BLOKUJEMY — zasada z całego projektu.
   ============================================================================= */

/* =============================================================================
   FxCykl — REGUŁA SERII, bez DOM-u i bez stanu.

   Wydzielone z modułu niżej celowo. Reguła „ten sam dzień tygodnia przelicza
   ogon, inny nie" to jedyne miejsce w tym pliku, gdzie da się pomylić
   rachunek, a jednocześnie jedyne, którego nie widać na ekranie: efekt zmiany
   widać dopiero w kalendarzu, tydzień później. Jako czysta funkcja daje się
   sprawdzić (`node test_cykl.js`) zamiast wyklikiwać.
   ============================================================================= */
var FxCykl = (function () {
  "use strict";

  /* Daty liczymy w UTC. Na `new Date("2026-10-25")` w strefie z czasem letnim
     dodanie 7 dni potrafi dać przesunięcie o godzinę, a po zamianie z powrotem
     na tekst wychodzi dzień wcześniej. W Polsce zegar cofa się pod koniec
     października — czyli dokładnie w środku sezonu zajęć. */
  function naDate(iso) {
    var d = new Date(String(iso) + "T00:00:00Z");
    return isNaN(d.getTime()) ? null : d;
  }

  function przesun(iso, dni) {
    var d = naDate(iso);
    if (!d) return "";
    d.setUTCDate(d.getUTCDate() + dni);
    return d.toISOString().slice(0, 10);
  }

  function dzienTyg(iso) {
    var d = naDate(iso);
    return d ? d.getUTCDay() : -1;
  }

  /* Propozycja całej serii: `ile` terminów co `krok` tygodni od `start`. */
  function seria(start, ile, krok) {
    var out = [];
    for (var i = 0; i < ile; i++) out.push(przesun(start, 7 * krok * i));
    return out;
  }

  /*
    Zmiana jednego terminu. Zwraca { terminy, przeliczone }.

      ten sam dzień tygodnia → przesunął się CAŁY cykl, przeliczamy następne
      inny dzień tygodnia    → wyjątek na JEDNO spotkanie, następne bez ruchu

    `terminy` to tablica obiektów z polami `data` i `reczna`; zwracamy NOWĄ
    tablicę, żeby wywołujący nie zależał od tego, czy modyfikujemy w miejscu.
  */
  function zmien(terminy, i, noweISO, krok) {
    var out = terminy.map(function (t) { return { data: t.data, reczna: t.reczna }; });
    if (!out[i]) return { terminy: out, przeliczone: 0 };
    var stareISO = out[i].data;
    out[i].data = noweISO;
    out[i].reczna = true;
    if (!noweISO || !stareISO || dzienTyg(noweISO) !== dzienTyg(stareISO)) {
      return { terminy: out, przeliczone: 0 };
    }
    var n = 0;
    for (var j = i + 1; j < out.length; j++) {
      // Ogon staje się z powrotem propozycją — bo właśnie go wyliczyliśmy.
      out[j].data = przesun(noweISO, 7 * krok * (j - i));
      out[j].reczna = false;
      n++;
    }
    return { terminy: out, przeliczone: n };
  }

  return { przesun: przesun, dzienTyg: dzienTyg, seria: seria, zmien: zmien };
})();

if (typeof module !== "undefined" && module.exports) module.exports = FxCykl;

(function () {
  "use strict";

  // Plik wczytany bez przeglądarki (`node test_cykl.js` sprawdza samo FxCykl).
  // Bez tego samo `require` wywala się na `document`, zanim dojdzie do testów.
  if (typeof document === "undefined") return;

  function tokenCsrf() {
    var m = document.querySelector('meta[name="csrf"]');
    return m ? m.content : "";
  }

  var root = document.getElementById("f2");
  if (!root) return;

  // Osobne klucze niż v2 i v3 — inaczej szkic zaczęty w jednym wariancie
  // wskakiwałby do drugiego i porównanie wariantów przez klienta robiłoby się
  // mętne. Tu dochodzi drugi powód: ten wariant trzyma w szkicu listę terminów,
  // której pozostałe nie umieją odczytać.
  var KLUCZ_SZKICU = "f4-szkic-v1";
  var POWROT = "/formularz/cykliczne";
  var $ = function (id) { return document.getElementById(id); };

  var stan = {
    handlowiec: root.dataset.handlowiec || "",
    wybrana: null,
    nowa: false
  };

  var moje = window.FX_MOJE || [];

  // Obsługa awarii (szkic, ostrzeżenie przy wyjściu, kolejka „niewysłane")
  // siedzi w formularz_awaria.js — jest wspólna dla obu wariantów.
  var awaria = null;
  var zapisano = false;

  /* ------------------------------------------------------------ pomocnicze */

  var toastEl = null, toastTimer = null;
  function toast(tekst, blad) {
    if (!toastEl) toastEl = document.getElementById("toast");
    if (!toastEl) { alert(tekst); return; }
    toastEl.textContent = tekst;
    toastEl.classList.toggle("err", !!blad);
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); },
                            blad ? 6000 : 2500);
  }

  function api(metoda, url, dane) {
    var o = { method: metoda, headers: { "X-CSRF": tokenCsrf() } };
    if (dane !== undefined) {
      o.headers["Content-Type"] = "application/json";
      o.body = JSON.stringify(dane);
    }
    return fetch(url, o).then(function (r) {
      return r.json().catch(function () { return { ok: r.ok }; }).then(function (j) {
        if (!r.ok || j.ok === false) throw new Error(j.error || ("Błąd " + r.status));
        return j;
      });
    });
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ================================================ MIEJSCOWOŚĆ → PLACÓWKA */

  var selMiasto = $("f2-miasto");
  var selSzkola = $("f2-szkola");
  var infoSzkola = $("f2-szkola-info");
  var indeks = {};                     // placowka_id → pełny rekord

  // Miasta, w których handlowiec ma przydzielone szkoły, oznaczamy w liście —
  // w 90% przypadków wypełnia formularz właśnie dla jednej z nich.
  (function oznaczMojeMiasta() {
    if (!moje.length) return;
    var licz = {};
    moje.forEach(function (m) {
      if (m.miejscowosc) licz[m.miejscowosc] = (licz[m.miejscowosc] || 0) + 1;
    });
    Array.prototype.forEach.call(selMiasto.options, function (o) {
      // Gwiazdka, a NIE „(twoje: 12)". Kasia czytała ten dopisek jako liczbę
      // szkół w mieście: „w Katowicach pojawiają się tylko moje 12 szkół, nie
      // ma całej listy placówek" — i prosiła wprost, żeby nie było tego słowa
      // w nawiasie. Gwiazdka to ten sam znak co przy szkołach na liście,
      // więc znaczy dokładnie to samo i nie da się jej wziąć za licznik.
      if (licz[o.value]) o.textContent = "★ " + o.textContent;
    });
  })();

  /* P07 (zgłoszenie K08 Kasi, 20.08): „jedno pole jest potrzebne w wyszukiwaniu
     sam numer szkoły jak wpiszę miasto i numer że mi przefiltruje a nie szukam
     na liscie".

     Filtrujemy to, co JUŻ wczytaliśmy dla wybranej miejscowości — bez pytania
     serwera. Dzięki temu reaguje z każdym znakiem, także wtedy, gdy zasięg
     w szkolnym korytarzu ledwie starczył na jedno żądanie. */
  var poleSzukaj = $("f2-szkola-szukaj");
  var wczytane = [];                   // placówki ostatnio wybranej miejscowości

  function bezOgonkow(s) {
    return (s || "").toLowerCase()
      .replace(/ą/g, "a").replace(/ć/g, "c").replace(/ę/g, "e").replace(/ł/g, "l")
      .replace(/ń/g, "n").replace(/ó/g, "o").replace(/ś/g, "s").replace(/[żź]/g, "z");
  }

  function pasuje(p, fraza) {
    var nazwa = bezOgonkow(p.nazwa);
    // KAŻDY człon musi trafić, więc „sp 12" zawęża mocniej niż samo „12",
    // a numer da się wpisać osobno — dokładnie o to prosiła Kasia.
    return bezOgonkow(fraza).split(/\s+/).every(function (czesc) {
      return !czesc || nazwa.indexOf(czesc) >= 0;
    });
  }

  function rysujSzkoly() {
    var fraza = poleSzukaj ? (poleSzukaj.value || "").trim() : "";
    var lista = fraza ? wczytane.filter(function (p) { return pasuje(p, fraza); }) : wczytane;
    var bylo = selSzkola.value;
    // Wybrana szkoła zostaje na liście, nawet gdy wypadła z filtra. Inaczej
    // select po cichu gubi wybór, a formularz dalej go pamięta i zapisuje.
    if (bylo && indeks[bylo] && lista.indexOf(indeks[bylo]) < 0) {
      lista = [indeks[bylo]].concat(lista);
    }
    var moich = 0;
    var html = '<option value="">Wybierz szkołę z listy</option>';
    lista.forEach(function (p) {
      if (p.moja) moich++;
      html += '<option value="' + p.placowka_id + '">' + esc(p.nazwa) +
              (p.moja ? "  ★" : "") + "</option>";
    });
    selSzkola.innerHTML = html;
    selSzkola.disabled = !wczytane.length;
    if (bylo) selSzkola.value = bylo;

    if (!wczytane.length) {
      infoSzkola.textContent = "Brak placówek w tej miejscowości — dodaj nową poniżej.";
    } else if (fraza) {
      infoSzkola.textContent = lista.length + " z " + wczytane.length +
        " pasuje do wpisanego tekstu";
    } else {
      /* P06 (zgłoszenie K04): „na liście miast przy wpisywaniu DT katoice
         pojawiają się tylko jako moje 12 szkół, nie ma całej listy plaówek".
         Lista NIGDY nie była zawężona do własnych szkół — mylił dopisek przy
         nazwie miasta. Mówimy więc wprost, że to cała baza miejscowości:
         ukryte zawężenie wygląda jak brakujące dane. */
      infoSzkola.textContent = wczytane.length + " szkół w tej miejscowości — cała baza" +
        (moich ? ", twoich " + moich + " ★" : "");
    }
  }

  if (poleSzukaj) poleSzukaj.addEventListener("input", rysujSzkoly);

  function wczytajSzkoly(miasto, poWczytaniu) {
    if (!miasto) {
      selSzkola.innerHTML = '<option value="">Najpierw wybierz miejscowość</option>';
      selSzkola.disabled = true;
      infoSzkola.textContent = "";
      if (poleSzukaj) poleSzukaj.hidden = true;
      return;
    }
    selSzkola.disabled = true;
    selSzkola.innerHTML = '<option value="">Wczytuję…</option>';
    api("GET", "/api/placowki?miejscowosc=" + encodeURIComponent(miasto) +
               "&handlowiec=" + encodeURIComponent(stan.handlowiec))
      .then(function (j) {
        indeks = {};
        // szkoły handlowca na górze, reszta alfabetycznie
        j.pozycje.sort(function (a, b) {
          if (a.moja !== b.moja) return a.moja ? -1 : 1;
          return a.nazwa.localeCompare(b.nazwa, "pl");
        });
        j.pozycje.forEach(function (p) { indeks[p.placowka_id] = p; });
        wczytane = j.pozycje;
        if (poleSzukaj) {
          poleSzukaj.value = "";
          poleSzukaj.hidden = !wczytane.length;
        }
        rysujSzkoly();
        if (poWczytaniu) poWczytaniu();
      })
      .catch(function (e) {
        selSzkola.innerHTML = '<option value="">Nie udało się wczytać</option>';
        infoSzkola.textContent = e.message;
      });
  }

  selMiasto.addEventListener("change", function () {
    stan.wybrana = null;
    wczytajSzkoly(selMiasto.value);
    odswiezDostepnosc();
    zapiszSzkic();
  });

  /* Dane kontaktowe podpowiadamy z bazy — handlowiec ma je POPRAWIĆ, a nie
     wpisywać od zera przy każdym spotkaniu.

     P04 (zgłoszenie K09 Kasi, 20.08): przy ZMIANIE szkoły pola zostawały
     wypełnione danymi poprzedniej — „wybrałam z listy szkołę, uzupełniły się
     dane typu osoba do kontaktu, a potem zmieniłam szkołę, to osoba się nie
     zmieniła". Skutek jest gorszy niż pusta rubryka: do bazy wchodzi cudzy
     mail przy dobrej szkole i nikt tego nie zauważy.

     Nadpisujemy więc ZAWSZE, także pustą wartością — szkoła bez kontaktu ma
     pole wyczyścić, a nie odziedziczyć poprzednie — i mówimy o tym, zgodnie
     z zasadą projektu: ostrzegamy, nie blokujemy. */
  function podstawKontakt(szkola) {
    var mapa = [["f2-osoba", "osoba_kontakt"],
                ["f2-telefon", "telefon"],
                ["f2-mail", "mail"]];
    var podmiana = false;
    for (var i = 0; i < mapa.length; i++) {
      var pole = $(mapa[i][0]);
      var nowa = (szkola && szkola[mapa[i][1]]) || "";
      // Komunikat należy się tylko wtedy, gdy coś WYPARŁO wpisaną wartość.
      // Pierwsze wypełnienie pustego formularza nie jest podmianą.
      if (pole.value && pole.value !== nowa) podmiana = true;
      pole.value = nowa;
    }
    return podmiana;
  }

  selSzkola.addEventListener("change", function () {
    stan.wybrana = indeks[selSzkola.value] || null;
    if (stan.wybrana) {
      stan.nowa = false;
      $("f2-nowa").hidden = true;
      if (podstawKontakt(stan.wybrana)) {
        toast("Dane kontaktowe podmienione na te ze szkoły z bazy — sprawdź je.");
      }
    }
    odswiezDostepnosc();
    zapiszSzkic();
  });

  // Wejście dla wspólnej sekcji „Plan na dziś" (fx_plan.js) — identyczne jak
  // w v2, bo wybór szkoły działa tu tak samo: dwie listy, druga doczytywana.
  window.FX_PLAN_WYBIERZ = function (p) {
    selMiasto.value = p.miejscowosc || "";
    wczytajSzkoly(selMiasto.value, function () {
      selSzkola.value = String(p.placowka_id);
      selSzkola.dispatchEvent(new Event("change"));
    });
  };

  $("f2-nowa-otworz").addEventListener("click", function () {
    stan.nowa = !stan.nowa;
    $("f2-nowa").hidden = !stan.nowa;
    this.textContent = stan.nowa
      ? "− Jednak wybieram z listy"
      : "+ Nie ma jej na liście — dodaj nową placówkę";
    if (stan.nowa) {
      stan.wybrana = null;
      selSzkola.value = "";
      $("f2-nowa-nazwa").focus();
    }
    zapiszSzkic();
  });

  /* ==================================================== DOSTĘPNOŚĆ TRENERÓW */

  var boxDost = $("f2-dostepnosc");
  var selTrener = $("f2-dt-trener");
  var timerDost = null;

  var boxStatus = $("f3-status");
  var boxDzien = $("f3-dzien");
  var ostatniaOdpowiedz = null;      // ostatnia odpowiedź API — do statusu i dnia

  // Nazwy kategorii z `przydzial.py`. Kolejność ta sama co na serwerze:
  // od najbardziej użytecznej do najmniej.
  var KATEGORIE = [
    { klucz: "wolny", tytul: "Wolni", znak: "✅", otwarta: true },
    { klucz: "nieznany", tytul: "Bez deklaracji", znak: "○", otwarta: false },
    { klucz: "zastrzezenie", tytul: "Z zastrzeżeniem", znak: "⚠️", otwarta: false },
    { klucz: "niedostepny", tytul: "Niedostępni", znak: "⛔", otwarta: false }
  ];

  function odswiezDostepnosc() {
    var data = $("f2-dt-data").value;
    if (!data) {
      ostatniaOdpowiedz = null;
      boxDost.innerHTML = "Po wybraniu daty pokażemy, kto jest wolny. Rejon podbija " +
                          "kolejność na liście, ale nikogo nie ukrywa.";
      boxDzien.hidden = true;
      rysujStatus();
      return;
    }
    var miasto = selMiasto.value || "";
    boxDost.textContent = "Sprawdzam dostępność…";
    clearTimeout(timerDost);
    timerDost = setTimeout(function () {
      api("GET", "/api/kandydaci?data=" + encodeURIComponent(data) +
                 "&godz_od=" + encodeURIComponent($("f2-dt-od").value || "") +
                 "&godz_do=" + encodeURIComponent($("f2-dt-do").value || "") +
                 "&miasto=" + encodeURIComponent(miasto))
        .then(function (j) {
          ostatniaOdpowiedz = j;
          rysujDostepnosc(j, miasto);
          rysujDzien(j, data);
          rysujStatus();
        })
        .catch(function () {
          ostatniaOdpowiedz = null;
          boxDost.textContent = "Nie udało się sprawdzić dostępności — wybierz prowadzącego z listy.";
          boxDzien.hidden = true;
          rysujStatus();
        });
    }, 200);
  }

  function wszyscy(j) {
    var lista = [];
    ((j && j.grupy) || []).forEach(function (g) {
      (g.pozycje || []).forEach(function (k) { lista.push(k); });
    });
    return lista;
  }

  /* Godziny zajęcia. W pliku klienta z 08.08 większość DT nie ma wpisanej
     godziny (48 z 66 bez początku, 65 bez końca) — pusty nawias wyglądałby
     jak błąd aplikacji, a to brak w danych. Mówimy o tym wprost, bo dla
     handlowca umawiającego termin „nie wiadomo o której" to realna informacja. */
  function godziny(z) {
    if (!z.godz_od) return "godz. nieustalona";
    return z.godz_od + (z.godz_do ? "–" + z.godz_do : "");
  }

  function kafelTrenera(k) {
    // wolne okna i zajęcia — serwer je liczy, a v2 wyrzucał do kosza
    var szczegol = "";
    if (k.wolne && k.wolne.length) {
      szczegol = "wolne: " + k.wolne.join(", ");
    } else if (k.zajete && k.zajete.length) {
      szczegol = k.zajete.map(function (z) {
        return godziny(z) + " " + (z.typ || "") + (z.miasto ? " " + z.miasto : "");
      }).join(" · ");
    } else if (k.powod) {
      szczegol = k.powod;
    }
    return '<li><button type="button" data-trener="' + esc(k.trener) + '"' +
      ' class="f3-kand f3-kand-' + esc(k.kategoria) + '"' +
      ' title="' + esc(k.powod || "") + '">' +
      '<span class="f3-kand-imie">' + esc(k.trener) +
      (k.rejon ? ' <span class="f3-rejon">jeździ tu</span>' : "") + "</span>" +
      (szczegol ? '<span class="f3-kand-info">' + esc(szczegol) + "</span>" : "") +
      "</button></li>";
  }

  function rysujDostepnosc(j, miasto) {
    var lista = wszyscy(j);
    var wolnych = lista.filter(function (k) { return k.kategoria === "wolny"; }).length;

    // Bez godziny startu serwer NIE liczy kolizji ani wyjścia poza deklarację
    // (patrz przydzial._zakres_spotkania) — mówimy o tym wprost, zamiast
    // pokazywać ranking, który udaje pełną wiedzę.
    var bezGodziny = !$("f2-dt-od").value;

    var html = wolnych
      ? "<b>" + wolnych + "</b> " + odmiana(wolnych, "osoba wolna", "osoby wolne", "osób wolnych") +
        " tego dnia" + (miasto ? ", rejon <b>" + esc(miasto) + "</b>" : "")
      : "Nikt nie zadeklarował dostępności na ten dzień.";
    if (bezGodziny) {
      html += ' <span class="f3-uwaga-godzina">Podaj godzinę rozpoczęcia, ' +
              "żeby sprawdzić kolizje.</span>";
    }

    KATEGORIE.forEach(function (kat) {
      var grupa = lista.filter(function (k) { return k.kategoria === kat.klucz; });
      if (!grupa.length) return;
      html += '<details class="f3-grupa f3-grupa-' + kat.klucz + '"' +
              (kat.otwarta ? " open" : "") + ">" +
              "<summary>" + kat.znak + " " + kat.tytul +
              ' <span class="f3-licznik">' + grupa.length + "</span></summary>" +
              '<ul class="f2-dost-lista">' +
              grupa.map(kafelTrenera).join("") + "</ul></details>";
    });
    boxDost.innerHTML = html;
  }

  /* Status WYBRANEJ osoby — to jest główna różnica wobec v2. */
  function rysujStatus() {
    var kto = selTrener.value;
    if (!kto || !ostatniaOdpowiedz) {
      boxStatus.hidden = true;
      return;
    }
    var k = wszyscy(ostatniaOdpowiedz).filter(function (x) {
      return x.trener === kto;
    })[0];
    if (!k) { boxStatus.hidden = true; return; }

    var znak = { wolny: "✅", nieznany: "○", zastrzezenie: "⚠️", niedostepny: "⛔" };
    var tekst = k.powod || "";
    if (k.kategoria === "wolny" && k.wolne && k.wolne.length) {
      tekst += " · wolne: " + k.wolne.join(", ");
    }
    if (k.zajete && k.zajete.length) {
      tekst += " · tego dnia ma " + k.zajete.length + " " +
               odmiana(k.zajete.length, "zajęcie", "zajęcia", "zajęć");
    }
    boxStatus.className = "f3-status f3-status-" + k.kategoria;
    boxStatus.innerHTML = "<b>" + (znak[k.kategoria] || "") + " " + esc(kto) + "</b> — " +
                          esc(tekst);
    boxStatus.hidden = false;
  }

  /* „Co się dzieje tego dnia" — z tej samej odpowiedzi, bez nowego zapytania. */
  function rysujDzien(j, data) {
    var wpisy = [];
    wszyscy(j).forEach(function (k) {
      (k.zajete || []).forEach(function (z) {
        wpisy.push({ trener: k.trener, godz: z.godz_od || "", do: z.godz_do || "",
                     typ: z.typ || "", szkola: z.szkola || "", miasto: z.miasto || "" });
      });
    });
    if (!wpisy.length) {
      boxDzien.hidden = false;
      $("f3-dzien-tytul").textContent = "Co się dzieje " + data + " — nic w kalendarzu";
      $("f3-dzien-tresc").innerHTML =
        '<p class="f3-dzien-pusto">Tego dnia nikt nie ma jeszcze wpisanych zajęć.</p>';
      return;
    }
    wpisy.sort(function (a, b) { return (a.godz || "99:99").localeCompare(b.godz || "99:99"); });
    var bezGodzin = wpisy.filter(function (w) { return !w.godz; }).length;
    $("f3-dzien-tytul").textContent = "Co się dzieje " + data + " — " + wpisy.length + " " +
      odmiana(wpisy.length, "zajęcie", "zajęcia", "zajęć") +
      (bezGodzin ? " (" + bezGodzin + " bez godziny)" : "");
    $("f3-dzien-tresc").innerHTML = '<ul class="f3-dzien-lista">' + wpisy.map(function (w) {
      return "<li><span class=\"f3-dzien-godz" + (w.godz ? "" : " f3-brak-godz") + "\">" +
             esc(godziny({ godz_od: w.godz, godz_do: w.do })) + "</span>" +
             '<span class="f3-dzien-kto">' + esc(w.trener) + "</span>" +
             '<span class="f3-dzien-gdzie">' + esc(w.typ + " · " + w.szkola +
             (w.miasto ? " · " + w.miasto : "")) + "</span></li>";
    }).join("") + "</ul>";
    boxDzien.hidden = false;
  }

  function odmiana(n, jeden, kilka, wiele) {
    if (n === 1) return jeden;
    var r10 = n % 10, r100 = n % 100;
    if (r10 >= 2 && r10 <= 4 && (r100 < 10 || r100 >= 20)) return kilka;
    return wiele;
  }

  boxDost.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-trener]");
    if (!btn) return;
    selTrener.value = btn.dataset.trener;
    czyscBlad(selTrener);
    rysujStatus();
    toast("Prowadzący: " + btn.dataset.trener);
    zapiszSzkic();
  });

  ["f2-dt-data", "f2-dt-od", "f2-dt-do"].forEach(function (id) {
    $(id).addEventListener("change", odswiezDostepnosc);
  });

  // Zmiana prowadzącego z listy też musi odświeżyć plakietkę — w v2 wybór
  // z selecta nie wywoływał NICZEGO i tak przechodziła osoba niedostępna.
  selTrener.addEventListener("change", rysujStatus);

  /* ====================================================== TERMINY ZAJĘĆ CYKLU

     Cała nowość tego wariantu. Reszta pliku jest v3.
     ========================================================================= */

  var DNI_SKR = ["niedz", "pon", "wt", "śr", "czw", "pt", "sob"];
  var MAX_TERMINOW = 60;          // ta sama granica co na serwerze

  // Jeden termin: { data, godz, reczna, godzReczna }
  //   reczna     — datę poprawił człowiek (nie jest już propozycją),
  //   godzReczna — godzinę poprawił człowiek, więc zmiana godziny całego cyklu
  //                jej nie nadpisze.
  stan.terminy = [];

  var elStart = $("f4-start");
  var elIle = $("f4-ile");
  var elCoIleDaty = $("f4-co-ile-daty");
  var elLista = $("f4-lista");
  var elInfo = $("f4-info");
  var elAkcje = $("f4-akcje-listy");
  var elRegula = $("f4-regula");
  var elDaty = $("f4-daty");
  var elCyklOd = $("f2-cykl-od");

  // Rachunek dat siedzi w FxCykl (góra pliku) — tu tylko go używamy.
  var przesun = FxCykl.przesun;
  var dzienTyg = FxCykl.dzienTyg;

  function nazwaDnia(iso) {
    var n = dzienTyg(iso);
    return n < 0 ? "" : DNI_SKR[n];
  }

  function coIle() {
    return Math.max(1, parseInt(elCoIleDaty.value, 10) || 1);
  }

  function ileZajec() {
    var n = parseInt(elIle.value, 10) || 0;
    return Math.min(MAX_TERMINOW, Math.max(1, n));
  }

  /* Propozycja całej serii od podanego startu. */
  function wygenerujOdStartu() {
    var start = elStart.value;
    if (!start) { stan.terminy = []; rysujTerminy(); return; }
    var godz = elCyklOd.value || "";
    stan.terminy = FxCykl.seria(start, ileZajec(), coIle()).map(function (d) {
      return { data: d, godz: godz, reczna: false, godzReczna: false };
    });
    rysujTerminy();
  }

  /* Dopasowanie DŁUGOŚCI listy bez ruszania tego, co już ustalone.
     Zmiana „5 zajęć" na „7" ma dołożyć dwa terminy na końcu, a nie wyrzucić
     poprawione ręcznie daty i zacząć od nowa. */
  function dopasujDlugosc() {
    var ile = ileZajec(), krok = coIle();
    if (!stan.terminy.length) { wygenerujOdStartu(); return; }
    while (stan.terminy.length > ile) stan.terminy.pop();
    while (stan.terminy.length < ile) {
      var ost = stan.terminy[stan.terminy.length - 1];
      stan.terminy.push({ data: przesun(ost.data, 7 * krok), godz: ost.godz,
                          reczna: false, godzReczna: false });
    }
    rysujTerminy();
  }

  /* SERCE SEKCJI — patrz nagłówek pliku.
     Ten sam dzień tygodnia = przesunięcie całego cyklu (przeliczamy ogon).
     Inny dzień tygodnia    = wyjątek na jedno spotkanie (ogon zostaje). */
  function zmienTermin(i, noweISO) {
    if (!stan.terminy[i]) return;
    var stareISO = stan.terminy[i].data;
    var wynik = FxCykl.zmien(stan.terminy, i, noweISO, coIle());

    // Godziny zostają przy swoich pozycjach — FxCykl liczy tylko daty.
    wynik.terminy.forEach(function (t, j) {
      t.godz = stan.terminy[j].godz;
      t.godzReczna = stan.terminy[j].godzReczna;
    });
    stan.terminy = wynik.terminy;

    if (wynik.przeliczone) {
      toast("Przesunięto cały cykl — kolejne terminy przeliczone (" +
            wynik.przeliczone + ").");
    } else if (noweISO && stareISO && dzienTyg(noweISO) !== dzienTyg(stareISO)) {
      toast("Zmiana na " + nazwaDnia(noweISO) + " tylko dla tych zajęć — " +
            "kolejne bez zmian.");
    }
    rysujTerminy();
  }

  /* Dzień tygodnia całej serii — ten, który się powtarza. Bierzemy pierwszy
     termin, bo od niego liczą się propozycje; wszystko, co z niego wypada,
     opisujemy jako „poza rytmem". */
  function rytmSerii() {
    return stan.terminy.length ? dzienTyg(stan.terminy[0].data) : -1;
  }

  function rysujTerminy() {
    if (!stan.terminy.length) {
      elLista.innerHTML = "";
      elAkcje.hidden = true;
      elInfo.textContent = "Wpisz datę pierwszych zajęć — resztę terminów " +
        "zaproponujemy, a każdy z nich możesz poprawić kalendarzem.";
      elInfo.className = "f4-info";
      zapiszSzkic();
      return;
    }
    var rytm = rytmSerii();
    var propozycji = 0, poza = 0;

    elLista.innerHTML = stan.terminy.map(function (t, i) {
      var dzien = dzienTyg(t.data);
      var czyPoza = dzien >= 0 && rytm >= 0 && dzien !== rytm;
      var czyWeekend = dzien === 0 || dzien === 6;
      if (!t.reczna) propozycji++;
      if (czyPoza) poza++;
      return '<li class="f4-poz' + (t.reczna ? " f4-poz-reczna" : "") + '">' +
        '<span class="f4-nr">' + (i + 1) + ".</span>" +
        '<span class="f4-dzien' + (czyWeekend ? " f4-dzien-weekend" : "") + '">' +
          esc(nazwaDnia(t.data)) + "</span>" +
        '<input type="date" class="f2-pole f4-data" data-i="' + i + '" value="' +
          esc(t.data) + '">' +
        '<input type="time" class="f2-pole f4-godz" step="300" data-i="' + i +
          '" value="' + esc(t.godz) + '">' +
        (czyPoza ? '<span class="f4-znak f4-znak-poza" ' +
                   'title="Ten termin wypada w innym dniu tygodnia niż reszta cyklu">' +
                   "poza rytmem</span>" : "") +
        (czyWeekend ? '<span class="f4-znak f4-znak-weekend">weekend</span>' : "") +
        (t.reczna ? "" : '<span class="f4-znak f4-znak-prop">propozycja</span>') +
        '<button type="button" class="f4-usun" data-usun="' + i +
          '" title="Usuń ten termin" aria-label="Usuń termin ' + (i + 1) + '">×</button>' +
        "</li>";
    }).join("");

    elAkcje.hidden = false;
    var opis = stan.terminy.length + " " +
      odmiana(stan.terminy.length, "zajęcia", "zajęcia", "zajęć") +
      ": " + stan.terminy[0].data + " – " + stan.terminy[stan.terminy.length - 1].data;
    if (propozycji) {
      opis += " · " + propozycji + " " +
        odmiana(propozycji, "termin jeszcze jest propozycją",
                "terminy jeszcze są propozycją", "terminów jeszcze jest propozycją");
    }
    if (poza) {
      opis += " · " + poza + " poza rytmem cyklu";
    }
    elInfo.textContent = opis;
    elInfo.className = "f4-info" + (poza ? " f4-info-uwaga" : "");
    zapiszSzkic();
  }

  /* Delegowane nasłuchy — lista przerysowuje się w całości, więc podpinanie
     zdarzeń do pojedynczych pól i tak by nie przetrwało. */
  elLista.addEventListener("change", function (ev) {
    var pole = ev.target;
    if (pole.classList.contains("f4-data")) {
      zmienTermin(parseInt(pole.dataset.i, 10), pole.value);
    } else if (pole.classList.contains("f4-godz")) {
      var t = stan.terminy[parseInt(pole.dataset.i, 10)];
      if (t) { t.godz = pole.value; t.godzReczna = true; zapiszSzkic(); }
    }
  });

  elLista.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-usun]");
    if (!btn) return;
    stan.terminy.splice(parseInt(btn.dataset.usun, 10), 1);
    // Pole „ilość zajęć" ma zgadzać się z listą — inaczej następna zmiana
    // ilości cofnęłaby właśnie skasowany termin.
    elIle.value = stan.terminy.length || 1;
    rysujTerminy();
  });

  $("f4-dodaj").addEventListener("click", function () {
    if (stan.terminy.length >= MAX_TERMINOW) {
      toast("Więcej niż " + MAX_TERMINOW + " terminów w jednym pakiecie się nie zmieści.", true);
      return;
    }
    var ost = stan.terminy[stan.terminy.length - 1];
    stan.terminy.push({
      data: ost ? przesun(ost.data, 7 * coIle()) : (elStart.value || ""),
      godz: ost ? ost.godz : (elCyklOd.value || ""),
      reczna: false, godzReczna: false
    });
    elIle.value = stan.terminy.length;
    rysujTerminy();
  });

  $("f4-przelicz").addEventListener("click", function () {
    if (!elStart.value) { toast("Najpierw wpisz datę pierwszych zajęć.", true); return; }
    var reczne = stan.terminy.filter(function (t) { return t.reczna; }).length;
    if (reczne && !confirm("Przeliczyć wszystkie terminy od pierwszych zajęć?\n\n" +
                           reczne + " " + odmiana(reczne, "termin poprawiony",
                             "terminy poprawione", "terminów poprawionych") +
                           " ręcznie wróci do propozycji.")) return;
    wygenerujOdStartu();
  });

  elStart.addEventListener("change", function () {
    var reczne = stan.terminy.filter(function (t) { return t.reczna; }).length;
    if (reczne && !confirm("Zmiana daty pierwszych zajęć przeliczy całą listę.\n\n" +
                           reczne + " ręcznie poprawionych " +
                           odmiana(reczne, "termin wróci", "terminy wrócą", "terminów wróci") +
                           " do propozycji. Przeliczyć?")) {
      elStart.value = stan.terminy.length ? stan.terminy[0].data : "";
      return;
    }
    wygenerujOdStartu();
  });

  elIle.addEventListener("change", dopasujDlugosc);
  elCoIleDaty.addEventListener("change", function () {
    if (stan.terminy.length) wygenerujOdStartu();
  });

  /* Godzina całego cyklu spływa na terminy, KTÓRYCH NIKT NIE RUSZAŁ. Gdyby
     nadpisywała wszystkie, poprawiona godzina jednych zajęć ginęłaby przy
     najbliższej zmianie godziny ogólnej — i to bez śladu. */
  elCyklOd.addEventListener("change", function () {
    var g = elCyklOd.value || "";
    var zmienione = 0;
    stan.terminy.forEach(function (t) {
      if (!t.godzReczna) { t.godz = g; zmienione++; }
    });
    if (zmienione) rysujTerminy();
  });

  /* ============================================= WYŁĄCZNIK DNIA TECHNOLOGII

     Zajęcia cykliczne umawia się często bez świeżego DT: albo już był, albo
     placówka wchodzi w cykl bez dnia pokazowego. Bez tego wyłącznika zapisanie
     samego pakietu wymagało WYMYŚLENIA daty, godziny i prowadzącego DT —
     a wymyślony DT ląduje na grafiku trenera i ktoś na niego pojedzie.
     ========================================================================= */

  var elDtWl = $("f4-dt-wl");
  var elDtTresc = $("f4-dt-tresc");
  var elDtBrak = $("f4-dt-brak");

  function czyDT() {
    return elDtWl.checked;
  }

  function pokazDT() {
    var wl = czyDT();
    elDtTresc.hidden = !wl;
    elDtBrak.hidden = wl;
    $("f4-sekcja-dt").classList.toggle("f2-sekcja-wylaczona", !wl);
    if (!wl) {
      // Błędy z pól, których już nie widać, zostałyby na ekranie na zawsze —
      // z czerwoną obwódką pod schowaną sekcją i licznikiem „uzupełnij 5 pól".
      elDtTresc.querySelectorAll(".f2-blad").forEach(function (e) { e.remove(); });
      elDtTresc.querySelectorAll(".zly").forEach(function (e) { e.classList.remove("zly"); });
    }
    zapiszSzkic();
  }

  elDtWl.addEventListener("change", pokazDT);

  /* ------------------------------------------- przełączanie typu i sposobu */

  function wybranyTyp() {
    var el = root.querySelector('input[name="f4-typ"]:checked');
    return el ? el.value : "CYKLICZNE";
  }

  function wybranyTryb() {
    var el = root.querySelector('input[name="f4-tryb"]:checked');
    return el ? el.value : "regula";
  }

  function ustawTryb(tryb) {
    var el = root.querySelector('input[name="f4-tryb"][value="' + tryb + '"]');
    if (el) el.checked = true;
    pokazTryb();
  }

  function pokazTryb() {
    var daty = wybranyTryb() === "daty";
    elRegula.hidden = daty;
    elDaty.hidden = !daty;
    // Wejście w tryb dat z wpisaną datą DT: podpowiadamy start tydzień po DT.
    // Zajęcia cykliczne ruszają po Dniu Technologii — to jest cała mechanika
    // sprzedaży w tej firmie, więc pusty start byłby pytaniem bez treści.
    if (daty && !elStart.value && $("f2-dt-data").value) {
      elStart.value = przesun($("f2-dt-data").value, 7);
    }
    if (daty && !stan.terminy.length && elStart.value) wygenerujOdStartu();
    zapiszSzkic();
  }

  root.querySelectorAll('input[name="f4-tryb"]').forEach(function (el) {
    el.addEventListener("change", pokazTryb);
  });

  // Wybór rodzaju zajęć USTAWIA domyślny sposób, ale go nie zabiera:
  // przedszkole umawia pakiet dat, szkoła — regułę „co wtorek".
  root.querySelectorAll('input[name="f4-typ"]').forEach(function (el) {
    el.addEventListener("change", function () {
      ustawTryb(wybranyTyp() === "CYKLICZNE-PRZEDSZKOLE" ? "daty" : "regula");
    });
  });

  /* =============================================================== WALIDACJA */

  function bladPola(el, tekst) {
    czyscBlad(el);
    el.classList.add("zly");
    var p = document.createElement("p");
    p.className = "f2-blad";
    p.textContent = tekst;
    el.parentNode.insertBefore(p, el.nextSibling);
  }

  function czyscBlad(el) {
    el.classList.remove("zly");
    var n = el.nextSibling;
    if (n && n.className === "f2-blad") n.remove();
  }

  function sprawdz() {
    root.querySelectorAll(".f2-blad").forEach(function (e) { e.remove(); });
    root.querySelectorAll(".zly").forEach(function (e) { e.classList.remove("zly"); });

    var braki = [];
    if (stan.nowa) {
      if (!$("f2-nowa-nazwa").value.trim()) braki.push([$("f2-nowa-nazwa"), "Podaj nazwę placówki."]);
      if (!selMiasto.value) braki.push([selMiasto, "Wybierz miejscowość."]);
    } else if (!stan.wybrana) {
      if (!selMiasto.value) braki.push([selMiasto, "Wybierz miejscowość."]);
      else braki.push([selSzkola, "Wybierz szkołę z listy albo dodaj nową."]);
    }
    // Pola DT są wymagane TYLKO wtedy, gdy DT w ogóle umawiamy. Wymaganie ich
    // przy wyłączonej sekcji znaczyłoby „wymyśl datę, żeby móc zapisać cykl".
    if (czyDT()) {
      [["f2-dt-data", "Podaj datę DT."],
       ["f2-dt-od", "Podaj godzinę DT."],
       ["f2-dt-trener", "Wybierz prowadzącego DT."],
       ["f2-dt-klas", "Podaj liczbę klas 1–4."],
       ["f2-dt-dzieci", "Podaj liczbę dzieci."],
       ["f2-mail-rodzice", "Zaznacz, czy szkoła wyśle wiadomość do rodziców."]]
        .forEach(function (p) {
          var el = $(p[0]);
          if (!String(el.value || "").trim()) braki.push([el, p[1]]);
        });
    } else if (!zbierzCykl()) {
      // DT wyłączony I pusta sekcja cykliczna = zapis, po którym nie powstaje
      // ŻADNE spotkanie. Przycisk mruga, ekran sukcesu pokazuje samą szkołę
      // i wygląda to jak zgubiony formularz. Mówimy wprost, czego brakuje.
      var cel = wybranyTryb() === "daty" ? $("f4-start") : $("f2-cykl-dzien");
      braki.push([cel, "Bez Dnia Technologii trzeba ustalić zajęcia cykliczne — " +
                       (wybranyTryb() === "daty"
                         ? "podaj datę pierwszych zajęć."
                         : "wybierz dzień tygodnia.")]);
    }

    braki.forEach(function (b) { bladPola(b[0], b[1]); });
    if (braki.length) {
      braki[0][0].scrollIntoView({ behavior: "smooth", block: "center" });
      braki[0][0].focus({ preventScroll: true });
      toast("Uzupełnij " + braki.length + " " +
            odmiana(braki.length, "pole", "pola", "pól"), true);
      return false;
    }
    // Data w przeszłości to OSTRZEŻENIE, nie blokada — czasem wpisuje się
    // ustalenia po fakcie. Przy wyłączonym DT pole jest puste, a pusty tekst
    // jest „mniejszy" od dzisiejszej daty — bez tego warunku ostrzeżenie
    // wyskakiwałoby za każdym razem, gdy DT pomijamy.
    if (czyDT() && $("f2-dt-data").value < root.dataset.dzis) {
      toast("Uwaga: data DT jest w przeszłości — zapisuję tak, jak wpisałeś.");
    }
    // Pierwsze zajęcia PRZED Dniem Technologii to prawie zawsze pomyłka
    // (cykl otwiera się po dniu pokazowym), ale bywa świadome przy szkole,
    // która już nas zna — więc ostrzegamy, nie blokujemy.
    if (czyDT() && stan.terminy.length && $("f2-dt-data").value &&
        stan.terminy[0].data && stan.terminy[0].data < $("f2-dt-data").value) {
      toast("Uwaga: pierwsze zajęcia cykliczne wypadają przed DT.");
    }
    return true;
  }

  /* =================================================================== ZAPIS */

  function zbierz() {
    var d = { handlowiec: stan.handlowiec };
    if (stan.wybrana) {
      d.lead_id = stan.wybrana.lead_id;
    } else {
      d.placowka = {
        nazwa: $("f2-nowa-nazwa").value.trim(),
        miejscowosc: selMiasto.value,
        typ: $("f2-nowa-typ").value,
        adres: $("f2-nowa-adres").value.trim()
      };
    }
    d.kontakt = {
      osoba_kontakt: $("f2-osoba").value.trim(),
      telefon: $("f2-telefon").value.trim(),
      mail: $("f2-mail").value.trim()
    };
    d.cykle = $("f2-cykle").value;
    // Przy wyłączonym DT nie wysyłamy ANI bloku `dt`, ani pytania o wiadomość
    // do rodziców — to pole dotyczy zapowiedzi dnia pokazowego. Serwer
    // pomijający pusty blok nie utworzy spotkania i nie ruszy statusu leada
    // na „03. DT umówione".
    if (czyDT()) {
      d.mail_rodzice = $("f2-mail-rodzice").value;
      d.dt = {
        data: $("f2-dt-data").value,
        godz_od: $("f2-dt-od").value,
        godz_do: $("f2-dt-do").value,
        trener: selTrener.value,
        numer_sali: $("f2-dt-sala").value.trim(),
        ilosc_klas: $("f2-dt-klas").value,
        ilosc_dzieci: $("f2-dt-dzieci").value,
        uwagi: $("f2-dt-uwagi").value.trim()
      };
    }
    d.cykl = zbierzCykl();
    return d;
  }

  /* Blok zajęć cyklicznych. Serwer pomija go, gdy nie ma ani dnia tygodnia,
     ani listy terminów — czyli „nie wypełniłem tej sekcji" nie tworzy pustych
     zajęć. Zwracamy `null`, żeby to było widać także tutaj. */
  function zbierzCykl() {
    var wspolne = {
      typ: wybranyTyp(),
      godz_od: elCyklOd.value,
      numer_sali: $("f2-cykl-sala").value.trim(),
      sprzet: $("f2-cykl-sprzet").value,
      uwagi: $("f2-cykl-uwagi").value.trim()
    };

    if (wybranyTryb() !== "daty") {
      if (!$("f2-cykl-dzien").value) return null;
      wspolne.cykl_dzien = $("f2-cykl-dzien").value;
      wspolne.co_ile_tygodni = $("f4-co-ile").value;
      return wspolne;
    }

    var terminy = stan.terminy.filter(function (t) { return t.data; });
    if (!terminy.length) return null;
    wspolne.terminy = terminy.map(function (t) {
      return { data: t.data, godz_od: t.godz || wspolne.godz_od || "" };
    });
    wspolne.co_ile_tygodni = coIle();

    // Dzień tygodnia dopisujemy TYLKO wtedy, gdy cała seria trzyma jeden rytm.
    // Przy mieszanych datach byłby nieprawdą — a to pole ląduje na karcie
    // szkoły i w planszy STARTY, gdzie trener sprawdza, kiedy ma przyjechać.
    var dni = terminy.map(function (t) { return dzienTyg(t.data); });
    var jeden = dni.every(function (n) { return n === dni[0]; });
    if (jeden && dni[0] >= 1 && dni[0] <= 6) {
      wspolne.cykl_dzien = ["", "poniedziałek", "wtorek", "środa", "czwartek",
                            "piątek", "sobota"][dni[0]];
    }
    return wspolne;
  }

  var btnZapisz = $("f2-zapisz");
  btnZapisz.addEventListener("click", function () {
    if (!sprawdz()) return;
    btnZapisz.disabled = true;
    var stary = btnZapisz.innerHTML;
    btnZapisz.textContent = "Zapisuję…";
    var payload = zbierz();
    // Klucz próby — chroni przed dublem, gdy zapis dojdzie, a odpowiedź nie wróci.
    payload.klucz_zapisu = FxAwaria.losowyKlucz();
    api("POST", "/api/formularz", payload)
      .then(function (j) {
        localStorage.removeItem(KLUCZ_SZKICU);
        if (awaria) awaria.wyczysc();
        zapisano = true;
        pokazSukces(j);
      })
      .catch(function (e) {
        btnZapisz.disabled = false;
        btnZapisz.innerHTML = stary;
        // Treść formularza zostaje w kolejce „niewysłane" — do ponowienia
        // jednym kliknięciem, gdy wróci zasięg.
        if (awaria) awaria.zapamietaj(payload, e.message);
        toast("Nie zapisano: " + e.message, true);
      });
  });

  $("f2-wyczysc").addEventListener("click", function () {
    if (!confirm("Wyczyścić cały formularz? Wpisane dane przepadną.")) return;
    localStorage.removeItem(KLUCZ_SZKICU);
    location.href = POWROT +
      (stan.handlowiec ? "?handlowiec=" + encodeURIComponent(stan.handlowiec) : "");
  });

  function pokazSukces(j) {
    root.querySelectorAll(".f2-sekcja, .f2-akcje, .fx-alarm")
      .forEach(function (el) { el.hidden = true; });
    $("f2-szkic").hidden = true;
    $("f2-sukces-tytul").textContent = "Zapisano: " + j.placowka;
    var tresc = czyDT()
      ? ("DT " + $("f2-dt-data").value + " o " + $("f2-dt-od").value +
         (selTrener.value ? ", prowadzi " + selTrener.value : "") + ".")
      : "Bez Dnia Technologii — zapisane same zajęcia cykliczne.";
    // Ile terminów naprawdę wylądowało w bazie — z odpowiedzi serwera, nie
    // z tego, co widać na ekranie. Serwer odsiewa daty puste i zdublowane,
    // więc liczba z formularza potrafi być większa niż zapisana.
    (j.eventy || []).forEach(function (e) {
      if (e.terminy) {
        tresc += " Zajęcia cykliczne: " + e.terminy + " " +
                 odmiana(e.terminy, "termin", "terminy", "terminów") + " w kalendarzu.";
      }
    });
    $("f2-sukces-tresc").textContent = tresc;
    if (j.kolizja) {
      $("f2-sukces-kolizja").textContent = "Uwaga: " + j.kolizja;
      $("f2-sukces-kolizja").hidden = false;
    }
    $("f2-do-leada").href = "/lead/" + j.lead_id;
    $("f2-sukces").hidden = false;
    window.scrollTo(0, 0);
  }

  $("f2-nowy").addEventListener("click", function () {
    localStorage.removeItem(KLUCZ_SZKICU);
    location.href = POWROT +
      (stan.handlowiec ? "?handlowiec=" + encodeURIComponent(stan.handlowiec) : "");
  });

  /* ========================================================= SZKIC W TELEFONIE */

  var POLA = ["f2-miasto", "f2-osoba", "f2-telefon", "f2-mail", "f2-nowa-nazwa",
              "f2-nowa-typ", "f2-nowa-adres", "f2-dt-data", "f2-dt-od", "f2-dt-do",
              "f2-dt-sala", "f2-dt-trener", "f2-dt-uwagi", "f2-dt-klas", "f2-dt-dzieci",
              "f2-mail-rodzice", "f2-cykle", "f2-cykl-dzien", "f2-cykl-od",
              "f2-cykl-sala", "f2-cykl-sprzet", "f2-cykl-uwagi",
              "f4-co-ile", "f4-start", "f4-ile", "f4-co-ile-daty"];

  var timerSzkicu = null;

  function zapiszSzkic() {
    clearTimeout(timerSzkicu);
    timerSzkicu = setTimeout(function () {
      var pola = {};
      POLA.forEach(function (id) { var el = $(id); if (el) pola[id] = el.value; });
      try {
        localStorage.setItem(KLUCZ_SZKICU, JSON.stringify({
          kiedy: new Date().toISOString(),
          handlowiec: stan.handlowiec,
          placowka_id: stan.wybrana ? stan.wybrana.placowka_id : null,
          nowa: stan.nowa,
          pola: pola,
          // Lista terminów NIE jest zwykłym polem formularza — bez tego
          // przywrócony szkic wracałby z pustą listą i wyglądałby jak
          // uszkodzony właśnie w tej części, dla której ten wariant powstał.
          typCyklu: wybranyTyp(),
          trybCyklu: wybranyTryb(),
          dtWlaczony: czyDT(),
          terminy: stan.terminy
        }));
        var t = new Date();
        var el = $("f2-szkic");
        el.textContent = "Szkic zapisany w telefonie o " +
          String(t.getHours()).padStart(2, "0") + ":" +
          String(t.getMinutes()).padStart(2, "0") + " — możesz zamknąć przeglądarkę.";
        el.hidden = false;
      } catch (e) {
        // prywatne okno albo pełna pamięć — brak szkicu nie blokuje pracy
      }
    }, 400);
  }

  function wczytajSzkic() {
    var s;
    try { s = JSON.parse(localStorage.getItem(KLUCZ_SZKICU) || "null"); } catch (e) { return; }
    if (!s || s.handlowiec !== stan.handlowiec) return;
    if (new Date() - new Date(s.kiedy) > 24 * 3600 * 1000) {
      localStorage.removeItem(KLUCZ_SZKICU);
      return;
    }
    var k = new Date(s.kiedy);
    var opis = String(k.getHours()).padStart(2, "0") + ":" +
               String(k.getMinutes()).padStart(2, "0");
    if (!confirm("Masz niedokończony formularz z godz. " + opis + ".\n\nPrzywrócić go?")) {
      localStorage.removeItem(KLUCZ_SZKICU);
      return;
    }
    Object.keys(s.pola || {}).forEach(function (id) {
      var el = $(id);
      // listę szkół podstawiamy dopiero po doczytaniu placówek dla miasta
      if (el && id !== "f2-szkola") el.value = s.pola[id];
    });
    if (s.nowa) {
      stan.nowa = true;
      $("f2-nowa").hidden = false;
      $("f2-nowa-otworz").textContent = "− Jednak wybieram z listy";
    }
    if (s.typCyklu) {
      var elTyp = root.querySelector('input[name="f4-typ"][value="' + s.typCyklu + '"]');
      if (elTyp) elTyp.checked = true;
    }
    // Terminy przed `ustawTryb` — inaczej `pokazTryb` uznałby listę za pustą
    // i wygenerował propozycje na miejsce przywróconych ustaleń.
    stan.terminy = Array.isArray(s.terminy) ? s.terminy : [];
    ustawTryb(s.trybCyklu === "daty" ? "daty" : "regula");
    rysujTerminy();
    // Szkice sprzed tej wersji nie mają tego pola — wtedy DT zostaje włączony,
    // czyli tak, jak było w chwili zapisywania szkicu.
    if (s.dtWlaczony === false) { elDtWl.checked = false; pokazDT(); }
    if (selMiasto.value) {
      wczytajSzkoly(selMiasto.value, function () {
        if (s.placowka_id && indeks[s.placowka_id]) {
          selSzkola.value = String(s.placowka_id);
          stan.wybrana = indeks[s.placowka_id];
        }
        odswiezDostepnosc();
      });
    }
    toast("Przywrócono szkic");
  }

  POLA.forEach(function (id) {
    var el = $(id);
    if (!el) return;
    el.addEventListener("input", function () { czyscBlad(el); zapiszSzkic(); });
    el.addEventListener("change", function () { czyscBlad(el); zapiszSzkic(); });
  });

  /* =================================================================== START */

  // Pola, które mają wartość OD RAZU po wejściu („5 zajęć", „co tydzień").
  // Bez tego wyjątku ostrzeżenie „masz niezapisane dane" wyskakiwałoby przy
  // wychodzeniu z pustego formularza — czyli za każdym razem, a wtedy przestaje
  // cokolwiek znaczyć i ludzie klikają je odruchowo.
  var POLA_DOMYSLNE = ["f4-ile", "f4-co-ile", "f4-co-ile-daty"];

  function czyCosWpisane() {
    if (zapisano) return false;
    if (stan.wybrana || stan.nowa) return true;
    if (stan.terminy.length) return true;
    return POLA.some(function (id) {
      if (POLA_DOMYSLNE.indexOf(id) >= 0) return false;
      var el = $(id);
      return el && String(el.value || "").trim();
    });
  }

  awaria = FxAwaria.utworz({
    klucz: "f4-niewyslany-v1",
    kontener: root,
    handlowiec: stan.handlowiec,
    toast: toast,
    naSukces: function (j) { zapisano = true; pokazSukces(j); }
  });

  FxAwaria.pilnujWyjscia(czyCosWpisane);
  FxAwaria.pilnujZakonczenia($("f2-zakoncz"), czyCosWpisane);

  pokazTryb();
  pokazDT();
  if (stan.handlowiec) wczytajSzkic();
})();
