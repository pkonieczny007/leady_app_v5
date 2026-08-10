<#
.SYNOPSIS
Ściąga kopie zapasowe z VPS na ten komputer. Uruchamiany z ręki, gdy chcesz.

.DESCRIPTION
PO CO
Cron na serwerze robi kopię codziennie o 6:00 — ale ona leży w wolumenie
dockera, na tej samej maszynie co oryginał. To zabezpieczenie przed pomyłką
człowieka, NIE przed awarią serwera. Kopią zapasową staje się dopiero po
ściągnięciu tutaj.

DLACZEGO .ps1, A NIE .py JAK RESZTA `narzedzia/`
Tamte narzędzia działają na bazie i uruchamiają się także w kontenerze. To
działa na Twoim komputerze i rozmawia z serwerem — nie ma czego importować
z aplikacji, a PowerShell jest tu wszędzie pod ręką.

CZEGO NIE ROBI
Nie wysyła niczego na serwer i nic tam nie zmienia poza katalogiem
przejściowym `~/kopie-vps`, który sam po sobie sprząta. Kopii bazy świadomie
NIE wkładamy do gita — są w niej telefony i maile dyrektorów szkół, a git
nigdy nie zapomina.

.PARAMETER Cel
Katalog na kopie. Domyślnie C:\XEN\AI-szkolenie\SIERPIEN2026\kopie_vps

.PARAMETER Librus
Dołóż zrzut wolumenu aplikacji librus (osobna aplikacja na tym samym serwerze,
dziś bez żadnej kopii).

.PARAMETER Kod
Odśwież lustro repozytorium z GitHuba — kopia awaryjna kodu na wypadek, gdyby
GitHub zniknął albo konto zostało zablokowane.

.EXAMPLE
.\narzedzia\kopia_z_serwera.ps1
.\narzedzia\kopia_z_serwera.ps1 -Librus -Kod
#>
param(
    [string]$Cel = "C:\XEN\AI-szkolenie\SIERPIEN2026\kopie_vps",
    [switch]$Librus,
    [switch]$Kod
)

$ErrorActionPreference = "Stop"

$Serwer     = "ubuntu@57.128.241.52"
$Kontener   = "leady_app_v5"
$Przejsciowy = "~/kopie-vps"        # katalog na serwerze, kasowany po ściągnięciu
$RepoUrl    = "https://github.com/pkonieczny007/leady_app_v5.git"

$stempel = Get-Date -Format "yyyy-MM-dd_HHmm"
$dzis    = Join-Path $Cel $stempel

function Krok($tekst) { Write-Host "`n== $tekst ==" -ForegroundColor Cyan }
function Blad($tekst) { Write-Host "BLAD: $tekst" -ForegroundColor Red }
function Info($tekst) { Write-Host "  $tekst" -ForegroundColor DarkGray }

