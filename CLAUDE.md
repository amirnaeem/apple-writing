# Apple Intelligence TUI — Project Guide

> **IMPORTANT:** Read this fully at session start. Keep responses focused and changes surgical.

---

## What this is
A privacy-first terminal interface to Apple's on-device Foundation Models (`apple-fm-sdk`).
No data leaves the device. Built with Python + Textual.

---

## Workflow: Explore → Plan → Implement → Commit

1. **Explore** — read relevant files before touching anything
2. **Plan** — propose approach and confirm before writing code
3. **Implement** — make changes, run tests, iterate until green
4. **Commit** — summarize what changed and why

**Never skip the Explore step.** Never modify code you haven't read.

---

## Project structure
```
apple_tui/
  __init__.py        # version
  __main__.py        # CLI entry: `ai` command, pipe mode, help
  app.py             # Textual TUI (all UI logic)
  tools.py           # SDK Tool subclasses (read_file, clipboard_read)
  plugins.py         # TOML plugin loader
  sessions.py        # Persistent session serialization
docs/ideas/          # Brainstorm one-pagers
test_app.py          # TUI pytest suite (43 tests)
test_new_modules.py  # Module pytest suite (38 tests)
```

---

## Bash commands

```bash
# Test (works on any platform — MOCK_MODE auto-activates on non-Darwin)
pytest test_app.py test_new_modules.py -v

# Run directly
python -m apple_tui
python -m apple_tui "prompt"
python -m apple_tui /summarize < file.txt

# Install
pip install -e .                    # local editable
python -m pipx install . --force   # global `ai` command

# Build wheel
python -m build --wheel
```

---

## Key constraints

**IMPORTANT — never violate these:**

- **MOCK_MODE**: `os.uname().sysname != "Darwin"` — all non-macOS runs use mock SDK stubs. Mock classes must subclass `int` where the real SDK uses IntEnum.
- **4096 token context window** — hard limit, no Python API to check usage
- **Streaming contract**: `session.stream_response()` yields full snapshots (not deltas). Delta = `snapshot[len(last):]`. Real SDK typically yields 1 snapshot for short responses.
- **Always escape user text**: `from rich.markup import escape` — apply before every Rich markup interpolation
- **Timer leak guard**: cancel `_spinner_timer` before reassigning it
- **Tool API**: real SDK `Tool` subclasses require `arguments_schema` property returning a `GenerationSchema`, and `call(self, args)` receiving `GeneratedContent`. Use `@fm.generable` + `fm.guide()` to define schemas.

---

## SDK classes in use

```python
from apple_fm_sdk import (
    LanguageModelSession,
    SystemLanguageModel,
    SystemLanguageModelGuardrails,   # int subclass: DEFAULT=0, PERMISSIVE=1
    SystemLanguageModelUseCase,       # int subclass: GENERAL=0, CONTENT_TAGGING=1
    SystemLanguageModelUnavailableReason,
    Tool,                             # abstract — requires arguments_schema + call(args)
    GenerationOptions,
)

import apple_fm_sdk as fm
# Schema pattern for Tool subclasses:
@fm.generable("description")
class MyParams:
    field: str = fm.guide("description of field")

class MyTool(fm.Tool):
    name = "my_tool"
    description = "..."
    @property
    def arguments_schema(self): return MyParams.generation_schema()
    async def call(self, args) -> str:
        value = args.value(str, for_property="field")
        ...
```

---

## Coding conventions

- No type annotations on code you didn't change
- No docstrings unless the logic is genuinely non-obvious
- `escape()` all user-supplied strings before Rich markup interpolation
- Tests use Textual pilot: `async with app.run_test() as pilot:`
- `KeyboardInterrupt` is not a subclass of `Exception` — catch it explicitly, exit with code 130
- Pipe mode commands: detect `/command` prefix → `make_command_session(cmd)` + `cmd.template + content`
- Build backend: `setuptools.build_meta` (not `setuptools.backends.legacy:build`)

---

## Config paths

- Sessions: `~/.config/apple-tui/sessions/`
- Plugins: `~/.config/apple-tui/commands/*.toml`

---

## Testing

- **Always run tests after any change.** All 81 tests must stay green.
- Tests force `MOCK_MODE=True` by patching `os.uname` before import — never hit the real SDK
- TDD: write a failing test first, confirm it fails, implement, confirm it passes
- Integration tests use `pilot.pause()` after key presses — never remove these

---

## Common gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `Can't instantiate abstract class Tool` | Missing `arguments_schema` | Add `@property arguments_schema` returning `GenerationSchema` |
| `setuptools.backends.legacy not found` | Wrong build backend | Use `setuptools.build_meta` |
| Traceback on Ctrl+C | `KeyboardInterrupt` not caught | Catch explicitly, `sys.exit(130)` |
| Pipe mode outputs `null` | Command sent to chat session | Detect `/cmd` prefix, route to `make_command_session` |
| `Static has no attribute 'renderable'` | Wrong Textual API | Use `str(static.render())` |
| `RichLog has no attribute '_lines'` | Private API | Use `len(history.lines)` |

---

## What NOT to build

- `run_shell` tool — security boundary, explicitly deferred
- macOS Share Sheet / Quick Actions — low discovery for terminal devs
- Web UI or Electron wrapper — defeats the privacy value prop
- Multi-model support — muddies the on-device message
