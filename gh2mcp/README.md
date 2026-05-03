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


## License

Licensed under Apache-2.0.
