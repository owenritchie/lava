"""BM25 indexing and querying for lava vault search."""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    """Simple lowercase word tokenizer."""
    return re.findall(r"\w+", text.lower())


def _note_to_text(note: dict) -> str:
    """Combine note name, frontmatter title/tags, and body into a single string."""
    parts = [note.get("name", "")]
    fm = note.get("frontmatter", {})
    if fm.get("title"):
        parts.append(str(fm["title"]))
    tags = fm.get("tags", [])
    if isinstance(tags, list):
        parts.extend(str(t) for t in tags)
    parts.append(note.get("body", ""))
    return " ".join(parts)


def build_index(notes: list[dict]) -> BM25Okapi:
    """Build a BM25 index from a list of parsed notes."""
    corpus = [_tokenize(_note_to_text(note)) for note in notes]
    return BM25Okapi(corpus)


def search(
    index: BM25Okapi,
    notes: list[dict],
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Search the index and return top_k notes with their scores."""
    tokens = _tokenize(query)
    if not tokens:
        return []

    scores = index.get_scores(tokens)
    ranked = sorted(
        enumerate(scores), key=lambda x: x[1], reverse=True
    )

    results = []
    for idx, score in ranked[:top_k]:
        if score > 0:
            note = dict(notes[idx])
            note["score"] = round(float(score), 4)
            results.append(note)

    return results


def fuzzy_find(notes: list[dict], query: str) -> dict | None:
    """Find a single best-matching note for a query."""
    if not notes:
        return None

    # Exact name match first
    query_lower = query.lower().strip()
    for note in notes:
        if note.get("name", "").lower() == query_lower:
            return note

    # BM25 ranking
    index = build_index(notes)
    results = search(index, notes, query, top_k=1)
    if results:
        return results[0]

    return None
