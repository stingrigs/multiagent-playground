# ====================================
#  🔰 [RESEARCH AGENT] Config
# ====================================

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    model_name: str = "gpt-5-mini"

    max_search_results: int = 5
    max_url_content_length: int = 5000
    max_file_content_length: int = 10000
    request_timeout: int = 20
    output_dir: str = "output"
    max_iterations: int = 25

    model_config = {"env_file": ".env"}

    @property
    def recursion_limit(self) -> int:
        """LangGraph counts graph steps, not tool-calling rounds: each round
        costs an agent step plus a tools step, plus one final agent step."""
        return 2 * self.max_iterations + 1
