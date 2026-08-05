# FAZA2: PH Nowy  Nad którym pracuję jako główny  .xlsx

## 1. PELNE listy walidacji (per arkusz)

### BAZA
  sqref=A4:A640
    type=list formula1="01. Sacawa,02. Olszewska,03. Małolepsza,04. Chytry,Bitner"
  sqref=T4:U330 Z4:AG330
    type=list formula1="01. Tak,02. Nie"
  sqref=Q4:Q582
    type=list formula1="01. Podsumowanie DT,02. Propozycja DT"
  sqref=C4:C640
    type=list formula1="01. Próba kontaktu (Brak konkretów),02. Próba kontaktu (czekam na termin),03. DT umówione,04. BRAK KONTAKTU ZE SZKOŁĄ"
  sqref=E4:E640
    type=list formula1="01. Orzesze,02. Mikołów,03. Łaziska Górne,04. Tychy,05. Knurów,06. Rybnik,07. Żory,08. Katowice,09. Pszczyna powiat,10. Piekary Śląskie,11. Siemianowice Śląskie,12. Świętochłowice,13. Sosnowiec,14. Dąbrowa Górnicza,15. Będzin powiat,16. Chorzów,17. Dąbrow"&"a Górnicza,18. Jaworzno,19. Zabrze,20. Ruda Śląska"
  sqref=Y4:Y330
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Bitner,19. Leś"&"niak,20. Sacawa,21. Płaszczymąka,22. Kopczyński,23. Bednarek,24. Palus,25. Adamczyk,26. Miękina,27. Bąk-Kopaniarz,28. Musiał,29. Cichoń,30. Jeziorczak,31. ,32.,33.,34.,35.,36.,37.,38.,39.,40."
  sqref=B4:B640
    type=list formula1="01. Nowa szkoła,02. Kontynuacja"
  sqref=D4:D330 M4:M378
    type=custom formula1=OR(NOT(ISERROR(DATEVALUE(D4))), AND(ISNUMBER(D4), LEFT(CELL("format", D4))="D"))
  sqref=O4:O543
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Młynarczyk Ada"&"m,19. Leśniak,20. Trener 1,21. Trener 2,22. Trene 3,23. Trener 4,24. Trener 5"
  sqref=V4:V330
    type=list formula1="poniedziałek,wtorek,środa,czwartek,piątek,sobota"
  sqref=L4:L579
    type=list formula1="01. Tak,02. Do ustalenia"

### Niewykorzystane rekordy
  sqref=D2:D327
    type=custom formula1=OR(NOT(ISERROR(DATEVALUE(D2))), AND(ISNUMBER(D2), LEFT(CELL("format", D2))="D"))

### Szkoły z DT
  sqref=D2:D327
    type=custom formula1=OR(NOT(ISERROR(DATEVALUE(D2))), AND(ISNUMBER(D2), LEFT(CELL("format", D2))="D"))

### Sacawa
  sqref=E14:E200
    type=list formula1="01. Orzesze,02. Mikołów,03. Łaziska Górne,04. Tychy,05. Knurów,06. Rybnik,07. Żory,08. Katowice Południe,09. Pszczyna,10. Katowice,11. Zabrze,12. Ruda Śląska,13. Świętochłowice,14. Siemianowice Śląskie,15. Piekary Śląskie,16. Dąbrowa Górnicza,17. Sosnowie"&"c,18. Jaworzno,19. Chorzow,20. Ornontowice,21. Wyry,22. Gostyń"
  sqref=C4:C200
    type=list formula1="01. Próba kontaktu (Brak konkretów),02. Próba kontaktu (czekam na termin),03. DT umówione,04. BRAK KONTAKTU ZE SZKOŁĄ"
  sqref=O4:O15 Y4:Y200
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Bitner,19. Leś"&"niak,20. Sacawa,21. Płaszczymąka,22. Kopczyński,23. Bednarek,24. Palus,25. Adamczyk,26. Miękina,27. Bąk-Kopaniarz,28. Musiał,29. Cichoń,30. Jeziorczak,31. ,32.,33.,34.,35.,36.,37.,38.,39.,40."
  sqref=E4:E13
    type=list formula1="01. Orzesze,02. Mikołów,03. Łaziska Górne,04. Tychy,05. Knurów,06. Rybnik,07. Żory,08. Katowice,09. Pszczyna,10. Piekary Śląskie,11. Siemianowice Śląskie,12. Świętochłowice,13. Sosnowiec,14. Dąbrowa Górnicza,15. Będzin,16. Chorzów,17. Dąbrowa Górnicza,18."&" Jaworzno,19. Zabrze,20. Ruda Śląska,21. Strzyzowice"
  sqref=O16:O200
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Młynarczyk Ada"&"m,19. Leśniak,20. Trener 1,21. Trener 2,22. Trene 3,23. Trener 4,24. Trener 5"
  sqref=A20:A200
    type=list formula1="01. Sacawa,02. Olaszewska,03. Małolepsza,04. Chytry,05. Młynarczyk"
  sqref=T4:U200 Z4:AG200
    type=list formula1="01. Tak,02. Nie"
  sqref=Q4:Q200
    type=list formula1="01. Podsumowanie DT,02. Propozycja DT"
  sqref=B4:B200
    type=list formula1="01. Nowa szkoła,02. Kontynuacja"
  sqref=A4:A19
    type=list formula1="01. Sacawa,02. Olszewska,03. Małolepsza,04. Chytry"
  sqref=D4:D342 K28:K32 L343:M390 M4:M342 O343:O390
    type=custom formula1=OR(NOT(ISERROR(DATEVALUE(D4))), AND(ISNUMBER(D4), LEFT(CELL("format", D4))="D"))
  sqref=V4:V200
    type=list formula1="poniedziałek,wtorek,środa,czwartek,piątek,sobota"
  sqref=L4:L200
    type=list formula1="01. Tak,02. Do ustalenia"

