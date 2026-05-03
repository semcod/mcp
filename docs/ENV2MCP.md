# env2mcp — Zarządzanie konfiguracją środowiskową

Narzędzie do zarządzania zmiennymi środowiskowymi w projekcie MCP. Umożliwia bezpieczne przechowywanie tokenów, integrację z GitHub CLI oraz wygodny dostęp do konfiguracji z poziomu shell i kodu Python.

---

## Instalacja

### Z Makefile (zalecane)

```bash
make install-env2mcp
```

### Ręcznie

```bash
pip install -e ./env2mcp
```

### Z pipx (izolowane środowisko)

```bash
pipx install ./env2mcp
```

---

## Szybki start

### 1. Konfiguracja GitHub

```bash
# Interaktywny wizard - sprawdzi gh CLI, zaloguje, zapisze token
env2mcp setup-github

# Lub użyj make
make setup-github
```

Co się dzieje:
1. Sprawdza czy `gh` CLI jest zainstalowane
2. Jeśli tak → otwiera przeglądarkę do logowania GitHub
3. Pobiera token i zapisuje do `.env` jako `GITHUB_PAT`
4. Jeśli nie ma `gh` → prosi o ręczne wprowadzenie tokena

### 2. Sprawdź status

```bash
env2mcp github status
```

Wyjście:
```
✓ GitHub CLI is authenticated
  User: twoj-login
✓ Token found in .env
```

### 3. Lista repozytoriów

```bash
# Twoje repozytoria
env2mcp github repos --limit 10

# Repozytoria organizacji
env2mcp github repos --owner microsoft --limit 5
```

---

## Komendy CLI

### `env2mcp setup-github`

Główny wizard konfiguracji. Równoważne:
```bash
env2mcp github login
```

### `env2mcp github`

#### `login` — Logowanie interaktywne
```bash
env2mcp github login
```
Uruchamia przeglądarkę do autentykacji GitHub (jeśli `gh` jest dostępny).

#### `status` — Sprawdź autentykację
```bash
env2mcp github status
```
Pokazuje:
- Czy `gh` CLI jest zainstalowane
- Czy jesteś zalogowany
- Czy token jest w `.env`

#### `repos` — Lista repozytoriów
```bash
env2mcp github repos                    # Twoje repo
env2mcp github repos --owner org      # Repo organizacji
env2mcp github repos --limit 20       # Limit wyników
```

#### `logout` — Wylogowanie
```bash
env2mcp github logout
```
Wylogowuje z `gh` CLI i usuwa token z `.env`.

### `env2mcp env`

#### `show` — Pokaż wszystkie zmienne
```bash
env2mcp env show
```
Pokazuje zmienne z `.env` i środowiska. Wartości wrażliwe są maskowane.

#### `get` — Pobierz zmienną
```bash
env2mcp env get OPENROUTER_API_KEY           # Maskowana
env2mcp env get OPENROUTER_API_KEY --show   # Pełna wartość
```

#### `set` — Ustaw zmienną
```bash
env2mcp env set OPENROUTER_API_KEY "sk-or-v1-..."
env2mcp env set LLM_MODEL "openrouter/x-ai/grok-code-fast-1"
```

---

## Użycie w kodzie Python

### Podstawowe operacje na `.env`

```python
from env2mcp import EnvConfig

# Załaduj plik .env
config = EnvConfig(".env")

# Pobierz wartość (sprawdza najpierw env, potem plik)
api_key = config.get("OPENROUTER_API_KEY")

# Ustaw wartość
config["GITHUB_PAT"] = "ghp_xxx"
config["GITHUB_USER"] = "moj-login"

# Zapisz do pliku (z automatycznym backup)
config.save()

# Sprawdź czy zmienna istnieje
if "GITHUB_PAT" in config:
    print("GitHub skonfigurowany")

# Iteruj po wszystkich zmiennych
for key, value in config.items():
    print(f"{key}={value}")
```

### Integracja z GitHub CLI

```python
from env2mcp import GitHubCLI, get_github_token

# Sprawdź czy gh CLI jest dostępne
gh = GitHubCLI()
if gh.is_available():
    print("GitHub CLI gotowe")

# Pobierz token (z env, pliku lub gh CLI)
token = get_github_token(".env")

# Pobierz dane użytkownika
user = gh.get_user()
print(f"Zalogowany jako: {user}")

# Lista repozytoriów
repos = gh.list_repos(limit=10)
for repo in repos:
    print(f"  {repo['name']}: {repo['url']}")

# Klonowanie URL z tokenem
def get_clone_url(repo: str, token: str) -> str:
    """Zwraca URL do klonowania z tokenem."""
    return f"https://{token}@github.com/{repo}.git"
```

### Pełny przykład — konfiguracja środowiska

