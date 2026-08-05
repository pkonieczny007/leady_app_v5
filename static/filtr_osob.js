/* ============================================================================
   FILTR OSÓB — chipy z wpisywanym nazwiskiem

   Zgłoszenie klienta: „rozsuwane listy z trenerami wyglądają jak filtr, ale to
   są wypełnij". Filtrować dało się tylko po handlowcu i tylko jedną wartością
   wybraną z listy; po trenerze — wcale.

   Cały stan mieści się w JEDNYM ukrytym polu `osoby`, zapisanym dokładnie tym
   samym formatem, który parsuje `repo.parsuj_osoby`. Ten plik nie filtruje
   niczego samodzielnie — dokłada/zmienia chip, przepisuje pole i wysyła
   formularz GET. Filtrowanie zostaje po stronie SQL, więc stronicowanie,
   licznik rekordów i eksport XLSX pokazują to samo, co tabela. Gdyby filtr
   działał w przeglądarce, zawężałby tylko widoczną stronę ze 150 wierszy.

   Format chipa:  [flagi][zakres:]tekst
     flagi   -  wyłączony   #  zablokowany
     zakres  o dowolna osoba · h handlowiec · t prowadzący
   ========================================================================== */
(function () {
  var box = document.getElementById('osoby-filtr');
  if (!box) return;                       // ekran bez filtra osób — nic do roboty

  var form = box.closest('form');
  var pole = document.getElementById('osoby-wartosc');
  var poleTryb = document.getElementById('osoby-tryb');
  var wpis = document.getElementById('osoby-wpis');
  var nowyZakres = document.getElementById('osoby-nowy-zakres');
  /* Zakresy zależą od ekranu: listy leadów pytają „czyj to lead" (o/h/t),
     kalendarz i dostępność — „wszystko czy nazwisko" (w/n). Serwer wypisuje
     dozwolone litery w data-zakresy, żeby nie było drugiej listy w JS. */
  var ZAKRESY = (box.dataset.zakresy || 'o').split('');
  var DOMYSLNY = box.dataset.domyslny || ZAKRESY[0];
  /* wszystkie litery znane aplikacji (także te z innych ekranów) — po to, żeby
     „x:Kowal" zostało nazwiskiem z dwukropkiem, a „t:Kowal" zakresem */
  var ZNANE = (box.dataset.wszystkie || '').split('');

  /* ogonki jak w db.pl_fold — tylko do porównywania, czy wpis już jest */
  var OGONKI = { 'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n',
                 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z' };
  function fold(s) {
    return String(s || '').toLowerCase().replace(/[ąćęłńóśźż]/g, function (z) {
      return OGONKI[z];
    });
  }

  function parsuj(s) {
    var out = [];
    String(s || '').split('|').forEach(function (kawalek) {
      var t = kawalek.trim(), wyl = false, zab = false;
      while (t && (t[0] === '-' || t[0] === '#')) {
        if (t[0] === '-') { wyl = true; } else { zab = true; }
        t = t.slice(1);
      }
      var zakres = DOMYSLNY;
      /* zakres spoza tego ekranu sprowadzamy do domyślnego — tak samo jak
         `filtry.parsuj` po stronie serwera, żeby obie strony widziały to samo */
      if (t.length >= 2 && t[1] === ':' && ZNANE.indexOf(t[0]) >= 0) {
        if (ZAKRESY.indexOf(t[0]) >= 0) zakres = t[0];
        t = t.slice(2);
      }
      t = t.trim();
      if (t) out.push({ tekst: t, zakres: zakres, wylaczony: wyl, zablokowany: zab });
    });
    return out;
  }

  function zapisz(chipy) {
    return chipy.map(function (c) {
      return (c.wylaczony ? '-' : '') + (c.zablokowany ? '#' : '') +
             c.zakres + ':' + c.tekst;
    }).join('|');
  }

  /* jedyne wyjście z tego pliku: zapisz stan i przeładuj przez GET */
  function zastosuj(chipy) {
    pole.value = zapisz(chipy);
    form.submit();
  }

  function stan() { return parsuj(pole.value); }

  function dodaj() {
    /* „|" jest separatorem zapisu, a nazwisko go nie potrzebuje */
    var tekst = (wpis.value || '').replace(/\|/g, ' ').trim();
    if (!tekst) { wpis.focus(); return; }
    var zakres = nowyZakres.value || DOMYSLNY;
    var chipy = stan();
    var juz = null;
    chipy.forEach(function (c) {
      if (c.zakres === zakres && fold(c.tekst) === fold(tekst)) juz = c;
    });
    if (juz) {
      juz.wylaczony = false;              /* powtórka nie dubluje — włącza wpis */
    } else {
      if (chipy.length >= 12) {
        window.alert('Filtr osób przyjmuje najwyżej 12 wpisów. Usuń któryś, żeby dodać nowy.');
        return;
      }
      chipy.push({ tekst: tekst, zakres: zakres, wylaczony: false, zablokowany: false });
    }
    zastosuj(chipy);
  }

  box.addEventListener('click', function (ev) {
    var przycisk = ev.target.closest('[data-akcja]');
    if (przycisk) {
      var chipy = stan();
      var c = chipy[parseInt(przycisk.dataset.i, 10)];
      if (!c) return;
      var akcja = przycisk.dataset.akcja;
      if (akcja === 'wl') {
        c.wylaczony = !c.wylaczony;
      } else if (akcja === 'lock') {
        c.zablokowany = !c.zablokowany;
      } else if (akcja === 'zakres') {
        c.zakres = ZAKRESY[(ZAKRESY.indexOf(c.zakres) + 1) % ZAKRESY.length];
      } else if (akcja === 'usun') {
        /* kłódka ma coś znaczyć także tutaj — inaczej blokada broniłaby
           tylko przed „Wyczyść", a przed przypadkowym ✕ już nie */
        if (c.zablokowany &&
            !window.confirm('Wpis „' + c.tekst + '" jest zablokowany. Usunąć mimo to?')) return;
        chipy.splice(parseInt(przycisk.dataset.i, 10), 1);
      }
      zastosuj(chipy);
      return;
    }

    var tryb = ev.target.closest('[data-tryb]');
    if (tryb) {
      poleTryb.value = tryb.dataset.tryb;
      form.submit();
      return;
    }

    if (ev.target.closest('#osoby-dodaj')) dodaj();

    if (ev.target.closest('#osoby-czysc')) {
      var zostaja = stan().filter(function (c) { return c.zablokowany; });
      zastosuj(zostaja);
    }
  });

  /* Enter w polu = dodaj chip, nie wyślij formularza z pustym wpisem */
  wpis.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      dodaj();
    }
  });

  /* Klik w podpowiedź z datalisty dokłada chip od razu — bez drugiego ruchu.
     Rozpoznajemy go po `inputType`; zwykłe pisanie ma 'insertText' i nic nie robi.
     Świadomie NIE wieszamy się na `change`: ten leci też przy wyjściu z pola,
     więc samo kliknięcie obok dokładałoby wpis, o który nikt nie prosił. */
  wpis.addEventListener('input', function (ev) {
    if (ev.inputType === 'insertReplacementText' && wpis.value) dodaj();
  });
})();
