"""lava — Notes commands: new, edit, view, delete, move."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.prompt import Confirm, Prompt

from lava import config as cfg
from lava import editor as ed
from lava import graph as gph
from lava import vault as vlt
from lava import ui
from lava.ui import C_PRIMARY
from lava._app import app, console
from lava._helpers import _cwd, _cwd_label, _pick_move_destination


@app.command("new", rich_help_panel="Notes")
def cmd_new(
    name: Annotated[Optional[str], typer.Argument(help="Note name. Omit to be prompted.")] = None,
    link: Annotated[bool, typer.Option("--link", help="Create in links folder, prompt for tags")] = False,
) -> None:
    """Create a new note in the vault.  [n]"""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    if link:
        links_folder = config.get("links_folder", "")
        if not links_folder:
            ui.print_error("No links folder set. Run: lava config set --link-folder")
            raise typer.Exit(1)
        links_root = vault_path / links_folder
        if not links_root.exists():
            ui.print_error(f"Links folder does not exist: {links_root}")
            raise typer.Exit(1)

        subdirs = sorted([p for p in links_root.rglob("*") if p.is_dir()])
        if subdirs:
            console.print(f"\n[bold {C_PRIMARY}]Links folder[/bold {C_PRIMARY}]  [dim]{links_folder}/[/dim]\n")
            console.print(f"  [dim] 0.[/dim]  [white]{links_folder}/[/white]  [dim](root)[/dim]")
            for i, d in enumerate(subdirs, 1):
                rel = d.relative_to(links_root)
                console.print(f"  [dim]{i:2}.[/dim]  [white]{rel}/[/white]")
            console.print()
            pick = Prompt.ask("Create in folder #", default="0").strip()
            try:
                idx = int(pick)
                current = subdirs[idx - 1] if idx > 0 else links_root
            except (ValueError, IndexError):
                current = links_root
        else:
            current = links_root
    else:
        current = _cwd(vault_path)

    if not name:
        rel = current.relative_to(vault_path)
        console.print(f"\n[dim]{rel}/[/dim]\n")
        name = Prompt.ask("[orange1]Note name[/orange1]").strip()
        if not name:
            raise typer.Exit(0)

    target = current / f"{name}.md"
    if target.exists():
        ui.print_error(f"Note already exists: {target}")
        raise typer.Exit(1)

    extra: dict = {}
    if link:
        tags_input = Prompt.ask("[dim]Tags (comma-separated, or Enter to skip)[/dim]", default="").strip()
        if tags_input:
            extra["tags"] = [t.strip() for t in tags_input.split(",") if t.strip()]

    note_path = vlt.create_note(current, name, body="", links=[], frontmatter_extra=extra)
    ui.print_success(f"Created: {note_path}")

    open_after = Confirm.ask("Open in editor?", default=False)
    if open_after:
        editor_cfg = config.get("editor", "")
        start = ed.body_start_line(note_path)
        ed.open_in_editor(note_path, editor_override=editor_cfg, start_line=start)
        _suggest_links(vault_path, note_path)


@app.command("edit", rich_help_panel="Notes")
def cmd_edit(
    name: Annotated[Optional[str], typer.Argument(help="Note name (fuzzy matched). Omit to pick from current folder.")] = None,
    tui: Annotated[bool, typer.Option("--tui", help="Force built-in TUI editor")] = False,
) -> None:
    """Edit a note in $EDITOR or the built-in TUI editor.  [e]"""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    current = _cwd(vault_path)

    if not name:
        notes = sorted([p for p in current.iterdir() if p.is_file() and p.suffix == ".md"])
        if not notes:
            ui.print_error("No notes in current folder.")
            raise typer.Exit(1)
        console.print(f"\n{_cwd_label(vault_path)}\n")
        for i, n in enumerate(notes):
            console.print(f"  [dim]{i:2}.[/dim]  [white]{n.stem}[/white]")
        console.print()
        choice = Prompt.ask("Edit #", default="").strip()
        if not choice:
            raise typer.Exit(0)
        try:
            matched = notes[int(choice)]
        except (ValueError, IndexError):
            ui.print_error("Invalid choice.")
            raise typer.Exit(1)
    else:
        matched = vlt.fuzzy_match(vault_path, name)
        if matched is None:
            ui.print_error(f"No note found matching: {name}")
            raise typer.Exit(1)
        if matched.stem.lower() != name.lower():
            confirmed = Confirm.ask(f"Open [orange1]{matched.stem}[/orange1]?", default=True)
            if not confirmed:
                raise typer.Exit(0)

    if tui:
        ed.open_in_tui(matched)
    else:
        editor_cfg = config.get("editor", "")
        start = ed.body_start_line(matched)
        ed.open_in_editor(matched, editor_override=editor_cfg, start_line=start)

    _suggest_links(vault_path, matched)


def _suggest_links(vault_path: Path, note_path: Path) -> None:
    """After editing, suggest highly-linked hub notes to wikilink into this note."""
    note = vlt.parse_note(note_path)
    existing_links = {lnk.lower() for lnk in note["links"]}
    note_name_lower = note_path.stem.lower()

    notes_paths = vlt.list_notes(vault_path)
    all_notes = [vlt.parse_note(p) for p in notes_paths]
    graph = gph.build_graph(all_notes)

    candidates = sorted(
        (
            n for n in all_notes
            if n["name"].lower() != note_name_lower
            and n["name"].lower() not in existing_links
        ),
        key=lambda n: graph.in_degree(n["name"].lower()),
        reverse=True,
    )

    results = [n for n in candidates if graph.in_degree(n["name"].lower()) > 0][:7]
    if not results:
        return

    console.print(f"\n[bold {C_PRIMARY}]Suggested links[/bold {C_PRIMARY}] [dim](most linked notes)[/dim]")
    for i, r in enumerate(results, 1):
        inbound = graph.in_degree(r["name"].lower())
        console.print(f"  [dim]{i}.[/dim]  [white]{r['name']}[/white]  [dim]←{inbound}[/dim]")
    console.print()

    choice = Prompt.ask(
        r'[dim]Add links (e.g.[/dim] [white]1 3 "School" "Work"[/white][dim]), \[l] for links folder, or Enter to skip[/dim]',
        default="",
    ).strip()
    if not choice:
        return

    if choice.lower() == "l":
        config = cfg.load_config()
        links_folder = config.get("links_folder", "")
        if not links_folder:
            ui.print_error("No links folder set. Run: lava config set --link-folder")
            return
        links_dir = vault_path / links_folder
        if not links_dir.exists():
            ui.print_error(f"Links folder does not exist: {links_dir}")
            return

        def _collect_links(directory: Path) -> list[tuple[Path, int]]:
            """Return (note_path, depth) tuples recursively, folders first at each level."""
            collected: list[tuple[Path, int]] = []
            depth = len(directory.relative_to(links_dir).parts)
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            for p in entries:
                if p.is_dir():
                    collected.extend(_collect_links(p))
                elif p.is_file() and p.suffix == ".md":
                    collected.append((p, depth))
            return collected

        all_link_notes = _collect_links(links_dir)
        if not all_link_notes:
            console.print("[dim]No notes in links folder.[/dim]")
            return

        rel_root = links_dir.relative_to(vault_path)
        console.print(f"\n[bold {C_PRIMARY}]Links[/bold {C_PRIMARY}]  [dim]{rel_root}/[/dim]\n")

        current_section: Path | None = None
        numbered: list[Path] = []
        for note_path, depth in all_link_notes:
            section = note_path.parent
            if section != current_section:
                current_section = section
                rel_section = section.relative_to(vault_path)
                console.print(f"  [dim]{rel_section}/[/dim]")
            inbound = graph.in_degree(note_path.stem.lower()) if graph.has_node(note_path.stem.lower()) else 0
            i = len(numbered) + 1
            indent = "    " * depth
            console.print(f"  [dim]{i:2}.[/dim]  {indent}[white]{note_path.stem}[/white]  [dim]←{inbound}[/dim]")
            numbered.append(note_path)
        console.print()

        pick = Prompt.ask(
            r'[dim]Pick note numbers (e.g.[/dim] [white]1 3[/white][dim]) or Enter to skip[/dim]',
            default="",
        ).strip()
        if not pick:
            return

        import re as _re2
        picked_notes = []
        for tok in _re2.findall(r'\S+', pick):
            try:
                idx = int(tok) - 1
                if 0 <= idx < len(numbered):
                    picked_notes.append(numbered[idx])
            except ValueError:
                pass

        if picked_notes:
            results = [{"name": p.stem} for p in picked_notes]
            choice = " ".join(str(i + 1) for i in range(len(results)))

    import re as _re
    tokens = _re.findall(r'"[^"]*"|\S+', choice)

    selected: list[str] = []
    for token in tokens:
        try:
            idx = int(token) - 1
            if 0 <= idx < len(results):
                selected.append(results[idx]["name"])
        except ValueError:
            note_name = token.strip('"').strip("'")
            if not note_name:
                continue
            # Case-insensitive stem match against all_notes
            name_match = next(
                (n["name"] for n in all_notes if n["name"].lower() == note_name.lower()),
                None,
            )
            if name_match is not None:
                selected.append(name_match)
            else:
                console.print(f'[gold1]Warning:[/gold1] "{note_name}" doesn\'t exist — creating it.')
                vlt.create_note(vault_path, note_name, body="", links=[])
                selected.append(note_name)

    if not selected:
        return

    text = note_path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + "".join(f"[[{name}]]\n" for name in selected)
    note_path.write_text(text, encoding="utf-8")
    ui.print_success(f"Added: {', '.join(f'[[{n}]]' for n in selected)}")


@app.command("delete", rich_help_panel="Notes")
def cmd_delete(
    name: Annotated[Optional[str], typer.Argument(help="Note or folder name. Omit to pick from list.")] = None,
    hard: Annotated[bool, typer.Option("--hard", help="Permanently delete instead of archiving")] = False,
) -> None:
    """Delete a note or folder (moves to _archive/ by default).  [d]"""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    current = _cwd(vault_path)

    if not name:
        name = _pick_delete_target(current, vault_path)
        if name is None:
            raise typer.Exit(0)

    folder_target = current / name
    if not folder_target.exists():
        subdirs = [p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "_archive"]
        matches = [d for d in subdirs if name.lower() in d.name.lower()]
        if len(matches) == 1:
            folder_target = matches[0]

    if folder_target.exists() and folder_target.is_dir():
        note_count = sum(1 for _ in folder_target.rglob("*.md"))
        confirmed = Confirm.ask(
            f"Delete folder [orange1]{folder_target.name}/[/orange1] ({note_count} notes)?",
            default=False,
        )
        if not confirmed:
            raise typer.Exit(0)
        if hard:
            shutil.rmtree(str(folder_target))
            ui.print_success(f"Permanently deleted folder: {folder_target.name}/")
        else:
            archive_dir = vault_path / "_archive"
            archive_dir.mkdir(exist_ok=True)
            dest = archive_dir / folder_target.name
            if dest.exists():
                dest = archive_dir / f"{folder_target.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            shutil.move(str(folder_target), str(dest))
            ui.print_success(f"Archived folder to: _archive/{dest.name}/")
        return

    matched = vlt.fuzzy_match(vault_path, name)
    if matched is None:
        ui.print_error(f"No note or folder found matching: {name}")
        raise typer.Exit(1)

    confirmed = Confirm.ask(f"Delete [orange1]{matched.stem}[/orange1]?", default=False)
    if not confirmed:
        raise typer.Exit(0)

    notes_paths = vlt.list_notes(vault_path)
    notes = [vlt.parse_note(p) for p in notes_paths]
    graph = gph.build_graph(notes)
    parents = gph.get_parents(graph, matched.stem)

    if parents:
        console.print(
            f"[gold1]Warning:[/gold1] {len(parents)} note(s) link to [orange1]{matched.stem}[/orange1]:"
        )
        for p in parents[:10]:
            console.print(f"  • {p}")
        if not Confirm.ask("Delete anyway?", default=False):
            raise typer.Exit(0)

    if hard:
        matched.unlink()
        ui.print_success(f"Permanently deleted: {matched.name}")
    else:
        archive_dir = vault_path / "_archive"
        archive_dir.mkdir(exist_ok=True)
        dest = archive_dir / matched.name
        if dest.exists():
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            dest = archive_dir / f"{matched.stem}_{timestamp}{matched.suffix}"
        shutil.move(str(matched), str(dest))
        ui.print_success(f"Archived to: _archive/{dest.name}")


def _pick_delete_target(current: Path, vault_path: Path) -> str | None:
    """Show numbered list of current folder contents and return the chosen name."""
    subdirs = sorted([p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "_archive"])
    notes = sorted([p for p in current.iterdir() if p.is_file() and p.suffix == ".md"])

    if not subdirs and not notes:
        console.print("[dim]Nothing to delete here.[/dim]")
        return None

    items: list[tuple[str, str]] = []  # (display, name)
    console.print(f"\n{_cwd_label(vault_path)}\n")
    for d in subdirs:
        note_count = sum(1 for _ in d.rglob("*.md"))
        idx = len(items)
        console.print(f"  [dim]{idx:2}.[/dim]  [orange1]{d.name}/[/orange1] [dim]{note_count}n[/dim]")
        items.append((f"{d.name}/", d.name))
    for n in notes:
        idx = len(items)
        console.print(f"  [dim]{idx:2}.[/dim]  [white]{n.stem}[/white]")
        items.append((n.stem, n.stem))

    console.print()
    choice = Prompt.ask("Delete #", default="").strip()
    if not choice:
        return None
    try:
        idx = int(choice)
        return items[idx][1]
    except (ValueError, IndexError):
        ui.print_error("Invalid choice.")
        return None


@app.command("move", rich_help_panel="Notes")
def cmd_move(
    name: Annotated[Optional[str], typer.Argument(help="Note to move/rename (fuzzy matched). Omit to pick.")] = None,
    destination: Annotated[Optional[str], typer.Argument(help="New name or relative path. Omit for interactive picker.")] = None,
) -> None:
    """Rename or move a note, updating all wikilinks that point to it.  [m]"""
    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    current = _cwd(vault_path)

    if name is None:
        notes = sorted([p for p in current.iterdir() if p.is_file() and p.suffix == ".md"])
        if not notes:
            ui.print_error("No notes in current folder.")
            raise typer.Exit(1)
        console.print(f"\n{_cwd_label(vault_path)}\n")
        for i, n in enumerate(notes):
            console.print(f"  [dim]{i:2}.[/dim]  [white]{n.stem}[/white]")
        console.print()
        choice = Prompt.ask("Move #", default="").strip()
        if not choice:
            raise typer.Exit(0)
        try:
            matched = notes[int(choice)]
        except (ValueError, IndexError):
            ui.print_error("Invalid choice.")
            raise typer.Exit(1)
    else:
        matched = vlt.fuzzy_match(vault_path, name)
        if matched is None:
            ui.print_error(f"No note found matching: {name}")
            raise typer.Exit(1)

        if matched.stem.lower() != name.lower():
            confirmed = Confirm.ask(f"Move [orange1]{matched.stem}[/orange1]?", default=True)
            if not confirmed:
                raise typer.Exit(0)

    if destination is None:
        destination = _pick_move_destination(vault_path, matched)
        if destination is None:
            raise typer.Exit(0)

    new_path, updated = vlt.move_note(vault_path, matched, destination)
    ui.print_success(f"Moved: {matched.stem} → {new_path.stem}")
    if updated:
        console.print(f"[dim]Updated wikilinks in {updated} note(s).[/dim]")


@app.command("view", rich_help_panel="Notes")
def cmd_view(
    name: Annotated[Optional[str], typer.Argument(help="Note name, path, or fuzzy match. Omit to pick from current folder.")] = None,
) -> None:
    """Render a note as formatted markdown in the terminal.  [v]"""
    from rich.markdown import Markdown

    config = cfg.load_config()
    try:
        vault_path = vlt.get_vault_path(config)
    except ValueError as e:
        ui.print_error(str(e))
        raise typer.Exit(1)

    current = _cwd(vault_path)

    if not name:
        notes = sorted([p for p in current.iterdir() if p.is_file() and p.suffix == ".md"])
        if not notes:
            ui.print_error("No notes in current folder.")
            raise typer.Exit(1)
        console.print(f"\n{_cwd_label(vault_path)}\n")
        for i, n in enumerate(notes):
            console.print(f"  [dim]{i:2}.[/dim]  [white]{n.stem}[/white]")
        console.print()
        choice = Prompt.ask("View #", default="").strip()
        if not choice:
            raise typer.Exit(0)
        try:
            matched = notes[int(choice)]
        except (ValueError, IndexError):
            ui.print_error("Invalid choice.")
            raise typer.Exit(1)
    elif "/" in name or name.endswith(".md"):
        p = Path(name)
        if p.is_absolute():
            resolved = p
        else:
            resolved = vault_path / name
        if not resolved.exists():
            ui.print_error(f"No file found at: {resolved}")
            raise typer.Exit(1)
        matched = resolved
    else:
        matched = vlt.fuzzy_match(vault_path, name)
        if matched is None:
            ui.print_error(f"No note found matching: {name}")
            raise typer.Exit(1)

    note = vlt.parse_note(matched)
    fm = note["frontmatter"]
    body = note["body"]

    title = fm.get("title", matched.stem)
    date = fm.get("date") or fm.get("created", "")
    tags = fm.get("tags", [])

    header_parts = []
    if date:
        header_parts.append(f"[dim]{date}[/dim]")
    if tags:
        tag_str = "  ".join(f"[orange1]#{t}[/orange1]" for t in tags)
        header_parts.append(tag_str)

    console.print(f"\n[bold white]{title}[/bold white]" + (f"   {'   '.join(header_parts)}" if header_parts else ""))
    console.rule(style="dim")

    console.print(Markdown(body))
