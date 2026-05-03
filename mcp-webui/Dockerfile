FROM python:3.11-slim

WORKDIR /app

COPY mcp-webui/requirements.txt .
COPY env2mcp /tmp/env2mcp
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir /tmp/env2mcp \
    && rm -rf /tmp/env2mcp

COPY mcp-webui/server.py .
COPY mcp-webui/templates ./templates

EXPOSE 8090
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8090"]
