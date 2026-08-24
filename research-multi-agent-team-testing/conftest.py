# must run before any project import -- Settings() resolves paths off CWD at import
# time, so this can't live in a fixture

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("OUTPUT_DIR", str(PROJECT_ROOT / "tests" / "runs" / "output"))

if not os.getenv("OPENAI_API_KEY") and not (PROJECT_ROOT / ".env").exists():
    raise RuntimeError(
        "OPENAI_API_KEY is not set and no .env file was found. "
        "Copy .env.example to .env and fill in your key before running tests."
    )
