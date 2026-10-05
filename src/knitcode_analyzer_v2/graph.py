"""Display-only graph projection. Never adds or changes analysis relations."""

from collections import defaultdict


def graph_data(result):
    nodes = {node["id"]: node for node in result["nodes"]}
    files = {node["file"]: node["id"] for node in nodes.values() if node["type"] == "file"}
    groups = defaultdict(list)
    symbol_groups = defaultdict(list)
    for edge in result["edges"]:
        if edge["target"] is not None:
            symbol_groups[(edge["source"], edge["target"], edge["type"])].append(edge["id"])
            source, target = files[nodes[edge["source"]]["file"]], files[nodes[edge["target"]]["file"]]
            if edge["type"] != "contains":
                groups[(source, target, edge["type"])].append(edge["id"])
    return {
        "snapshot_id": result["metadata"]["snapshot_id"],
        "nodes": [{key: node.get(key) for key in ("id", "file", "name", "qualified_name", "type", "parent", "range", "docstring")}
                  for node in nodes.values()],
        "edges": result["edges"],
        "symbol_edges": [{"source": source, "target": target, "type": kind, "edge_ids": ids}
                         for (source, target, kind), ids in sorted(symbol_groups.items())],
        "file_edges": [{"source": source, "target": target, "type": kind, "edge_ids": ids}
                       for (source, target, kind), ids in sorted(groups.items())],
    }
