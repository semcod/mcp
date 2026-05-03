FROM python:3.11-slim

WORKDIR /app

COPY mcp-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-gateway/server.py .
COPY mcp-gateway/tenants ./tenants

EXPOSE 9000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000"]
