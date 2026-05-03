#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

GATEWAY_URL="${GATEWAY_URL:-http://localhost:9000}"
API_KEY="${WEBUI_API_KEY:-sk-mcp-default-dev-key}"

REPO=""
GH_OWNER=""
BRANCH="main"
TASK="Refaktoryzuj etap 1: uprość strukturę, popraw nazewnictwo, dodaj typowanie bez zmian API publicznego."
TEST_COMMAND="python3 -m compileall -q ."
REMOTE="origin"
LIMIT=100
SHOW_TOP=10
EXECUTE=0
PUSH=0
OPEN_PR=0
DRAFT=1

usage() {
  cat <<'EOF'
Użycie:
  bash scripts/refactor-last-repo.sh [opcje]

Opcje:
  --repo owner/repo        Użyj konkretnego repo zamiast auto-wyboru z GitHub.
  --owner <owner>          Właściciel dla auto-wyboru (domyślnie: aktualny użytkownik gh).
  --branch <branch>        Branch bazowy (domyślnie: main).
  --task "..."             Zadanie refaktoryzacji dla modelu refactor.
  --test "..."             Komenda testowa (domyślnie: python3 -m compileall -q .).
  --remote <name>          Remote do push (domyślnie: origin).
  --limit <n>              Ile repo pobrać z GitHub do sortowania (domyślnie: 100).
  --show-top <n>           Ile pozycji pokazać w podglądzie rankingowym (domyślnie: 10).
  --execute                Wykonaj refactor + commit (w gateway: Execute=true).
  --push                   Wymuś Push=true (działa tylko razem z --execute).
  --pr                     Wymuś PR=true (działa tylko razem z --execute i --push).
  --no-draft               Draft=false (domyślnie Draft=true).
  --api-key <key>          Nadpisz WEBUI_API_KEY.
  --gateway <url>          Nadpisz URL gateway (domyślnie: http://localhost:9000).
  -h, --help               Pomoc.

Przykłady:
  bash scripts/refactor-last-repo.sh
  bash scripts/refactor-last-repo.sh --execute --push --pr
  bash scripts/refactor-last-repo.sh --repo semcod/mcp --execute --task "Etap 2 refaktoryzacji gateway"
EOF
}

strip_quotes() {
  local value="$1"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "$value"
}

load_env_defaults() {
  local env_file="$ROOT_DIR/.env"
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi

  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    line="${line#export }"
    if [[ ! "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      continue
    fi

    local key="${line%%=*}"
    local raw_val="${line#*=}"
    local value
    value="$(strip_quotes "$raw_val")"

    if [[ -z "${!key:-}" ]]; then
      export "$key=$value"
    fi
  done < "$env_file"

  if [[ -z "${WEBUI_API_KEY:-}" && -n "${API_KEY:-}" ]]; then
    WEBUI_API_KEY="$API_KEY"
  fi
  API_KEY="${WEBUI_API_KEY:-$API_KEY}"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Brak wymaganej komendy: $1" >&2
    exit 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)
        REPO="$2"; shift 2 ;;
      --owner)
        GH_OWNER="$2"; shift 2 ;;
      --branch)
        BRANCH="$2"; shift 2 ;;
      --task)
        TASK="$2"; shift 2 ;;
      --test)
        TEST_COMMAND="$2"; shift 2 ;;
      --remote)
        REMOTE="$2"; shift 2 ;;
      --limit)
        LIMIT="$2"; shift 2 ;;
      --show-top)
        SHOW_TOP="$2"; shift 2 ;;
      --execute)
        EXECUTE=1; shift ;;
      --push)
        PUSH=1; shift ;;
      --pr)
        OPEN_PR=1; shift ;;
      --no-draft)
        DRAFT=0; shift ;;
      --api-key)
        API_KEY="$2"; shift 2 ;;
      --gateway)
        GATEWAY_URL="$2"; shift 2 ;;
      -h|--help)
        usage; exit 0 ;;
      *)
        echo "Nieznana opcja: $1" >&2
        usage
        exit 1 ;;
    esac
  done

  if [[ "$EXECUTE" -eq 0 ]]; then
    PUSH=0
    OPEN_PR=0
  fi

  if [[ "$PUSH" -eq 0 ]]; then
    OPEN_PR=0
  fi
}

resolve_last_repo() {
  if [[ -n "$REPO" ]]; then
    return 0
  fi

  require_cmd gh

  local owner="$GH_OWNER"
  if [[ -z "$owner" ]]; then
    owner="$(gh api user --jq .login)"
  fi

  local repos_json
  repos_json="$(gh repo list "$owner" --limit "$LIMIT" --json nameWithOwner,pushedAt,url)"

  REPO="$(printf '%s' "$repos_json" | jq -r 'sort_by(.pushedAt) | reverse | .[0].nameWithOwner // empty')"
  if [[ -z "$REPO" ]]; then
    echo "Nie udało się wybrać repo z GitHub (sprawdź gh auth)." >&2
    exit 1
  fi

  echo "Top $SHOW_TOP ostatnio aktualizowanych repo (GitHub):"
  printf '%s' "$repos_json" | jq -r --argjson top "$SHOW_TOP" '
    sort_by(.pushedAt) | reverse | .[0:$top] |
    .[] | "- \(.pushedAt)  \(.nameWithOwner)"'
}

