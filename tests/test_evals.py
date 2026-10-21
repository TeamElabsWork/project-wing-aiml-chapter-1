"""Tests for evaluation harness runner."""

from routing_router.mock_router import MockRouter

from evals.runner import run_evals


def test_evals_harness_runs_and_passes() -> None:
    router = MockRouter()
    results = run_evals(router, cases_path="evals/cases.yaml")

    assert results["total_cases"] == 29
    assert results["persona_matches"] == 29
    assert results["accuracy"] == 1.0
