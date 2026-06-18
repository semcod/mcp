# Cursor + semcod-mcp — workflow

Przewodnik: jak używać stacku `semcod/mcp` w **Cursor Agent** (nie Ask).

Powiązane: [spis dokumentacji](README.md) · [SEMCOD_MCP_CLI.md](SEMCOD_MCP_CLI.md) · [IDE_AND_AGENT_INTEGRATION.md](IDE_AND_AGENT_INTEGRATION.md)

---

## 1. Wymagania

```bash
cd ~/github/semcod/mcp
docker compose up -d          # lub: make start
semcod-mcp doctor             # wszystkie required: OK
semcod-mcp validate           # passed
```

## 2. Konfiguracja Cursor (jednorazowo)

1. Otwórz **folder** `~/github/semcod/mcp` jako root workspace.
2. `semcod-mcp init` (jeśli brak `.cursor/mcp.json`).
3. **Settings → MCP** — serwer `semcod-mcp-skills` musi być **zielony**.
4. **Command Palette → Developer: Reload Window**.

Opcjonalnie globalnie (wszystkie projekty):

```bash
semcod-mcp init --global --stack-path ~/github/semcod/mcp
```

## 3. Test w chacie Agent

```
Wywołaj compute_metrics_for_repo dla repo_id semcod/mcp
i pokaż largest_files (top 5).
```

Oczekiwany wynik: listy plików z liczbą linii, np. `mcp-gateway/server.py`, `mcp-skills/server.py`.

## 4. Czy Cursor używa MCP automatycznie?

| Mechanizm | Automatyczny? |
|-----------|----------------|
| MCP tools (`semcod-mcp-skills`) | **Nie w 100%** — agent decyduje, czy wywołać narzędzie |
| Reguła `.cursor/rules/semcod-mcp.mdc` | Półautomatyczny — instruuje agenta |
| Globalne MCP (`user-llx`: code2llm, vallm) | Często — lepsze opisy narzędzi |
| `semcod-mcp analyze` w terminalu | Ręczny — zawsze działa |

**Zasada:** im bardziej konkretny prompt (repo_id, faza, narzędzie), tym częściej agent wywoła MCP.

## 5. Workflow 3-fazowy (zalecany)

### Faza 1 — Analiza (przed refactorem)

W chacie Agent:

```
Repo: semcod/mcp
Zadanie: split mcp-gateway/server.py — tylko analiza

1. compute_metrics_for_repo(semcod/mcp)
2. recommend_refactoring — goal maintainability
3. Nie edytuj plików jeszcze
```

Lub w terminalu:

```bash
semcod-mcp analyze . --task "split gateway_render — etap 1"
```

### Faza 2 — Implementacja

```
Na podstawie largest_files zaimplementuj tylko:
- mcp-gateway/gateway_render.py (już wydzielony)
- cienki mcp-gateway/server.py z importami

Bez zmiany zachowania API. Uruchom pytest mcp-gateway/.
```

### Faza 3 — Weryfikacja

```bash
semcod-mcp validate
semcod-mcp doctor
pytest mcp-skills/ mcp-gateway/
make smoke
```

W chacie (globalne MCP):

```
vallm_validate na zmienionych plikach
code2llm_analyze na mcp-gateway/
```

## 6. Dwa poziomy narzędzi

| Poziom | Serwer | Kiedy |
|--------|--------|-------|
| Repo (git-proxy) | `semcod-mcp-skills` | `repo_id: semcod/mcp`, sync, metryki całego repo |
| Lokalny kod | `user-llx` / `code2llm` | Analiza ścieżki na dysku bez sync |

## 7. Moduły po refaktorze (2026-06)

### mcp-skills

| Moduł | Rola |
|-------|------|
| `server.py` | MCP stdio + FastAPI routes (~690 L) |
| `code_analysis.py` | Metryki, `largest_files`, rekomendacje |
| `tools_registry.py` | Rejestr paczek `semcod/*` |
| `tool_run.py` | `/tools/run` |
| `http_models.py` | Pydantic request models |
| `redsl_runner.py` | subprocess redsl |
| `mcp_parse.py` | parse MCP JSON |

### mcp-gateway

| Moduł | Rola |
|-------|------|
| `server.py` | Routes, dispatch (~2480 L — etap 2 split w toku) |
| `gateway_config.py` | Env, `SKILL_MODELS` |
| `gateway_render.py` | Markdown dla chat UI |

Plan dalszego splitu: [GATEWAY_MODULE_SPLIT.md](GATEWAY_MODULE_SPLIT.md).

## 8. Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| MCP `semcod-mcp-skills` szary | Reload Window; `docker compose ps`; sprawdź `.cursor/mcp.json` |
| `doctor` FAIL gateway | `docker compose restart mcp-gateway mcp-skills`; poczekaj 10 s |
| Agent nie wywołuje MCP | Użyj jawnych nazw narzędzi w promptcie; tryb **Agent** nie Ask |
| Brak `largest_files` | `docker compose build mcp-skills && docker compose up -d mcp-skills` |
