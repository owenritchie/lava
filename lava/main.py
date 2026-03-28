"""lava — CLI entry point."""
from lava._app import app

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


def main() -> None:
    app()
