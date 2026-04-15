#!/bin/bash
# Ralph Loop Watch - Real-time observability monitoring
# ======================================================

OBS_DIR="${RALPH_OBS_DIR:-.ralph-obs}"
STATE_LOG="$OBS_DIR/state.json"
HEALTH_LOG="$OBS_DIR/health.log"
ITERATIONS_LOG="$OBS_DIR/iterations.jsonl"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Watch function
watch_loop() {
  local refresh=${1:-2}

  while true; do
    clear

    echo -e "${BLUE}════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}    Ralph Loop — Real-Time Monitor${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Show state
    if [ -f "$STATE_LOG" ]; then
      current_task=$(cat "$STATE_LOG" | jq -r '.current_task // "none"' 2>/dev/null || echo "none")
      stuck_count=$(cat "$STATE_LOG" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")
      total_failed=$(cat "$STATE_LOG" | jq -r '.total_failed // 0' 2>/dev/null || echo "0")
      last_successful=$(cat "$STATE_LOG" | jq -r '.last_successful // "never"' 2>/dev/null || echo "never")
      updated_at=$(cat "$STATE_LOG" | jq -r '.updated_at // "unknown"' 2>/dev/null || echo "unknown")

      echo -e "${CYAN}Current State:${NC}"
      echo -e "  Task:         ${current_task}"
      echo -e "  Stuck:        ${YELLOW}${stuck_count}${NC} / 5"
      echo -e "  Failed:       ${RED}${total_failed}${NC}"
      echo -e "  Last Success: ${GREEN}${last_successful}${NC}"
      echo -e "  Updated:      ${updated_at}"
      echo ""
    else
      echo -e "${YELLOW}No state file found - loop may not be running${NC}"
      echo ""
    fi

    # Show iteration stats if available
    if [ -f "$ITERATIONS_LOG" ]; then
      total=$(grep -c '"type":"iteration"' "$ITERATIONS_LOG" 2>/dev/null || echo "0")
      success=$(grep '"status":"success"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")
      failed=$(grep '"status":"test_failed"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")
      errors=$(grep '"status":"agent_error"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")

      if [ "$total" -gt 0 ]; then
        rate=$(echo "scale=1; $success * 100 / $total" | bc 2>/dev/null || echo "0")
        echo -e "${CYAN}Iteration Stats:${NC}"
        echo -e "  Total:    ${total}"
        echo -e "  Success:  ${GREEN}${success}${NC} (${rate}%)"
        echo -e "  Failed:   ${RED}${failed}${NC}"
        echo -e "  Errors:   ${MAGENTA}${errors}${NC}"
        echo ""
      fi
    fi

    # Show recent health events
    if [ -f "$HEALTH_LOG" ]; then
      echo -e "${CYAN}Recent Health Events (last 5):${NC}"
      tail -5 "$HEALTH_LOG" 2>/dev/null | while read -r line; do
        level=$(echo "$line" | sed -E 's/.*\[(INFO|WARN|ERROR)\].*/\1/' 2>/dev/null || echo "INFO")
        message=$(echo "$line" | sed -E 's/.*\] (.*)/\1/' 2>/dev/null || echo "$line")

        case "$level" in
          INFO)
            echo -e "  ${GREEN}✓${NC} $message"
            ;;
          WARN)
            echo -e "  ${YELLOW}⚠${NC} $message"
            ;;
          ERROR)
            echo -e "  ${RED}✗${NC} $message"
            ;;
        esac
      done
      echo ""
    fi

    # Status indicator
    if [ -f "$STATE_LOG" ]; then
      stuck_count=$(cat "$STATE_LOG" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")
      if [ "$stuck_count" -ge 5 ]; then
        echo -e "${RED}⚠⚠⚠ LOOP STOPPED - STUCK ON TASK ⚠⚠⚠${NC}"
      elif [ "$stuck_count" -ge 3 ]; then
        echo -e "${RED}⚠ WARNING - Loop may be stuck${NC}"
      elif [ "$stuck_count" -ge 1 ]; then
        echo -e "${YELLOW}⚠ Loop encountering failures${NC}"
      else
        echo -e "${GREEN}✓ Loop running normally${NC}"
      fi
    else
      echo -e "${YELLOW}? Loop not started or no data${NC}"
    fi

    echo ""
    echo -e "${CYAN}Press Ctrl+C to exit${NC}"
    echo -e "Refresh: ${refresh}s${NC}"

    sleep "$refresh"
  done
}

# Parse arguments
refresh=2
while getopts "r:" opt; do
  case $opt in
    r) refresh=$OPTARG ;;
    \?) echo "Usage: $0 [-r refresh_seconds]" >&2; exit 1 ;;
  esac
done

watch_loop "$refresh"