```python
import os
from env2mcp import EnvConfig, GitHubCLI

def setup_environment():
    """Setup env for MCP project."""
    config = EnvConfig(".env")

    # Sprawdź wymagane zmienne
    required = ["OPENROUTER_API_KEY", "GITHUB_PAT"]
    missing = [k for k in required if k not in config]

    if missing:
        print(f"Brakujące zmienne: {missing}")

        # Spróbuj pobrać GitHub token z gh CLI
        if "GITHUB_PAT" in missing:
            gh = GitHubCLI()
            if gh.is_available() and gh.get_auth_status()["authenticated"]:
                token = gh.get_token()
                if token:
                    config["GITHUB_PAT"] = token
                    user = gh.get_user()
                    if user:
                        config["GITHUB_USER"] = user
                    config.save()
                    print(f"GitHub skonfigurowany dla: {user}")

    # Załaduj do środowiska
    for key, value in config.items():
        os.environ.setdefault(key, value)

    return config

if __name__ == "__main__":
    cfg = setup_environment()
    print(f"GitHub user: {cfg.get('GITHUB_USER')}")
```

---

## Scenariusze użycia

### Scenariusz 1: Pierwsza konfiguracja projektu

```bash
# 1. Klonuj repo
 git clone <repo-url>
cd mcp

# 2. Skonfiguruj GitHub
make setup-github

# 3. Sprawdź czy działa
env2mcp github status
env2mcp github repos --limit 5
```

### Scenariusz 2: Dodanie nowego tokena

```bash
# Jeśli token wygasł lub chcesz zmienić konto
env2mcp github logout
env2mcp github login

# Lub ręcznie
env2mcp env set GITHUB_PAT "ghp_nowy-token"
```

### Scenariusz 3: Użycie w skrypcie deploy

```bash
#!/bin/bash
# scripts/deploy.sh

# Załaduj zmienne z .env
eval "$(env2mcp env export)"

# Użyj w docker-compose
export GITHUB_PAT=$(env2mcp env get GITHUB_PAT --show)
docker-compose up -d
```

### Scenariusz 4: Migracja konfiguracji

```python
# migrate_config.py
from env2mcp import EnvConfig

# Stary format
old_config = EnvConfig(".env.old")

# Nowy format
new_config = EnvConfig(".env")

# Przenieś kluczowe zmienne
for key in ["GITHUB_PAT", "OPENROUTER_API_KEY", "LLM_MODEL"]:
    if key in old_config:
        new_config[key] = old_config[key]

new_config.save()
print("Migracja zakończona")
```

---

## Struktura `.env`

Po konfiguracji przez `env2mcp`, plik `.env` ma uporządkowaną strukturę:

```bash
# Generated by env2mcp v0.1.3
# /home/user/projects/mcp/.env

# GitHub Configuration
GITHUB_PAT="ghp_xxxxxxxxxxxxxxxxxxxx"
GITHUB_USER="twoj-login"

# LLM Configuration
OPENROUTER_API_KEY="sk-or-v1-..."
LLM_MODEL="openrouter/x-ai/grok-code-fast-1"
LLM_PROVIDER="openrouter-lite"

# MCP Configuration
WEBUI_API_KEY="sk-mcp-default-dev-key"
MCP_GATEWAY_URL="http://mcp-gateway:9000"
GIT_PROXY_URL="http://mcp-git-proxy:8080"

# Other Configuration
OPENWEBUI_AUTH="False"
```

Funkcje:
- Automatyczny backup (`.env.backup`)
- Sekcje tematyczne
- Wrażliwe dane są czytelnie oznaczone

---

## Troubleshooting

### Problem: `gh` CLI nie jest znalezione

```bash
# Instalacja na różnych systemach

# macOS
brew install gh

# Ubuntu/Debian
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Windows (z admin)
winget install --id GitHub.cli
```

### Problem: Token nie działa

```bash
# Sprawdź czy token ma wymagane scope
env2mcp github status

# Sprawdź czy nie wygasł
gh auth status

# Wygeneruj nowy token na https://github.com/settings/tokens
# Wymagane scope: repo (dostęp do repozytoriów)
```

### Problem: `env2mcp` nie jest dostępne

```bash
# Sprawdź instalacj
which env2mcp
pip list | grep env2mcp

# Reinstalacja
pip uninstall env2mcp
pip install -e ./env2mcp
```

---

## Powiązane dokumentacje

- `docs/USAGE.md` — Główna dokumentacja MCP z przykładami użycia
- `docs/PRODUCT.md` — Architektura systemu
- `git2mcp/README.md` — Pakiet do operacji git
- https://cli.github.com/ — Dokumentacja GitHub CLI
- https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token — Tworzenie PAT
