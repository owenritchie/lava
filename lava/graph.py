"""NetworkX DAG for vault note relationships."""

from __future__ import annotations

import networkx as nx


def build_graph(notes: list[dict]) -> nx.DiGraph:
    """Build a directed graph from parsed notes.

    Nodes are note name stems (lowercase for matching), edges are wikilinks.
    Node attribute 'display' holds the original-case stem.
    """
    graph = nx.DiGraph()

    name_map: dict[str, str] = {}
    for note in notes:
        name = note["name"]
        key = name.lower()
        name_map[key] = name
        graph.add_node(key, display=name, path=str(note["path"]))

    for note in notes:
        src_key = note["name"].lower()
        for link in note.get("links", []):
            link_key = link.lower().strip()
            if link_key and link_key in name_map:
                if src_key != link_key:
                    graph.add_edge(src_key, link_key)
            elif link_key:
                if link_key not in graph:
                    graph.add_node(link_key, display=link, path=None)
                if src_key != link_key:
                    graph.add_edge(src_key, link_key)

    return graph


def _resolve_node(graph: nx.DiGraph, name: str) -> str | None:
    """Return the node key for a name, case-insensitively.

    Strips folder prefixes (e.g. 'projects/meeting-notes') and .md
    extensions before lookup so all of the following resolve identically:
    'meeting-notes', 'projects/meeting-notes', 'meeting-notes.md'.
    """
    from pathlib import Path as _Path
    stem = _Path(name.replace("\\", "/")).stem
    key = stem.lower().strip()
    if key in graph:
        return key
    for node in graph.nodes:
        if key in node.lower():
            return node
    return None


def get_children(graph: nx.DiGraph, name: str) -> list[str]:
    """Return outbound link targets (notes this note links to)."""
    key = _resolve_node(graph, name)
    if key is None:
        return []
    return [graph.nodes[n].get("display", n) for n in graph.successors(key)]


def get_parents(graph: nx.DiGraph, name: str) -> list[str]:
    """Return inbound link sources (notes that link to this note)."""
    key = _resolve_node(graph, name)
    if key is None:
        return []
    return [graph.nodes[n].get("display", n) for n in graph.predecessors(key)]


def get_orphans(graph: nx.DiGraph) -> list[str]:
    """Return notes with no inbound or outbound edges (among real notes with paths)."""
    orphans = []
    for node in graph.nodes:
        node_data = graph.nodes[node]
        if node_data.get("path") is None:
            continue
        if graph.in_degree(node) == 0 and graph.out_degree(node) == 0:
            orphans.append(node_data.get("display", node))
    return orphans


def get_most_linked(graph: nx.DiGraph, n: int = 5) -> list[tuple[str, int]]:
    """Return top-n notes by inbound link count."""
    counts = []
    for node in graph.nodes:
        node_data = graph.nodes[node]
        if node_data.get("path") is None:
            continue
        counts.append((node_data.get("display", node), graph.in_degree(node)))
    counts.sort(key=lambda x: x[1], reverse=True)
    return counts[:n]


def get_subtree(graph: nx.DiGraph, root: str, depth: int) -> nx.DiGraph:
    """Return a subgraph containing all nodes reachable from root within depth."""
    root_key = _resolve_node(graph, root)
    if root_key is None:
        return nx.DiGraph()

    nodes_to_include = {root_key}
    frontier = {root_key}

    for _ in range(depth):
        next_frontier: set[str] = set()
        for node in frontier:
            for child in graph.successors(node):
                if child not in nodes_to_include:
                    nodes_to_include.add(child)
                    next_frontier.add(child)
        frontier = next_frontier
        if not frontier:
            break

    return graph.subgraph(nodes_to_include).copy()


def get_subtree_reversed(graph: nx.DiGraph, root: str, depth: int) -> nx.DiGraph:
    """Return a subgraph containing all nodes reachable via predecessors from root within depth."""
    root_key = _resolve_node(graph, root)
    if root_key is None:
        return nx.DiGraph()

    nodes_to_include = {root_key}
    frontier = {root_key}

    for _ in range(depth):
        next_frontier: set[str] = set()
        for node in frontier:
            for pred in graph.predecessors(node):
                if pred not in nodes_to_include:
                    nodes_to_include.add(pred)
                    next_frontier.add(pred)
        frontier = next_frontier
        if not frontier:
            break

    return graph.subgraph(nodes_to_include).copy()
