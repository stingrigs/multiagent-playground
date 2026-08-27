# ====================================
#  🔰 [RESEARCH TEAM] Config
# ====================================

import os

# faiss-cpu + torch link separate OpenMP runtimes on macOS -> OMP: Error #15
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
# HF_HUB_DISABLE_PROGRESS_BARS/TRANSFORMERS_VERBOSITY don't stop tqdm's own bars; TQDM_DISABLE does
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TQDM_DISABLE", "1")

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    model_name: str = "gpt-5.2"

    # Langfuse
    langfuse_public_key: SecretStr = Field(alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: SecretStr = Field(alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: str = Field(
        "https://cloud.langfuse.com", alias="LANGFUSE_BASE_URL"
    )
    prompt_label: str = "production"
    user_id: str = "grigs"

    max_search_results: int = 5
    max_url_content_length: int = 5000
    request_timeout: int = 20
    llm_timeout: int = 60  # SDK default is 600s — fail fast instead of hanging
    output_dir: str = "output"
    max_iterations: int = 25
    max_revision_rounds: int = 1  # was 2 — 3x pipeline cost per round for little gain

    # RAG
    embedding_model: str = "text-embedding-3-small"
    data_dir: str = "data"
    index_dir: str = "index"
    chunk_size: int = 500
    chunk_overlap: int = 100
    retrieval_top_k: int = 10
    rerank_top_n: int = 3

    model_config = {"env_file": ".env"}

    @property
    def recursion_limit(self) -> int:
        """Sub-agent step budget. LangGraph counts steps, not tool rounds."""
        return 2 * self.max_iterations + 1

    @property
    def supervisor_recursion_limit(self) -> int:
        """Supervisor budget: each tool call costs 3 steps (HITL middleware adds one), not 2."""
        supervisor_max_steps = 18
        return 2 * supervisor_max_steps + 1


def make_llm(settings: Settings):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.api_key,
        timeout=settings.llm_timeout,
    )
