# -*- coding: utf-8 -*-
"""
Buduje `index.html` — prezentację produktu prowadzoną scenariuszami z pracy.

Zasady, które trzymamy:
  * KAŻDA liczba i każde nazwisko pochodzi z bazy (patrz `dane.py`). Nic nie jest
    wymyślone „na pokaz” — jeśli klientka zapyta „a skąd te 152”, odpowiedź brzmi
    „z Twojego pliku”.
  * Plik jest samowystarczalny: styl i skrypt w środku, zero pobierania z sieci.
    Otwiera się dwuklikiem, działa na laptopie bez internetu (jak prezentacja
    z `ANALIZA\\03082026`).
  * Prowadzimy DNIEM PRACY, nie listą funkcji. Kolejność slajdów to kolejność
    czynności: koordynator rozdaje → handlowiec dzwoni → ktoś jedzie → grafik się
    zapełnia. Funkcja pokazana bez sytuacji, w której jest potrzebna, nie sprzedaje się.

Uruchomienie:  cd prezentacja && python zbuduj.py
"""
import html
import io
import os

from dane import zbierz, MIESIAC_GRAFIK, MIESIAC_KOLIZJE

TU = os.path.dirname(os.path.abspath(__file__))
WYJSCIE = os.path.join(TU, "index.html")

DNI_PL = {"2026-09-01": "wtorek", "2026-09-02": "środa", "2026-09-03": "czwartek"}


def e(s):
    return html.escape("" if s is None else str(s))


def bp(v):
    """„04. Zemela” → „Zemela” — jak filtr `bez_prefiksu` w aplikacji."""
    s = "" if v is None else str(v)
    if len(s) > 3 and s[:2].isdigit() and s[2] == ".":
        return s[3:].strip()
    return s


def krotka(v, n=44):
    """Ucina po SŁOWIE, nie w połowie wyrazu — „SZKOŁA … MAKUSZYŃSKIEGO W" wygląda
    jak błąd renderowania, a nie jak skrót."""
    s = "" if v is None else str(v).strip()
    if len(s) <= n:
        return s
    ciety = s[:n].rsplit(" ", 1)[0]
    return (ciety or s[:n]) + "…"


def data_pl(iso):
    if not iso or len(str(iso)) < 10:
        return e(iso)
    r, m, dz = str(iso)[:4], str(iso)[5:7], str(iso)[8:10]
    return "%s.%s.%s" % (dz, m, r)


# ==================================================================== STYL