check_gateway() {
  require_cmd curl
  require_cmd jq

  if [[ -z "$API_KEY" ]]; then
    echo "Brak API key. Ustaw WEBUI_API_KEY lub użyj --api-key." >&2
    exit 1
  fi

  curl -fsS "$GATEWAY_URL/health" >/dev/null
  curl -fsS -H "Authorization: Bearer $API_KEY" "$GATEWAY_URL/v1/models" >/dev/null
}

post_chat_completion() {
  local model="$1"
  local prompt="$2"
  local response_file="$3"

  local payload
  payload="$(jq -n \
    --arg model "$model" \
    --arg content "$prompt" \
    '{model:$model,stream:false,messages:[{role:"user",content:$content}]}')"

  curl -fsS -X POST "$GATEWAY_URL/v1/chat/completions" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$payload" > "$response_file"
}

extract_result_content() {
  local response_file="$1"
  local result_file="$2"

  local content
  content="$(jq -r '.choices[0].message.content // ""' "$response_file")"

  if [[ -z "$content" ]]; then
    jq -n '{error:"Pusta odpowiedź modelu", raw_response:true}' > "$result_file"
    return 0
  fi

  if printf '%s' "$content" | jq -e . >/dev/null 2>&1; then
    printf '%s' "$content" | jq '.' > "$result_file"
  else
    jq -n --arg raw_content "$content" '{raw_content:$raw_content}' > "$result_file"
  fi
}

print_analyze_summary() {
  local result_file="$1"
  echo
  echo "Analiza gotowa (propozycja etapów):"
  jq -r '
    if .analysis then
      "- repo_id: \(.repo_id // "?")\n- pliki: \(.analysis.metrics.file_count // "?")\n- linie: \(.analysis.metrics.total_lines // "?")"
    elif .raw_content then
      "- surowa odpowiedź modelu zapisana (raw_content)"
    else
      "- wynik zapisany (sprawdź plik JSON)"
    end
  ' "$result_file"
}

print_refactor_summary() {
  local result_file="$1"
  echo
  echo "Wynik wykonania refaktoryzacji:"
  jq -r '
    if .execution then
      "- committed: \(.execution.committed // false)\n- pushed: \(.execution.pushed // false)\n- draft_branch: \(.execution.draft_branch.branch // "-")\n- pr_url: \(.execution.pull_request.url // "-")"
    elif .raw_content then
      "- surowa odpowiedź modelu zapisana (raw_content)"
    else
      "- wynik zapisany (sprawdź plik JSON)"
    end
  ' "$result_file"
}

main() {
  load_env_defaults
  parse_args "$@"
  resolve_last_repo
  check_gateway

  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  local run_dir="$ROOT_DIR/output/refactor-last-repo-$ts"
  mkdir -p "$run_dir"

  echo
  echo "Repo wybrane do pracy: $REPO"
  echo "Gateway: $GATEWAY_URL"
  echo "Artifacts: $run_dir"

  local analyze_prompt
  analyze_prompt="Repo: $REPO
Repo URL: $REPO
Branch: $BRANCH
Zadanie: Zaproponuj kolejne etapy refaktoryzacji w modelu iteracyjnym (Etap 1/2/3), z priorytetami, ryzykami i kryteriami akceptacji."

  post_chat_completion "mcp-skills/analyze" "$analyze_prompt" "$run_dir/analyze.response.json"
  extract_result_content "$run_dir/analyze.response.json" "$run_dir/analyze.result.json"
  print_analyze_summary "$run_dir/analyze.result.json"

  if [[ "$EXECUTE" -eq 0 ]]; then
    echo
    echo "Tryb analyze-only zakończony."
    echo "Aby wdrożyć zmiany: uruchom ponownie z --execute [--push --pr]."
    return 0
  fi

  local draft_name="refactor-${REPO//\//-}-$ts"
  local refactor_prompt
  refactor_prompt="Repo: $REPO
Repo URL: $REPO
Branch: $BRANCH
Execute: true
Push: $([[ "$PUSH" -eq 1 ]] && echo true || echo false)
Remote: $REMOTE
Draft: $([[ "$DRAFT" -eq 1 ]] && echo true || echo false)
Draft name: $draft_name
PR: $([[ "$OPEN_PR" -eq 1 ]] && echo true || echo false)
Test: $TEST_COMMAND
Zadanie: $TASK"

  post_chat_completion "mcp-skills/refactor" "$refactor_prompt" "$run_dir/refactor.response.json"
  extract_result_content "$run_dir/refactor.response.json" "$run_dir/refactor.result.json"
  print_refactor_summary "$run_dir/refactor.result.json"

  echo
  echo "Gotowe. Pliki wynikowe:"
  echo "- $run_dir/analyze.response.json"
  echo "- $run_dir/analyze.result.json"
  echo "- $run_dir/refactor.response.json"
  echo "- $run_dir/refactor.result.json"
}

main "$@"
