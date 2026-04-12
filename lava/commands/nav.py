"""lava — Navigation commands: path, cd, mkdir, ls."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.prompt import Prompt
from rich.table import Table

from lava import config as cfg
from lava import vault as vlt
from lava import ui
from lava.ui import C_PRIMARY, C_TEXT
from lava._app import app, console
from lava._helpers import _cwd, _cwd_label


@app.command("path", rich_help_panel="Navigation")
def cmd_path() -> None:
    """Print the current vault path and working directory."""
    vault_str = cfg.get_vault_path()
    if not vault_str:
        ui.print_error("No vault set. Use: lava dir set <path>")
        raise typer.Exit(1)
    vault_path = Path(vault_str)
    cwd = _cwd(vault_path)
    console.print(_cwd_label(vault_path))
    if cwd != vault_path:
        console.print(f"[dim]{cwd}[/dim]")


@app.command("cd", rich_help_panel="Navigation")
def cmd_cd(
    folder: Annotated[Optional[str], typer.Argument(help="Folder to navigate into. Omit to pick. Use '..' to go up, '/' for root.")] = None,
) -> None:
    """Navigate into a subfolder of the vault."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    current = _cwd(vault_path)

    if folder is None:
        subdirs = sorted([p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "_archive"])
        if not subdirs:
            console.print("[dim]No subfolders here.[/dim]")
            return
        console.print(f"\n{_cwd_label(vault_path)}\n")
        console.print(f"  [dim] 0.[/dim]  [dim].. (up)[/dim]")
        for i, d in enumerate(subdirs, 1):
            note_count = sum(1 for _ in d.rglob("*.md"))
            console.print(f"  [dim]{i:2}.[/dim]  [{C_PRIMARY}]{d.name}/[/{C_PRIMARY}] [dim]{note_count}n[/dim]")
        console.print()
        choice = Prompt.ask("Pick A Directory #", default="").strip()
        if not choice:
            return
        try:
            idx = int(choice)
        except ValueError:
            ui.print_error("Invalid choice.")
            return
        if idx == 0:
            folder = ".."
        elif 1 <= idx <= len(subdirs):
            folder = subdirs[idx - 1].name
        else:
            ui.print_error("Invalid choice.")
            return

    if folder in ("/", "~"):
        cfg.set_vault_cwd("")
        console.print(_cwd_label(vault_path))
        return

    if folder == "..":
        if current == vault_path:
            console.print("[dim]Already at vault root.[/dim]")
            return
        parent = current.parent
        rel = str(parent.relative_to(vault_path)) if parent != vault_path else ""
        cfg.set_vault_cwd(rel)
        console.print(_cwd_label(vault_path))
        return

    target = current / folder
    if not target.exists():
        subdirs = [p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".")]
        matches = [d for d in subdirs if folder.lower() in d.name.lower()]
        if len(matches) == 1:
            target = matches[0]
        elif len(matches) > 1:
            ui.print_error(f"Ambiguous: {[d.name for d in matches]}")
            raise typer.Exit(1)
        else:
            ui.print_error(f"No folder found: {folder}")
            raise typer.Exit(1)

    if not target.is_dir():
        ui.print_error(f"Not a directory: {folder}")
        raise typer.Exit(1)

    rel = str(target.relative_to(vault_path))
    cfg.set_vault_cwd(rel)
    console.print(_cwd_label(vault_path))


@app.command("mkdir", rich_help_panel="Navigation")
def cmd_mkdir(
    name: Annotated[Optional[str], typer.Argument(help="Folder name to create (in current directory). Omit to be prompted.")] = None,
) -> None:
    """Create a new folder inside the current vault directory."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    if not name:
        name = Prompt.ask(f"[{C_PRIMARY}]Folder name[/{C_PRIMARY}]").strip()
        if not name:
            raise typer.Exit(0)

    current = _cwd(vault_path)
    new_dir = current / name
    if new_dir.exists():
        ui.print_error(f"Already exists: {name}")
        raise typer.Exit(1)

    new_dir.mkdir(parents=True)
    ui.print_success(f"Created: {new_dir.relative_to(vault_path)}")


@app.command("ls", rich_help_panel="Navigation")
def cmd_ls(
    folder: Annotated[Optional[str], typer.Argument(help="Subfolder to list (fuzzy matched). Omit for vault root.")] = None,
    all_dirs: Annotated[bool, typer.Option("--folder", "-f", help="Show all nested folders as a tree instead")] = False,
) -> None:
    """List folders and notes inside the vault or a specific folder."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    if all_dirs:
        current = _cwd(vault_path)
        subdirs = sorted(
            [p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".")],
            key=lambda p: p.name.lower(),
        )
        if not subdirs:
            console.print("[dim]No folders here.[/dim]")
        else:
            for d in subdirs:
                console.print(f"[{C_PRIMARY}]{d.name}/[/{C_PRIMARY}]")
        return

    target_is_specific = False
    if folder is None:
        target = _cwd(vault_path)
    else:
        target_is_specific = True
        folders = vlt.list_folders(vault_path)
        folder_lower = folder.lower()
        match = None
        for f in folders:
            if f.name.lower() == folder_lower:
                match = f
                break
        if match is None:
            for f in folders:
                if folder_lower in str(f.relative_to(vault_path)).lower():
                    match = f
                    break
        if match is None:
            ui.print_error(f"No folder found matching: {folder}")
            raise typer.Exit(1)
        target = match

    if target_is_specific:
        rel = target.relative_to(vault_path)
        parts = rel.parts
        trail = "/".join(f"[{C_PRIMARY}]{p}[/{C_PRIMARY}]" for p in parts)
        folder_label = f"[dim]{vault_path.name}/[/dim]{trail} [dim]/[/dim]"
        console.print(f"\n{folder_label}\n")
    else:
        console.print(f"\n{_cwd_label(vault_path)}\n")

    subdirs = sorted([p for p in target.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "_archive"])
    notes = sorted([p for p in target.iterdir() if p.is_file() and p.suffix == ".md"])

    if not subdirs and not notes:
        console.print("[dim]Empty folder.[/dim]")
        return

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("icon", style="", width=3)
    table.add_column("name")
    table.add_column("meta", style="dim")

    for d in subdirs:
        note_count = sum(1 for _ in d.rglob("*.md"))
        table.add_row(f"[{C_PRIMARY}]📁[/{C_PRIMARY}]", f"[{C_PRIMARY}]{d.name}/[/{C_PRIMARY}]", f"{note_count} note{'s' if note_count != 1 else ''}")

    for n in notes:
        stat = n.stat()
        from datetime import datetime
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
        table.add_row("[dim]·[/dim]", f"[{C_TEXT}]{n.stem}[/{C_TEXT}]", mtime)

    console.print(table)
    console.print(f"\n[dim]{len(subdirs)} folder{'s' if len(subdirs) != 1 else ''}  {len(notes)} note{'s' if len(notes) != 1 else ''}[/dim]")
