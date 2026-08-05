# Wymagania klienta (tekst z: opis tabelki do zrobionia.docx)

1. Przypisanie: Koordynator wybiera handlowca z listy rozwijanej w bazie głównej. Może być jedna na cały region, ważne żeby było możliwe filtrowanie po mieście i handlowcu

2. Transfer: Lead automatycznie znika z bazy głównej i trafia do arkusza danego handlowca. Ważne filtrowanie po mieście i po statusach – umówione DT lub brak ruchu)

3. Sukces: Handlowiec umawia spotkanie, a dane wpadają do kalendarza DT (czasem 2-3 eventy dziennie u jednego trenera), kalendarza zajęć cyklicznych i zbiorczego arkusza Julki (ważne filtrowanie w każdej komórce).

4. Brak efektu: Jeśli handlowiec nie umówi spotkania w terminie, koordynator odbiera mu dostęp i przenosi rekord do zakładki niewykorzystane rekordy, z której może przydzielić go innemu handlowcowi - filtrowanie po mieście i po statusach



1. Struktura wejściowa (Zakładki handlowców)W pliku znajduje się 5 zakładek imiennych handlowców: Sacawa, Olszewska, Małolepsza, Chytry, Młynarczyk.
	Teraz handlowcy wpisują tam dane szkół sami, bo póki co pracujemy na swoich „starych szkołach”. Docelowo ma się to „przypisywać” z bazy ogólnej po wybraniu z listy rozwijanej nazwiska handlowca
	Zmiana statusu w dedykowanej kolumnie na wartość „DT umówione” 
2. Logika przesyłania danych (Po spełnieniu warunku „DT umówione”)Gdy warunek jest spełniony, dany wiersz ze szkoły musi automatycznie kopiuje się do dwóch miejsc jednocześnie, a potem do trzech:
1. Plik zbiorczy Julki: Dane dopisują się jako nowy wiersz w głównym zestawieniu, gdzie Julka ma swoje własne kolumny do ręcznego uzupełniania.
2. Kalendarze miesięczne: Dane muszą trafić do odpowiedniej zakładki miesięcznej („kalendarz wrzesień”, „kalendarz październik” itd.). System musi automatycznie rozpoznawać miesiąc na podstawie wpisanej w wierszu daty i kierować rekord do właściwej zakładki (mechanizm musi działać płynnie dla kolejnych miesięcy, bez sztywnego kodowania na stałe). Tu mam też problem, bo jeśli dany trener prowadzący event ma 2 lub więcej takie spotkania w szkołach w danym dniu to nie widzę 2 wpisów w tej dacie w kalendarzu DT, a powinnam, bo z tego kalendarza będą korzystali trenerzy planując swój czas pracy. Docelowo będę chciała, żeby to się przenosiło do kalendarza google każdemu trenerowi, ale to jest przyszłość- chyba że nie zajmie to dużo czasu
3.Jak handlowiec umówi kolejny szczegół czyli dni kiedy bedą zajęcia cykliczne będzie potrzebny arkusz z kalendarzem trenerów i to już jest Meksyk -  wyślę Ci dostęp jako podgląd z zeszłego roku i tam zobaczysz jest zakładka np. STARTY CZERWIEC – każdy trener ma swój kolor – my to im nanosimy na google kalendarz z ręki, ale my musimy mieć taka planszę gdzie widzimy cała firmę kto gdzie jest, bo to ułatwia ustawianie pracy handlowca i dogrywanie szkół no i potem pracę np. w przypadku zastępstw i szybkiej lokalizacji trenera. Więc potrzebny będzie kolejny kalendarz w tabeli z TRENERAMI i fajnie jak by si to układało w takim schemacie jak ułożyłam wpisy w kalendarzu DT

3. Nowy moduł zarządzania bazą (Dane z RSPO)Docelowo do pliku zostanie wgrana czysta baza szkół z rejestru RSPO, przefiltrowana przez Koordynatora pod kątem miast z danego regionu. Muszą być listy rozwijane na każdym arkuszu takie same (generalnie całe tabele są powielone jak widzisz)
	Zadanie dla systemu przydzielania: Koordynator ręcznie przypisuje szkołę z tej bazy do konkretnego handlowca (z listy rozijanej) oraz wpisuje „ostateczny termin” (datę) na wykonanie ruchu. To musi automatycznie zniknąć z bazy ogólnej i tracić do bazy tego handlowca
	Logika sprawdzania aktywności: System musi kontrolować, czy handlowiec wykonał jakikolwiek wpis/ruch przy przypisanej szkole przed upływem wpisanej daty. (jeśli się to da zrobić – jeśli nie będę to robiła ręcznie  tu akurat to najmniej ważne)
	Jeśli brak aktywności po terminie: Wiersz z tą szkołą ma automatycznie (lub ma zostać przepisany do listy niewykorzystane rekordy) zniknąć z widoku handlowca i zostać przeniesiony do osobnej zakładki o nazwie „niewykorzystane rekordy”.

