#!/usr/bin/env python3
"""Reproduce PlantUML inputs from the previously validated D2 semantic mappings.

Usage: python3 translate.py SOURCE_MAPPING_DIRECTORY OUTPUT_DIRECTORY
No node, edge, ordering constraint, or layout dummy is inserted by this translator.
"""
import collections
import hashlib
import json
from pathlib import Path
import sys


def value(attributes, key, default=""):
    return (attributes.get(key) or {}).get("value", default)


def escape(text):
    # Entity substitution occurs in label rendering. Literal syntax cannot
    # introduce Creole emphasis, URLs, UML delimiters, preprocessing, or HTML.
    specials = set('"<>~*_[]|#&\\')
    return "".join("\\n" if c == "\n" else f"&#{ord(c)};" if c in specials else c
                   for c in text.replace("\r", "")) or "&#160;"


def styled_label(obj):
    st = obj["source_attributes"].get("style", {})
    labels = []
    # PlantUML resets inline HTML formatting at each line break. Balance the
    # tags on each line so closing tags never become visible text.
    for text in obj["translated_label"].split("\n"):
        label = escape(text)
        if value(st, "bold") == "true": label = "<b>" + label + "</b>"
        elif value(st, "bold") == "false": label = "<plain>" + label + "</plain>"
        if value(st, "italic") == "true": label = "<i>" + label + "</i>"
        if value(st, "underline") == "true": label = "<u>" + label + "</u>"
        if value(st, "fontColor"): label = "<color:" + value(st, "fontColor") + ">" + label + "</color>"
        if value(st, "fontSize"): label = "<size:" + value(st, "fontSize") + ">" + label + "</size>"
        labels.append(label)
    return "\\n".join(labels)


def shape_style(obj):
    st = obj["source_attributes"].get("style", {})
    parts = []
    fill, stroke = value(st, "fill"), value(st, "stroke")
    if obj["source_shape"] == "text" or value(st, "opacity") == "0":
        fill = stroke = "transparent"
    if value(st, "strokeWidth") == "0": stroke = "transparent"
    if fill: parts.append("back:" + fill.lstrip("#"))
    if stroke: parts.append("line:" + stroke.lstrip("#"))
    if value(st, "strokeDash") not in ("", "0"): parts.append("line.dashed")
    if value(st, "fontColor"): parts.append("text:" + value(st, "fontColor").lstrip("#"))
    return " #" + ";".join(parts) if parts else ""


