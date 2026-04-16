"""Textual-based TUI editor for lava."""

from __future__ import annotations

from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TextArea


class LavaEditorApp(App):
    """A minimal TUI editor for editing vault notes."""

    TITLE = "lava editor"
    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("ctrl+q", "save_quit", "Save & Quit", show=True),
        Binding("ctrl+c", "quit_no_save", "Quit without saving", show=True),
    ]

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._content = path.read_text(encoding="utf-8") if path.exists() else ""
        self._saved = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield TextArea(self._content, id="editor", language="markdown")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"lava — {self._path.name}"
        text_area = self.query_one("#editor", TextArea)
        text_area.focus()
        text_area.move_cursor(text_area.document.end)

    def action_save(self) -> None:
        content = self.query_one("#editor", TextArea).text
        self._path.write_text(content, encoding="utf-8")
        self._saved = True
        self.notify(f"Saved {self._path.name}", severity="information")

    def action_save_quit(self) -> None:
        self.action_save()
        self.exit()

    def on_key(self, event: events.Key) -> None:
        if event.key == "space":
            text_area = self.query_one("#editor", TextArea)
            if text_area.has_focus:
                text_area.insert(" ")
                event.prevent_default()
                event.stop()

    def action_quit_no_save(self) -> None:
        self.exit()


def run_tui_editor(path: Path) -> None:
    """Launch the Textual TUI editor for a file."""
    app = LavaEditorApp(path)
    app.run()
