"""Evaluation harness running labeled routing cases against any Router implementation.

Owner: F2
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml
from contracts.models import RequestEnvelope, RouteDecision, SurfaceContext
from routing_router.base import Router
from routing_router.mock_router import MockRouter


def run_evals(router: Router, cases_path: Path | str = "evals/cases.yaml") -> Dict[str, Any]:
    """Execute evaluation cases against the provided router and return results."""
    # TODO (F2 Evals Owner): Add semantic similarity matching for reasoning explanations,
    # latency benchmarking, and confusion matrix generation.
    path = Path(cases_path)
    if not path.exists():
        raise FileNotFoundError(f"Evaluation cases file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    cases: List[Dict[str, Any]] = data.get("cases", [])
    results: List[Dict[str, Any]] = []
    persona_matches = 0

    for c in cases:
        case_id = c["id"]
        input_text = c["input_text"]
        surface = c.get("surface", "cli")
        expected_persona = c.get("expected_persona")

        surface_ctx = SurfaceContext(
            surface_type=surface,
            client_id="eval-client",
            is_interactive=True,
            supports_markdown=True,
        )

        envelope = RequestEnvelope(
            message_id=f"eval-{case_id}",
            session_id=f"sess-eval-{case_id}",
            user_id="eval-user",
            raw_text=input_text,
            surface_context=surface_ctx,
        )

        decision: RouteDecision = router.route(
            envelope=envelope,
            session_state={},
            surface_policy={"is_urgent": "urgent" in input_text.lower()},
            memory_context=[],
        )

        matched = decision.persona.lower() == str(expected_persona).lower()
        if matched:
            persona_matches += 1

        results.append(
            {
                "case_id": case_id,
                "input_text": input_text,
                "surface": surface,
                "expected_persona": expected_persona,
                "predicted_persona": decision.persona,
                "matched": matched,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
            }
        )

    total = len(cases)
    accuracy = (persona_matches / total) if total > 0 else 0.0

    return {
        "total_cases": total,
        "persona_matches": persona_matches,
        "accuracy": accuracy,
        "case_results": results,
    }


def main() -> None:
    """Run evaluation harness from CLI with default mock router."""
    router = MockRouter()
    print("Running routing evaluation harness against MockRouter...")
    report = run_evals(router)
    print(
        f"Results: {report['persona_matches']}/{report['total_cases']} matched ({report['accuracy']:.1%})"
    )
    for r in report["case_results"]:
        status = "PASS" if r["matched"] else "FAIL"
        print(
            f"[{status}] {r['case_id']}: expected '{r['expected_persona']}', got '{r['predicted_persona']}'"
        )


if __name__ == "__main__":
    main()
