/* =============================================================================
   WARIANT 2 formularza — jeden ciągły, przewijany w dół.

   Zapisuje przez to samo API co wariant 1 (`/api/formularz`) i ma tę samą
   walidację. Różni się WYŁĄCZNIE sposobem podania — inaczej porównanie obu
   wariantów na spotkaniu nie miałoby sensu, bo klient wybierałby między
   układem a funkcjami.

   Trzy rzeczy specyficzne dla tego wariantu:

   1. Para list „Miejscowość → Placówka" jak w makiecie. Lista szkół doczytuje
      się po wyborze miasta — 551 pozycji naraz to przewijanie kciukiem przez
      pół województwa.
   2. Podpowiedź dostępności siedzi POD listą prowadzących, a nie zastępuje jej:
      w makiecie jest tam pole tekstowe, więc zachowujemy jej kształt, ale
      dokładamy informację, kto jest realnie wolny.
   3. Wszystko jest widoczne naraz, więc walidacja przewija do pierwszego błędu
      zamiast przełączać ekran.
   ============================================================================= */
(function () {
  "use strict";

  function tokenCsrf() {
    var m = document.querySelector('meta[name="csrf"]');
    return m ? m.content : "";
  }

  var root = document.getElementById("f2");
  if (!root) return;

  var KLUCZ_SZKICU = "f2-szkic-v1";
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
      if (licz[o.value]) o.textContent = o.textContent + "  (twoje: " + licz[o.value] + ")";
    });
  })();

  function wczytajSzkoly(miasto, poWczytaniu) {
    if (!miasto) {
      selSzkola.innerHTML = '<option value="">Najpierw wybierz miejscowość</option>';
      selSzkola.disabled = true;
      infoSzkola.textContent = "";
      return;
    }
    selSzkola.disabled = true;
    selSzkola.innerHTML = '<option value="">Wczytuję…</option>';
    api("GET", "/api/placowki?miejscowosc=" + encodeURIComponent(miasto) +
               "&handlowiec=" + encodeURIComponent(stan.handlowiec))
      .then(function (j) {
        indeks = {};
        var moich = 0;
        var html = '<option value="">Wybierz szkołę z listy</option>';
        // szkoły handlowca na górze, reszta alfabetycznie
        j.pozycje.sort(function (a, b) {
          if (a.moja !== b.moja) return a.moja ? -1 : 1;
          return a.nazwa.localeCompare(b.nazwa, "pl");
        });
        j.pozycje.forEach(function (p) {
          indeks[p.placowka_id] = p;
          if (p.moja) moich++;
          html += '<option value="' + p.placowka_id + '">' + esc(p.nazwa) +
                  (p.moja ? "  ★" : "") + "</option>";
        });
        selSzkola.innerHTML = html;
        selSzkola.disabled = false;
        infoSzkola.textContent = j.pozycje.length
          ? (j.pozycje.length + " placówek" + (moich ? ", w tym " + moich + " twoich (★)" : ""))
          : "Brak placówek w tej miejscowości — dodaj nową poniżej.";
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

  selSzkola.addEventListener("change", function () {
    stan.wybrana = indeks[selSzkola.value] || null;
    if (stan.wybrana) {
      stan.nowa = false;
      $("f2-nowa").hidden = true;
      // dane kontaktowe podpowiadamy z bazy — handlowiec ma je POPRAWIĆ,
      // a nie wpisywać od zera przy każdym spotkaniu
      if (!$("f2-osoba").value) $("f2-osoba").value = stan.wybrana.osoba_kontakt || "";
      if (!$("f2-telefon").value) $("f2-telefon").value = stan.wybrana.telefon || "";
      if (!$("f2-mail").value) $("f2-mail").value = stan.wybrana.mail || "";
    }
    odswiezDostepnosc();
    zapiszSzkic();
  });

  // Wejście dla wspólnej sekcji „Plan na dziś" (fx_plan.js). Tu wybór szkoły
  // to ustawienie DWÓCH list, a druga doczytuje się z serwera — dlatego
  // podstawiamy szkołę dopiero w callbacku po wczytaniu, a nie od razu.
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

  function odswiezDostepnosc() {
    var data = $("f2-dt-data").value;
    if (!data) {
      boxDost.innerHTML = "Po wybraniu daty pokażemy, kto jest wolny i jeździ po tej okolicy.";
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
        .then(function (j) { rysujDostepnosc(j, miasto); })
        .catch(function () {
          boxDost.textContent = "Nie udało się sprawdzić dostępności — wybierz prowadzącego z listy.";
        });
    }, 200);
  }

  function rysujDostepnosc(j, miasto) {
    var lista = [];
    (j.grupy || []).forEach(function (g) {
      g.pozycje.forEach(function (k) { lista.push(k); });
    });
    // Pokazujemy tylko tych, na których warto kliknąć: wolnych i bez deklaracji.
    // „Niedostępny" i „kolizja" zostają w liście rozwijanej — nie blokujemy,
    // ale też nie podsuwamy pod palec.
    var dobrzy = lista.filter(function (k) {
      return k.kategoria === "wolny" || k.kategoria === "nieznany";
    }).slice(0, 8);

    var wolnych = lista.filter(function (k) { return k.kategoria === "wolny"; }).length;
    var html = wolnych
      ? "<b>" + wolnych + "</b> " + odmiana(wolnych, "osoba wolna", "osoby wolne", "osób wolnych") +
        " tego dnia" + (miasto ? ", rejon <b>" + esc(miasto) + "</b>" : "") + ":"
      : "Nikt nie zadeklarował dostępności na ten dzień — wybierz z listy powyżej.";

    if (dobrzy.length) {
      html += '<ul class="f2-dost-lista">';
      dobrzy.forEach(function (k) {
        var uwaga = k.kategoria !== "wolny";
        html += '<li><button type="button" data-trener="' + esc(k.trener) + '"' +
          (uwaga ? ' class="f2-dost-uwaga"' : "") +
          ' title="' + esc(k.powod) + '">' + esc(k.trener) +
          (k.rejon ? " · jeździ tu" : "") + "</button></li>";
      });
      html += "</ul>";
    }
    boxDost.innerHTML = html;
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
    toast("Prowadzący: " + btn.dataset.trener);
    zapiszSzkic();
  });

  ["f2-dt-data", "f2-dt-od", "f2-dt-do"].forEach(function (id) {
    $(id).addEventListener("change", odswiezDostepnosc);
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
    klucz: "f2-niewyslany-v1",
    kontener: root,
    handlowiec: stan.handlowiec,
    toast: toast,
    naSukces: function (j) { zapisano = true; pokazSukces(j); }
  });

  FxAwaria.pilnujWyjscia(czyCosWpisane);
  FxAwaria.pilnujZakonczenia($("f2-zakoncz"), czyCosWpisane);

  if (stan.handlowiec) wczytajSzkic();
})();
