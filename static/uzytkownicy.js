/* =============================================================================
   Panel kont — nadawanie PIN-ów, role, blokowanie.
   ============================================================================= */
(function () {
  "use strict";

  if (!document.querySelector(".uz-pin-nadaj, .uz-dodaj")) return;

  var okno = document.getElementById("uz-okno");

  function csrf() {
    var m = document.querySelector('meta[name="csrf"]');
    return m ? m.content : "";
  }

  function api(metoda, url, dane) {
    return fetch(url, {
      method: metoda,
      headers: { "Content-Type": "application/json", "X-CSRF": csrf() },
      body: dane === undefined ? undefined : JSON.stringify(dane)
    }).then(function (r) {
      return r.json().catch(function () { return { ok: r.ok }; }).then(function (j) {
        if (!r.ok || j.ok === false) throw new Error(j.error || "Błąd " + r.status);
        return j;
      });
    });
  }

  function toast(t, blad) {
    var el = document.getElementById("toast");
    if (!el) { alert(t); return; }
    el.textContent = t;
    el.classList.toggle("err", !!blad);
    el.classList.add("show");
    setTimeout(function () { el.classList.remove("show"); }, blad ? 6000 : 2500);
  }

  /* PIN pokazujemy RAZ — w bazie zostaje tylko jego skrót, więc jeśli
     koordynator go teraz nie zapisze, trzeba będzie nadać nowy. */
  function pokazPin(osoba, pin) {
    document.getElementById("uz-okno-kto").textContent = osoba;
    document.getElementById("uz-okno-pin").textContent = pin;
    okno.hidden = false;
  }

  document.getElementById("uz-okno-ok").addEventListener("click", function () {
    okno.hidden = true;
    location.reload();
  });

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("button");
    if (!b) return;

    if (b.classList.contains("uz-pin-nadaj")) {
      var osoba = b.dataset.osoba;
      if (!confirm("Nadać nowy PIN dla „" + osoba + "”?\n\n" +
                   "Poprzedni przestanie działać, a konto zostanie odblokowane.")) return;
      b.disabled = true;
      api("POST", "/api/uzytkownik/pin", { osoba: osoba })
        .then(function (j) { pokazPin(j.osoba, j.pin); })
        .catch(function (e) { b.disabled = false; toast("Nie nadano: " + e.message, true); });
      return;
    }

    if (b.classList.contains("uz-dodaj")) {
      var kto = b.dataset.osoba;
      b.disabled = true;
      api("POST", "/api/uzytkownik", { osoba: kto, rola: "handlowiec" })
        .then(function (j) { pokazPin(j.osoba, j.pin); })
        .catch(function (e) { b.disabled = false; toast("Nie dodano: " + e.message, true); });
      return;
    }

    if (b.classList.contains("uz-wylacz")) {
      var wl = b.dataset.aktywny === "1";
      b.disabled = true;
      api("PATCH", "/api/uzytkownik", { osoba: b.dataset.osoba, aktywny: wl ? 1 : 0 })
        .then(function () { location.reload(); })
        .catch(function (e) { b.disabled = false; toast("Nie zmieniono: " + e.message, true); });
    }
  });

  document.addEventListener("change", function (ev) {
    var sel = ev.target.closest(".uz-rola-wybor");
    if (!sel) return;
    var poprzednia = sel.dataset.poprzednia || "";
    api("PATCH", "/api/uzytkownik", { osoba: sel.dataset.osoba, rola: sel.value })
      .then(function () {
        sel.dataset.poprzednia = sel.value;
        toast("Rola zmieniona");
      })
      .catch(function (e) {
        if (poprzednia) sel.value = poprzednia;
        toast("Nie zmieniono: " + e.message, true);
      });
  });

  document.querySelectorAll(".uz-rola-wybor").forEach(function (s) {
    s.dataset.poprzednia = s.value;
  });
})();
