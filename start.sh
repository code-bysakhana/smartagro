#!/usr/bin/env bash
# SmartAgro v3 — Ubuntu/Linux Startup
set -e
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'; BOLD='\033[1m'
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "\n${GREEN}${BOLD}  SmartAgro v3 — Starting up${NC}\n"

# Check deps
command -v python3 &>/dev/null || { echo "Install python3: sudo apt install python3 python3-pip"; exit 1; }
command -v node    &>/dev/null || { echo "Install nodejs: sudo apt install nodejs npm"; exit 1; }

# Backend
echo -e "${CYAN}[1/3] Installing Python dependencies…${NC}"
cd "$ROOT/backend"
pip3 install -q -r requirements.txt
[ -f .env ] && export $(grep -v '^#' .env | grep -v '^\s*$' | xargs) 2>/dev/null || true

echo -e "${CYAN}[2/3] Starting Flask backend (port 5000)…${NC}"
python3 app.py > /tmp/smartagro_backend.log 2>&1 &
BPID=$!
echo -e "${GREEN}✓ Backend PID $BPID${NC}"
echo "  Logs: tail -f /tmp/smartagro_backend.log"

# Wait for backend
echo -n "  Waiting for backend"
for i in $(seq 1 15); do
  curl -s http://localhost:5000/api/ping > /dev/null 2>&1 && echo -e " ${GREEN}✓${NC}" && break
  echo -n "."; sleep 1
done

# Frontend
echo -e "${CYAN}[3/3] Starting React frontend (port 3000)…${NC}"
cd "$ROOT/frontend"
[ ! -d node_modules ] && npm install --silent
BROWSER=none npm start > /tmp/smartagro_frontend.log 2>&1 &
FPID=$!
echo -e "${GREEN}✓ Frontend PID $FPID${NC}"

echo -e "\n${BOLD}  ─────────────────────────────────────${NC}"
echo -e "  ${GREEN}Frontend${NC} : http://localhost:3000"
echo -e "  ${GREEN}Backend${NC}  : http://localhost:5000"
echo -e "  ${GREEN}API ping${NC} : http://localhost:5000/api/ping"
echo -e "${BOLD}  ─────────────────────────────────────${NC}"
echo -e "\n  Press ${BOLD}Ctrl+C${NC} to stop\n"

cleanup() { kill $BPID $FPID 2>/dev/null||true; echo -e "\n${YELLOW}Stopped.${NC}"; }
trap cleanup EXIT INT TERM
wait
