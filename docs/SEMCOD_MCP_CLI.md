# semcod-mcp CLI

Pakiet `semcod-mcp` konfiguruje integrację projektu z stackiem [semcod/mcp](https://github.com/semcod/mcp) dla Cursor, VS Code, Windsurf i Continue.

## Instalacja

```bash
pip install -e ~/github/semcod/mcp
```

## Komendy

| Komenda | Opis |
|---------|------|
| `semcod-mcp init` | Merge konfiguracji IDE w bieżącym (lub podanym) katalogu |
| `semcod-mcp doctor` | Health check: Docker, gateway, manifest |
| `semcod-mcp validate` | Walidacja plików integracji |
| `semcod-mcp analyze` | Analiza repo przez gateway |

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

## Przykład

```bash
cd ~/github/semcod/nlp2cmd
semcod-mcp init
semcod-mcp init    # bezpieczne — nic nie duplikuje
semcod-mcp doctor
semcod-mcp validate
```

## Pełna dokumentacja integracji IDE

[`docs/IDE_AND_AGENT_INTEGRATION.md`](../docs/IDE_AND_AGENT_INTEGRATION.md)
