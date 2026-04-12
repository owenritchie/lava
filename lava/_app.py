"""lava — app singleton, console, and shared constants."""

from __future__ import annotations

import typer
from rich.console import Console

from lava import __version__ as _LAVA_VERSION

app = typer.Typer(
    name="lava",
    help="A CLI toolkit for interacting with Obsidian vaults.",
    add_completion=False,
    no_args_is_help=False,
)

console = Console()
