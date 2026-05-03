# Autonomiczny Agent Refaktoryzacji MCP

System autonomicznej refaktoryzacji kodu oparty na Model Context Protocol (MCP), integrujący:
- **MCP Skills Server** - analiza kodu i metryki
- **MCP Git Server** - operacje na repozytoriach
- **LLM Agent** - podejmowanie decyzji refaktoryzacyjnych

## Architektura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  LLM Agent  │────▶│ MCP Skills  │     │  MCP Git    │
│             │◀────│  Server     │     │  Server     │
└─────────────┘     └─────────────┘     └─────────────┘
      │
      ▼
┌─────────────┐
│  LLM API    │
│ (OpenAI/    │
│  Ollama)    │
└─────────────┘
```

## Szybki Start

### 1. Wymagania

- Docker & Docker Compose
- Python 3.11+ (dla lokalnego uruchomienia)
- (Opcjonalnie) GitHub PAT - dla operacji na repo
- (Opcjonalnie) OpenAI API Key - dla zaawansowanej analizy LLM

### 2. Instalacja

```bash
# Klonowanie i setup
./scripts/deploy.sh
```

### 3. Konfiguracja

```bash
# Skopiuj przykładową konfigurację
cp .env.example .env

# Edytuj .env zgodnie z potrzebami
nano .env
```

### 4. Uruchomienie

```bash
# Uruchom wszystkie serwisy
docker-compose up -d

# Uruchom agenta z analizą repozytorium
docker-compose run --rm llm-agent python agent.py \
  --repo my-org/my-repo \
  --paths src/module1 src/module2 \
  --dry-run
```

## Struktura Projektu

```
.
├── docker-compose.yml          # Konfiguracja Docker
├── .env.example                # Przykładowa konfiguracja
├── README.md                   # Dokumentacja
│
├── mcp-skills/                 # MCP Skills Server
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py               # Implementacja narzędzi MCP
│
├── llm-agent/                  # Autonomiczny Agent
│   ├── Dockerfile
│   ├── requirements.txt
│   └── agent.py                # Logika agenta LLM
│
├── scripts/                    # Skrypty pomocnicze
│   ├── deploy.sh               # Deployment
│   └── test.sh                 # Testy
│
├── repos/                      # Sklonowane repozytoria (volume)
└── output/                     # Wyniki analizy (volume)
```

## MCP Skills - Narzędzia

### analyze_code_structure
Analiza struktury kodu dla podanych ścieżek:
- Liczba linii kodu
- Liczba importów
- Liczba funkcji i klas
- Podgląd kodu

### compute_metrics_for_repo
Metryki całego repozytorium:
- Całkowita liczba plików
- Całkowita liczba linii
- Średnia liczba linii na plik
- Liczba funkcji i klas

### detect_code_patterns
Wykrywanie wzorców i antywzorców:
- Duże pliki (>500 linii)
- Wysoka złożoność
- Najczęściej używane importy
- Potencjalne problemy

### recommend_refactoring
Rekomendacje refaktoryzacji:
- Priorytetyzacją zmian
- Sugestie podziału plików
- Sugestie organizacji kodu

## Przykłady Użycia

### Analiza lokalnego repozytorium

```bash
# Przygotuj testowe repozytorium
mkdir -p repos/my-project
cp -r /path/to/code/* repos/my-project/

# Uruchom analizę
docker-compose run --rm llm-agent python agent.py \
  --repo my-project \
  --dry-run
```

### Użycie z OpenAI

```bash
# W .env ustaw:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...

docker-compose run --rm llm-agent python agent.py \
  --repo my-org/my-repo \
  --llm openai \
  --dry-run
```

### Użycie z lokalnym Ollama

```bash
# Uruchom Ollama
docker-compose --profile ollama up -d ollama

# W .env ustaw:
# LLM_PROVIDER=ollama
# OLLAMA_HOST=http://ollama:11434

docker-compose run --rm llm-agent python agent.py \
  --repo my-project \
  --llm ollama
```

## Workflow Autonomicznej Refaktoryzacji

1. **Analiza** - Agent pobiera metryki i wykrywa problemy
2. **Planowanie** - LLM generuje plan refaktoryzacji
3. **Weryfikacja** - Plan jest weryfikowany pod kątem ryzyka
4. **Wykonanie** (opcjonalnie) - Zmiany są aplikowane przez MCP Git
5. **Walidacja** - Testy weryfikują poprawność zmian

## Testowanie

```bash
# Uruchom wszystkie testy
./scripts/test.sh

# Sprawdź strukturę
ls -la repos/ output/

# Sprawdź logi
docker-compose logs -f mcp-skills
```

## Rozwój

### Lokalne uruchomienie serwera MCP Skills

```bash
cd mcp-skills
pip install -r requirements.txt
python server.py
```

### Lokalne uruchomienie agenta

```bash
cd llm-agent
pip install -r requirements.txt
python agent.py --repo test/project --dry-run
```

## Dokumentacja MCP

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP GitHub Server](https://github.com/github/github-mcp-server)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## Licencja

Zobacz plik LICENSE.

## License

Licensed under Apache-2.0.
