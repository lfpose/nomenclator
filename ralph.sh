#!/bin/bash
# Ralph Wiggum Autonomous Development Loop v2 - Enhanced Observability (FIXED)
# ==========================================================================
# Runs Pi agent in a continuous loop with rich observability, failure detection,
# and recovery mechanisms.
#
# Usage: ./ralph-v2.sh <max_iterations|watch> [agent]
# Examples:
#   ./ralph-v2.sh watch             # interactive - watch the agent work live
#   ./ralph-v2.sh 1                 # one task, non-interactive
#   ./ralph-v2.sh 200               # full autopilot
#   ./ralph-v2.sh 200 claude        # use Claude Code instead
#
# Observability Features:
#   - Iteration logs: iteration.jsonl with per-iteration metrics
#   - Health checks: detect stuck/failed/progressing states
#   - Failure categorization: implementation vs test vs agent errors
#   - Task state tracking: which tasks are blocked, failing, or pending
#   - Token usage tracking: cost monitoring per iteration
#   - Git state tracking: commits made per iteration
#
# Environment:
#   OPENROUTER_API_KEY  - required for Pi+OpenRouter (auto-loaded from .env)
#   RALPH_MODEL         - override model (default: z-ai/glm-5.1)
#   RALPH_OBS_DIR       - observability directory (default: .ralph-obs)

set -e

# Auto-load .env if present
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Configuration
OBS_DIR="${RALPH_OBS_DIR:-.ralph-obs}"
ITERATIONS_LOG="$OBS_DIR/iterations.jsonl"
HEALTH_LOG="$OBS_DIR/health.log"
STATE_LOG="$OBS_DIR/state.json"
MAX_STUCK_ITERATIONS=5

