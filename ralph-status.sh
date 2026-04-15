#!/bin/bash
# Ralph Loop Status Check
# ======================
# Quick status check for Ralph Loop observability data

OBS_DIR="${RALPH_OBS_DIR:-.ralph-obs}"
STATE_LOG="$OBS_DIR/state.json"
HEALTH_LOG="$OBS_DIR/health.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Check if observability data exists
if [ ! -f "$STATE_LOG" ]; then
  echo -e "${YELLOW}No Ralph Loop observability data found${NC}"
  echo "Start the loop: ./ralph-v2.sh <iterations>"
  exit 0
fi

echo -e "${BLUE}Ralph Loop Status${NC}"
echo ""

# Get current state (safe with defaults)
current_task=$(cat "$STATE_LOG" | jq -r '.current_task // "none"' 2>/dev/null || echo "none")
stuck_count=$(cat "$STATE_LOG" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")
total_failed=$(cat "$STATE_LOG" | jq -r '.total_failed // 0' 2>/dev/null || echo "0")
last_successful=$(cat "$STATE_LOG" | jq -r '.last_successful // "never"' 2>/dev/null || echo "never")

echo -e "Current Task: ${CYAN}${current_task}${NC}"
echo -e "Stuck Count:  ${YELLOW}${stuck_count}${NC} / 5"
echo -e "Total Failed: ${RED}${total_failed}${NC}"
echo -e "Last Success: ${GREEN}${last_successful}${NC}"
echo ""

# Check for recent errors
if [ -f "$HEALTH_LOG" ]; then
  recent_errors=$(tail -10 "$HEALTH_LOG" 2>/dev/null | grep -c "\[ERROR\]" || echo "0")
  if [ "$recent_errors" -gt 0 ]; then
    echo -e "${RED}⚠ Recent errors detected (${recent_errors} in last 10 events)${NC}"
    tail -10 "$HEALTH_LOG" 2>/dev/null | grep "\[ERROR\]" | tail -3
    echo ""
  fi
fi

# Status assessment
if [ "$stuck_count" -ge 3 ]; then
  echo -e "${RED}⚠ WARNING: Loop is stuck on the same task${NC}"
  echo "   Consider manual intervention"
elif [ "$stuck_count" -ge 1 ]; then
  echo -e "${YELLOW}⚠ Loop encountering some failures${NC}"
  echo "   Monitoring recommended"
else
  echo -e "${GREEN}✓ Loop running smoothly${NC}"
fi

echo ""
echo "Run './ralph-analyze.sh report' for detailed analysis"
