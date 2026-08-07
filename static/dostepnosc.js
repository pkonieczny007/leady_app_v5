/* =============================================================================
   Ekran „Dostępność trenerów" — edycja komórki i wypełnianie zakresu.

   Osobny plik, bo to interakcje tylko tego ekranu. Ta sama zasada co w app.js:
   zero bibliotek, zapis przez API, każda operacja kończy się widocznym
   komunikatem albo przeładowaniem z nowym stanem.
   ============================================================================= */
(function () {
  "use strict";

  function tokenCsrf() {
    var m = document.querySelector('meta[name="csrf"]');
    return m ? m.content : "";
  }

  function toast(tekst, blad) {
    var el = document.getElementById("toast");
    if (!el) { if (blad) alert(tekst); return; }
    el.textContent = tekst;
    el.classList.toggle("err", !!blad);
    el.classList.add("show");
    setTimeout(function () { el.classList.remove("show"); }, blad ? 6000 : 2200);
  }

  function api(metoda, url, dane) {
    return fetch(url, {
      method: metoda,
      headers: { "Content-Type": "application/json", "X-CSRF": tokenCsrf() },
      body: JSON.stringify(dane || {})
    }).then(function (r) {
      return r.json().catch(function () { return { ok: r.ok }; })
        .then(function (j) {
          if (!r.ok || j.ok === false) throw new Error(j.error || ("Błąd " + r.status));
          return j;
        });
    });
  }

  /* ------------------------------------------------------- edytor komórki */

  var editor = document.getElementById("av-editor");
  var aktywna = null;                       // komórka, w której siedzi edytor

  function zamknij() {
    if (!editor || editor.hidden) return;
    editor.hidden = true;
    document.body.appendChild(editor);      // wyjmij z komórki
    if (aktywna) aktywna.classList.remove("av-edytowana");
    aktywna = null;
  }

  function otworz(td) {
    zamknij();
    aktywna = td;
    td.classList.add("av-edytowana");
    document.getElementById("ave-head").textContent =
      td.dataset.trener.replace(/^\d+b?\.\s*/, "") + " · " + td.dataset.data;
    document.getElementById("ave-od").value = td.dataset.od || "";
    document.getElementById("ave-do").value = td.dataset.do || "";
    document.getElementById("ave-nied").checked = td.dataset.nied === "1";
    document.getElementById("ave-uwagi").value = td.dataset.uwagi || "";
    przelaczGodziny();
    td.appendChild(editor);
    editor.hidden = false;
    document.getElementById("ave-od").focus();
  }

  function przelaczGodziny() {
    var nied = document.getElementById("ave-nied").checked;
    document.getElementById("ave-godziny").style.opacity = nied ? ".35" : "1";
    document.getElementById("ave-od").disabled = nied;
    document.getElementById("ave-do").disabled = nied;
  }

  document.addEventListener("click", function (ev) {
    if (editor && editor.contains(ev.target)) return;   // klik w sam edytor
    var td = ev.target.closest("td.av-cell");
    // Komórka oznaczona jako podgląd należy do kogoś innego (trener) albo do
    // roli bez prawa zmiany (handlowiec). Serwer i tak by odmówił — nie
    // otwieramy edytora, żeby nie obiecywać czegoś, co się nie uda.
    if (td && !td.classList.contains("av-tylko-podglad")) { otworz(td); return; }
    zamknij();                                          // klik gdziekolwiek indziej
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") zamknij();
    if (ev.key === "Enter" && ev.target.classList
        && ev.target.classList.contains("av-cell")
        && !ev.target.classList.contains("av-tylko-podglad")) otworz(ev.target);
  });

  document.addEventListener("change", function (ev) {
    if (ev.target.id === "ave-nied") przelaczGodziny();
    if (ev.target.id === "az-tryb") {
      document.getElementById("az-godziny").hidden = ev.target.value !== "okno";
    }
  });

  document.addEventListener("click", function (ev) {
    if (ev.target.id === "ave-anuluj") { zamknij(); return; }

    if (ev.target.id === "ave-zapisz" && aktywna) {
      api("POST", "/api/dostepnosc", {
        trener: aktywna.dataset.trener,
        data: aktywna.dataset.data,
        godz_od: document.getElementById("ave-od").value,
        godz_do: document.getElementById("ave-do").value,
        niedostepny: document.getElementById("ave-nied").checked,
        uwagi: document.getElementById("ave-uwagi").value
      }).then(function () { location.reload(); })
        .catch(function (e) { toast("Nie zapisano: " + e.message, true); });
    }

    if (ev.target.id === "ave-wyczysc" && aktywna) {
      api("DELETE", "/api/dostepnosc", {
        trener: aktywna.dataset.trener, data: aktywna.dataset.data
      }).then(function () { location.reload(); })
        .catch(function (e) { toast("Nie usunięto: " + e.message, true); });
    }
  });

  /* --------------------------------------------------- wypełnianie zakresu */

  document.addEventListener("click", function (ev) {
    if (ev.target.id !== "btn-az-zapisz") return;
    var trener = document.getElementById("az-trener").value;
    if (!trener) { toast("Wybierz trenera", true); return; }
    var dni = Array.prototype.slice
      .call(document.querySelectorAll(".az-dzien:checked"))
      .map(function (c) { return parseInt(c.value, 10); });
    if (!dni.length) { toast("Zaznacz przynajmniej jeden dzień tygodnia", true); return; }
    var tryb = document.getElementById("az-tryb").value;
    api("POST", "/api/dostepnosc/zakres", {
      trener: trener,
      od: document.getElementById("az-od").value,
      do: document.getElementById("az-do").value,
      dni: dni,
      niedostepny: tryb === "nie",
      godz_od: tryb === "okno" ? document.getElementById("az-god").value : "",
      godz_do: tryb === "okno" ? document.getElementById("az-gdo").value : ""
    }).then(function (j) {
      toast("Wypełniono " + j.n + " dni");
      setTimeout(function () { location.reload(); }, 600);
    }).catch(function (e) { toast("Nie wypełniono: " + e.message, true); });
  });

  /* -------------------------------------------------------------- demo */

  document.addEventListener("click", function (ev) {
    if (ev.target.id !== "btn-av-demo") return;
    var btn = ev.target;
    btn.disabled = true;
    api("POST", "/api/dostepnosc/demo", { m: btn.dataset.m })
      .then(function (j) {
        toast("Dodano " + j.n + " przykładowych deklaracji");
        setTimeout(function () { location.reload(); }, 600);
      })
      .catch(function (e) { btn.disabled = false; toast(e.message, true); });
  });
})();