Krok "Sprawdzam, czy serwer odpowiada"
# Bez tego skrypt wywala się dopiero przy scp, komunikatem o niczym.
$test = ssh -o BatchMode=no -o ConnectTimeout=10 $Serwer "echo ok"
if ($test -ne "ok") {
    Blad "nie mogę się zalogować na $Serwer"
    Write-Host @"
Jeśli za każdym razem pyta o hasło, wgraj klucz — skrypt robi trzy połączenia,
więc bez klucza zapytа trzy razy:
    ssh-keygen -t ed25519                       # jeśli jeszcze nie masz
    type `$env:USERPROFILE\.ssh\id_ed25519.pub | ssh $Serwer "cat >> ~/.ssh/authorized_keys"
"@
    exit 1
}
Info "serwer odpowiada"

New-Item -ItemType Directory -Force -Path $dzis | Out-Null

# ------------------------------------------------------------------ leady
Krok "Wykładam kopie z wolumenu dockera"
# Kopie leżą w /var/lib/docker/volumes/... — katalogu z prawami drwx--x--- dla
# roota. Ani scp, ani eksplorator plików tam nie zajrzą, więc najpierw trzeba je
# wyjąć przez `docker cp` w miejsce, do którego użytkownik `ubuntu` ma dostęp.
# Pliki -shm/-wal to towarzysze SQLite; przy odtwarzaniu tylko mylą, więc lecą.
$polecenie = "rm -rf $Przejsciowy && mkdir -p $Przejsciowy && " +
             "docker cp ${Kontener}:/data/kopie/. $Przejsciowy/ && " +
             "rm -f $Przejsciowy/*-shm $Przejsciowy/*-wal && " +
             "chmod 700 $Przejsciowy && chmod 600 $Przejsciowy/* && " +
             "ls -1 $Przejsciowy | wc -l"
$ile = ssh $Serwer $polecenie
if (-not $?) { Blad "nie udało się wyłożyć kopii na serwerze"; exit 1 }
Info "plików do pobrania: $($ile | Select-Object -Last 1)"

# ------------------------------------------------------------------ librus
if ($Librus) {
    Krok "Zrzut wolumenu librusa"
    # Librus to OSOBNA aplikacja na tym samym serwerze i dziś nie ma żadnej
    # kopii. Niczego w niej nie zmieniamy — tar z wolumenu jest operacją
    # wyłącznie do odczytu. UWAGA: kopia na poziomie plików z działającej bazy
    # może złapać stan niespójny. Dopóki raz jej nie odtworzymy, to jest
    # „lepsze niż nic", a nie sprawdzona kopia.
    # Format trzymamy w osobnej zmiennej w apostrofach — inaczej cudzysłowy
    # wewnątrz szablonu Go zamykają łańcuch PowerShella i skrypt się nie parsuje.
    $fmt = '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}'
    $wol = ssh $Serwer "docker inspect librus_raport_app --format '$fmt'"
    $wol = ($wol | Select-Object -Last 1)
    if ($null -ne $wol) { $wol = $wol.Trim() }
    if ([string]::IsNullOrWhiteSpace($wol)) {
        Info "librus nie ma nazwanego wolumenu — pomijam (sprawdz docker inspect recznie)"
    } else {
        Info "wolumen: $wol"
        $tar = "librus_$stempel.tar.gz"
        $cmd = "docker run --rm -v ${wol}:/v -v ${Przejsciowy}:/out alpine tar czf /out/$tar -C /v . && chmod 600 $Przejsciowy/$tar"
        ssh $Serwer $cmd
        if ($?) { Info "spakowany: $tar" } else { Blad "zrzut librusa sie nie udal" }
    }
}

# ------------------------------------------------------------------ pobranie
Krok "Pobieram na ten komputer"
scp "${Serwer}:~/kopie-vps/*" $dzis
if (-not $?) { Blad "scp się nie udał — kopie ZOSTAJĄ na serwerze, nie kasuję"; exit 1 }

$pliki = Get-ChildItem $dzis
if ($pliki.Count -eq 0) {
    Blad "nic nie pobrano, choć scp nie zgłosił błędu — sprawdź ręcznie"
    exit 1
}
Info "pobrano $($pliki.Count) plików, razem $([math]::Round(($pliki | Measure-Object Length -Sum).Sum / 1MB, 1)) MB"

Krok "Sprzątam katalog przejściowy na serwerze"
# W tych plikach są dane osobowe — nie zostawiamy ich w katalogu domowym.
ssh $Serwer "rm -rf $Przejsciowy"
if ($?) { Info "sprzątnięte" } else { Info "UWAGA: nie udało się sprzątnąć $Przejsciowy — zrób to ręcznie" }

# ------------------------------------------------------------------ kontrola
Krok "Sprawdzam, czy to na pewno działające bazy"
# Sam fakt, że plik ma poprawną nazwę i rozmiar, nic nie znaczy. Kopia jest
# kopią dopiero wtedy, gdy da się ją otworzyć i policzyć w niej rekordy.
$sprawdz = @'
import sqlite3, sys, glob, os
zle = 0
for p in sorted(glob.glob(os.path.join(sys.argv[1], "*.db"))):
    try:
        c = sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)
        stan = c.execute("PRAGMA integrity_check").fetchone()[0]
        pl = c.execute("SELECT COUNT(*) FROM placowki").fetchone()[0]
        le = c.execute("SELECT COUNT(*) FROM leady").fetchone()[0]
        c.close()
        ok = (stan == "ok" and pl > 0)
        print("  [%s] %-34s %s, %d placowek, %d leadow"
              % ("OK  " if ok else "BLAD", os.path.basename(p), stan, pl, le))
        if not ok:
            zle += 1
    except Exception as e:
        print("  [BLAD] %-34s %s" % (os.path.basename(p), e))
        zle += 1
sys.exit(1 if zle else 0)
'@
$tmpPy = Join-Path $env:TEMP "sprawdz_kopie_$stempel.py"
Set-Content -Path $tmpPy -Value $sprawdz -Encoding utf8
python $tmpPy $dzis
$kontrola = $LASTEXITCODE
Remove-Item $tmpPy -ErrorAction SilentlyContinue

# ------------------------------------------------------------------ kod
if ($Kod) {
    Krok "Odświeżam lustro repozytorium"
    # Lustro, nie zwykły klon: z gałęziami, tagami i całą historią. Gdyby
    # GitHub zniknął albo konto zostało zablokowane, z tego katalogu odtworzysz
    # repozytorium jednym `git clone`.
    $lustro = Join-Path $Cel "leady_app_v5.git"
    if (Test-Path $lustro) {
        Push-Location $lustro
        git remote update --prune
        Pop-Location
    } else {
        git clone --mirror $RepoUrl $lustro
    }
    if ($?) { Info "lustro: $lustro" } else { Blad "nie udało się odświeżyć lustra" }
}

# ------------------------------------------------------------------ podsumowanie
Krok "Gotowe"
Write-Host "  Kopie:  $dzis"

# Wiek najnowszej kopii — jedyna rzecz, która wykrywa CICHĄ awarię.
# Mac mini ciągnie kopie z crona, ale bywa wyłączony; wtedy nic się nie dzieje
# i nic o tym nie mówi. Brak kopii nie boli, dopóki nie jest potrzebna, więc
# jedyną obroną jest patrzenie na datę przy każdym ręcznym uruchomieniu.
$wszystkie = Get-ChildItem $Cel -Recurse -Filter "*.db" -ErrorAction SilentlyContinue
if ($wszystkie) {
    $najnowsza = $wszystkie | Sort-Object LastWriteTime | Select-Object -Last 1
    $dni = [math]::Round(((Get-Date) - $najnowsza.LastWriteTime).TotalDays, 1)
    Write-Host "  Najnowsza kopia w tym katalogu: $($najnowsza.Name), sprzed $dni dni"
    if ($dni -gt 8) {
        Write-Host "  UWAGA: najnowsza kopia ma ponad tydzien - sprawdz, czy cron na serwerze zyje" -ForegroundColor Yellow
    }
}
if ($kontrola -eq 0) {
    Write-Host "  Kontrola zawartosci: wszystkie bazy otwieraja sie poprawnie" -ForegroundColor Green
} else {
    Write-Host "  Kontrola zawartosci: CZESC BAZ NIE PRZESZLA - patrz wyzej" -ForegroundColor Red
}
Write-Host @"

  Pamietaj: w tych plikach sa telefony i maile dyrektorow szkol oraz skroty
  PIN-ow. Katalog `$Cel jest POZA repozytorium i ma tam zostac.

  Czego tu NIE MA: pliku .env z serwera (SECRET_KEY, PIN koordynatora).
  On nie jest w gicie i nie powinien lezec na dysku obok kopii — jego miejsce
  jest w menedzerze hasel.
"@
if ($kontrola -ne 0) { exit 1 }
