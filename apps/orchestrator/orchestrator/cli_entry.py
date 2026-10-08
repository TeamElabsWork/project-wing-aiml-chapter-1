"""CLI entry point for running the interactive demo or single query execution.

Invoked via `python -m orchestrator.cli_entry`, `make demo`, or `make demo-safety`.
"""

import sys

from surface_cli.repl import CLIAdapter

from orchestrator.pipeline import create_pipeline


def main() -> None:
    # Check for --safety flag
    safety_mode = False
    args = [a for a in sys.argv[1:] if a != "--safety"]
    if len(args) < len(sys.argv) - 1 or "--safety" in sys.argv:
        safety_mode = True

    # When in safety mode: runtime=scripted and approval_manager=pending
    pipeline = create_pipeline(
        config_dir="config",
        runtime_override="scripted" if safety_mode else None,
        approval_override="pending" if safety_mode else None,
    )
    cli_adapter = CLIAdapter(pipeline=pipeline)

    if args:
        # One-off command line invocation: python -m orchestrator.cli_entry "Hello"
        query = " ".join(args)
        resp = cli_adapter.send_message(query)
        cli_adapter.render_response(resp)
    else:
        # Full interactive REPL
        cli_adapter.run_repl()


if __name__ == "__main__":
    main()
