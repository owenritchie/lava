"""lava — Graph commands: child, parent, tree, links, orphans."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.tree import Tree

from lava import config as cfg
from lava import editor as ed
from lava import graph as gph
from lava import vault as vlt
from lava import ui
from lava.ui import C_PRIMARY, C_EMBER, C_TEXT, C_MUTED
from lava._app import app, console
from lava._helpers import _cwd, _cwd_label, _pick_move_destination


@app.command("child", rich_help_panel="Graph")
def cmd_child(
    name: Annotated[str, typer.Argument(help="Note name")],
    all_links: Annotated[bool, typer.Option("--all", help="Show all without pagination")] = False,
) -> None:
    """Show notes that link TO this note (inbound links)."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    notes_paths = vlt.list_notes(vault_path)
    notes = [vlt.parse_note(p) for p in notes_paths]
    graph = gph.build_graph(notes)

    children = gph.get_parents(graph, name)

    if not children:
        console.print(f"[dim]No inbound links to[/dim] [{C_PRIMARY}]{name}[/{C_PRIMARY}]")
        return

    page_size = 50 if not all_links else len(children)

    def render(batch: list) -> None:
        table = Table(header_style=f"bold {C_PRIMARY}", title=f"Children of '{name}'")
        table.add_column("Note", style=C_TEXT)
        for item in batch:
            table.add_row(item)
        console.print(table)

    ui.paginate(children, page_size=page_size, render_fn=render)


@app.command("parent", rich_help_panel="Graph")
def cmd_parent(
    name: Annotated[str, typer.Argument(help="Note name")],
) -> None:
    """Show notes that this note links to (outbound links)."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    notes_paths = vlt.list_notes(vault_path)
    notes = [vlt.parse_note(p) for p in notes_paths]
    graph = gph.build_graph(notes)
    parents = gph.get_children(graph, name)

    if not parents:
        console.print(f"[dim]No outbound links from[/dim] [{C_PRIMARY}]{name}[/{C_PRIMARY}]")
        return

    page_size = cfg.load_config().get("pagination", 50)

    def render(batch: list) -> None:
        table = Table(header_style=f"bold {C_PRIMARY}", title=f"Parents of '{name}'")
        table.add_column("Note", style=C_TEXT)
        for item in batch:
            table.add_row(item)
        console.print(table)

    ui.paginate(parents, page_size=page_size, render_fn=render)


@app.command("tree", rich_help_panel="Graph")
def cmd_tree(
    name: Annotated[Optional[str], typer.Argument(help="Root note (omit for full vault)")] = None,
    depth: Annotated[Optional[int], typer.Option("--depth", help="Max tree depth")] = None,
) -> None:
    """Render a Rich tree of the note hierarchy."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    max_depth = depth if depth is not None else config.get("ui", {}).get("tree_depth", 4)

    current = _cwd(vault_path)
    all_notes_paths = vlt.list_notes(vault_path)
    cwd_note_paths = [p for p in all_notes_paths if str(p).startswith(str(current))]
    notes = [vlt.parse_note(p) for p in cwd_note_paths]
    graph = gph.build_graph(notes)

    if name:
        subtree = gph.get_subtree_reversed(graph, name, max_depth)
        root_key = name.lower()
        display = graph.nodes[root_key].get("display", name) if root_key in graph else name
        rich_tree = Tree(f"[bold {C_PRIMARY}]{display}[/bold {C_PRIMARY}]")
        _build_rich_tree_reversed(subtree, root_key, rich_tree, max_depth, set())
        console.print(rich_tree)
    else:
        roots = [
            n for n in graph.nodes
            if graph.out_degree(n) == 0 and graph.nodes[n].get("path") is not None
        ]
        roots.sort(key=lambda n: graph.in_degree(n), reverse=True)

        label = _cwd_label(vault_path)
        rich_tree = Tree(label)
        for root in roots:
            display = graph.nodes[root].get("display", root)
            branch = rich_tree.add(f"[{C_TEXT}]{display}[/{C_TEXT}]")
            _build_rich_tree_reversed(graph, root, branch, max_depth - 1, set())

        console.print(rich_tree)


def _build_rich_tree(
    graph,
    node: str,
    branch,
    remaining_depth: int,
    visited: set,
) -> None:
    if remaining_depth <= 0:
        return
    visited = visited | {node}
    for child in graph.successors(node):
        if child in visited:
            branch.add(f"[dim]{graph.nodes[child].get('display', child)} (↩ cycle)[/dim]")
            continue
        display = graph.nodes[child].get("display", child)
        child_branch = branch.add(f"[{C_TEXT}]{display}[/{C_TEXT}]")
        _build_rich_tree(graph, child, child_branch, remaining_depth - 1, visited)


