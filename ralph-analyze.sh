#!/bin/bash
# Ralph Loop Observability Analysis Tool
# =======================================

OBS_DIR="${RALPH_OBS_DIR:-.ralph-obs}"
ITERATIONS_LOG="$OBS_DIR/iterations.jsonl"
HEALTH_LOG="$OBS_DIR/health.log"
STATE_LOG="$OBS_DIR/state.json"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

show_summary() {
  echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}    Ralph Loop — Summary${NC}"
  echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
  echo ""

  # Get total iterations (exclude header)
  total_iterations=$(grep -c '"type":"iteration"' "$ITERATIONS_LOG" 2>/dev/null || echo "0")

  # Count by status
  success_count=$(grep '"status":"success"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")
  failed_count=$(grep '"status":"test_failed"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")
  error_count=$(grep '"status":"agent_error"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")
  unknown_count=$(grep '"status":"unknown"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")

  echo -e "Total Iterations: ${CYAN}${total_iterations}${NC}"
  echo ""
  echo -e "By Status:"
  echo -e "  Success:     ${GREEN}${success_count}${NC}"
  echo -e "  Test Failed: ${RED}${failed_count}${NC}"
  echo -e "  Agent Error: ${RED}${error_count}${NC}"
  echo -e "  Unknown:     ${YELLOW}${unknown_count}${NC}"
  echo ""

  # Get current state
  if [ -f "$STATE_LOG" ]; then
    current_task=$(cat "$STATE_LOG" | jq -r '.current_task // none' 2>/dev/null || echo "none")
    stuck_count=$(cat "$STATE_LOG" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")
    total_failed=$(cat "$STATE_LOG" | jq -r '.total_failed // 0' 2>/dev/null || echo "0")

    echo -e "Current State:"
    echo -e "  Current Task: ${CYAN}${current_task}${NC}"
    echo -e "  Stuck Count:  ${YELLOW}${stuck_count}${NC}"
    echo -e "  Total Failed: ${RED}${total_failed}${NC}"
    echo ""
  fi

  # Success rate
  if [ "$total_iterations" -gt 0 ]; then
    success_rate=$(echo "scale=1; $success_count * 100 / $total_iterations" | bc 2>/dev/null || echo "0")
    echo -e "Success Rate: ${GREEN}${success_rate}%${NC}"
    echo ""
  fi
}

show_failed() {
  echo -e "${RED}═════════════════════════════════════════════════════════${NC}"
  echo -e "${RED}    Failed Iterations${NC}"
  echo -e "${RED}═════════════════════════════════════════════════════════${NC}"
  echo ""

  grep '"status":"test_failed"\|"status":"agent_error"\|"status":"unknown"' "$ITERATIONS_LOG" 2>/dev/null | while read -r line; do
    iteration=$(echo "$line" | jq -r '.iteration' 2>/dev/null || echo "?")
    task=$(echo "$line" | jq -r '.task_id // "unknown"' 2>/dev/null || echo "unknown")
    status=$(echo "$line" | jq -r '.status' 2>/dev/null || echo "unknown")
    test_result=$(echo "$line" | jq -r '.test_result // "N/A"' 2>/dev/null || echo "N/A")
    duration=$(echo "$line" | jq -r '.duration' 2>/dev/null || echo "?")
    output=$(echo "$line" | jq -r '.output // ""' 2>/dev/null | head -c 200)

    echo -e "Iteration ${BLUE}${iteration}${NC}: ${RED}${status}${NC}"
    echo -e "  Task: ${CYAN}${task}${NC}"
    echo -e "  Test Result: ${test_result}"
    echo -e "  Duration: ${duration}s"
    echo -e "  Output: ${output}"
    echo ""
  done
}

show_slow() {
  local threshold=${1:-60}

  echo -e "${YELLOW}═════════════════════════════════════════════════════════${NC}"
  echo -e "${YELLOW}    Slow Iterations (> ${threshold}s)${NC}"
  echo -e "${YELLOW}═════════════════════════════════════════════════════════${NC}"
  echo ""

  if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is required for this command${NC}"
    return
  fi

  grep '"type":"iteration"' "$ITERATIONS_LOG" 2>/dev/null | jq --arg threshold "$threshold" 'select(.duration > ($threshold | tonumber))' | jq -r '
    "Iteration: \(.iteration)",
    "  Task: \(.task_id // "unknown")",
    "  Duration: \(.duration)s",
    "  Status: \(.status)",
    "  Output: \(.output[0:200])...",
    ""
  '
}

show_health() {
  echo -e "${CYAN}═════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}    Health Log (Last 20 entries)${NC}"
  echo -e "${CYAN}═════════════════════════════════════════════════════════${NC}"
  echo ""

  tail -20 "$HEALTH_LOG" 2>/dev/null | while read -r line; do
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
}

show_report() {
  echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}    Ralph Loop Report${NC}"
  echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
  echo ""

  # Get run info
  start_time=$(head -1 "$ITERATIONS_LOG" 2>/dev/null | jq -r '.timestamp' 2>/dev/null || echo "unknown")
  end_time=$(tail -1 "$ITERATIONS_LOG" 2>/dev/null | jq -r '.timestamp' 2>/dev/null || echo "unknown")

  echo -e "Run Period:"
  echo -e "  Start: ${CYAN}${start_time}${NC}"
  echo -e "  End:   ${CYAN}${end_time}${NC}"
  echo ""

  show_summary

  echo -e "Recommendations:"
  echo ""

  # Check stuck count
  if [ -f "$STATE_LOG" ]; then
    stuck_count=$(cat "$STATE_LOG" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")
    if [ "$stuck_count" -ge 3 ]; then
      echo -e "  ${YELLOW}⚠${NC} Loop is stuck on the same task ($stuck_count iterations)"
      echo -e "     Consider: Manual review of the task and tests"
      echo ""
    fi
  fi

  # Check failure rate
  total_iterations=$(grep -c '"type":"iteration"' "$ITERATIONS_LOG" 2>/dev/null || echo "0")
  failed_count=$(grep '"status":"test_failed"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")

  if [ "$total_iterations" -gt 0 ]; then
    failure_rate=$(echo "scale=1; $failed_count * 100 / $total_iterations" | bc 2>/dev/null || echo "0")
    if (( $(echo "$failure_rate > 20" | bc -l 2>/dev/null) )); then
      echo -e "  ${YELLOW}⚠${NC} High failure rate: ${failure_rate}%"
      echo -e "     Consider: Reviewing model, task complexity, or test design"
      echo ""
    fi
  fi

  # Check for very slow iterations
  if command -v jq &> /dev/null; then
    slow_count=$(grep '"type":"iteration"' "$ITERATIONS_LOG" 2>/dev/null | jq 'select(.duration > 120)' | wc -l || echo "0")
    if [ "$slow_count" -gt 0 ]; then
      echo -e "  ${YELLOW}⚠${NC} Found $slow_count very slow iterations (> 120s)"
      echo -e "     Consider: Using a faster model or breaking down complex tasks"
      echo ""
    fi
  fi

  # Check for agent errors
  error_count=$(grep '"status":"agent_error"' "$ITERATIONS_LOG" 2>/dev/null | wc -l || echo "0")
  if [ "$error_count" -gt 0 ]; then
    echo -e "  ${RED}✗${NC} Found $error_count agent errors"
    echo -e "     Consider: Checking model stability, API quotas, network issues"
    echo ""
  fi

  if [ "$failed_count" -eq 0 ] && [ "$error_count" -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} No failures detected! Loop is running smoothly."
    echo ""
  fi
}

show_help() {
  echo "Ralph Loop Analysis Tool"
  echo ""
  echo "Usage: $0 <command>"
  echo ""
  echo "Commands:"
  echo "  summary   - Show overall summary"
  echo "  failed    - Show failed iterations"
  echo "  slow      - Show slow iterations (> 60s)"
  echo "  slow <n>  - Show iterations slower than <n> seconds"
  echo "  health    - Show recent health log entries"
  echo "  report    - Generate comprehensive report"
  echo "  help      - Show this help message"
  echo ""
  echo "Environment:"
  echo "  RALPH_OBS_DIR - Observability directory (default: .ralph-obs)"
}

# Main dispatch
case "${1:-help}" in
  summary)
    show_summary
    ;;
  failed)
    show_failed
    ;;
  slow)
    show_slow "$2"
    ;;
  health)
    show_health
    ;;
  report)
    show_report
    ;;
  help|--help|-h)
    show_help
    ;;
  *)
    echo -e "${RED}Unknown command: $1${NC}"
    echo ""
    show_help
    exit 1
    ;;
esac
