# Etap A — meldunek z VPS (20.08.2026, przed rozdzieleniem demo)

Stan serwera `57.128.241.52` **przed** przeniesieniem demo do własnego katalogu.
Zapisany, bo to punkt odniesienia: gdyby coś poszło nie tak, tu jest napisane,
jak było.

## Kod

| | |
|---|---|
| Produkcja stoi na | `6a3e181` „Zajęcia cykliczne na konkretne daty…" (17.08, 09:26) |
| Kontener wstał | 17.08, 09:42 — **po** tym commicie, więc naprawdę na nim chodzi |
| `origin/main` | `6360429` „START POPRAWKI 20.08.2026" (20.08, 07:02) — **sama dokumentacja** |
| Wniosek | kod produkcji = kod na GitHubie; nie ma rozjazdu do nadrobienia |
| Gałęzie | `CYKLICZNE-PRZEDSZKOLE` (`80232ad`) jest przodkiem `6a3e181` → scalona, do skasowania |
| Tagi | tylko `v4.0-spotkanie`; `przed-poprawkami-2026-08-20` jeszcze nie istnieje |

## Docker

| | |
|---|---|
| Projekt compose | `phsilesia3dsite` (bierze się z nazwy katalogu) |
| Kontenery | `leady_app_v5` → 127.0.0.1:5301, `leady_app_v5_demo` → 127.0.0.1:5302 |
| Obrazy | `phsilesia3dsite-leady_v5`, `phsilesia3dsite-leady_v5_demo` |
| Wolumen produkcji | `phsilesia3dsite_leady_v5_data` → `/data` — **nie dotykać** |
| Wolumen starego demo | `phsilesia3dsite_leady_v5_demo_data` → zostaje sierotą po Etapie D |

Sąsiedzi na tym samym serwerze: `librus.silesia3d.site` (5100),
`rspo.silesia3d.site` (5310), `akademia.silesia3d.site`.

**Żadnego `docker volume prune` przez najbliższe tygodnie** — skasowałby
osierocony wolumen starego demo, czyli jedyną kopię jego danych.

## nginx

`ph.silesia3d.site` → `127.0.0.1:5301`, `demo-ph.silesia3d.site` → `127.0.0.1:5302`.
Zgadza się z planem — przeniesienie demo do innego katalogu **nie wymaga zmian
w nginx**, bo port zostaje ten sam.

## Dane

| Profil | Placówki | Leady |
|---|---|---|
| produkcja | 545 | 544 |
| demo (przed przenosinami) | 545 | 545 |

Demo miało własne, rozjechane dane z 17.08 — po Etapie E zostaną zastąpione
kopią produkcji.

Kopie: cron 6:00 dziennie, `--trzymaj 30`, 15 kopii w wolumenie produkcji,
najświeższa `prod_2026-08-19_0600.db`. Baza produkcji waży 0,5 MB.

Dysk: 52 GB wolnego z 72 GB.

## Uwierzytelnienie do GitHuba

Remote po HTTPS, **brak klucza SSH i brak `~/.git-credentials`** — działa,
bo repozytorium jest **publiczne**: anonimowy `clone` i `pull` przechodzą bez
żadnej konfiguracji.

Skutki, o których trzeba pamiętać:

1. **`git push` z serwera nie zadziała** — nie ma tam żadnych poświadczeń.
   To zgodne z zasadą „kod jedzie gitem z Windowsa", ale nie licz, że poprawisz
   coś szybko na serwerze i wypchniesz.
2. **Przełączenie repozytorium na prywatne zepsuje `wdroz.sh` w OBU katalogach**
   (`git pull --ff-only` na prywatnym repo bez poświadczeń kończy się błędem,
   a `set -e` przerywa skrypt). Jeśli taka decyzja zapadnie, trzeba tym samym
   ruchem założyć klucz wdrożeniowy (read-only) i przestawić remote na SSH.
