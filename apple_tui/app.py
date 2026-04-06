"""
Apple Intelligence TUI

A terminal interface to Apple's on-device Foundation Models.
Uses apple-fm-sdk on macOS 26+ with Apple Intelligence enabled.

Controls:
  Enter          Send message
  Shift+Enter    New line in input
  /              Open command picker
  ↑↓             Navigate picker
  Tab/Enter      Select command
  Esc            Dismiss picker
  Ctrl+G         Toggle guardrails
  Ctrl+N         New session
  Ctrl+L         Clear history
  Ctrl+C         Quit
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Optional

from rich.markup import escape

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Footer, Label, RichLog, Static, TextArea
from textual.worker import get_current_worker

# ── Apple Intelligence color palette ──────────────────────────────────────────
C_BG     = "#000000"
C_BG2    = "#1C1C1E"
C_BG3    = "#2C2C2E"
C_SEP    = "#38383A"
C_LABEL3 = "#48484A"
C_LABEL2 = "#8E8E93"
C_LABEL1 = "#FFFFFF"
C_PURPLE = "#BF5AF2"
C_BLUE   = "#0A84FF"
C_RED    = "#FF453A"
C_ORANGE = "#FF9F0A"
C_INDIGO = "#5E5CE6"

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# Pre-built gradient for the header title (computed once at import)
_GRADIENT = [C_INDIGO, "#7D56F4", "#9F50EC", C_PURPLE, "#D4569E",
             "#E85E6C", "#F0703A", C_ORANGE, "#F0703A", "#E85E6C",
             "#D4569E", C_PURPLE, "#9F50EC", "#7D56F4", C_INDIGO]
_TITLE_COLORED = "".join(
    f"[bold {_GRADIENT[i % len(_GRADIENT)]}]{ch}[/bold {_GRADIENT[i % len(_GRADIENT)]}]"
    for i, ch in enumerate("Apple Intelligence")
)

# ── SDK ────────────────────────────────────────────────────────────────────────

MOCK_MODE = os.uname().sysname != "Darwin"

if MOCK_MODE:
    class SystemLanguageModelUseCase(int):
        GENERAL = 0
        CONTENT_TAGGING = 1

    class SystemLanguageModelGuardrails(int):
        DEFAULT = 0
        PERMISSIVE_CONTENT_TRANSFORMATIONS = 1

    class SystemLanguageModelUnavailableReason:
        APPLE_INTELLIGENCE_NOT_ENABLED = 0
        DEVICE_NOT_ELIGIBLE = 1
        MODEL_NOT_READY = 2
        UNKNOWN = 255

    class SystemLanguageModel:
        def __init__(self, use_case=0, guardrails=0):
            self.use_case = use_case
            self.guardrails = guardrails

        def is_available(self):
            return True, None

    class LanguageModelSession:
        def __init__(self, instructions=None, model=None):
            self._uc = getattr(model, "use_case", 0)

        async def stream_response(self, prompt, options=None):
            short = prompt[:100].replace("\n", " ")
            reply = f'[mock] "{short}{"…" if len(prompt) > 100 else ""}"'
            acc = ""
            await asyncio.sleep(0.3)
            for word in reply.split():
                await asyncio.sleep(0.04)
                acc += ("" if not acc else " ") + word
                yield acc
else:
    import apple_fm_sdk
    LanguageModelSession                 = apple_fm_sdk.LanguageModelSession
    SystemLanguageModel                  = apple_fm_sdk.SystemLanguageModel
    SystemLanguageModelGuardrails        = apple_fm_sdk.SystemLanguageModelGuardrails
    SystemLanguageModelUseCase           = apple_fm_sdk.SystemLanguageModelUseCase
    SystemLanguageModelUnavailableReason = apple_fm_sdk.SystemLanguageModelUnavailableReason

# ── Commands ───────────────────────────────────────────────────────────────────

@dataclass
class Command:
    name: str
    description: str
    template: str
    use_case: int = 0  # 0 = GENERAL, 1 = CONTENT_TAGGING

COMMANDS: list[Command] = [
    Command("/summarize", "2–4 sentence summary",
            "Summarize the following text in 2-4 concise sentences:\n\n"),
    Command("/bullets",   "Key points as bullet list",
            "Extract key points as a concise bulleted list:\n\n"),
    Command("/formal",    "Rewrite in professional tone",
            "Rewrite the following text in a professional, formal tone:\n\n"),
    Command("/friendly",  "Rewrite in warm casual tone",
            "Rewrite the following text in a warm, friendly, conversational tone:\n\n"),
    Command("/concise",   "Make significantly shorter",
            "Rewrite the following text to be significantly shorter while preserving all key information:\n\n"),
    Command("/proofread", "Fix grammar, spelling, punctuation",
            "Proofread the following text. Show the corrected version, then list each change:\n\n"),
    Command("/table",     "Reorganise as a structured table",
            "Reorganise the following information into a clear table with appropriate columns:\n\n"),
    Command("/reply",     "Draft 3 reply options  [Smart Reply]",
            "Write 3 short reply options for the following message. Vary tone: neutral, warm, brief.\n\nMessage:\n"),
    Command("/notify",    "Summarise notifications",
            "Summarise the following notifications into one concise sentence:\n\n"),
    Command("/tag",       "Generate topic tags  [Content Tagging]",
            "Generate 3-7 short lowercase topic tags for the following content:\n\n",
            use_case=1),
    Command("/actions",   "Extract action items and tasks",
            "Extract all action items and next steps. Format as actionable tasks starting with a verb:\n\n"),
    Command("/entities",  "Extract people, orgs, locations",
            "Extract named entities grouped into: People, Organizations, Locations:\n\n"),
]

# Merge user plugins at import time
try:
    from apple_tui.plugins import load_plugins
    COMMANDS = COMMANDS + load_plugins(Command)
except Exception:
    pass

CHAT_SYSTEM = (
    "You are a helpful, knowledgeable assistant. "
    "Answer questions directly and concisely."
)
COMMAND_SYSTEM = (
    "You are a text processing assistant. Perform the requested task on the provided text. "
    "Output only the result with no preamble or meta-commentary."
)

# ── Availability ───────────────────────────────────────────────────────────────

_UNAVAILABLE_MESSAGES = {
    0: ("Apple Intelligence is not enabled.",
        "→ System Settings → Apple Intelligence & Siri → Enable Apple Intelligence"),
    1: ("This device does not support Apple Intelligence.",
        "→ Requires Apple Silicon Mac with macOS 26+"),
    2: ("The on-device model is still downloading.",
        "→ System Settings → Apple Intelligence & Siri → check download progress"),
}

def check_availability() -> tuple[bool, Optional[str]]:
    if MOCK_MODE:
        return True, None
    model = SystemLanguageModel()
    ok, reason = model.is_available()
    if ok:
        return True, None
    code = int(reason) if reason is not None else 255
    headline, hint = _UNAVAILABLE_MESSAGES.get(code, ("Apple Intelligence unavailable.", ""))
    return False, f"{headline}\n{hint}"

# ── Session factories ──────────────────────────────────────────────────────────

def make_chat_session(guardrails: int) -> LanguageModelSession:
    model = SystemLanguageModel(
        use_case=SystemLanguageModelUseCase.GENERAL,
        guardrails=SystemLanguageModelGuardrails(guardrails),
    )
    return LanguageModelSession(instructions=CHAT_SYSTEM, model=model)

def make_command_session(cmd: Command) -> LanguageModelSession:
    model = SystemLanguageModel(
        use_case=SystemLanguageModelUseCase(cmd.use_case),
        guardrails=SystemLanguageModelGuardrails.PERMISSIVE_CONTENT_TRANSFORMATIONS,
    )
    return LanguageModelSession(instructions=COMMAND_SYSTEM, model=model)

# ── ChatInput ──────────────────────────────────────────────────────────────────

class ChatInput(TextArea):
    """
    Multiline input — Enter sends, Shift+Enter adds newline.
    intercept_enter=True routes Enter to PickerSelect instead.
    """
    intercept_enter: bool = False

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class PickerSelect(Message):
        pass

    def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            if self.intercept_enter:
                self.post_message(self.PickerSelect())
            elif text := self.text.strip():
                self.post_message(self.Submitted(text))
        elif event.key == "tab" and self.intercept_enter:
            event.prevent_default()
            event.stop()
            self.post_message(self.PickerSelect())
        else:
            super()._on_key(event)

# ── App ────────────────────────────────────────────────────────────────────────

class AppleIntelligenceTUI(App):

    CSS = f"""
    Screen {{ layout: vertical; background: {C_BG}; }}

    /* ── Header: single compact row ── */
    #header {{
        height: 2;
        background: {C_BG};
        border-bottom: solid {C_SEP};
        padding: 0 2;
        content-align: left middle;
    }}

    /* ── Message history: full-height, tight left gutter ── */
    #history {{
        height: 1fr;
        background: {C_BG};
        padding: 1 2 0 2;
        scrollbar-color: {C_SEP};
        scrollbar-background: {C_BG};
    }}

    /* ── Live status: single row, collapses when idle ── */
    #live {{
        height: 1;
        background: {C_BG};
        border-top: solid {C_SEP};
        padding: 0 2;
        content-align: left middle;
    }}
    #live.idle {{
        height: 0;
        border-top: none;
        padding: 0;
    }}

    /* ── Command picker ── */
    #command-picker {{
        display: none;
        background: {C_BG2};
        border: solid {C_SEP};
        margin: 0 2;
        padding: 1;
        height: auto;
        max-height: 15;
    }}
    #command-picker.visible {{ display: block; }}

    #picker-keys {{
        display: none;
        height: 1;
        padding: 0 3;
        color: {C_LABEL3};
    }}
    #picker-keys.visible {{ display: block; }}

    /* ── Input zone ── */
    #input-hint {{
        height: 1;
        padding: 0 3;
        margin-top: 1;
        color: {C_LABEL3};
    }}

    ChatInput {{
        background: {C_BG2};
        border: solid {C_SEP};
        color: {C_LABEL1};
        height: auto;
        min-height: 3;
        max-height: 8;
        margin: 1 2 1 2;
        padding: 0 1;
    }}
    ChatInput:focus {{ border: solid {C_PURPLE}; }}
    ChatInput.-processing {{ opacity: 0.4; }}

    /* ── Footer: minimal key reference ── */
    Footer {{ height: 1; background: {C_BG2}; color: {C_LABEL3}; }}
    Footer > .footer--key {{ background: {C_BG3}; color: {C_LABEL2}; }}
    """

    BINDINGS = [
        Binding("ctrl+g", "toggle_guardrails", "Guardrails",  show=True),
        Binding("ctrl+n", "new_session",       "New Session", show=True),
        Binding("ctrl+l", "clear_history",     "Clear",       show=True),
        Binding("ctrl+c", "quit",              "Quit",        show=True, priority=True),
    ]

    _guardrails: int = 0
    _processing: bool = False
    _chat_session: Optional[object] = None
    _picker_items: list = []
    _picker_index: int = 0
    _picker_visible: bool = False
    _active_command: Optional[Command] = None
    _spinner_frame: int = 0
    _spinner_timer = None

    # ── Layout ─────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("", id="header", markup=True)
        yield RichLog(id="history", highlight=True, markup=True, wrap=True)
        yield Static("", id="live", markup=True)
        yield Static("", id="command-picker", markup=True)
        yield Label("↑↓ navigate   Enter / Tab select   Esc dismiss", id="picker-keys")
        yield Label("/ commands  ·  Shift+Enter new line", id="input-hint")
        yield ChatInput(id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self._picker_items = []
        self._reset_chat_session()
        self.query_one("#live", Static).add_class("idle")
        self._check_and_warn_availability()
        self.query_one(ChatInput).focus()

    # ── Header ─────────────────────────────────────────────────────────────────

    def _reset_chat_session(self) -> None:
        self._chat_session = make_chat_session(self._guardrails)
        self._render_header()

    def _render_header(self) -> None:
        mode  = f"[{C_LABEL3}]mock[/{C_LABEL3}]" if MOCK_MODE else f"[{C_LABEL3}]on-device[/{C_LABEL3}]"
        g_col = C_ORANGE if self._guardrails else C_LABEL3
        g_lbl = "permissive" if self._guardrails else "default"
        self.query_one("#header", Static).update(
            f"[{C_PURPLE}]◆[/{C_PURPLE}]  {_TITLE_COLORED}"
            f"  [{C_SEP}]│[/{C_SEP}]  {mode}"
            f"  [{C_SEP}]│[/{C_SEP}]  [{g_col}]guardrails: {g_lbl}[/{g_col}]"
        )

    # ── Availability ────────────────────────────────────────────────────────────

    def _check_and_warn_availability(self) -> None:
        available, error_msg = check_availability()
        if available:
            return
        history = self.query_one("#history", RichLog)
        history.write(f"[bold {C_RED}]  Apple Intelligence Unavailable[/bold {C_RED}]")
        history.write(f"[{C_ORANGE}]  {error_msg}[/{C_ORANGE}]")
        self.query_one(ChatInput).disabled = True
        self.query_one("#input-hint").display = False

    # ── Actions ────────────────────────────────────────────────────────────────

    def action_toggle_guardrails(self) -> None:
        if self._processing:
            return
        self._guardrails = 1 - self._guardrails
        self._reset_chat_session()
        label = "permissive" if self._guardrails else "default"
        self._write_divider(f"guardrails → {label}  ·  session reset")

    def action_new_session(self) -> None:
        if self._processing:
            return
        self._reset_chat_session()
        self._write_divider("new session")

    def action_clear_history(self) -> None:
        self.query_one("#history", RichLog).clear()
        live = self.query_one("#live", Static)
        live.update("")
        live.add_class("idle")

    def _write_divider(self, label: str) -> None:
        self.query_one("#history", RichLog).write(
            f"\n[{C_LABEL3}]  ── {label} ──[/{C_LABEL3}]\n"
        )

    # ── Command picker ──────────────────────────────────────────────────────────

    def _show_picker(self, query: str) -> None:
        filtered = [c for c in COMMANDS if c.name.startswith(query)]
        self._picker_items = filtered
        self._picker_index = min(self._picker_index, max(0, len(filtered) - 1))

        picker = self.query_one("#command-picker", Static)
        keys   = self.query_one("#picker-keys")
        inp    = self.query_one(ChatInput)

        if not filtered:
            self._hide_picker()
            return

        lines = []
        for i, cmd in enumerate(filtered):
            tag = f" [{C_INDIGO}][tagging][/{C_INDIGO}]" if cmd.use_case == 1 else ""
            if i == self._picker_index:
                lines.append(
                    f"[bold {C_PURPLE}]▶ {cmd.name:<14}[/bold {C_PURPLE}]"
                    f"[{C_LABEL1}]{cmd.description}[/{C_LABEL1}]{tag}"
                )
            else:
                lines.append(
                    f"  [{C_LABEL3}]{cmd.name:<14}[/{C_LABEL3}]"
                    f"[{C_LABEL3}]{cmd.description}[/{C_LABEL3}]{tag}"
                )

        picker.update("\n".join(lines))
        picker.add_class("visible")
        keys.add_class("visible")
        inp.intercept_enter = True
        self._picker_visible = True

    def _hide_picker(self) -> None:
        self.query_one("#command-picker", Static).remove_class("visible")
        self.query_one("#picker-keys").remove_class("visible")
        inp = self.query_one(ChatInput)
        inp.intercept_enter = False
        self._picker_visible = False
        self._picker_items = []
        self._picker_index = 0

    def _select_command(self) -> None:
        if not self._picker_items:
            return
        cmd = self._picker_items[self._picker_index]
        self._active_command = cmd
        self._hide_picker()
        inp = self.query_one(ChatInput)
        inp.load_text(cmd.template)
        inp.move_cursor(inp.document.end)

    # ── Key handling ────────────────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        if self._picker_visible:
            first = self.query_one(ChatInput).text.split("\n")[0]
            if event.key == "down":
                self._picker_index = (self._picker_index + 1) % max(1, len(self._picker_items))
                self._show_picker(first)
                event.stop()
            elif event.key == "up":
                self._picker_index = (self._picker_index - 1) % max(1, len(self._picker_items))
                self._show_picker(first)
                event.stop()
            elif event.key == "escape":
                self._hide_picker()
                self.query_one(ChatInput).load_text("")
                event.stop()
            return

        inp = self.query_one(ChatInput)
        if not inp.has_focus and not self._processing and event.is_printable:
            inp.focus()

    def on_chat_input_picker_select(self, _: ChatInput.PickerSelect) -> None:
        self._select_command()

    # ── TextArea change → picker trigger ───────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self._processing:
            return
        text  = event.text_area.text
        first = text.split("\n")[0]
        self.query_one("#input-hint").display = not bool(text.strip())
        if first.startswith("/") and "\n" not in text:
            self._active_command = None
            self._show_picker(first)
        elif self._picker_visible:
            self._hide_picker()

    # ── Submit ──────────────────────────────────────────────────────────────────

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        if self._processing:
            return
        prompt = event.text.strip()
        if not prompt:
            return
        cmd = self._active_command
        self._active_command = None
        self._hide_picker()
        self.query_one(ChatInput).load_text("")
        self._submit(prompt, command=cmd)

    def _submit(self, prompt: str, command: Optional[Command] = None) -> None:
        self._processing = True
        inp = self.query_one(ChatInput)
        inp.disabled = True
        inp.add_class("-processing")

        history = self.query_one("#history", RichLog)
        lines   = prompt.split("\n")
        preview = (
            lines[0] if len(lines) == 1
            else f"{lines[0]} [{C_LABEL3}](+{len(lines)-1} lines)[/{C_LABEL3}]"
        )
        sender = command.name if command else "You"
        # Claude Code-style message block: sender label then indented text
        history.write(f"\n[bold {C_BLUE}]  ▸  {sender}[/bold {C_BLUE}]")
        history.write(f"[{C_LABEL2}]  {escape(preview)}[/{C_LABEL2}]")

        self._spinner_frame = 0
        if self._spinner_timer is not None:
            self._spinner_timer.stop()
        self._spinner_timer = self.set_interval(0.08, self._tick_spinner)
        self.run_worker(self._stream(prompt, command=command), exclusive=True)

    # ── Spinner ─────────────────────────────────────────────────────────────────

    def _tick_spinner(self) -> None:
        frame = SPINNER[self._spinner_frame % len(SPINNER)]
        self._spinner_frame += 1
        live = self.query_one("#live", Static)
        live.remove_class("idle")
        live.update(
            f"[{C_PURPLE}]{frame}[/{C_PURPLE}]"
            f"  [{C_LABEL2}]thinking…[/{C_LABEL2}]"
        )

    # ── Stream ──────────────────────────────────────────────────────────────────

    async def _stream(self, prompt: str, command: Optional[Command] = None) -> None:
        worker  = get_current_worker()
        live    = self.query_one("#live", Static)
        history = self.query_one("#history", RichLog)
        last    = ""
        session = make_command_session(command) if command else self._chat_session

        def stop_spinner() -> None:
            if self._spinner_timer is not None:
                self._spinner_timer.stop()

        def set_idle() -> None:
            live.add_class("idle")
            live.update("")

        try:
            first_token = True
            async for snapshot in session.stream_response(prompt):
                if worker.is_cancelled:
                    break
                if first_token:
                    stop_spinner()
                    live.remove_class("idle")
                    first_token = False
                last = snapshot
                preview = snapshot.split("\n")[0][:120]
                live.update(
                    f"[{C_PURPLE}]◉[/{C_PURPLE}]"
                    f"  [{C_LABEL2}]{escape(preview)}[/{C_LABEL2}]"
                    f"[{C_PURPLE}]▌[/{C_PURPLE}]"
                )

            if last:
                # Claude Code-style response block
                history.write(f"\n[bold {C_PURPLE}]  ◆  Apple Intelligence[/bold {C_PURPLE}]")
                history.write(f"[{C_LABEL1}]  {escape(last)}[/{C_LABEL1}]\n")
            set_idle()

        except Exception as e:
            stop_spinner()
            set_idle()
            name = type(e).__name__
            hint = "  · Ctrl+N to reset" if "Context" in name else ""
            history.write(f"\n[bold {C_RED}]  ✕  Error[/bold {C_RED}]")
            history.write(f"[{C_RED}]  {name}: {escape(str(e))}{hint}[/{C_RED}]\n")

        finally:
            self._processing = False
            try:
                inp = self.query_one(ChatInput)
                inp.disabled = False
                inp.remove_class("-processing")
                inp.focus()
            except Exception:
                pass


if __name__ == "__main__":
    AppleIntelligenceTUI().run()
