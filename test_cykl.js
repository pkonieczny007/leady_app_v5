/* =============================================================================
   Sprawdzenie reguły serii terminów.   Uruchomienie:  node test_cykl.js

   DLACZEGO OSOBNO OD TESTÓW PYTHONOWYCH
   Cała reszta projektu testuje się skryptami `.py` na tymczasowej bazie i tak
   ma zostać. Ale ta jedna reguła żyje wyłącznie w przeglądarce i nie da się jej
   sprawdzić przez API: serwer dostaje GOTOWĄ listę dat i nie ma pojęcia,
   czy powstała z przeliczenia, czy z wyklikania. A pomyłka w niej jest tania
   do zrobienia i droga do zauważenia — wyjdzie w kalendarzu, tydzień później,
   jako termin, na który nikt nie przyjedzie.

   Plik nie wchodzi do listy testów w CLAUDE.md, bo wymaga node'a, którego
   aplikacja do działania nie potrzebuje.
   ============================================================================= */
const FxCykl = require("./static/formularz4.js");

let ok = 0, zle = 0;
function sprawdz(nazwa, warunek, opis) {
  if (warunek) { ok++; console.log("  [OK  ] " + nazwa); }
  else { zle++; console.log("  [BLAD] " + nazwa + (opis ? " — " + opis : "")); }
}
const daty = (t) => t.map((x) => x.data);
const seria = (l) => l.map((d) => ({ data: d, reczna: false }));

// Przykład wprost z ustaleń: start wtorek 18.08.2026, pięć zajęć co tydzień.
const START = ["2026-08-18", "2026-08-25", "2026-09-01", "2026-09-08", "2026-09-15"];

console.log("\nC1 — propozycja serii od daty pierwszych zajęć");
sprawdz("5 zajęć co tydzień od wtorku 18.08",
        JSON.stringify(FxCykl.seria("2026-08-18", 5, 1)) === JSON.stringify(START));
sprawdz("co 2 tygodnie liczy się co 14 dni",
        JSON.stringify(FxCykl.seria("2026-08-18", 3, 2)) ===
        JSON.stringify(["2026-08-18", "2026-09-01", "2026-09-15"]));

console.log("\nC2 — zmiana na TEN SAM dzień tygodnia przelicza kolejne");
let w = FxCykl.zmien(seria(START), 1, "2026-09-01", 1);
sprawdz("25.08 → 1.09 (wtorek): ogon przesunięty",
        JSON.stringify(daty(w.terminy)) ===
        JSON.stringify(["2026-08-18", "2026-09-01", "2026-09-08",
                        "2026-09-15", "2026-09-22"]),
        daty(w.terminy).join(", "));
sprawdz("policzono trzy przeliczone terminy", w.przeliczone === 3);
sprawdz("zmieniony termin jest ustaleniem, nie propozycją", w.terminy[1].reczna === true);
sprawdz("przeliczony ogon wraca do propozycji",
        w.terminy[2].reczna === false && w.terminy[4].reczna === false);

console.log("\nC3 — zmiana na INNY dzień tygodnia zostawia kolejne w spokoju");
w = FxCykl.zmien(seria(START), 1, "2026-08-26", 1);
sprawdz("25.08 → 26.08 (środa): reszta bez zmian",
        JSON.stringify(daty(w.terminy)) ===
        JSON.stringify(["2026-08-18", "2026-08-26", "2026-09-01",
                        "2026-09-08", "2026-09-15"]),
        daty(w.terminy).join(", "));
sprawdz("nic nie przeliczono", w.przeliczone === 0);
sprawdz("wyjątek zapamiętany jako ręczny", w.terminy[1].reczna === true);

console.log("\nC4 — przypadki brzegowe");
w = FxCykl.zmien(seria(START), 4, "2026-09-22", 1);
sprawdz("zmiana OSTATNIEGO terminu nie ma czego przeliczać", w.przeliczone === 0);
w = FxCykl.zmien(seria(START), 0, "2026-08-25", 1);
sprawdz("zmiana PIERWSZEGO przesuwa całą resztę",
        JSON.stringify(daty(w.terminy)) ===
        JSON.stringify(["2026-08-25", "2026-09-01", "2026-09-08",
                        "2026-09-15", "2026-09-22"]));
w = FxCykl.zmien(seria(START), 1, "", 1);
sprawdz("wyczyszczona data nie przelicza niczego", w.przeliczone === 0);
sprawdz("poza zakresem nie wywala się", FxCykl.zmien(seria(START), 9, "2026-09-01", 1).przeliczone === 0);

// Zegar cofa się w nocy 24/25.10.2026. Licząc w czasie lokalnym, dodanie 7 dni
// do 25.10 potrafi dać 31.10 zamiast 1.11 — czyli zajęcia dzień wcześniej,
// w środku sezonu.
console.log("\nC5 — zmiana czasu z letniego na zimowy (koniec października)");
sprawdz("18.10 + 7 dni = 25.10", FxCykl.przesun("2026-10-18", 7) === "2026-10-25");
sprawdz("25.10 + 7 dni = 1.11 (a nie 31.10)", FxCykl.przesun("2026-10-25", 7) === "2026-11-01");
sprawdz("seria przez zmianę czasu trzyma niedziele",
        JSON.stringify(FxCykl.seria("2026-10-18", 4, 1)) ===
        JSON.stringify(["2026-10-18", "2026-10-25", "2026-11-01", "2026-11-08"]));
sprawdz("dzień tygodnia liczony w UTC jest stały",
        FxCykl.dzienTyg("2026-10-25") === 0 && FxCykl.dzienTyg("2026-11-01") === 0);

console.log("\n== " + ok + "/" + (ok + zle) + " sprawdzeń OK ==");
process.exit(zle ? 1 : 0);
