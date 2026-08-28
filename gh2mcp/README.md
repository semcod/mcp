# gh2mcp

`gh2mcp` to lekka paczka Python używana przez stack MCP do synchronizacji tokenu GitHub z `gh` CLI do pliku `.env`.

## Funkcje

- pobranie tokenu przez `gh auth token`
- zapis `GITHUB_PAT` i `GITHUB_USER` do `.env` przez `env2mcp`
- endpoint HTTP dla integracji z `mcp-webui`
- opcjonalny tryb agenta (sync przy starcie i okresowo)

## Lokalne użycie CLI

```bash
pip install -e ./env2mcp
pip install -e ./gh2mcp

gh2mcp status
gh2mcp sync --force-gh-cli
gh2mcp agent --interval 300
```

## Docker

Kontener uruchamia API:

- `GET /health`
- `GET /status`
- `POST /sync/token`
- `POST /repo/last-pushed`

API nigdy nie zwraca pełnego tokenu. Zapis tokenu i organizacji jest domyślnie
wyłączony i wymaga `GH2MCP_ALLOW_MUTATION=1`; automatyczna synchronizacja przy
starcie wymaga dodatkowo `GH2MCP_SYNC_ON_START=true`. Port kontenera jest
domyślnie związany z `127.0.0.1`.


## License

Licensed under Apache-2.0.