### Olszewska
  sqref=T4:U340 Z4:AF340
    type=list formula1="01. Tak,02. Nie"
  sqref=Q4:Q340
    type=list formula1="01. Podsumowanie DT,02. Propozycja DT"
  sqref=C4:C340
    type=list formula1="01. Próba kontaktu (Brak konkretów),02. Próba kontaktu (czekam na termin),03. DT umówione,04. BRAK KONTAKTU ZE SZKOŁĄ"
  sqref=O4:O388
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Bitner,19. Leś"&"niak,20. Sacawa,21. Płaszczymąka,22. Kopczyński,23. Bednarek,24. Palus,25. Adamczyk,26. Miękina,27. Bąk-Kopaniarz,28. Musiał,29. Cichoń,30. Jeziorczak,31. ,32.,33.,34.,35.,36.,37.,38.,39.,40."
  sqref=B4:B340
    type=list formula1="01. Nowa szkoła,02. Kontynuacja"
  sqref=A29:A340
    type=list formula1="01. Sacawa,02. Olaszewska,03. Małolepsza,04. Chytry"
  sqref=A4:A28
    type=list formula1="01. Sacawa,02. Olszewska,03. Małolepsza,04. Chytry"
  sqref=D4:D340 L341:M388 M4:M340 O389
    type=custom formula1=OR(NOT(ISERROR(DATEVALUE(D4))), AND(ISNUMBER(D4), LEFT(CELL("format", D4))="D"))
  sqref=E4:E366
    type=list formula1="01. Orzesze,02. Mikołów,03. Łaziska Górne,04. Tychy,05. Knurów,06. Rybnik,07. Żory,08. Katowice,09. Pszczyna,10. Piekary Śląskie,11. Siemianowice Śląskie,12. Świętochłowice,13. Sosnowiec,14. Dąbrowa Górnicza,15. Będzin,16. Chorzów,17. Dąbrowa Górnicza,18."&" Jaworzno,19. Zabrze,20. Ruda Śląska,21. Strzyzowice"
  sqref=V4:V340
    type=list formula1="poniedziałek,wtorek,środa,czwartek,piątek,sobota"
  sqref=L4:L340
    type=list formula1="01. Tak,02. Do ustalenia"
  sqref=Y4:Y340
    type=list formula1="01. Olszewska Zuza,02. Sacawa Dominika,03. Zemela Paulina"

### Małolepsza
  sqref=T4:U342 Z4:AG342
    type=list formula1="01. Tak,02. Nie"
  sqref=Q4:Q342
    type=list formula1="01. Podsumowanie DT,02. Propozycja DT"
  sqref=C4:C342
    type=list formula1="01. Próba kontaktu (Brak konkretów),02. Próba kontaktu (czekam na termin),03. DT umówione,04. BRAK KONTAKTU ZE SZKOŁĄ"
  sqref=Y4:Y342
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Bitner,19. Leś"&"niak,20. Sacawa,21. Płaszczymąka,22. Kopczyński,23. Bednarek,24. Palus,25. Adamczyk,26. Miękina,27. Bąk-Kopaniarz,28. Musiał,29. Cichoń,30. Jeziorczak,31. ,32.,33.,34.,35.,36.,37.,38.,39.,40."
  sqref=B4:B342
    type=list formula1="01. Nowa szkoła,02. Kontynuacja"
  sqref=A4:A392
    type=list formula1="01. Sacawa,02. Olszewska,03. Małolepsza,04. Chytry"
  sqref=D4:D342 L343:M390 M4:M342 O343:O390
    type=custom formula1=OR(NOT(ISERROR(DATEVALUE(D4))), AND(ISNUMBER(D4), LEFT(CELL("format", D4))="D"))
  sqref=E4:E348
    type=list formula1="01. Orzesze,02. Mikołów,03. Łaziska Górne,04. Tychy,05. Knurów,06. Rybnik,07. Żory,08. Katowice,09. Pszczyna,10. Piekary Śląskie,11. Siemianowice Śląskie,12. Świętochłowice,13. Sosnowiec,14. Dąbrowa Górnicza,15. Będzin,16. Chorzów,17. Dąbrowa Górnicza,18."&" Jaworzno,19. Zabrze,20. Ruda Śląska,21. Strzyzowice"
  sqref=O4:O342
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Młynarczyk Ada"&"m,19. Leśniak,20. Trener 1,21. Trener 2,22. Trene 3,23. Trener 4,24. Trener 5"
  sqref=V4:V342
    type=list formula1="poniedziałek,wtorek,środa,czwartek,piątek,sobota"
  sqref=L4:L342
    type=list formula1="01. Tak,02. Do ustalenia"

