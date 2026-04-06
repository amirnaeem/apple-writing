# Changelog

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

## [0.3.1] — 2026-04-07

### Added
- **Homebrew formula** — `brew tap amirnaeem/tap && brew install apple-tui`
  - Formula lives in dedicated tap [amirnaeem/homebrew-tap](https://github.com/amirnaeem/homebrew-tap)
  - Creates an isolated virtualenv via `virtualenv_create`, pinned to Python 3.11, macOS-only
  - `brew test` verifies `ai --version` output matches formula version

### Fixed
- Binary stdin (e.g. `.docx`, `.pdf`) now exits 1 with a helpful conversion hint instead of
  crashing with a raw `UnicodeEncodeError` from the SDK

## [0.3.0] — 2026-04-06

### Added
- **`write_file` tool** — model can write text to files within the user's home directory
  - Security: rejects paths outside `~`, rejects content > 200 KB
  - Model instructed to ask for confirmation before calling the tool
  - Available in real-SDK chat sessions alongside `read_file` and `clipboard_read`
- **Context window usage indicator** — header now shows `~N/4096 tok` estimate
  - Estimated via 4-chars-per-token heuristic from prompt + response lengths
  - Colour-coded: grey → orange (>50%) → red (>80%)
  - Resets on `Ctrl+N` (new session) and `Ctrl+L` (clear history)
- **13 new tests** — `TestWriteFileTool` (8) and `TestContextWindowIndicator` (5); 110 total

## [0.2.2] — 2026-04-06

### Added
- **Named sessions** — `--session <name>` flag persists and restores a named conversation
  - `save_transcript(data, name=)` writes `<name>.json`; unnamed uses date-based filename
  - `load_transcript(name=)` loads by name or falls back to most-recent
  - `--session` defaults to `None` (existing behaviour unchanged)

## [0.2.1] — 2026-04-06

### Added
- **`--json` flag** — structured JSON array output for list commands (`/actions`, `/bullets`, `/entities`, `/tag`, `/notify`)
  - `ai --json /actions < notes.txt | jq '.[]'`
  - Strips markdown fences from model output before parsing
  - Falls back to line-splitting if JSON parse fails
  - Warns on stderr when used with non-list commands
- **`ai help`** now annotates JSON-capable commands with `[json]` tag

## [0.2.0] — 2026-04-06

### Added
- **Pipe mode** — `ai "prompt"`, `ai /command < file.txt`, `cat file | ai /formal`
- **`ai help`** — lists all commands, keyboard shortcuts, examples, plugin format
- **Plugin system** — custom `/commands` via `~/.config/apple-tui/commands/*.toml`
- **Persistent sessions** — JSON serialized to `~/.config/apple-tui/sessions/`
- **Tool use** — `read_file` and `clipboard_read` wired into chat sessions on real macOS
- **`--guardrails` flag** — pipe mode guardrail control (`default` / `permissive`)
- **Ambiguous prefix detection** — `ai /f` errors with `matches: /formal, /friendly`
- **38 new tests** — `test_new_modules.py` covers plugins, sessions, tools, pipe mode

### Fixed
- Pipe mode `/commands` now correctly route to command sessions with templates — previously sent as raw chat, producing `null` or hallucinated responses
- `ai help < file.txt` now shows help regardless of stdin content
- `KeyboardInterrupt` (Ctrl+C) exits cleanly with code 130, no traceback
- `ReadFileTool` / `ClipboardReadTool` now implement correct SDK `arguments_schema` + `call(args)` API — previously crashed on instantiation
- Tools instantiated once at module load instead of on every session reset
- Build backend fixed to `setuptools.build_meta`
- `pipx install .` now works end-to-end

### Security
- All subprocess calls use list form, no `shell=True`
- No secrets, tokens, or credentials in codebase

## [0.1.0] — 2026-04-06

### Added
- Terminal TUI for Apple's on-device Foundation Models via `apple-fm-sdk`
- Free-form chat with persistent session memory across turns
- 12 built-in `/commands` for writing tools, smart reply, content tagging, and extraction:
  `/summarize`, `/bullets`, `/formal`, `/friendly`, `/concise`, `/proofread`,
  `/table`, `/reply`, `/notify`, `/tag`, `/actions`, `/entities`
- Keyboard command picker — type `/` to browse, `↑↓` to navigate, `Enter`/`Tab` to select
- Guardrail toggle (`Ctrl+G`) — default vs permissive content transformations
- Streaming output with live spinner and inline preview
- Apple Intelligence color palette (system purple `#BF5AF2`, system blue `#0A84FF`)
- `MOCK_MODE` for development and CI on non-macOS systems
- Availability check on launch with actionable error messages for all four SDK reason codes
- `Ctrl+C` to quit (priority binding overrides TextArea copy)

### Fixed
- Rich markup injection — user text now escaped via `rich.markup.escape`
- Spinner timer leak — previous timer cancelled before new one is created
- Mock SDK enum classes now subclass `int` so constructors accept integer arguments
- `_stream` finally block wrapped in try/except to handle app teardown during tests

### Security
- No network calls — all inference runs on-device via Apple Foundation Models
- No credentials, tokens, or API keys required or stored
