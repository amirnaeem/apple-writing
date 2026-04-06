"""
Entry point for the `ai` CLI command.

  ai                         Launch interactive TUI
  ai help                    Show all commands and usage
  ai "summarize this text"   One-shot pipe mode (prompt as argument)
  ai < file.txt              One-shot pipe mode (stdin)
  ai /summarize < file.txt   One-shot with a built-in command
  ai --version               Print version
"""

import argparse
import asyncio
import sys

from apple_tui import __version__


def _print_help() -> None:
    from apple_tui.app import COMMANDS

    lines = [
        f"Apple Intelligence TUI  v{__version__}  — private, on-device AI",
        "",
        "USAGE",
        "  ai                          Launch interactive TUI",
        "  ai \"<prompt>\"               One-shot answer (pipe mode)",
        "  ai /command < file.txt      Run a command on stdin",
        "  ai --guardrails permissive  Use permissive content mode",
        "  ai --version                Show version",
        "  ai help                     Show this help",
        "",
        "BUILT-IN COMMANDS",
    ]

    for cmd in COMMANDS:
        lines.append(f"  {cmd.name:<14}  {cmd.description}")

    lines += [
        "",
        "EXAMPLES",
        "  ai \"what is a closure in Python?\"",
        "  ai /summarize < meeting-notes.txt",
        "  cat contract.txt | ai /formal",
        "  ai /bullets < report.txt | pbcopy",
        "",
        "KEYBOARD SHORTCUTS  (inside TUI)",
        "  /            Open command picker",
        "  ↑ ↓          Navigate picker",
        "  Enter        Send message / select command",
        "  Shift+Enter  New line in input",
        "  Esc          Dismiss picker",
        "  Ctrl+G       Toggle guardrails",
        "  Ctrl+N       New session",
        "  Ctrl+L       Clear history",
        "  Ctrl+C       Quit",
        "",
        "PLUGINS",
        "  Drop a .toml file in ~/.config/apple-tui/commands/ to add custom commands.",
        "  Example:  name=\"/legal\"  description=\"...\"  template=\"Rewrite as plain English:\\n\\n\"",
        "",
        "TOOL USE  (inside TUI)",
        "  read_file      Model can read a local file by path",
        "  clipboard_read Model can read your current clipboard",
    ]

    print("\n".join(lines))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ai",
        description="Apple Intelligence — private, on-device AI in your terminal.",
        add_help=True,
    )
    parser.add_argument("prompt", nargs="*", help="Prompt text or 'help'")
    parser.add_argument("--version", action="version", version=f"apple-tui {__version__}")
    parser.add_argument("--guardrails", choices=["default", "permissive"], default="default",
                        help="Guardrail mode for the session (default: default)")
    return parser.parse_args()


async def _run_pipe(prompt: str, guardrails: int) -> None:
    """Stream a single response to stdout without launching the TUI."""
    from apple_tui.app import (
        make_chat_session, make_command_session, check_availability, COMMANDS,
    )

    available, msg = check_availability()
    if not available:
        print(msg, file=sys.stderr)
        sys.exit(1)

    # Resolve /command prefix → command session + template
    first_word = prompt.split()[0] if prompt.split() else ""
    effective_prompt = prompt

    if first_word.startswith("/"):
        # Exact match first, then prefix match
        exact = [c for c in COMMANDS if c.name == first_word]
        prefix = [c for c in COMMANDS if c.name.startswith(first_word)] if not exact else []
        matched = exact or prefix

        if not matched:
            close = [c.name for c in COMMANDS if first_word[1:] in c.name]
            hint = f"  Did you mean: {', '.join(close)}" if close else ""
            print(f"Unknown command: {first_word}{hint}", file=sys.stderr)
            print("Run 'ai help' to see all available commands.", file=sys.stderr)
            sys.exit(1)

        if len(matched) > 1:
            names = ", ".join(c.name for c in matched)
            print(f"Ambiguous command '{first_word}' matches: {names}", file=sys.stderr)
            print(f"Use a longer prefix, e.g. '{matched[0].name}'", file=sys.stderr)
            sys.exit(1)

        cmd = matched[0]
        content = prompt[len(first_word):].strip()
        effective_prompt = cmd.template + content
        session = make_command_session(cmd)
    else:
        session = make_chat_session(guardrails)

    last = ""
    try:
        async for snapshot in session.stream_response(effective_prompt):
            delta = snapshot[len(last):]
            print(delta, end="", flush=True)
            last = snapshot
        print()  # trailing newline
    except KeyboardInterrupt:
        print()  # move cursor to clean line
        sys.exit(130)  # standard shell exit code for Ctrl+C
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


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
        # Check for help before appending stdin content
        if args.prompt == ["help"]:
            _print_help()
            return
        prompt = " ".join(parts)
        # Pipe mode — no TUI
        try:
            asyncio.run(_run_pipe(prompt, guardrails))
        except KeyboardInterrupt:
            print()
            sys.exit(130)
    else:
        # Interactive TUI mode
        from apple_tui.app import AppleIntelligenceTUI
        try:
            AppleIntelligenceTUI().run()
        except KeyboardInterrupt:
            sys.exit(130)


if __name__ == "__main__":
    main()
