/* =============================================================================
   „Plan na dziś" — szkoły od koordynatora, wspólne dla v1, v2 i v3.

   Ten sam plik dołączają wszystkie trzy warianty formularza. Dzięki temu lista
   zadań wygląda i zachowuje się identycznie, a warianty różnią się wyłącznie
   sposobem wypełniania — o to chodziło w porównaniu dla klienta.

   Wariant podaje własną funkcję wybierającą szkołę (`window.FX_PLAN_WYBIERZ`),
   bo każdy robi to inaczej: v1 ma jedno pole wyszukiwania, v2 i v3 parę list
   Miejscowość → Placówka.

   KOLEJNOŚĆ jest tu treścią, nie kosmetyką. Handlowiec w szkolnym korytarzu
   patrzy na pierwsze dwie pozycje, więc na górze musi być to, co najpilniejsze:
   po terminie → dziś → jutro → dalej. Zrobione (DT umówione) na końcu i wyblakłe,
   bo to już nie jest zadanie, tylko potwierdzenie.
   ============================================================================= */
(function () {
  "use strict";

  var box = document.getElementById("fx-plan-lista");
  if (!box) return;
  var moje = window.FX_MOJE || [];
  if (!moje.length) return;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (z) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[z];
    });
  }

  function dni(iso) {
    if (!iso) return null;
    var d = new Date(iso + "T00:00:00");
    if (isNaN(d)) return null;
    var dzis = new Date();
    dzis.setHours(0, 0, 0, 0);
    return Math.round((d - dzis) / 86400000);
  }

  /* Termin słowami. „za 14 dni" jest mniej czytelne w biegu niż „14 dni",
     ale „dziś" i „jutro" muszą brzmieć jak w rozmowie — na nie patrzy się
     najczęściej i one decydują o kolejności zadań. */
  function opisTerminu(iso) {
    var n = dni(iso);
    if (n === null) return { tekst: "bez terminu", klasa: "fx-plan-brak" };
    if (n < 0) return { tekst: "po terminie od " + (-n) + " dni", klasa: "fx-plan-pilne" };
    if (n === 0) return { tekst: "termin DZIŚ", klasa: "fx-plan-pilne" };
    if (n === 1) return { tekst: "termin jutro", klasa: "fx-plan-pilne" };
    if (n <= 3) return { tekst: "termin za " + n + " dni", klasa: "fx-plan-blisko" };
    return { tekst: iso + " (za " + n + " dni)", klasa: "" };
  }

  function porzadek(p) {
    // zrobione na koniec, potem najpilniejsze; bez terminu przed tymi z terminem
    // odległym, bo „nie wiadomo do kiedy" też wymaga ruchu
    if (p.ma_dt) return 100000;
    var n = dni(p.deadline);
    return n === null ? 9000 : n;
  }

  /* Co jest ZADANIEM, a co tylko przypisaniem.

     Handlowiec ma przypisane wszystko, czym się zajmuje — u jednego z nich to
     159 szkół. Gdyby „plan na dziś" pokazywał je wszystkie, przestałby być
     planem i stałby się drugą listą bazy. Zadanie to szkoła, którą koordynator
     oznaczył terminem, albo taka, którą handlowiec sam przypiął gwiazdką na ten
     tydzień. Reszta zostaje dostępna pod przyciskiem — nic nie znika. */
  function zadanie(p) {
    return !p.ma_dt && (!!p.deadline || !!p.pin || !p.moja);
  }

  function pozycja(p, i) {
    var t = opisTerminu(p.deadline);
    var klasy = "fx-plan-poz" + (p.ma_dt ? " fx-plan-zrobione" : "") +
                (p.moja ? "" : " fx-plan-cudza");
    return '<button type="button" class="' + klasy + '" data-plan="' + i + '">' +
      '<span class="fx-plan-nazwa">' + esc(p.nazwa) +
        (p.pin ? ' <span class="fx-plan-gwiazdka" title="przypięta przez Ciebie na ten tydzień">★</span>' : "") +
      "</span>" +
      '<span class="fx-plan-miasto">' + esc(p.miejscowosc) + "</span>" +
      (p.ma_dt
        ? '<span class="fx-plan-stan fx-plan-ok">DT umówione</span>'
        : '<span class="fx-plan-stan ' + t.klasa + '">' + esc(t.tekst) + "</span>") +
      (p.moja ? "" :
        '<span class="fx-plan-ostrzezenie">⚠ przypisana do: ' +
        esc(p.wlasciciel || "kogoś innego") + "</span>") +
      "</button>";
  }

  function rysuj() {
    var lista = moje.slice().sort(function (a, b) {
      var r = porzadek(a) - porzadek(b);
      return r !== 0 ? r : String(a.nazwa).localeCompare(String(b.nazwa), "pl");
    });
    var zadania = lista.filter(zadanie);
    var reszta = lista.filter(function (p) { return !zadanie(p); });
    // gdy koordynator nie nadał jeszcze żadnego terminu, lista zadań byłaby
    // pusta i sekcja wyglądałaby na zepsutą — wtedy pokazujemy zwykłe szkoły
    var widoczne = zadania.length ? zadania : reszta.slice(0, 10);
    var ukryte = zadania.length ? reszta : reszta.slice(10);

    box.innerHTML = widoczne.map(pozycja).join("");

    // dane w tej samej kolejności co przyciski — klik trafia we właściwą szkołę
    box._lista = widoczne;

    if (ukryte.length) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "fx-plan-wiecej";
      b.textContent = "Pokaż pozostałe swoje szkoły (" + ukryte.length + ")";
      b.addEventListener("click", function () {
        var start = box._lista.length;
        box._lista = box._lista.concat(ukryte);
        b.remove();
        ukryte.forEach(function (p, i) {
          box.insertAdjacentHTML("beforeend", pozycja(p, start + i));
        });
      });
      box.appendChild(b);
    }

    var licznik = document.getElementById("fx-plan-n");
    if (licznik) {
      licznik.textContent = zadania.length
        ? zadania.length + " do zrobienia"
        : lista.length + " szkół";
      licznik.title = zadania.length
        ? "z terminem od koordynatora albo przypięte gwiazdką"
        : "koordynator nie nadał jeszcze terminów";
    }
  }

  box.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-plan]");
    if (!btn || !box._lista) return;
    var p = box._lista[parseInt(btn.dataset.plan, 10)];
    if (!p) return;
    if (typeof window.FX_PLAN_WYBIERZ === "function") {
      window.FX_PLAN_WYBIERZ(p);
    }
    var szczegoly = document.getElementById("fx-plan");
    if (szczegoly) szczegoly.open = false;    // lista schodzi z drogi po wyborze
  });

  rysuj();
})();
