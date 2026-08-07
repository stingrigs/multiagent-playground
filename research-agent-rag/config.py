# ====================================
#  🔰 [RESEARCH AGENT] Config
# ====================================

import os

# faiss-cpu + torch link separate OpenMP runtimes on macOS -> OMP: Error #15
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
# quiet the reranker's first-load progress bars (transformers uses tqdm directly,
# ignoring HF_HUB_DISABLE_PROGRESS_BARS/TRANSFORMERS_VERBOSITY)
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TQDM_DISABLE", "1")

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    model_name: str = "gpt-5.2"

    max_search_results: int = 5
    max_url_content_length: int = 5000
    max_file_content_length: int = 10000
    request_timeout: int = 20
    llm_timeout: int = 60  # SDK default is 600s — fail fast instead of hanging
    output_dir: str = "output"
    max_iterations: int = 25

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
        """LangGraph counts steps, not tool rounds: round = agent step + tools step."""
        return 2 * self.max_iterations + 1