### Chytry
  sqref=T4:U342 Z4:AG342
    type=list formula1="01. Tak,02. Nie"
  sqref=Q4:Q342
    type=list formula1="01. Podsumowanie DT,02. Propozycja DT"
  sqref=C4:C342
    type=list formula1="01. Próba kontaktu (Brak konkretów),02. Próba kontaktu (czekam na termin),03. DT umówione,04. BRAK KONTAKTU ZE SZKOŁĄ"
  sqref=Y4:Y342
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Bitner,19. Leś"&"niak,20. Sacawa,21. Płaszczymąka,22. Kopczyński,23. Bednarek,24. Palus,25. Adamczyk,26. Miękina,27. Bąk-Kopaniarz,28. Musiał,29. Cichoń,30. Jeziorczak,31. ,32.,33.,34.,35.,36.,37.,38.,39.,40."
  sqref=B4:B342
    type=list formula1="01. Nowa szkoła,02. Kontynuacja"
  sqref=A4:A389
    type=list formula1="01. Sacawa,02. Olszewska,03. Małolepsza,04. Chytry"
  sqref=D4:D342 L343:M390 M4:M342 O343:O390
    type=custom formula1=OR(NOT(ISERROR(DATEVALUE(D4))), AND(ISNUMBER(D4), LEFT(CELL("format", D4))="D"))
  sqref=E4:E394
    type=list formula1="01. Orzesze,02. Mikołów,03. Łaziska Górne,04. Tychy,05. Knurów,06. Rybnik,07. Żory,08. Katowice,09. Pszczyna,10. Piekary Śląskie,11. Siemianowice Śląskie,12. Świętochłowice,13. Sosnowiec,14. Dąbrowa Górnicza,15. Będzin,16. Chorzów,17. Dąbrowa Górnicza,18."&" Jaworzno,19. Zabrze,20. Ruda Śląska,21. Strzyzowice"
  sqref=O4:O342
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Młynarczyk Ada"&"m,19. Leśniak,20. Trener 1,21. Trener 2,22. Trene 3,23. Trener 4,24. Trener 5"
  sqref=V4:V342
    type=list formula1="poniedziałek,wtorek,środa,czwartek,piątek,sobota"
  sqref=L4:L342
    type=list formula1="01. Tak,02. Do ustalenia"

### Młynarczyk
  sqref=T4:U342 Z4:AG342
    type=list formula1="01. Tak,02. Nie"
  sqref=Q4:Q342
    type=list formula1="01. Podsumowanie DT,02. Propozycja DT"
  sqref=C4:C342
    type=list formula1="01. Próba kontaktu (Brak konkretów),02. Próba kontaktu (czekam na termin),03. DT umówione,04. BRAK KONTAKTU ZE SZKOŁĄ"
  sqref=Y4:Y342
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Bitner,19. Leś"&"niak,20. Sacawa,21. Płaszczymąka,22. Kopczyński,23. Bednarek,24. Palus,25. Adamczyk,26. Miękina,27. Bąk-Kopaniarz,28. Musiał,29. Cichoń,30. Jeziorczak,31. ,32.,33.,34.,35.,36.,37.,38.,39.,40."
  sqref=B4:B342
    type=list formula1="01. Nowa szkoła,02. Kontynuacja"
  sqref=A4:A382
    type=list formula1="01. Sacawa,02. Olszewska,03. Małolepsza,04. Chytry"
  sqref=D4:D342 L343:M390 M4:M342 O343:O390
    type=custom formula1=OR(NOT(ISERROR(DATEVALUE(D4))), AND(ISNUMBER(D4), LEFT(CELL("format", D4))="D"))
  sqref=E4:E383
    type=list formula1="01. Orzesze,02. Mikołów,03. Łaziska Górne,04. Tychy,05. Knurów,06. Rybnik,07. Żory,08. Katowice,09. Pszczyna,10. Piekary Śląskie,11. Siemianowice Śląskie,12. Świętochłowice,13. Sosnowiec,14. Dąbrowa Górnicza,15. Będzin,16. Chorzów,17. Dąbrowa Górnicza,18."&" Jaworzno,19. Zabrze,20. Ruda Śląska,21. Strzyzowice"
  sqref=O4:O342
    type=list formula1="01. Małolepsza,02. Olszewska,03. Majewska,04. Zemela,05. Polakowska,06. Jankowska,07. Krzysztofik,08. Brzozowska,09. Bochniarz,10. Łukaszek,11. Białas (Pszczyna),12. Jasińska Nina,13. Cebula,14. Swoboda,15. Gawron,16. Król,17. Paziewski,18. Młynarczyk Ada"&"m,19. Leśniak,20. Trener 1,21. Trener 2,22. Trene 3,23. Trener 4,24. Trener 5"
  sqref=V4:V342
    type=list formula1="poniedziałek,wtorek,środa,czwartek,piątek,sobota"
  sqref=L4:L342
    type=list formula1="01. Tak,02. Do ustalenia"


## 1b. Unikalne listy (deduplikacja)

LISTA 1 (n=5)  uzyta w: BAZA!A4:A640
   - 01. Sacawa
   - 02. Olszewska
   - 03. Małolepsza
   - 04. Chytry
   - Bitner

LISTA 2 (n=2)  uzyta w: BAZA!T4:U330 Z4:AG330; Sacawa!T4:U200 Z4:AG200; Olszewska!T4:U340 Z4:AF340; Małolepsza!T4:U342 Z4:AG342; Chytry!T4:U342 Z4:AG342; Młynarczyk!T4:U342 Z4:AG342
   - 01. Tak
   - 02. Nie

LISTA 3 (n=2)  uzyta w: BAZA!Q4:Q582; Sacawa!Q4:Q200; Olszewska!Q4:Q340; Małolepsza!Q4:Q342; Chytry!Q4:Q342; Młynarczyk!Q4:Q342
   - 01. Podsumowanie DT
   - 02. Propozycja DT

LISTA 4 (n=4)  uzyta w: BAZA!C4:C640; Sacawa!C4:C200; Olszewska!C4:C340; Małolepsza!C4:C342; Chytry!C4:C342; Młynarczyk!C4:C342
   - 01. Próba kontaktu (Brak konkretów)
   - 02. Próba kontaktu (czekam na termin)
   - 03. DT umówione
   - 04. BRAK KONTAKTU ZE SZKOŁĄ

