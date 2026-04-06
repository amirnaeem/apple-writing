"""
Entry point for the `ai` CLI command.

  ai                         Launch interactive TUI
  ai "summarize this text"   One-shot pipe mode (prompt as argument)
  ai < file.txt              One-shot pipe mode (stdin)
  ai /summarize < file.txt   One-shot with a built-in command
  ai --version               Print version
"""

import argparse
import asyncio
import sys

from apple_tui import __version__


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ai",
        description="Apple Intelligence — private, on-device AI in your terminal.",
    )
    parser.add_argument("prompt", nargs="*", help="Prompt text (pipe mode)")
    parser.add_argument("--version", action="version", version=f"apple-tui {__version__}")
    parser.add_argument("--guardrails", choices=["default", "permissive"], default="default",
                        help="Guardrail mode for the session (default: default)")
    return parser.parse_args()


async def _run_pipe(prompt: str, guardrails: int) -> None:
    """Stream a single response to stdout without launching the TUI."""
    from apple_tui.app import make_chat_session, check_availability
    from rich.markup import escape

    available, msg = check_availability()
    if not available:
        print(msg, file=sys.stderr)
        sys.exit(1)

    session = make_chat_session(guardrails)
    last = ""
    try:
        async for snapshot in session.stream_response(prompt):
            delta = snapshot[len(last):]
            print(delta, end="", flush=True)
            last = snapshot
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    print()  # trailing newline


def main() -> None:
    args = _parse_args()
    guardrails = 1 if args.guardrails == "permissive" else 0

    # Collect prompt: argument words + stdin (if piped)
    parts = list(args.prompt)
    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            parts.append(stdin_text)

    if parts:
        # Pipe mode — no TUI
        prompt = " ".join(parts)
        asyncio.run(_run_pipe(prompt, guardrails))
    else:
        # Interactive TUI mode
        from apple_tui.app import AppleIntelligenceTUI
        AppleIntelligenceTUI().run()


if __name__ == "__main__":
    main()
