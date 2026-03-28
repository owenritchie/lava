"""Vault scanning, note CRUD, frontmatter parsing, and link extraction."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter

LINK_RE = re.compile(r"\[\[([^\[\]|#]+?)(?:[|#][^\[\]]*)?\]\]")


def get_vault_path(config: dict) -> Path:
    """Return the configured vault path, raising if not set."""
    path_str = config.get("vault", {}).get("path", "")
    if not path_str:
        raise ValueError(
            "No vault path configured. Run: lava dir set <path>"
        )
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Vault path does not exist: {path}")
    return path


def list_notes(vault_path: Path) -> list[Path]:
    """Return all .md files recursively, excluding _archive."""
    archive = vault_path / "_archive"
    notes = []
    for p in vault_path.rglob("*.md"):
        try:
            p.relative_to(archive)
            continue
        except ValueError:
            pass
        notes.append(p)
    return sorted(notes)


def parse_note(path: Path) -> dict:
    """Parse a note file and return its frontmatter, body, links, and path."""
    try:
        post = frontmatter.load(str(path))
        body = post.content
        fm = dict(post.metadata)
    except Exception:
        body = path.read_text(encoding="utf-8", errors="replace")
        fm = {}

    links = extract_links(body)
    return {
        "frontmatter": fm,
        "body": body,
        "links": links,
        "path": path,
        "name": path.stem,
    }


def extract_links(body: str) -> list[str]:
    """Extract all [[wikilink]] targets from body text."""
    return [m.group(1).strip() for m in LINK_RE.finditer(body)]


def create_note(
    vault_path: Path,
    name: str,
    body: str = "",
    links: list[str] | None = None,
    frontmatter_extra: dict[str, Any] | None = None,
) -> Path:
    """Create a new .md note in the vault root with YAML frontmatter."""
    if links is None:
        links = []
    if frontmatter_extra is None:
        frontmatter_extra = {}

    fm: dict[str, Any] = {
        "title": name,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "tags": [],
    }
    fm.update(frontmatter_extra)

    full_body = body
    if links:
        if full_body and not full_body.endswith("\n"):
            full_body += "\n"
        full_body += "\n"
        for link in links:
            full_body += f"[[{link}]]\n"

    post = frontmatter.Post(full_body, **fm)
    content = frontmatter.dumps(post)

    note_path = vault_path / f"{name}.md"
    note_path.write_text(content, encoding="utf-8")
    return note_path


def move_note(vault_path: Path, source_path: Path, destination: str) -> tuple[Path, int]:
    """Move/rename a note and rewrite all wikilinks that referenced the old name.

    destination can be:
      - a bare name like "New Name"  → stays in same folder, renamed
      - a relative path like "folder/New Name" → moved into subfolder
    Returns (new_path, num_files_updated).
    """
    old_stem = source_path.stem

    dest = Path(destination)
    if dest.suffix != ".md":
        dest = dest.with_suffix(".md")
    if not dest.parent or dest.parent == Path("."):
        new_path = source_path.parent / dest.name
    else:
        new_path = vault_path / dest
        new_path.parent.mkdir(parents=True, exist_ok=True)

    new_stem = new_path.stem

    try:
        post = frontmatter.load(str(source_path))
        if post.metadata.get("title") == old_stem:
            post.metadata["title"] = new_stem
        source_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    except Exception:
        pass

    source_path.rename(new_path)

    updated = 0
    old_pattern = re.compile(
        r"\[\[" + re.escape(old_stem) + r"(\s*[|#][^\[\]]*)?\]\]",
        re.IGNORECASE,
    )

    def _replace(m: re.Match) -> str:
        suffix = m.group(1) or ""
        return f"[[{new_stem}{suffix}]]"

    old_stem_lower = old_stem.lower()
    for note_path in list_notes(vault_path):
        if note_path == new_path:
            continue
        text = note_path.read_text(encoding="utf-8", errors="replace")
        if old_stem_lower not in text.lower():
            continue
        new_text, count = old_pattern.subn(_replace, text)
        if count:
            note_path.write_text(new_text, encoding="utf-8")
            updated += 1

    return new_path, updated


def list_folders(vault_path: Path) -> list[Path]:
    """Return all subdirectories in the vault, excluding _archive and hidden dirs."""
    folders = []
    for p in sorted(vault_path.rglob("*")):
        if not p.is_dir():
            continue
        parts = p.relative_to(vault_path).parts
        if any(part.startswith(".") or part == "_archive" for part in parts):
            continue
        folders.append(p)
    return folders


def fuzzy_match(vault_path: Path, query: str) -> Path | None:
    """Find the best-matching note for a query using substring then BM25."""
    notes = list_notes(vault_path)
    if not notes:
        return None

    query_lower = query.lower().strip()
    for note in notes:
        if note.stem.lower() == query_lower:
            return note

    candidates = [n for n in notes if query_lower in n.stem.lower()]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return min(candidates, key=lambda p: len(p.stem))

    try:
        from lava.search import build_index, fuzzy_find

        parsed = [parse_note(p) for p in notes]
        result = fuzzy_find(parsed, query)
        if result:
            return result["path"]
    except Exception:
        pass

    return None
