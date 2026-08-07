/* =============================================================================
   AWARIA W TRAKCIE WYPEŁNIANIA — wspólne dla obu wariantów formularza.

   Pytanie z 07.08: „co w przypadku awarii w trakcie wypełniania formularza?".
   Awaria ma kilka postaci i każda wymaga czego innego. Ten plik obsługuje je
   wszystkie, bo są wspólne dla v1 i v2.

   1. ZNIKA ZASIĘG / GAŚNIE EKRAN / TELEFON SIĘ RESETUJE — zanim naciśnie Zapisz
      → szkic leci do localStorage po każdej zmianie pola (to robi już sam
        formularz). Po powrocie pyta „przywrócić?". Dane siedzą w telefonie,
        nie w pamięci przeglądarki, więc przeżywają zamknięcie i restart.

   2. UŻYTKOWNIK PRZYPADKIEM ZAMYKA KARTĘ albo klika wstecz
      → `pilnujWyjscia` zakłada ostrzeżenie przeglądarki. Nie zapobiega utracie
        w 100% (systemowe zamknięcie aplikacji go ominie), ale łapie przypadek
        najczęstszy: nieopatrzny ruch kciukiem.

   3. NACISKA ZAPISZ, A ZAPIS NIE DOCHODZI — brak sieci, serwer nie odpowiada,
      błąd 500
      → to jest przypadek najgorszy, bo handlowiec MYŚLI, że skończył.
        Cała treść formularza ląduje w localStorage jako „do wysłania", a przy
        następnym wejściu (i od razu po błędzie) wisi czerwona ramka
        „Formularz NIE został wysłany — Ponów wysyłkę". Jedno kliknięcie
        i dane idą do bazy. Nic nie trzeba wpisywać drugi raz.

   4. ZAPIS DOSZEDŁ, ALE ODPOWIEDŹ NIE WRÓCIŁA (zerwanie w pół drogi)
      → wysyłka niesie `klucz_zapisu` — losowy identyfikator tej konkretnej
        próby. Serwer, widząc drugi raz ten sam klucz, zwraca poprzedni wynik
        zamiast tworzyć drugi lead. Dzięki temu „Ponów wysyłkę" jest bezpieczne
        także wtedy, gdy pierwsza próba jednak przeszła.

   CZEGO TO NIE ROBI: nie jest to praca offline. Wysyłka wymaga sieci — moduł
   pilnuje tylko, żeby przy jej braku NIC SIĘ NIE ZGUBIŁO i żeby dało się
   dokończyć jednym kliknięciem. Kolejka wysyłająca sama z siebie po odzyskaniu
   zasięgu to osobny etap.
   ============================================================================= */
