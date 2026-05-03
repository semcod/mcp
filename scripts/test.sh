#!/bin/bash
# Test script dla MCP Autonomous Refactoring Agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Kolory
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "MCP Autonomous Refactoring Agent - Tests"
echo "=========================================="

# Test 1: Sprawdzenie struktury projektu
test_structure() {
    echo -e "${BLUE}Test 1: Project structure${NC}"

    local required_files=(
        "docker-compose.yml"
        "mcp-git-proxy/Dockerfile"
        "mcp-git-proxy/server.py"
        "mcp-skills/Dockerfile"
        "mcp-skills/server.py"
        "mcp-skills/requirements.txt"
        "git2mcp/client.py"
        "git2mcp/proxy.py"
        "llm-agent/Dockerfile"
        "llm-agent/agent.py"
        "llm-agent/agent_git2mcp.py"
        "llm-agent/requirements.txt"
    )

    for file in "${required_files[@]}"; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            echo -e "  ${GREEN}✓${NC} $file"
        else
            echo -e "  ${RED}✗ Missing: $file${NC}"
            return 1
        fi
    done
}

# Test 2: Sprawdzenie składni Python
test_python_syntax() {
    echo -e "${BLUE}Test 2: Python syntax${NC}"

    if python3 -m py_compile "$PROJECT_ROOT/mcp-skills/server.py" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} mcp-skills/server.py"
    else
        echo -e "  ${RED}✗ Syntax error in mcp-skills/server.py${NC}"
        return 1
    fi

    if python3 -m py_compile "$PROJECT_ROOT/llm-agent/agent.py" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} llm-agent/agent.py"
    else
        echo -e "  ${RED}✗ Syntax error in llm-agent/agent.py${NC}"
        return 1
    fi

    if python3 -m py_compile "$PROJECT_ROOT/llm-agent/agent_git2mcp.py" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} llm-agent/agent_git2mcp.py"
    else
        echo -e "  ${RED}✗ Syntax error in llm-agent/agent_git2mcp.py${NC}"
        return 1
    fi

    if python3 -m py_compile "$PROJECT_ROOT/mcp-git-proxy/server.py" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} mcp-git-proxy/server.py"
    else
        echo -e "  ${RED}✗ Syntax error in mcp-git-proxy/server.py${NC}"
        return 1
    fi
}

# Test 3: Sprawdzenie Docker
test_docker() {
    echo -e "${BLUE}Test 3: Docker validation${NC}"

    cd "$PROJECT_ROOT"

    if docker-compose config > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} docker-compose.yml is valid"
    else
        echo -e "  ${RED}✗ Invalid docker-compose.yml${NC}"
        return 1
    fi
}

# Test 4: Przygotowanie testowego repozytorium
test_repo_setup() {
    echo -e "${BLUE}Test 4: Test repository setup${NC}"

    TEST_REPO="$PROJECT_ROOT/repos/test/sample-project"
    mkdir -p "$TEST_REPO"

    # Stwórz przykładowy kod Python
    cat > "$TEST_REPO/main.py" << 'EOF'
"""Sample project for testing MCP Skills"""
import os
import sys
import json
import logging
from typing import Dict, List

class DataProcessor:
    """Main data processor class"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def process(self, data: List[Dict]) -> List[Dict]:
        results = []
        for item in data:
            processed = self._transform(item)
            results.append(processed)
        return results

    def _transform(self, item: Dict) -> Dict:
        return {k: v.upper() if isinstance(v, str) else v for k, v in item.items()}

def main():
    processor = DataProcessor({"debug": True})
    data = [{"name": "test", "value": 123}]
    results = processor.process(data)
    print(json.dumps(results))

if __name__ == "__main__":
    main()
EOF

    # Stwórz więcej plików
    for i in {1..5}; do
        cat > "$TEST_REPO/module_$i.py" << EOF
"""Module $i"""
import os
import sys
from typing import Dict, List

def function_$i(data: Dict) -> Dict:
    return {\"result\": data}
EOF
    done

    echo -e "  ${GREEN}✓${NC} Test repository created at repos/test/sample-project"
    find "$TEST_REPO" -name "*.py" | wc -l | xargs echo -e "  ${GREEN}✓${NC} Created files:"
}

# Test 5: End-to-end git2mcp workflow
test_git2mcp_workflow() {
    echo -e "${BLUE}Test 5: git2mcp end-to-end workflow${NC}"

    cd "$PROJECT_ROOT"
    docker-compose up -d mcp-git-proxy mcp-skills > /dev/null

    if docker ps | grep -q "mcp-git-proxy"; then
        echo -e "  ${GREEN}✓${NC} MCP Git Proxy is running"
    else
        echo -e "  ${RED}✗ MCP Git Proxy is not running${NC}"
        return 1
    fi

    docker-compose run --rm llm-agent python agent_git2mcp.py \
      --repo test/sample-project \
      --source-path /host-repos/test/sample-project \
      --branch main \
      --execute \
      --test-command "python -m compileall -q ." > /tmp/git2mcp-test.log

    if grep -q '"status": "analysis_complete"' /tmp/git2mcp-test.log; then
        echo -e "  ${GREEN}✓${NC} git2mcp workflow finished with analysis_complete"
    else
        echo -e "  ${RED}✗ git2mcp workflow did not complete successfully${NC}"
        cat /tmp/git2mcp-test.log
        return 1
    fi
}

# Test 6: Linting
# test_linting() {
#     echo -e "${BLUE}Test 6: Code linting${NC}"
#
#     if command -v pylint &> /dev/null; then
#         pylint "$PROJECT_ROOT/mcp-skills/server.py" --errors-only || true
#         pylint "$PROJECT_ROOT/llm-agent/agent.py" --errors-only || true
#     else
#         echo -e "  ${YELLOW}⚠${NC} pylint not installed, skipping"
#     fi
# }

# Główna funkcja
main() {
    test_structure
    test_python_syntax
    test_docker
    test_repo_setup
    test_git2mcp_workflow

    echo ""
    echo "=========================================="
    echo -e "${GREEN}All tests completed!${NC}"
    echo "=========================================="
}

main "$@"