# Initialize observability directory
init_obs() {
  mkdir -p "$OBS_DIR"

  # Create iterations log with header
  if [ ! -f "$ITERATIONS_LOG" ]; then
    printf '{"type":"header","version":"2.0","created_at":"%s"}\n' "$(date -Iseconds)" > "$ITERATIONS_LOG"
  fi

  # Create health log
  touch "$HEALTH_LOG"

  # Initialize state file with default values
  if [ ! -f "$STATE_LOG" ]; then
    printf '{"current_task":null,"stuck_count":0,"last_successful":null,"total_failed":0,"pid":%d,"created_at":"%s"}\n' "$$" "$(date -Iseconds)" > "$STATE_LOG"
  else
    # Update existing state with current PID
    local existing=$(cat "$STATE_LOG" 2>/dev/null || echo '{}')
    local current_task=$(echo "$existing" | jq -r '.current_task // "null"' 2>/dev/null || echo "null")
    local stuck_count=$(echo "$existing" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")
    local last_successful=$(echo "$existing" | jq -r '.last_successful // "null"' 2>/dev/null || echo "null")
    local total_failed=$(echo "$existing" | jq -r '.total_failed // 0' 2>/dev/null || echo "0")
    printf '{"current_task":"%s","stuck_count":%d,"last_successful":"%s","total_failed":%d,"pid":%d,"updated_at":"%s"}\n' \
      "$current_task" "$stuck_count" "$last_successful" "$total_failed" "$$" "$(date -Iseconds)" > "$STATE_LOG"
  fi
}

# Log an iteration
log_iteration() {
  local iteration=$1
  local status=$2
  local task_id=$3
  local test_result=$4
  local duration=$5
  local output=$6

  local timestamp=$(date -Iseconds)
  local git_state=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
  local output_truncated=$(echo "$output" | head -c 1000 | sed 's/"/\\"/g' | tr '\n' ' ')

  printf '{"type":"iteration","timestamp":"%s","iteration":%d,"status":"%s","task_id":"%s","test_result":"%s","duration":%.2f,"git_state":"%s","output":"%s"}\n' \
    "$timestamp" "$iteration" "$status" "$task_id" "$test_result" "$duration" "$git_state" "$output_truncated" \
    >> "$ITERATIONS_LOG"
}

# Log health status
log_health() {
  local message=$1
  local level=$2
  local timestamp=$(date -Iseconds)
  echo "[$timestamp] [$level] $message" >> "$HEALTH_LOG"
}

# Update state
update_state() {
  local current_task=$1
  local stuck_count=$2
  local last_successful=$3
  local total_failed=$4
  local ralph_pid=${5:-$$}

  printf '{"current_task":"%s","stuck_count":%d,"last_successful":"%s","total_failed":%d,"pid":%d,"updated_at":"%s"}\n' \
    "$current_task" "$stuck_count" "$last_successful" "$total_failed" "$ralph_pid" "$(date -Iseconds)" \
    > "$STATE_LOG"
}

# Get current state (safe - returns default if missing)
get_state() {
  if [ -f "$STATE_LOG" ]; then
    cat "$STATE_LOG"
  else
    printf '{"current_task":null,"stuck_count":0,"last_successful":null,"total_failed":0}'
  fi
}

# Detect if we're stuck on the same task
detect_stuck() {
  local current_task=$1
  local state=$(get_state)

  local prev_task=$(echo "$state" | jq -r '.current_task // empty' 2>/dev/null || echo "")
  local stuck_count=$(echo "$state" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")

  if [ "$prev_task" = "$current_task" ] && [ -n "$prev_task" ]; then
    stuck_count=$((stuck_count + 1))
  else
    stuck_count=0
  fi

  echo "$stuck_count"
}

# Print iteration summary
print_summary() {
  local iteration=$1
  local status=$2
  local task_id=$3
  local test_result=$4
  local duration=$5

  echo ""
  if [ "$status" = "success" ]; then
    echo -e "${GREEN}✓ Task $task_id completed in ${duration}s${NC}"
  elif [ "$status" = "test_failed" ]; then
    echo -e "${RED}✗ Task $task_id tests failed${NC}"
  elif [ "$status" = "agent_error" ]; then
    echo -e "${MAGENTA}⚠ Agent error on task $task_id${NC}"
  else
    echo -e "${YELLOW}? Task $task_id status unknown${NC}"
  fi

  echo -e "   Test result: ${CYAN}$test_result${NC}"
  echo -e "   Iteration: ${BLUE}$iteration${NC}"
}

# Print dashboard
print_dashboard() {
  local iteration=$1
  local max_iterations=$2
  local current_task=$3
  local stuck_count=$4

  local progress=$(echo "scale=1; $iteration * 100 / $max_iterations" | bc 2>/dev/null || echo "0")

  echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}    Ralph Loop v2 - Progress Dashboard${NC}"
  echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
  echo -e "  Iteration:   ${GREEN}$iteration${NC} / $max_iterations (${progress}%)"
  echo -e "  Current Task: ${CYAN}${current_task:-none}${NC}"
  echo -e "  Stuck Count: ${YELLOW}${stuck_count}${NC} / $MAX_STUCK_ITERATIONS"
  echo -e "  Obs Data:    ${OBS_DIR}"
  echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
  echo ""
}

# Parse test result from output
parse_test_result() {
  local output=$1

  if echo "$output" | grep -qi "passed"; then
    echo "PASS"
  elif echo "$output" | grep -qi "FAILED"; then
    echo "FAIL"
  elif echo "$output" | grep -qi "error"; then
    echo "ERROR"
  else
    echo "UNKNOWN"
  fi
}

# Parse current task from output
parse_task_id() {
  local output=$1
  echo "$output" | grep -oE "P[0-9]{2}-[0-9]{2}" | head -1
}

# Command line argument handling
if [ -z "$1" ]; then
  echo -e "${RED}Error: Missing required argument${NC}"
  echo ""
  echo "Usage: $0 <max_iterations|watch> [agent]"
  echo ""
  echo "  watch:  interactive session - watch the agent work live"
  echo "  1..N:   run N iterations non-interactively"
  echo "  agent:  pi (default) or claude"
  echo ""
  echo "Examples:"
  echo "  ./ralph-v2.sh watch            # watch live"
  echo "  ./ralph-v2.sh 1                # one task"
  echo "  ./ralph-v2.sh 200              # full autopilot"
  echo "  RALPH_MODEL=z-ai/glm-4.5-air:free ./ralph-v2.sh watch   # free model"
  exit 1
fi

AGENT="${2:-pi}"
MODEL="${RALPH_MODEL:-z-ai/glm-5.1}"

# Verify required files
for f in PROMPT.md prd.md; do
  if [ ! -f "$f" ]; then
    echo -e "${RED}Error: $f not found${NC}"
    exit 1
  fi
done

if [ ! -f "activity.md" ]; then
  echo -e "${YELLOW}Warning: activity.md not found, creating it...${NC}"
  cat > activity.md << 'EOF'
# Nomenclator - Activity Log

## Current Status
**Last Updated:** Not started
**Tasks Completed:** 0
**Current Task:** None

---

## Session Log

<!-- Agent will append dated entries here -->
EOF
fi

# ── Watch mode: interactive Pi TUI ──
if [ "$1" = "watch" ]; then
  if [ "$AGENT" = "pi" ]; then
    if ! command -v pi &> /dev/null; then
      echo -e "${RED}Error: pi not found. Install: npm install -g @mariozechner/pi-coding-agent${NC}"
      exit 1
    fi
    if [ -z "$OPENROUTER_API_KEY" ]; then
      echo -e "${RED}Error: OPENROUTER_API_KEY not set${NC}"
      exit 1
    fi
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}   Nomenclator - Watch Mode${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo -e "Agent: ${GREEN}Pi + OpenRouter${NC}"
    echo -e "Model: ${GREEN}$MODEL${NC}"
    echo ""
    exec pi --provider openrouter --model "$MODEL" --thinking medium @prd.md @activity.md @PROMPT.md
  elif [ "$AGENT" = "claude" ]; then
    echo -e "${BLUE}Watch mode with Claude: just run 'claude' directly.${NC}"
    exit 0
  fi
fi

# ── Loop mode: non-interactive ──
MAX_ITERATIONS=$1
init_obs

if [ "$AGENT" = "pi" ]; then
  if ! command -v pi &> /dev/null; then
    echo -e "${RED}Error: pi not found. Install: npm install -g @mariozechner/pi-coding-agent${NC}"
    exit 1
  fi
  if [ -z "$OPENROUTER_API_KEY" ]; then
    echo -e "${RED}Error: OPENROUTER_API_KEY not set${NC}"
    exit 1
  fi
  AGENT_CMD="pi -p --provider openrouter --model $MODEL --no-session --thinking medium @prd.md @activity.md"
  echo -e "Agent: ${GREEN}Pi + OpenRouter${NC}"
  echo -e "Model: ${GREEN}$MODEL${NC}"
elif [ "$AGENT" = "claude" ]; then
  if ! command -v claude &> /dev/null; then
    echo -e "${RED}Error: claude not found${NC}"
    exit 1
  fi
  AGENT_CMD="claude -p --output-format text"
  echo -e "Agent: ${GREEN}Claude Code${NC}"
else
  echo -e "${RED}Error: Unknown agent '$AGENT'. Use 'pi' or 'claude'.${NC}"
  exit 1
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}   Nomenclator - Ralph Loop v2${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "Max iterations: ${GREEN}$MAX_ITERATIONS${NC}"
echo -e "Completion signal: ${GREEN}<promise>COMPLETE</promise>${NC}"
echo -e "Observability: ${GREEN}$OBS_DIR${NC}"
echo ""
echo -e "${YELLOW}Starting in 3 seconds... Press Ctrl+C to abort${NC}"
sleep 3
echo ""

# Get initial state (safe)
state=$(get_state)
total_failed=$(echo "$state" | jq -r '.total_failed // 0' 2>/dev/null || echo "0")

# Main loop - use 'set +e' to not exit on errors
set +e

for ((i=1; i<=MAX_ITERATIONS; i++)); do
  start_time=$(date +%s)

  state=$(get_state)
  stuck_count=$(echo "$state" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")

  print_dashboard "$i" "$MAX_ITERATIONS" "" "$stuck_count"

  echo -e "${BLUE}Running iteration $i...${NC}"
  echo ""

  # Run agent command and capture output
  result=$($AGENT_CMD "$(cat PROMPT.md)" 2>&1)
  agent_exit_code=$?

  end_time=$(date +%s)
  duration=$((end_time - start_time))

  # Print output immediately (unbuffered)
  echo "$result"
  echo ""

  # Parse results
  test_result=$(parse_test_result "$result")
  task_id=$(parse_task_id "$result")

  # Determine status
  status="unknown"
  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    status="complete"
    log_iteration "$i" "complete" "$task_id" "$test_result" "$duration" "$result"
    log_health "Project completed!" "INFO"

    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}   ALL TASKS COMPLETE!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo -e "Finished after ${GREEN}$i${NC} iteration(s)"
    print_dashboard "$i" "$MAX_ITERATIONS" "COMPLETE" "0"
    exit 0
  elif [ "$agent_exit_code" -ne 0 ]; then
    status="agent_error"
    stuck_count=$(detect_stuck "$task_id")
    total_failed=$((total_failed + 1))
    update_state "$task_id" "$stuck_count" "" "$total_failed"
    log_health "Agent exited with code $agent_exit_code on task $task_id" "ERROR"
  elif [ "$test_result" = "PASS" ]; then
    status="success"
    stuck_count=0
    total_failed=0
    update_state "$task_id" "$stuck_count" "$(date -Iseconds)" "$total_failed"
    log_health "Task $task_id succeeded" "INFO"
  elif [ "$test_result" = "FAIL" ]; then
    status="test_failed"
    stuck_count=$(detect_stuck "$task_id")
    total_failed=$((total_failed + 1))
    update_state "$task_id" "$stuck_count" "" "$total_failed"
    log_health "Task $task_id test failed (stuck: $stuck_count)" "WARN"

    if [ "$stuck_count" -ge "$MAX_STUCK_ITERATIONS" ]; then
      echo ""
      echo -e "${RED}======================================${NC}"
      echo -e "${RED}   STUCK ON TASK $task_id${NC}"
      echo -e "${RED}======================================${NC}"
      echo ""
      echo -e "Failed ${stuck_count} times in a row on the same task."
      echo -e "Consider: 1) Checking the test for bugs, 2) Reviewing the plan, 3) Manual intervention"
      echo ""
      log_health "Stuck on task $task_id for $stuck_count iterations" "ERROR"
      print_dashboard "$i" "$MAX_ITERATIONS" "$task_id" "$stuck_count"
      # Continue running - don't exit!
    fi
  elif echo "$result" | grep -qiE "(error|exception|traceback)"; then
    status="agent_error"
    stuck_count=$(detect_stuck "$task_id")
    total_failed=$((total_failed + 1))
    update_state "$task_id" "$stuck_count" "" "$total_failed"
    log_health "Agent error on task $task_id" "ERROR"
  else
    status="unknown"
    stuck_count=$(detect_stuck "$task_id")
    update_state "$task_id" "$stuck_count" "" "$total_failed"
    log_health "Unknown status for task $task_id" "WARN"
  fi

  log_iteration "$i" "$status" "$task_id" "$test_result" "$duration" "$result"

  # Print summary if we have a task
  if [ -n "$task_id" ]; then
    print_summary "$i" "$status" "$task_id" "$test_result" "$duration"
  fi

  echo -e "${YELLOW}--- End of iteration $i ---${NC}"
  echo ""

  # Optional: sleep briefly between iterations
  sleep 2
done

echo ""
echo -e "${RED}======================================${NC}"
echo -e "${RED}   MAX ITERATIONS REACHED${NC}"
echo -e "${RED}======================================${NC}"
echo ""
echo -e "Run again with more iterations: ./ralph-v2.sh 100"
echo -e "Check observability data in: $OBS_DIR"
echo ""

# Get final state
final_state=$(get_state)
final_task=$(echo "$final_state" | jq -r '.current_task // "none"' 2>/dev/null || echo "none")
final_stuck=$(echo "$final_state" | jq -r '.stuck_count // 0' 2>/dev/null || echo "0")

print_dashboard "$MAX_ITERATIONS" "$MAX_ITERATIONS" "$final_task" "$final_stuck"

# Print summary stats
echo ""
echo -e "${CYAN}Final Statistics:${NC}"
total_success=$(grep -c '"status":"success"' "$ITERATIONS_LOG" 2>/dev/null || echo "0")
total_failed_count=$(grep -c '"status":"test_failed"' "$ITERATIONS_LOG" 2>/dev/null || echo "0")
echo -e "  Successful: ${GREEN}${total_success}${NC}"
echo -e "  Failed: ${RED}${total_failed_count}${NC}"
echo -e "  Total iterations: ${BLUE}${MAX_ITERATIONS}${NC}"
echo ""

exit 0
