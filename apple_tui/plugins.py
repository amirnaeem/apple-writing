"""
Plugin loader — merges user-defined commands from ~/.config/apple-tui/commands/*.toml
with the built-in COMMANDS list at startup.

Plugin TOML format:
  name        = "/myplugin"       # must start with /
  description = "What it does"
  template    = "Do this:\n\n"   # pre-fills the input; must end with \n
  use_case    = 0                 # 0 = GENERAL, 1 = CONTENT_TAGGING (optional)

Example ~/.config/apple-tui/commands/legal.toml:
  name        = "/legal"
  description = "Simplify legal text to plain English"
  template    = "Rewrite the following legal text in plain English. Preserve all meaning:\n\n"
"""

import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "apple-tui"
COMMANDS_DIR = CONFIG_DIR / "commands"


def load_plugins(Command) -> list:
    """Load all TOML plugin files and return a list of Command instances."""
    if not COMMANDS_DIR.exists():
        return []

    plugins = []
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return []

    for toml_file in sorted(COMMANDS_DIR.glob("*.toml")):
        try:
            data = tomllib.loads(toml_file.read_text(encoding="utf-8"))
            name = data.get("name", "")
            description = data.get("description", "")
            template = data.get("template", "")
            use_case = int(data.get("use_case", 0))

            if not name.startswith("/") or not template or not description:
                continue
            if not template.endswith("\n"):
                template += "\n"

            plugins.append(Command(
                name=name,
                description=description,
                template=template,
                use_case=use_case,
            ))
        except Exception:
            continue

    return plugins
