"""
Apple Intelligence TUI

A terminal interface to Apple's on-device Foundation Models.
Uses apple-fm-sdk (pip install apple-fm-sdk) on macOS 26+ with Apple Intelligence enabled.

Controls:
  Enter          Send message
  Shift+Enter    New line in input
  /              Open command picker
  ↑↓             Navigate picker
  Tab/Enter      Select command
  Esc            Dismiss picker
  Ctrl+G         Toggle guardrails (chat session only)
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

# ── Apple Intelligence color palette (iOS/macOS dark mode system colors) ──────
C_BG        = "#000000"   # system background
C_BG2       = "#1C1C1E"   # secondary background
C_BG3       = "#2C2C2E"   # tertiary background
C_SEP       = "#38383A"   # separator
C_LABEL3    = "#48484A"   # tertiary label
C_LABEL2    = "#8E8E93"   # secondary label
C_LABEL1    = "#FFFFFF"   # primary label
C_PURPLE    = "#BF5AF2"   # Apple Intelligence (system purple)
C_BLUE      = "#0A84FF"   # system blue (user)
C_RED       = "#FF453A"   # system red
C_ORANGE    = "#FF9F0A"   # system orange
C_INDIGO    = "#5E5CE6"   # system indigo

SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

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
    LanguageModelSession                  = apple_fm_sdk.LanguageModelSession
    SystemLanguageModel                   = apple_fm_sdk.SystemLanguageModel
    SystemLanguageModelGuardrails         = apple_fm_sdk.SystemLanguageModelGuardrails
    SystemLanguageModelUseCase            = apple_fm_sdk.SystemLanguageModelUseCase
    SystemLanguageModelUnavailableReason  = apple_fm_sdk.SystemLanguageModelUnavailableReason

# ── Commands (grounded in official Apple Writing Tools + SDK docs) ─────────────

@dataclass
class Command:
    name: str
    description: str
    template: str       # pre-fills textarea; user appends text after the colon
    use_case: int = 0   # 0 = GENERAL, 1 = CONTENT_TAGGING

COMMANDS: list[Command] = [
    # Writing Tools — official Apple Intelligence UI operations
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
    # Apple Intelligence system features
    Command("/reply",     "Draft 3 reply options  [Smart Reply]",
            "Write 3 short reply options for the following message. Vary tone: neutral, warm, brief. Address any questions asked.\n\nMessage:\n"),
    Command("/notify",    "Summarise notifications",
            "Summarise the following notifications into one concise sentence:\n\n"),
    # Content Tagging adapter
    Command("/tag",       "Generate topic tags  [Content Tagging]",
            "Generate 3-7 short lowercase topic tags for the following content:\n\n",
            use_case=1),
    # Extraction
    Command("/actions",   "Extract action items and tasks",
            "Extract all action items and next steps. Format as actionable tasks starting with a verb:\n\n"),
    Command("/entities",  "Extract people, orgs, locations",
            "Extract named entities grouped into: People, Organizations, Locations:\n\n"),
]

CHAT_SYSTEM = (
    "You are a helpful, knowledgeable assistant. "
    "Answer questions directly and concisely."
)

# Commands are text-transformation tasks — always use PERMISSIVE guardrails
COMMAND_SYSTEM = (
    "You are a text processing assistant. Perform the requested task on the provided text. "
    "Output only the result with no preamble or meta-commentary."
)

# ── Availability check ─────────────────────────────────────────────────────────

_UNAVAILABLE_MESSAGES = {
    0: (  # APPLE_INTELLIGENCE_NOT_ENABLED
        "Apple Intelligence is not enabled on this device.",
        "→ System Settings → Apple Intelligence & Siri → Enable Apple Intelligence",
    ),
    1: (  # DEVICE_NOT_ELIGIBLE
        "This device does not support Apple Intelligence.",
        "→ Requires Apple Silicon Mac with macOS 26+",
    ),
    2: (  # MODEL_NOT_READY
        "The on-device model is still downloading.",
        "→ System Settings → Apple Intelligence & Siri → check download progress",
    ),
}

def check_availability() -> tuple[bool, Optional[str]]:
    """Returns (available, error_message). Always True in MOCK_MODE."""
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
    """Persistent session for free-form chat — maintains history across turns."""
    model = SystemLanguageModel(
        use_case=SystemLanguageModelUseCase.GENERAL,
        guardrails=SystemLanguageModelGuardrails(guardrails),
    )
    return LanguageModelSession(instructions=CHAT_SYSTEM, model=model)


def make_command_session(cmd: Command) -> LanguageModelSession:
    """Fresh stateless session per command — always PERMISSIVE (text transformation)."""
    model = SystemLanguageModel(
        use_case=SystemLanguageModelUseCase(cmd.use_case),
        guardrails=SystemLanguageModelGuardrails.PERMISSIVE_CONTENT_TRANSFORMATIONS,
    )
    return LanguageModelSession(instructions=COMMAND_SYSTEM, model=model)

# ── ChatInput ──────────────────────────────────────────────────────────────────

class ChatInput(TextArea):
    """
    Multiline input:
      Enter          → send (or select picker command when intercept_enter=True)
      Tab            → select picker command (when intercept_enter=True)
      Shift+Enter    → insert newline (TextArea default)
    """

    intercept_enter: bool = False

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class PickerSelect(Message):
        """Fired when Enter/Tab is pressed while the command picker is open."""

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

    # ── 3-column horizontal rhythm: all content at offset 3 from edge ──
    CSS = f"""
    Screen {{ layout: vertical; background: {C_BG}; }}

    #header {{
        height: 3;
        background: {C_BG};
        border-bottom: solid {C_SEP};
        padding: 0 3;
        content-align: left middle;
    }}

    #history {{
        height: 1fr;
        background: {C_BG};
        padding: 1 3;
        scrollbar-color: {C_SEP};
        scrollbar-background: {C_BG};
    }}

    /* Status bar: collapsed when idle, visible while thinking/streaming */
    #live {{
        height: 3;
        background: {C_BG2};
        border-top: solid {C_SEP};
        border-bottom: solid {C_SEP};
        padding: 0 3;
        content-align: left middle;
    }}
    #live.idle {{
        height: 0;
        border-top: none;
        border-bottom: none;
        padding: 0;
    }}

    /* Command picker — appears above input, aligned with history */
    #command-picker {{
        display: none;
        background: {C_BG2};
        border: solid {C_SEP};
        margin: 0 3;
        padding: 1;
        height: auto;
        max-height: 20;
    }}
    #command-picker.visible {{ display: block; }}

    #picker-keys {{
        display: none;
        height: 1;
        padding: 0 4;
        color: {C_LABEL3};
    }}
    #picker-keys.visible {{ display: block; }}

    /* Separator between history and input zone */
    #input-sep {{
        height: 1;
        border-bottom: solid {C_SEP};
        background: {C_BG};
    }}

    /* Placeholder hint — 2 rows tall: top row is breathing space, text on row 2 */
    #input-hint {{
        height: 2;
        padding: 1 4 0 4;
        color: {C_LABEL3};
    }}

    ChatInput {{
        background: {C_BG2};
        border: solid {C_SEP};
        color: {C_LABEL1};
        height: auto;
        min-height: 3;
        max-height: 8;
        margin: 1 3 2 3;
        padding: 0 1;
    }}
    ChatInput:focus {{ border: solid {C_PURPLE}; }}
    ChatInput.-processing {{ opacity: 0.4; }}

    Footer {{ background: {C_BG2}; color: {C_LABEL3}; }}
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
        yield Static("", id="input-sep")
        yield Label("/ for commands  ·  Shift+Enter for new line", id="input-hint")
        yield ChatInput(id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self._reset_chat_session()
        self.query_one("#live", Static).add_class("idle")
        self._check_and_warn_availability()
        self.query_one(ChatInput).focus()

    # ── Header ─────────────────────────────────────────────────────────────────

    def _reset_chat_session(self) -> None:
        self._chat_session = make_chat_session(self._guardrails)
        self._render_header()

    def _render_header(self) -> None:
        badge = f"[{C_LABEL3}]MOCK[/{C_LABEL3}]" if MOCK_MODE else f"[{C_LABEL3}]on-device[/{C_LABEL3}]"
        g_color = C_ORANGE if self._guardrails else C_LABEL3
        g_label = "permissive" if self._guardrails else "default"
        # Gradient: indigo → purple → pink → orange (matches Apple Intelligence branding)
        gradient = [C_INDIGO, "#7D56F4", "#9F50EC", C_PURPLE, "#D4569E",
                    "#E85E6C", "#F0703A", C_ORANGE, "#F0703A", "#E85E6C",
                    "#D4569E", C_PURPLE, "#9F50EC", "#7D56F4", C_INDIGO, "#7D56F4", C_PURPLE]
        title = "Apple Intelligence"
        colored = "".join(
            f"[bold {gradient[i % len(gradient)]}]{ch}[/bold {gradient[i % len(gradient)]}]"
            for i, ch in enumerate(title)
        )
        self.query_one("#header", Static).update(
            f" [{C_PURPLE}]◆[/{C_PURPLE}]  {colored}"
            f"   {badge}   [{g_color}]guardrails: {g_label}[/{g_color}]"
        )

    # ── Availability check ──────────────────────────────────────────────────────

    def _check_and_warn_availability(self) -> None:
        available, error_msg = check_availability()
        if available:
            return
        history = self.query_one("#history", RichLog)
        history.write(f"[bold {C_RED}]Apple Intelligence Unavailable[/bold {C_RED}]")
        history.write(f"[{C_ORANGE}]{error_msg}[/{C_ORANGE}]\n")
        self.query_one(ChatInput).disabled = True
        self.query_one("#input-hint").display = False

    # ── Actions ────────────────────────────────────────────────────────────────

    def action_toggle_guardrails(self) -> None:
        if self._processing:
            return
        self._guardrails = 1 - self._guardrails
        self._reset_chat_session()
        label = "permissive" if self._guardrails else "default"
        self.query_one("#history", RichLog).write(
            f"[{C_SEP}]─── guardrails → {label} · session reset ───[/{C_SEP}]\n"
        )

    def action_new_session(self) -> None:
        if self._processing:
            return
        self._reset_chat_session()
        self.query_one("#history", RichLog).write(
            f"[{C_SEP}]─── new session ───[/{C_SEP}]\n"
        )

    def action_clear_history(self) -> None:
        self.query_one("#history", RichLog).clear()
        live = self.query_one("#live", Static)
        live.update("")
        live.add_class("idle")

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
                    f"[bold {C_PURPLE}]▶ {cmd.name:<13}[/bold {C_PURPLE}]"
                    f"  [{C_LABEL1}]{cmd.description}[/{C_LABEL1}]{tag}"
                )
            else:
                lines.append(
                    f"  [{C_LABEL3}]{cmd.name:<13}[/{C_LABEL3}]"
                    f"  [{C_LABEL3}]{cmd.description}[/{C_LABEL3}]{tag}"
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

    # ── TextArea → picker trigger ───────────────────────────────────────────────

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
        label = f"[bold {C_BLUE}]{command.name}[/bold {C_BLUE}]" if command else f"[bold {C_BLUE}]You[/bold {C_BLUE}]"
        history.write(label)
        history.write(f"[{C_LABEL1}]{escape(preview)}[/{C_LABEL1}]\n")

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
            f"[bold {C_PURPLE}]{frame}[/bold {C_PURPLE}]"
            f"  [{C_LABEL2}]Apple Intelligence is thinking…[/{C_LABEL2}]"
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
                    f"[bold {C_PURPLE}]◉[/bold {C_PURPLE}]"
                    f"  [{C_LABEL2}]{escape(preview)}[/{C_LABEL2}]"
                    f"[{C_PURPLE}]▌[/{C_PURPLE}]"
                )

            if last:
                history.write(f"[bold {C_PURPLE}]Apple Intelligence[/bold {C_PURPLE}]")
                history.write(f"[{C_LABEL1}]{escape(last)}[/{C_LABEL1}]\n")
            set_idle()

        except Exception as e:
            stop_spinner()
            set_idle()
            name = type(e).__name__
            hint = "  · Ctrl+N to reset" if "Context" in name else ""
            history.write(f"[bold {C_RED}]Error[/bold {C_RED}]")
            history.write(f"[{C_RED}]{name}: {escape(str(e))}{hint}[/{C_RED}]\n")

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
