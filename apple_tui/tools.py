"""
SDK Tool subclasses for agentic file and clipboard access.

Only safe, read-only tools are implemented in v1.
write_file and run_shell are explicitly deferred (security boundary).
"""

import os
import subprocess

MOCK_MODE = os.uname().sysname != "Darwin"

if MOCK_MODE:
    class _MockTool:
        name: str = ""
        description: str = ""

        async def call(self, args=None) -> str:
            return f"[mock tool: {self.name}]"

    class ReadFileTool(_MockTool):
        name = "read_file"
        description = "Read the contents of a file at the given path."

        async def call(self, path: str = "") -> str:
            if not path:
                return "Error reading file: no path provided"
            try:
                with open(os.path.expanduser(path), encoding="utf-8") as f:
                    return f.read(8000)
            except Exception as e:
                return f"Error reading {path}: {e}"

    class ClipboardReadTool(_MockTool):
        name = "clipboard_read"
        description = "Read the current contents of the macOS clipboard."

        async def call(self, args=None) -> str:
            return "[mock clipboard content]"

else:
    import apple_fm_sdk as fm
    from apple_fm_sdk import Tool

    @fm.generable("Parameters for reading a file")
    class _ReadFileParams:
        path: str = fm.guide("The absolute or home-relative (~) file path to read")

    @fm.generable("Parameters for reading the clipboard (no arguments needed)")
    class _ClipboardParams:
        unused: str = fm.guide("Pass an empty string", constant="")

    class ReadFileTool(Tool):
        name = "read_file"
        description = "Read the text contents of a file at the given path on the user's Mac."

        @property
        def arguments_schema(self):
            return _ReadFileParams.generation_schema()

        async def call(self, args) -> str:
            try:
                path = args.value(str, for_property="path")
                full = os.path.expanduser(path)
                if not os.path.isfile(full):
                    return f"File not found: {path}"
                size = os.path.getsize(full)
                if size > 100_000:
                    return f"File too large to read ({size:,} bytes). Ask the user to paste a specific section."
                with open(full, encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file: {e}"

    class ClipboardReadTool(Tool):
        name = "clipboard_read"
        description = "Read the current text contents of the user's clipboard."

        @property
        def arguments_schema(self):
            return _ClipboardParams.generation_schema()

        async def call(self, args) -> str:
            try:
                result = subprocess.run(
                    ["pbpaste"], capture_output=True, text=True, timeout=3
                )
                return result.stdout or "[clipboard is empty]"
            except Exception as e:
                return f"Error reading clipboard: {e}"