CSS = """
:root{
  --bg:#0d232a; --panel:#ffffff; --panel-2:#f7fafc;
  --ink:#1f2937; --ink-2:#374151; --muted:#667085; --muted-2:#98a2b3;
  --brand:#0f2a33; --brand-l:#1d4757;
  --cyan:#22c2f2; --cyan-d:#1c9dc4; --cyan-t:#0b6f93;
  --amber:#fcaf23; --amber-d:#d68a29; --amber-l:#fff8e8;
  --line:#e3e9ee; --line-2:#eef3f7;
  --ok:#28a745; --ok-l:#d4edda;
  --warn:#ee3c23; --warn-d:#b82812; --warn-l:#fdece9;
  --filtr:#eef7fb; --filtr-b:#bfe4f2; --filtr-t:#0b6f93;
  --fill:#fffcf2; --fill-b:#ecd9a6; --fill-t:#8a6516;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;height:100%}
body{
  background:var(--bg);color:var(--ink);
  font:15px/1.55 "Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;overflow:hidden;
}
.nums{font-variant-numeric:tabular-nums}

/* ---------------------------------------------------------------- slajdy */
.deck{height:100vh;width:100vw;position:relative}
.slide{
  position:absolute;inset:0;display:none;
  padding:34px 54px 60px;overflow:auto;
  background:linear-gradient(160deg,#ffffff 0%,#f4f7f9 100%);
}
.slide.on{display:block;animation:wejscie .28s ease-out}
@keyframes wejscie{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}

.slide-head{display:flex;align-items:flex-end;gap:18px;
  border-bottom:2px solid var(--line);padding-bottom:12px;margin-bottom:22px}
.kicker{font-size:11px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
  color:var(--cyan-t)}
h1{font-size:31px;line-height:1.15;margin:2px 0 0;color:var(--brand)}
h2{font-size:19px;margin:0 0 10px;color:var(--brand)}
.slide-head .krok{margin-left:auto;font-size:12px;color:var(--muted);white-space:nowrap}
.lede{font-size:17px;color:var(--ink-2);margin:0 0 18px;max-width:80ch}
.slide p{max-width:88ch}

/* tytułowy i przerywniki */
.slide.tytul,.slide.rozdzial{
  background:linear-gradient(155deg,#1d4757 0%,#0d232a 100%);color:#fff;
  display:none;place-content:center;text-align:left;padding:0 10vw;
}
.slide.tytul.on,.slide.rozdzial.on{display:grid}
.slide.tytul h1,.slide.rozdzial h1{color:#fff;font-size:46px;max-width:22ch}
.slide.rozdzial h1{font-size:38px}
.slide.tytul .kicker,.slide.rozdzial .kicker{color:var(--cyan)}
.slide.tytul .lede,.slide.rozdzial .lede{color:#cfe4ec;font-size:19px;max-width:70ch}
.rozdzial-nr{font-size:96px;font-weight:800;color:rgba(34,194,242,.20);line-height:1}

/* ---------------------------------------------------------------- układy */
.cols{display:grid;gap:22px}
.c2{grid-template-columns:1fr 1fr}
.c23{grid-template-columns:2fr 3fr}
.c32{grid-template-columns:3fr 2fr}
@media (max-width:1100px){.cols{grid-template-columns:1fr}}

.karta{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:16px 18px;box-shadow:0 2px 6px rgba(13,35,42,.07)}
.karta h3{margin:0 0 8px;font-size:14px;color:var(--brand);
  text-transform:uppercase;letter-spacing:.05em}
.karta.akcent{border-left:4px solid var(--cyan)}
.karta.uwaga{border-left:4px solid var(--warn);background:var(--warn-l)}
.karta.dobra{border-left:4px solid var(--ok);background:#f2fbf4}
.karta.nowa{border-left:4px solid var(--amber-d);background:var(--amber-l)}

ul.lista{margin:0;padding-left:18px}
ul.lista li{margin-bottom:7px}
ul.lista li::marker{color:var(--cyan-d)}
.male{font-size:13px}
.muted{color:var(--muted)}
b.licz{font-size:15px;color:var(--brand)}

/* liczby */
.kafle{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.kafel{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:14px 16px;border-top:3px solid var(--cyan)}
.kafel .n{font-size:34px;font-weight:700;color:var(--brand);line-height:1}
.kafel .l{font-size:12px;color:var(--muted);margin-top:4px}
.kafel.ostrzega{border-top-color:var(--warn)}
.kafel.ostrzega .n{color:var(--warn-d)}
.kafel.dobrze{border-top-color:var(--ok)}

/* ---------------------------------------------------------------- makieta ekranu */
.ekran{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  overflow:hidden;box-shadow:0 6px 18px rgba(13,35,42,.11)}
.ekran-pasek{background:linear-gradient(135deg,#1d4757 0%,#0d232a 100%);color:#fff;
  padding:7px 14px;font-size:12px;display:flex;align-items:center;gap:10px}
.ekran-pasek .sciezka{font-family:Consolas,monospace;color:#8fd8f0}
.ekran-body{padding:12px 14px}

table.t{width:100%;border-collapse:separate;border-spacing:0;font-size:12.5px}
table.t th{background:var(--brand);color:#fff;text-align:left;font-size:11px;
  font-weight:600;padding:7px 8px;white-space:nowrap}
table.t td{padding:5px 8px;border-bottom:1px solid var(--line-2);vertical-align:top}
table.t tr:last-child td{border-bottom:0}
.r{text-align:right}

/* dwa języki pola — sedno jednej z poprawek */
.pole-filtr{display:inline-block;background:var(--filtr);border:2px solid var(--filtr-b);
  border-radius:6px;padding:3px 9px;font-size:12px;color:var(--ink)}
.pole-fill{display:inline-block;background:var(--fill);border:1px solid transparent;
  border-bottom:1px solid var(--fill-b);border-radius:5px;padding:3px 9px;font-size:12px}

.pasek-filtr{background:var(--filtr);border:1px solid var(--filtr-b);
  border-left:4px solid var(--cyan);border-radius:10px;padding:9px 12px;
  display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pasek-filtr::before{content:"FILTR";font-size:10px;font-weight:700;
  letter-spacing:.09em;color:var(--filtr-t)}
.lab-osoby{font-size:10px;font-weight:700;letter-spacing:.09em;color:var(--filtr-t);
  text-transform:uppercase}

.chip{display:inline-flex;align-items:center;background:#fff;border:1px solid var(--cyan-d);
  border-radius:20px;font-size:12px;overflow:hidden;box-shadow:0 1px 2px rgba(13,35,42,.06)}
.chip .z{background:var(--cyan-d);color:#fff;font-weight:700;padding:4px 7px}
.chip .t{padding:4px 8px;font-weight:600;color:var(--cyan-t)}
.chip .k{padding:4px 7px 4px 2px;font-size:11px;opacity:.6}
.chip.off{border-color:var(--line);border-style:dashed;background:var(--panel-2);box-shadow:none}
.chip.off .z{background:var(--muted-2)}
.chip.off .t{color:var(--muted-2);text-decoration:line-through;font-weight:500}
.chip.zamk{border-color:var(--amber-d);background:var(--amber-l)}
.chip.zamk .z{background:var(--amber-d)}
.chip.zamk .t{color:var(--fill-t)}
.chip.zamk .k{opacity:1}

.tag{display:inline-block;font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:20px;
  white-space:nowrap}
.tag-dt{background:var(--warn);color:#fff}
.tag-cykl{background:#e8f7fd;color:#08536e}
.tag-kol{background:var(--warn);color:#fff}
.tag-rola{background:var(--amber-l);color:var(--fill-t);border:1px solid var(--amber-d)}
.tag-ok{background:var(--ok-l);color:#155724}

.kropka{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;
  vertical-align:baseline}

/* kafelek spotkania w kalendarzu */
.ev{border-left:3px solid var(--ev,#9b9797);background:var(--panel-2);border-radius:5px;
  padding:4px 7px;margin-bottom:4px;font-size:11.5px;display:flex;gap:7px;
  align-items:center;flex-wrap:wrap}
.ev.kolizja{background:var(--warn-l);border-left-color:var(--warn)}
.ev .g{font-weight:700;font-variant-numeric:tabular-nums}
.ev .s{color:var(--ink-2)}
.ev .m{color:var(--muted);font-size:10.5px}

/* kandydaci */
.kand{display:flex;align-items:center;gap:9px;padding:5px 9px;border-radius:7px;
  margin-bottom:4px;font-size:12.5px;border:1px solid var(--line)}
.kand .kat{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;
  padding:1px 7px;border-radius:20px}
.kand.wolny{background:#f2fbf4;border-color:#bfe3c8}
.kand.wolny .kat{background:var(--ok);color:#fff}
.kand.nieznany{background:var(--panel-2)}
.kand.nieznany .kat{background:var(--muted-2);color:#fff}
.kand.zastrzezenie{background:var(--amber-l);border-color:var(--amber-d)}
.kand.zastrzezenie .kat{background:var(--amber-d);color:#fff}
.kand.niedostepny{background:var(--warn-l);border-color:#f3b8ac}
.kand.niedostepny .kat{background:var(--warn);color:#fff}
.kand .p{margin-left:auto;color:var(--muted);font-size:11.5px}

/* komórka dostępności */
.av{border:1px solid var(--line);border-radius:8px;padding:9px 11px;background:var(--ok-l)}
.av .st{font-weight:700;font-size:12px;color:#155724}
.av .z{display:block;font-size:11.5px;color:var(--ink-2);margin-top:3px}
.av .w{display:inline-block;background:#fff;border:1px solid var(--ok);border-radius:4px;
  padding:1px 6px;font-size:11.5px;font-weight:600;margin-right:4px;margin-top:3px}

/* cytat klientki */
.cytat{border-left:4px solid var(--amber-d);background:var(--amber-l);
  padding:11px 16px;border-radius:0 8px 8px 0;font-style:italic;color:var(--fill-t);
  max-width:86ch}
.cytat .kto{display:block;font-style:normal;font-size:12px;color:var(--muted);margin-top:5px}

/* przed / po */
.przedpo{display:grid;grid-template-columns:1fr 1fr;gap:0;border-radius:12px;overflow:hidden;
  border:1px solid var(--line)}
.przedpo>div{padding:14px 18px}
.przedpo .przed{background:var(--warn-l)}
.przedpo .po{background:#f2fbf4;border-left:1px solid var(--line)}
.przedpo h3{margin:0 0 8px;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.przedpo .przed h3{color:var(--warn-d)}
.przedpo .po h3{color:#155724}

/* ---------------------------------------------------------------- nawigacja */
.nawi{position:fixed;left:0;right:0;bottom:0;height:38px;background:rgba(13,35,42,.92);
  color:#cfe4ec;display:flex;align-items:center;gap:14px;padding:0 18px;font-size:12px;z-index:50}
.nawi b{color:#fff}
.nawi .rozdz{color:#8fd8f0}
.nawi .prawo{margin-left:auto;display:flex;gap:8px;align-items:center}
.nawi button{background:rgba(255,255,255,.10);color:#fff;border:0;border-radius:6px;
  padding:4px 11px;font:inherit;cursor:pointer}
.nawi button:hover{background:rgba(34,194,242,.35)}
.postep{position:fixed;left:0;bottom:38px;height:3px;background:var(--cyan);z-index:51;
  transition:width .25s}

/* przegląd wszystkich slajdów */
.przeglad{position:fixed;inset:0;background:rgba(13,35,42,.97);z-index:60;display:none;
  overflow:auto;padding:26px 30px 60px}
.przeglad.on{display:block}
.przeglad h2{color:#fff;margin:0 0 16px;font-size:16px;letter-spacing:.05em}
.pg{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:11px}
.pg a{display:block;background:#fff;border-radius:8px;padding:10px 12px;text-decoration:none;
  color:var(--ink);border-left:3px solid var(--cyan)}
.pg a:hover{outline:2px solid var(--cyan)}
.pg .n{font-size:10px;color:var(--muted);font-weight:700}
.pg .t{font-size:12.5px;font-weight:600;color:var(--brand);line-height:1.3;margin-top:2px}
.pg a.r{border-left-color:var(--amber)}

@media print{
  body{overflow:visible;background:#fff}
  .deck{height:auto}
  .slide{position:static;display:block!important;page-break-after:always;height:auto;
    min-height:0;box-shadow:none;padding:18mm 16mm}
  .slide.tytul,.slide.rozdzial{display:grid!important;min-height:150mm}
  .nawi,.postep,.przeglad{display:none!important}
}
"""

