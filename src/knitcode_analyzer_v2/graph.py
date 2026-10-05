"""Display-only graph projection. Never adds or changes analysis relations."""

from collections import defaultdict


def graph_data(result, *, runtime=None):
    nodes = {node["id"]: node for node in result["nodes"]}
    files = {node["file"]: node["id"] for node in nodes.values() if node["type"] == "file"}
    groups = defaultdict(list)
    symbol_groups = defaultdict(list)
    edges = list(result["edges"])
    if runtime is not None:
        edges.extend({**edge, "resolution_status": "observed", "expression": f"실행에서 관측 · {edge['count']}회"}
                     for edge in runtime["summary"]["observed_calls"])
    by_id = {e["id"]: e for e in edges}
    for edge in edges:
        if edge["target"] is not None:
            symbol_groups[(edge["source"], edge["target"], edge["type"])].append(edge["id"])
            source, target = files[nodes[edge["source"]]["file"]], files[nodes[edge["target"]]["file"]]
            if edge["type"] != "contains":
                groups[(source, target, edge["type"])].append(edge["id"])
    return {
        "snapshot_id": result["metadata"]["snapshot_id"],
        "nodes": [{key: node.get(key) for key in ("id", "file", "name", "qualified_name", "type", "parent", "range", "docstring")}
                  for node in nodes.values()],
        "edges": edges,
        "symbol_edges": [{"source": source, "target": target, "type": kind, "edge_ids": ids, "count": sum(by_id[i].get("count", 1) for i in ids)}
                         for (source, target, kind), ids in sorted(symbol_groups.items())],
        "file_edges": [{"source": source, "target": target, "type": kind, "edge_ids": ids, "count": sum(by_id[i].get("count", 1) for i in ids)}
                       for (source, target, kind), ids in sorted(groups.items())],
    }
