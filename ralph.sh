#!/bin/bash

# Ralph Wiggum Autonomous Development Loop for Nomenclator
# =========================================================
# Runs Pi agent (or Claude Code) in a continuous loop, each iteration with
# a fresh context window. Reads PROMPT.md and feeds it to the agent until
# all tasks are complete or max iterations is reached.
#
# Usage: ./ralph.sh <max_iterations> [agent]
# Examples:
#   ./ralph.sh 50              # uses Pi with OpenRouter (default)
#   ./ralph.sh 50 pi           # explicit Pi
#   ./ralph.sh 50 claude       # use Claude Code instead
#
# Environment:
#   OPENROUTER_API_KEY  — required for Pi+OpenRouter (load via: source .env)
#   RALPH_MODEL         — override model (default: anthropic/claude-sonnet-4)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ -z "$1" ]; then
  echo -e "${RED}Error: Missing required argument${NC}"
  echo ""
  echo "Usage: $0 <max_iterations> [agent]"
  echo ""
  echo "  agent: pi (default) or claude"
  echo ""
  echo "Examples:"
  echo "  source .env && ./ralph.sh 50"
  echo "  source .env && RALPH_MODEL=anthropic/claude-sonnet-4 ./ralph.sh 50"
  echo "  ./ralph.sh 50 claude"
  exit 1
fi

MAX_ITERATIONS=$1
AGENT="${2:-pi}"
MODEL="${RALPH_MODEL:-thudm/glm-5.1}"

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
# Nomenclator — Activity Log

## Current Status
**Last Updated:** Not started
**Tasks Completed:** 0
**Current Task:** None

---

## Session Log

<!-- Agent will append dated entries here -->
EOF
fi

# Verify agent is available
if [ "$AGENT" = "pi" ]; then
  if ! command -v pi &> /dev/null; then
    echo -e "${RED}Error: pi not found. Install: npm install -g @mariozechner/pi-coding-agent${NC}"
    exit 1
  fi
  if [ -z "$OPENROUTER_API_KEY" ]; then
    echo -e "${RED}Error: OPENROUTER_API_KEY not set. Run: source .env${NC}"
    exit 1
  fi
  AGENT_CMD="pi -p --provider openrouter --model $MODEL --no-session --thinking medium"
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

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}   Nomenclator — Ralph Loop${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "Max iterations: ${GREEN}$MAX_ITERATIONS${NC}"
echo -e "Completion signal: ${GREEN}<promise>COMPLETE</promise>${NC}"
echo ""
echo -e "${YELLOW}Starting in 3 seconds... Press Ctrl+C to abort${NC}"
sleep 3
echo ""

for ((i=1; i<=MAX_ITERATIONS; i++)); do
  echo -e "${BLUE}======================================${NC}"
  echo -e "${BLUE}   Iteration $i of $MAX_ITERATIONS${NC}"
  echo -e "${BLUE}======================================${NC}"
  echo ""

  result=$($AGENT_CMD "$(cat PROMPT.md)" 2>&1) || true

  echo "$result"
  echo ""

  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}   ALL TASKS COMPLETE!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo -e "Finished after ${GREEN}$i${NC} iteration(s)"
    exit 0
  fi

  echo -e "${YELLOW}--- End of iteration $i ---${NC}"
  echo ""
  sleep 2
done

echo ""
echo -e "${RED}======================================${NC}"
echo -e "${RED}   MAX ITERATIONS REACHED${NC}"
echo -e "${RED}======================================${NC}"
echo ""
echo -e "Run again with more iterations: ./ralph.sh 100"
echo "Check activity.md and prd.md for progress."
exit 1
