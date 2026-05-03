FROM python:3.11-slim

WORKDIR /app

COPY mcp-webui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-webui/server.py .
COPY mcp-webui/templates ./templates

EXPOSE 8090
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8090"]
