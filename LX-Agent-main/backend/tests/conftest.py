from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_PACKAGES = ROOT / "backend" / "skills" / "catalog" / "rtl-manual-generation" / "packages"
RTL_MANUAL_SCRIPTS = ROOT / "backend" / "skills" / "catalog" / "rtl-manual-generation" / "scripts"

for path in (ROOT, KNOWLEDGE_PACKAGES, RTL_MANUAL_SCRIPTS):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
