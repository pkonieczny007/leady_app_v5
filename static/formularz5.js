/* =============================================================================
   FORMULARZ v5 — KASKADA OD PLACÓWKI

   Odwrócone sterowanie wobec v1–v4: tam ekran ma stałą listę sekcji i jeden
   wyłącznik („czy było DT"), tu najpierw wiadomo GDZIE jesteś, potem CO
   ustaliłeś, a sekcje rozsuwają się dopiero po zaznaczeniu chipa.

   TRZY RZECZY, KTÓRE TRZYMAJĄ TEN PLIK W RYZACH

   1. Sekcje rodzajów zajęć NIE są pisane ręcznie w HTML — są rysowane
      z jednej definicji `POLA_RODZAJU`. Sześć bloków HTML trzeba by trzymać
      zgodne ze sobą i przy siódmym rodzaju ktoś zapomniałby o jednym.

   2. Odznaczenie chipa ZWIJA sekcję, ale nie kasuje wpisanego. Dane siedzą
      w `stan.zajecia` i w szkicu; do żądania nie wchodzą. Handlowiec, który
      odznaczył przez pomyłkę, nie traci pracy — a przy zapisie z wypełnioną,
      lecz odznaczoną sekcją dostaje OSTRZEŻENIE (ostrzegamy, nie blokujemy).

   3. Geografia idzie przez adapter `/api/formularz/geografia`. Rysujemy tyle
      selectów, ile serwer poda osi — dziś jedną (miejscowość), po migracji na
      RSPO dwie (powiat → miejscowość). Ten plik nie zna nazw kolumn, więc
      przełączenie geografii go nie dotknie.

   Zapis: jedno żądanie `POST /api/formularz` z `klucz_zapisu`, ta sama
   walidacja i ta sama kolejka awaryjna co w v1–v4. Nowe jest wyłącznie to,
   że zajęcia jadą LISTĄ (`zajecia: [...]`) — stare warianty wysyłają dwa
   bloki `dt`/`cykl` i nic o tym nie wiedzą.
   ============================================================================= */
