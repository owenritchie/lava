"""lava — Configuration commands: dir_app, config_app, version, uninstall."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.prompt import Confirm

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
    clear_vault_history: Annotated[bool, typer.Option("--clear-vault-history", help="Clear vault history")] = False,
) -> None:
    """Manage the active vault directory."""
    if ctx.invoked_subcommand is not None:
        return

    if clear_vault_history:
        config = cfg.load_config()
        config["vault"]["history"] = []
        cfg.save_config(config)
        ui.print_success("Vault history cleared.")
        return

    config = cfg.load_config()
    history = config.get("vault", {}).get("history", [])
    current = cfg.get_vault_path()

    if not history:
        if current:
            console.print(f"[{C_PRIMARY}]{current}[/{C_PRIMARY}]")
        else:
            console.print("[dim]No vault set. Run [bold]lava dir <path>[/bold] to configure one.[/dim]")
        return

    console.print()
    for i, p in enumerate(history, 1):
        if p == current:
            console.print(f"  [grey50]{i}.  {p}[/grey50] [{C_EMBER}]●[/{C_EMBER}]")
        else:
            console.print(f"  [grey50]{i}.  {p}[/grey50]")
    console.print()

    console.print("  Switch to #: ", end="")
    choice = input().strip()
    if not choice:
        return
    try:
        selected = history[int(choice) - 1]
    except (ValueError, IndexError):
        ui.print_error("Invalid selection.")
        return
    cfg.set_vault_path(selected)
    cfg.add_to_history(selected)
    ui.print_success(f"Vault set to: {selected}")




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
