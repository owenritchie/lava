"""lava — CLI entry point."""
import typer
from lava._app import app, console
from lava import __version__ as _LAVA_VERSION
from lava.ui import C_PRIMARY, C_EMBER

import lava.commands.nav  # noqa: F401
import lava.commands.notes  # noqa: F401
import lava.commands.vault_info  # noqa: F401
import lava.commands.graph_cmds  # noqa: F401
import lava.commands.config_cmds  # noqa: F401

from lava.commands.config_cmds import dir_app, config_app
app.add_typer(dir_app, name="dir", rich_help_panel="Configuration")
app.add_typer(config_app, name="config", rich_help_panel="Configuration")

from lava.commands.vault_info import cmd_status, cmd_count
from lava.commands.notes import cmd_new, cmd_edit, cmd_delete, cmd_move, cmd_view
from lava.commands.graph_cmds import cmd_orphans

app.command("s", hidden=True)(cmd_status)
app.command("c", hidden=True)(cmd_count)
app.command("n", hidden=True)(cmd_new)
app.command("e", hidden=True)(cmd_edit)
app.command("d", hidden=True)(cmd_delete)
app.command("m", hidden=True)(cmd_move)
app.command("v", hidden=True)(cmd_view)
app.command("o", hidden=True)(cmd_orphans)


_ASCII_LAVA = """\
  ██╗      █████╗ ██╗   ██╗ █████╗
  ██║     ██╔══██╗██║   ██║██╔══██╗
  ██║     ███████║██║   ██║███████║
  ██║     ██╔══██║╚██╗ ██╔╝██╔══██║
  ███████╗██║  ██║ ╚████╔╝ ██║  ██║
  ╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝"""


@app.callback(invoke_without_command=True)
def _home(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    console.print(f"\n[{C_PRIMARY}]{_ASCII_LAVA}[/{C_PRIMARY}]\n")
    console.print(f"  [{C_EMBER}]v{_LAVA_VERSION}[/{C_EMBER}]\n")
    console.print(
        "  Lava is a simple, easy to use note-taker for UNIX CLIs. Notes can be easily\n"
        "  created, tagged and linked in tree style hierarchies. To begin, set your root\n"
        "  directory (vault) by using [bold]lava dir set <path>[/bold]\n"
    )
    console.print("  [dim]Use --help for further information.[/dim]\n")


def main() -> None:
    app()