JS = """
var slajdy = Array.prototype.slice.call(document.querySelectorAll('.slide'));
var i = 0;
var licznik = document.getElementById('licznik');
var tytulNaw = document.getElementById('tytul-nawi');
var postep = document.getElementById('postep');

function pokaz(n){
  i = Math.max(0, Math.min(slajdy.length - 1, n));
  slajdy.forEach(function(s, k){ s.classList.toggle('on', k === i); });
  licznik.textContent = (i + 1) + ' / ' + slajdy.length;
  tytulNaw.textContent = slajdy[i].dataset.tytul || '';
  postep.style.width = ((i + 1) / slajdy.length * 100) + '%';
  slajdy[i].scrollTop = 0;
  try { location.hash = 's' + (i + 1); } catch (err) {}
}

document.addEventListener('keydown', function(ev){
  var p = document.getElementById('przeglad');
  if (ev.key === 'Escape') { p.classList.remove('on'); return; }
  if (p.classList.contains('on')) return;
  if (ev.key === 'ArrowRight' || ev.key === 'PageDown' || ev.key === ' ') { ev.preventDefault(); pokaz(i + 1); }
  else if (ev.key === 'ArrowLeft' || ev.key === 'PageUp') { ev.preventDefault(); pokaz(i - 1); }
  else if (ev.key === 'Home') { pokaz(0); }
  else if (ev.key === 'End') { pokaz(slajdy.length - 1); }
  else if (ev.key === 'o' || ev.key === 'O') { p.classList.add('on'); }
});

document.getElementById('dalej').onclick = function(){ pokaz(i + 1); };
document.getElementById('wstecz').onclick = function(){ pokaz(i - 1); };
document.getElementById('spis').onclick = function(){
  document.getElementById('przeglad').classList.toggle('on');
};
document.getElementById('przeglad').addEventListener('click', function(ev){
  var a = ev.target.closest('a[data-do]');
  if (a) { ev.preventDefault(); this.classList.remove('on'); pokaz(parseInt(a.dataset.do, 10)); }
});

var start = parseInt((location.hash || '').replace('#s', ''), 10);
pokaz(isNaN(start) ? 0 : start - 1);
"""


# ==================================================================== slajdy

SLAJDY = []      # (typ, tytul_do_spisu, html)


def slajd(kicker, tytul, tresc, krok=""):
    SLAJDY.append(("s", tytul, """
<section class="slide" data-tytul="%s">
  <div class="slide-head">
    <div><div class="kicker">%s</div><h1>%s</h1></div>
    %s
  </div>
  %s
</section>""" % (e(tytul), e(kicker), e(tytul),
                 ('<div class="krok">%s</div>' % e(krok)) if krok else "", tresc)))


def rozdzial(nr, tytul, lede):
    SLAJDY.append(("r", tytul, """
<section class="slide rozdzial" data-tytul="%s">
  <div class="rozdzial-nr">%s</div>
  <div class="kicker">Część %s</div>
  <h1>%s</h1>
  <p class="lede">%s</p>
</section>""" % (e(tytul), e(nr), e(nr), e(tytul), lede)))


def ekran(sciezka, opis, body):
    return """
<div class="ekran">
  <div class="ekran-pasek"><span class="sciezka">%s</span><span>%s</span></div>
  <div class="ekran-body">%s</div>
</div>""" % (e(sciezka), e(opis), body)


