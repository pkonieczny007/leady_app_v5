/* =============================================================================
   Logowanie PIN-em.

   Własna klawiatura cyfrowa zamiast systemowej: na telefonie klawiatura systemowa
   zasłania pół ekranu, trzeba ją zamykać żeby zobaczyć przycisk „Zaloguj", a przy
   czterech cyfrach to więcej zachodu niż samo logowanie. Duże klawisze działają
   też w rękawiczkach, co zimą w szkolnym korytarzu nie jest teoretyczne.

   Logowanie odpala się SAMO po czwartej cyfrze — nie ma czego potwierdzać,
   a jedno kliknięcie mniej przy każdym wejściu robi różnicę.
   ============================================================================= */
(function () {
  "use strict";

  var root = document.getElementById("lg");
  if (!root) return;

  var $ = function (id) { return document.getElementById(id); };
  var selOsoba = $("lg-osoba");
  var polePin = $("lg-pin");
  var kropki = $("lg-kropki").children;
  var boxBlad = $("lg-blad");
  var btnWejdz = $("lg-wejdz");
  var KLUCZ_OSOBY = "lg-ostatnia-osoba";

  // Kto logował się ostatnio na tym telefonie — w praktyce zawsze ta sama osoba.
  var ostatnia = localStorage.getItem(KLUCZ_OSOBY);
  if (ostatnia) {
    selOsoba.value = ostatnia;
    if (selOsoba.value) setTimeout(function () { polePin.focus(); }, 100);
  }

  function odswiezKropki() {
    var n = polePin.value.length;
    for (var i = 0; i < kropki.length; i++) {
      kropki[i].classList.toggle("pelna", i < n);
    }
  }

  function blad(tekst) {
    boxBlad.textContent = tekst;
    boxBlad.hidden = !tekst;
    if (tekst) {
      root.classList.add("lg-trzesie");
      setTimeout(function () { root.classList.remove("lg-trzesie"); }, 400);
    }
  }

  function cyfra(c) {
    if (polePin.value.length >= 4) return;
    polePin.value += c;
    blad("");
    odswiezKropki();
    if (polePin.value.length === 4) setTimeout(zaloguj, 120);
  }

  $("lg-klawiatura").addEventListener("click", function (ev) {
    var b = ev.target.closest("button");
    if (!b) return;
    if (b.dataset.cyfra) return cyfra(b.dataset.cyfra);
    if (b.dataset.akcja === "kasuj") polePin.value = polePin.value.slice(0, -1);
    if (b.dataset.akcja === "czysc") polePin.value = "";
    blad("");
    odswiezKropki();
  });

  // Klawiatura fizyczna — na komputerze koordynatorka woli wystukać na numerycznej
  document.addEventListener("keydown", function (ev) {
    if (ev.target === selOsoba) return;
    if (ev.key >= "0" && ev.key <= "9") { cyfra(ev.key); ev.preventDefault(); }
    else if (ev.key === "Backspace") {
      polePin.value = polePin.value.slice(0, -1); odswiezKropki(); ev.preventDefault();
    } else if (ev.key === "Enter") { zaloguj(); }
  });

  selOsoba.addEventListener("change", function () {
    blad("");
    polePin.value = "";
    odswiezKropki();
  });

  var trwa = false;

  function zaloguj() {
    if (trwa) return;
    if (!selOsoba.value) { blad("Wybierz, kto się loguje"); selOsoba.focus(); return; }
    if (polePin.value.length !== 4) { blad("PIN ma cztery cyfry"); return; }

    trwa = true;
    btnWejdz.disabled = true;
    btnWejdz.textContent = "Sprawdzam…";

    fetch("/api/logowanie", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ osoba: selOsoba.value, pin: polePin.value })
    })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (!r.ok || j.ok === false) throw new Error(j.error || "Błąd " + r.status);
          return j;
        });
      })
      .then(function (j) {
        localStorage.setItem(KLUCZ_OSOBY, j.osoba);
        // `dalej` to ekran, na który człowiek szedł, zanim odbiła go sesja —
        // wracamy tam, zamiast rzucać go na stronę startową.
        var dalej = root.dataset.dalej;
        location.href = (dalej && dalej.charAt(0) === "/" &&
                         dalej.indexOf("//") !== 0) ? dalej : j.dalej;
      })
      .catch(function (e) {
        trwa = false;
        btnWejdz.disabled = false;
        btnWejdz.textContent = "Zaloguj";
        polePin.value = "";
        odswiezKropki();
        blad(e.message);
      });
  }

  btnWejdz.addEventListener("click", zaloguj);
  odswiezKropki();
})();