LISTA 5 (n=20)  uzyta w: BAZA!E4:E640
   - 01. Orzesze
   - 02. Mikołów
   - 03. Łaziska Górne
   - 04. Tychy
   - 05. Knurów
   - 06. Rybnik
   - 07. Żory
   - 08. Katowice
   - 09. Pszczyna powiat
   - 10. Piekary Śląskie
   - 11. Siemianowice Śląskie
   - 12. Świętochłowice
   - 13. Sosnowiec
   - 14. Dąbrowa Górnicza
   - 15. Będzin powiat
   - 16. Chorzów
   - 17. Dąbrow"&"a Górnicza
   - 18. Jaworzno
   - 19. Zabrze
   - 20. Ruda Śląska

LISTA 6 (n=40)  uzyta w: BAZA!Y4:Y330; Sacawa!O4:O15 Y4:Y200; Olszewska!O4:O388; Małolepsza!Y4:Y342; Chytry!Y4:Y342; Młynarczyk!Y4:Y342
   - 01. Małolepsza
   - 02. Olszewska
   - 03. Majewska
   - 04. Zemela
   - 05. Polakowska
   - 06. Jankowska
   - 07. Krzysztofik
   - 08. Brzozowska
   - 09. Bochniarz
   - 10. Łukaszek
   - 11. Białas (Pszczyna)
   - 12. Jasińska Nina
   - 13. Cebula
   - 14. Swoboda
   - 15. Gawron
   - 16. Król
   - 17. Paziewski
   - 18. Bitner
   - 19. Leś"&"niak
   - 20. Sacawa
   - 21. Płaszczymąka
   - 22. Kopczyński
   - 23. Bednarek
   - 24. Palus
   - 25. Adamczyk
   - 26. Miękina
   - 27. Bąk-Kopaniarz
   - 28. Musiał
   - 29. Cichoń
   - 30. Jeziorczak
   - 31. 
   - 32.
   - 33.
   - 34.
   - 35.
   - 36.
   - 37.
   - 38.
   - 39.
   - 40.

LISTA 7 (n=2)  uzyta w: BAZA!B4:B640; Sacawa!B4:B200; Olszewska!B4:B340; Małolepsza!B4:B342; Chytry!B4:B342; Młynarczyk!B4:B342
   - 01. Nowa szkoła
   - 02. Kontynuacja

LISTA 8 (n=24)  uzyta w: BAZA!O4:O543; Sacawa!O16:O200; Małolepsza!O4:O342; Chytry!O4:O342; Młynarczyk!O4:O342
   - 01. Małolepsza
   - 02. Olszewska
   - 03. Majewska
   - 04. Zemela
   - 05. Polakowska
   - 06. Jankowska
   - 07. Krzysztofik
   - 08. Brzozowska
   - 09. Bochniarz
   - 10. Łukaszek
   - 11. Białas (Pszczyna)
   - 12. Jasińska Nina
   - 13. Cebula
   - 14. Swoboda
   - 15. Gawron
   - 16. Król
   - 17. Paziewski
   - 18. Młynarczyk Ada"&"m
   - 19. Leśniak
   - 20. Trener 1
   - 21. Trener 2
   - 22. Trene 3
   - 23. Trener 4
   - 24. Trener 5

LISTA 9 (n=6)  uzyta w: BAZA!V4:V330; Sacawa!V4:V200; Olszewska!V4:V340; Małolepsza!V4:V342; Chytry!V4:V342; Młynarczyk!V4:V342
   - poniedziałek
   - wtorek
   - środa
   - czwartek
   - piątek
   - sobota

LISTA 10 (n=2)  uzyta w: BAZA!L4:L579; Sacawa!L4:L200; Olszewska!L4:L340; Małolepsza!L4:L342; Chytry!L4:L342; Młynarczyk!L4:L342
   - 01. Tak
   - 02. Do ustalenia

LISTA 11 (n=22)  uzyta w: Sacawa!E14:E200
   - 01. Orzesze
   - 02. Mikołów
   - 03. Łaziska Górne
   - 04. Tychy
   - 05. Knurów
   - 06. Rybnik
   - 07. Żory
   - 08. Katowice Południe
   - 09. Pszczyna
   - 10. Katowice
   - 11. Zabrze
   - 12. Ruda Śląska
   - 13. Świętochłowice
   - 14. Siemianowice Śląskie
   - 15. Piekary Śląskie
   - 16. Dąbrowa Górnicza
   - 17. Sosnowie"&"c
   - 18. Jaworzno
   - 19. Chorzow
   - 20. Ornontowice
   - 21. Wyry
   - 22. Gostyń

LISTA 12 (n=21)  uzyta w: Sacawa!E4:E13; Olszewska!E4:E366; Małolepsza!E4:E348; Chytry!E4:E394; Młynarczyk!E4:E383
   - 01. Orzesze
   - 02. Mikołów
   - 03. Łaziska Górne
   - 04. Tychy
   - 05. Knurów
   - 06. Rybnik
   - 07. Żory
   - 08. Katowice
   - 09. Pszczyna
   - 10. Piekary Śląskie
   - 11. Siemianowice Śląskie
   - 12. Świętochłowice
   - 13. Sosnowiec
   - 14. Dąbrowa Górnicza
   - 15. Będzin
   - 16. Chorzów
   - 17. Dąbrowa Górnicza
   - 18."&" Jaworzno
   - 19. Zabrze
   - 20. Ruda Śląska
   - 21. Strzyzowice

