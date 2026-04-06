"""
Tests for new v0.2.0 modules:
  - apple_tui/plugins.py   — TOML plugin loader
  - apple_tui/sessions.py  — persistent session storage
  - apple_tui/tools.py     — ReadFileTool, ClipboardReadTool
  - apple_tui/__main__.py  — pipe mode, CLI entry point

Run:
  pytest test_new_modules.py -v
"""

import asyncio
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Force MOCK_MODE so tests never hit the real SDK ───────────────────────────
_real_uname = os.uname


def _fake_uname():
    u = _real_uname()
    return types.SimpleNamespace(
        sysname="Linux",
        nodename=u.nodename, release=u.release,
        version=u.version, machine=u.machine,
    )


os.uname = _fake_uname
import apple_tui.tools as T   # noqa: E402
import apple_tui.app as APP   # noqa: E402
os.uname = _real_uname

assert T.MOCK_MODE, "Tests must run in MOCK_MODE"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Plugin loader
# ═══════════════════════════════════════════════════════════════════════════════

from apple_tui.plugins import load_plugins  # noqa: E402


class TestPlugins:

    def _write_toml(self, tmp_path: Path, filename: str, content: str) -> Path:
        f = tmp_path / filename
        f.write_text(content, encoding="utf-8")
        return f

    def test_empty_directory_returns_empty_list(self, tmp_path):
        """No TOML files → empty list."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path
        try:
            result = load_plugins(APP.Command)
            assert result == []
        finally:
            pm.COMMANDS_DIR = original

    def test_nonexistent_directory_returns_empty_list(self, tmp_path):
        """Missing commands dir → empty list."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path / "does_not_exist"
        try:
            result = load_plugins(APP.Command)
            assert result == []
        finally:
            pm.COMMANDS_DIR = original

    def test_valid_toml_loads_command(self, tmp_path):
        """Valid TOML produces a Command with correct fields."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path

        self._write_toml(tmp_path, "legal.toml", """\
name        = "/legal"
description = "Simplify legal text"
template    = "Rewrite in plain English:\\n\\n"
""")
        try:
            result = load_plugins(APP.Command)
            assert len(result) == 1
            cmd = result[0]
            assert cmd.name == "/legal"
            assert cmd.description == "Simplify legal text"
            assert cmd.template == "Rewrite in plain English:\n\n"
        finally:
            pm.COMMANDS_DIR = original

    def test_template_without_trailing_newline_gets_one_appended(self, tmp_path):
        """Templates not ending with \\n get \\n appended."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path

        self._write_toml(tmp_path, "test.toml", """\
name        = "/test"
description = "Test command"
template    = "Do this"
""")
        try:
            result = load_plugins(APP.Command)
            assert result[0].template.endswith("\n")
        finally:
            pm.COMMANDS_DIR = original

    def test_invalid_name_no_slash_is_skipped(self, tmp_path):
        """Commands whose name doesn't start with / are skipped."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path

        self._write_toml(tmp_path, "bad.toml", """\
name        = "noslash"
description = "Bad command"
template    = "Do this:\\n"
""")
        try:
            result = load_plugins(APP.Command)
            assert result == []
        finally:
            pm.COMMANDS_DIR = original

    def test_missing_template_is_skipped(self, tmp_path):
        """Commands with no template are skipped."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path

        self._write_toml(tmp_path, "notemplate.toml", """\
name        = "/cmd"
description = "Missing template"
""")
        try:
            result = load_plugins(APP.Command)
            assert result == []
        finally:
            pm.COMMANDS_DIR = original

    def test_invalid_toml_syntax_is_skipped(self, tmp_path):
        """Malformed TOML files don't crash the loader."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path

        self._write_toml(tmp_path, "broken.toml", "[[[ not valid toml")
        try:
            result = load_plugins(APP.Command)
            assert result == []
        finally:
            pm.COMMANDS_DIR = original

    def test_use_case_defaults_to_general(self, tmp_path):
        """Commands without use_case default to 0 (GENERAL)."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path

        self._write_toml(tmp_path, "cmd.toml", """\
name        = "/cmd"
description = "A command"
template    = "Do this:\\n"
""")
        try:
            result = load_plugins(APP.Command)
            assert result[0].use_case == 0
        finally:
            pm.COMMANDS_DIR = original

    def test_use_case_content_tagging(self, tmp_path):
        """Commands with use_case=1 load correctly."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path

        self._write_toml(tmp_path, "tag.toml", """\
