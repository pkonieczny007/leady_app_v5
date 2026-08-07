/* =============================================================================
   Formularz ustaleń z placówką — logika ekranu terenowego.

   Trzy rzeczy, które ten plik ma zapewnić, i które wynikają wprost ze zgłoszenia
   „handlowiec czegoś nie wpisał":

   1. NIE DA SIĘ PRZEJŚĆ DALEJ z pustym polem wymaganym — komunikat siada przy
      konkretnym polu, nie jako ogólne „wypełnij formularz".
   2. SZKIC ŻYJE W TELEFONIE — każda zmiana pola ląduje w localStorage. Telefon
      do ucha, przełączenie aplikacji, zgaszony ekran, utrata zasięgu: po powrocie
      formularz jest tam, gdzie skończył.
   3. ZAPIS KOŃCZY SIĘ WIDOCZNYM POTWIERDZENIEM z nazwą szkoły i datą. Bez tego
      handlowiec nie wie, czy poszło, i wypełnia drugi raz.

   Bez bibliotek i bez buildu — jak reszta projektu.
   ============================================================================= */
(function () {
  "use strict";

  var root = document.getElementById("fx");
  if (!root) return;

  var KROKOW = 4;
  var KLUCZ_SZKICU = "fx-szkic-v1";
  var KLUCZ_OSOBY = "fx-handlowiec";

  var stan = {
    krok: 1,
    handlowiec: root.dataset.handlowiec || "",
    wybrana: null,        // {lead_id, placowka_id, nazwa, miejscowosc, ...}
    nowa: false,          // czy tworzymy placówkę od zera
    trener: "",
    cyklPominiety: false
  };

  var $ = function (id) { return document.getElementById(id); };
  var moje = window.FX_MOJE || [];

  // Awaria w trakcie wypełniania: szkic, ostrzeżenie przy wyjściu i kolejka
  // „niewysłane" — całość w formularz_awaria.js, bo dotyczy obu wariantów.
  var awaria = null;

  /* ------------------------------------------------------------------ toast */

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
    var o = { method: metoda, headers: {} };
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

  /* =============================================================== WYBÓR OSOBY
     Do czasu logowania PIN-em handlowiec wybiera się z listy. Wybór zostaje
     w telefonie, żeby nie klikać go co rano. */

  var selKto = $("fx-kto");
  if (selKto) {
    var zapamietany = localStorage.getItem(KLUCZ_OSOBY);
    if (zapamietany) {
      selKto.value = zapamietany;
      if (selKto.value) { location.replace("/formularz/kroki?handlowiec=" + encodeURIComponent(zapamietany)); return; }
    }
    selKto.addEventListener("change", function () {
      if (!selKto.value) return;
      localStorage.setItem(KLUCZ_OSOBY, selKto.value);
      location.href = "/formularz/kroki?handlowiec=" + encodeURIComponent(selKto.value);
    });
  } else if (stan.handlowiec) {
    localStorage.setItem(KLUCZ_OSOBY, stan.handlowiec);
  }

  /* =============================================================== KROK 1 — SZKOŁA */

  var poleSzukaj = $("fx-szukaj");
  var boxWyniki = $("fx-wyniki");
  var boxWybrana = $("fx-wybrana");
  var boxNowa = $("fx-nowa");
  var timerSzukania = null;

  function rysujWyniki(pozycje, naglowek) {
    if (!pozycje.length) {
      boxWyniki.innerHTML = '<p class="fx-wyniki-pusto">Nic nie znaleziono. ' +
        'Sprawdź pisownię albo dodaj nową placówkę poniżej.</p>';
      boxWyniki.hidden = false;
      return;
    }
    var html = naglowek ? '<p class="fx-wyniki-naglowek">' + esc(naglowek) + "</p>" : "";
    pozycje.forEach(function (p, i) {
      html += '<button type="button" class="fx-wynik" data-i="' + i + '">' +
        '<span class="fx-wynik-nazwa">' + esc(p.nazwa) + "</span>" +
        '<span class="fx-wynik-meta">' + esc(p.miejscowosc || "") +
        (p.moja ? ' <span class="fx-znak fx-znak-moja">moja</span>' : "") +
        (p.ma_dt ? ' <span class="fx-znak fx-znak-dt">ma DT</span>' : "") +
        "</span></button>";
    });
    boxWyniki.innerHTML = html;
    boxWyniki._pozycje = pozycje;
    boxWyniki.hidden = false;
  }

  function pokazMoje() {
    if (!moje.length) { boxWyniki.hidden = true; return; }
    rysujWyniki(moje.slice(0, 12), "Twoje szkoły");
  }

  poleSzukaj.addEventListener("focus", function () {
    if (!poleSzukaj.value.trim()) pokazMoje();
  });

  poleSzukaj.addEventListener("input", function () {
    var q = poleSzukaj.value.trim();
    clearTimeout(timerSzukania);
    if (q.length < 2) { pokazMoje(); return; }
    // 250 ms zwłoki: przy pisaniu kciukiem inaczej leci żądanie na każdą literę
    timerSzukania = setTimeout(function () {
      api("GET", "/api/placowki/szukaj?q=" + encodeURIComponent(q) +
                 "&handlowiec=" + encodeURIComponent(stan.handlowiec))
        .then(function (j) { rysujWyniki(j.pozycje, null); })
        .catch(function (e) { toast("Nie udało się wyszukać: " + e.message, true); });
    }, 250);
  });

  boxWyniki.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".fx-wynik");
    if (!btn) return;
    wybierz((boxWyniki._pozycje || [])[+btn.dataset.i]);
  });

  function wybierz(p) {
    if (!p) return;
    stan.wybrana = p;
    stan.nowa = false;
    $("fx-wybrana-nazwa").textContent = p.nazwa;
    var meta = [p.miejscowosc, p.typ, p.adres].filter(Boolean).join(" · ");
    if (p.osoba_kontakt) meta += (meta ? " · " : "") + p.osoba_kontakt;
    if (p.telefon) meta += (meta ? " · " : "") + p.telefon;
    $("fx-wybrana-meta").textContent = meta;
    boxWybrana.hidden = false;
    boxWyniki.hidden = true;
    boxNowa.hidden = true;
    poleSzukaj.hidden = true;
    $("fx-nowa-otworz").hidden = true;
    zapiszSzkic();
  }

  $("fx-zmien").addEventListener("click", function () {
    stan.wybrana = null;
    boxWybrana.hidden = true;
    poleSzukaj.hidden = false;
    poleSzukaj.value = "";
    $("fx-nowa-otworz").hidden = false;
    poleSzukaj.focus();
    pokazMoje();
    zapiszSzkic();
  });

  $("fx-nowa-otworz").addEventListener("click", function () {
    stan.nowa = true;
    stan.wybrana = null;
    boxNowa.hidden = false;
    boxWyniki.hidden = true;
    boxWybrana.hidden = true;
    this.hidden = true;
    $("fx-nowa-nazwa").focus();
    zapiszSzkic();
  });

  /* =============================================== KROK 2 — PODPOWIEDŹ TRENERA */

  var boxTrenerzy = $("fx-trenerzy");
  var selInnyTrener = $("fx-dt-trener");
  var timerKandydatow = null;

  var OPIS_KATEGORII = {
    wolny: "wolny",
    nieznany: "brak deklaracji",
    zastrzezenie: "uwaga",
    niedostepny: "niedostępny"
  };

  function odswiezKandydatow() {
    var data = $("fx-dt-data").value;
    if (!data) {
      boxTrenerzy.innerHTML = '<p class="fx-podpowiedz fx-trenerzy-pusto">' +
        "Wybierz najpierw datę — podpowiemy, kto jest wolny.</p>";
      selInnyTrener.hidden = true;
      return;
    }
    var miasto = stan.wybrana ? (stan.wybrana.miejscowosc || "")
                              : ($("fx-nowa-miasto").value || "");
    var url = "/api/kandydaci?data=" + encodeURIComponent(data) +
      "&godz_od=" + encodeURIComponent($("fx-dt-od").value || "") +
      "&godz_do=" + encodeURIComponent($("fx-dt-do").value || "") +
      "&miasto=" + encodeURIComponent(miasto);

    boxTrenerzy.innerHTML = '<p class="fx-podpowiedz">Sprawdzam dostępność…</p>';
    clearTimeout(timerKandydatow);
    timerKandydatow = setTimeout(function () {
      api("GET", url).then(function (j) { rysujKandydatow(j, miasto); })
        .catch(function (e) {
          boxTrenerzy.innerHTML = '<p class="fx-podpowiedz">Nie udało się sprawdzić ' +
            "dostępności (" + esc(e.message) + "). Wybierz prowadzącego z listy.</p>";
          selInnyTrener.hidden = false;
        });
    }, 200);
  }

  function rysujKandydatow(j, miasto) {
    // Spłaszczamy grupy: na telefonie cztery nagłówki kategorii to same przewijanie.
    // Kolejność z serwera jest już poprawna (wolni → bez deklaracji → uwagi → niedostępni),
    // wystarczy pokazać pierwszych kilku i schować resztę pod przyciskiem.
    var lista = [];
    (j.grupy || []).forEach(function (g) {
      g.pozycje.forEach(function (k) { lista.push(k); });
    });
    if (!lista.length) {
      boxTrenerzy.innerHTML = '<p class="fx-podpowiedz">Brak trenerów w słowniku.</p>';
      selInnyTrener.hidden = false;
      return;
    }
    var wolnych = lista.filter(function (k) { return k.kategoria === "wolny"; }).length;
    var html = '<p class="fx-trenerzy-info">' +
      (wolnych ? "<b>" + wolnych + "</b> " + odmiana(wolnych, "wolny", "wolnych", "wolnych")
               : "Nikt nie zadeklarował dostępności") +
      (miasto ? " · rejon <b>" + esc(miasto) + "</b>" : "") + "</p>";

    lista.forEach(function (k, i) {
      var ukryty = i >= 5 ? " fx-trener-ukryty" : "";
      html += '<button type="button" class="fx-trener fx-trener-' + k.kategoria + ukryty +
        '" data-trener="' + esc(k.trener) + '">' +
        '<span class="fx-trener-kropka" style="background:' + esc(k.kolor) + '"></span>' +
        '<span class="fx-trener-txt">' +
          '<span class="fx-trener-nazwa">' + esc(k.trener) + "</span>" +
          '<span class="fx-trener-powod">' + esc(OPIS_KATEGORII[k.kategoria] || "") +
            " · " + esc(k.powod) +
            (k.rejon ? ' · <b class="fx-trener-rejon">jeździ tu</b>' : "") +
          "</span>" +
        "</span></button>";
    });
    if (lista.length > 5) {
      html += '<button type="button" class="fx-btn fx-btn-lekki" id="fx-trener-wiecej">' +
        "Pokaż pozostałych (" + (lista.length - 5) + ")</button>";
    }
    boxTrenerzy.innerHTML = html;
    selInnyTrener.hidden = true;

    if (stan.trener) {
      var wybrany = boxTrenerzy.querySelector('[data-trener="' + cssEsc(stan.trener) + '"]');
      if (wybrany) { wybrany.classList.add("on"); wybrany.classList.remove("fx-trener-ukryty"); }
    }
  }

  function cssEsc(s) { return String(s).replace(/["\\]/g, "\\$&"); }

  function odmiana(n, jeden, kilka, wiele) {
    if (n === 1) return jeden;
    var r10 = n % 10, r100 = n % 100;
    if (r10 >= 2 && r10 <= 4 && (r100 < 10 || r100 >= 20)) return kilka;
    return wiele;
  }

  boxTrenerzy.addEventListener("click", function (ev) {
    if (ev.target.id === "fx-trener-wiecej") {
      boxTrenerzy.querySelectorAll(".fx-trener-ukryty").forEach(function (el) {
        el.classList.remove("fx-trener-ukryty");
      });
      ev.target.remove();
      return;
    }
    var btn = ev.target.closest(".fx-trener");
    if (!btn) return;
    boxTrenerzy.querySelectorAll(".fx-trener").forEach(function (el) {
      el.classList.remove("on");
    });
    btn.classList.add("on");
    stan.trener = btn.dataset.trener;
    selInnyTrener.value = "";
    zapiszSzkic();
  });

  selInnyTrener.addEventListener("change", function () {
    stan.trener = selInnyTrener.value;
    zapiszSzkic();
  });

  ["fx-dt-data", "fx-dt-od", "fx-dt-do"].forEach(function (id) {
    $(id).addEventListener("change", odswiezKandydatow);
  });

  /* ========================================================= KROK 3 — CYKLE */

  $("fx-cykl-pomin").addEventListener("click", function () {
    stan.cyklPominiety = !stan.cyklPominiety;
    $("fx-cykl").hidden = stan.cyklPominiety;
    this.textContent = stan.cyklPominiety
      ? "Jednak ustalamy zajęcia cykliczne"
      : "Bez zajęć cyklicznych — pomiń";
    this.classList.toggle("on", stan.cyklPominiety);
    zapiszSzkic();
  });

  /* ============================================================ NAWIGACJA */

  function pokazKrok(nr) {
    stan.krok = Math.max(1, Math.min(KROKOW, nr));
    root.querySelectorAll(".fx-ekran").forEach(function (s) {
      s.hidden = +s.dataset.krok !== stan.krok;
    });
    root.querySelectorAll(".fx-krok").forEach(function (b) {
      var n = +b.dataset.nr;
      b.classList.toggle("on", n === stan.krok);
      b.classList.toggle("zrobiony", n < stan.krok);
    });
    $("fx-wstecz").hidden = stan.krok === 1;
    $("fx-dalej").hidden = stan.krok === KROKOW;
    $("fx-zapisz").hidden = stan.krok !== KROKOW;
    if (stan.krok === KROKOW) rysujPodsumowanie();
    if (stan.krok === 2) odswiezKandydatow();
    window.scrollTo(0, 0);
    zapiszSzkic();
  }

  root.querySelectorAll(".fx-krok").forEach(function (b) {
    b.addEventListener("click", function () {
      var cel = +b.dataset.idz;
      // Wstecz zawsze wolno; do przodu tylko przez walidację, po kolei.
      if (cel <= stan.krok) { pokazKrok(cel); return; }
      for (var k = stan.krok; k < cel; k++) {
        if (!sprawdzKrok(k)) return;
      }
      pokazKrok(cel);
    });
  });

  $("fx-dalej").addEventListener("click", function () {
    if (sprawdzKrok(stan.krok)) pokazKrok(stan.krok + 1);
  });
  $("fx-wstecz").addEventListener("click", function () { pokazKrok(stan.krok - 1); });

  /* =========================================================== WALIDACJA
     Komunikat siada PRZY POLU i ekran przewija się do pierwszego błędu —
     ogólne „wypełnij formularz" na telefonie nie mówi nic, bo pola nie widać. */

  function bladPola(el, tekst) {
    czyscBlad(el);
    el.classList.add("zly");
    var p = document.createElement("p");
    p.className = "fx-blad";
    p.textContent = tekst;
    el.parentNode.insertBefore(p, el.nextSibling);
  }

  function czyscBlad(el) {
    el.classList.remove("zly");
    var n = el.nextSibling;
    if (n && n.className === "fx-blad") n.remove();
  }

  function czyscBledy() {
    root.querySelectorAll(".fx-blad").forEach(function (e) { e.remove(); });
    root.querySelectorAll(".zly").forEach(function (e) { e.classList.remove("zly"); });
  }

  function wymagane(pary) {
    var pierwszy = null;
    pary.forEach(function (para) {
      var el = $(para[0]);
      if (el && !String(el.value || "").trim()) {
        bladPola(el, para[1]);
        if (!pierwszy) pierwszy = el;
      }
    });
    if (pierwszy) {
      pierwszy.scrollIntoView({ behavior: "smooth", block: "center" });
      pierwszy.focus({ preventScroll: true });
    }
    return !pierwszy;
  }

  function sprawdzKrok(nr) {
    czyscBledy();
    if (nr === 1) {
      if (stan.wybrana) return true;
      if (!stan.nowa) {
        bladPola(poleSzukaj, "Wybierz szkołę z listy albo dodaj nową.");
        poleSzukaj.scrollIntoView({ behavior: "smooth", block: "center" });
        return false;
      }
      return wymagane([["fx-nowa-nazwa", "Podaj nazwę placówki."],
                       ["fx-nowa-miasto", "Wybierz miejscowość."]]);
    }
    if (nr === 2) {
      if (!wymagane([["fx-dt-data", "Podaj datę DT."],
                     ["fx-dt-od", "Podaj godzinę rozpoczęcia."],
                     ["fx-dt-klas", "Podaj liczbę klas 1–4."],
                     ["fx-dt-dzieci", "Podaj liczbę dzieci."],
                     ["fx-mail-rodzice", "Zaznacz, czy szkoła wyśle wiadomość do rodziców."]])) {
        return false;
      }
      if (!stan.trener) {
        boxTrenerzy.scrollIntoView({ behavior: "smooth", block: "center" });
        toast("Wybierz prowadzącego DT", true);
        return false;
      }
      // Data w przeszłości to OSTRZEŻENIE, nie blokada — czasem wpisuje się
      // ustalenia po fakcie i blokada zmusiłaby do kombinowania.
      if ($("fx-dt-data").value < root.dataset.dzis) {
        toast("Uwaga: data DT jest w przeszłości — zapisuję tak, jak wpisałeś.");
      }
      return true;
    }
    if (nr === 3) {
      if (stan.cyklPominiety) return true;
      // Cykl jest opcjonalny w całości; częściowo wypełniony bez dnia tygodnia
      // nie da się zapisać sensownie, więc pytamy wprost.
      var cos = ["fx-cykl-od", "fx-cykl-sala", "fx-cykl-sprzet", "fx-cykl-uwagi"]
        .some(function (id) { return String($(id).value || "").trim(); });
      if (cos && !$("fx-cykl-dzien").value) {
        bladPola($("fx-cykl-dzien"), "Wybierz dzień tygodnia albo pomiń cykle.");
        $("fx-cykl-dzien").scrollIntoView({ behavior: "smooth", block: "center" });
        return false;
      }
      return true;
    }
    return true;
  }

  /* ========================================================= PODSUMOWANIE */

  function wiersz(etykieta, wartosc) {
    if (!wartosc) return "";
    return '<div class="fx-podsum-w"><dt>' + esc(etykieta) + "</dt><dd>" +
      esc(wartosc) + "</dd></div>";
  }

  function rysujPodsumowanie() {
    var szkola = stan.wybrana
      ? stan.wybrana.nazwa + (stan.wybrana.miejscowosc ? ", " + stan.wybrana.miejscowosc : "")
      : ($("fx-nowa-nazwa").value + (($("fx-nowa-miasto").value)
          ? ", " + $("fx-nowa-miasto").value : "") + "  (nowa placówka)");

    var godziny = $("fx-dt-od").value + ($("fx-dt-do").value ? "–" + $("fx-dt-do").value : "");
    var html = '<h3 class="fx-podsum-tytul">Placówka</h3><dl class="fx-podsum-lista">' +
      wiersz("Szkoła", szkola) +
      wiersz("Osoba kontaktowa", $("fx-osoba").value) +
      wiersz("Telefon", $("fx-telefon").value) +
      wiersz("Mail", $("fx-mail").value) +
      "</dl>";

    html += '<h3 class="fx-podsum-tytul">Dzień Technologii</h3><dl class="fx-podsum-lista">' +
      wiersz("Data", $("fx-dt-data").value) +
      wiersz("Godziny", godziny) +
      wiersz("Prowadzący", stan.trener) +
      wiersz("Sala", $("fx-dt-sala").value) +
      wiersz("Klasy 1–4", $("fx-dt-klas").value) +
      wiersz("Dzieci", $("fx-dt-dzieci").value) +
      wiersz("Wiadomość do rodziców", $("fx-mail-rodzice").value) +
      wiersz("Ustalenia", $("fx-dt-uwagi").value) +
      "</dl>";

    if (!stan.cyklPominiety && $("fx-cykl-dzien").value) {
      var gc = $("fx-cykl-od").value + ($("fx-cykl-do").value ? "–" + $("fx-cykl-do").value : "");
      html += '<h3 class="fx-podsum-tytul">Zajęcia cykliczne</h3><dl class="fx-podsum-lista">' +
        wiersz("Dzień", $("fx-cykl-dzien").value) +
        wiersz("Godziny", gc) +
        wiersz("Sala", $("fx-cykl-sala").value) +
        wiersz("Sprzęt", $("fx-cykl-sprzet").value) +
        wiersz("Uwagi", $("fx-cykl-uwagi").value) +
        "</dl>";
    } else {
      html += '<p class="fx-podsum-brak">Zajęcia cykliczne: nie ustalono.</p>';
    }
    $("fx-podsumowanie").innerHTML = html;
  }

  /* =============================================================== ZAPIS */

  function zbierz() {
    var d = { handlowiec: stan.handlowiec };
    if (stan.wybrana) {
      d.lead_id = stan.wybrana.lead_id;
    } else {
      d.placowka = {
        nazwa: $("fx-nowa-nazwa").value.trim(),
        miejscowosc: $("fx-nowa-miasto").value,
        typ: $("fx-nowa-typ").value,
        adres: $("fx-nowa-adres").value.trim()
      };
    }
    d.kontakt = {
      osoba_kontakt: $("fx-osoba").value.trim(),
      telefon: $("fx-telefon").value.trim(),
      mail: $("fx-mail").value.trim()
    };
    d.mail_rodzice = $("fx-mail-rodzice").value;
    d.dt = {
      data: $("fx-dt-data").value,
      godz_od: $("fx-dt-od").value,
      godz_do: $("fx-dt-do").value,
      trener: stan.trener,
      numer_sali: $("fx-dt-sala").value.trim(),
      ilosc_klas: $("fx-dt-klas").value,
      ilosc_dzieci: $("fx-dt-dzieci").value,
      uwagi: $("fx-dt-uwagi").value.trim()
    };
    if (!stan.cyklPominiety && $("fx-cykl-dzien").value) {
      d.cykl = {
        cykl_dzien: $("fx-cykl-dzien").value,
        godz_od: $("fx-cykl-od").value,
        godz_do: $("fx-cykl-do").value,
        numer_sali: $("fx-cykl-sala").value.trim(),
        sprzet: $("fx-cykl-sprzet").value,
        uwagi: $("fx-cykl-uwagi").value.trim()
      };
    }
    return d;
  }

  var btnZapisz = $("fx-zapisz");
  btnZapisz.addEventListener("click", function () {
    for (var k = 1; k <= 3; k++) {
      if (!sprawdzKrok(k)) { pokazKrok(k); return; }
    }
    btnZapisz.disabled = true;
    btnZapisz.textContent = "Zapisuję…";
    var payload = zbierz();
    // Klucz próby: gdy zapis dojdzie, a odpowiedź nie wróci, ponowienie z tym
    // samym kluczem NIE stworzy drugiego leada (serwer zwróci poprzedni wynik).
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
        btnZapisz.textContent = "Zapisz formularz";
        // Treść formularza NIE ginie: ląduje w kolejce „niewysłane" i wraca
        // czerwoną ramką z przyciskiem „Ponów wysyłkę".
        if (awaria) awaria.zapamietaj(payload, e.message);
        toast("Nie zapisano: " + e.message, true);
      });
  });

  function pokazSukces(j) {
    root.querySelectorAll(".fx-ekran, .fx-kroki, .fx-stopka, .fx-karta-wybor, .fx-alarm")
      .forEach(function (el) { el.hidden = true; });
    $("fx-szkic").hidden = true;
    $("fx-sukces-tytul").textContent = "Zapisano: " + j.placowka;
    var dtData = $("fx-dt-data").value;
    $("fx-sukces-tresc").textContent =
      "DT " + dtData + " o " + $("fx-dt-od").value +
      (stan.trener ? ", prowadzi " + stan.trener : "") + ".";
    if (j.kolizja) {
      $("fx-sukces-kolizja").textContent = "Uwaga: " + j.kolizja;
      $("fx-sukces-kolizja").hidden = false;
    }
    $("fx-do-leada").href = "/lead/" + j.lead_id;
    $("fx-sukces").hidden = false;
    window.scrollTo(0, 0);
  }

  $("fx-nowy").addEventListener("click", function () {
    localStorage.removeItem(KLUCZ_SZKICU);
    location.href = "/formularz/kroki?handlowiec=" + encodeURIComponent(stan.handlowiec);
  });

  /* ======================================================== SZKIC W TELEFONIE
     Nie „autozapis do bazy": zapis idzie dopiero z przycisku. To jest wyłącznie
     ochrona przed utratą wpisanego tekstu — telefon do ucha, przełączenie
     aplikacji, wygaszony ekran, zerwana sesja. */

  var POLA = ["fx-osoba", "fx-telefon", "fx-mail", "fx-nowa-nazwa", "fx-nowa-miasto",
              "fx-nowa-typ", "fx-nowa-adres", "fx-dt-data", "fx-dt-od", "fx-dt-do",
              "fx-dt-sala", "fx-dt-klas", "fx-dt-dzieci", "fx-mail-rodzice",
              "fx-dt-uwagi", "fx-cykl-dzien", "fx-cykl-od", "fx-cykl-do",
              "fx-cykl-sala", "fx-cykl-sprzet", "fx-cykl-uwagi"];

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
          krok: stan.krok,
          wybrana: stan.wybrana,
          nowa: stan.nowa,
          trener: stan.trener,
          cyklPominiety: stan.cyklPominiety,
          pola: pola
        }));
        oznaczSzkic();
      } catch (e) {
        // Prywatne okno albo pełna pamięć — brak szkicu nie może zablokować pracy.
      }
    }, 400);
  }

  function oznaczSzkic() {
    var el = $("fx-szkic");
    var t = new Date();
    el.textContent = "Szkic zapisany w telefonie o " +
      String(t.getHours()).padStart(2, "0") + ":" + String(t.getMinutes()).padStart(2, "0") +
      " — możesz zamknąć przeglądarkę.";
    el.hidden = false;
  }

  function wczytajSzkic() {
    var s;
    try { s = JSON.parse(localStorage.getItem(KLUCZ_SZKICU) || "null"); } catch (e) { return; }
    if (!s || s.handlowiec !== stan.handlowiec) return;
    // Szkic starszy niż dobę to najpewniej zapomniany formularz — nie podstawiamy
    // go po cichu pod nową rozmowę, bo to gorsze niż jego brak.
    if (new Date() - new Date(s.kiedy) > 24 * 3600 * 1000) {
      localStorage.removeItem(KLUCZ_SZKICU);
      return;
    }
    var kiedy = new Date(s.kiedy);
    var opis = String(kiedy.getHours()).padStart(2, "0") + ":" +
               String(kiedy.getMinutes()).padStart(2, "0");
    var nazwa = s.wybrana ? s.wybrana.nazwa : (s.pola["fx-nowa-nazwa"] || "");
    if (!confirm("Masz niedokończony formularz z godz. " + opis +
                 (nazwa ? " (" + nazwa + ")" : "") + ".\n\nPrzywrócić go?")) {
      localStorage.removeItem(KLUCZ_SZKICU);
      return;
    }
    Object.keys(s.pola || {}).forEach(function (id) {
      var el = $(id); if (el) el.value = s.pola[id];
    });
    stan.trener = s.trener || "";
    stan.cyklPominiety = !!s.cyklPominiety;
    if (stan.cyklPominiety) {
      $("fx-cykl").hidden = true;
      $("fx-cykl-pomin").textContent = "Jednak ustalamy zajęcia cykliczne";
      $("fx-cykl-pomin").classList.add("on");
    }
    if (s.wybrana) {
      wybierz(s.wybrana);
    } else if (s.nowa) {
      stan.nowa = true;
      boxNowa.hidden = false;
      $("fx-nowa-otworz").hidden = true;
    }
    pokazKrok(s.krok || 1);
    toast("Przywrócono szkic");
  }

  POLA.forEach(function (id) {
    var el = $(id);
    if (!el) return;
    el.addEventListener("input", function () { czyscBlad(el); zapiszSzkic(); });
    el.addEventListener("change", function () { czyscBlad(el); zapiszSzkic(); });
  });

  /* =============================================================== START */

  var zapisano = false;

  function czyCosWpisane() {
    if (zapisano) return false;
    if (stan.wybrana || stan.nowa || stan.trener) return true;
    return POLA.some(function (id) {
      var el = $(id);
      return el && String(el.value || "").trim();
    });
  }

  awaria = FxAwaria.utworz({
    klucz: "fx-niewyslany-v1",
    kontener: root,
    handlowiec: stan.handlowiec,
    toast: toast,
    naSukces: function (j) { zapisano = true; pokazSukces(j); }
  });

  FxAwaria.pilnujWyjscia(czyCosWpisane);
  FxAwaria.pilnujZakonczenia($("fx-zakoncz"), czyCosWpisane);

  pokazKrok(1);
  if (stan.handlowiec) wczytajSzkic();
})();