LISTA 13 (n=5)  uzyta w: Sacawa!A20:A200
   - 01. Sacawa
   - 02. Olaszewska
   - 03. Małolepsza
   - 04. Chytry
   - 05. Młynarczyk

LISTA 14 (n=4)  uzyta w: Sacawa!A4:A19; Olszewska!A4:A28; Małolepsza!A4:A392; Chytry!A4:A389; Młynarczyk!A4:A382
   - 01. Sacawa
   - 02. Olszewska
   - 03. Małolepsza
   - 04. Chytry

LISTA 15 (n=4)  uzyta w: Olszewska!A29:A340
   - 01. Sacawa
   - 02. Olaszewska
   - 03. Małolepsza
   - 04. Chytry

LISTA 16 (n=3)  uzyta w: Olszewska!Y4:Y340
   - 01. Olszewska Zuza
   - 02. Sacawa Dominika
   - 03. Zemela Paulina


## 2. Pelne formuly kluczowych komorek

### Zbiorczy!A2
=IFERROR(__xludf.DUMMYFUNCTION("VSTACK( FILTER(Sacawa!A2:Y1075, Sacawa!A2:A1075<>""""), FILTER(Olszewska!A2:Y1075, Olszewska!A2:A1075<>""""), FILTER('Małolepsza'!A2:Y1075, 'Małolepsza'!A2:A1075<>""""), FILTER(Chytry!A2:Y1075, Chytrychi!A2:A1075<>""""), FILTER('Młynarczyk'!A2:Y1075, 'Mły"&"narczyk'!A2:A1075<>"""") )"),"01. Sacawa")

### Zbiorczy!AG2  [ARRAY ref=AG2:AG1075]
=MAP(A2:A1075, B2:B1075, E2:E1075, F2:F1075, G2:G1075, H2:H1075, I2:I1075, N2:N1075, P2:P1075, R2:R1075, S2:S1075, LAMBDA(a,b,e,f,g,h,i,n,p,r,s, IF(a="", "", "Handlowiec: " & a & CHAR(10) & "Status szkoły: " & b & CHAR(10) & "Miejscowość: " & e & CHAR(10) & "Numer placówki: " & f & CHAR(10) & "Adres placówki: " & g & CHAR(10) & "Osoby decyzyjne i kontakt: " & h & CHAR(10) & "Numer telefonu: " & i & CHAR(10) & "Godzina DT: " & IF(n="", "", TEXT(n, "hh:mm")) & CHAR(10) & "Numer sali DT: " & p & CHAR(10) & "Ilość klas 1-4: " & r & CHAR(10) & "Ilość dzieci w klasach: " & s )))

### Zbiorczy!AG3
Handlowiec: 01. Sacawa
Status szkoły: 02. Kontynuacja
Miejscowość: 05. Knurów
Numer placówki: MSP 2
Adres placówki: Thomasa Woodrowa Wilsona 22
Osoby decyzyjne i kontakt: Joanna Kucyniak
Numer telefonu: 32 235 27 27
Godzina DT: 08:55
Numer sali DT: 
Ilość klas 1-4: 12 klas
Ilość dzieci w klasach: około 240

### Zbiorczy!AH2
=M2&"-"&O2

### Zbiorczy!AI2  [ARRAY ref=AI2:AI1075]
=MAP(M2:M1075, O2:O1075, LAMBDA(d, t, IF(AND(d="", t=""), "", TEXT(d, "dd.mm.yyyy") & "||" & t)))

### Niewykorzystane rekordy!A2
=IFERROR(__xludf.DUMMYFUNCTION("QUERY({Sacawa!A2:Y984; Olszewska!A2:Y984; 'Małolepsza'!A2:Y984; Chytry!A2:Y984}, ""SELECT * WHERE Col1 IS NOT NULL AND Col3 = '04. BRAK KONTAKTU ZE SZKOŁĄ'"", 0)"),"#N/A")

### Szkoły z DT!A2
=IFERROR(__xludf.DUMMYFUNCTION("QUERY({Sacawa!A2:Y1000; Olszewska!A2:Y1000; 'Małolepsza'!A2:Y1000; Chytry!A2:Y1000}, ""SELECT * WHERE Col1 IS NOT NULL AND Col12 = '01. Tak'"", 0)"),"01. Sacawa")

### Szkoły z cyklami!A2
=IFERROR(__xludf.DUMMYFUNCTION("QUERY({Sacawa!A2:Y1000; Olszewska!A2:Y1000; 'Małolepsza'!A2:Y1000; Chytry!A2:Y1000}, ""SELECT * WHERE Col1 IS NOT NULL AND Col21 = '01. Tak'"", 0)"),"01. Sacawa")

### Kalendarz WRZESIEŃ DT!B3  [ARRAY ref=B3]
=IFERROR(XLOOKUP(TEXT(B$2, "dd.mm.yyyy") & "||" & $A3, Zbiorczy!$AI$2:$AI$1100, Zbiorczy!$AG$2:$AG$1100), "")

### Kalendarz WRZESIEŃ DT!B4  [ARRAY ref=B4]
=IFERROR(XLOOKUP(TEXT(B$2, "dd.mm.yyyy") & "||" & $A4, Zbiorczy!$AI$2:$AI$1100, Zbiorczy!$AG$2:$AG$1100), "")

### Kalendarz WRZESIEŃ DT!I3  [ARRAY ref=I3]
=IFERROR(XLOOKUP(TEXT(I$2, "dd.mm.yyyy") & "||" & $A3, Zbiorczy!$AI$2:$AI$1100, Zbiorczy!$AG$2:$AG$1100), "")

### Kalendarz WRZESIEŃ DT!B50
=IFERROR(__xludf.DUMMYFUNCTION("IFERROR(TEXTJOIN(CHAR(10) & ""--------------------"" & CHAR(10), PRAWDZIWE, FILTER(Zbiorczy!$AG:$AG, Zbiorczy!$AI:$AI = TEXT(B$2, ""dd.mm.yyyy"") & ""||"" & $A50)), """")"),"")