def _build_rich_tree_reversed(
    graph,
    node: str,
    branch,
    remaining_depth: int,
    visited: set,
) -> None:
    if remaining_depth <= 0:
        return
    visited = visited | {node}
    for pred in graph.predecessors(node):
        if pred in visited:
            branch.add(f"[dim]{graph.nodes[pred].get('display', pred)} (↩ cycle)[/dim]")
            continue
        display = graph.nodes[pred].get("display", pred)
        child_branch = branch.add(f"[{C_TEXT}]{display}[/{C_TEXT}]")
        _build_rich_tree_reversed(graph, pred, child_branch, remaining_depth - 1, visited)


@app.command("links", rich_help_panel="Graph")
def cmd_links(
    name: Annotated[str, typer.Argument(help="Note name")],
) -> None:
    """Show both inbound and outbound links for a note."""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    notes_paths = vlt.list_notes(vault_path)
    notes = [vlt.parse_note(p) for p in notes_paths]
    graph = gph.build_graph(notes)

    inbound = gph.get_parents(graph, name)
    outbound = gph.get_children(graph, name)

    console.print(f"\n[bold {C_PRIMARY}]Links for:[/bold {C_PRIMARY}] [{C_TEXT}]{name}[/{C_TEXT}]\n")
    ui.print_links_table(inbound, outbound)


@app.command("orphans", rich_help_panel="Graph")
def cmd_orphans() -> None:
    """List all notes with no inbound or outbound links.  [o]"""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    notes_paths = vlt.list_notes(vault_path)
    notes = [vlt.parse_note(p) for p in notes_paths]
    graph = gph.build_graph(notes)
    orphan_names = gph.get_orphans(graph)

    if not orphan_names:
        console.print("[dim]No orphaned notes found.[/dim]")
        return

    name_to_path = {p.stem: p for p in notes_paths}
    orphans: list[tuple[str, Path]] = []
    for name in sorted(orphan_names):
        path = name_to_path.get(name)
        if path:
            orphans.append((name, path))

    now = datetime.now()

    def _age_label(path: Path) -> str:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            days = (now - mtime).days
            if days == 0:
                return "today"
            elif days == 1:
                return "1 day ago"
            else:
                return f"{days} days ago"
        except OSError:
            return ""

    def _age_color(path: Path) -> str:
        try:
            days = (now - datetime.fromtimestamp(path.stat().st_mtime)).days
        except OSError:
            return C_TEXT
        if days > 90:
            return C_PRIMARY
        if days > 30:
            return C_EMBER
        return C_MUTED

    def _print_orphans(orphan_list: list[tuple[str, Path]]) -> None:
        console.print(f"\n[bold {C_PRIMARY}]Orphaned Notes[/bold {C_PRIMARY}] [dim]({len(orphan_list)})[/dim]\n")
        for i, (name, path) in enumerate(orphan_list):
            rel = path.relative_to(vault_path)
            age = _age_label(path)
            color = _age_color(path)
            rel_str = str(rel).replace("\\", "/")
            console.print(
                f"  [dim]{i + 1:2}.[/dim]  [{C_TEXT}]{name:<40}[/{C_TEXT}]"
                f"  [dim]{rel_str}[/dim]  [{color}]{age}[/{color}]"
            )
        console.print()

    while orphans:
        _print_orphans(orphans)
        choice = Prompt.ask("Pick a number to act on (or Enter to quit)", default="").strip()
        if not choice:
            break
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(orphans):
                raise ValueError
        except ValueError:
            ui.print_error("Invalid number.")
            continue

        selected_name, selected_path = orphans[idx]
        console.print(f"\n  [{C_PRIMARY}]{selected_name}[/{C_PRIMARY}]  [dim]{selected_path.relative_to(vault_path)}[/dim]\n")
        action = Prompt.ask(r"  \[e]dit  \[m]ove  \[d]elete", default="").strip().lower()

        if action == "e":
            start_line = ed.last_line(selected_path)
            ed.open_in_editor(selected_path, editor_override=config.get("editor", ""), start_line=start_line)
            orphans.pop(idx)

        elif action == "m":
            destination = _pick_move_destination(vault_path, selected_path)
            if destination:
                new_path, updated = vlt.move_note(vault_path, selected_path, destination)
                ui.print_success(f"Moved: {selected_name} → {new_path.stem}")
                if updated:
                    console.print(f"[dim]Updated wikilinks in {updated} note(s).[/dim]")
                orphans.pop(idx)

        elif action == "d":
            confirmed = Confirm.ask(f"Archive [{C_PRIMARY}]{selected_name}[/{C_PRIMARY}]?", default=False)
            if confirmed:
                archive_dir = vault_path / "_archive"
                archive_dir.mkdir(exist_ok=True)
                dest = archive_dir / selected_path.name
                if dest.exists():
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    dest = archive_dir / f"{selected_path.stem}_{timestamp}{selected_path.suffix}"
                shutil.move(str(selected_path), str(dest))
                ui.print_success(f"Archived to: _archive/{dest.name}")
                orphans.pop(idx)

        console.print()
