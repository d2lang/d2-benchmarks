#!/usr/bin/env python3
"""Audit DOT through Graphviz's JSON parser/layout and native SVG renderer.

Semantic expectations come from the original audited D2/Mermaid mappings, not
the generated DOT manifests. Runs here are correctness checks, not benchmarks.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import os
import shutil
import xml.etree.ElementTree as ET


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def label_text(encoded):
    # DOT preserves quoted label escape sequences in its JSON output. All
    # source literals are escaped by the translator, so decode only its escapes.
    result = []
    pos = 0
    while pos < len(encoded):
        char = encoded[pos]
        if char == "\\" and pos + 1 < len(encoded):
            pos += 1
            char = {"n": "\n", "r": "\r", "t": "\t"}.get(encoded[pos], encoded[pos])
        result.append(char)
        pos += 1
    return "".join(result)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(source_path, dot_dir, dot, out):
    source = json.loads(source_path.read_text())
    name = source["fixture"]
    dot_path = dot_dir / f"{name}.dot"
    json_path = out / f"{name}.graphviz.json"
    svg_path = out / f"{name}.svg"
    warnings = []
    commands = []
    for fmt, target in [("json", json_path), ("svg", svg_path)]:
        command = [*dot, "-T" + fmt, str(dot_path), "-o", str(target)]
        commands.append(command)
        run = subprocess.run(command, text=True, capture_output=True, timeout=120)
        require(run.returncode == 0, f"{name}: {fmt} failed: {run.stderr}")
        if run.stderr.strip():
            warnings.append(dict(format=fmt, stderr=run.stderr.strip()))
    graph = json.loads(json_path.read_text())
    require(graph["directed"] and not graph["strict"], f"{name}: must retain directed, non-strict multiplicity")
    objects = source["objects"]
    by_id = {obj["d2_id"]: obj for obj in objects}
    groups = {obj["d2_id"] for obj in objects if obj["kind"] == "group"}
    dot_ids = {obj["d2_id"]: ("cluster_" if obj["kind"] == "group" else "node_") + obj["mermaid_id"] for obj in objects}
    endpoint_groups = {edge[key] for edge in source["edges"] for key in ("source_d2_id", "target_d2_id") if edge[key] in groups}
    proxy_ids = {key: "proxy_" + by_id[key]["mermaid_id"] for key in endpoint_groups}
    actual = {obj["name"]: obj for obj in graph["objects"]}
    gvids = {obj["_gvid"]: obj["name"] for obj in graph["objects"]}
    require(set(actual) == set(dot_ids.values()) | set(proxy_ids.values()), f"{name}: extra or missing node/cluster")
    for obj in objects:
        parsed = actual[dot_ids[obj["d2_id"]]]
        require(parsed["d2_id"] == obj["d2_id"], f"{name}: object identity")
        require(parsed["semantic_kind"] == obj["kind"], f"{name}: object kind")
        require(label_text(parsed.get("label", "")) == obj["translated_label"], f"{name}: object label {obj['d2_id']}")

    def is_within(child, ancestor):
        while child:
            if child == ancestor:
                return True
            child = by_id[child]["parent_d2_id"]
        return False

    for group in groups:
        parsed = actual[dot_ids[group]]
        expected_nodes = {dot_ids[obj["d2_id"]] for obj in objects if obj["kind"] == "node" and is_within(obj["d2_id"], group)}
        expected_nodes.update(proxy_ids[key] for key in endpoint_groups if is_within(key, group))
        require({gvids[num] for num in parsed.get("nodes", [])} == expected_nodes, f"{name}: cluster leaf nesting {group}")
        expected_groups = {dot_ids[key] for key in groups if by_id[key]["parent_d2_id"] == group}
        require({gvids[num] for num in parsed.get("subgraphs", [])} == expected_groups, f"{name}: cluster nesting {group}")
    for key, proxy in proxy_ids.items():
        parsed = actual[proxy]
        require(parsed.get("label") == "" and parsed.get("style") == "invis", f"{name}: visible proxy {proxy}")
        require(parsed.get("synthetic_for") == key, f"{name}: proxy identity")
        require(float(parsed["width"]) <= 0.011 and float(parsed["height"]) <= 0.011, f"{name}: proxy dimensions")

    actual_edges = {edge["id"]: edge for edge in graph.get("edges", [])}
    require(len(actual_edges) == len(source["edges"]) == len(graph.get("edges", [])), f"{name}: edge count/multiplicity")
    drawn_arrows = 0
    for edge in source["edges"]:
        parsed = actual_edges[f"edge{edge['index']:03d}"]
        source_id, target_id = edge["source_d2_id"], edge["target_d2_id"]
        require(parsed["d2_id"] == edge["d2_id"], f"{name}: edge identity")
        require(gvids[parsed["tail"]] == proxy_ids.get(source_id, dot_ids[source_id]), f"{name}: edge source")
        require(gvids[parsed["head"]] == proxy_ids.get(target_id, dot_ids[target_id]), f"{name}: edge target")
        require(parsed.get("ltail", "") == (dot_ids[source_id] if source_id in groups else ""), f"{name}: logical source")
        require(parsed.get("lhead", "") == (dot_ids[target_id] if target_id in groups else ""), f"{name}: logical target")
        require(label_text(parsed.get("label", "")) == edge["translated_label"], f"{name}: edge label")
        expected_dir = {(False, False): "none", (False, True): "forward", (True, False): "back", (True, True): "both"}[(edge["source_visible_arrow"], edge["target_visible_arrow"])]
        require(parsed["dir"] == expected_dir, f"{name}: edge direction")
        for end, draw_key, shape_key in [("source", "_tdraw_", "arrowtail"), ("target", "_hdraw_", "arrowhead")]:
            expected = edge[end + "_visible_arrow"]
            require(parsed[shape_key] == ("normal" if expected else "none"), f"{name}: arrow shape")
            require(bool(parsed.get(draw_key)) == expected, f"{name}: rendered arrow {edge['index']} {end}")
            drawn_arrows += int(bool(parsed.get(draw_key)))
        require(bool(parsed.get("_draw_")), f"{name}: edge route not rendered")
        # Check actual routed endpoints, not just lhead/ltail metadata: the
        # endpoint (or arrow tip) must lie on the corresponding cluster border.
        tokens = parsed["pos"].split()
        points = [list(map(float, token.split(","))) for token in tokens if token[0] not in "es"]
        tips = {token[0]: list(map(float, token[2:].split(","))) for token in tokens if token[0] in "es"}
        for logical_attr, end in [("lhead", "e"), ("ltail", "s")]:
            if not parsed.get(logical_attr):
                continue
            x, y = tips.get(end, points[-1 if end == "e" else 0])
            x0, y0, x1, y1 = map(float, actual[parsed[logical_attr]]["bb"].split(","))
            tolerance = 0.1  # JSON positions are rounded to two decimal places.
            on_border = min(abs(x - x0), abs(x - x1), abs(y - y0), abs(y - y1)) <= tolerance
            within_box = x0 - tolerance <= x <= x1 + tolerance and y0 - tolerance <= y <= y1 + tolerance
            require(on_border and within_box, f"{name}: compound endpoint does not reach group border")
    svg = ET.parse(svg_path).getroot()
    svg_groups = {el.get("id"): el for el in svg.iter() if el.tag.endswith("}g") and el.get("id")}
    require(set(actual_edges).issubset(svg_groups), f"{name}: missing SVG edge")
    require(not set(proxy_ids.values()) & set(svg_groups), f"{name}: proxy unexpectedly present in SVG")
    require(set(dot_ids.values()).issubset(svg_groups), f"{name}: missing SVG semantic object")
    rendered_labels = 0
    for ident, expected in [(dot_ids[obj["d2_id"]], obj["translated_label"]) for obj in objects] + [(f"edge{edge['index']:03d}", edge["translated_label"]) for edge in source["edges"]]:
        text_nodes = ["".join(el.itertext()) for el in svg_groups[ident].iter() if el.tag.endswith("}text")]
        expected_lines = [line for line in expected.split("\n") if line]
        # Graphviz converts repeated spaces to nonbreaking spaces in SVG so
        # browser whitespace collapsing cannot shorten their rendered label.
        require([line.replace("\u00a0", " ") for line in text_nodes] == [line.replace("\u00a0", " ") for line in expected_lines], f"{name}: SVG text differs for {ident}: {text_nodes!r} vs {expected_lines!r}")
        rendered_labels += len(expected_lines)
    return dict(fixture=name, status="pass", **source["counts"], synthetic_nodes=len(proxy_ids), synthetic_edges=0, enabled_arrowhead_geometries=drawn_arrows, painted_arrowheads=sum(int(e["source_visible_arrow"]) + int(e["target_visible_arrow"]) for e in source["edges"] if (e["source_attributes"].get("style", {}).get("stroke") or {}).get("value") != "transparent"), rendered_text_lines=rendered_labels, checks=["exact semantic object and edge identities", "exact edge multiplicity and endpoint direction", "all cluster descendants and leaf nesting", "all plaintext object and edge labels in parsed JSON and rendered SVG", "all visible and suppressed arrowheads in drawing operations", "compound edges clipped to true semantic groups", "small invisible proxies have no rendered SVG elements", "every semantic object and edge has an SVG element"], warnings=warnings, commands=commands, source_mapping_sha256=digest(source_path), dot_sha256=digest(dot_path), json_sha256=digest(json_path), svg_sha256=digest(svg_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dot", type=str, default="dot")
    parser.add_argument("--toolchain", type=Path, help="Use graphviz-dot argv/env from this configured toolchain")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    dot = [args.dot]
    if args.toolchain:
        configured = json.loads(args.toolchain.read_text())["tools"]["graphviz-dot"]
        dot = configured["argv"]
        os.environ.update(configured.get("env", {}))
    results = []
    for source in sorted(args.source.glob("*.mapping.json")):
        result = validate(source, args.input, dot, args.output)
        results.append(result)
        print(result["fixture"], result["status"], flush=True)
    totals = {key: sum(row[key] for row in results) for key in ("objects", "leaf_nodes", "groups", "edges", "synthetic_nodes", "synthetic_edges", "enabled_arrowhead_geometries", "painted_arrowheads", "rendered_text_lines")}
    version = subprocess.run([*dot, "-V"], text=True, capture_output=True, check=True)
    report = dict(status="pass", fixtures=len(results), graphviz_version=(version.stdout + version.stderr).strip(), totals=totals, cases=results)
    (args.output / "validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
