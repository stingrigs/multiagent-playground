# ====================================
#  🔰 [RESEARCH TEAM] Agent Spec
# ====================================

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    """Everything a2a_servers.py needs to publish one agent over A2A."""

    name: str
    description: str
    skill_id: str
    skill_name: str
    skill_description: str
    skill_tags: list[str]
    tool_names: tuple[str, ...]
    port: int
    structured: bool  # answers with a Pydantic model, not prose
    out_of_steps: str  # what to tell the Supervisor when the step budget runs out
