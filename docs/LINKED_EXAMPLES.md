# Przykłady z linkowaniem — mcp-docs ↔ OpenWebUI

Ten dokument pokazuje jak łączyć dokumentację (http://localhost:8093/) z OpenWebUI (http://localhost:3000/).

---

## Szybki dostęp — linki bezpośrednie

| Usługa | URL |
|--------|-----|
| **Dokumentacja** | http://localhost:8093/ |
| **OpenWebUI (chat)** | http://localhost:3000/ |
| **MCP WebUI (admin)** | http://localhost:8092/ |
| **Gateway API** | http://localhost:9000/ |

---

## Przykład 1: Otwórz chat z gotowym promptem

Z dokumentacji możesz przejść bezpośrednio do OpenWebUI:

```markdown
[Otwórz OpenWebUI → nowy chat](http://localhost:3000/)
```

**Rezultat:** [Otwórz OpenWebUI → nowy chat](http://localhost:3000/)

---

## Przykład 2: Playbook z linkiem do wykonania

### Analiza ostatniego repo

**Krok 1:** Sprawdź dokumentację playbooka:  
[📖 Czytaj CHAT_PLAYBOOKS.md](http://localhost:8093/docs/CHAT_PLAYBOOKS.md)

**Krok 2:** Otwórz OpenWebUI i wklej prompt:  
[💬 Otwórz chat](http://localhost:3000/)

```text
Repo: {{show last pushed repo from github}}
Branch: main
Execute: false
Push: false
Zadanie: Przygotuj etapowy plan refaktoryzacji.
```

---

## Przykład 3: Pełny workflow z linkami

### Refaktoryzacja wielu projektów

| Krok | Dokumentacja | Akcja w OpenWebUI |
|------|--------------|-------------------|
| 1 | [📖 Analiza repo 1](http://localhost:8093/docs/CHAT_PLAYBOOKS.md) | [💬 Wyślij prompt](http://localhost:3000/) |
| 2 | [📖 Analiza repo 2](http://localhost:8093/docs/CHAT_PLAYBOOKS.md) | [💬 Wyślij prompt](http://localhost:3000/) |
| 3 | [📖 Wdrożenie](http://localhost:8093/docs/CHAT_PLAYBOOKS.md) | [💬 Execute](http://localhost:3000/) |

---

## Przykład 4: Komendy systemowe — dokumentacja + wykonanie

### Zarządzanie tokenem GitHub

**Dokumentacja:** [📖 Ustawienia GitHub](http://localhost:8093/docs/CHAT_PLAYBOOKS.md)  
**Wykonaj w czacie:** [💬 Otwórz OpenWebUI](http://localhost:3000/)

```text
Pobierz token GitHub z gh CLI
```

---

### Lista organizacji

**Dokumentacja:** [📖 Organizacje](http://localhost:8093/docs/CHAT_PLAYBOOKS.md)  
**Wykonaj w czacie:** [💬 Otwórz OpenWebUI](http://localhost:3000/)

```text
Pokaż listę repo organizacji
```

---

## Przykład 5: Automatyczny workflow (refactor-last-repo.sh)

**Dokumentacja:** [📖 Scenariusz 10 — USAGE.md](http://localhost:8093/docs/USAGE.md)  
**Wykonaj w terminalu:**

```bash
bash scripts/refactor-last-repo.sh --execute --push --pr
```

**Sprawdź wynik w OpenWebUI:** [💬 Otwórz chat](http://localhost:3000/)

---

## Nowe funkcje: Kopiowanie i wysyłanie promptów

Każdy blok kodu (`<pre>`) w dokumentacji ma teraz automatycznie dodawane przyciski:

### 📋 Kopiuj
- Kopiuje zawartość bloku do schowka
- Pokazuje powiadomienie "Skopiowano do schowka!"
- Dostępne dla **każdego** bloku kodu

### 🚀 OpenWebUI (tylko dla promptów)
- Wyświetla się tylko gdy blok zawiera pola: `Repo:`, `Zadanie:` lub `Execute:`
- Kopiuje prompt do schowka
- Otwiera OpenWebUI (http://localhost:3000/) w nowej karcie
- Automatycznie wykrywa prompty konfiguracyjne

### Przykład użycia

W dokumencie Markdown:
```markdown
    ```text
    Repo: demo/refactor-lab
    Branch: main
    Execute: false
    Zadanie: Przygotuj plan refaktoryzacji.
    ```
```

W przeglądarce zobaczysz:
```
┌─────────────────────────────────────────┐
│ Repo: demo/refactor-lab                 │
│ Branch: main                            │
│ ...                                     │
│                              [📋 Kopiuj]│
│                              [🚀 OpenWebUI]│
└─────────────────────────────────────────┘
```

### Template HTML dla mcp-docs (server.js)

Przyciski są dodawane automatycznie przez JavaScript, ale możesz też dodać własny link:

```html
<div style="margin: 16px 0; padding: 12px; border: 1px solid var(--border); border-radius: 8px;">
  <strong>🚀 Wykonaj w OpenWebUI:</strong>
  <a href="http://localhost:3000/" target="_blank" style="margin-left: 12px;">
    Otwórz chat →
  </a>
</div>
```

---

## Przykład 6: `Repo URL` jako override `repo_url` z template

Gdy używasz template `{{show last pushed repo from github}}`, gateway automatycznie pobiera `repo_url` z `gh2mcp`.  
Jeśli jednak podasz **ręcznie** `Repo URL:`, ma on **wyższy priorytet**.

### Bez `Repo URL` — gateway użyje `repo_url` z gh2mcp

```text
Repo: {{show last pushed repo from github owner=semcod}}
Branch: main
Execute: true
Push: true
PR: true
PR title: MCP: auto-refactor last repo
Zadanie: Wdróż Etap 1 planu refaktoryzacji.
```

→ `repo_url` pobrane z `gh2mcp /repo/last-pushed` → użyte do push/PR.

### Z `Repo URL` — ręczny override

```text
Repo: {{show last pushed repo from github owner=semcod}}
Repo URL: https://github.com/semcod/mcp
Branch: main
Execute: true
Push: true
PR: true
PR title: MCP: explicit url
Zadanie: Wdróż Etap 1 planu refaktoryzacji.
```

→ `Repo URL` ręczny wygrywa — `repo_url` z gh2mcp jest ignorowany.

**Dokumentacja:** [📖 USAGE.md — Pola Repo i Repo URL](http://localhost:8093/docs/USAGE.md)  
**Wykonaj:** [💬 Otwórz OpenWebUI](http://localhost:3000/)

---

## Przykład 7: Testy automatyczne

### Testy jednostkowe (pytest)

```bash
python3 -m pytest -q mcp-gateway/test_gateway_token_command.py gh2mcp/tests/test_gh2mcp.py
```

Co jest testowane:

| Moduł | Testy |
|-------|-------|
| `_is_github_token_sync_command` | detekcja komend sync tokenu |
| `_is_github_token_save_command` | detekcja komend zapisu tokenu |
| `_is_org_set_command` / `_is_org_list_command` | detekcja komend org |
| `_extract_org_from_text` | wyciąganie org z tekstu i `Repo URL` |
| `_resolve_repo_id_template` | rozwiązywanie `{{...}}` przez gh2mcp |
| `effective_repo_url` | priorytet `Repo URL` nad `repo_url` z template |
| `_render_chat_content` | Markdown render dla analyze/refactor/system |
| `GitHubTokenSyncService` | sync, org set/list, last pushed repo |

### Testy E2E Ansible

```bash
# gh2mcp: health, status, sync/token, org/set, org/list, repo/last-pushed, chat commands
make ansible-gh2mcp

# gateway + openwebui + prompts refactor/analyze
make ansible-e2e
```

**Dokumentacja:** [📖 CHAT_PLAYBOOKS.md](http://localhost:8093/docs/CHAT_PLAYBOOKS.md)

---

## API — lista dokumentów z linkami

```bash
curl http://localhost:8093/api/docs
```

Odpowiedź zawiera listę plików Markdown dostępnych pod `/docs/{nazwa}`.

---

## Podsumowanie linków

```markdown
Dokumentacja:     http://localhost:8093/
├── README:       http://localhost:8093/docs/README.md
├── Playbooki:    http://localhost:8093/docs/CHAT_PLAYBOOKS.md
├── Use Cases:    http://localhost:8093/docs/USE_CASES.md
└── USAGE:        http://localhost:8093/docs/USAGE.md

OpenWebUI:        http://localhost:3000/
MCP WebUI:        http://localhost:8092/
Gateway:          http://localhost:9000/
```

---

## Dodaj do mcp-docs/server.py

Aby automatycznie dodawać linki do OpenWebUI w każdym dokumencie:

```python
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3000")

# W funkcji render_doc(), przed zamknięciem card:
openwebui_link = f'''
<div style="margin-top: 20px; padding: 12px; background: rgba(125, 211, 252, 0.1); 
            border: 1px solid var(--link); border-radius: 8px;">
  <a href="{OPENWEBUI_URL}/" target="_blank" style="color: var(--link);">
    🚀 Otwórz w OpenWebUI →
  </a>
</div>
'''
```
