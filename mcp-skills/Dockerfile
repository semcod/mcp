FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY mcp/mcp-skills/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install redsl from local source
COPY redsl /tmp/redsl
RUN pip install --no-cache-dir /tmp/redsl

# Copy redsl config directory (excluded from pip package)
RUN cp -r /tmp/redsl/config /usr/local/lib/python3.11/site-packages/config \
    && rm -rf /tmp/redsl

# Pre-install commonly used semcod CLI tools so first /tools/run is fast.
# Best-effort: any individual missing/broken package falls back to runtime
# auto_install via /tools/run.
RUN for pkg in sumd code2llm code2docs code2logic code2schema redup pyqual domd; do \
        pip install --no-cache-dir "$pkg" || echo "WARN: failed to pre-install $pkg"; \
    done

COPY mcp/mcp-skills/server.py .

EXPOSE 8080

CMD ["python", "server.py"]
