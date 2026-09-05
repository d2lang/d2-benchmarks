#!/usr/bin/env python3
"""Translate the benchmark's audited semantic mappings into reproducible DOT.

python3 scripts/translations/graphviz.py --source corpus/semantic --output /tmp/graphviz-inputs
Only invisible endpoint representatives are synthetic. Every semantic edge is
emitted once, in compiler order, without changing its source/target direction.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def value(attrs, key, default=""):
    return (attrs.get(key) or {}).get("value", default)


def quoted(text):
    return json.dumps(str(text), ensure_ascii=False)


def attrs_text(attrs):
    return ", ".join(f"{key}={quoted(val)}" for key, val in attrs.items())


def style(attrs, kind):
    original = attrs.get("style", {})
    result = {}
    styles = []
    for source, target in {"stroke": "color", "fill": "fillcolor", "strokeWidth": "penwidth", "fontSize": "fontsize", "fontColor": "fontcolor"}.items():
        val = value(original, source)
        if val:
            result[target] = val
    if kind != "edge" and "fillcolor" in result:
        styles.append("filled")
    if value(original, "strokeDash") not in ("", "0"):
        styles.append("dashed")
    if kind != "edge" and value(original, "borderRadius") not in ("", "0"):
        styles.append("rounded")
    if value(original, "font") == "mono":
        result["fontname"] = "Courier"
    elif value(original, "bold") == "true":
        result["fontname"] = "Helvetica-Bold"
    if value(original, "opacity") == "0":
        result.update(color="transparent", fillcolor="transparent", fontcolor="transparent")
    elif value(original, "opacity"):
        alpha = f"{round(255 * float(value(original, 'opacity'))):02x}"
        for key in ("color", "fillcolor", "fontcolor"):
            color = result.get(key)
            if color and len(color) == 7 and color.startswith("#"):
                result[key] = color + alpha
    if styles:
        result["style"] = ",".join(styles)
    return result


def translate(source_path, output):
    source = json.loads(source_path.read_text())
    name = source["fixture"]
    objects = source["objects"]
    by_id = {obj["d2_id"]: obj for obj in objects}
    children = collections.defaultdict(list)
    for obj in sorted(objects, key=lambda obj: obj["mermaid_id"]):
        children[obj["parent_d2_id"]].append(obj)
    groups = {obj["d2_id"] for obj in objects if obj["kind"] == "group"}
    endpoint_groups = {
        edge[key] for edge in source["edges"]
        for key in ("source_d2_id", "target_d2_id") if edge[key] in groups
    }
    ids = {obj["d2_id"]: ("cluster_" if obj["kind"] == "group" else "node_") + obj["mermaid_id"] for obj in objects}
    proxy_ids = {key: "proxy_" + by_id[key]["mermaid_id"] for key in sorted(endpoint_groups)}
    root_attrs = source["root_attributes"]
    direction = {"up": "BT", "down": "TB", "left": "RL", "right": "LR"}.get(value(root_attrs, "direction"), "TB")
    if not value(root_attrs, "direction") and value(root_attrs, "gridRows") == "1":
        direction = "LR"
    graphattrs = dict(compound="true", rankdir=direction, bgcolor="white", fontname="Helvetica", fontsize="14", pad="0.25")
    if value(root_attrs, "label"):
        graphattrs["label"] = value(root_attrs, "label")
    lines = [
        "// Generated from the audited D2 semantic mapping. See TRANSLATION.md.",
        "digraph diagram {",
        "  graph [" + attrs_text(graphattrs) + "];",
        '  node [shape="box", fontname="Helvetica", fontsize="14", color="#333333", margin="0.12,0.08"];',
        '  edge [fontname="Helvetica", fontsize="14", color="#333333"];',
    ]
    manifest_objects = []
    limitations = collections.Counter()
    retained_styles = {"stroke", "fill", "strokeWidth", "fontSize", "fontColor", "borderRadius", "strokeDash", "bold", "font", "opacity"}

    def emit(obj, depth):
        ident = ids[obj["d2_id"]]
        kind = obj["kind"]
        source_attrs = obj["source_attributes"]
        shape = obj["source_shape"]
        indent = "  " * depth
        attrs = {"id": ident, "label": obj["translated_label"], "d2_id": obj["d2_id"], "semantic_kind": kind}
        attrs.update(style(source_attrs, kind))
        diffs = []
        if kind == "group":
            attrs.update(labelloc="t", labeljust="l", margin="12")
            lines.append(indent + "subgraph " + ident + " {")
            lines.append(indent + "  graph [" + attrs_text(attrs) + "];")
            if obj["d2_id"] in proxy_ids:
                proxy = proxy_ids[obj["d2_id"]]
                proxy_attrs = dict(id=proxy, shape="point", label="", width="0.01", height="0.01", fixedsize="true", style="invis", synthetic_for=obj["d2_id"])
                lines.append(indent + "  " + proxy + " [" + attrs_text(proxy_attrs) + "];")
                diffs.append("invisible endpoint representative inside cluster")
            for child in children[obj["d2_id"]]:
                emit(child, depth + 1)
            lines.append(indent + "}")
            if shape != "rectangle":
                diffs.append("container shape approximated by rectangular cluster")
            if value(source_attrs, "direction"):
                diffs.append("per-container direction omitted; dot uses one global rank direction")
        else:
            attrs["shape"] = {"cylinder": "cylinder", "queue": "cylinder", "person": "circle", "text": "plaintext"}.get(shape, "box")
            if shape == "text":
                attrs.update(color="transparent", fillcolor="transparent")
                attrs.pop("style", None)
            if shape == "person":
                diffs.append("person silhouette approximated by labeled circle")
            if shape == "queue":
                diffs.append("queue approximated by vertical cylinder")
            if shape == "square":
                diffs.append("square aspect ratio not forced")
            lines.append(indent + ident + " [" + attrs_text(attrs) + "];")
        for key in ("gridRows", "gridColumns", "gridGap", "verticalGap", "horizontalGap"):
            if source_attrs.get(key):
                diffs.append("grid layout constraint omitted")
                break
        if source_attrs.get("near_key"):
            diffs.append("near positioning omitted")
        for key in ("width", "height", "top", "left", "labelPosition", "iconPosition"):
            if source_attrs.get(key):
                diffs.append(f"{key} placement/sizing omitted")
        for key in source_attrs.get("style", {}):
            if key not in retained_styles:
                diffs.append(f"{key} style omitted")
        if source_attrs.get("language") == "markdown":
            diffs.append("markdown uses the same plain multiline text as Mermaid")
        if source_attrs.get("link") or source_attrs.get("tooltip"):
            diffs.append("link/tooltip metadata retained only in source mapping")
        if value(source_attrs.get("style", {}), "borderRadius"):
            diffs.append("numeric corner radius approximated by Graphviz rounded style")
        if value(source_attrs.get("style", {}), "opacity") not in ("", "0", "1"):
            diffs.append("opacity applied to explicit hex colors only")
        limitations.update(diffs)
        manifest_objects.append(dict(d2_id=obj["d2_id"], dot_id=ident, parent_d2_id=obj["parent_d2_id"], parent_dot_id=ids.get(obj["parent_d2_id"]), kind=kind, label=obj["translated_label"], source_shape=shape, dot_shape="cluster" if kind == "group" else attrs["shape"], differences=diffs))

    for obj in children[""]:
        emit(obj, 1)
    manifest_edges = []
    lines.append("  // Exactly one DOT edge per compiled D2 edge, preserving order and multiplicity.")
    for edge in source["edges"]:
        source_id, target_id = edge["source_d2_id"], edge["target_d2_id"]
        actual_source = proxy_ids.get(source_id, ids[source_id])
        actual_target = proxy_ids.get(target_id, ids[target_id])
        ident = f"edge{edge['index']:03d}"
        source_arrow, target_arrow = edge["source_visible_arrow"], edge["target_visible_arrow"]
        attrs = dict(id=ident, d2_id=edge["d2_id"], label=edge["translated_label"], dir={(False, False): "none", (False, True): "forward", (True, False): "back", (True, True): "both"}[(source_arrow, target_arrow)], arrowtail="normal" if source_arrow else "none", arrowhead="normal" if target_arrow else "none")
        attrs.update(style(edge["source_attributes"], "edge"))
        if source_id in groups:
            attrs["ltail"] = ids[source_id]
        if target_id in groups:
            attrs["lhead"] = ids[target_id]
        lines.append(f"  {actual_source} -> {actual_target} [" + attrs_text(attrs) + "];")
        diffs = [f"edge {key} style omitted" for key in edge["source_attributes"].get("style", {}) if key not in retained_styles]
        if edge["source_attributes"].get("language") == "markdown":
            diffs.append("edge markdown uses the same plain multiline text as Mermaid")
        limitations.update(diffs)
        manifest_edges.append(dict(index=edge["index"], dot_id=ident, d2_id=edge["d2_id"], source_d2_id=source_id, target_d2_id=target_id, actual_source=actual_source, actual_target=actual_target, ltail=attrs.get("ltail"), lhead=attrs.get("lhead"), label=edge["translated_label"], source_visible_arrow=source_arrow, target_visible_arrow=target_arrow, differences=diffs))
    lines.append("}")
    dot_text = "\n".join(lines) + "\n"
    (output / f"{name}.dot").write_text(dot_text)
    manifest = dict(fixture=name, source_mapping_file=source_path.name, source_mapping_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(), source_d2_sha256=source["source_sha256"], dot_sha256=hashlib.sha256(dot_text.encode()).hexdigest(), counts=source["counts"], rankdir=direction, objects=manifest_objects, edges=manifest_edges, synthetic_nodes=[dict(dot_id=proxy_ids[key], represents_d2_group=key, parent_dot_id=ids[key], visible=False, role="cluster endpoint representative") for key in sorted(proxy_ids)], synthetic_edges=0, limitations=dict(limitations))
    (output / f"{name}.mapping.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return dict(fixture=name, **source["counts"], synthetic_nodes=len(proxy_ids), synthetic_edges=0, group_endpoint_edges=sum(bool(e["lhead"] or e["ltail"]) for e in manifest_edges), dot_sha256=manifest["dot_sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = [translate(path, args.output) for path in sorted(args.source.glob("*.mapping.json"))]
    if len(summary) != 10:
        raise SystemExit(f"Expected 10 input mappings, found {len(summary)}")
    (args.output / "corpus.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
