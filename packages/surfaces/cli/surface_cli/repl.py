"""CLI surface adapter and interactive REPL.

Owner: A2
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Protocol

from contracts.models import ApprovalResponse, Response

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory

    HAS_PROMPT_TOOLKIT = True
except ImportError:  # pragma: no cover
    HAS_PROMPT_TOOLKIT = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".surface-agent"
CONFIG_FILE = CONFIG_DIR / "config.json"


class CLIConfig:
    """Configuration loaded from ~/.surface-agent/config.json.

    Fields:
        api_endpoint: Base URL of the orchestrator API server.
        auth_token:   Bearer token used for authenticated API requests.
        user_id:      Override for the default ``local-developer`` user id.
    """

    def __init__(
        self,
        api_endpoint: str = "",
        auth_token: str = "",
        user_id: str = "",
    ) -> None:
        self.api_endpoint = api_endpoint
        self.auth_token = auth_token
        self.user_id = user_id

    def get(self, key: str, default: str = "") -> str:
        """Dict-like access for convenience."""
        return getattr(self, key, default) or default


def load_config() -> CLIConfig:
    """Load CLI configuration from ``~/.surface-agent/config.json``.

    Returns a default ``CLIConfig`` if the file is missing or malformed.
    """
    if not CONFIG_FILE.exists():
        return CLIConfig()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return CLIConfig()
        return CLIConfig(
            api_endpoint=data.get("api_endpoint", ""),
            auth_token=data.get("auth_token", ""),
            user_id=data.get("user_id", ""),
        )
    except (json.JSONDecodeError, OSError):
        return CLIConfig()


# ---------------------------------------------------------------------------
# Local tool execution handlers (ADR-006)
# ---------------------------------------------------------------------------

LOCAL_TOOL_HANDLERS: Dict[str, Callable[..., Any]] = {
    "read_file": lambda path, **kw: Path(path).read_text(encoding="utf-8"),
}


# ---------------------------------------------------------------------------
# Pipeline protocol
# ---------------------------------------------------------------------------


class PipelineRunner(Protocol):
    """Protocol representing the orchestrator pipeline execution entry point."""

    async def process(
        self,
        raw_input: Any,
        surface_type: str = "cli",
        external_user_id: str = "cli-user",
        session_id: str | None = None,
    ) -> Response: ...


# ---------------------------------------------------------------------------
# CLI adapter
# ---------------------------------------------------------------------------


class CLIAdapter:
    """CLI surface adapter managing user interaction and console rendering."""

    def __init__(self, pipeline: PipelineRunner) -> None:
        self.pipeline = pipeline
        self.session_id = f"cli-session-{uuid.uuid4().hex[:6]}"
        self.config = load_config()

    async def send_message_async(self, text: str) -> Response:
        """Send a single message to the pipeline asynchronously."""
        user_id = self.config.get("user_id", "local-developer")
        return await self.pipeline.process(
            raw_input=text,
            surface_type="cli",
            external_user_id=user_id,
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

    # -- Local tool execution (ADR-006) ------------------------------------

    def execute_local_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool locally on the developer's machine.

        Used when the agent requests a tool action with ``execution_target='local'``.
        New handlers can be added to :data:`LOCAL_TOOL_HANDLERS` by tool name.
        """
        handler = LOCAL_TOOL_HANDLERS.get(tool_name)
        if not handler:
            return f"No local handler registered for tool '{tool_name}'."
        try:
            result = handler(**arguments)
            return str(result)
        except Exception as e:
            return f"Local execution failed: {e}"

    # -- Prompt toolkit helpers ---------------------------------------------

    def _create_prompt_session(self) -> Any:
        """Create a prompt_toolkit PromptSession with persistent file history.

        Returns ``None`` when prompt_toolkit is unavailable, in which case the
        REPL gracefully degrades to the built-in ``input()`` function.
        """
        if not HAS_PROMPT_TOOLKIT:
            return None
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            history_file = CONFIG_DIR / "history.txt"
            return PromptSession(history=FileHistory(str(history_file)))
        except Exception:  # pragma: no cover — filesystem edge cases
            return None

    def _read_input(self, prompt_session: Any) -> str:
        """Read user input via prompt_toolkit when available, else bare ``input()``."""
        if prompt_session is not None:
            result: str = str(prompt_session.prompt("\n[CLI] > ")).strip()
            return result
        return input("\n[CLI] > ").strip()

    # -- REPL loop ----------------------------------------------------------

    def run_repl(self) -> None:
        """Run the interactive console REPL."""
        print("=" * 60)
        print("Surface-Aware Agent Orchestration - Interactive CLI REPL")
        print(f"Session ID: {self.session_id}")
        if self.config.api_endpoint:
            print(f"API Endpoint: {self.config.api_endpoint}")
        print("Commands: /approve <id>, /deny <id>, exit")
        print("=" * 60)

        prompt_session = self._create_prompt_session()

        while True:
            try:
                user_input = self._read_input(prompt_session)
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

        # Handle local tool actions passed via response metadata (ADR-006).
        # When the pipeline or remote API flags tool actions for client-side
        # execution, they are expected under metadata["local_tool_actions"].
        local_actions = response.metadata.get("local_tool_actions", [])
        for action in local_actions:
            tool_name = action.get("tool_name", "")
            arguments = action.get("arguments", {})
            print("-" * 50)
            print(f"[LOCAL TOOL] Executing '{tool_name}' client-side...")
            result = self.execute_local_tool(tool_name, arguments)
            print(f"[LOCAL TOOL RESULT]: {result}")

        print("-" * 50)
        print(f"[REPLY - {response.persona_used.upper()}]:\n{response.reply_text}")
        print("-" * 50)
