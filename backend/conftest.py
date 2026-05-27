import sys
from pathlib import Path

# Ensure the backend package root is on sys.path so `import app` works
# regardless of how pytest resolves the editable install.
sys.path.insert(0, str(Path(__file__).parent))
