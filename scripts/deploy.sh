#!/bin/bash
# Deploy script dla Autonomicznego Agenta Refaktoryzacji MCP

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Porty z .env lub defaults
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a; source "$PROJECT_ROOT/.env"; set +a
fi
PORT_GIT_PROXY="${PORT_GIT_PROXY:-8081}"
PORT_DASHBOARD="${PORT_DASHBOARD:-8085}"
PORT_GATEWAY="${PORT_GATEWAY:-9000}"

echo "=========================================="
echo "MCP Autonomous Refactoring Agent - Deploy"
echo "=========================================="

# Kolory
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Sprawdzenie wymagań
check_requirements() {
    echo -e "${YELLOW}Checking requirements...${NC}"

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is required but not installed${NC}"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}Docker Compose is required but not installed${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ All requirements met${NC}"
}

# Setup katalogów
setup_directories() {
    echo -e "${YELLOW}Setting up directories...${NC}"

    mkdir -p "$PROJECT_ROOT/repos"
    mkdir -p "$PROJECT_ROOT/output"
    mkdir -p "$PROJECT_ROOT/logs"

    echo -e "${GREEN}✓ Directories created${NC}"
}

# Kopiowanie env jeśli nie istnieje
setup_env() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        echo -e "${YELLOW}Creating .env file from example...${NC}"
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        echo -e "${YELLOW}⚠ Please edit .env file with your configuration${NC}"
    fi
}

# Budowanie obrazów
build_images() {
    echo -e "${YELLOW}Building Docker images...${NC}"
    cd "$PROJECT_ROOT"
    docker-compose build --no-cache
    echo -e "${GREEN}✓ Images built${NC}"
}

# Uruchamianie serwisów
start_services() {
    echo -e "${YELLOW}Starting services...${NC}"
    cd "$PROJECT_ROOT"
    docker-compose up -d mcp-git-proxy mcp-skills dashboard
    echo -e "${GREEN}✓ Services started${NC}"
}

# Health check
health_check() {
    echo -e "${YELLOW}Running health checks...${NC}"

    sleep 3

    if docker ps | grep -q "mcp-skills-server"; then
        echo -e "${GREEN}✓ MCP Skills Server is running${NC}"
    else
        echo -e "${RED}✗ MCP Skills Server failed to start${NC}"
        docker-compose logs mcp-skills
        exit 1
    fi

    if docker ps | grep -q "mcp-git-proxy"; then
        echo -e "${GREEN}✓ MCP Git Proxy is running${NC}"
    else
        echo -e "${RED}✗ MCP Git Proxy failed to start${NC}"
        docker-compose logs mcp-git-proxy
        exit 1
    fi
}

# Główna funkcja
main() {
    check_requirements
    setup_directories
    setup_env
    build_images
    start_services
    health_check

    echo ""
    echo "=========================================="
    echo -e "${GREEN}Deploy completed successfully!${NC}"
    echo "=========================================="
    echo ""
    echo "Services available:"
    echo "  - MCP Git Proxy:    http://localhost:${PORT_GIT_PROXY}"
    echo "  - Dashboard:         http://localhost:${PORT_DASHBOARD}"
    echo "  - Gateway:           http://localhost:${PORT_GATEWAY}"
    echo ""
    echo "To view the dashboard:"
    echo "  open http://localhost:${PORT_DASHBOARD}"
    echo ""
    echo "To run the agent:"
    echo "  docker-compose run --rm llm-agent python agent_git2mcp.py --repo team/sample --source-path /host-repos/test/sample-project"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "To stop:"
    echo "  docker-compose down"
}

main "$@"