name        = "/mytag"
description = "Tag command"
template    = "Tag this:\\n"
use_case    = 1
""")
        try:
            result = load_plugins(APP.Command)
            assert result[0].use_case == 1
        finally:
            pm.COMMANDS_DIR = original

    def test_multiple_toml_files_all_loaded(self, tmp_path):
        """Multiple TOML files each produce a Command."""
        from apple_tui import plugins as pm
        original = pm.COMMANDS_DIR
        pm.COMMANDS_DIR = tmp_path

        for i in range(3):
            self._write_toml(tmp_path, f"cmd{i}.toml", f"""\
name        = "/cmd{i}"
description = "Command {i}"
template    = "Do {i}:\\n"
""")
        try:
            result = load_plugins(APP.Command)
            assert len(result) == 3
            names = {c.name for c in result}
            assert names == {"/cmd0", "/cmd1", "/cmd2"}
        finally:
            pm.COMMANDS_DIR = original


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Session storage
# ═══════════════════════════════════════════════════════════════════════════════

import apple_tui.sessions as S  # noqa: E402


class TestSessions:

    def _patch_sessions_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(S, "SESSIONS_DIR", tmp_path / "sessions")

    def test_save_transcript_writes_json(self, tmp_path, monkeypatch):
        """save_transcript writes a JSON file that can be parsed back."""
        self._patch_sessions_dir(tmp_path, monkeypatch)
        data = {"messages": [{"role": "user", "content": "hello"}]}
        path = S.save_transcript(data)
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == data

    def test_save_transcript_filename_has_date_prefix(self, tmp_path, monkeypatch):
        """Saved file is named <date>-<n>.json."""
        from datetime import date
        self._patch_sessions_dir(tmp_path, monkeypatch)
        path = S.save_transcript({"x": 1})
        today = date.today().isoformat()
        assert path.name.startswith(today)
        assert path.suffix == ".json"

    def test_save_transcript_auto_increments(self, tmp_path, monkeypatch):
        """Saving twice on the same day creates two different files."""
        self._patch_sessions_dir(tmp_path, monkeypatch)
        p1 = S.save_transcript({"n": 1})
        p2 = S.save_transcript({"n": 2})
        assert p1 != p2

    def test_load_latest_transcript_returns_none_when_empty(self, tmp_path, monkeypatch):
        """Returns None when no session files exist."""
        self._patch_sessions_dir(tmp_path, monkeypatch)
        result = S.load_latest_transcript()
        assert result is None

    def test_load_latest_transcript_returns_most_recent(self, tmp_path, monkeypatch):
        """Returns the content of the most recently modified session."""
        self._patch_sessions_dir(tmp_path, monkeypatch)
        S.save_transcript({"order": 1})
        S.save_transcript({"order": 2})
        result = S.load_latest_transcript()
        # Most recently written file should have order=2
        assert result is not None
        assert result["order"] == 2

    def test_load_latest_transcript_handles_corrupt_file(self, tmp_path, monkeypatch):
        """Returns None if the latest file is corrupt JSON."""
        self._patch_sessions_dir(tmp_path, monkeypatch)
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        bad = sessions_dir / "2000-01-01-1.json"
        bad.write_text("not valid json", encoding="utf-8")
        result = S.load_latest_transcript()
        assert result is None

    def test_list_sessions_returns_newest_first(self, tmp_path, monkeypatch):
        """list_sessions returns paths sorted by mtime descending."""
        self._patch_sessions_dir(tmp_path, monkeypatch)
        p1 = S.save_transcript({"n": 1})
        p2 = S.save_transcript({"n": 2})
        p3 = S.save_transcript({"n": 3})
        sessions = S.list_sessions()
        assert sessions[0] == p3
        assert sessions[-1] == p1

    def test_list_sessions_empty_returns_empty_list(self, tmp_path, monkeypatch):
        """list_sessions returns [] when no files exist."""
        self._patch_sessions_dir(tmp_path, monkeypatch)
        sessions = S.list_sessions()
        assert sessions == []


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Tools
# ═══════════════════════════════════════════════════════════════════════════════

class TestReadFileTool:

    @pytest.mark.asyncio
    async def test_reads_existing_file(self, tmp_path):
        """ReadFileTool returns contents of an existing file."""
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        tool = T.ReadFileTool()
        result = await tool.call(path=str(f))
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_file(self, tmp_path):
        """ReadFileTool returns an error string for a nonexistent path."""
        tool = T.ReadFileTool()
        result = await tool.call(path=str(tmp_path / "nonexistent.txt"))
        assert "Error" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_truncates_large_files(self, tmp_path):
        """ReadFileTool in MOCK_MODE reads up to 8000 chars."""
        f = tmp_path / "big.txt"
        content = "x" * 20000
        f.write_text(content, encoding="utf-8")
        tool = T.ReadFileTool()
        result = await tool.call(path=str(f))
        assert len(result) <= 8000

    @pytest.mark.asyncio
    async def test_expands_tilde_in_path(self, tmp_path, monkeypatch):
        """ReadFileTool expands ~ in paths."""
        # Create a file in tmp_path, monkeypatch home to tmp_path
        f = tmp_path / "file.txt"
        f.write_text("tilde content", encoding="utf-8")
        monkeypatch.setenv("HOME", str(tmp_path))
        tool = T.ReadFileTool()
        result = await tool.call(path="~/file.txt")
        assert result == "tilde content"

    def test_read_file_tool_has_correct_name(self):
        assert T.ReadFileTool.name == "read_file"

    def test_read_file_tool_has_description(self):
        assert len(T.ReadFileTool.description) > 0


class TestClipboardReadTool:

    @pytest.mark.asyncio
    async def test_returns_string_in_mock_mode(self):
        """ClipboardReadTool returns a string in MOCK_MODE."""
        tool = T.ClipboardReadTool()
        result = await tool.call()
        assert isinstance(result, str)

    def test_clipboard_tool_has_correct_name(self):
        assert T.ClipboardReadTool.name == "clipboard_read"

    def test_clipboard_tool_has_description(self):
        assert len(T.ClipboardReadTool.description) > 0


class TestWriteFileTool:

    @pytest.mark.asyncio
    async def test_writes_content_to_file(self, tmp_path, monkeypatch):
        """WriteFileTool writes the given content to the given path."""
        monkeypatch.setenv("HOME", str(tmp_path))
        target = tmp_path / "output.txt"
        tool = T.WriteFileTool()
        result = await tool.call(path=str(target), content="hello world")
        assert target.read_text() == "hello world"

    @pytest.mark.asyncio
    async def test_returns_success_message(self, tmp_path, monkeypatch):
        """WriteFileTool returns a confirmation string on success."""
        monkeypatch.setenv("HOME", str(tmp_path))
        target = tmp_path / "out.txt"
        tool = T.WriteFileTool()
        result = await tool.call(path=str(target), content="data")
        assert isinstance(result, str)
        assert "wrote" in result.lower() or "written" in result.lower() or str(target) in result

    @pytest.mark.asyncio
    async def test_returns_error_for_unwritable_path(self, tmp_path, monkeypatch):
        """WriteFileTool returns an error string when the path is not writable."""
        monkeypatch.setenv("HOME", str(tmp_path))
        bad = tmp_path / "no_such_dir" / "file.txt"
        tool = T.WriteFileTool()
        result = await tool.call(path=str(bad), content="data")
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_expands_tilde_in_path(self, tmp_path, monkeypatch):
        """WriteFileTool expands ~ in paths."""
        monkeypatch.setenv("HOME", str(tmp_path))
        tool = T.WriteFileTool()
        result = await tool.call(path="~/tilde_test.txt", content="tilde")
        assert (tmp_path / "tilde_test.txt").read_text() == "tilde"

    @pytest.mark.asyncio
    async def test_rejects_path_outside_home(self, tmp_path, monkeypatch):
        """WriteFileTool refuses writes outside the user's home directory."""
        monkeypatch.setenv("HOME", str(tmp_path))
        tool = T.WriteFileTool()
        result = await tool.call(path="/etc/passwd", content="hacked")
        assert "error" in result.lower() or "not allowed" in result.lower() or "denied" in result.lower()

    @pytest.mark.asyncio
    async def test_rejects_oversized_content(self, tmp_path, monkeypatch):
        """WriteFileTool rejects content larger than the allowed limit (size check, not path check)."""
        monkeypatch.setenv("HOME", str(tmp_path))
        target = tmp_path / "big.txt"
        tool = T.WriteFileTool()
        big_content = "x" * 200_001
        result = await tool.call(path=str(target), content=big_content)
        assert "too large" in result.lower()
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_rejects_symlink_escaping_home(self, tmp_path, monkeypatch):
        """WriteFileTool refuses a path that is a symlink pointing outside home."""
        monkeypatch.setenv("HOME", str(tmp_path))
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("original")
        link = tmp_path / "evil_link"
        link.symlink_to(outside)
        tool = T.WriteFileTool()
        result = await tool.call(path=str(link), content="hacked")
        assert "error" in result.lower() or "not allowed" in result.lower()
        assert outside.read_text() == "original"  # file must be untouched

    def test_write_file_tool_has_correct_name(self):
        assert T.WriteFileTool.name == "write_file"

    def test_write_file_tool_has_description(self):
        assert len(T.WriteFileTool.description) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Pipe mode / CLI entry point
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipeMode:

    @pytest.mark.asyncio
    async def test_run_pipe_outputs_text(self, capsys):
        """_run_pipe streams text to stdout."""
        from apple_tui.__main__ import _run_pipe
        await _run_pipe("say hello", guardrails=0)
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    @pytest.mark.asyncio
    async def test_run_pipe_ends_with_newline(self, capsys):
        """_run_pipe always ends output with a newline."""
        from apple_tui.__main__ import _run_pipe
        await _run_pipe("hello", guardrails=0)
        captured = capsys.readouterr()
        assert captured.out.endswith("\n")

    @pytest.mark.asyncio
    async def test_run_pipe_routes_slash_command(self, capsys):
        """/summarize prefix routes to a command session, not chat."""
        from apple_tui.__main__ import _run_pipe
        # Should not error — command is recognized and template is prepended
        await _run_pipe("/summarize some text to summarize", guardrails=0)
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    @pytest.mark.asyncio
    async def test_run_pipe_unknown_command_exits_1(self, capsys):
        """Unknown /command prints error and exits with code 1."""
        from apple_tui.__main__ import _run_pipe
        with pytest.raises(SystemExit) as exc:
            await _run_pipe("/nosuchcommand some text", guardrails=0)
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Unknown command" in captured.err

    @pytest.mark.asyncio
    async def test_run_pipe_prefix_match_resolves_command(self, capsys):
        """/sum prefix matches /summarize."""
        from apple_tui.__main__ import _run_pipe
        await _run_pipe("/sum short text here", guardrails=0)
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_main_launches_tui_with_no_args(self, monkeypatch):
        """main() launches the TUI when no args and no stdin."""
        from apple_tui import __main__ as M

        launched = []

        class _FakeTUI:
            def run(self):
                launched.append(True)

        monkeypatch.setattr(sys, "argv", ["ai"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        # AppleIntelligenceTUI is imported lazily inside main(); patch at the source
        with patch("apple_tui.app.AppleIntelligenceTUI", return_value=_FakeTUI()):
            M.main()

        assert launched == [True]

    def test_main_runs_pipe_mode_with_prompt_arg(self, monkeypatch):
        """main() calls asyncio.run(_run_pipe) when prompt args are given."""
        from apple_tui import __main__ as M

        pipe_calls = []

        async def _fake_pipe(prompt, guardrails):
            pipe_calls.append((prompt, guardrails))

        monkeypatch.setattr(sys, "argv", ["ai", "summarize", "this"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(M, "_run_pipe", _fake_pipe)

        M.main()
        assert len(pipe_calls) == 1
        assert pipe_calls[0][0] == "summarize this"

    def test_main_permissive_guardrails_flag(self, monkeypatch):
        """--guardrails permissive passes guardrails=1 to _run_pipe."""
        from apple_tui import __main__ as M

        pipe_calls = []

        async def _fake_pipe(prompt, guardrails):
            pipe_calls.append((prompt, guardrails))

        monkeypatch.setattr(sys, "argv", ["ai", "--guardrails", "permissive", "hello"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(M, "_run_pipe", _fake_pipe)

        M.main()
        assert pipe_calls[0][1] == 1  # permissive = 1

    def test_main_default_guardrails_flag(self, monkeypatch):
        """Default guardrails passes guardrails=0."""
        from apple_tui import __main__ as M

        pipe_calls = []

        async def _fake_pipe(prompt, guardrails):
            pipe_calls.append((prompt, guardrails))

        monkeypatch.setattr(sys, "argv", ["ai", "hello"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(M, "_run_pipe", _fake_pipe)

        M.main()
        assert pipe_calls[0][1] == 0

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_in_run_pipe_exits_130(self):
        """KeyboardInterrupt raised mid-stream → SystemExit(130), no traceback."""
        from apple_tui import __main__ as M
        from apple_tui.app import make_chat_session

        async def _bad_stream(prompt, options=None):
            raise KeyboardInterrupt
            yield  # make it an async generator

        session = make_chat_session(0)
        session.stream_response = _bad_stream

        # make_chat_session is imported inside _run_pipe from apple_tui.app
        with patch("apple_tui.app.make_chat_session", return_value=session):
            with pytest.raises(SystemExit) as exc:
                await M._run_pipe("test", guardrails=0)
        assert exc.value.code == 130

    def test_main_keyboard_interrupt_exits_130(self, monkeypatch):
        """KeyboardInterrupt propagating out of asyncio.run → SystemExit(130)."""
        from apple_tui import __main__ as M

        async def _raising_pipe(prompt, guardrails):
            raise KeyboardInterrupt

        monkeypatch.setattr(sys, "argv", ["ai", "hello"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(M, "_run_pipe", _raising_pipe)

        with pytest.raises(SystemExit) as exc:
            M.main()
        assert exc.value.code == 130

    def test_binary_stdin_exits_with_error(self, monkeypatch, capsys):
        """Piping a binary file (e.g. .docx) prints a helpful error and exits 1."""
        import io
        from apple_tui import __main__ as M

        # Simulate what Python produces when reading a binary file as text:
        # surrogate-escaped bytes from a ZIP/docx header (PK\x03\x04 → surrogates)
        binary_as_text = b"PK\x03\x04\xed\xa0\x80".decode("utf-8", errors="surrogateescape")

        monkeypatch.setattr(sys, "argv", ["ai", "/summarize"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        monkeypatch.setattr(sys, "stdin", io.StringIO(binary_as_text))

        with pytest.raises(SystemExit) as exc:
            M.main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "binary" in captured.err.lower() or "text" in captured.err.lower()

    def test_binary_stdin_suggests_conversion(self, monkeypatch, capsys):
        """Error message for binary stdin mentions how to convert."""
        import io
        from apple_tui import __main__ as M

        binary_as_text = b"PK\x03\x04\xed\xa0\x80".decode("utf-8", errors="surrogateescape")

        monkeypatch.setattr(sys, "argv", ["ai", "/summarize"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        monkeypatch.setattr(sys, "stdin", io.StringIO(binary_as_text))

        with pytest.raises(SystemExit) as exc:
            M.main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        # Should hint at textutil or plain text conversion
        assert "textutil" in captured.err or "txt" in captured.err.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Structured output / JSON mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestJsonMode:

    @pytest.mark.asyncio
    async def test_run_pipe_json_outputs_valid_json(self, capsys):
        """`--json` with a list command outputs valid JSON to stdout."""
        from apple_tui.__main__ import _run_pipe_json
        from apple_tui.app import COMMANDS
        cmd = next(c for c in COMMANDS if c.name == "/actions")
        await _run_pipe_json("Buy milk. Call John. Write report.", cmd, guardrails=0)
        captured = capsys.readouterr()
        import json
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_run_pipe_json_each_item_is_string(self, capsys):
        """JSON output items are strings."""
        from apple_tui.__main__ import _run_pipe_json
        from apple_tui.app import COMMANDS
        cmd = next(c for c in COMMANDS if c.name == "/bullets")
        await _run_pipe_json("Python is fast. Python is readable.", cmd, guardrails=0)
        captured = capsys.readouterr()
        import json
        data = json.loads(captured.out)
        assert all(isinstance(item, str) for item in data)

    @pytest.mark.asyncio
    async def test_run_pipe_json_ends_with_newline(self, capsys):
        """JSON output ends with a newline for clean piping."""
        from apple_tui.__main__ import _run_pipe_json
        from apple_tui.app import COMMANDS
        cmd = next(c for c in COMMANDS if c.name == "/tag")
        await _run_pipe_json("Python programming tutorial", cmd, guardrails=0)
        captured = capsys.readouterr()
        assert captured.out.endswith("\n")

    def test_json_flag_parsed_by_argparse(self, monkeypatch):
        """--json flag is recognized by _parse_args."""
        from apple_tui import __main__ as M
        monkeypatch.setattr(sys, "argv", ["ai", "--json", "/actions"])
        args = M._parse_args()
        assert args.json is True

    def test_json_flag_default_is_false(self, monkeypatch):
        """--json defaults to False."""
        from apple_tui import __main__ as M
        monkeypatch.setattr(sys, "argv", ["ai", "hello"])
        args = M._parse_args()
        assert args.json is False

    def test_main_routes_to_json_pipe_when_flag_set(self, monkeypatch):
        """main() calls _run_pipe_json when --json flag is set with a /command."""
        from apple_tui import __main__ as M

        calls = []

        async def _fake_json_pipe(content, cmd, guardrails):
            calls.append((content, cmd.name, guardrails))

        monkeypatch.setattr(sys, "argv", ["ai", "--json", "/actions"])
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("Buy milk. Call John."))
        monkeypatch.setattr(M, "_run_pipe_json", _fake_json_pipe)

        M.main()
        assert len(calls) == 1
        assert calls[0][1] == "/actions"

    @pytest.mark.asyncio
    async def test_run_pipe_json_keyboard_interrupt_exits_130(self):
        """KeyboardInterrupt in _run_pipe_json → SystemExit(130)."""
        from apple_tui import __main__ as M
        from apple_tui.app import COMMANDS

        async def _bad_stream(prompt, options=None):
            raise KeyboardInterrupt
            yield  # make it an async generator

        cmd = next(c for c in COMMANDS if c.name == "/actions")
        session = APP.make_command_session(cmd)
        session.stream_response = _bad_stream

        with patch("apple_tui.app.make_command_session", return_value=session):
            with pytest.raises(SystemExit) as exc:
                await M._run_pipe_json("some text", cmd, guardrails=0)
        assert exc.value.code == 130


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Named sessions
# ═══════════════════════════════════════════════════════════════════════════════

class TestNamedSessions:

    def _patch(self, monkeypatch, tmp_path):
        monkeypatch.setattr(S, "SESSIONS_DIR", tmp_path / "sessions")

    def test_save_named_session_creates_named_file(self, tmp_path, monkeypatch):
        """save_transcript with name= writes <name>.json."""
        self._patch(monkeypatch, tmp_path)
        path = S.save_transcript({"x": 1}, name="myproject")
        assert path.name == "myproject.json"

    def test_save_named_session_is_in_sessions_dir(self, tmp_path, monkeypatch):
        """Named session file lands in the sessions directory."""
        self._patch(monkeypatch, tmp_path)
        path = S.save_transcript({"x": 1}, name="work")
        assert path.parent == (tmp_path / "sessions")

    def test_load_named_session_returns_data(self, tmp_path, monkeypatch):
        """load_transcript(name=) returns the saved data."""
        self._patch(monkeypatch, tmp_path)
        S.save_transcript({"project": "alpha"}, name="alpha")
        result = S.load_transcript(name="alpha")
        assert result == {"project": "alpha"}

    def test_load_named_session_returns_none_when_missing(self, tmp_path, monkeypatch):
        """load_transcript for unknown name returns None."""
        self._patch(monkeypatch, tmp_path)
        result = S.load_transcript(name="nonexistent")
        assert result is None

    def test_save_named_overwrites_existing(self, tmp_path, monkeypatch):
        """Saving a named session twice updates the file in place."""
        self._patch(monkeypatch, tmp_path)
        S.save_transcript({"v": 1}, name="proj")
        S.save_transcript({"v": 2}, name="proj")
        result = S.load_transcript(name="proj")
        assert result == {"v": 2}
        # Only one file should exist for this name
        sessions_dir = tmp_path / "sessions"
        named = list(sessions_dir.glob("proj.json"))
        assert len(named) == 1

    def test_unnamed_save_unchanged(self, tmp_path, monkeypatch):
        """save_transcript without name still uses date-based filename."""
        self._patch(monkeypatch, tmp_path)
        from datetime import date
        path = S.save_transcript({"x": 1})
        assert path.name.startswith(date.today().isoformat())

    def test_session_flag_parsed_by_argparse(self, monkeypatch):
        """--session flag is recognized by _parse_args."""
        from apple_tui import __main__ as M
        monkeypatch.setattr(sys, "argv", ["ai", "--session", "myproject"])
        args = M._parse_args()
        assert args.session == "myproject"

    def test_session_flag_default_is_none(self, monkeypatch):
        """--session defaults to None."""
        from apple_tui import __main__ as M
        monkeypatch.setattr(sys, "argv", ["ai"])
        args = M._parse_args()
        assert args.session is None

    def test_list_named_sessions_returns_named_files(self, tmp_path, monkeypatch):
        """list_sessions returns named .json files."""
        self._patch(monkeypatch, tmp_path)
        S.save_transcript({"x": 1}, name="alpha")
        S.save_transcript({"x": 2}, name="beta")
        sessions = S.list_sessions()
        names = {p.stem for p in sessions}
        assert "alpha" in names
        assert "beta" in names
