# Apple Intelligence TUI

A privacy-first terminal interface to Apple's on-device Foundation Models. Runs entirely on-device — no data leaves your Mac.

> Requires macOS 26+ with Apple Intelligence enabled and Apple Silicon.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![macOS](https://img.shields.io/badge/macOS-26+-black) ![License](https://img.shields.io/badge/license-MIT-green) ![Version](https://img.shields.io/badge/version-0.3.0-purple)

---

## Why

Cloud AI (ChatGPT, Claude) sees everything you send. Apple Intelligence runs the model on your device. This TUI gives you a fast keyboard-driven interface for sensitive tasks — drafting, summarising, proofreading — without any data leaving your machine.

---

## Features

- **Privacy-first** — 100% on-device via Apple Foundation Models, zero network calls
- **Full TUI** — Claude Code-inspired aesthetic, dark, dense, terminal-native
- **Pipe mode** — `ai "summarize this" < file.txt` with no UI, pure stdin/stdout
- **12 built-in commands** — writing tools, smart reply, content tagging, extraction
- **Command picker** — type `/` to browse, `↑↓` to navigate, `Enter` to select
- **Plugin system** — add custom `/commands` via TOML files in `~/.config/apple-tui/commands/`
- **Tool use** — model can read local files and clipboard mid-conversation
- **Persistent sessions** — conversation history saved to `~/.config/apple-tui/sessions/`
- **Guardrail toggle** — switch between default and permissive content transformations

---

## Requirements

```
macOS 26+
Apple Silicon (M-series)
Apple Intelligence enabled in System Settings
Python 3.11+
```

Enable Apple Intelligence: **System Settings → Apple Intelligence & Siri → Enable Apple Intelligence**

---

## Installation

**Recommended — pipx (isolated, global `ai` command):**

```bash
pipx install git+https://github.com/amirnaeem/apple-tui.git
```

**From source:**

```bash
git clone https://github.com/amirnaeem/apple-tui.git
cd apple-tui
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

---

## Usage

```bash
# Interactive TUI
ai

# One-shot pipe mode
ai "summarize this text"
ai "what are the action items?" < meeting-notes.txt
cat contract.txt | ai /formal

# Structured JSON output (pipe to jq)
ai --json /actions < meeting-notes.txt
ai --json /bullets < report.txt | jq '.[]'
cat notes.txt | ai --json /tag

# With options
ai --guardrails permissive "rewrite this"
ai help
```

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in input |
| `/` | Open command picker |
| `↑` `↓` | Navigate picker |
| `Enter` / `Tab` | Select command |
| `Esc` | Dismiss picker |
| `Ctrl+G` | Toggle guardrails |
| `Ctrl+N` | New session |
| `Ctrl+L` | Clear history |
| `Ctrl+C` | Quit |

---

## Built-in Commands

| Command | Description |
|---------|-------------|
| `/summarize` | 2–4 sentence summary |
| `/bullets` | Key points as bullet list |
| `/formal` | Rewrite in professional tone |
| `/friendly` | Rewrite in warm casual tone |
| `/concise` | Make significantly shorter |
| `/proofread` | Fix grammar, spelling, punctuation |
| `/table` | Reorganise as a structured table |
| `/reply` | Draft 3 reply options (Smart Reply) |
| `/notify` | Summarise notifications |
| `/tag` | Generate topic tags (Content Tagging) |
| `/actions` | Extract action items and tasks |
| `/entities` | Extract people, orgs, locations |

---

## Custom Plugins

Add your own commands by dropping a `.toml` file into `~/.config/apple-tui/commands/`:

```toml
# ~/.config/apple-tui/commands/legal.toml
name        = "/legal"
description = "Simplify legal text to plain English"
template    = "Rewrite the following legal text in plain English. Preserve all meaning:\n\n"
```

Plugins appear in the command picker automatically on next launch. Share them as gists.

---

## Tool Use

In chat mode, the model can invoke tools mid-conversation:

- **`read_file`** — reads a local file by path (up to 100KB)
- **`clipboard_read`** — reads your current clipboard contents
- **`write_file`** — writes text to a file in your home directory (model asks for confirmation first)

Example: *"Summarize the file at ~/Documents/report.pdf"* — the model will call `read_file` automatically.

---

## How It Works

- Uses [`apple-fm-sdk`](https://github.com/apple/python-apple-fm-sdk) — Apple's official Python SDK for Foundation Models
- **Chat** uses a persistent `LanguageModelSession` (maintains conversation history across turns)
- **Commands** use a fresh `PERMISSIVE` session per invocation (stateless text transformation)
- **Pipe mode** shares the same stream logic as the TUI — same model, no UI overhead
- Streaming via `session.stream_response()` — async generator yielding full snapshot strings
- Built with [Textual](https://github.com/Textualize/textual)

**Context window:** 4096 tokens (input + output). For large pastes, use `/summarize` or `/bullets` first.

---

## Development

The app runs in **MOCK_MODE** on non-macOS systems (Linux, CI), simulating the SDK so you can develop and test without Apple Silicon.

```bash
# Install dev dependencies
pip install -e .

# Run tests (works on any platform)
pytest test_app.py test_new_modules.py -v

# Run directly without installing
python -m apple_tui
```

### Project structure

```
apple_tui/
  __init__.py      # version
  __main__.py      # CLI entry point (pipe mode, help, TUI launcher)
  app.py           # Textual TUI application
  plugins.py       # TOML plugin loader
  sessions.py      # Persistent session storage
  tools.py         # SDK Tool subclasses (read_file, clipboard_read, write_file)
docs/ideas/        # Brainstorm one-pagers
test_app.py        # TUI pytest suite (49 tests)
test_new_modules.py # Module pytest suite (63 tests)
```

---

## Roadmap

- [ ] Homebrew formula
- [x] `write_file` tool (with confirmation prompt)
- [x] Structured output mode — `ai --json /actions < notes.txt | jq '.[]'`
- [x] Named sessions with `--session <name>`
- [x] Context window usage indicator

---

## License

MIT
