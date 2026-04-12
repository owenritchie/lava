"""Rich formatting helpers for lava."""

from __future__ import annotations

from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

C_PRIMARY = "#FF350C"
C_HOT     = "#FF350C"
C_EMBER   = "#6DE8E4"
C_ERROR   = "bold #FF350C"
C_RULE    = "#282926"
C_MUTED   = "#6D7E85"
C_TEXT    = "#FFF7E4"


def print_error(msg: str) -> None:
    err_console.print(f"[{C_ERROR}]Error:[/{C_ERROR}] [white]{msg}[/white]")


def print_success(msg: str) -> None:
    console.print(f"[bold {C_EMBER}]✓ {msg}[/bold {C_EMBER}]")


def print_links_table(inbound: list[str], outbound: list[str]) -> None:
    table = Table(show_header=True, header_style=f"bold {C_PRIMARY}")
    table.add_column("Inbound Links", style=C_EMBER)
    table.add_column("Outbound Links", style=C_HOT)

    max_rows = max(len(inbound), len(outbound), 1)
    for i in range(max_rows):
        in_val = inbound[i] if i < len(inbound) else ""
        out_val = outbound[i] if i < len(outbound) else ""
        table.add_row(in_val, out_val)

    console.print(table)


def paginate(
    items: list,
    page_size: int = 50,
    render_fn: Callable | None = None,
) -> None:
    if render_fn is None:
        render_fn = lambda batch: console.print("\n".join(str(i) for i in batch))

    total = len(items)
    start = 0
    while start < total:
        end = min(start + page_size, total)
        render_fn(items[start:end])
        start = end
        if start < total:
            try:
                response = input(
                    f"\n  [{start}/{total}] Show next {min(page_size, total - start)}? [y/N] "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            if response != "y":
                break


def config_panel(config: dict) -> None:
    import toml
    content = toml.dumps(config)
    console.print(Panel(
        content,
        title=f"[bold {C_PRIMARY}]lava config[/bold {C_PRIMARY}]",
        border_style=C_RULE,
        expand=False,
    ))
