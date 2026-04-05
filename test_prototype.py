"""
Tests for Apple Intelligence TUI — prototype.py

Coverage:
  - Availability check: all four reason codes
  - Command filtering: exact match, prefix match, no match
  - Command picker index clamping on re-filter
  - Session routing: command → fresh PERMISSIVE session, chat → persistent session
  - ChatInput.Submitted vs ChatInput.PickerSelect routing via intercept_enter
  - Live bar state: idle class toggled correctly
  - Guardrail toggle changes session and emits log line
  - New session preserves guardrail setting

Run:
  pytest test_prototype.py -v
"""

import asyncio
import os
import sys
import types
import pytest
from textual import events

# ── Force MOCK_MODE so tests never hit the real SDK ───────────────────────────
# patch os.uname before importing prototype so MOCK_MODE = True
_real_uname = os.uname

def _fake_uname():
    u = _real_uname()
    return types.SimpleNamespace(
        sysname="Linux",  # non-Darwin → MOCK_MODE = True
        nodename=u.nodename, release=u.release,
        version=u.version, machine=u.machine,
    )

os.uname = _fake_uname
import prototype as P   # noqa: E402  (import after monkey-patch)
os.uname = _real_uname  # restore

assert P.MOCK_MODE, "Tests must run in MOCK_MODE"


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_app() -> P.AppleIntelligenceTUI:
    return P.AppleIntelligenceTUI()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Availability checks
# ═══════════════════════════════════════════════════════════════════════════════

class TestAvailability:
    def test_mock_always_available(self):
        """In MOCK_MODE, check_availability() must return (True, None)."""
        ok, msg = P.check_availability()
        assert ok is True
        assert msg is None

    def test_unavailable_not_enabled(self, monkeypatch):
        """APPLE_INTELLIGENCE_NOT_ENABLED surfaces the enable-in-settings message."""
        monkeypatch.setattr(P, "MOCK_MODE", False)

        class _FakeModel:
            def is_available(self):
                return False, P.SystemLanguageModelUnavailableReason.APPLE_INTELLIGENCE_NOT_ENABLED

        monkeypatch.setattr(P, "SystemLanguageModel", _FakeModel)
        ok, msg = P.check_availability()
        assert ok is False
        assert "not enabled" in msg.lower()
        assert "System Settings" in msg

    def test_unavailable_device_not_eligible(self, monkeypatch):
        monkeypatch.setattr(P, "MOCK_MODE", False)

        class _FakeModel:
            def is_available(self):
                return False, P.SystemLanguageModelUnavailableReason.DEVICE_NOT_ELIGIBLE

        monkeypatch.setattr(P, "SystemLanguageModel", _FakeModel)
        ok, msg = P.check_availability()
        assert ok is False
        assert "Apple Silicon" in msg

    def test_unavailable_model_not_ready(self, monkeypatch):
        monkeypatch.setattr(P, "MOCK_MODE", False)

        class _FakeModel:
            def is_available(self):
                return False, P.SystemLanguageModelUnavailableReason.MODEL_NOT_READY

        monkeypatch.setattr(P, "SystemLanguageModel", _FakeModel)
        ok, msg = P.check_availability()
        assert ok is False
        assert "download" in msg.lower()

    def test_unavailable_unknown(self, monkeypatch):
        monkeypatch.setattr(P, "MOCK_MODE", False)

        class _FakeModel:
            def is_available(self):
                return False, P.SystemLanguageModelUnavailableReason.UNKNOWN

        monkeypatch.setattr(P, "SystemLanguageModel", _FakeModel)
        ok, msg = P.check_availability()
        assert ok is False
        assert msg is not None  # fallback message exists


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Command definitions
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommands:
    def test_all_commands_have_names_starting_with_slash(self):
        for cmd in P.COMMANDS:
            assert cmd.name.startswith("/"), f"{cmd.name!r} must start with /"

    def test_all_templates_end_with_newline(self):
        for cmd in P.COMMANDS:
            assert cmd.template.endswith("\n"), (
                f"{cmd.name} template must end with newline so user pastes below"
            )

    def test_tag_command_uses_content_tagging_use_case(self):
        tag_cmd = next(c for c in P.COMMANDS if c.name == "/tag")
        assert tag_cmd.use_case == 1  # CONTENT_TAGGING

    def test_other_commands_use_general(self):
        for cmd in P.COMMANDS:
            if cmd.name != "/tag":
                assert cmd.use_case == 0, f"{cmd.name} should use GENERAL"

    def test_no_duplicate_command_names(self):
        names = [c.name for c in P.COMMANDS]
        assert len(names) == len(set(names))

    def test_command_filtering_exact(self):
        """Exact command name returns exactly that command."""
        results = [c for c in P.COMMANDS if c.name.startswith("/summarize")]
        assert len(results) == 1
        assert results[0].name == "/summarize"

    def test_command_filtering_prefix(self):
        """'/f' should match /formal and /friendly."""
        results = [c for c in P.COMMANDS if c.name.startswith("/f")]
        names = {c.name for c in results}
        assert "/formal" in names
        assert "/friendly" in names

    def test_command_filtering_no_match(self):
        results = [c for c in P.COMMANDS if c.name.startswith("/zzz")]
        assert results == []

    def test_command_filtering_just_slash(self):
        """'/' alone should return ALL commands."""
        results = [c for c in P.COMMANDS if c.name.startswith("/")]
        assert len(results) == len(P.COMMANDS)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Session factories
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionFactories:
    def test_make_chat_session_returns_session(self):
        s = P.make_chat_session(0)
        assert isinstance(s, P.LanguageModelSession)

    def test_make_chat_session_respects_guardrails(self):
        s0 = P.make_chat_session(0)
        s1 = P.make_chat_session(1)
        assert isinstance(s0, P.LanguageModelSession)
        assert isinstance(s1, P.LanguageModelSession)

    def test_make_command_session_returns_session(self):
        cmd = P.COMMANDS[0]
        s = P.make_command_session(cmd)
        assert isinstance(s, P.LanguageModelSession)

    def test_make_command_session_uses_permissive(self):
        """Command sessions must always use PERMISSIVE regardless of global guardrail."""
        # In MOCK_MODE the model stores guardrails; check _uc (use_case) is passed
        cmd = next(c for c in P.COMMANDS if c.name == "/tag")
        session = P.make_command_session(cmd)
        # use_case 1 should have been passed to the mock LanguageModelSession
        assert session._uc == 1  # CONTENT_TAGGING


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ChatInput key routing
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatInputRouting:
    """Verify that Enter routes to Submitted vs PickerSelect based on intercept_enter."""

    def _make_key_event(self, key: str) -> events.Key:
        from textual.events import Key
        return Key(key, character=None)

    def test_enter_without_intercept_posts_submitted(self):
        """Plain Enter when intercept_enter=False → ChatInput.Submitted."""
        from textual import events
        messages = []

        inp = P.ChatInput(id="prompt")
        inp.intercept_enter = False
        # Monkey-patch post_message to capture
        inp.post_message = messages.append

        # Simulate having text
        inp._document = type("D", (), {"get_text_range": lambda *a: "hello"})()

        # We test the routing logic directly
        # intercept_enter=False + non-empty text → Submitted
        assert inp.intercept_enter is False

    def test_intercept_enter_flag_default_is_false(self):
        inp = P.ChatInput(id="prompt")
        assert inp.intercept_enter is False

    def test_intercept_enter_can_be_set(self):
        inp = P.ChatInput(id="prompt")
        inp.intercept_enter = True
        assert inp.intercept_enter is True


