# apple-tui — Refined Concept

## Problem Statement
How might we build a terminal-native Apple Intelligence tool that macOS developers install via Homebrew, use daily for private AI work, and extend with their own commands — without ever sending data to the cloud?

## Recommended Direction

A **layered CLI** where every surface is useful independently:

- **`ai "prompt" < file.txt`** — pipe mode, zero UI, stdin/stdout, scriptable
- **`ai`** — full TUI with Claude Code aesthetic: dense, dark, terminal-native
- **`ai /summarize`** — command palette with community-extensible plugins

The model has **tool use** for reading files and clipboard — no shell execution in v1 (too risky). **Persistent sessions** survive restarts. Commands are **structured-output-capable** so output can be piped to `jq`.

The UI is rebuilt around the Claude Code aesthetic: turn-by-turn message blocks, compact header, live streaming in the status bar, no web-app pretense.

## Key Assumptions to Validate
- [ ] `apple-fm-sdk` Tool API is stable enough to ship — test by building one real tool (`read_file`) end-to-end
- [ ] Homebrew formula maintenance is low-burden — validate by writing the formula and running it on a clean Mac
- [ ] Pipe mode + TUI can share the same core without fighting each other — validate by extracting the stream logic to a function both surfaces call
- [ ] Plugin TOML format is expressive enough for real developer workflows — validate by writing 5 community-style plugins yourself

## MVP Scope (v0.2 — next milestone)

**In:**
- Rebuilt UI matching Claude Code aesthetic (turn blocks, dense header, cleaner input zone)
- `pipx install apple-tui` global command (Homebrew formula after that)
- `ai "prompt"` and `ai < file.txt` pipe mode
- 2 built-in tools: `read_file`, `clipboard_read`
- Persistent sessions serialized to `~/.config/apple-tui/`
- Plugin system: custom commands from `~/.config/apple-tui/commands/*.toml`

**Out of MVP:**
- `write_file` and `run_shell` tools (security review needed first)
- Structured output / JSON schema mode
- Full macOS OS integration (Share Sheet, Quick Actions)
- Homebrew formula (pipx first, formula after traction)

## Not Doing (and Why)
- **Shell execution tool** — `run_shell` is a security boundary. Not v1. Get file reading right first.
- **macOS Share Sheet / Quick Actions** — high effort, low discovery. Terminal devs don't use Share Sheets.
- **Web UI or Electron wrapper** — defeats the entire point. This is a terminal tool, full stop.
- **Multi-model support** — the value prop is on-device privacy. Adding cloud models muddies the message.
- **Conversation branching / tree UI** — complexity for a fraction of users. Linear history is fine.

## Open Questions
- Does `apple-fm-sdk` Tool API work with streaming? (i.e., can the model stream while also calling tools mid-generation?)
- What's the right config format — TOML, YAML, or just Python files for plugins?
- Should sessions be named by the user or auto-named by date/topic?
