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
    llm_timeout: int = 60
    output_dir: str = "output"
    max_iterations: int = 25
    wrap_up_at: int = 6

    model_config = {"env_file": ".env"}


# The one shared instance. Everything imports this rather than constructing
# its own, so a missing key fails here — in the module named config — and
# not with a confusing traceback pointing at tools or prompts.
settings = Settings()
