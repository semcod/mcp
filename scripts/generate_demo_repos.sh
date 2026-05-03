#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCES_DIR="$ROOT_DIR/repos/generated-sources"
REMOTES_DIR="$ROOT_DIR/repos/generated-remotes"
PROXY_REMOTES_DIR="/host-semcod/mcp/repos/generated-remotes"

mkdir -p "$SOURCES_DIR" "$REMOTES_DIR"

create_repo() {
  local repo_name="$1"
  local repo_path="$SOURCES_DIR/$repo_name"
  local remote_path="$REMOTES_DIR/$repo_name.git"

  rm -rf "$repo_path" "$remote_path"
  mkdir -p "$repo_path"

  git init "$repo_path" >/dev/null
  git -C "$repo_path" branch -M main

  case "$repo_name" in
    refactor-lab)
      mkdir -p "$repo_path/app"
      cat >"$repo_path/app/utils.py" <<'PY'
def normalize_items(items):
    result = []
    for item in items:
        if isinstance(item, str):
            value = item.strip().lower()
            if value:
                result.append(value)
        elif item is None:
            continue
        else:
            value = str(item).strip().lower()
            if value:
                result.append(value)
    return sorted(list(set(result)))


def score_payload(payload):
    score = 0
    for key, value in payload.items():
        if key.startswith("is_") and value:
            score += 5
        elif isinstance(value, int):
            score += value
        elif isinstance(value, str) and value:
            score += len(value)
    return score
PY
      cat >"$repo_path/app/service.py" <<'PY'
from app.utils import normalize_items, score_payload


def build_report(payload):
    tags = normalize_items(payload.get("tags", []))
    score = score_payload(payload)
    return {
        "tags": tags,
        "score": score,
        "summary": f"Report for {payload.get('name', 'unknown')}",
    }
PY
      cat >"$repo_path/README.md" <<'MD'
# refactor-lab

Small Python project with intentionally compact logic for refactoring demos.
MD
      ;;
    migration-lab)
      mkdir -p "$repo_path/src"
      cat >"$repo_path/src/main.py" <<'PY'
import json


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run(config_path):
    cfg = load_config(config_path)
    print("service:", cfg.get("service", "unknown"))


if __name__ == "__main__":
    run("config.json")
PY
      cat >"$repo_path/setup.py" <<'PY'
from setuptools import setup, find_packages

setup(
    name="migration-lab",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests==2.31.0"],
)
PY
      cat >"$repo_path/requirements.txt" <<'TXT'
requests==2.31.0
TXT
      cat >"$repo_path/config.json" <<'JSON'
{
  "service": "migration-lab",
  "mode": "legacy"
}
JSON
      ;;
    integration-lab)
      mkdir -p "$repo_path/integrations" "$repo_path/services"
      cat >"$repo_path/services/users.py" <<'PY'
def fetch_users():
    return [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
PY
      cat >"$repo_path/services/orders.py" <<'PY'
def fetch_orders():
    return [
        {"id": 100, "user_id": 1, "total": 55.0},
        {"id": 101, "user_id": 2, "total": 34.5},
    ]
PY
      cat >"$repo_path/integrations/pipeline.py" <<'PY'
from services.users import fetch_users
from services.orders import fetch_orders


def build_user_totals():
    users = {u["id"]: u for u in fetch_users()}
    totals = {u_id: 0.0 for u_id in users}
    for order in fetch_orders():
        totals[order["user_id"]] += order["total"]

    result = []
    for user_id, amount in totals.items():
        result.append({
            "user": users[user_id]["name"],
            "total": amount,
        })
    return result
PY
      cat >"$repo_path/README.md" <<'MD'
# integration-lab

Repository used to demo integration-oriented refactoring plans.
MD
      ;;
    *)
      echo "Unknown repo: $repo_name" >&2
      return 1
      ;;
  esac

  git -C "$repo_path" add .
  git -C "$repo_path" -c user.name='demo-bot' -c user.email='demo@example.com' commit -m "seed: $repo_name" >/dev/null

  git init --bare "$remote_path" >/dev/null
  git -C "$repo_path" remote add origin "$remote_path"
  git -C "$repo_path" push -u origin main >/dev/null

  echo "$repo_name|$repo_path|$remote_path"
}

sync_to_proxy() {
  local repo_id="$1"
  local remote_path_for_proxy="$2"

  curl -fsS -X POST "http://localhost:8081/repos/sync" \
    -H 'Content-Type: application/json' \
    -d "{\"repo_id\":\"$repo_id\",\"repo_url\":\"$remote_path_for_proxy\",\"branch\":\"main\"}" >/dev/null
}

OUTPUT_LINES=()
OUTPUT_LINES+=("$(create_repo refactor-lab)")
OUTPUT_LINES+=("$(create_repo migration-lab)")
OUTPUT_LINES+=("$(create_repo integration-lab)")

echo "Generated repositories:"
for line in "${OUTPUT_LINES[@]}"; do
  IFS='|' read -r name path remote <<<"$line"
  echo "- $name"
  echo "  source: $path"
  echo "  remote: $remote"
done

if curl -fsS "http://localhost:8081/health" >/dev/null 2>&1; then
  sync_to_proxy "demo/refactor-lab" "$PROXY_REMOTES_DIR/refactor-lab.git"
  sync_to_proxy "demo/migration-lab" "$PROXY_REMOTES_DIR/migration-lab.git"
  sync_to_proxy "demo/integration-lab" "$PROXY_REMOTES_DIR/integration-lab.git"
  echo "Synced to mcp-git-proxy as: demo/refactor-lab, demo/migration-lab, demo/integration-lab"
else
  echo "mcp-git-proxy is not reachable on http://localhost:8081 (skip sync)."
fi
