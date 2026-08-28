# syntax=docker/dockerfile:1.5
FROM python:3.11-slim

WORKDIR /app

# System deps — cached as long as this layer doesn't change
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt — cached until file changes
COPY mcp/mcp-skills/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# redsl from local source — cached until redsl/ source changes
COPY redsl /tmp/redsl
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install /tmp/redsl \
    && cp -r /tmp/redsl/config /usr/local/lib/python3.11/site-packages/config \
    && rm -rf /tmp/redsl

# Pre-install semcod tools — cached; add psutil for code2llm
RUN --mount=type=cache,target=/root/.cache/pip \
    for pkg in sumd code2llm code2docs code2logic code2schema redup pyqual domd psutil; do \
        pip install "$pkg" || echo "WARN: failed to pre-install $pkg"; \
    done

# server.py is bind-mounted at runtime; include here only as fallback
COPY mcp/mcp-skills/server.py .

EXPOSE 8080

CMD ["python", "server.py"]