### Kalendarz PAŹDZIERNIK DT!B3  [ARRAY ref=B3]
=IFERROR(XLOOKUP(TEXT(B$2, "dd.mm.yyyy") & "||" & $A3, Zbiorczy!$AI$2:$AI$1100, Zbiorczy!$AG$2:$AG$1100), "")

### Kalendarz LISTOPAD DT!B3  [ARRAY ref=B3]
=IFERROR(XLOOKUP(TEXT(B$2, "dd.mm.yyyy") & "||" & $A3, Zbiorczy!$AI$2:$AI$1100, Zbiorczy!$AG$2:$AG$1100), "")

### BAZA!A2
None

### BAZA!I4
="601290441"

### Sacawa!A2
None

### Sacawa!B2
None


## 3. Kalendarze - struktura

### Kalendarz WRZESIEŃ DT  (dim=A1:BI1019)
  R1: [('B1', 'Poniedziałek'), ('C1', 'Wtorek'), ('D1', 'Środa'), ('E1', 'Czwartek'), ('F1', 'Piątek'), ('I1', 'Poniedziałek'), ('J1', 'Wtorek'), ('K1', 'Środa'), ('L1', 'Czwartek'), ('M1', 'Piątek'), ('P1', 'Poniedziałek'), ('Q1', 'Wtorek'), ('R1', 'Środa'), ('S1', 'Czwartek'), ('T1', 'Piątek'), ('W1', 'Poniedziałek'), ('X1', 'Wtorek'), ('Y1', 'Środa'), ('Z1', 'Czwartek'), ('AA1', 'Piątek'), ('AD1', 'Poniedziałek'), ('AE1', 'Wtorek'), ('AF1', 'Środa')]
  R2: [('B2', datetime.datetime(2026, 8, 31, 0, 0)), ('C2', '=B2+1'), ('D2', '=C2+1'), ('E2', '=D2+1'), ('F2', '=E2+1'), ('I2', datetime.datetime(2026, 9, 7, 0, 0)), ('J2', '=I2+1'), ('K2', '=J2+1'), ('L2', '=K2+1'), ('M2', '=L2+1'), ('P2', datetime.datetime(2026, 9, 14, 0, 0)), ('Q2', '=P2+1'), ('R2', '=Q2+1'), ('S2', '=R2+1'), ('T2', '=S2+1'), ('W2', datetime.datetime(2026, 9, 21, 0, 0)), ('X2', '=W2+1'), ('Y2', '=X2+1'), ('Z2', '=Y2+1'), ('AA2', '=Z2+1'), ('AD2', datetime.datetime(2026, 9, 28, 0, 0)), ('AE2', '=AD2+1'), ('AF2', '=AE2+1')]
  Kolumna A (trenerzy) n=23:
     A3 = 01. Małolepsza
     A4 = 02. Olszewska
     A5 = 03. Majewska
     A6 = 04. Zemela
     A7 = 05. Polakowska
     A8 = 06. Jankowska
     A9 = 07. Krzysztofik
     A10 = 08. Brzozowska
     A11 = 09. Bochniarz
     A12 = 10. Łukaszek
     A13 = 11. Białass (Pszczyna)
     A14 = 12. Jasińska Nina
     A15 = 13. Cebula
     A16 = 14. Swoboda
     A17 = 15. Gawron
     A18 = 16. Król
     A19 = 17. Paziewski
     A20 = 18. Młynarczyk Adam
     A21 = 19. Leśniak
     A22 = 20. Trener 1
     A23 = 21. Trener 3
     A24 = 22. Trener 4
     A25 = 23. Trenner 5
  Formatowanie warunkowe:
     sqref=A3:F373 H3:M373 O3:T373 V3:AA373 AC3:AF373 type=expression formula=['$A3="01. Małolepsza"'] -> fill=FFFF00FF
     sqref=A3:F373 H3:M373 O3:T373 V3:AA373 AC3:AF373 type=expression formula=['$A3="02. Olszewska"'] -> fill=FFFF9900
     sqref=A3:A140 B3:F345 H3:H140 I3:M345 O3:O140 P3:T345 V3:V140 W3:A type=expression formula=['$A3="03. Majewska"'] -> fill=FF00FF00
     sqref=A3:A253 B3:F345 H3:H253 I3:M345 O3:O253 P3:T345 V3:V253 W3:A type=expression formula=['$A3="04. Zemela"'] -> fill=FFB7E1CD

