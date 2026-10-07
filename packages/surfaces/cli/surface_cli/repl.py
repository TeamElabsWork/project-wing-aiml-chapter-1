"""CLI surface adapter and interactive REPL.

Owner: A2
"""

import sys
import uuid
from typing import Any, Protocol

from contracts.models import Response


class PipelineRunner(Protocol):
    """Protocol representing the orchestrator pipeline execution entry point."""

    def process(
        self,
        raw_input: Any,
        surface_type: str = "cli",
        external_user_id: str = "cli-user",
        session_id: str | None = None,
    ) -> Response: ...


class CLIAdapter:
    """CLI surface adapter managing user interaction and console rendering."""

    def __init__(self, pipeline: PipelineRunner) -> None:
        self.pipeline = pipeline
        self.session_id = f"cli-session-{uuid.uuid4().hex[:6]}"

    def send_message(self, text: str) -> Response:
        """Send a single message to the pipeline."""
        return self.pipeline.process(
            raw_input=text,
            surface_type="cli",
            external_user_id="local-developer",
            session_id=self.session_id,
        )

    def run_repl(self) -> None:
        """Run the interactive console REPL."""
        print("=" * 60)
        print("Surface-Aware Agent Orchestration - Interactive CLI REPL")
        print(f"Session ID: {self.session_id}")
        print("Type your message and press Enter. Type 'exit' or 'quit' to quit.")
        print("=" * 60)

        while True:
            try:
                user_input = input("\n[CLI] > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", ":q"):
                    print("Exiting CLI. Goodbye!")
                    break

                response = self.send_message(user_input)
                self.render_response(response)

            except (KeyboardInterrupt, EOFError):
                print("\nExiting CLI REPL...")
                break
            except Exception as e:
                print(f"[Error]: {e}", file=sys.stderr)

    def render_response(self, response: Response) -> None:
        """Render the response including the required transparency log line."""
        print("\n" + "-" * 50)
        # Required transparency explanation line
        print(f"[ROUTING] {response.routing_explanation}")
        print("-" * 50)
        print(f"[REPLY - {response.persona_used.upper()}]:\n{response.reply_text}")
        print("-" * 50)