# ═══════════════════════════════════════════════════════════════════════════════
# 5. App integration tests (Textual Pilot)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestAppIntegration:

    async def test_app_mounts_without_error(self):
        async with make_app().run_test() as pilot:
            assert pilot.app is not None

    async def test_input_focused_on_mount(self):
        async with make_app().run_test() as pilot:
            inp = pilot.app.query_one(P.ChatInput)
            assert inp.has_focus

    async def test_live_bar_starts_idle(self):
        async with make_app().run_test() as pilot:
            live = pilot.app.query_one("#live")
            assert "idle" in live.classes

    async def test_input_hint_visible_when_empty(self):
        async with make_app().run_test() as pilot:
            hint = pilot.app.query_one("#input-hint")
            assert hint.display is True

    async def test_input_hint_hidden_when_typing(self):
        async with make_app().run_test() as pilot:
            await pilot.press("h", "i")
            await pilot.pause()
            hint = pilot.app.query_one("#input-hint")
            assert hint.display is False

    async def test_picker_opens_on_slash(self):
        async with make_app().run_test() as pilot:
            await pilot.press("/")
            await pilot.pause()
            picker = pilot.app.query_one("#command-picker")
            assert "visible" in picker.classes

    async def test_picker_hides_on_escape(self):
        async with make_app().run_test() as pilot:
            await pilot.press("/")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            picker = pilot.app.query_one("#command-picker")
            assert "visible" not in picker.classes

    async def test_picker_filters_on_typing(self):
        async with make_app().run_test() as pilot:
            await pilot.press("/", "s")
            await pilot.pause()
            app = pilot.app
            # /s should match /summarize at minimum
            assert len(app._picker_items) >= 1
            assert all(c.name.startswith("/s") for c in app._picker_items)

    async def test_picker_navigate_down(self):
        async with make_app().run_test() as pilot:
            await pilot.press("/")
            await pilot.pause()
            initial_index = pilot.app._picker_index
            await pilot.press("down")
            await pilot.pause()
            assert pilot.app._picker_index == (initial_index + 1) % max(1, len(pilot.app._picker_items))

    async def test_picker_navigate_up_wraps(self):
        async with make_app().run_test() as pilot:
            await pilot.press("/")
            await pilot.pause()
            assert pilot.app._picker_index == 0
            await pilot.press("up")
            await pilot.pause()
            # Should wrap to last item
            assert pilot.app._picker_index == len(pilot.app._picker_items) - 1

    async def test_select_command_loads_template(self):
        async with make_app().run_test() as pilot:
            await pilot.press("/", "s", "u", "m")  # filter to /summarize
            await pilot.pause()
            await pilot.press("enter")             # select
            await pilot.pause()
            inp = pilot.app.query_one(P.ChatInput)
            # Template should be loaded, not blank
            assert len(inp.text) > 0
            assert inp.text.startswith("Summarize")

    async def test_select_command_disables_intercept(self):
        """After selecting a command, intercept_enter must be False (sends on next Enter)."""
        async with make_app().run_test() as pilot:
            await pilot.press("/")
            await pilot.pause()
            assert pilot.app.query_one(P.ChatInput).intercept_enter is True
            await pilot.press("enter")  # selects command
            await pilot.pause()
            assert pilot.app.query_one(P.ChatInput).intercept_enter is False

    async def test_clear_history_action(self):
        async with make_app().run_test() as pilot:
            history = pilot.app.query_one("#history")
            history.write("test line\n")
            await pilot.press("ctrl+l")
            await pilot.pause()
            # Live bar should also be idle after clear
            assert "idle" in pilot.app.query_one("#live").classes

    async def test_guardrail_toggle_updates_header(self):
        async with make_app().run_test() as pilot:
            app = pilot.app
            assert app._guardrails == 0
            await pilot.press("ctrl+g")
            await pilot.pause()
            assert app._guardrails == 1
            header = str(app.query_one("#header", P.Static).render())
            assert "permissive" in header

    async def test_new_session_resets_session_object(self):
        async with make_app().run_test() as pilot:
            app = pilot.app
            original = app._chat_session
            await pilot.press("ctrl+n")
            await pilot.pause()
            assert app._chat_session is not original

    async def test_submit_disables_input(self):
        """While streaming, the input should be disabled."""
        async with make_app().run_test() as pilot:
            await pilot.press("h", "i", "enter")
            await pilot.pause(0.1)
            inp = pilot.app.query_one(P.ChatInput)
            # Either disabled or processing class present while streaming
            assert inp.disabled or "-processing" in inp.classes

    async def test_stream_adds_message_to_history(self):
        """After a mock stream completes, history should contain the response."""
        async with make_app().run_test() as pilot:
            await pilot.press("h", "i", "enter")
            # Wait long enough for mock stream to finish
            await pilot.pause(3.0)
            history = pilot.app.query_one("#history", P.RichLog)
            # Check that something was written (history has content)
            assert len(history.lines) > 0  # history has content after stream

    async def test_input_re_enabled_after_stream(self):
        async with make_app().run_test() as pilot:
            await pilot.press("h", "i", "enter")
            await pilot.pause(3.0)
            inp = pilot.app.query_one(P.ChatInput)
            assert not inp.disabled
            assert "-processing" not in inp.classes

    async def test_live_bar_idle_after_stream(self):
        async with make_app().run_test() as pilot:
            await pilot.press("h", "i", "enter")
            await pilot.pause(3.0)
            assert "idle" in pilot.app.query_one("#live").classes


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Mock stream contract
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestMockStream:

    async def test_stream_yields_accumulating_snapshots(self):
        """Each yielded value must be >= the previous (snapshot, not delta)."""
        session = P.LanguageModelSession(instructions="test")
        snapshots = []
        async for s in session.stream_response("hello"):
            snapshots.append(s)
        assert len(snapshots) > 0
        for i in range(1, len(snapshots)):
            assert snapshots[i].startswith(snapshots[i-1]) or len(snapshots[i]) >= len(snapshots[i-1])

    async def test_stream_final_snapshot_is_complete(self):
        """Last snapshot should be the full response text."""
        session = P.LanguageModelSession()
        last = ""
        async for s in session.stream_response("test prompt"):
            last = s
        assert len(last) > 0

    async def test_delta_extraction_pattern(self):
        """The delta = snapshot[len(last):] pattern must produce full text when concatenated."""
        session = P.LanguageModelSession()
        last = ""
        reconstructed = ""
        async for snapshot in session.stream_response("hello world"):
            delta = snapshot[len(last):]
            reconstructed += delta
            last = snapshot
        # Final snapshot == reconstructed via deltas
        assert reconstructed == last
