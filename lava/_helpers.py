"""lava — shared helpers used across multiple command modules."""

from __future__ import annotations

from pathlib import Path

from rich.prompt import Prompt

from lava import config as cfg
from lava import vault as vlt
from lava import ui
from lava._app import console


def _cwd(vault_path: Path) -> Path:
    """Return the current working directory within the vault."""
    rel = cfg.get_vault_cwd()
    if not rel:
        return vault_path
    candidate = vault_path / rel
    if candidate.exists() and candidate.is_dir():
        return candidate
    # cwd no longer valid (folder deleted), reset to root
    cfg.set_vault_cwd("")
    return vault_path


def _cwd_label(vault_path: Path) -> str:
    cwd = _cwd(vault_path)
    if cwd == vault_path:
        return f"[bold orange1]{vault_path.name}[/bold orange1] [dim]/[/dim]"
    rel = cwd.relative_to(vault_path)
    parts = rel.parts
    trail = "/".join(f"[orange1]{p}[/orange1]" for p in parts)
    return f"[dim]{vault_path.name}/[/dim]{trail} [dim]/[/dim]"


def _pick_move_destination(vault_path: Path, source: Path) -> str | None:
    """Interactive folder picker + optional rename."""
    folders = vlt.list_folders(vault_path)

    console.print(f"\n[bold orange1]Move:[/bold orange1] [white]{source.stem}[/white]\n")
    console.print(f"  [dim] 0.[/dim]  [white]/ (vault root)[/white]")
    for i, folder in enumerate(folders, 1):
        rel = folder.relative_to(vault_path)
        console.print(f"  [dim]{i:2}.[/dim]  [white]{rel}[/white]")

    choice = Prompt.ask("\nDestination folder", default="0")
    try:
        idx = int(choice)
    except ValueError:
        ui.print_error("Invalid choice.")
        return None

    if idx == 0:
        folder_path = vault_path
    elif 1 <= idx <= len(folders):
        folder_path = folders[idx - 1]
    else:
        ui.print_error("Invalid choice.")
        return None

    new_name = Prompt.ask("New name", default=source.stem)

    rel_folder = folder_path.relative_to(vault_path)
    if str(rel_folder) == ".":
        return new_name
    return str(rel_folder / new_name)