def buduj(d):
    m = d["metryki"]
    KOL = "#22c2f2"

    # Deklaracje dostępności w tej bazie są wypełnione przykładowo. Mówimy o tym
    # WPROST na obu slajdach, które z nich korzystają — bo dopisek „(demo)"
    # wychodzi w powodach przy kandydatach i bez wyjaśnienia wygląda na usterkę.
    # Po wyczyszczeniu wierszy demo przypis znika sam przy kolejnym budowaniu.
    przypis_demo = ""
    if d.get("dostepnosc_demo"):
        przypis_demo = ("""
    <div class="karta" style="margin-top:14px;border-left:4px solid var(--muted-2)">
      <h3>Uczciwie o danych na tym slajdzie</h3>
      <p class="male" style="margin:0">Leady, szkoły, spotkania i nazwiska są
         <b>prawdziwe — z pliku PH Nowy</b>. Deklaracje dostępności to jedyna rzecz,
         której w Waszym pliku nie ma wcale, więc na potrzeby pokazu jest ich
         <b class="nums">%s</b> wypełnionych przykładowo (stąd dopisek „demo”
         przy powodach). Mechanizm jest prawdziwy, godziny zmyślone.</p>
    </div>""" % d.get("dostepnosc_n_demo", 0))

    # ---------------------------------------------------------------- tytuł
    SLAJDY.append(("t", "System Leadów — start", """
<section class="slide tytul" data-tytul="System Leadów — start">
  <div class="kicker">SILESIA 3D · prototyp na Waszych danych</div>
  <h1>System Leadów zamiast arkusza</h1>
  <p class="lede">Jeden dzień pracy: od rozdania leadów rano, przez umówienie DT
     i obsadzenie trenera, po grafik i eksport do Excela. Wszystko na Waszym pliku
     <b>PH Nowy</b> — %s placówek, %s spotkań, %s trenerów.</p>
  <p class="lede" style="font-size:15px;opacity:.75">
     ← → przewijanie · <b>O</b> spis slajdów · <b>Ctrl+P</b> wydruk do PDF</p>
</section>""" % (m["placowki"], m["eventy_dt"] + m["eventy_cykl"], d["n_trenerow"])))

    slajd("Dlaczego", "Cztery rzeczy, które bolały w arkuszu", """
<div class="przedpo">
  <div class="przed">
    <h3>Jak jest w arkuszu</h3>
    <ul class="lista male">
      <li><b>Ten sam wiersz w trzech zakładkach.</b> Poprawiasz datę w jednym miejscu,
          w dwóch zostaje stara.</li>
      <li><b>Trener ma 2 DT jednego dnia, a widać jedno.</b> Komórka kalendarza to
          <code>XLOOKUP</code>, który zwraca <i>pierwsze</i> trafienie.</li>
      <li><b>Listy rozjeżdżają się między zakładkami.</b> „02. Olaszewska” obok
          „02. Olszewska”, trzy różne listy miejscowości.</li>
      <li><b>Odebranie leada = wycinanie wiersza</b> do zakładki „niewykorzystane”.</li>
    </ul>
  </div>
  <div class="po">
    <h3>Jak jest tutaj</h3>
    <ul class="lista male">
      <li><b>Jedno źródło, ekrany to filtry.</b> Poprawka widoczna od razu wszędzie.</li>
      <li><b>W komórce jest lista.</b> Widać wszystkie spotkania, a nakładające się
          godziny dostają ostrzeżenie.</li>
      <li><b>Jeden słownik + aliasy.</b> Wartości spoza listy nie da się zapisać
          (%s aliasów scala literówki przy imporcie).</li>
      <li><b>Zmiana statusu.</b> Nic się nie usuwa i nic nie przenosi — zmienia się
          tylko to, na których ekranach lead widać.</li>
    </ul>
  </div>
</div>
<p class="lede" style="margin-top:18px">To nie jest makieta. Poniższe slajdy pokazują
   ekrany wypełnione <b>Waszymi danymi</b> — z nazwiskami, szkołami i terminami,
   które są dziś w pliku.</p>""" % d["n_aliasow"])

    # ================================================================ 1
    rozdzial("1", "Poniedziałek rano — koordynator",
             "Pytanie na start dnia: co mamy w robocie, kto jest do tyłu "
             "i co dziś rozdać handlowcom.")

    kafle = [
        ("dobrze", m["placowki"], "placówek w bazie"),
        ("", m["nieprzydzielone"], "czeka na rozdanie"),
        ("dobrze", m["umowione"], "z umówionym DT"),
        ("ostrzega", m["po_terminie"], "po terminie ostatecznym"),
        ("", d["n_kolizji"], "kolizji w %s" % d["miesiac_kolizje"].lower()),
    ]
    slajd("Pulpit", "Jedno spojrzenie zamiast przeglądania zakładek", """
<div class="kafle">%s</div>
<div class="cols c2" style="margin-top:20px">
  <div class="karta akcent">
    <h3>Realizacja minimum tygodniowego</h3>
    <table class="t"><thead><tr><th>Handlowiec</th><th class="r">Leadów</th>
      <th class="r">Umówione DT</th><th class="r">Skuteczność</th></tr></thead><tbody>%s</tbody></table>
    <p class="male muted" style="margin:8px 0 0">Tydzień liczony od poniedziałku
       (%s). To odpowiedź na „STATUS — minimum na tydzień” z Waszych notatek.</p>
  </div>
  <div class="karta">
    <h3>Co z tym robię</h3>
    <ul class="lista male">
      <li>Widzę, że <b>%s placówek</b> nikt jeszcze nie dostał — idę na ekran „Baza”.</li>
      <li>Widzę <b>%s leadów po terminie</b> — kandydaci do odebrania handlowcowi.</li>
      <li>Widzę kolizje w grafiku — ktoś ma dwa zajęcia na raz, trzeba przestawić.</li>
    </ul>
    <p class="male muted" style="margin:10px 0 0">Każda liczba jest klikalna i prowadzi
       do listy, z której powstała. Nigdzie nie trzeba przepisywać.</p>
  </div>
</div>""" % (
        "".join('<div class="kafel %s"><div class="n nums">%s</div><div class="l">%s</div></div>'
                % (k, n, e(l)) for k, n, l in kafle),
        "".join('<tr><td>%s</td><td class="r nums">%s</td><td class="r nums">%s</td>'
                '<td class="r nums"><b>%s%%</b></td></tr>'
                % (e(r["handlowiec"]), r["leadow"], r["umowione"], r["proc"])
                for r in d["per_handlowiec"]),
        data_pl(d["poniedzialek"]), m["nieprzydzielone"], m["po_terminie"]))

    slajd("Baza · rozdanie leadów", "Zaznaczam kilka szkół i przypisuję je naraz",
          ekran("/baza", "Koordynator · rozdawanie leadów", """
<div class="pasek-filtr" style="margin-bottom:10px">
  <span class="pole-filtr">— handlowiec —</span>
  <span class="pole-filtr">— miejscowość —</span>
  <span class="pole-filtr">szukaj: placówka / kontakt…</span>
  <span class="muted male" style="margin-left:auto">%s rekordów</span>
</div>
<div style="background:linear-gradient(135deg,#1d4757,#0d232a);color:#fff;border-radius:8px;
     padding:8px 12px;font-size:12px;display:flex;gap:12px;align-items:center;margin-bottom:10px">
  <b class="nums">4</b> zaznaczone
  <span class="pole-filtr" style="background:#fff">— wybierz handlowca —</span>
  <span>termin ostateczny</span><span class="pole-filtr" style="background:#fff">2026-09-30</span>
  <span style="background:var(--cyan-d);padding:3px 12px;border-radius:6px;font-weight:600">Przypisz</span>
</div>
<table class="t">
  <thead><tr><th style="width:26px"></th><th>Placówka</th><th>Miejscowość</th>
    <th>Handlowiec</th><th>Termin ostateczny</th></tr></thead>
  <tbody>%s</tbody>
</table>""" % (m["nieprzydzielone"], "".join(
              '<tr><td>☑</td><td><b>%s</b></td><td class="muted">%s</td>'
              '<td><span class="pole-fill">— %s</span></td>'
              '<td><span class="pole-fill">%s</span></td></tr>'
              % (e(krotka(r["nazwa"], 44)), e(bp(r["miejscowosc"])), e(bp(r["handlowiec"] or "—")),
                 data_pl(r["deadline"]))
              for r in d["po_terminie"][:4]))) + """
<div class="cols c2" style="margin-top:18px">
  <div class="karta dobra">
    <h3>Co się dzieje po kliknięciu „Przypisz”</h3>
    <ul class="lista male">
      <li>Cztery leady dostają handlowca i wspólny <b>termin ostateczny</b>.</li>
      <li>Nic nie zostaje skopiowane do innej zakładki — te same wiersze
          po prostu pojawiają się na ekranie „Leady” tego handlowca.</li>
      <li>Zmiana ląduje w historii: kto, kiedy, z czego na co.</li>
    </ul>
  </div>
  <div class="karta nowa">
    <h3>Kolor mówi, co robi pole</h3>
    <p class="male" style="margin:0 0 8px">To jedyna rzecz, której trzeba się nauczyć —
       i uczy się jej raz:</p>
    <p style="margin:0 0 6px"><span class="pole-filtr">zimny błękit</span>
       &nbsp;= <b>filtruję</b>, danych nie ruszam</p>
    <p style="margin:0"><span class="pole-fill">ciepły krem</span>
       &nbsp;= <b>wypełniam</b>, zapis do bazy od razu po zmianie</p>
    <p class="male muted" style="margin:9px 0 0">Wcześniej jedno i drugie było
       białym prostokątem — i próba filtrowania nadpisywała dane.</p>
  </div>
</div>""")

    # ================================================================ 2
    rozdzial("2", "Handlowiec — mój dzień",
             "Mam swoje szkoły, mam terminy i mam jeden ekran, na którym widzę,"
             " co się pali.")

    po_t = d["po_terminie"]
    slajd("Leady · po terminie", "„Komu minął termin i nic z tym nie zrobił?”",
          ekran("/leady?zakres=po_terminie", "Praca bieżąca · Po terminie", """
<table class="t">
  <thead><tr><th>Placówka</th><th>Miejscowość</th><th>Handlowiec</th>
    <th>Termin ostateczny</th><th>Status</th></tr></thead>
  <tbody>%s</tbody>
</table>""" % "".join(
              '<tr><td><b>%s</b></td><td class="muted">%s</td><td>%s</td>'
              '<td style="background:#fbdad3;color:#b82812;font-weight:700" class="nums">%s</td>'
              '<td class="male muted">%s</td></tr>'
              % (e(krotka(r["nazwa"], 40)), e(bp(r["miejscowosc"])), e(bp(r["handlowiec"] or "—")),
                 data_pl(r["deadline"]), e(r["status_realizacji"]))
              for r in po_t)) + """
<div class="cols c32" style="margin-top:18px">
  <div class="karta uwaga">
    <h3>To jest kontrola, nie kara</h3>
    <p class="male" style="margin:0">Magenta zapala się, gdy <b>termin minął, a DT nadal
       nie ma</b>. System niczego nie kasuje i nie przenosi — pokazuje listę do rozmowy.
       Jeśli lead ma wrócić do puli, koordynator klika „Odbierz handlowcowi”, co zmienia
       <b>status</b>, a nie usuwa wiersz. Historia zostaje.</p>
  </div>
  <div class="karta">
    <h3>Skąd to wiadomo</h3>
    <p class="male" style="margin:0">Każda zmiana pola jest zapisywana z datą, więc
       na karcie leada widać, czy handlowiec ruszył sprawę przed terminem, czy dopiero
       po. To był wprost jeden z Waszych wymogów.</p>
  </div>
</div>"""
          , krok="%s leadów spełnia ten warunek dziś" % m["po_terminie"])

    lead = d["lead"]
    dt_ev = [x for x in lead["eventy"] if x["typ"] == "DT"]
    cyk = [x for x in lead["eventy"] if x["typ"] != "DT"]
    slajd("Karta leada", "Umawiam DT — status zmienia się sam", """
<div class="cols c23">
  <div>
    %s
    <div class="karta dobra" style="margin-top:14px">
      <h3>Dodanie DT z datą robi trzy rzeczy naraz</h3>
      <ul class="lista male">
        <li>status leada przechodzi na <b>„03. DT umówione”</b>,</li>
        <li>szkoła znika z listy „w pracy”, a pojawia się w „DT umówione” i u Julii,</li>
        <li>spotkanie od razu widać w kalendarzu i w dostępności trenera.</li>
      </ul>
      <p class="male muted" style="margin:8px 0 0">Nie trzeba nic przepisywać do innej
         zakładki — to ten sam rekord oglądany z innej strony.</p>
    </div>
  </div>
  <div class="karta">
    <h3>Spotkania tej szkoły (<span class="nums">%s</span>)</h3>
    %s
    <p class="male muted" style="margin:10px 0 0"><b>Cykl to jeden rekord z regułą</b>,
       a nie kilkadziesiąt skopiowanych wierszy. Przesunięcie godziny zajęć to jedna
       edycja; zastępstwo na jedną datę to jeden wyjątek.</p>
  </div>
</div>""" % (
        ekran("/lead/%s" % lead["id"], "Karta leada", """
<div style="font-size:13px">
  <div style="font-size:16px;font-weight:700;color:#0f2a33">%s</div>
  <div class="muted male" style="margin-bottom:10px">%s · %s</div>
  <table class="t"><tbody>
    <tr><td class="muted" style="width:44%%">Handlowiec</td><td><span class="pole-fill">%s</span></td></tr>
    <tr><td class="muted">Status realizacji</td><td><span class="pole-fill">%s</span></td></tr>
    <tr><td class="muted">Termin ostateczny</td><td><span class="pole-fill">%s</span></td></tr>
  </tbody></table>
</div>""" % (e(krotka(lead["placowka"], 46)), e(bp(lead["miejscowosc"])), e(lead["adres"] or ""),
             e(lead["handlowiec"] or "—"), e(lead["status_realizacji"] or "—"),
             data_pl(lead["deadline"]))),
        len(lead["eventy"]),
        "".join(
            '<div class="ev" style="--ev:%s"><span class="tag %s">%s</span>'
            '<span class="g">%s</span><span class="s">%s</span>'
            '<span class="m">%s</span></div>'
            % (KOL, "tag-dt" if x["typ"] == "DT" else "tag-cykl", e(x["typ"]),
               data_pl(x["data"]),
               e((x["godz_od"] or "—") + ("–" + x["godz_do"] if x["godz_do"] else "")),
               e(bp(x["trener"]) or "bez obsady"))
            for x in (dt_ev + cyk)[:6])))

    # ================================================================ 3
    rozdzial("3", "Kogo wysłać na to DT",
             "Najdroższe pytanie dnia. Do tej pory odpowiadało się na nie z pamięci"
             " i przez telefon.")

    ev = d["obsada_event"]
    ile = d["kandydaci_ile"]
    top = []
    for kat in ("wolny", "nieznany", "zastrzezenie", "niedostepny"):
        for k in d["kandydaci"]:
            if k["kategoria"] == kat:
                top.append(k)
                break
    slajd("Panel „Kogo wysłać?”", "Ranking zamiast telefonów", """
<div class="cols c32">
  <div>
    %s
  </div>
  <div>
    <div class="karta akcent">
      <h3>Czym się różnią kategorie</h3>
      <ul class="lista male">
        <li><b>wolny</b> — jest deklaracja dostępności i nic mu w tym czasie nie koliduje,</li>
        <li><b>bez deklaracji</b> — po prostu nie wiemy. To <u>nie</u> znaczy „nie może”,</li>
        <li><b>z zastrzeżeniem</b> — coś nie gra: kolizja godzin albo termin poza jego oknem,</li>
        <li><b>niedostępny</b> — sam wpisał, że go nie ma (Wasze arkuszowe „XXX”).</li>
      </ul>
    </div>
    <div class="karta nowa" style="margin-top:14px">
      <h3>Nic nie jest zablokowane</h3>
      <p class="male" style="margin:0">Niedostępnego trenera <b>też da się przydzielić</b> —
         przycisk zmienia się wtedy na „Mimo to przydziel” i wraca ostrzeżenie.
         Decyzja należy do człowieka, system tylko mówi, co wie.</p>
    </div>
    %s
  </div>
</div>
<p class="lede" style="margin-top:16px">Kolejność w rankingu:
   <b>kategoria → rejon → obciążenie → nazwisko</b>. Dzięki temu na górze jest ktoś,
   kto jest wolny, jeździ po tym mieście i ma najmniej zajęć w miesiącu.</p>""" % (
        ekran("/lead/… → „Kogo wysłać?”",
              "%s · %s · %s–%s" % (bp(ev["miejscowosc"]), data_pl(ev["data"]),
                                   ev["godz_od"], ev["godz_do"]), """
<div class="male muted" style="margin-bottom:8px">%s</div>
<div style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap">
  <span class="tag tag-ok">wolni: %s</span>
  <span class="tag" style="background:#e6edf2;color:#667085">bez deklaracji: %s</span>
  <span class="tag" style="background:#fff8e8;color:#8a6516;border:1px solid #d68a29">z zastrzeżeniem: %s</span>
  <span class="tag tag-kol">niedostępni: %s</span>
</div>
%s""" % (e(krotka(ev["placowka"], 52)), ile.get("wolny", 0), ile.get("nieznany", 0),
         ile.get("zastrzezenie", 0), ile.get("niedostepny", 0),
         "".join('<div class="kand %s"><span class="kat">%s</span>'
                 '<b>%s</b><span class="p">%s</span></div>'
                 % (k["kategoria"],
                    {"wolny": "wolny", "nieznany": "bez deklaracji",
                     "zastrzezenie": "zastrzeżenie", "niedostepny": "niedostępny"}[k["kategoria"]],
                    e(bp(k["trener"])), e(k["powod"]))
                 for k in top))), przypis_demo))

    av = d["dostepnosc_przyklad"]
    c = av["cell"]
    slajd("Dostępność trenerów", "Wolne okna liczą się same", """
<div class="cols c2">
  <div>
    %s
    <p class="male muted" style="margin-top:10px">Komórka z siatki
       <b>trener × dzień</b> — ten sam układ co kalendarz, żeby nie uczyć się dwóch.</p>
  </div>
  <div>
    <div class="karta akcent">
      <h3>Skąd się biorą „wolne”</h3>
      <p class="male" style="margin:0 0 8px"><b>Deklaracja minus to, co już wisi
         w kalendarzu.</b> Trenerka zadeklarowała %s. W tym czasie ma już %s zajęcia.
         Zostaje realnie <b>%s</b>.</p>
      <p class="male" style="margin:0">Przerwa %s została pominięta, bo jest krótsza
         niż 45 minut — nie zmieści się w niej ani DT, ani cykl. W arkuszu trenerki
         dopisywały zajętość ręcznie w nawiasach i to się rozjeżdżało.</p>
    </div>
    <div class="karta" style="margin-top:14px">
      <h3>Trzy stany, nie dwa</h3>
      <ul class="lista male">
        <li><b>pusto</b> = dostępność <u>nieznana</u> — nikt nie pytał,</li>
        <li><b>niedostępny</b> = Wasze „XXX”, ktoś jawnie powiedział „nie”,</li>
        <li><b>okno godzin</b> albo „cały dzień” = deklaracja.</li>
      </ul>
      <p class="male muted" style="margin:8px 0 0">W arkuszu wszystkie trzy mieszały się
         w jednej komórce tekstowej. To ekran, którego w „PH Nowy” nie ma wcale —
         był w pliku zeszłorocznym.</p>
    </div>
    %s
  </div>
</div>""" % (
        ekran("/dostepnosc", "%s · %s" % (bp(av["trener"]), data_pl(c["iso"])), """
<div class="av">
  <span class="st">deklaracja: %s</span>
  %s
  <div style="margin-top:6px"><span class="male muted">wolne:</span> %s</div>
</div>""" % (e(c["okno"]),
             "".join('<span class="z">zajęte %s–%s · %s</span>'
                     % (e(z["godz_od"] or "?"), e(z["godz_do"] or "?"), e(krotka(z["placowka"], 34)))
                     for z in c["zajete"]),
             "".join('<span class="w nums">%s</span>' % e(w) for w in c["wolne"]))),
        e(c["okno"]), len(c["zajete"]), e(", ".join(c["wolne"])),
        e("%s–%s" % (c["zajete"][0]["godz_do"], c["zajete"][1]["godz_od"]))
        if len(c["zajete"]) > 1 and c["zajete"][0]["godz_do"] else "między zajęciami",
        przypis_demo))

    # ================================================================ 4
    rozdzial("4", "Grafik — kalendarz DT",
             "Ten sam komplet spotkań w trzech widokach. I miejsce, w którym"
             " arkusz gubił dane.")

    kol = d["kolizja"]
    if len(kol) >= 2:
        a, b = kol[0], kol[1]
        slajd("Kalendarz · kolizja", "Dwa zajęcia jednej osoby w tym samym czasie", """
<div class="cols c32">
  <div>
    %s
    <p class="male muted" style="margin-top:10px">Kafelki leżą w komórce
       <b>%s · %s</b> siatki trener × dzień.</p>
  </div>
  <div>
    <div class="karta uwaga">
      <h3>Czego arkusz nie umiał pokazać</h3>
      <p class="male" style="margin:0">Komórka kalendarza w Waszym pliku to
         <code>XLOOKUP(data &amp; trener; …)</code>, a <code>XLOOKUP</code> zwraca
         <b>pierwsze</b> trafienie. Drugie zajęcia były w danych, ale formuła nie
         miała jak ich wyświetlić. Tutaj w komórce jest <b>lista</b>, więc widać oba.</p>
    </div>
    <div class="karta" style="margin-top:14px">
      <h3>Skąd wiadomo, że to kolizja</h3>
      <p class="male" style="margin:0">Godziny są osobnymi polami czasu, a nie tekstem
         „08:00-12:30” — więc da się je porównać. %s i %s to dwie różne szkoły
         (%s i %s), więc dojazd też jest problemem.</p>
      <p class="male muted" style="margin:8px 0 0">W %s wykryto <b>%s</b> takich zajęć.
         Ostrzegamy — nie blokujemy.</p>
    </div>
  </div>
</div>""" % (
            ekran("/kalendarz?widok=macierz", "Grafik trenerów · %s" % d["miesiac_kolizje"],
                  "".join(
                      '<div class="ev kolizja" style="--ev:%s"><span class="g">%s–%s</span>'
                      '<span class="s"><b>%s</b></span><span class="m">%s</span>'
                      '<span class="tag tag-kol">kolizja</span></div>'
                      % (KOL, e(x["godz_od"]), e(x["godz_do"]), e(krotka(x["placowka"], 32)),
                         e(bp(x["miejscowosc"])))
                      for x in (a, b))),
            e(bp(a["trener"])), data_pl(a["data"]),
            e(bp(a["miejscowosc"])), e(bp(b["miejscowosc"])),
            e(krotka(a["placowka"], 24)), e(krotka(b["placowka"], 24)),
            d["miesiac_kolizje"].lower(), d["n_kolizji"]))

    slajd("Kalendarz · filtr", "„Gdzie dziś jest %s?”" % bp(d["filtr_osoba"]), """
<div class="cols c2">
  <div class="karta">
    <h3>Wpisuję nazwisko — nie szukam go na liście</h3>
    <div class="pasek-filtr" style="margin-bottom:12px">
      <span class="lab-osoby">Szukaj</span>
      <span class="chip"><span class="z">N</span><span class="t">%s</span><span class="k">🔓 ✕</span></span>
      <span class="pole-filtr">wpisz cokolwiek i naciśnij Enter…</span>
    </div>
    <p class="male" style="margin:0">Wystarczy <b>fragment</b> — „olsz” znajdzie
       i „02. Olszewska”, i „Olszewska”. Wpisów może być kilka, każdy da się
       <b>wyłączyć</b> bez kasowania i <b>przypiąć kłódką</b>, żeby przetrwał zmianę
       miesiąca, widoku i przycisk „Wyczyść”.</p>
  </div>
  <div class="karta nowa">
    <h3>Dwa zakresy — i to jest ważne</h3>
    <p style="margin:0 0 8px"><span class="chip"><span class="z">∗</span><span class="t">wszystko</span></span>
       &nbsp;→ <b class="licz nums">%s</b> spotkań w %s wierszach</p>
    <p style="margin:0 0 10px"><span class="chip zamk"><span class="z">N</span><span class="t">nazwisko</span></span>
       &nbsp;→ <b class="licz nums">%s</b> spotkań w %s wierszach</p>
    <p class="male" style="margin:0">Skąd ta różnica? <b>%s jest u Was jednocześnie
       handlowcem i trenerką.</b> „Wszystko” łapie też zajęcia, które <i>sprzedała</i>,
       a jeździ na nie kto inny. „Nazwisko” pyta wyłącznie o to, <b>kto tam będzie</b>.</p>
  </div>
</div>
<div class="cols c2" style="margin-top:16px">
  <div class="karta akcent">
    <h3>A gdy jest tam w innej roli?</h3>
    <p class="male" style="margin:0 0 8px">Zostaje <b>%s</b> spotkań, na których jest
       <b>drukarzem</b> u kogo innego. Trafiają do wiersza tamtego trenera — słusznie,
       bo naprawdę tam jedzie — więc kafelek dostaje podpis roli:</p>
    <div class="ev" style="--ev:%s"><span class="g">13:50–14:50</span>
      <span class="s">SP nr 8 im. W. Korfantego</span>
      <span class="tag tag-rola">drukarz</span></div>
    <p class="male muted" style="margin:8px 0 0">Bez tego podpisu wpis w cudzym wierszu
       wygląda na pomyłkę filtra.</p>
  </div>
  <div class="karta">
    <h3>Ten sam filtr na listach leadów</h3>
    <ul class="lista male">
      <li><span class="chip"><span class="z">H</span><span class="t">Sacawa</span></span>
          → <b class="nums">%s</b> leadów tego handlowca</li>
      <li><span class="chip"><span class="z">T</span><span class="t">Zemela</span></span>
          → <b class="nums">%s</b> leadów, na które jeździ ten prowadzący</li>
      <li>oba naraz w trybie <b>ORAZ</b> → <b class="nums">%s</b> — „leady Sacawy,
          na które jeździ Zemela”</li>
    </ul>
    <p class="male muted" style="margin:6px 0 0">Po prowadzących nie dało się
       wcześniej filtrować w ogóle.</p>
  </div>
</div>""" % (e(bp(d["filtr_osoba"])), d["filtr_wszystko"], d["filtr_wiersze_w"],
             d["filtr_nazwisko"], d["filtr_wiersze_n"], e(d["filtr_osoba"]),
             d["filtr_role"], KOL,
             d["leady_sacawa"], d["leady_zemela"], d["leady_oba"]),
          krok="%s · %s spotkań w miesiącu" % (d["miesiac_kolizje"], d["n_eventow_miesiac"]))

    slajd("Kalendarz · trzy widoki", "Te same dane, trzy sposoby patrzenia", """
<div class="cols" style="grid-template-columns:repeat(3,1fr)">
  <div class="karta akcent">
    <h3>▦ Macierz</h3>
    <p class="male" style="margin:0 0 8px"><b>Trener × dzień</b>, bloki tygodniowe —
       tak jak w Waszym arkuszu, tylko bloki są pod sobą, a nie obok siebie.</p>
    <p class="male muted" style="margin:0">Do pytania: <i>„kto ma wolne w czwartek?”</i></p>
  </div>
  <div class="karta akcent">
    <h3>☰ Agenda</h3>
    <p class="male" style="margin:0 0 8px">Dzień po dniu, spotkania w kolejności godzin.
       Czytelne przy dużym ruchu — u Was bywa ~30 zajęć dziennie.</p>
    <p class="male muted" style="margin:0">Do pytania: <i>„co się dzieje we wtorek?”</i></p>
  </div>
  <div class="karta akcent">
    <h3>▤ Starty</h3>
    <p class="male" style="margin:0 0 8px">Odwzorowanie zakładki „STARTY &lt;MIESIĄC&gt;”:
       karty z godzinami, adresem, grupą, sprzętem, obsadą i kodem Tinkercad.</p>
    <p class="male muted" style="margin:0">Do pytania: <i>„co drukuję na jutro?”</i></p>
  </div>
</div>
<div class="karta" style="margin-top:18px">
  <h3>Jedna rzecz, która jest wspólna dla wszystkich trzech</h3>
  <p class="male" style="margin:0"><b>Kolizje wykrywamy na pełnym miesiącu, a liczymy
     po filtrze.</b> Nakładka to zawsze <i>para</i> zajęć — gdyby filtr działał pierwszy,
     wyfiltrowanie jednej szkoły chowałoby drugą stronę nakładki i ostrzeżenie
     znikałoby po cichu. To najgorszy rodzaj błędu, jaki mógłby tu być, więc
     jest zrobione odwrotnie.</p>
</div>""")

    # ================================================================ 5
    rozdzial("5", "Porządek w danych i wyjście do Excela",
             "Żeby to, co wpisujecie, dało się potem wyjąć — i żeby literówka"
             " nie wracała tylnymi drzwiami.")

    slajd("Słowniki i aliasy", "„02. Olaszewska” już nie wróci", """
<div class="cols c2">
  <div class="karta">
    <h3>Aliasy z Waszego pliku (<span class="nums">%s</span>)</h3>
    <table class="t"><thead><tr><th>Zapis w arkuszu</th><th>Wartość docelowa</th>
      <th>Lista</th></tr></thead><tbody>%s</tbody></table>
    <p class="male muted" style="margin:8px 0 0">Alias działa <b>przy imporcie</b>:
       cokolwiek historycznie wpisano, wjeżdża jako jedna wartość kanoniczna.</p>
  </div>
  <div>
    <div class="karta dobra">
      <h3>Skąd biorą się wartości</h3>
      <p class="male" style="margin:0 0 8px">Jeden słownik na całą aplikację —
         nie ma „listy trenerów w zakładce A” i „listy trenerów w zakładce B”:</p>
      <p class="male" style="margin:0">%s</p>
    </div>
    <div class="karta uwaga" style="margin-top:14px">
      <h3>Wartości spoza listy nie da się zapisać</h3>
      <p class="male" style="margin:0">Próba wpisania nazwiska, którego nie ma w słowniku,
         jest odrzucana — również przy dodawaniu nowej placówki. To jedyne miejsce,
         gdzie system mówi „nie”, i celowo: tu właśnie rodził się bałagan.</p>
    </div>
  </div>
</div>""" % (d["n_aliasow"],
             "".join('<tr><td><b>%s</b></td><td>%s</td><td class="muted male">%s</td></tr>'
                     % (e(a["alias"]), e(a["wartosc"]), e(a["rodzaj"])) for a in d["aliasy"]),
             " · ".join('<b class="nums">%s</b>&nbsp;%s' % (s["c"], e(s["rodzaj"]))
                        for s in d["slowniki"][:8])))

    slajd("Eksport", "„Chcę pobrać to, co widzę” — dosłownie", """
<div class="cols c23">
  <div class="karta akcent">
    <h3>Jedna zasada</h3>
    <p class="male" style="margin:0 0 8px">Przycisk <b>„↓ Pobierz XLSX”</b> bierze
       <u>dokładnie ten sam filtr</u>, który widzisz na ekranie — łącznie z wpisanymi
       nazwiskami. Nie „wszystko”, nie „bieżącą stronę”.</p>
    <p class="male" style="margin:0">Filtr siedzi w adresie strony, więc widok, licznik
       „N rekordów” i eksport czytają to samo. Nie mają jak się rozjechać.</p>
  </div>
  <div class="karta">
    <h3>Cztery arkusze w pliku</h3>
    <table class="t"><tbody>
      <tr><td><b>Leady</b></td><td class="male muted">układ kolumn jak u Was</td></tr>
      <tr><td><b>Spotkania</b></td><td class="male muted">1 wiersz = 1 spotkanie</td></tr>
      <tr><td><b>Kolizje</b></td><td class="male muted">co się nakłada</td></tr>
      <tr><td><b>Filtr</b></td><td class="male muted">co było ustawione przy eksporcie</td></tr>
    </tbody></table>
    <p class="male muted" style="margin:8px 0 0">Ostatni arkusz jest po to, żeby za
       miesiąc dało się odtworzyć, skąd wziął się ten plik.</p>
  </div>
</div>
<div class="karta nowa" style="margin-top:18px">
  <h3>Przykład z tej prezentacji</h3>
  <p class="male" style="margin:0">Wpisuję na liście leadów
     <span class="chip"><span class="z">H</span><span class="t">Sacawa</span></span>
     i <span class="chip"><span class="z">T</span><span class="t">Zemela</span></span>
     w trybie <b>ORAZ</b> → tabela pokazuje <b class="nums">%s</b> rekordów, licznik
     pokazuje <b class="nums">%s</b>, a pobrany XLSX ma <b class="nums">%s</b> wierszy.</p>
</div>""" % (d["leady_oba"], d["leady_oba"], d["leady_oba"]))

    # ================================================================ 6
    rozdzial("6", "Granice i co dalej",
             "Uczciwie: czego tutaj nie ma i dlaczego.")

    slajd("Zakres", "Czego świadomie nie zrobiliśmy", """
<div class="cols c2">
  <div class="karta uwaga">
    <h3>Poza zakresem prototypu</h3>
    <ul class="lista male">
      <li><b>Logowania i ról.</b> Do decyzji, czy handlowcy mają się nawzajem nie widzieć.</li>
      <li><b>Wysyłki do Google Calendar.</b> Kalendarz jest tutaj, nie synchronizuje się.</li>
      <li><b>Modułu rozliczeń</b> („JEDNORAZÓWKI”, „PRZEDSZKOLA FAKTURY”).</li>
      <li><b>Pobierania RSPO przez API</b> — import jest z pliku.</li>
      <li><b>Przypominajek</b> pilnujących terminów (nic nie wysyła maili).</li>
      <li><b>Dostępności cyklicznej</b> („każdy wtorek 8–12”) i samoobsługi trenera.</li>
    </ul>
  </div>
  <div>
    <div class="karta dobra">
      <h3>Co jest gotowe i działa na Waszych danych</h3>
      <ul class="lista male">
        <li>rozdawanie leadów, statusy, terminy ostateczne, historia zmian,</li>
        <li>DT i cykle, zastępstwa i odwołania na konkretną datę,</li>
        <li>kalendarz w trzech widokach + wykrywanie kolizji,</li>
        <li>dostępność trenerów i wyliczane wolne okna,</li>
        <li>panel „Kogo wysłać?” i rejony,</li>
        <li>filtr wpisywany na wszystkich listach i na grafiku,</li>
        <li>eksport XLSX zgodny z tym, co widać.</li>
      </ul>
    </div>
    <div class="karta" style="margin-top:14px">
      <h3>Status</h3>
      <p class="male" style="margin:0">To <b>prototyp do obejrzenia i obgadania</b>,
         uruchomiony na realnym pliku — nie system produkcyjny. Celem jest ustalić,
         co zostaje, czego brakuje i co trzeba zrobić inaczej.</p>
    </div>
  </div>
</div>""")

    SLAJDY.append(("t", "Pytania", """
<section class="slide tytul" data-tytul="Pytania">
  <div class="kicker">Koniec</div>
  <h1>Co z tego zostaje, a co robimy inaczej?</h1>
  <p class="lede">Trzy pytania, na które warto odpowiedzieć dziś:<br>
     1. Czy handlowcy mają widzieć nawzajem swoje leady?<br>
     2. Czy dostępność trenerzy wpisują sobie sami?<br>
     3. Który moduł jest następny — rozliczenia czy przypomnienia o terminach?</p>
</section>"""))


