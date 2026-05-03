FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Configure git to trust all directories (needed for Docker volume mounts with different ownership)
RUN git config --global --add safe.directory '*'

COPY mcp-git-proxy/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-git-proxy/server.py .
COPY git2mcp /app/git2mcp

EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
