# semcod-mcp CLI

Pakiet `semcod-mcp` konfiguruje integrację projektu z stackiem [semcod/mcp](https://github.com/semcod/mcp) dla Cursor, VS Code, Windsurf i Continue.

**Powiązane:** [spis dokumentacji](README.md) · [integracja IDE](IDE_AND_AGENT_INTEGRATION.md) · [plan splitu gateway](GATEWAY_MODULE_SPLIT.md)

## Instalacja

```bash
pip install -e ~/github/semcod/mcp
```

## Komendy

| Komenda | Opis |
|---------|------|
| `semcod-mcp init` | Merge konfiguracji IDE w bieżącym (lub podanym) katalogu |
| `semcod-mcp deinit` | Usuwa wpisy dodane przez `init` (inne `mcpServers` zostają) |
| `semcod-mcp doctor` | Health check: Docker, gateway, manifest |
| `semcod-mcp validate` | Walidacja plików integracji |
| `semcod-mcp analyze` | Analiza repo przez gateway (`--task`, opcjonalnie `--execute`) |

## Manifest `.semcod-mcp.yaml`

Po `init` w katalogu projektu powstaje manifest audytu integracji:

```yaml
repo_id: semcod/nlp2cmd
stack_path: /home/tom/github/semcod/mcp
ides:
  - cursor
  - vscode
  - windsurf
  - continue
```

- **`ides`** — które integracje zostały skonfigurowane (jeden `init` = wszystkie naraz)
- **`repo_id`** — logiczny identyfikator dla gateway / git-proxy
- Nie jest to rejestr paczek `semcod/*` — patrz [Rejestry w IDE_AND_AGENT_INTEGRATION.md](IDE_AND_AGENT_INTEGRATION.md#rejestry-paczek-skilli-i-integracji-ide)

### Audyt wielu projektów

```bash
find ~/github/semcod -name '.semcod-mcp.yaml' | while read m; do
  d=$(dirname "$m")
  printf "%-40s " "$(basename "$d")"
  semcod-mcp validate "$d" 2>&1 | tail -1
done
```

## Idempotentność `init` (ważne)

**Ponowne `semcod-mcp init` nie duplikuje wpisów MCP.**

| Plik | Pierwszy `init` | Drugi `init` (bez `--force`) |
|------|-----------------|------------------------------|
| `.cursor/mcp.json` | dodaje `semcod-mcp-skills` | `unchanged` — jeden wpis, brak kopii |
| `.vscode/mcp.json` | j.w. | `unchanged` |
| `.windsurf/mcp.json` | j.w. | `unchanged` |
| `.continue/config.json` | dodaje 3 modele po `title` | `unchanged` — bez duplikatów |
| `.vscode/settings.json` | dodaje klucze `semcod-mcp.*` | `unchanged` lub `skipped` |
| `.cursor/rules/semcod-mcp.mdc` | tworzy plik | `skipped (exists)` |
| `.semcod-mcp.yaml` | zapisuje manifest | `unchanged` — bez nadpisywania |

Na końcu drugiego uruchomienia zobaczysz:

```text
Already initialized — no changes (idempotent).
```

### Kiedy coś się zmieni przy ponownym `init`

- **`--force`** — nadpisuje wpisy `semcod-mcp-skills` i modele Continue
- **Zmiana `stack_path`** lub `gateway_url` w env — manifest zostanie zaktualizowany
- **Ręczna edycja** wpisu `semcod-mcp-skills` na inną wartość — bez `--force` zostanie `skipped` (Twoja wersja chroniona)

### Czego `init` nigdy nie robi

- Nie usuwa innych `mcpServers` (np. `user-algitex-aider`)
- Nie nadpisuje obcych ustawień VS Code
- Nie dodaje drugiego `semcod-mcp-skills` przy kolejnym uruchomieniu

## `deinit` — cofnięcie integracji

```bash
semcod-mcp deinit              # usuwa wpisy semcod z projektu
semcod-mcp deinit --dry-run    # podgląd bez zapisu
semcod-mcp deinit --global     # także ~/.cursor/mcp.json i Claude Desktop
```

| Plik | Co robi `deinit` |
|------|------------------|
| `.cursor/mcp.json` | usuwa `semcod-mcp-skills`; plik kasowany jeśli pusty |
| `.vscode/mcp.json`, `.windsurf/mcp.json` | j.w. |
| `.cursor/rules/semcod-mcp.mdc` | usuwa plik |
| `.continue/config.json` | usuwa modele `semcod-mcp-*` |
| `.vscode/settings.json` | usuwa klucze `semcod-mcp.*` |
| `.semcod-mcp.yaml` | usuwa manifest |

**Nie usuwa** innych serwerów MCP ani obcych ustawień VS Code. Po `deinit` w Cursorze: **Reload Window**.

## Przykład

```bash
cd ~/github/semcod/nlp2cmd
semcod-mcp init
semcod-mcp init    # bezpieczne — nic nie duplikuje
semcod-mcp doctor
semcod-mcp validate
semcod-mcp analyze --task "Które pliki split w tym repo?"
```

Wynik `analyze` (przez gateway) zawiera m.in. `largest_files` i rekomendacje z konkretnymi ścieżkami plików — szczegóły: [USAGE.md § Jak czytać wynik](USAGE.md#jak-czytać-wynik-w-czacie).

## Hurtowe init (folder)

```bash
STACK=~/github/semcod/mcp
for d in /home/tom/github/tellmesh/*/; do
  [ -d "$d/.git" ] || continue
  semcod-mcp init "$d" --stack-path "$STACK"
done
```

Więcej: [IDE_AND_AGENT_INTEGRATION.md §9](IDE_AND_AGENT_INTEGRATION.md#9-automatyczne-podpięcie-do-wielu-projektów).

## Pełna dokumentacja integracji IDE

[`docs/IDE_AND_AGENT_INTEGRATION.md`](IDE_AND_AGENT_INTEGRATION.md)