def translate(source, destination):
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    summaries = []
    for path in sorted(source.glob("*.mapping.json")):
        data = json.loads(path.read_text())
        objects = data["objects"]
        by_id = {o["d2_id"]: o for o in objects}
        children = collections.defaultdict(list)
        for obj in objects: children[obj["parent_d2_id"]].append(obj)
        limitation_counts = collections.Counter()
        lines = ["@startuml", "' Generated from the compiled D2 semantic mapping; see TRANSLATION.md.",
                 "' Graphviz is PlantUML's default deployment-diagram layout; GRAPHVIZ_DOT pins it.",
                 "skinparam shadowing false", "skinparam defaultTextAlignment center"]
        direction = value(data["root_attributes"], "direction")
        if direction == "right": lines.append("left to right direction")
        elif direction in ("", "down"): lines.append("top to bottom direction")
        else: raise ValueError("Unimplemented root direction: " + direction)
        mapping_objects = []

        def emit(obj, depth):
            ident = obj["mermaid_id"]
            attr, st = obj["source_attributes"], obj["source_attributes"].get("style", {})
            group = obj["kind"] == "group"
            shape = {"cylinder": "database", "queue": "queue", "person": "person"}.get(obj["source_shape"], "rectangle")
            differences = []
            for field in ("gridRows", "gridColumns", "gridGap", "verticalGap", "horizontalGap"):
                if attr.get(field): differences.append(field + " layout omitted")
            if value(attr, "direction"): differences.append("per-container direction omitted")
            if attr.get("near_key"): differences.append("near positioning omitted")
            for field in ("width", "height", "top", "left", "labelPosition", "iconPosition"):
                if attr.get(field): differences.append(field + " placement/sizing omitted")
            retained = {"fill", "stroke", "fontSize", "fontColor", "bold", "italic", "underline", "strokeDash"}
            for field in st:
                if field == "opacity":
                    if value(st, field) != "0": differences.append("partial opacity omitted")
                elif field == "strokeWidth":
                    if value(st, field) != "0": differences.append("stroke width omitted")
                elif field not in retained: differences.append(field + " style omitted")
            if value(st, "strokeDash"): differences.append("dash pattern approximated by dashed line")
            if obj["source_shape"] == "square": differences.append("square aspect ratio not forced")
            if obj["source_shape"] == "person": differences.append("person silhouette uses PlantUML person")
            if obj["source_shape"] == "queue": differences.append("queue uses PlantUML queue")
            if attr.get("language") == "markdown": differences.append("markdown formatted as validated plain multiline text")
            if attr.get("link") or attr.get("tooltip"): differences.append("link/tooltip metadata retained only in manifest")
            label = styled_label(obj)
            line = "  " * depth + f'{shape} "{label}" as {ident}' + shape_style(obj)
            lines.append(line + (" {" if group else ""))
            if group:
                for child in children[obj["d2_id"]]: emit(child, depth + 1)
                lines.append("  " * depth + "}")
            mapped = {k: v for k, v in obj.items() if not k.startswith("mermaid") and k != "differences"}
            mapped.update(plantuml_id=ident, parent_plantuml_id=obj["parent_mermaid_id"],
                          plantuml_shape=shape, encoded_label=label, differences=differences)
            mapping_objects.append(mapped)
            limitation_counts.update(differences)

        for obj in children[""]: emit(obj, 0)
        assert len(mapping_objects) == len(objects)
        lines.append("' One link per D2 edge, in compiler order; no synthetic layout links.")
        mapped_edges = []
        for edge in data["edges"]:
            st = edge["source_attributes"].get("style", {})
            params = []
            if value(st, "stroke"): params.append("#" + value(st, "stroke").lstrip("#"))
            if value(st, "strokeDash") not in ("", "0"): params.append("dashed")
            if value(st, "strokeWidth"): params.append("thickness=" + value(st, "strokeWidth"))
            arrow = ("<" if edge["source_visible_arrow"] else "") + "-"
            arrow += ("[" + ",".join(params) + "]") if params else ""
            arrow += "-" + (">" if edge["target_visible_arrow"] else "")
            label = styled_label(edge) if edge["translated_label"] else ""
            lines.append(f'{edge["source_mermaid_id"]} {arrow} {edge["target_mermaid_id"]}' + (" : " + label if label else ""))
            mapped = {k: v for k, v in edge.items() if "mermaid" not in k}
            mapped.update(source_plantuml_id=edge["source_mermaid_id"], target_plantuml_id=edge["target_mermaid_id"],
                          plantuml_arrow=arrow, encoded_label=label)
            mapped_edges.append(mapped)
        lines.append("@enduml")
        text = "\n".join(lines) + "\n"
        output = destination / (data["fixture"] + ".puml")
        output.write_text(text)
        result = {"fixture":data["fixture"], "counts":data["counts"], "source_sha256":data["source_sha256"],
                  "semantic_mapping_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                  "plantuml_sha256":hashlib.sha256(text.encode()).hexdigest(), "layout":"Graphviz dot (PlantUML default)",
                  "root_attributes":data["root_attributes"], "source_config":data["source_config"],
                  "limitations":dict(limitation_counts), "objects":mapping_objects, "edges":mapped_edges,
                  "synthetic_objects":0, "synthetic_edges":0}
        (destination / (data["fixture"] + ".mapping.json")).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        summaries.append({"fixture":data["fixture"], **data["counts"], "limitations":dict(limitation_counts)})
    (destination / "corpus.json").write_text(json.dumps(summaries, indent=2) + "\n")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    translate(*sys.argv[1:])
