"""lava — Init commands: scaffold vault structure."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.prompt import Confirm, Prompt

from lava import config as cfg
from lava import vault as vlt
from lava import ui
from lava.ui import C_PRIMARY, C_TEXT, C_MUTED
from lava._app import app, console


init_app = typer.Typer(
    name="init",
    help="Scaffold folders and config files inside the vault.",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _get_vault() -> Path:
    config = cfg.load_config()
    try:
        return vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)


def _init_notes(vault_path: Path) -> None:
    """Create notes/ folder."""
    target = vault_path / "notes"
    if target.exists():
        console.print(f"[{C_MUTED}]notes/ already exists[/{C_MUTED}]")
        return
    target.mkdir()
    ui.print_success("Created: notes/")


def _init_links(vault_path: Path) -> None:
    """Create links/ folder and optionally set as default links folder."""
    target = vault_path / "links"
    target.mkdir(exist_ok=True)
    if not target.exists() or not any(True for _ in [target]):
        ui.print_success("Created: links/")
    else:
        ui.print_success("Created: links/")

    config = cfg.load_config()
    current_links_folder = config.get("links_folder", "")

    if not current_links_folder:
        set_default = Confirm.ask("Set as default links folder?", default=True)
        if set_default:
            cfg.set_dotted_key("links_folder", "links")
            ui.print_success("Links folder set to: links/")
    else:
        set_new = Confirm.ask(
            f"Change default links folder? [{C_MUTED}]{current_links_folder}[/{C_MUTED}] → links/",
            default=False,
        )
        if set_new:
            cfg.set_dotted_key("links_folder", "links")
            ui.print_success("Links folder updated to: links/")


def _init_config(vault_path: Path) -> None:
    """Create tags/ with tag_db.md and templates/ subfolder."""
    tags_dir = vault_path / "tags"
    templates_dir = vault_path / "templates"

    if not tags_dir.exists():
        tags_dir.mkdir()
        ui.print_success("Created: tags/")
    else:
        console.print(f"[{C_MUTED}]tags/ already exists[/{C_MUTED}]")

    tag_db = tags_dir / "tag_db.md"
    if not tag_db.exists():
        tag_db.write_text(
            "---\ntitle: Tag Database\ncreated: \ntags: []\n---\n\n"
            "# Tag Database\n\n<!-- tag: description -->\n",
            encoding="utf-8",
        )
        ui.print_success("Created: tags/tag_db.md")
    else:
        console.print(f"[{C_MUTED}]tags/tag_db.md already exists[/{C_MUTED}]")

    if not templates_dir.exists():
        templates_dir.mkdir()
        ui.print_success("Created: templates/")
    else:
        console.print(f"[{C_MUTED}]templates/ already exists[/{C_MUTED}]")


@init_app.callback(invoke_without_command=True)
def init_callback(ctx: typer.Context) -> None:
    """Scaffold vault structure — runs all init steps when called with no subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    vault_path = _get_vault()
    console.print(f"\n[bold {C_PRIMARY}]Initialising vault:[/bold {C_PRIMARY}] [{C_TEXT}]{vault_path}[/{C_TEXT}]\n")
    _init_notes(vault_path)
    _init_links(vault_path)
    _init_config(vault_path)


@init_app.command("notes")
@init_app.command("n", hidden=True)
def init_notes() -> None:
    """Create a notes/ folder in the vault."""
    _init_notes(_get_vault())


@init_app.command("links")
@init_app.command("l", hidden=True)
def init_links() -> None:
    """Create a links/ folder and optionally set it as the default links folder."""
    _init_links(_get_vault())


@init_app.command("config")
@init_app.command("c", hidden=True)
def init_config() -> None:
    """Create tags/ with tag_db.md and a templates/ folder."""
    _init_config(_get_vault())


@init_app.command("all")
@init_app.command("a", hidden=True)
def init_all() -> None:
    """Run all init steps: notes/, links/, tags/, templates/."""
    vault_path = _get_vault()
    console.print(f"\n[bold {C_PRIMARY}]Initialising vault:[/bold {C_PRIMARY}] [{C_TEXT}]{vault_path}[/{C_TEXT}]\n")
    _init_notes(vault_path)
    _init_links(vault_path)
    _init_config(vault_path)


@app.command("from-scratch", rich_help_panel="Configuration")
def cmd_from_scratch(
    path: Annotated[Optional[str], typer.Argument(help="Vault path. Omit to use current directory.")] = None,
) -> None:
    """Set a vault path and scaffold it from scratch."""
    if path is None:
        use_cwd = Confirm.ask("Set vault to current directory?", default=True)
        if use_cwd:
            vault_path = Path(".").resolve()
        else:
            raw = Prompt.ask(f"[{C_PRIMARY}]Vault path[/{C_PRIMARY}]").strip()
            if not raw:
                raise typer.Exit(0)
            vault_path = Path(raw).expanduser().resolve()
    else:
        vault_path = Path(path).expanduser().resolve()

    if not vault_path.exists():
        ui.print_error(f"Path does not exist: {vault_path}")
        raise typer.Exit(1)
    if not vault_path.is_dir():
        ui.print_error(f"Not a directory: {vault_path}")
        raise typer.Exit(1)

    cfg.set_vault_path(str(vault_path))
    cfg.add_to_history(str(vault_path))
    ui.print_success(f"Vault set to: {vault_path}")

    console.print()
    _init_notes(vault_path)
    _init_links(vault_path)
    _init_config(vault_path)
