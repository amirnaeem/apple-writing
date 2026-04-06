# Apple Intelligence TUI — Project Guide

## What this is
A privacy-first terminal interface to Apple's on-device Foundation Models (`apple-fm-sdk`).
No data leaves the device. Built with Python + Textual.

## Project structure
```
apple_tui/          # Package (created in v0.2)
  __init__.py
  __main__.py       # CLI entry point: `ai` command
  app.py            # Textual TUI
  core.py           # Shared stream logic (used by both TUI and pipe mode)
  tools.py          # SDK Tool subclasses (read_file, clipboard_read)
  plugins.py        # TOML plugin loader
  sessions.py       # Persistent session serialization
docs/ideas/         # Brainstorm one-pagers
test_app.py         # pytest suite (43 tests)
```

## Key constraints
- **MOCK_MODE**: `os.uname().sysname != "Darwin"` — all non-macOS runs use mock SDK stubs
- **4096 token context window** — hard limit, no Python API to check current usage
- **Streaming contract**: `session.stream_response()` is an async generator yielding full snapshots (not deltas). Delta = `snapshot[len(last):]`
- **Always escape user text**: use `rich.markup.escape()` before interpolating into Rich markup strings

## SDK classes in use
```python
from apple_fm_sdk import (
    LanguageModelSession,
    SystemLanguageModel,
    SystemLanguageModelGuardrails,   # int subclass: DEFAULT=0, PERMISSIVE=1
    SystemLanguageModelUseCase,       # int subclass: GENERAL=0, CONTENT_TAGGING=1
    SystemLanguageModelUnavailableReason,
    Tool,                             # Subclass for agentic tool use
    GenerationOptions,                # temperature, max_tokens, sampling
    Transcript,                       # Full session history
)
```

## Commands
```bash
pytest test_app.py -v        # Run tests (works on any platform via MOCK_MODE)
python app.py                # Run TUI directly (pre-package)
pipx install .               # Install as `ai` CLI (post-package)
ai                           # Launch TUI
ai "summarize this"          # Pipe mode one-shot
ai /summarize < file.txt     # Pipe mode with command
```

## Coding conventions
- No type annotations on code you didn't change
- No docstrings unless the logic is genuinely non-obvious
- `escape()` all user-supplied strings before Rich markup interpolation
- Mock SDK stubs must subclass `int` where the real SDK uses IntEnum
- Tests use Textual pilot for integration tests — `async with app.run_test() as pilot:`
- `_spinner_timer` must be cancelled before reassignment (timer leak guard)

## Config paths
- Sessions: `~/.config/apple-tui/sessions/`
- Plugins: `~/.config/apple-tui/commands/*.toml`

## What NOT to build (v1)
- `run_shell` tool — security boundary, deferred
- macOS Share Sheet / Quick Actions — low discovery for terminal devs
- Web UI, Electron wrapper — defeats the privacy value prop
- Multi-model support — muddies the on-device message
