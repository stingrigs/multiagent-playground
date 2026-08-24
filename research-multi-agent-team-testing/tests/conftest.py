import pytest
from harness import goldens_by_category, load_golden_dataset, record, run_supervisor


@pytest.fixture(scope="session")
def golden_dataset() -> list[dict]:
    return load_golden_dataset()


@pytest.fixture(scope="session")
def happy_path_run(golden_dataset) -> dict:
    """Shared with test_tools.py so the full pipeline only runs once."""
    happy = goldens_by_category(golden_dataset, "happy_path")[0]
    return record(
        "supervisor_happy_path",
        lambda: run_supervisor(happy["input"], thread_id="fixture-happy-path"),
    )
