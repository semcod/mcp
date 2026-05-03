#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCES_DIR="$ROOT_DIR/repos/generated-sources"
REMOTES_DIR="$ROOT_DIR/repos/generated-remotes"
PROXY_REMOTES_DIR="/host-semcod/mcp/repos/generated-remotes"
ENV_FILE="$ROOT_DIR/.env"

GH_DEMO_PROVIDER="${GH_DEMO_PROVIDER:-auto}"
GH_DEMO_PREFIX="${GH_DEMO_PREFIX:-mcp-demo}"
GH_DEMO_VISIBILITY="${GH_DEMO_VISIBILITY:-private}"

# Porty z .env lub defaults
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi
PORT_GIT_PROXY="${PORT_GIT_PROXY:-8081}"

DEMO_REPOS=(
  "refactor-lab"
  "migration-lab"
  "integration-lab"
)

ACTIVE_PROVIDER="local"
GH_TOKEN=""
GH_USER=""

mkdir -p "$SOURCES_DIR" "$REMOTES_DIR"

read_env_value() {
  local key="$1"
  if [ ! -f "$ENV_FILE" ]; then
    return 1
  fi
  local line
  line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)"
  if [ -z "$line" ]; then
    return 1
  fi
  local value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

resolve_github_token() {
  local token="${GITHUB_TOKEN:-${GITHUB_PAT:-}}"
  if [ -z "$token" ] && command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then
      token="$(gh auth token 2>/dev/null || true)"
    fi
  fi
  if [ -z "$token" ]; then
    token="$(read_env_value GITHUB_TOKEN || true)"
  fi
  if [ -z "$token" ]; then
    token="$(read_env_value GITHUB_PAT || true)"
  fi
  printf '%s' "$token"
}

resolve_github_user() {
  local user="${GITHUB_USER:-}"
  if [ -z "$user" ]; then
    user="$(read_env_value GITHUB_USER || true)"
  fi
  if [ -z "$user" ] && command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then
      user="$(gh api user -q .login 2>/dev/null || true)"
    fi
  fi
  printf '%s' "$user"
}

select_provider() {
  local requested="$GH_DEMO_PROVIDER"
  requested="${requested,,}"
  if [ "$requested" != "auto" ] && [ "$requested" != "local" ] && [ "$requested" != "github" ]; then
    echo "Invalid GH_DEMO_PROVIDER=$GH_DEMO_PROVIDER (expected auto|local|github), falling back to auto."
    requested="auto"
  fi

  GH_TOKEN="$(resolve_github_token)"
  GH_USER="$(resolve_github_user)"

  local gh_ok="false"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh_ok="true"
  fi

  if [ "$requested" = "local" ]; then
    ACTIVE_PROVIDER="local"
    return
  fi

  if [ "$gh_ok" = "true" ] && [ -n "$GH_TOKEN" ] && [ -n "$GH_USER" ]; then
    ACTIVE_PROVIDER="github"
    return
  fi

  if [ "$requested" = "github" ]; then
    echo "GitHub provider requested, but gh/token/user not fully available; falling back to local remotes."
  fi
  ACTIVE_PROVIDER="local"
}


seed_repo_files() {
  local repo_name="$1"
  local repo_path="$2"

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
}

create_repo() {
  local repo_name="$1"
  local repo_path="$SOURCES_DIR/$repo_name"

  rm -rf "$repo_path"
  mkdir -p "$repo_path"

  git init "$repo_path" >/dev/null
  git -C "$repo_path" branch -M main

  seed_repo_files "$repo_name" "$repo_path"

  git -C "$repo_path" add .
  git -C "$repo_path" -c user.name='demo-bot' -c user.email='demo@example.com' commit -m "seed: $repo_name" >/dev/null

  printf '%s' "$repo_path"
}


create_local_remote() {
  local repo_name="$1"
  local repo_path="$2"
  local remote_path="$REMOTES_DIR/$repo_name.git"

  rm -rf "$remote_path"
  git init --bare "$remote_path" >/dev/null

  git -C "$repo_path" remote remove origin >/dev/null 2>&1 || true
  git -C "$repo_path" remote add origin "$remote_path"
  git -C "$repo_path" push -u origin main >/dev/null

  local remote_for_proxy="$PROXY_REMOTES_DIR/$repo_name.git"
  printf '%s|%s|%s' "$remote_path" "$remote_for_proxy" "local"
}