(function () {
  "use strict";

  var root = document.getElementById("f5");
  if (!root) return;

  var HANDLOWIEC = root.dataset.handlowiec || "";
  var DZIS = root.dataset.dzis || "";
  var SL = window.F5_SLOWNIKI || {};
  var KLUCZ_SZKICU = "f5-szkic";
  var KLUCZ_AWARII = "f5-niewyslany";

  function $(id) { return document.getElementById(id); }

  function toast(tekst, blad) {
    var t = $("toast");
    if (!t) return;
    t.textContent = tekst;
    t.className = "toast toast-on" + (blad ? " toast-err" : "");
    setTimeout(function () { t.className = "toast"; }, blad ? 6000 : 3500);
  }

  function api(url, dane) {
    var m = document.querySelector('meta[name="csrf"]');
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF": m ? m.content : "" },
      body: JSON.stringify(dane)
    }).then(function (r) {
      return r.json().catch(function () { return { ok: r.ok }; }).then(function (j) {
        if (!r.ok || j.ok === false) throw new Error(j.error || ("Błąd " + r.status));
        return j;
      });
    });
  }

  function bezOgonkow(s) {
    return String(s || "").toLowerCase()
      .replace(/ą/g, "a").replace(/ć/g, "c").replace(/ę/g, "e").replace(/ł/g, "l")
      .replace(/ń/g, "n").replace(/ó/g, "o").replace(/ś/g, "s")
      .replace(/ź/g, "z").replace(/ż/g, "z");
  }

  // ---------------------------------------------------------------- stan

  var stan = {
    osie: [],           // definicje z serwera
    wybor: {},          // wybrane wartości osi (poziom → wartość)
    rodzaj: "",         // filtr typu placówki na liście
    placowki: [],
    placowka: null,     // wybrany rekord
    zajecia: {},        // typ → { pola }
    wlaczone: {}        // typ → czy chip zaznaczony
  };

  // ------------------------------------------------- definicje pól sekcji

  /* Rodzaj zajęć rozpoznajemy po nazwie typu, nie po sztywnej liście: klient
     dodaje pozycje słownika sam, a każda „CYKLICZNE-COŚ" jest cyklem. */
  function czyCykl(typ) { return /^CYKLICZNE/.test(typ); }

  var POLE_TRENER = { k: "trener", e: "Prowadzący", t: "slownik", s: "trener" };
  var POLE_UWAGI = { k: "uwagi", e: "Uwagi", t: "txt" };

  function polaRodzaju(typ) {
    if (typ === "DT") {
      return [
        { k: "data", e: "Data DT", t: "date", wym: true },
        { k: "godz_od", e: "Godz. od", t: "time" },
        { k: "godz_do", e: "Godz. do", t: "time" },
        POLE_TRENER,
        { k: "ilosc_klas", e: "Ile klas", t: "int" },
        { k: "ilosc_dzieci", e: "Ile dzieci", t: "int" },
        { k: "numer_sali", e: "Nr sali", t: "text" },
        POLE_UWAGI
      ];
    }
    if (czyCykl(typ)) {
      return [
        { k: "godz_od", e: "Godz. od", t: "time" },
        { k: "godz_do", e: "Godz. do", t: "time" },
        POLE_TRENER,
        { k: "sprzet", e: "Sprzęt", t: "slownik", s: "sprzet" },
        { k: "grupa", e: "Grupa", t: "text" },
        POLE_UWAGI
      ];
    }
    // jednorazowe: JEDNORAZÓWKA, FESTYN, VR, INNE…
    return [
      { k: "data", e: "Data", t: "date", wym: true },
      { k: "godz_od", e: "Godz. od", t: "time" },
      { k: "godz_do", e: "Godz. do", t: "time" },
      POLE_TRENER,
      { k: "grupa", e: "Dla kogo (grupa, odbiorca)", t: "text" },
      POLE_UWAGI
    ];
  }

  function polePodpis(typ, p) {
    var id = "f5-" + bezOgonkow(typ).replace(/[^a-z0-9]+/g, "-") + "-" + p.k;
    var wart = (stan.zajecia[typ] && stan.zajecia[typ][p.k]) || "";
    var html = '<div class="f2-pole-grupa"><label class="f2-etykieta" for="' + id + '">' +
               p.e + (p.wym ? ' <span class="f2-wym">*</span>' : "") + "</label>";
    if (p.t === "slownik") {
      html += '<select id="' + id + '" class="f2-pole" data-typ="' + typ + '" data-pole="' + p.k + '">';
      html += '<option value="">—</option>';
      (SL[p.s] || []).forEach(function (w) {
        html += '<option value="' + w + '"' + (w === wart ? " selected" : "") + ">" + w + "</option>";
      });
      html += "</select>";
    } else if (p.t === "txt") {
      html += '<textarea id="' + id + '" class="f2-pole f2-pole-txt" rows="2" ' +
              'data-typ="' + typ + '" data-pole="' + p.k + '">' + wart + "</textarea>";
    } else {
      var typInput = p.t === "date" ? "date" : p.t === "time" ? "time"
                   : p.t === "int" ? "number" : "text";
      html += '<input type="' + typInput + '" id="' + id + '" class="f2-pole" ' +
              'value="' + wart + '" data-typ="' + typ + '" data-pole="' + p.k + '">';
    }
    return html + "</div>";
  }

  function sekcjaCyklu(typ) {
    var z = stan.zajecia[typ] || {};
    var tryb = z.__tryb || domyslnyTryb();
    var html = '<div class="f5-tryb" data-typ="' + typ + '">' +
      '<button type="button" class="f5-chip' + (tryb === "regula" ? " f5-chip-on" : "") +
        '" data-tryb="regula" data-typ="' + typ + '">Reguła „co wtorek”</button>' +
      '<button type="button" class="f5-chip' + (tryb === "daty" ? " f5-chip-on" : "") +
        '" data-tryb="daty" data-typ="' + typ + '">Konkretne daty (pakiet)</button>' +
      "</div>";

    if (tryb === "regula") {
      html += '<div class="f2-siatka f2-siatka-3">' +
        polePodpis(typ, { k: "cykl_dzien", e: "Dzień tygodnia", t: "slownik", s: "dzien_tyg" }) +
        polePodpis(typ, { k: "co_ile_tygodni", e: "Co ile tygodni", t: "int" }) +
        polePodpis(typ, { k: "data", e: "Pierwsze zajęcia", t: "date" }) +
        "</div>";
    } else {
      html += '<div class="f2-siatka f2-siatka-3">' +
        polePodpis(typ, { k: "data", e: "Pierwsze zajęcia", t: "date" }) +
        polePodpis(typ, { k: "__ile", e: "Ile spotkań", t: "int" }) +
        polePodpis(typ, { k: "__co", e: "Co ile tygodni", t: "int" }) +
        "</div>" +
        '<button type="button" class="f2-link f5-generuj" data-typ="' + typ + '">' +
        "Podpowiedz daty →</button>" +
        '<div class="f5-terminy" data-terminy="' + typ + '">' + terminyHtml(typ) + "</div>";
    }
    return html;
  }

  function terminyHtml(typ) {
    var lista = (stan.zajecia[typ] && stan.zajecia[typ].terminy) || [];
    if (!lista.length) {
      return '<p class="f2-info">Wpisz datę pierwszych zajęć i ile ich będzie, ' +
             "potem popraw pojedyncze daty, jeśli któraś nie pasuje.</p>";
    }
    return lista.map(function (t, i) {
      return '<label class="f5-termin"><span>' + (i + 1) + ".</span>" +
             '<input type="date" class="f2-pole" value="' + (t.data || "") +
             '" data-termin="' + i + '" data-typ="' + typ + '"></label>';
    }).join("");
  }

  /* Przedszkole umawia PAKIET dat (ferie, bal, wyjazd grupy), szkoła — regułę
     „co wtorek do czerwca". Domyślny tryb wynika z typu placówki, ale drugiego
     nie zabiera: przedszkole z prawdziwym „co wtorek" nie klika trzydziestu dat. */
  function domyslnyTryb() {
    var t = (stan.placowka && stan.placowka.typ) || "";
    return /^0[23]\./.test(t) ? "daty" : "regula";
  }

  /* Przedszkole zapisuje się innym typem eventu niż szkoła — ale to decyzja
     BAZY, nie handlowca: on zaznacza jeden chip „Cykliczne". */
  function typCyklu() {
    var t = (stan.placowka && stan.placowka.typ) || "";
    var przedszkolny = /^0[23]\./.test(t);
    if (!przedszkolny) return "CYKLICZNE";
    return (SL.typ_eventu || []).indexOf("CYKLICZNE-PRZEDSZKOLE") >= 0
      ? "CYKLICZNE-PRZEDSZKOLE" : "CYKLICZNE";
  }

  // ------------------------------------------------------------- rysowanie

  function rysujOsie() {
    var box = $("f5-osie");
    box.innerHTML = stan.osie.map(function (o, i) {
      var id = "f5-os-" + o.poziom;
      // Oś bez wartości jest ZABLOKOWANA i mówi dlaczego. Pusta lista, którą
      // da się rozwinąć, wygląda jak brak danych; zablokowana z podpisem
      // „Najpierw powiat" mówi, co zrobić.
      var pusto = !o.wartosci.length;
      var opcje = ['<option value="">' + (o.pusta_etykieta || "Wybierz…") + "</option>"]
        .concat(o.wartosci.map(function (w) {
          return '<option value="' + w + '"' +
                 (stan.wybor[o.poziom] === w ? " selected" : "") + ">" + w + "</option>";
        })).join("");
      return '<div class="f2-pole-grupa"><label class="f2-etykieta" for="' + id + '">' +
             o.etykieta + (i === 0 ? ' <span class="f2-wym">*</span>' : "") + "</label>" +
             '<select id="' + id + '" class="f2-pole" data-os="' + o.poziom + '"' +
             (pusto ? " disabled" : "") + ">" + opcje + "</select></div>";
    }).join("");
  }

  function rysujListe() {
    var box = $("f5-lista");
    var szukaj = bezOgonkow(($("f5-szukaj").value || "").trim());
    var poz = stan.placowki.filter(function (p) {
      if (!szukaj) return true;
      return bezOgonkow(p.nazwa).indexOf(szukaj) >= 0 ||
             bezOgonkow(p.adres || "").indexOf(szukaj) >= 0;
    });

    $("f5-szukaj").hidden = stan.placowki.length < 8;

    if (!stan.placowki.length) {
      box.innerHTML = '<p class="f2-info">' +
        (Object.keys(stan.wybor).some(function (k) { return stan.wybor[k]; })
          ? "Nie ma tu placówek w wybranym rodzaju. Zdejmij filtr albo zmień " +
            "miejscowość — baza obejmuje cały rejestr z terenu firmy."
          : "Wybierz powiat, żeby zobaczyć placówki.") + "</p>";
      return;
    }
    if (!poz.length) {
      box.innerHTML = '<p class="f2-info">Nic nie pasuje do „' +
                      $("f5-szukaj").value + "”.</p>";
      return;
    }

    box.innerHTML = poz.map(function (p) {
      var wybrana = stan.placowka && stan.placowka.placowka_id === p.placowka_id;
      // Gwiazdka = „twoja szkoła" (P06). Cudza własność jest podpisana wprost,
      // bo za termin odpowiada ten, do kogo szkoła jest przypisana.
      var czyj = p.moja ? '<span class="f5-moja" title="twoja szkoła">★</span>'
               : (p.handlowiec ? '<span class="f5-czyja">' + p.handlowiec + "</span>" : "");
      return '<label class="f5-poz' + (wybrana ? " f5-poz-on" : "") + '">' +
             '<input type="radio" name="f5-placowka" value="' + p.placowka_id + '"' +
             (wybrana ? " checked" : "") + ">" +
             '<span class="f5-poz-nazwa">' + p.nazwa + "</span>" + czyj +
             (p.adres ? '<span class="f5-poz-adres">' + p.adres + "</span>" : "") +
             "</label>";
    }).join("");
  }

  function rysujSekcje() {
    var box = $("f5-sekcje");
    var wlaczone = Object.keys(stan.wlaczone).filter(function (t) { return stan.wlaczone[t]; });
    box.innerHTML = wlaczone.map(function (typ) {
      var wewnatrz = czyCykl(typ)
        ? sekcjaCyklu(typ)
        : '<div class="f2-siatka f2-siatka-3">' +
          polaRodzaju(typ).map(function (p) { return polePodpis(typ, p); }).join("") +
          "</div>";
      return '<div class="f5-sekcja" data-sekcja="' + typ + '">' +
             '<h3 class="f5-sekcja-tytul">' + etykietaChipa(typ) + "</h3>" +
             wewnatrz + "</div>";
    }).join("");
  }

  function etykietaChipa(typ) {
    return typ === "CYKLICZNE" || typ === "CYKLICZNE-PRZEDSZKOLE" ? "Zajęcia cykliczne" : typ;
  }

  function pokazKroki() {
    var jest = !!stan.placowka;
    $("f5-sek-kontakt").hidden = !jest;
    $("f5-sek-zajecia").hidden = !jest;
    $("f5-sek-wynik").hidden = !jest;
  }

  // --------------------------------------------------------------- dane

  function wczytajPlacowki() {
    // Wysyłamy WSZYSTKIE wybrane osie — przy jednej wybranej (sam powiat) lista
    // pokazuje cały powiat, co jest normalną drogą: Kasia prosiła o miejscowość
    // jako filtr POMOCNICZY, nie jako obowiązkowy krok.
    var czesci = [];
    stan.osie.forEach(function (o) {
      if (stan.wybor[o.poziom]) {
        czesci.push(o.poziom + "=" + encodeURIComponent(stan.wybor[o.poziom]));
      }
    });
    if (!czesci.length) { stan.placowki = []; rysujListe(); return; }
    var q = "?" + czesci.join("&") +
            "&rodzaj=" + encodeURIComponent(stan.rodzaj) +
            (HANDLOWIEC ? "&handlowiec=" + encodeURIComponent(HANDLOWIEC) : "");
    fetch("/api/formularz/placowki" + q)
      .then(function (r) { return r.json(); })
      .then(function (j) { stan.placowki = j.pozycje || []; rysujListe(); })
      .catch(function () { toast("Nie udało się pobrać listy placówek", true); });
  }

  function podstawKontakt(p) {
    /*
      KONTAKT NALEŻY DO PLACÓWKI, WIĘC PRZY ZMIANIE PLACÓWKI PODMIENIA SIĘ
      W CAŁOŚCI — także na pustą wartość.

      To jest ta sama reguła, którą warianty 2–4 mają od czerwca, i ten sam
      błąd, który v5 popełnił od nowa. Zgłoszenie wraca po raz trzeci: raz od
      Kasi („wprowadziłam dane typu osoba do kontaktu, a potem zmieniłam szkołę,
      to osoba się nie zmieniła"), dwa razy od Pawła w tej rundzie.

      Wersja z 24.08 próbowała rozróżniać, czy pole podstawiła aplikacja, czy
      wpisał je człowiek — i chroniła to drugie. Nie działa, bo sekcja kontaktu
      jest ZAKRYTA do czasu wybrania placówki: cokolwiek w niej wpisano,
      dotyczyło POPRZEDNIEJ szkoły. „Ochrona" oznaczała więc przeniesienie
      dyrektorki jednego przedszkola do karty drugiego.

      Skutek pustej rubryki jest odwracalny (widać brak), skutek cudzego maila
      przy dobrej szkole — nie: nikt tego nie zauważy. Dlatego nadpisujemy
      zawsze i mówimy o tym wprost (ostrzegamy, nie blokujemy).
    */
    var zrodla = { "f5-osoba": p.osoba_kontakt || "", "f5-telefon": p.telefon || "",
                   "f5-mail": p.mail || "" };
    var wziete = 0, podmiana = false;
    Object.keys(zrodla).forEach(function (id) {
      var el = $(id);
      if (!el) return;
      // Komunikat należy się tylko wtedy, gdy coś WYPARŁO poprzednią wartość.
      // Pierwsze wypełnienie pustego formularza nie jest podmianą.
      if (el.value && el.value !== zrodla[id]) podmiana = true;
      el.value = zrodla[id];
      if (zrodla[id]) wziete++;
    });
    var info = $("f5-kontakt-info");
    if (podmiana) {
      info.textContent = "Kontakt podmieniony na dane z karty tej placówki — " +
                         "poprzedni dotyczył innej szkoły. Sprawdź go.";
    } else {
      info.textContent = wziete
        ? "Kontakt z karty placówki — popraw, jeśli się zmienił."
        : "";
    }
  }

  // -------------------------------------------------------------- zdarzenia

  root.addEventListener("change", function (ev) {
    var el = ev.target;

    if (el.dataset.os) {
      stan.wybor[el.dataset.os] = el.value;
      stan.placowka = null;
      pokazKroki();
      // Zmiana osi WYŻSZEJ zawęża niższą — i czyści jej wybór, bo „Czeladź"
      // wybrana przy będzińskim nie ma sensu po przełączeniu na Katowice.
      if (el.dataset.os === stan.osie[0].poziom) {
        stan.osie.slice(1).forEach(function (o) { delete stan.wybor[o.poziom]; });
        wczytajOsie(el.value);
      } else {
        wczytajPlacowki();
      }
      zapiszSzkic();
      return;
    }

    if (el.name === "f5-placowka") {
      var id = parseInt(el.value, 10);
      stan.placowka = stan.placowki.filter(function (p) {
        return p.placowka_id === id;
      })[0] || null;
      if (stan.placowka) podstawKontakt(stan.placowka);
      pokazKroki();
      rysujListe();
      rysujSekcje();
      zapiszSzkic();
      return;
    }

    if (el.dataset.typ && el.dataset.pole) {
      stan.zajecia[el.dataset.typ] = stan.zajecia[el.dataset.typ] || {};
      stan.zajecia[el.dataset.typ][el.dataset.pole] = el.value;
      zapiszSzkic();
      return;
    }

    if (el.dataset.termin !== undefined) {
      var z = stan.zajecia[el.dataset.typ] || {};
      if (z.terminy && z.terminy[el.dataset.termin]) {
        z.terminy[el.dataset.termin].data = el.value;
        zapiszSzkic();
      }
      return;
    }

    zapiszSzkic();
  });

  root.addEventListener("input", function (ev) {
    if (ev.target.id === "f5-szukaj") rysujListe();
  });

  root.addEventListener("click", function (ev) {
    var el = ev.target.closest("button");
    if (!el) return;

    if (el.dataset.rodzaj !== undefined) {
      stan.rodzaj = el.dataset.rodzaj;
      root.querySelectorAll("[data-rodzaj]").forEach(function (b) {
        b.classList.toggle("f5-chip-on", b === el);
      });
      wczytajPlacowki();
      return;
    }

    if (el.classList.contains("f5-chip-rodzaj")) {
      var typ = el.dataset.typ;
      // Chip „Cykliczne" zapisuje się typem zależnym od placówki — handlowiec
      // widzi jeden przycisk, baza dostaje właściwy typ.
      if (typ === "CYKLICZNE") typ = typCyklu();
      stan.wlaczone[typ] = !stan.wlaczone[typ];
      el.classList.toggle("f5-chip-on", stan.wlaczone[typ]);
      rysujSekcje();
      zapiszSzkic();
      return;
    }

    if (el.dataset.tryb) {
      stan.zajecia[el.dataset.typ] = stan.zajecia[el.dataset.typ] || {};
      stan.zajecia[el.dataset.typ].__tryb = el.dataset.tryb;
      rysujSekcje();
      return;
    }

    if (el.classList.contains("f5-generuj")) {
      generujTerminy(el.dataset.typ);
      return;
    }

    if (el.id === "f5-wyczysc") {
      if (!confirm("Wyczyścić formularz? Wpisane dane przepadną.")) return;
      localStorage.removeItem(KLUCZ_SZKICU);
      location.reload();
    }
  });

  /* Propozycja dat pakietu. Świadomie tylko PROPOZYCJA — każdą datę da się
     poprawić, bo w przedszkolu zawsze wypadnie bal albo wyjazd. */
  function generujTerminy(typ) {
    var z = stan.zajecia[typ] || (stan.zajecia[typ] = {});
    var start = z.data;
    var ile = parseInt(z.__ile, 10) || 0;
    var co = parseInt(z.__co, 10) || 1;
    if (!start || ile < 1) {
      toast("Podaj datę pierwszych zajęć i ile ich będzie", true);
      return;
    }
    if (ile > 60) { toast("Najwyżej 60 spotkań w jednym pakiecie", true); return; }
    var d = new Date(start + "T00:00:00");
    z.terminy = [];
    for (var i = 0; i < ile; i++) {
      var kolejna = new Date(d.getTime());
      kolejna.setDate(d.getDate() + i * 7 * co);
      z.terminy.push({ data: kolejna.toISOString().slice(0, 10) });
    }
    rysujSekcje();
    zapiszSzkic();
  }

  // ------------------------------------------------------------------ szkic

  function zapiszSzkic() {
    try {
      localStorage.setItem(KLUCZ_SZKICU, JSON.stringify({
        handlowiec: HANDLOWIEC, wybor: stan.wybor, rodzaj: stan.rodzaj,
        placowka: stan.placowka, zajecia: stan.zajecia, wlaczone: stan.wlaczone,
        kontakt: {
          osoba_kontakt: $("f5-osoba").value, telefon: $("f5-telefon").value,
          mail: $("f5-mail").value
        },
        status: $("f5-status").value, notatka: $("f5-notatka").value
      }));
    } catch (e) { /* pamięć pełna albo tryb prywatny — szkic to wygoda, nie warunek */ }
  }

  function czyCosJest() {
    return !!(stan.placowka || $("f5-notatka").value ||
              Object.keys(stan.zajecia).length);
  }

  // ------------------------------------------------------------------ zapis

  function zbierzZajecia() {
    var out = [], braki = [], odlozone = [];
    Object.keys(stan.zajecia).forEach(function (typ) {
      var z = stan.zajecia[typ];
      var cos = Object.keys(z).some(function (k) {
        return k.indexOf("__") !== 0 && z[k] && String(z[k]).length;
      });
      if (!stan.wlaczone[typ]) {
        if (cos) odlozone.push(etykietaChipa(typ));
        return;
      }
      var blok = { typ: typ };
      Object.keys(z).forEach(function (k) {
        if (k.indexOf("__") === 0) return;
        if (k === "terminy") { blok.terminy = z.terminy; return; }
        if (z[k] !== "" && z[k] !== null && z[k] !== undefined) blok[k] = z[k];
      });
      if (czyCykl(typ)) {
        var maDate = (blok.terminy && blok.terminy.length) || blok.cykl_dzien;
        if (!maDate) { braki.push(etykietaChipa(typ) + " — brak dnia tygodnia i dat"); return; }
      } else if (!blok.data) {
        braki.push(etykietaChipa(typ) + " — brak daty");
        return;
      }
      out.push(blok);
    });
    return { zajecia: out, braki: braki, odlozone: odlozone };
  }

  var awaria = window.FxAwaria ? window.FxAwaria.utworz({
    klucz: KLUCZ_AWARII, kontener: root, handlowiec: HANDLOWIEC, toast: toast,
    naSukces: function () { localStorage.removeItem(KLUCZ_SZKICU); location.reload(); }
  }) : null;

  $("f5-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var blad = $("f5-blad");
    blad.hidden = true;

    if (!stan.placowka) {
      blad.textContent = "Najpierw wybierz placówkę (krok 1).";
      blad.hidden = false;
      return;
    }

    var z = zbierzZajecia();
    if (z.braki.length) {
      blad.textContent = "Uzupełnij: " + z.braki.join(" · ");
      blad.hidden = false;
      return;
    }

    var payload = {
      klucz_zapisu: window.FxAwaria ? window.FxAwaria.losowyKlucz() : "",
      handlowiec: HANDLOWIEC,
      kontakt: {
        osoba_kontakt: $("f5-osoba").value.trim(),
        telefon: $("f5-telefon").value.trim(),
        mail: $("f5-mail").value.trim()
      },
      zajecia: z.zajecia
    };
    if (stan.placowka.lead_id) {
      payload.lead_id = stan.placowka.lead_id;
    } else {
      // Placówka bez leada — lista v5 czyta placówki LEFT JOIN-em, więc taka
      // może się na niej pojawić. Wysyłamy jej `placowka_id`, a serwer zakłada
      // lead do ISTNIEJĄCEGO rekordu.
      //
      // Do 24.08 szedł tu blok `placowka` z nazwą przepisaną z rekordu, w
      // przekonaniu, że serwer rozpozna placówkę po nazwie. Nie rozpoznawał —
      // wstawiał drugi wiersz. Dubel z tego samego rekordu, o którym Kasia
      // pisała, że robią go ludzie.
      payload.placowka_id = stan.placowka.placowka_id;
    }
    if ($("f5-status").value) payload.status_realizacji = $("f5-status").value;
    if ($("f5-notatka").value.trim()) {
      // Podpis z sesji dokleja serwer? Nie — na razie robi to formularz,
      // bo `uwagi` to zwykłe pole leada. Nazwisko bierzemy z `data-handlowiec`,
      // czyli z tego, co serwer wpisał z SESJI, a nie z pola do wpisania.
      payload.uwagi = "[" + DZIS + (HANDLOWIEC ? " · " + HANDLOWIEC : "") + "] " +
                      $("f5-notatka").value.trim();
    }

    var btn = $("f5-zapisz");
    btn.disabled = true;
    btn.textContent = "Zapisuję…";

    api("/api/formularz", payload)
      .then(function (j) {
        localStorage.removeItem(KLUCZ_SZKICU);
        if (awaria) awaria.wyczysc();
        var ile = (j.eventy || []).length;
        var tekst = "Zapisano: " + j.placowka +
                    (ile ? " · " + ile + (ile === 1 ? " wpis" : " wpisy") : " (sama wizyta)");
        if (z.odlozone.length) {
          tekst += " · UWAGA: " + z.odlozone.join(", ") +
                   " — wypełnione, ale odznaczone, więc NIE zapisane";
        }
        toast(tekst);
        setTimeout(function () { location.reload(); }, z.odlozone.length ? 6000 : 1500);
      })
      .catch(function (e) {
        btn.disabled = false;
        btn.textContent = "Zapisz";
        blad.textContent = e.message;
        blad.hidden = false;
        if (awaria) awaria.zapamietaj(payload, e.message);
      });
  });

  if (window.FxAwaria) {
    window.FxAwaria.pilnujWyjscia(czyCosJest);
    window.FxAwaria.pilnujZakonczenia($("f5-zakoncz"), czyCosJest);
  }

  // ------------------------------------------------------------------ start

  function wczytajOsie(powiat, poStarcie) {
    return fetch("/api/formularz/geografia" +
                 (powiat ? "?powiat=" + encodeURIComponent(powiat) : ""))
      .then(function (r) { return r.json(); })
      .then(function (j) {
        stan.osie = j.osie || [];
        rysujOsie();
        if (poStarcie) poStarcie();
        else wczytajPlacowki();
      })
      .catch(function () { toast("Nie udało się pobrać listy powiatów", true); });
  }

  wczytajOsie("", przywrocSzkic);

  function przywrocSzkic() {
    var s;
    try { s = JSON.parse(localStorage.getItem(KLUCZ_SZKICU) || "null"); } catch (e) { s = null; }
    if (!s || s.handlowiec !== HANDLOWIEC || !s.wybor) return;
    var info = $("f5-szkic");
    info.hidden = false;
    info.innerHTML = "Masz niedokończony formularz. " +
      '<button type="button" class="f2-link" id="f5-wroc">Wróć do niego</button>';
    $("f5-wroc").addEventListener("click", function () {
      stan.wybor = s.wybor || {};
      stan.rodzaj = s.rodzaj || "";
      stan.zajecia = s.zajecia || {};
      stan.wlaczone = s.wlaczone || {};
      stan.placowka = s.placowka || null;
      $("f5-osoba").value = (s.kontakt || {}).osoba_kontakt || "";
      $("f5-telefon").value = (s.kontakt || {}).telefon || "";
      $("f5-mail").value = (s.kontakt || {}).mail || "";
      $("f5-status").value = s.status || "";
      $("f5-notatka").value = s.notatka || "";
      rysujOsie();
      root.querySelectorAll(".f5-chip-rodzaj").forEach(function (b) {
        var t = b.dataset.typ === "CYKLICZNE" ? typCyklu() : b.dataset.typ;
        b.classList.toggle("f5-chip-on", !!stan.wlaczone[t]);
      });
      pokazKroki();
      rysujSekcje();
      wczytajPlacowki();
      info.hidden = true;
    });
  }
})();
