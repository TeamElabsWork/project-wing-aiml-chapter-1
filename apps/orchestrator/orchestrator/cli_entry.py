"""CLI entry point for running the interactive demo or single query execution.

Invoked via `python -m orchestrator.cli_entry` or `make demo`.
"""

import sys

from surface_cli.repl import CLIAdapter

from orchestrator.pipeline import create_pipeline


def main() -> None:
    pipeline = create_pipeline(config_dir="config")
    cli_adapter = CLIAdapter(pipeline=pipeline)

    if len(sys.argv) > 1:
        # One-off command line invocation: python -m orchestrator.cli_entry "Hello"
        query = " ".join(sys.argv[1:])
        resp = cli_adapter.send_message(query)
        cli_adapter.render_response(resp)
    else:
        # Full interactive REPL
        cli_adapter.run_repl()


if __name__ == "__main__":
    main()
