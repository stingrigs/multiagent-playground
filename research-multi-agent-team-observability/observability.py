# ====================================
#  🔰 [RESEARCH TEAM] Observability
# ====================================

import os
import uuid

from config import Settings

settings = Settings()

# pydantic-settings reads .env into Settings, not into os.environ — but the Langfuse
# SDK takes its credentials from env vars, so export them before importing the client.
os.environ.setdefault(
    "LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key.get_secret_value()
)
os.environ.setdefault(
    "LANGFUSE_SECRET_KEY", settings.langfuse_secret_key.get_secret_value()
)
os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)

from langfuse import get_client
from langfuse.langchain import CallbackHandler

langfuse = get_client()
handler = CallbackHandler()

# One process = one session; main.py reuses this as the LangGraph thread_id.
SESSION_ID = f"research-{uuid.uuid4().hex[:8]}"
USER_ID = settings.user_id
TAGS = ["research-team", "hw12"]
