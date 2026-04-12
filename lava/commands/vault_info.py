"""lava — Vault info commands: status, count, search."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from lava import config as cfg
from lava import editor as ed
from lava import graph as gph
from lava import search as srch
from lava import vault as vlt
from lava import ui
from lava._app import app, console
from lava._helpers import _cwd, _cwd_label, _pick_move_destination


@app.command("status", rich_help_panel="Vault")
def cmd_status() -> None:
    """Show vault statistics: note count, orphans, most-linked, last modified.  [s]"""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("[orange1]{task.description}"), transient=True) as progress:
        progress.add_task("Scanning vault...", total=None)
        notes_paths = vlt.list_notes(vault_path)
        notes = [vlt.parse_note(p) for p in notes_paths]

    graph = gph.build_graph(notes)
    orphans = gph.get_orphans(graph)
    most_linked = gph.get_most_linked(graph, n=5)

    last_mod_path: Path | None = None
    last_mod_time: float = 0
    for p in notes_paths:
        mtime = p.stat().st_mtime
        if mtime > last_mod_time:
            last_mod_time = mtime
            last_mod_path = p

    last_mod_str = ""
    if last_mod_path:
        dt = datetime.fromtimestamp(last_mod_time)
        last_mod_str = f"{last_mod_path.stem} ({dt.strftime('%Y-%m-%d %H:%M')})"

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="orange1")
    table.add_column("Value", style="white")
    table.add_row("Total notes", str(len(notes)))
    table.add_row("Orphaned notes", str(len(orphans)))
    table.add_row("Last modified", last_mod_str or "[dim]—[/dim]")

    console.print(Panel(table, title="[bold orange1]Vault Status[/bold orange1]", border_style="dark_red", expand=False))

    if most_linked:
        ml_table = Table(title="Most Linked Notes", header_style="bold orange1")
        ml_table.add_column("Note", style="white")
        ml_table.add_column("Inbound Links", style="gold1", justify="right")
        for name, count in most_linked:
            ml_table.add_row(name, str(count))
        console.print(ml_table)


@app.command("count", rich_help_panel="Vault")
def cmd_count() -> None:
    """Count notes in the current working directory and vault total.  [c]"""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    all_notes = vlt.list_notes(vault_path)
    current = _cwd(vault_path)
    cwd_notes = [p for p in all_notes if str(p).startswith(str(current))]
    label = _cwd_label(vault_path)
    console.print(f"[cornflower_blue]{len(cwd_notes)}[/cornflower_blue] notes [dim]in[/dim] {label}")
    console.print(f"[orange1]{len(all_notes)}[/orange1] notes [dim]in vault[/dim]")


@app.command("clear", rich_help_panel="Vault")
def cmd_clear() -> None:
    """Clear all notes from the archive (_archive/)."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    archive_dir = vault_path / "_archive"
    if not archive_dir.exists() or not any(archive_dir.iterdir()):
        console.print("[dim]Archive is already empty.[/dim]")
        return

    items = list(archive_dir.iterdir())
    console.print(f"\n[bold]Archive contains {len(items)} item{'s' if len(items) != 1 else ''}.[/bold]\n")
    confirm = Prompt.ask("Type [bold red]DELETE[/bold red] to confirm").strip()
    if confirm != "DELETE":
        console.print("[dim]Cancelled.[/dim]")
        return

    shutil.rmtree(archive_dir)
    ui.print_success("Archive cleared.")


@app.command("search", rich_help_panel="Vault")
def cmd_search(
    query: Annotated[str, typer.Argument(help="Search query")],
    top: Annotated[int, typer.Option("--top", help="Number of results")] = 10,
) -> None:
    """BM25 full-text search across all notes."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    notes_paths = vlt.list_notes(vault_path)
    notes = [vlt.parse_note(p) for p in notes_paths]

    if not notes:
        ui.print_error("No notes found in vault.")
        raise typer.Exit(1)

    index = srch.build_index(notes)
    results = srch.search(index, notes, query, top_k=top)

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    result_items: list[tuple[str, Path]] = []
    for r in results:
        name = r.get("name", "")
        path = vlt.fuzzy_match(vault_path, name)
        if path:
            result_items.append((name, path))

    def _print_results() -> None:
        console.print(f"\n[bold orange1]Search:[/bold orange1] [dim]{query}[/dim]\n")
        for i, (name, path) in enumerate(result_items, 1):
            rel = path.relative_to(vault_path)
            r = next((x for x in results if x.get("name") == name), {})
            snippet = _make_snippet(r.get("body", ""), query, length=60)
            console.print(
                f"  [dim]{i:2}.[/dim]  [white]{name}[/white]  [dim]{rel.parent}/[/dim]"
            )
            if snippet:
                console.print(f"        [dim italic]{snippet}[/dim italic]")
        console.print()

    while result_items:
        _print_results()
        choice = Prompt.ask(
            "Pick a number to act on (or Enter to quit)", default=""
        ).strip()
        if not choice:
            break
        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(result_items)):
                raise ValueError
        except ValueError:
            ui.print_error("Invalid choice.")
            continue

        selected_name, selected_path = result_items[idx]
        console.print(
            f"\n[bold white]{selected_name}[/bold white]  "
            f"[dim]{selected_path.relative_to(vault_path)}[/dim]"
        )
        action = Prompt.ask(
            r"  \[e]dit  \[v]iew  \[m]ove  \[d]elete  \[Enter] back",
            default="",
        ).strip().lower()

        if action == "e":
            editor_cfg = config.get("editor", "")
            start_line = ed.last_line(selected_path)
            ed.open_in_editor(selected_path, editor_override=editor_cfg, start_line=start_line)
        elif action == "v":
            note = vlt.parse_note(selected_path)
            fm = note["frontmatter"]
            body = note["body"]
            title = fm.get("title", selected_path.stem)
            console.print(f"\n[bold white]{title}[/bold white]")
            console.rule(style="dim")
            from rich.markdown import Markdown
            console.print(Markdown(body))
        elif action == "m":
            destination = _pick_move_destination(vault_path, selected_path)
            if destination:
                new_path, updated = vlt.move_note(vault_path, selected_path, destination)
                ui.print_success(f"Moved: {selected_name} → {new_path.stem}")
                if updated:
                    console.print(f"[dim]Updated wikilinks in {updated} note(s).[/dim]")
                result_items.pop(idx)
        elif action == "d":
            confirmed = Confirm.ask(f"Archive [orange1]{selected_name}[/orange1]?", default=False)
            if confirmed:
                archive_dir = vault_path / "_archive"
                archive_dir.mkdir(exist_ok=True)
                dest = archive_dir / selected_path.name
                if dest.exists():
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    dest = archive_dir / f"{selected_path.stem}_{timestamp}{selected_path.suffix}"
                shutil.move(str(selected_path), str(dest))
                ui.print_success(f"Archived: {selected_name}")
                result_items.pop(idx)
        console.print()


def _make_snippet(body: str, query: str, length: int = 80) -> str:
    """Find the first occurrence of any query word and return surrounding text."""
    import re
    words = re.findall(r"\w+", query.lower())
    lower_body = body.lower()
    best_pos = len(body)
    for word in words:
        pos = lower_body.find(word)
        if pos != -1 and pos < best_pos:
            best_pos = pos

    if best_pos == len(body):
        return body[:length].replace("\n", " ").strip()

    start = max(0, best_pos - 20)
    end = min(len(body), start + length)
    snippet = body[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(body):
        snippet = snippet + "…"
    return snippet
