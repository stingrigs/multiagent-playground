# ====================================
#  🔰 [RESEARCH TEAM] Prompts
# ====================================
# Prompt texts live in Langfuse Prompt Management, not here. The names below are
# the contract between this code and the Langfuse project; see README → Prompts.

from observability import langfuse, settings

PLANNER = "research_planner_system"
RESEARCHER = "research_researcher_system"
CRITIC = "research_critic_system"
SUPERVISOR = "research_supervisor_system"


def load_prompt(name: str, **variables: object) -> str:
    """Fetch a prompt at the configured label and fill its {{variables}}."""
    try:
        prompt = langfuse.get_prompt(name, label=settings.prompt_label)
    except Exception as e:
        raise RuntimeError(
            f"Cannot load prompt '{name}' at label '{settings.prompt_label}' "
            f"[{type(e).__name__}]. Create it in Langfuse UI → Prompts as a Text "
            f"prompt with that label, and check LANGFUSE_* in .env."
        ) from e
    return prompt.compile(**variables)