### Kalendarz PAŹDZIERNIK DT  (dim=A1:AH1019)
  R1: [('B1', 'Poniedziałek'), ('C1', 'Wtorek'), ('D1', 'Środa'), ('E1', 'Czwartek'), ('F1', 'Piątek'), ('I1', 'Poniedziałek'), ('J1', 'Wtorek'), ('K1', 'Środa'), ('L1', 'Czwartek'), ('M1', 'Piątek'), ('P1', 'Poniedziałek'), ('Q1', 'Wtorek'), ('R1', 'Środa'), ('S1', 'Czwartek'), ('T1', 'Piątek'), ('W1', 'Poniedziałek'), ('X1', 'Wtorek'), ('Y1', 'Środa'), ('Z1', 'Czwartek'), ('AA1', 'Piątek'), ('AD1', 'Poniedziałek'), ('AE1', 'Wtorek'), ('AF1', 'Środa'), ('AG1', 'Czwartek'), ('AH1', 'Piątek')]
  R2: [('B2', datetime.datetime(2026, 9, 28, 0, 0)), ('C2', '=B2+1'), ('D2', '=C2+1'), ('E2', '=D2+1'), ('F2', '=E2+1'), ('I2', datetime.datetime(2026, 10, 5, 0, 0)), ('J2', '=I2+1'), ('K2', '=J2+1'), ('L2', '=K2+1'), ('M2', '=L2+1'), ('P2', datetime.datetime(2026, 10, 12, 0, 0)), ('Q2', '=P2+1'), ('R2', '=Q2+1'), ('S2', '=R2+1'), ('T2', '=S2+1'), ('W2', datetime.datetime(2026, 10, 19, 0, 0)), ('X2', '=W2+1'), ('Y2', '=X2+1'), ('Z2', '=Y2+1'), ('AA2', '=Z2+1'), ('AD2', datetime.datetime(2026, 10, 26, 0, 0)), ('AE2', '=AD2+1'), ('AF2', '=AE2+1'), ('AG2', '=AF2+1'), ('AH2', '=AG2+1')]
  Kolumna A (trenerzy) n=23:
     A3 = 01. Małolepsza
     A4 = 02. Olszewska
     A5 = 03. Majewska
     A6 = 04. Zemela
     A7 = 05. Polakowska
     A8 = 06. Jankowska
     A9 = 07. Krzysztofik
     A10 = 08. Brzozowska
     A11 = 09. Bochniarz
     A12 = 10. Łukaszek
     A13 = 11. Białass (Pszczyna)
     A14 = 12. Jasińska Nina
     A15 = 13. Cebula
     A16 = 14. Swoboda
     A17 = 15. Gawron
     A18 = 16. Król
     A19 = 17. Paziewski
     A20 = 18. Młynarczyk Adam
     A21 = 19. Leśniak
     A22 = 20. Trener 1
     A23 = 21. Trener 3
     A24 = 22. Trener 4
     A25 = 23. Trenner 5
  Formatowanie warunkowe:
     sqref=A3:F373 H3:M373 O3:T25 V3:AA25 AC3:AH25 type=expression formula=['$A3="01. Małolepsza"'] -> fill=FFFF00FF
     sqref=A3:F373 H3:M373 O3:T25 V3:AA25 AC3:AH25 type=expression formula=['$A3="02. Olszewska"'] -> fill=FFFF9900
     sqref=A3:A140 B3:F345 H3:H140 I3:M345 O3:T25 V3:AA25 AC3:AH25 type=expression formula=['$A3="03. Majewska"'] -> fill=FF00FF00
     sqref=A3:A253 B3:F345 H3:H253 I3:M345 O3:T25 V3:AA25 AC3:AH25 type=expression formula=['$A3="04. Zemela"'] -> fill=FFB7E1CD

### Kalendarz LISTOPAD DT  (dim=A1:AD1019)
  R1: [('B1', 'Poniedziałek'), ('C1', 'Wtorek'), ('D1', 'Środa'), ('E1', 'Czwartek'), ('F1', 'Piątek'), ('I1', 'Poniedziałek'), ('J1', 'Wtorek'), ('K1', 'Środa'), ('L1', 'Czwartek'), ('M1', 'Piątek'), ('P1', 'Poniedziałek'), ('Q1', 'Wtorek'), ('R1', 'Środa'), ('S1', 'Czwartek'), ('T1', 'Piątek'), ('W1', 'Poniedziałek'), ('X1', 'Wtorek'), ('Y1', 'Środa'), ('Z1', 'Czwartek'), ('AA1', 'Piątek'), ('AD1', 'Poniedziałek')]
  R2: [('B2', datetime.datetime(2026, 11, 2, 0, 0)), ('C2', '=B2+1'), ('D2', '=C2+1'), ('E2', '=D2+1'), ('F2', '=E2+1'), ('I2', datetime.datetime(2026, 11, 9, 0, 0)), ('J2', '=I2+1'), ('K2', '=J2+1'), ('L2', '=K2+1'), ('M2', '=L2+1'), ('P2', datetime.datetime(2026, 11, 16, 0, 0)), ('Q2', '=P2+1'), ('R2', '=Q2+1'), ('S2', '=R2+1'), ('T2', '=S2+1'), ('W2', datetime.datetime(2026, 11, 23, 0, 0)), ('X2', '=W2+1'), ('Y2', '=X2+1'), ('Z2', '=Y2+1'), ('AA2', '=Z2+1'), ('AD2', datetime.datetime(2026, 11, 30, 0, 0))]
  Kolumna A (trenerzy) n=23:
     A3 = 01. Małolepsza
     A4 = 02. Olszewska
     A5 = 03. Majewska
     A6 = 04. Zemela
     A7 = 05. Polakowska
     A8 = 06. Jankowska
     A9 = 07. Krzysztofik
     A10 = 08. Brzozowska
     A11 = 09. Bochniarz
     A12 = 10. Łukaszek
     A13 = 11. Białass (Pszczyna)
     A14 = 12. Jasińska Nina
     A15 = 13. Cebula
     A16 = 14. Swoboda
     A17 = 15. Gawron
     A18 = 16. Król
     A19 = 17. Paziewski
     A20 = 18. Młynarczyk Adam
     A21 = 19. Leśniak
     A22 = 20. Trener 1
     A23 = 21. Trener 3
     A24 = 22. Trener 4
     A25 = 23. Trenner 5
  Formatowanie warunkowe:
     sqref=A3:A373 B3:F25 B28:F373 H3:M25 O3:T25 V3:AA25 AC3:AD25 type=expression formula=['$A3="01. Małolepsza"'] -> fill=FFFF00FF
     sqref=A3:A373 B3:F25 B28:F373 H3:M25 O3:T25 V3:AA25 AC3:AD25 type=expression formula=['$A3="02. Olszewska"'] -> fill=FFFF9900
     sqref=A3:A140 B3:F25 B28:F345 H3:M25 O3:T25 V3:AA25 AC3:AD25 type=expression formula=['$A3="03. Majewska"'] -> fill=FF00FF00
     sqref=A3:A253 B3:F25 B28:F345 H3:M25 O3:T25 V3:AA25 AC3:AD25 type=expression formula=['$A3="04. Zemela"'] -> fill=FFB7E1CD

