FROM python:3.11-slim

WORKDIR /app

COPY mcp-gateway/requirements.txt .
COPY env2mcp /tmp/env2mcp
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir /tmp/env2mcp \
    && rm -rf /tmp/env2mcp

COPY mcp-gateway/server.py mcp-gateway/worker.py mcp-gateway/gateway_*.py mcp-gateway/dispatch_refactor.py mcp-gateway/render_tools.py mcp-gateway/render_system_actions.py mcp-gateway/render_refactor_actions.py mcp-gateway/chat_workflow_handlers.py ./
COPY mcp-gateway/tenants ./tenants

EXPOSE 9000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000"]
