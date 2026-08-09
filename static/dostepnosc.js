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

  /* ====================================================== TRYB ZAZNACZANIA
     Z uwagi trenera po teście z telefonu (09.08): „wypełnianie jest
     nieintuicyjne". Klikanie komórka po komórce, z przeładowaniem strony po
     każdej, nie odpowiada temu, jak trener myśli o swoim czasie — a myśli
     tygodniami („w tym jestem rano, w przyszłym mnie nie ma").

     Tryb jest domyślnie WYŁĄCZONY, bo poprawka jednego dnia to nadal
     najczęstsza czynność. Włącza się świadomie i wtedy komórka nie otwiera
     edytora, tylko wchodzi do paczki.

     Zaznaczać można też CAŁY TYDZIEŃ (klik w nagłówek bloku) i CAŁĄ KOLUMNĘ
     dnia — u koordynatora, który ustawia to wielu osobom naraz. */

  var zaznaczanie = false;
  var zaznaczone = [];                      // komórki w paczce (kolejność klikania)

  function przyciskTrybu() { return document.getElementById("btn-av-tryb"); }

  function mojeKomorki(kontener) {
    // tylko te, które wolno ruszyć — resztę serwer i tak odrzuci
    return Array.prototype.slice.call(
      (kontener || document).querySelectorAll("td.av-cell:not(.av-tylko-podglad)"));
  }

  function odswiezPasek() {
    var pasek = document.getElementById("av-pasek");
    if (!pasek) return;
    var n = zaznaczone.length;
    document.getElementById("av-n").textContent = n;
    document.getElementById("av-n-opis").textContent =
      n === 1 ? "dzień zaznaczony" : "dni zaznaczonych";
    // czyja to paczka — przy koordynatorze zaznaczenie może objąć kilka osób,
    // a wtedy trzeba to powiedzieć, zanim kliknie „cały dzień"
    var kto = {};
    zaznaczone.forEach(function (td) { kto[td.dataset.trener] = 1; });
    var osoby = Object.keys(kto);
    document.getElementById("av-pasek-kto").textContent =
      osoby.length === 1 ? osoby[0] : (osoby.length ? osoby.length + " osób" : "");
    pasek.hidden = n === 0;
  }

  function przelaczKomorke(td) {
    var i = zaznaczone.indexOf(td);
    if (i >= 0) {
      zaznaczone.splice(i, 1);
      td.classList.remove("av-zazn");
    } else {
      zaznaczone.push(td);
      td.classList.add("av-zazn");
    }
    odswiezPasek();
  }

  function odznaczWszystko() {
    zaznaczone.forEach(function (td) { td.classList.remove("av-zazn"); });
    zaznaczone = [];
    odswiezPasek();
  }

  function ustawTryb(wl) {
    zaznaczanie = wl;
    var b = przyciskTrybu();
    if (b) {
      b.setAttribute("aria-pressed", wl ? "true" : "false");
      b.textContent = wl ? "✓ Koniec zaznaczania" : "✎ Zaznaczaj dni";
      b.classList.toggle("btn-primary", !wl);
      b.classList.toggle("btn-danger", wl);
    }
    var opis = document.getElementById("av-tryb-opis");
    if (opis) {
      opis.textContent = wl
        ? "klikaj dni (albo nagłówek tygodnia), potem wybierz godziny na pasku"
        : "kliknij komórkę, żeby wpisać lub poprawić dostępność pojedynczego dnia";
    }
    document.body.classList.toggle("av-tryb-zazn", wl);
    if (!wl) odznaczWszystko();
    if (wl) zamknij();                      // edytor pojedynczego dnia schodzi
  }

  document.addEventListener("click", function (ev) {
    if (ev.target.closest("#btn-av-tryb")) {
      ustawTryb(!zaznaczanie);
      return;
    }
    if (!zaznaczanie) return;

    // cały tydzień — nagłówek bloku tygodniowego
    var glowa = ev.target.closest(".cal-week-head");
    if (glowa) {
      var sekcja = glowa.closest("section");
      var komorki = mojeKomorki(sekcja);
      var wszystkieZazn = komorki.length &&
        komorki.every(function (td) { return zaznaczone.indexOf(td) >= 0; });
      komorki.forEach(function (td) {
        var jest = zaznaczone.indexOf(td) >= 0;
        if (wszystkieZazn && jest) przelaczKomorke(td);
        if (!wszystkieZazn && !jest) przelaczKomorke(td);
      });
      return;
    }

    var td = ev.target.closest("td.av-cell");
    if (td && !td.classList.contains("av-tylko-podglad")) {
      przelaczKomorke(td);
    }
  });

  /* Paczka → serwer. Jedno żądanie na całe zaznaczenie i jedno przeładowanie,
     zamiast jednego na komórkę. */
  function wyslijPaczke(tryb, godzOd, godzDo) {
    if (!zaznaczone.length) { toast("Najpierw zaznacz dni", true); return; }
    // Grupujemy po trenerze: serwer sprawdza uprawnienia per osoba, a przy
    // koordynatorze jedna paczka może objąć kilka wierszy siatki.
    var wg = {};
    zaznaczone.forEach(function (td) {
      (wg[td.dataset.trener] = wg[td.dataset.trener] || []).push(td.dataset.data);
    });
    var nazwiska = Object.keys(wg);
    Promise.all(nazwiska.map(function (t) {
      return api("POST", "/api/dostepnosc/dni", {
        trener: t, dni: wg[t], tryb: tryb, godz_od: godzOd, godz_do: godzDo
      });
    })).then(function (wyniki) {
      var n = wyniki.reduce(function (s, j) { return s + (j.n || 0); }, 0);
      toast(tryb === "usun" ? ("Wyczyszczono " + n + " dni")
                            : ("Zapisano " + n + " dni"));
      setTimeout(function () { location.reload(); }, 400);
    }).catch(function (e) { toast("Nie zapisano: " + e.message, true); });
  }

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-av]");
    if (!btn) return;
    var akcja = btn.dataset.av;
    if (akcja === "odznacz") { odznaczWszystko(); return; }
    if (akcja === "okno") {
      var od = btn.dataset.od || document.getElementById("av-od").value;
      var doo = btn.dataset.do || document.getElementById("av-do").value;
      if (!od) { toast("Podaj godzinę początku", true); return; }
      wyslijPaczke("okno", od, doo);
      return;
    }
    wyslijPaczke(akcja);                    // caly | nie | usun
  });

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
    // W trybie zaznaczania komórka nie otwiera edytora, tylko wchodzi do paczki
    // — obsługę ma sekcja „tryb zaznaczania" niżej.
    if (zaznaczanie) return;
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
