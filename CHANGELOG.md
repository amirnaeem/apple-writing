# Changelog

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

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
