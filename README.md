# Apple Intelligence TUI

A privacy-first terminal interface to Apple's on-device Foundation Models. Runs entirely on-device — no data leaves your Mac.

> Requires macOS 26+ with Apple Intelligence enabled and Apple Silicon.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![macOS](https://img.shields.io/badge/macOS-26+-black) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Why

Cloud AI (ChatGPT, Claude) sees everything you send. Apple Intelligence runs the model on your device. This TUI gives you a fast keyboard-driven interface for sensitive tasks — drafting, summarising, proofreading — without any data leaving your machine.

---

## Features

- **Free-form chat** with persistent session memory
- **12 built-in commands** for writing tools, smart reply, content tagging, and extraction
- **Command picker** — type `/` to browse and select commands with `↑↓` + `Enter`
- **Guardrail toggle** — switch between default and permissive content transformations
- **Streaming output** — see the response as it's generated
- **Apple Intelligence color palette** — dark mode, system purple/blue accents

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

```bash
git clone https://github.com/amirnaeem/apple-tui.git
cd apple-tui

python -m venv .venv
source .venv/bin/activate

pip install apple-fm-sdk textual
```

---

## Usage

```bash
python app.py
```

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `/` | Open command picker |
| `↑` `↓` | Navigate picker |
| `Enter` / `Tab` | Select command |
| `Esc` | Dismiss picker |
| `Ctrl+G` | Toggle guardrails |
| `Ctrl+N` | New session |
| `Ctrl+L` | Clear history |
| `Ctrl+C` | Quit |

### Commands

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

## Development

The app runs in **MOCK_MODE** on non-macOS systems (Linux, CI), simulating the SDK so you can develop and test without an Apple Silicon Mac.

```bash
# Run tests (works on any platform)
pip install pytest pytest-asyncio
pytest test_app.py -v
```

---

## How it works

- Uses [`apple-fm-sdk`](https://github.com/apple/python-apple-fm-sdk) — Apple's official Python SDK for Foundation Models
- **Chat** uses a persistent `LanguageModelSession` (maintains conversation history)
- **Commands** use a fresh `PERMISSIVE` session per invocation (stateless text transformation)
- Streaming via `session.stream_response()` — an async generator yielding full snapshot strings
- Built with [Textual](https://github.com/Textualize/textual)

**Context window:** 4096 tokens (input + output). For large pastes, use `/summarize` or `/bullets` first.

---

## License

MIT
