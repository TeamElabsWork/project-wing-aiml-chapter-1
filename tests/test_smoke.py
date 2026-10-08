"""End-to-end smoke test covering full pipeline execution using only mocks."""

import pytest
from orchestrator.pipeline import create_pipeline
from surface_cli.repl import CLIAdapter


@pytest.mark.asyncio
async def test_end_to_end_smoke_pipeline() -> None:
    """Verifies fake message in -> normalizer -> router -> runtime -> memory -> fake routed reply out."""
    pipeline = create_pipeline(config_dir="config")
    cli = CLIAdapter(pipeline=pipeline)

    input_text = "Refactor the authentication middleware to support JWT refresh tokens"
    response = cli.send_message(input_text)

    # 1. Verify response structure and contracts
    assert response is not None
    assert response.reply_text != ""
    assert response.persona_used == "coder"
    assert response.route_decision.confidence > 0.0

    # 2. Verify routing explanation line
    assert "Summoned" in response.routing_explanation
    assert "coder" in response.routing_explanation

    # 3. Verify memory write occurred in repository
    memories = await pipeline.memory_repo.list_all()
    assert len(memories) >= 1
    latest_memory = memories[-1]
    assert latest_memory.persona == "coder"
    assert latest_memory.surface == "cli"

    # 4. Verify session state updated
    session = await pipeline.session_manager.get_session(response.session_id)
    assert len(session.history) >= 1
    assert session.history[-1]["persona"] == "coder"