(function () {
  "use strict";

  function losowyKlucz() {
    // Wystarczy unikalność w obrębie jednego handlowca i jednego dnia —
    // nie jest to identyfikator kryptograficzny.
    return "z" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  function api(url, dane) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dane)
    }).then(function (r) {
      return r.json().catch(function () { return { ok: r.ok }; }).then(function (j) {
        if (!r.ok || j.ok === false) throw new Error(j.error || ("Błąd " + r.status));
        return j;
      });
    });
  }

  /**
   * @param opts.klucz        klucz w localStorage (inny dla v1 i v2)
   * @param opts.kontener     element, na początku którego pojawi się ramka
   * @param opts.handlowiec   czyj formularz (nie pokazujemy cudzego)
   * @param opts.toast        funkcja komunikatu
   * @param opts.naSukces     wywołane po udanym ponowieniu, dostaje odpowiedź
   */
  function utworz(opts) {
    var ramka = null;

    function zapisany() {
      try {
        var s = JSON.parse(localStorage.getItem(opts.klucz) || "null");
        if (!s || s.handlowiec !== opts.handlowiec) return null;
        return s;
      } catch (e) { return null; }
    }

    function wyczysc() {
      localStorage.removeItem(opts.klucz);
      if (ramka) { ramka.remove(); ramka = null; }
    }

    /** Wywoływane, gdy zapis się nie powiódł. Treść formularza nie ginie. */
    function zapamietaj(payload, blad) {
      payload.klucz_zapisu = payload.klucz_zapisu || losowyKlucz();
      try {
        localStorage.setItem(opts.klucz, JSON.stringify({
          kiedy: new Date().toISOString(),
          handlowiec: opts.handlowiec,
          blad: String(blad || ""),
          payload: payload
        }));
      } catch (e) {
        // Pamięć pełna albo tryb prywatny. Wtedy zostaje sam komunikat —
        // dlatego jest wyraźny i nie znika sam.
      }
      pokaz();
    }

    function opisCzasu(iso) {
      var d = new Date(iso);
      return String(d.getHours()).padStart(2, "0") + ":" +
             String(d.getMinutes()).padStart(2, "0");
    }

    function pokaz() {
      var s = zapisany();
      if (!s) return;
      if (ramka) ramka.remove();

      var szkola = (s.payload.placowka && s.payload.placowka.nazwa) || "";
      var data = (s.payload.dt && s.payload.dt.data) || "";

      ramka = document.createElement("div");
      ramka.className = "f-niewyslany";
      ramka.innerHTML =
        "<b>Formularz NIE został wysłany</b>" +
        "<p>Próba z godz. " + opisCzasu(s.kiedy) +
          (szkola ? " · " + szkola : "") + (data ? " · DT " + data : "") +
          " — <span class=\"muted\">" + (s.blad || "brak połączenia") + "</span>." +
          "<br>Dane są zapisane w tym telefonie. Naciśnij „Ponów wysyłkę”, " +
          "gdy wróci zasięg — nic nie trzeba wpisywać drugi raz.</p>" +
        "<div class=\"f-niewyslany-akcje\">" +
          "<button type=\"button\" class=\"f-ponow\">Ponów wysyłkę</button>" +
          "<button type=\"button\" class=\"f-odrzuc\">Odrzuć</button>" +
        "</div>";

      ramka.querySelector(".f-ponow").addEventListener("click", function () {
        var btn = this;
        btn.disabled = true;
        btn.textContent = "Wysyłam…";
        api("/api/formularz", s.payload)
          .then(function (j) {
            wyczysc();
            if (opts.toast) opts.toast("Wysłano: " + j.placowka);
            if (opts.naSukces) opts.naSukces(j);
          })
          .catch(function (e) {
            btn.disabled = false;
            btn.textContent = "Ponów wysyłkę";
            if (opts.toast) opts.toast("Nadal nie idzie: " + e.message, true);
          });
      });

      ramka.querySelector(".f-odrzuc").addEventListener("click", function () {
        if (!confirm("Odrzucić niewysłany formularz? Wpisane dane przepadną.")) return;
        wyczysc();
      });

      opts.kontener.insertBefore(ramka, opts.kontener.firstChild);
      ramka.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    // przy wejściu na ekran sprawdzamy, czy coś zostało niewysłane
    if (zapisany()) pokaz();

    return { zapamietaj: zapamietaj, wyczysc: wyczysc, nowyKlucz: losowyKlucz };
  }

  /**
   * Ostrzeżenie przeglądarki przy zamknięciu karty z niezapisanymi danymi.
   * `czyCosJest` ma zwrócić true, gdy jest co tracić.
   */
  function pilnujWyjscia(czyCosJest) {
    window.addEventListener("beforeunload", function (ev) {
      if (!czyCosJest()) return;
      // Treści komunikatu nie da się ustawić — przeglądarki pokazują własną.
      ev.preventDefault();
      ev.returnValue = "";
      return "";
    });
  }

  /**
   * Przycisk „Zakończ” — jedyne wyjście z formularza. Pyta, gdy jest co stracić.
   */
  function pilnujZakonczenia(link, czyCosJest) {
    if (!link) return;
    link.addEventListener("click", function (ev) {
      if (!czyCosJest()) return;
      if (!confirm("Masz niezapisane dane w formularzu.\n\n" +
                   "Wyjść bez zapisania? Szkic zostanie w telefonie, " +
                   "więc możesz do niego wrócić.")) {
        ev.preventDefault();
      }
    });
  }

  window.FxAwaria = {
    utworz: utworz,
    pilnujWyjscia: pilnujWyjscia,
    pilnujZakonczenia: pilnujZakonczenia,
    losowyKlucz: losowyKlucz
  };
})();
