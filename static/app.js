/* =============================================================================
   System Leadów v3 — warstwa interakcji.

   Zasada: żadnych bibliotek i żadnego buildu. Cała logika to delegowane
   nasłuchy na dokumencie, więc działa też na treści dorysowanej po odświeżeniu.

   Zapis zawsze idzie przez API i zawsze kończy się widoczną informacją:
   „Zapisano" albo czerwony komunikat z powodem odrzucenia i przywróceniem
   poprzedniej wartości. Bez tego użytkownik nie wie, czy jego zmiana weszła —
   a to jest dokładnie ten rodzaj niepewności, który psuł im arkusz.
   ============================================================================= */
(function () {
  "use strict";

  /* ------------------------------------------------------------------ toast */

  var toastEl = null;
  var toastTimer = null;

  function toast(tekst, blad) {
    if (!toastEl) toastEl = document.getElementById("toast");
    if (!toastEl) { if (blad) alert(tekst); return; }
    toastEl.textContent = tekst;
    toastEl.classList.toggle("err", !!blad);
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.classList.remove("show");
    }, blad ? 6000 : 2200);
  }

  /* ------------------------------------------------------------------ HTTP */

  // Token CSRF z <meta>. Bez niego serwer odrzuca każdy zapis — obca strona
  // z jednym skryptem mogłaby inaczej działać w imieniu zalogowanego handlowca.
  function csrf() {
    var m = document.querySelector('meta[name="csrf"]');
    return m ? m.content : "";
  }

  function api(metoda, url, dane) {
    var opcje = { method: metoda, headers: { "X-CSRF": csrf() } };
    if (dane !== undefined) {
      opcje.headers["Content-Type"] = "application/json";
      opcje.body = JSON.stringify(dane);
    }
    return fetch(url, opcje).then(function (r) {
      return r.json().catch(function () { return { ok: r.ok }; })
        .then(function (j) {
          if (!r.ok || j.ok === false) {
            var e = new Error(j.error || ("Błąd " + r.status));
            e.dane = j;
            throw e;
          }
          return j;
        });
    });
  }

  /* ============================================================ EDYCJA INLINE
     Każda komórka z data-field zapisuje się sama. Pola słownikowe to <select>
     z opcjami TYLKO ze słownika — literówki („02. Olaszewska") nie da się wpisać.
  */

  document.addEventListener("change", function (ev) {
    var el = ev.target;
    if (!el.dataset || !el.dataset.field) return;

    var id = el.dataset.id;
    var pole = el.dataset.field;
    var poprzednia = el.dataset.prev || "";
    var wartosc = el.value;
    if (wartosc === poprzednia) return;

    var url = (el.dataset.api === "event")
      ? "/api/event/" + id
      : "/api/lead/" + id;

    el.classList.add("saving");
    api("PATCH", url, { field: pole, value: wartosc })
      .then(function (j) {
        el.dataset.prev = wartosc;
        el.classList.remove("saving");
        odswiezPoTerminie(id, j);
        if (j.kolizja) {
          toast("Zapisano. UWAGA: " + j.kolizja, true);
        } else {
          toast("Zapisano");
        }
      })
      .catch(function (e) {
        el.value = poprzednia;          // rollback — w bazie nic się nie zmieniło
        el.classList.remove("saving");
        toast("Nie zapisano: " + e.message, true);
      });
  });

  /* Po zmianie terminu albo statusu podświetlenie „po terminie" musi się przeliczyć
     — inaczej ekran kłamie do następnego odświeżenia. */
  function odswiezPoTerminie(id, j) {
    if (!j || typeof j.po_terminie === "undefined") return;
    var td = document.querySelector('[data-deadline-of="' + id + '"]');
    if (td) td.classList.toggle("cell-overdue", !!j.po_terminie);
  }

  /* ======================================================== ZAZNACZANIE WIERSZY
     Główny ruch koordynatora: zaznacz kilka placówek → przypisz handlowcowi
     z terminem ostatecznym. Jednym żądaniem, bez kopiowania wierszy.
  */

  function zaznaczone() {
    return Array.prototype.slice
      .call(document.querySelectorAll("input.chk:checked"))
      .map(function (c) { return parseInt(c.value, 10); });
  }

  function odswiezPasek() {
    var pasek = document.getElementById("bulkbar");
    if (!pasek) return;
    var ids = zaznaczone();
    var licznik = document.getElementById("bulk-n");
    if (licznik) licznik.textContent = ids.length;
    pasek.hidden = ids.length === 0;
  }

  // Termin przy przypisywaniu: z góry wypełniony na dziś + 14 dni — Kasia
  // rozdaje szkoły „na 2 tygodnie", więc kalendarzyk służy tylko do wyjątków.
  // Data składana lokalnie (nie toISOString), bo ta liczy w UTC i tuż po
  // północy podstawiałaby wczorajszą datę.
  (function () {
    var pole = document.getElementById("bulk-deadline");
    if (!pole || pole.value) return;
    var t = new Date();
    t.setDate(t.getDate() + 14);
    pole.value = t.getFullYear() + "-" + ("0" + (t.getMonth() + 1)).slice(-2)
               + "-" + ("0" + t.getDate()).slice(-2);
  })();

  document.addEventListener("change", function (ev) {
    if (ev.target.id === "chk-all") {
      var stan = ev.target.checked;
      document.querySelectorAll("input.chk").forEach(function (c) {
        c.checked = stan;
        c.closest("tr").classList.toggle("wybrany", stan);
      });
      odswiezPasek();
      return;
    }
    if (ev.target.classList && ev.target.classList.contains("chk")) {
      var tr = ev.target.closest("tr");
      if (tr) tr.classList.toggle("wybrany", ev.target.checked);
      odswiezPasek();
    }
  });

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-akcja]");
    if (!btn) return;
    var akcja = btn.dataset.akcja;

    if (akcja === "odznacz") {
      document.querySelectorAll("input.chk").forEach(function (c) {
        c.checked = false;
        c.closest("tr").classList.remove("wybrany");
      });
      var all = document.getElementById("chk-all");
      if (all) all.checked = false;
      odswiezPasek();
      return;
    }

    // Strzałki licznika dni działają bez zaznaczenia — ustawianie liczby
    // to nie akcja na rekordach.
    if (akcja === "dni") {
      var licznikDni = document.getElementById("bulk-dni");
      if (licznikDni) {
        var v = parseInt(licznikDni.value, 10) || 14;
        v = Math.min(365, Math.max(1, v + parseInt(btn.dataset.krok, 10)));
        licznikDni.value = v;
      }
      return;
    }

    var ids = zaznaczone();
    if (!ids.length) { toast("Najpierw zaznacz rekordy", true); return; }

    if (akcja === "przedluz") {
      var poleDni = document.getElementById("bulk-dni");
      var dni = poleDni ? parseInt(poleDni.value, 10) : 14;
      if (!dni || dni < 1 || dni > 365) { toast("Podaj liczbę dni (1–365)", true); return; }
      api("POST", "/api/przedluz", { ids: ids, dni: dni }).then(function (j) {
        toast("Przedłużono termin " + j.n + " rekordów o " + j.dni + " dni");
        setTimeout(function () { location.reload(); }, 500);
      }).catch(function (e) { toast("Nie przedłużono: " + e.message, true); });
      return;
    }

    if (akcja === "przypisz") {
      var h = document.getElementById("bulk-handlowiec");
      var d = document.getElementById("bulk-deadline");
      if (!h || !h.value) { toast("Wybierz handlowca", true); return; }
      api("POST", "/api/przypisz", {
        ids: ids, handlowiec: h.value, deadline: d ? d.value : ""
      }).then(function (j) {
        toast("Przypisano " + j.n + " rekordów do " + h.value);
        setTimeout(function () { location.reload(); }, 500);
      }).catch(function (e) { toast("Nie przypisano: " + e.message, true); });
    }

    if (akcja === "odbierz") {
      if (!confirm("Odebrać " + ids.length + " leadów handlowcom?\n"
                 + "Trafią do puli „Niewykorzystane rekordy” — dane zostają.")) return;
      api("POST", "/api/odbierz", { ids: ids }).then(function (j) {
        toast("Odebrano " + j.n + " leadów — są w puli zwrotnej");
        setTimeout(function () { location.reload(); }, 500);
      }).catch(function (e) { toast("Nie udało się: " + e.message, true); });
    }
  });

  /* ============================================================ PLAN TYGODNIA
     „Wybrane szkoły na tydzień do góry" — przypięcie gwiazdką.
  */

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".pin-btn");
    if (!btn) return;
    var wlacz = btn.dataset.pin !== "1";
    api("POST", "/api/pin", { id: parseInt(btn.dataset.pinId, 10), pin: wlacz })
      .then(function (j) {
        btn.dataset.pin = j.pin ? "1" : "0";
        btn.textContent = j.pin ? "★" : "☆";
        btn.classList.toggle("on", !!j.pin);
        toast(j.pin ? "Przypięto na tydzień " + j.pin : "Odpięto z planu tygodnia");
      })
      .catch(function (e) { toast("Nie zapisano: " + e.message, true); });
  });

  /* ============================================================ LEAD: NOWY / USUŃ */

  document.addEventListener("click", function (ev) {
    if (ev.target.id !== "btn-nowy-lead") return;
    var panel = document.getElementById("nowa-placowka");
    if (!panel) return;
    panel.hidden = !panel.hidden;
    if (!panel.hidden) {
      var pole = document.getElementById("np-nazwa");
      if (pole) pole.focus();
    }
  });

  document.addEventListener("click", function (ev) {
    if (ev.target.id !== "btn-zapisz-lead") return;
    var nazwa = (document.getElementById("np-nazwa") || {}).value || "";
    if (!nazwa.trim()) { toast("Podaj nazwę placówki", true); return; }
    api("POST", "/api/lead", {
      nazwa: nazwa.trim(),
      typ: (document.getElementById("np-typ") || {}).value || "",
      miejscowosc: (document.getElementById("np-miejscowosc") || {}).value || "",
      handlowiec: (document.getElementById("np-handlowiec") || {}).value || ""
    }).then(function (j) { location.href = "/lead/" + j.id; })
      .catch(function (e) { toast("Nie dodano: " + e.message, true); });
  });

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("#btn-usun-lead");
    if (!btn) return;
    if (!confirm("Usunąć ten lead wraz ze spotkaniami? Tego nie da się cofnąć.")) return;
    api("DELETE", "/api/lead/" + btn.dataset.id)
      .then(function () { location.href = "/baza"; })
      .catch(function (e) { toast("Nie usunięto: " + e.message, true); });
  });

  /* Oddanie leada przez handlowca (pkt 12, 30.08): „może usuwać, ale tylko
     wpisując powód — i on się pojawia u koordynatora na czerwono".
     Ten sam wzorzec `prompt` co przy odwołaniu spotkania — patrz niżej. */
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("#btn-oddaj-lead");
    if (!btn) return;
    var powod = prompt("Dlaczego oddajesz tę szkołę?\n\n" +
                       "Zniknie z Twojej listy i wróci do puli koordynatora " +
                       "z Twoim nazwiskiem i tym powodem. Notatki i historia zostają.");
    if (powod === null) return;                 // Anuluj — nie robimy nic
    if (!powod.trim()) {
      toast("Bez powodu nie da się oddać — koordynator nie będzie wiedział, co poprawić.", true);
      return;
    }
    api("POST", "/api/lead/" + btn.dataset.id + "/oddaj", { powod: powod.trim() })
      .then(function () {
        toast("Oddano — szkoła wróciła do koordynatora");
        setTimeout(function () { location.href = "/leady"; }, 900);
      })
      .catch(function (e) { toast("Nie oddano: " + e.message, true); });
  });

  /* ============================================================ SPOTKANIA (eventy)
     Dodanie DRUGIEGO DT temu samemu trenerowi w tym samym dniu MUSI się udać —
     to jest wprost naprawa zgłoszonego buga. Kolizja godzin to ostrzeżenie.
  */

  document.addEventListener("click", function (ev) {
    if (ev.target.id !== "btn-dodaj-event") return;
    var form = document.getElementById("event-form");
    if (!form) return;

    var dane = { lead_id: parseInt(form.dataset.lead, 10) };
    form.querySelectorAll("[name]").forEach(function (el) {
      if (el.value !== "") dane[el.name] = el.value;
    });
    if (!dane.typ) dane.typ = "DT";
    if (!dane.data) { toast("Podaj datę spotkania", true); return; }

    api("POST", "/api/event", dane)
      .then(function (j) {
        if (j.kolizja) {
          toast("Dodano, ale UWAGA: " + j.kolizja, true);
          setTimeout(function () { location.reload(); }, 3000);
        } else {
          toast("Dodano spotkanie");
          setTimeout(function () { location.reload(); }, 500);
        }
      })
      .catch(function (e) { toast("Nie dodano: " + e.message, true); });
  });

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".btn-usun-event");
    if (!btn) return;
    if (!confirm("Usunąć to spotkanie BEZ ŚLADU?\n\n" +
                 "Zniknie razem z powodem i historią. Jeśli szkoła odmówiła, " +
                 "użyj „Odwołaj” — wtedy zostanie widoczne w raporcie.")) return;
    api("DELETE", "/api/event/" + btn.dataset.id)
      .then(function () { location.reload(); })
      .catch(function (e) { toast("Nie usunięto: " + e.message, true); });
  });

  /* P08 — ODWOŁANIE SPOTKANIA (zgłoszenie K12 Kasi, 20.08)
     „nie widzę też możliwości wykasowania czegoś z kalendarza, w razie jakby
     np. szkoła w ostatnim momencie odmówiła współpracy".

     `prompt` zamiast własnego okienka jest tu świadomy: działa na telefonie,
     nie wymaga ani jednej linii CSS i nie da się go zostawić otwartego
     w tle. Ten formularz ma jedno pole i jest wypełniany raz na jakiś czas. */
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-odwolaj], .btn-odwolaj-event");
    if (!btn) return;
    ev.preventDefault();
    var id = btn.dataset.odwolaj || btn.dataset.id;
    var powod = prompt("Dlaczego odwołujemy to spotkanie?\n\n" +
                       "Zapisze się razem z Twoim nazwiskiem i datą. Wpis zniknie " +
                       "z grafiku, ale zostanie w historii szkoły.");
    if (powod === null) return;                 // Anuluj — nie robimy nic
    if (!powod.trim()) {
      toast("Bez powodu nie da się odwołać — za miesiąc nikt tego nie odtworzy.", true);
      return;
    }
    api("POST", "/api/event/" + id + "/odwolaj", { powod: powod.trim() })
      .then(function (j) {
        if (j && j.wrocil_do_umawiania) {
          toast("Odwołane. Szkoła wróciła na listę do umówienia.");
          setTimeout(function () { location.reload(); }, 1200);
        } else {
          location.reload();
        }
      })
      .catch(function (e) { toast("Nie odwołano: " + e.message, true); });
  });

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".btn-przywroc-event");
    if (!btn) return;
    if (!confirm("Cofnąć odwołanie? Spotkanie wróci do grafiku.")) return;
    api("POST", "/api/event/" + btn.dataset.id + "/odwolaj", { cofnij: true })
      .then(function () { location.reload(); })
      .catch(function (e) { toast("Nie cofnięto: " + e.message, true); });
  });

  /* Odwołanie JEDNYCH zajęć z cyklu (pkt 21, 30.08) — reszta pakietu zostaje.
     Osobny przycisk i osobny endpoint niż odwołanie całego spotkania: kafel
     cyklu to wystąpienie reguły, więc odwołanie „po id" zdjęłoby z grafiku
     wszystkie terminy naraz. Dlatego w treści pytania jest KONKRETNA data. */
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".btn-odwolaj-termin");
    if (!btn) return;
    ev.preventDefault();
    var powod = prompt("Dlaczego odwołujemy zajęcia " + btn.dataset.data + "?\n\n" +
                       "Odwołany zostanie TYLKO ten termin — reszta cyklu jedzie " +
                       "dalej. Zapisze się z Twoim nazwiskiem i datą.");
    if (powod === null) return;
    if (!powod.trim()) {
      toast("Bez powodu nie da się odwołać — za miesiąc nikt tego nie odtworzy.", true);
      return;
    }
    api("POST", "/api/event/" + btn.dataset.id + "/odwolaj-termin",
        { data: btn.dataset.data, powod: powod.trim() })
      .then(function () { location.reload(); })
      .catch(function (e) { toast("Nie odwołano: " + e.message, true); });
  });

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".btn-przywroc-termin");
    if (!btn) return;
    if (!confirm("Przywrócić zajęcia " + btn.dataset.data + " do grafiku?")) return;
    api("POST", "/api/event/" + btn.dataset.id + "/odwolaj-termin",
        { data: btn.dataset.data, cofnij: true })
      .then(function () { location.reload(); })
      .catch(function (e) { toast("Nie cofnięto: " + e.message, true); });
  });

  /* ============================================================ SŁOWNIKI */

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".btn-dodaj-slownik");
    if (!btn) return;
    var karta = btn.closest(".dict-card");
    var input = karta ? karta.querySelector(".dict-nowa") : null;
    if (!input || !input.value.trim()) { toast("Wpisz nazwę pozycji", true); return; }
    api("POST", "/api/slownik", { rodzaj: btn.dataset.rodzaj, wartosc: input.value.trim() })
      .then(function () { location.reload(); })
      .catch(function (e) { toast("Nie dodano: " + e.message, true); });
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Enter") return;
    if (!ev.target.classList || !ev.target.classList.contains("dict-nowa")) return;
    ev.preventDefault();
    var karta = ev.target.closest(".dict-card");
    var btn = karta ? karta.querySelector(".btn-dodaj-slownik") : null;
    if (btn) btn.click();
  });

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".btn-usun-slownik");
    if (!btn) return;
    api("DELETE", "/api/slownik/" + btn.dataset.slownikId)
      .then(function () {
        var poz = btn.closest(".dict-item");
        if (poz) poz.remove();
        toast("Usunięto pozycję");
      })
      .catch(function (e) {
        /* 409 = pozycja jest w użyciu. To celowa blokada: usunięcie zostawiłoby
           w bazie wartości spoza słownika, czyli ten sam bałagan, który naprawiamy. */
        toast(e.message, true);
      });
  });

  /* kolor trenera — widać go natychmiast w kalendarzu */
  document.addEventListener("change", function (ev) {
    var el = ev.target;
    if (!el.dataset || !el.dataset.kolorId) return;
    api("PATCH", "/api/slownik/" + el.dataset.kolorId, { kolor: el.value })
      .then(function () { toast("Zapisano kolor"); })
      .catch(function (e) { toast("Nie zapisano: " + e.message, true); });
  });

  /* ---- aliasy: „zapis w arkuszu" → wartość kanoniczna ---- */

  function slownikiJSON() {
    var el = document.getElementById("slowniki-json");
    if (!el) return {};
    try { return JSON.parse(el.textContent); } catch (e) { return {}; }
  }

  function odswiezWartosciAliasu() {
    var rodzaj = document.getElementById("alias-rodzaj");
    var cel = document.getElementById("alias-wartosc");
    if (!rodzaj || !cel) return;
    var lista = slownikiJSON()[rodzaj.value] || [];
    cel.innerHTML = "";
    lista.forEach(function (p) {
      var o = document.createElement("option");
      o.value = p.wartosc;
      o.textContent = p.wartosc;
      cel.appendChild(o);
    });
    if (!lista.length) {
      var o2 = document.createElement("option");
      o2.value = "";
      o2.textContent = "— brak pozycji w tym słowniku —";
      cel.appendChild(o2);
    }
  }

  document.addEventListener("change", function (ev) {
    if (ev.target.id === "alias-rodzaj") odswiezWartosciAliasu();
  });

  document.addEventListener("click", function (ev) {
    if (ev.target.id !== "btn-dodaj-alias") return;
    var rodzaj = document.getElementById("alias-rodzaj").value;
    var alias = document.getElementById("alias-alias").value.trim();
    var wartosc = document.getElementById("alias-wartosc").value;
    if (!alias || !wartosc) { toast("Podaj zapis z arkusza i wartość docelową", true); return; }
    api("POST", "/api/alias", { rodzaj: rodzaj, alias: alias, wartosc: wartosc })
      .then(function () { location.reload(); })
      .catch(function (e) { toast("Nie dodano: " + e.message, true); });
  });

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".btn-usun-alias");
    if (!btn) return;
    api("DELETE", "/api/alias/" + btn.dataset.aliasId)
      .then(function () {
        var tr = btn.closest("tr");
        if (tr) tr.remove();
        toast("Usunięto alias");
      })
      .catch(function (e) { toast("Nie usunięto: " + e.message, true); });
  });

  /* ================================================== ZWROT DO PULI (v5)
     Automat i tak przeleci sam raz na godzinę — ten przycisk służy temu, żeby
     koordynator nie musiał czekać, gdy właśnie patrzy na listę. Potwierdzenie
     jest obowiązkowe: to odbiera pracę konkretnym ludziom. */

  document.addEventListener("click", function (ev) {
    if (ev.target.id !== "btn-zwrot") return;
    var btn = ev.target;
    var ile = (btn.textContent.match(/\((\d+)\)/) || [])[1] || "0";
    if (!confirm("Zwrócić " + ile + " szkół do puli nieprzydzielonych?\n\n" +
                 "Handlowiec i termin zostaną wyczyszczone. Notatki, kontakty " +
                 "i historia zostają przy placówce.")) return;
    btn.disabled = true;
    btn.textContent = "Zwracam…";
    api("POST", "/api/zwrot", {})
      .then(function (j) {
        toast("Zwrócono do puli: " + j.n);
        setTimeout(function () { location.reload(); }, 700);
      })
      .catch(function (e) {
        btn.disabled = false;
        btn.textContent = "Zwróć teraz (" + ile + ")";
        toast("Nie zwrócono: " + e.message, true);
      });
  });

  /* ============================================================ DANE DEMO */

  document.addEventListener("click", function (ev) {
    if (ev.target.id !== "btn-demo") return;
    var btn = ev.target;
    btn.disabled = true;
    btn.textContent = "Wczytuję…";
    api("POST", "/api/demo")
      .then(function () { location.href = "/pulpit"; })
      .catch(function (e) {
        btn.disabled = false;
        btn.textContent = "Wczytaj dane demo";
        toast("Nie wczytano danych demo: " + e.message, true);
      });
  });

  /* ============================================================ start */

  document.addEventListener("DOMContentLoaded", function () {
    odswiezPasek();
    odswiezWartosciAliasu();
  });
})();
