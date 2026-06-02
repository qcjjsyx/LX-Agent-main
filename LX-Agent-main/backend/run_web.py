import os
import sys
from pathlib import Path

try:
    from .app import app
except ImportError:  # pragma: no cover - supports direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app import app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
