"""lava — Configuration commands: dir_app, config_app, version, uninstall."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.prompt import Confirm, Prompt
from rich.table import Table

from lava import config as cfg
from lava import ui
from lava._app import app, console, _LAVA_VERSION
from lava.ui import C_PRIMARY, C_TEXT, C_EMBER


dir_app = typer.Typer(
    name="dir",
    help="Manage the active vault directory.",
    invoke_without_command=True,
    no_args_is_help=False,
)

config_app = typer.Typer(
    name="config",
    help="View and edit lava configuration.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@dir_app.callback(invoke_without_command=True)
def dir_callback(
    ctx: typer.Context,
    history: Annotated[bool, typer.Option("--history", help="Show recent vaults")] = False,
    list_vaults: Annotated[bool, typer.Option("--list", help="Show recent vaults (alias for --history)")] = False,
    pick: Annotated[bool, typer.Option("--pick", help="Pick vault from history")] = False,
    clear: Annotated[bool, typer.Option("--clear", help="Unset the active vault path")] = False,
) -> None:
    """Manage the active vault directory."""
    if ctx.invoked_subcommand is not None:
        return

    if clear:
        cfg.set_vault_path("")
        ui.print_success("Vault path cleared.")
        return

    if history or list_vaults:
        _dir_history()
        return

    if pick:
        _dir_pick()
        return

    _dir_set_prompt()


def _dir_set_prompt() -> None:
    """Interactively set the active vault path."""
    current = cfg.get_vault_path()
    if current:
        console.print(f"[dim]Current vault:[/dim] [{C_PRIMARY}]{current}[/{C_PRIMARY}]")
    else:
        console.print("[dim]No vault set.[/dim]")

    console.print(
        f"\n  [dim]Enter a path, or [/dim][bold {C_TEXT}]f[/bold {C_TEXT}][dim] to browse folders[/dim]"
    )
    raw = Prompt.ask(f"[{C_PRIMARY}]Vault path[/{C_PRIMARY}]", default="").strip()

    if not raw:
        return

    if raw.lower() == "f":
        location = _pick_fs_folder()
        if location is None:
            return
        resolved = str(location)
    else:
        resolved = str(Path(raw).expanduser().resolve())

    if not Path(resolved).exists():
        ui.print_error(f"Path does not exist: {resolved}")
        raise typer.Exit(1)

    cfg.set_vault_path(resolved)
    cfg.add_to_history(resolved)
    ui.print_success(f"Vault set to: {resolved}")


def _dir_history() -> None:
    config = cfg.load_config()
    history = config.get("vault", {}).get("history", [])
    if not history:
        console.print("[dim]No vault history.[/dim]")
        return

    table = Table(title="Recent Vaults", header_style=f"bold {C_PRIMARY}")
    table.add_column("#", style="dim", width=4)
    table.add_column("Path", style=C_TEXT)
    current = cfg.get_vault_path()
    for i, p in enumerate(history, 1):
        marker = f" [{C_EMBER}](active)[/{C_EMBER}]" if p == current else ""
        table.add_row(str(i), p + marker)
    console.print(table)

    choice = Prompt.ask("Switch to vault # (or Enter to skip)", default="").strip()
    if not choice:
        return
    try:
        idx = int(choice) - 1
        selected = history[idx]
    except (ValueError, IndexError):
        ui.print_error("Invalid selection.")
        return
    cfg.set_vault_path(selected)
    cfg.add_to_history(selected)
    ui.print_success(f"Vault set to: {selected}")


def _dir_pick() -> None:
    config = cfg.load_config()
    history = config.get("vault", {}).get("history", [])
    if not history:
        ui.print_error("No vault history to pick from.")
        raise typer.Exit(1)

    console.print(f"[bold {C_PRIMARY}]Recent vaults:[/bold {C_PRIMARY}]")
    for i, p in enumerate(history, 1):
        console.print(f"  [dim]{i}.[/dim] {p}")

    choice = Prompt.ask("Pick a vault number", default="1")
    try:
        idx = int(choice) - 1
        selected = history[idx]
    except (ValueError, IndexError):
        ui.print_error("Invalid selection.")
        raise typer.Exit(1)

    cfg.set_vault_path(selected)
    cfg.add_to_history(selected)
    ui.print_success(f"Vault set to: {selected}")


def _pick_fs_folder() -> Path | None:
    """Navigate the real filesystem level-by-level (folders only) and return chosen path."""
    current = Path.home()

    while True:
        subdirs = sorted(
            [p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".")],
            key=lambda p: p.name.lower(),
        )

        console.print(f"\n[bold {C_PRIMARY}]{current}[/bold {C_PRIMARY}]\n")
        console.print(f"  [dim] 0.[/dim]  [dim]✓ use this folder[/dim]")
        if current != current.anchor:
            console.print(f"  [dim] b.[/dim]  [dim].. (go up)[/dim]")
        for i, d in enumerate(subdirs, 1):
            console.print(f"  [dim]{i:2}.[/dim]  [{C_PRIMARY}]{d.name}/[/{C_PRIMARY}]")
        console.print()

        choice = Prompt.ask("Pick folder or #", default="").strip().lower()
        if not choice:
            return None
        if choice == "0":
            return current
        if choice == "b" and current != Path(current.anchor):
            current = current.parent
            continue
        try:
            idx = int(choice)
            if 1 <= idx <= len(subdirs):
                current = subdirs[idx - 1]
            else:
                ui.print_error("Invalid choice.")
        except ValueError:
            ui.print_error("Invalid choice.")


@dir_app.command("init")
def dir_init(
    path: Annotated[Optional[str], typer.Argument(help="Path for the new vault. Omit to create in current directory.")] = None,
    pick: Annotated[bool, typer.Option("--pick", help="Navigate filesystem to pick location")] = False,
) -> None:
    """Create a new vault directory and set it as the active vault."""
    if pick:
        location = _pick_fs_folder()
        if location is None:
            raise typer.Exit(0)
        vault_name = Prompt.ask(f"[{C_PRIMARY}]Vault name[/{C_PRIMARY}]").strip()
        if not vault_name:
            raise typer.Exit(0)
        resolved = location / vault_name
    elif path:
        resolved = Path(path).expanduser().resolve()
    else:
        vault_name = Prompt.ask(f"[{C_PRIMARY}]Vault name[/{C_PRIMARY}]").strip()
        if not vault_name:
            raise typer.Exit(0)
        resolved = Path.cwd() / vault_name

    if resolved.exists() and any(resolved.iterdir()):
        ui.print_error(f"Directory already exists and is not empty: {resolved}")
        raise typer.Exit(1)

    resolved.mkdir(parents=True, exist_ok=True)

    cfg.set_vault_path(str(resolved))
    cfg.add_to_history(str(resolved))

    console.print(f"\n[bold {C_PRIMARY}]Vault created:[/bold {C_PRIMARY}] {resolved}")
    console.print(f"[dim]Active vault set. Run [{C_TEXT}]lava new[/{C_TEXT}] to get started.[/dim]")


@dir_app.command("set")
def dir_set(
    path: Annotated[str, typer.Argument(help="Vault path, or 'current' for cwd")],
) -> None:
    """Set the active vault path."""
    if path.lower() == "current":
        resolved = str(Path.cwd())
    else:
        resolved = str(Path(path).expanduser().resolve())

    if not Path(resolved).exists():
        ui.print_error(f"Path does not exist: {resolved}")
        raise typer.Exit(1)

    cfg.set_vault_path(resolved)
    cfg.add_to_history(resolved)
    ui.print_success(f"Vault set to: {resolved}")


@config_app.callback(invoke_without_command=True)
def config_callback(
    ctx: typer.Context,
    edit: Annotated[bool, typer.Option("--edit", help="Open config in $EDITOR")] = False,
) -> None:
    """View or edit the lava configuration."""
    if ctx.invoked_subcommand is not None:
        return

    config = cfg.load_config()

    if edit:
        config_path = cfg.get_config_path()
        editor = config.get("editor", "") or os.environ.get("EDITOR", "")
        if editor:
            subprocess.run([editor, str(config_path)])
        else:
            console.print(f"[{C_PRIMARY}]Config file:[/{C_PRIMARY}] {config_path}")
            console.print("[dim]Set $EDITOR or lava config set editor <editor> to open it.[/dim]")
        return

    ui.config_panel(config)


@config_app.command("set")
def config_set(
    key: Annotated[Optional[str], typer.Argument(help="Dotted config key (e.g. pagination, editor)")] = None,
    value: Annotated[Optional[str], typer.Argument(help="Value to set")] = None,
    link_folder: Annotated[bool, typer.Option("--link-folder", is_flag=True, help="Set the links folder to the current working directory.")] = False,
    link_folder_path: Annotated[Optional[str], typer.Option("--link-folder-path", help="Set the links folder to a specific path.")] = None,
) -> None:
    """Set a config value, or configure the links folder."""
    if link_folder_path is not None:
        cfg.set_dotted_key("links_folder", link_folder_path)
        ui.print_success(f"Links folder set to: {link_folder_path}")
        return

    if link_folder:
        path_val = cfg.get_vault_cwd() or "."
        cfg.set_dotted_key("links_folder", path_val)
        ui.print_success(f"Links folder set to: {path_val}")
        return

    if key is None or value is None:
        ui.print_error("Usage: lava config set <key> <value>  or  lava config set --link-folder")
        raise typer.Exit(1)

    try:
        cfg.set_dotted_key(key, value)
        ui.print_success(f"Config updated: {key} = {value}")
    except Exception as e:
        ui.print_error(str(e))
        raise typer.Exit(1)


@app.command("version", rich_help_panel="Configuration")
def cmd_version() -> None:
    """Show the installed lava version."""
    console.print(f"lava [{C_PRIMARY}]{_LAVA_VERSION}[/{C_PRIMARY}]")


@app.command("uninstall", rich_help_panel="Other")
def cmd_uninstall() -> None:
    """Uninstall lava from the current Python environment."""
    confirmed = Confirm.ask(
        f"Uninstall [{C_PRIMARY}]lava {_LAVA_VERSION}[/{C_PRIMARY}] from this environment?",
        default=False,
    )
    if not confirmed:
        raise typer.Exit(0)
    subprocess.run(["pip", "uninstall", "lava", "-y"], check=True)
