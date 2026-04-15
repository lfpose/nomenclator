#!/bin/bash
# Test script for Ralph Watch extension

set -e

echo "=== Testing Ralph Watch Extension ==="
echo ""

# Ensure we have test data
mkdir -p .ralph-obs

# Create test state.json if it doesn't exist
if [ ! -f ".ralph-obs/state.json" ]; then
  echo "Creating test state.json..."
  cat > .ralph-obs/state.json << EOJ
{
  "current_task": "P10-01",
  "stuck_count": 0,
  "last_successful": "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)",
  "total_failed": 0,
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
}
EOJ
fi

# Create test iterations.jsonl if it doesn't exist
if [ ! -f ".ralph-obs/iterations.jsonl" ]; then
  echo "Creating test iterations.jsonl..."
  for i in {1..5}; do
    echo "{\"type\":\"iteration\",\"status\":\"success\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"}" >> .ralph-obs/iterations.jsonl
  done
fi

# Create test health.log if it doesn't exist
if [ ! -f ".ralph-obs/health.log" ]; then
  echo "Creating test health.log..."
  echo "[$(date -u +%Y-%m-%dT%H:%M:%S+00:00)] [INFO] Test iteration completed successfully" > .ralph-obs/health.log
  echo "[$(date -u +%Y-%m-%dT%H:%M:%S+00:00)] [INFO] Task P10-01 started" >> .ralph-obs/health.log
  echo "[$(date -u +%Y-%m-%dT%H:%M:%S+00:00)] [INFO] All tests passed" >> .ralph-obs/health.log
fi

echo ""
echo "Test data created in .ralph-obs/:"
ls -la .ralph-obs/
echo ""

echo "To test the extension:"
echo "1. Run: pi"
echo "2. Type: /ralph-watch  (or press Ctrl+Alt+R)"
echo "3. You should see the Ralph watch widget appear above the editor"
echo ""
echo "Or start with watch enabled:"
echo "  pi --ralph-watch"
echo ""