create_github_remote() {
  local repo_name="$1"
  local repo_path="$2"
  local prefix_trimmed="${GH_DEMO_PREFIX%-}"
  local github_repo_name="${repo_name}"
  if [ -n "$prefix_trimmed" ]; then
    github_repo_name="${prefix_trimmed}-${repo_name}"
  fi

  local full_name="${GH_USER}/${github_repo_name}"
  local clone_url="https://github.com/${full_name}.git"
  local visibility_flag="--private"
  if [ "${GH_DEMO_VISIBILITY,,}" = "public" ]; then
    visibility_flag="--public"
  fi

  gh auth setup-git >/dev/null 2>&1 || true

  git -C "$repo_path" remote remove origin >/dev/null 2>&1 || true
  if gh repo view "$full_name" >/dev/null 2>&1; then
    echo "Reusing existing GitHub repo: $full_name" >&2
    git -C "$repo_path" remote add origin "$clone_url" || return 1
    git -C "$repo_path" push -u --force origin main >/dev/null || return 1
  else
    gh repo create "$full_name" "$visibility_flag" --source "$repo_path" --remote origin --push >/dev/null || return 1
    echo "Created GitHub repo: $full_name" >&2
  fi

  local proxy_clone_url="$clone_url"
  if [ -n "$GH_TOKEN" ]; then
    proxy_clone_url="https://x-access-token:${GH_TOKEN}@github.com/${full_name}.git"
  fi

  printf '%s|%s|%s' "$clone_url" "$proxy_clone_url" "github"
}


create_repo_bundle() {
  local repo_name="$1"
  local repo_path
  if ! repo_path="$(create_repo "$repo_name")"; then
    return 1
  fi

  local remote_data
  if [ "$ACTIVE_PROVIDER" = "github" ]; then
    if ! remote_data="$(create_github_remote "$repo_name" "$repo_path")"; then
      return 1
    fi
  else
    if ! remote_data="$(create_local_remote "$repo_name" "$repo_path")"; then
      return 1
    fi
  fi

  printf '%s|%s|%s' "$repo_name" "$repo_path" "$remote_data"
}


sync_to_proxy() {
  local repo_id="$1"
  local remote_url_for_proxy="$2"

  if command -v docker >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' | grep -q '^mcp-git-proxy$'; then
      docker exec mcp-git-proxy sh -lc "rm -rf /git-repos/${repo_id}" >/dev/null 2>&1 || true
    fi
  fi

  curl -fsS -X POST "http://localhost:${PORT_GIT_PROXY}/repos/sync" \
    -H 'Content-Type: application/json' \
    -d "{\"repo_id\":\"$repo_id\",\"repo_url\":\"$remote_url_for_proxy\",\"branch\":\"main\"}" >/dev/null
}


select_provider
echo "Demo repo provider: $ACTIVE_PROVIDER (requested: $GH_DEMO_PROVIDER)"
if [ "$ACTIVE_PROVIDER" = "github" ]; then
  echo "GitHub owner: $GH_USER"
fi

OUTPUT_LINES=()
for repo_name in "${DEMO_REPOS[@]}"; do
  repo_line="$(create_repo_bundle "$repo_name")" || {
    echo "Failed to prepare demo repository: $repo_name" >&2
    exit 1
  }
  OUTPUT_LINES+=("$repo_line")
done

echo "Generated repositories:"
for line in "${OUTPUT_LINES[@]}"; do
  IFS='|' read -r name path remote_display remote_for_proxy provider <<<"$line"
  echo "- $name"
  echo "  source: $path"
  echo "  remote: $remote_display"
  echo "  provider: $provider"
done

if curl -fsS "http://localhost:${PORT_GIT_PROXY}/health" >/dev/null 2>&1; then
  for line in "${OUTPUT_LINES[@]}"; do
    IFS='|' read -r name path remote_display remote_for_proxy provider <<<"$line"
    sync_to_proxy "demo/$name" "$remote_for_proxy"
  done
  echo "Synced to mcp-git-proxy as: demo/refactor-lab, demo/migration-lab, demo/integration-lab"
else
  echo "mcp-git-proxy is not reachable on http://localhost:${PORT_GIT_PROXY} (skip sync)."
fi
