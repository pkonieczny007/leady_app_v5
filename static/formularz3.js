/* =============================================================================
   WARIANT 3 formularza — układ wariantu 2, mocniejsza podpowiedź trenera.

   Zapisuje przez to samo API co v1 i v2 (`/api/formularz`), tą samą walidacją
   i z tą samą ochroną przed dublem. Różnica jest wyłącznie w sekcji Dnia
   Technologii i wynika z uwag po teście na telefonie (09.08).

   CO ZMIENIA WOBEC v2

   1. STATUS WYBRANEJ OSOBY. v2 pozwalał wybrać z listy kogoś niedostępnego
      albo mającego tego dnia inne zajęcia i nie mówił ani słowa — kolizja
      wychodziła dopiero na ekranie sukcesu, po zapisie. Tu status wybranej
      osoby jest widoczny od razu i przelicza się przy każdej zmianie daty,
      godziny i prowadzącego.
   2. WSZYSTKIE CZTERY KATEGORIE. v2 pokazywał osiem pierwszych wolnych i nic
      poza tym; kto jest niedostępny, tego nie dawało się sprawdzić inaczej niż
      wchodząc na grafik. Tutaj są cztery zwijane grupy z licznikami.
   3. WOLNE OKNA I ZAJĘCIA przy kandydacie. Serwer liczy je od dawna
      (`przydzial.kandydaci`), a żaden formularz ich nie pokazywał.
   4. „CO SIĘ DZIEJE TEGO DNIA" — kto z firmy gdzie jest. Budowane z TEJ SAMEJ
      odpowiedzi API co lista kandydatów, więc bez dodatkowego zapytania.

   OSTRZEGAMY, NIE BLOKUJEMY — zasada z całego projektu. Wybór osoby
   niedostępnej jest możliwy (czasem tak trzeba: ktoś się zamieni), tylko
   przestaje być niewidoczny.
   ============================================================================= */
(function () {
  "use strict";

  function tokenCsrf() {
    var m = document.querySelector('meta[name="csrf"]');
    return m ? m.content : "";
  }

  var root = document.getElementById("f2");
  if (!root) return;

  // Osobne klucze niż v2 — inaczej szkic zaczęty w jednym wariancie wskakiwałby
  // do drugiego i porównanie wariantów przez klienta robiłoby się mętne.
  var KLUCZ_SZKICU = "f3-szkic-v1";
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

    braki.forEach(function (b) { bladPola(b[0], b[1]); });
    if (braki.length) {
      braki[0][0].scrollIntoView({ behavior: "smooth", block: "center" });
      braki[0][0].focus({ preventScroll: true });
      toast("Uzupełnij " + braki.length + " " +
            odmiana(braki.length, "pole", "pola", "pól"), true);
      return false;
    }
    // Data w przeszłości to OSTRZEŻENIE, nie blokada — czasem wpisuje się
    // ustalenia po fakcie.
    if ($("f2-dt-data").value < root.dataset.dzis) {
      toast("Uwaga: data DT jest w przeszłości — zapisuję tak, jak wpisałeś.");
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
    d.mail_rodzice = $("f2-mail-rodzice").value;
    d.cykle = $("f2-cykle").value;
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
    if ($("f2-cykl-dzien").value) {
      d.cykl = {
        cykl_dzien: $("f2-cykl-dzien").value,
        godz_od: $("f2-cykl-od").value,
        numer_sali: $("f2-cykl-sala").value.trim(),
        sprzet: $("f2-cykl-sprzet").value,
        uwagi: $("f2-cykl-uwagi").value.trim()
      };
    }
    return d;
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
    location.href = "/formularz/ciagly" +
      (stan.handlowiec ? "?handlowiec=" + encodeURIComponent(stan.handlowiec) : "");
  });

  function pokazSukces(j) {
    root.querySelectorAll(".f2-sekcja, .f2-akcje, .fx-alarm")
      .forEach(function (el) { el.hidden = true; });
    $("f2-szkic").hidden = true;
    $("f2-sukces-tytul").textContent = "Zapisano: " + j.placowka;
    $("f2-sukces-tresc").textContent =
      "DT " + $("f2-dt-data").value + " o " + $("f2-dt-od").value +
      (selTrener.value ? ", prowadzi " + selTrener.value : "") + ".";
    if (j.kolizja) {
      $("f2-sukces-kolizja").textContent = "Uwaga: " + j.kolizja;
      $("f2-sukces-kolizja").hidden = false;
    }
    $("f2-do-leada").href = "/lead/" + j.lead_id;
    // P23: szkoła schodzi z „Planu na dziś" od razu, bez przeładowania —
    // ekran sukcesu strony nie odświeża, a licznik „N do zrobienia" musi
    // odpowiadać na wykonaną pracę, inaczej ludzie przestają na niego patrzeć.
    if (typeof window.FX_PLAN_ZROBIONE === "function") {
      window.FX_PLAN_ZROBIONE(j.lead_id);
    }

    $("f2-sukces").hidden = false;
    window.scrollTo(0, 0);
  }

  $("f2-nowy").addEventListener("click", function () {
    localStorage.removeItem(KLUCZ_SZKICU);
    location.href = "/formularz/ciagly" +
      (stan.handlowiec ? "?handlowiec=" + encodeURIComponent(stan.handlowiec) : "");
  });

  /* ========================================================= SZKIC W TELEFONIE */

  var POLA = ["f2-miasto", "f2-osoba", "f2-telefon", "f2-mail", "f2-nowa-nazwa",
              "f2-nowa-typ", "f2-nowa-adres", "f2-dt-data", "f2-dt-od", "f2-dt-do",
              "f2-dt-sala", "f2-dt-trener", "f2-dt-uwagi", "f2-dt-klas", "f2-dt-dzieci",
              "f2-mail-rodzice", "f2-cykle", "f2-cykl-dzien", "f2-cykl-od",
              "f2-cykl-sala", "f2-cykl-sprzet", "f2-cykl-uwagi"];

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
          pola: pola
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

  function czyCosWpisane() {
    if (zapisano) return false;
    if (stan.wybrana || stan.nowa) return true;
    return POLA.some(function (id) {
      var el = $(id);
      return el && String(el.value || "").trim();
    });
  }

  awaria = FxAwaria.utworz({
    klucz: "f3-niewyslany-v1",
    kontener: root,
    handlowiec: stan.handlowiec,
    toast: toast,
    naSukces: function (j) { zapisano = true; pokazSukces(j); }
  });

  FxAwaria.pilnujWyjscia(czyCosWpisane);
  FxAwaria.pilnujZakonczenia($("f2-zakoncz"), czyCosWpisane);

  if (stan.handlowiec) wczytajSzkic();
})();
