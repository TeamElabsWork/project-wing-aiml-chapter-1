"""CLI surface adapter and interactive REPL.

Owner: A2
"""

import asyncio
import sys
import uuid
from typing import Any, Protocol

from contracts.models import ApprovalResponse, Response


class PipelineRunner(Protocol):
    """Protocol representing the orchestrator pipeline execution entry point."""

    async def process(
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

    async def send_message_async(self, text: str) -> Response:
        """Send a single message to the pipeline asynchronously."""
        return await self.pipeline.process(
            raw_input=text,
            surface_type="cli",
            external_user_id="local-developer",
            session_id=self.session_id,
        )

    def send_message(self, text: str) -> Response:
        """Send a single message using asyncio.run at the REPL edge."""
        try:
            asyncio.get_running_loop()
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(self.send_message_async(text))).result()
        except RuntimeError:
            return asyncio.run(self.send_message_async(text))

    async def handle_approval_async(self, request_id: str, approved: bool) -> None:
        """Submit an approval decision to the pipeline's approval manager."""
        approval_manager = getattr(self.pipeline, "approval_manager", None)
        if not approval_manager or not hasattr(approval_manager, "submit_decision"):
            print("[APPROVAL ERROR]: No approval manager configured on pipeline.")
            return

        decision = ApprovalResponse(
            approved=approved,
            feedback=None,
            approver="cli-operator",
            pending=False,
        )
        res = await approval_manager.submit_decision(request_id, decision)
        action_str = "APPROVED & EXECUTED" if res.approved else "DENIED"
        print(f"\n[APPROVAL] Request '{request_id}' has been {action_str}.")

        # If a tool was executed upon approval, print the result
        exec_results = getattr(approval_manager, "execution_results", {})
        if request_id in exec_results:
            tr = exec_results[request_id]
            if tr.ok:
                print(f"[TOOL EXECUTED]: {tr.output}")
            else:
                print(f"[TOOL ERROR]: {tr.error}")

    def run_repl(self) -> None:
        """Run the interactive console REPL."""
        print("=" * 60)
        print("Surface-Aware Agent Orchestration - Interactive CLI REPL")
        print(f"Session ID: {self.session_id}")
        print("Commands: /approve <id>, /deny <id>, exit")
        print("=" * 60)

        while True:
            try:
                user_input = input("\n[CLI] > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", ":q"):
                    print("Exiting CLI. Goodbye!")
                    break

                if user_input.startswith("/approve ") or user_input.startswith("/deny "):
                    parts = user_input.split(maxsplit=1)
                    cmd = parts[0].lower()
                    req_id = parts[1].strip() if len(parts) > 1 else ""
                    approved = cmd == "/approve"
                    asyncio.run(self.handle_approval_async(req_id, approved))
                    continue

                response = self.send_message(user_input)
                self.render_response(response)

            except (KeyboardInterrupt, EOFError):
                print("\nExiting CLI REPL...")
                break
            except Exception as e:
                print(f"[Error]: {e}", file=sys.stderr)

    def render_response(self, response: Response) -> None:
        """Render the response including the required transparency log line and approval prompt."""
        print("\n" + "-" * 50)
        print(f"[ROUTING] {response.routing_explanation}")
        print("-" * 50)
        print(f"[STATUS]: {response.status}")
        if response.status == "pending_approval" and response.pending_approval:
            req = response.pending_approval
            print("-" * 50)
            print("[PENDING APPROVAL REQUIRED]")
            print(f"  Request ID: {req.request_id}")
            print(f"  Tool:       {req.action.tool_name}")
            print(f"  Arguments:  {req.action.arguments}")
            print(f"  Reason:     {req.reason}")
            print(f"  -> Type '/approve {req.request_id}' to approve and execute.")
            print(f"  -> Type '/deny {req.request_id}' to reject.")
        print("-" * 50)
        print(f"[REPLY - {response.persona_used.upper()}]:\n{response.reply_text}")
        print("-" * 50)