### Kalendarz GRUDZIEŃ DT  (dim=A1:G1019)
  R1: [('B1', 'Poniedziałek'), ('C1', 'Wtorek'), ('D1', 'Środa'), ('E1', 'Czwartek'), ('F1', 'Piątek')]
  R2: [('B2', datetime.datetime(2026, 11, 30, 0, 0)), ('C2', '=B2+1'), ('D2', '=C2+1'), ('E2', '=D2+1'), ('F2', '=E2+1')]
  Kolumna A (trenerzy) n=23:
     A3 = 01. Małolepsza
     A4 = 02. Olszewska
     A5 = 03. Majewska
     A6 = 04. Zemela
     A7 = 05. Polakowska
     A8 = 06. Jankowska
     A9 = 07. Krzysztofik
     A10 = 08. Brzozowska
     A11 = 09. Bochniarz
     A12 = 10. Łukaszek
     A13 = 11. Białass (Pszczyna)
     A14 = 12. Jasińska Nina
     A15 = 13. Cebula
     A16 = 14. Swoboda
     A17 = 15. Gawron
     A18 = 16. Król
     A19 = 17. Paziewski
     A20 = 18. Młynarczyk Adam
     A21 = 19. Leśniak
     A22 = 20. Trener 1
     A23 = 21. Trener 3
     A24 = 22. Trener 4
     A25 = 23. Trenner 5
  Formatowanie warunkowe:
     sqref=A3:A373 B3:F25 B28:F373 type=expression formula=['$A3="01. Małolepsza"'] -> fill=FFFF00FF
     sqref=A3:A373 B3:F25 B28:F373 type=expression formula=['$A3="02. Olszewska"'] -> fill=FFFF9900
     sqref=A3:A140 B3:F25 B28:F345 type=expression formula=['$A3="03. Majewska"'] -> fill=FF00FF00
     sqref=A3:A253 B3:F25 B28:F345 type=expression formula=['$A3="04. Zemela"'] -> fill=FFB7E1CD

### Kalendarz STYCZEŃ DT  (dim=A1:N1019)
  R1: [('B1', 'Poniedziałek'), ('C1', 'Wtorek'), ('D1', 'Środa'), ('E1', 'Czwartek'), ('F1', 'Piątek'), ('I1', 'Poniedziałek'), ('J1', 'Wtorek'), ('K1', 'Środa'), ('L1', 'Czwartek'), ('M1', 'Piątek')]
  R2: [('B2', datetime.datetime(2027, 1, 4, 0, 0)), ('C2', '=B2+1'), ('D2', '=C2+1'), ('E2', '=D2+1'), ('F2', '=E2+1'), ('I2', datetime.datetime(2027, 1, 11, 0, 0)), ('J2', '=I2+1'), ('K2', '=J2+1'), ('L2', '=K2+1'), ('M2', '=L2+1')]
  Kolumna A (trenerzy) n=23:
     A3 = 01. Małolepsza
     A4 = 02. Olszewska
     A5 = 03. Majewska
     A6 = 04. Zemela
     A7 = 05. Polakowska
     A8 = 06. Jankowska
     A9 = 07. Krzysztofik
     A10 = 08. Brzozowska
     A11 = 09. Bochniarz
     A12 = 10. Łukaszek
     A13 = 11. Białass (Pszczyna)
     A14 = 12. Jasińska Nina
     A15 = 13. Cebula
     A16 = 14. Swoboda
     A17 = 15. Gawron
     A18 = 16. Król
     A19 = 17. Paziewski
     A20 = 18. Młynarczyk Adam
     A21 = 19. Leśniak
     A22 = 20. Trener 1
     A23 = 21. Trener 3
     A24 = 22. Trener 4
     A25 = 23. Trenner 5
  Formatowanie warunkowe:
     sqref=A3:A373 B3:F25 B28:F373 H3:M25 type=expression formula=['$A3="01. Małolepsza"'] -> fill=FFFF00FF
     sqref=A3:A373 B3:F25 B28:F373 H3:M25 type=expression formula=['$A3="02. Olszewska"'] -> fill=FFFF9900
     sqref=A3:A140 B3:F25 B28:F345 H3:M25 type=expression formula=['$A3="03. Majewska"'] -> fill=FF00FF00
     sqref=A3:A253 B3:F25 B28:F345 H3:M25 type=expression formula=['$A3="04. Zemela"'] -> fill=FFB7E1CD

### Kalendarz LUTY DT  (dim=A1:A1)
  R1: []
  R2: []
  Kolumna A (trenerzy) n=0:
  Formatowanie warunkowe:

