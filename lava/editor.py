"""Editor integration: $EDITOR subprocess + Textual TUI fallback."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def body_start_line(path: Path) -> int:
    """Return the 1-based line number where the note body starts (after frontmatter)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return 1
    if not lines or lines[0].strip() != "---":
        return 1
    for i, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return i + 1
    return 1


def last_line(path: Path) -> int:
    """Return the 1-based line number to open the editor at (end of content, after frontmatter)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return 1
    return max(len(lines), body_start_line(path))


def open_in_editor(path: Path, editor_override: str = "", start_line: int = 1) -> None:
    """Open a file in $EDITOR at start_line, or fall back to the Textual TUI."""
    editor = editor_override or os.environ.get("EDITOR", "")
    if editor:
        try:
            editor_name = os.path.basename(editor).lower()
            if "hx" in editor_name:
                cmd = [editor, f"{path}:{start_line}"]
            elif start_line > 1:
                cmd = [editor, f"+{start_line}", str(path)]
            else:
                cmd = [editor, str(path)]
            subprocess.run(cmd, check=True)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    open_in_tui(path)


def open_in_tui(path: Path) -> None:
    """Open a simple Textual-based editor for the given file."""
    try:
        from lava._tui_editor import run_tui_editor
        run_tui_editor(path)
    except ImportError as e:
        from rich.console import Console
        Console().print(
            f"[red]Textual is not installed. Cannot open TUI editor.[/red]\n{e}"
        )
        raise SystemExit(1)
