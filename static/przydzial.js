/* =============================================================================
   Przydzielanie trenerów — panel „Kogo wysłać?" (karta leada)
   oraz edytor rejonów (ekran /rejony).

   Ta sama zasada co w app.js i dostepnosc.js: zero bibliotek, zapis przez API,
   każda operacja kończy się widocznym komunikatem.

   Przydzielenie NIE jest blokowane w żadnej kategorii — także trener oznaczony
   jako niedostępny da się wybrać. Panel sortuje i uzasadnia; decyduje człowiek.
   ============================================================================= */
(function () {
  "use strict";

  function toast(tekst, blad) {
    var el = document.getElementById("toast");
    if (!el) { if (blad) alert(tekst); return; }
    el.textContent = tekst;
    el.classList.toggle("err", !!blad);
    el.classList.add("show");
    setTimeout(function () { el.classList.remove("show"); }, blad ? 6000 : 2200);
  }

  function api(metoda, url, dane) {
    var opts = { method: metoda, headers: { "Content-Type": "application/json" } };
    if (dane) opts.body = JSON.stringify(dane);
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return { ok: r.ok }; })
        .then(function (j) {
          if (!r.ok || j.ok === false) throw new Error(j.error || ("Błąd " + r.status));
          return j;
        });
    });
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function bezPrefiksu(s) { return String(s || "").replace(/^\d+b?\.\s*/, ""); }

  /* ==================================================== panel „Kogo wysłać?" */

  var panel = document.getElementById("kd-panel");
  var aktywnyEvent = null;

  function zamknijPanel() {
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    panel.innerHTML = "";
    aktywnyEvent = null;
  }

  function wierszKandydata(k, eventId) {
    var znaczniki = "";
    if (k.rejon) znaczniki += '<span class="kd-rejon" title="jeździ po tym mieście">rejon</span>';
    if (k.n_zajec_dnia) {
      // w tooltipie to, co trener ma tego dnia — inaczej „2 tego dnia" nic nie mówi
      var co = (k.zajete || []).map(function (z) {
        return (z.godz_od || "?") + (z.godz_do ? "–" + z.godz_do : "") +
               " " + (z.szkola || z.typ || "");
      }).join("\n");
      znaczniki += '<span class="kd-dnia" title="' + esc(co) + '">' +
                   k.n_zajec_dnia + " tego dnia</span>";
    }
    var wolne = (k.wolne && k.wolne.length)
      ? '<span class="kd-wolne">wolne ' + esc(k.wolne.join(" · ")) + "</span>" : "";
    return '' +
      '<div class="kd-row kd-' + k.kategoria + '">' +
        '<span class="kd-dot" style="background:' + esc(k.kolor) + '"></span>' +
        '<span class="kd-nazwa">' + esc(bezPrefiksu(k.trener)) + "</span>" +
        '<span class="kd-powod">' + esc(k.powod) + "</span>" +
        wolne + znaczniki +
        '<span class="kd-obc nums" title="zajęć w tym miesiącu">' + k.obciazenie + "</span>" +
        '<button type="button" class="btn btn-sm ' +
          (k.kategoria === "wolny" ? "btn-primary" : "btn-secondary") +
          ' btn-kd-wybierz" data-event="' + eventId + '" data-trener="' +
          esc(k.trener) + '">' +
          (k.kategoria === "wolny" || k.kategoria === "nieznany"
            ? "Przydziel" : "Mimo to przydziel") +
        "</button>" +
      "</div>";
  }

  function rysujPanel(j, eventId) {
    var kontekst = j.kontekst || {};
    var naglowek = [
      kontekst.typ || "Spotkanie",
      j.data || "bez daty",
      (j.godz_od || "") + (j.godz_do ? "–" + j.godz_do : ""),
      kontekst.nazwa || "",
      j.miasto || ""
    ].filter(Boolean).join(" · ");

    var html = '<div class="kd-head">' +
      "<b>Kogo wysłać?</b> <span class='muted small'>" + esc(naglowek) + "</span>" +
      '<span class="kd-head-right muted small">' + j.n_wolnych + " wolnych z " + j.n + "</span>" +
      '<button type="button" class="btn btn-ghost btn-sm" id="kd-zamknij">✕</button></div>';

    if (!j.grupy.length) {
      html += '<p class="empty">Brak trenerów w słowniku.</p>';
    }
    j.grupy.forEach(function (g) {
      html += '<div class="kd-grupa kd-g-' + g.kategoria + '">' +
              '<span class="kd-grupa-l">' + esc(g.etykieta) + "</span>" +
              '<span class="muted small nums">' + g.n + "</span></div>";
      g.pozycje.forEach(function (k) { html += wierszKandydata(k, eventId); });
    });

    if (!j.godz_od) {
      html += '<p class="kd-nota muted small">Spotkanie nie ma godziny startu — ' +
              "kolizji i wyjścia poza deklarację nie da się policzyć. " +
              "Uzupełnij godziny, żeby ranking był pełny.</p>";
    }
    if (!j.miasto) {
      html += '<p class="kd-nota muted small">Placówka bez miasta — rejon pominięty.</p>';
    }
    panel.innerHTML = html;
  }

  function otworzPanel(btn) {
    var eventId = btn.dataset.id;
    if (aktywnyEvent === eventId) { zamknijPanel(); return; }
    zamknijPanel();
    aktywnyEvent = eventId;

    var karta = btn.closest(".event-card");
    panel.innerHTML = '<div class="kd-head"><b>Kogo wysłać?</b> ' +
                      '<span class="muted small">liczę kandydatów…</span></div>';
    panel.hidden = false;
    if (karta && karta.parentNode) karta.parentNode.insertBefore(panel, karta.nextSibling);

    api("GET", "/api/kandydaci?event_id=" + encodeURIComponent(eventId))
      .then(function (j) { rysujPanel(j, eventId); })
      .catch(function (e) { zamknijPanel(); toast(e.message, true); });
  }

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".btn-kandydaci");
    if (btn) { otworzPanel(btn); return; }

    if (ev.target.id === "kd-zamknij") { zamknijPanel(); return; }

    var wybierz = ev.target.closest(".btn-kd-wybierz");
    if (wybierz) {
      wybierz.disabled = true;
      api("PATCH", "/api/event/" + wybierz.dataset.event,
          { field: "trener", value: wybierz.dataset.trener })
        .then(function (j) {
          if (j.kolizja) toast(j.kolizja, true);
          else toast("Przydzielono: " + bezPrefiksu(wybierz.dataset.trener));
          setTimeout(function () { location.reload(); }, j.kolizja ? 1400 : 500);
        })
        .catch(function (e) { wybierz.disabled = false; toast(e.message, true); });
      return;
    }

    if (panel && !panel.hidden && !panel.contains(ev.target)) zamknijPanel();
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") zamknijPanel();
  });

  /* ============================================================ ekran rejonów */

  var rjEditor = document.getElementById("rj-editor");
  var rjTrener = null;

  function rjZamknij() {
    if (!rjEditor || rjEditor.hidden) return;
    rjEditor.hidden = true;
    document.body.appendChild(rjEditor);
    rjTrener = null;
  }

  function rjZaznaczone() {
    return Array.prototype.slice.call(document.querySelectorAll(".rje-m:checked"))
      .map(function (c) { return c.value; });
  }

  function rjLicznik() {
    var el = document.getElementById("rje-licznik");
    if (el) el.textContent = rjZaznaczone().length + " miast zaznaczonych";
  }

  function rjOtworz(tr) {
    rjZamknij();
    rjTrener = tr.dataset.trener;
    document.getElementById("rje-head").textContent = rjTrener;

    var maja = Array.prototype.slice.call(tr.querySelectorAll(".rj-miasta .tag"))
      .map(function (t) { return t.textContent.trim(); });
    Array.prototype.slice.call(document.querySelectorAll(".rje-m")).forEach(function (c) {
      c.checked = maja.indexOf(c.value) >= 0;
    });
    rjLicznik();

    var pod = document.getElementById("rje-podpowiedz");
    pod.hidden = true;
    document.getElementById("rje-podpowiedz-lista").textContent = "";

    tr.parentNode.insertBefore(rjEditor, tr.nextSibling);
    rjEditor.hidden = false;

    api("GET", "/api/rejon/podpowiedz?trener=" + encodeURIComponent(rjTrener))
      .then(function (j) {
        if (!j.miasta.length || rjTrener === null) return;
        document.getElementById("rje-podpowiedz-lista").textContent =
          j.miasta.map(function (m) { return m.miasto + " (" + m.n + ")"; }).join(" · ");
        pod.dataset.miasta = JSON.stringify(j.miasta.map(function (m) { return m.miasto; }));
        pod.hidden = false;
      })
      .catch(function () { /* podpowiedź jest miłym dodatkiem, nie warunkiem */ });
  }

  document.addEventListener("click", function (ev) {
    var edytuj = ev.target.closest(".btn-rj-edytuj");
    if (edytuj) { rjOtworz(edytuj.closest(".rj-row")); return; }

    if (ev.target.id === "rje-zamknij") { rjZamknij(); return; }

    if (ev.target.id === "rje-przyjmij") {
      var pod = document.getElementById("rje-podpowiedz");
      var lista = JSON.parse(pod.dataset.miasta || "[]");
      Array.prototype.slice.call(document.querySelectorAll(".rje-m")).forEach(function (c) {
        if (lista.indexOf(c.value) >= 0) c.checked = true;
      });
      rjLicznik();
      return;
    }

    if (ev.target.id === "rje-wyczysc") {
      Array.prototype.slice.call(document.querySelectorAll(".rje-m")).forEach(function (c) {
        c.checked = false;
      });
      rjLicznik();
      return;
    }

    if (ev.target.id === "rje-zapisz" && rjTrener) {
      api("POST", "/api/rejon", { trener: rjTrener, miasta: rjZaznaczone() })
        .then(function (j) {
          toast("Zapisano rejon: " + j.n + " miast");
          setTimeout(function () { location.reload(); }, 500);
        })
        .catch(function (e) { toast("Nie zapisano: " + e.message, true); });
    }
  });

  document.addEventListener("change", function (ev) {
    if (ev.target.classList && ev.target.classList.contains("rje-m")) rjLicznik();
  });
})();
