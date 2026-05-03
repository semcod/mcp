FROM python:3.11-slim

WORKDIR /app

COPY mcp-docs/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-docs/server.py .
COPY docs /docs
COPY README.md /docs/README.md

EXPOSE 8090

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8090"]
