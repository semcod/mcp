FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git gh \
    && rm -rf /var/lib/apt/lists/*

COPY env2mcp /tmp/env2mcp
COPY gh2mcp /tmp/gh2mcp

RUN pip install --no-cache-dir /tmp/env2mcp \
    && pip install --no-cache-dir /tmp/gh2mcp \
    && rm -rf /tmp/env2mcp /tmp/gh2mcp

EXPOSE 8079

CMD ["uvicorn", "gh2mcp.server:app", "--host", "0.0.0.0", "--port", "8079"]