# ==================================================================== zapis

def main():
    d = zbierz()
    buduj(d)

    spis = "".join(
        '<a href="#s%d" data-do="%d" class="%s"><span class="n">%02d</span>'
        '<span class="t">%s</span></a>' % (i + 1, i, "r" if typ in ("r", "t") else "",
                                           i + 1, e(tyt))
        for i, (typ, tyt, _) in enumerate(SLAJDY))

    doc = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>System Leadów — prezentacja produktu</title>
<style>%s</style>
</head>
<body>
<div class="deck">%s</div>

<div class="postep" id="postep"></div>
<div class="nawi">
  <span class="rozdz" id="tytul-nawi"></span>
  <span class="prawo">
    <button id="spis" title="klawisz O">☰ Slajdy</button>
    <button id="wstecz">←</button>
    <button id="dalej">→</button>
    <b id="licznik" class="nums"></b>
  </span>
</div>

<div class="przeglad" id="przeglad">
  <h2>SPIS SLAJDÓW — kliknij, żeby przejść (Esc zamyka)</h2>
  <div class="pg">%s</div>
</div>

<script>%s</script>
</body>
</html>""" % (CSS, "".join(h for _, _, h in SLAJDY), spis, JS)

    io.open(WYJSCIE, "w", encoding="utf-8").write(doc)
    print("Zapisano: %s" % WYJSCIE)
    print("Slajdów: %d" % len(SLAJDY))


if __name__ == "__main__":
    main()
