#!/usr/bin/env python3
"""Translate D2 compiler JSON, preserving each semantic object/group/edge.

Run export.go from the D2 module first, then:
  python3 translate.py GRAPH_DIR D2_FIXTURE_DIR OUTPUT_INPUT_DIR
No synthetic layout nodes or edges are inserted.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

graph_dir, fixture_dir, output_dir = map(Path, sys.argv[1:])
output_dir.mkdir(parents=True, exist_ok=True)

def value(obj, field, default=""):
    return (obj.get(field) or {}).get("value", default)

def plaintext(label, language):
    if language != "markdown":
        return label
    label = re.sub(r"(?m)^#{1,6}\s+", "", label)
    label = re.sub(r"\*\*(.*?)\*\*", r"\1", label)
    label = re.sub(r"`([^`]+)`", r"\1", label)
    label = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", label)
    return label

def escaped(label):
    # Mermaid entity codes prevent labels being parsed as syntax or HTML.
    label = label.replace("#", "#35;").replace("&", "#38;")
    label = label.replace('"', "#quot;").replace("<", "#60;").replace(">", "#62;").replace("|", "#124;")
    label = label.replace("\r", "").replace("\n", "<br/>")
    return label if label else "#160;"

def layout_dir(attr, inherited="TB"):
    explicit = value(attr, "direction")
    if explicit:
        return {"up":"BT", "down":"TB", "left":"RL", "right":"LR"}[explicit]
    rows, cols = value(attr, "gridRows"), value(attr, "gridColumns")
    if cols == "1": return "TB"
    if rows == "1": return "LR"
    return inherited

def css(attr, shape, edge=False, group=False):
    st = attr.get("style", {})
    pairs = []
    mapping = {"fill":"fill", "stroke":"stroke", "strokeWidth":"stroke-width", "opacity":"opacity", "fontColor":"color", "fontSize":"font-size"}
    for d2, mermaid in mapping.items():
        if group and d2 == "fontSize": continue
        val = value(st, d2)
        if val:
            if d2 in ("fontSize", "strokeWidth"): val += "px"
            pairs.append(f"{mermaid}:{val}")
    if not group and value(st, "bold") == "true": pairs.append("font-weight:bold")
    if not group and value(st, "italic") == "true": pairs.append("font-style:italic")
    if value(st, "underline") == "true": pairs.append("text-decoration:underline")
    if value(st, "strokeDash") not in ("", "0"):
        pairs.append("stroke-dasharray:5 5")
    radius = value(st, "borderRadius")
    if radius and not edge: pairs.extend([f"rx:{radius}", f"ry:{radius}"])
    if shape == "text":
        pairs.extend(["fill:transparent", "stroke:transparent"])
    return ",".join(pairs)

summary = []
for path in sorted(graph_dir.glob("*.d2.graph.json")):
    graph = json.loads(path.read_text())
    name = path.name.removesuffix(".d2.graph.json") if hasattr(str,"removesuffix") else path.name[:-14]
    objs = graph["objects"]
    ids = {o["id"]: f"n{i:03d}" for i,o in enumerate(objs)}
    by_id = {o["id"]: o for o in objs}
    direction = layout_dir(graph["root_attributes"])
    lines = ["%% Generated from the compiled D2 graph; see matching .mapping.json and TRANSLATION.md.", f"flowchart {direction}"]
    mapping_objects = []
    limitations = collections.Counter()
    retained_styles = {"fill", "stroke", "strokeWidth", "opacity", "fontColor", "fontSize", "bold", "italic", "underline", "strokeDash", "borderRadius"}

    def emit(obj, depth=1, inherited=direction):
        attr = obj["attributes"]
        indent = "  " * depth
        ident = ids[obj["id"]]
        label = plaintext(value(attr, "label"), attr.get("language"))
        shape = value(attr, "shape")
        group = bool(obj["children"])
        mshape = "subgraph" if group else {"cylinder":"cylinder", "queue":"horizontal-cylinder", "person":"circle", "text":"transparent-rectangle", "square":"rectangle"}.get(shape, "rectangle")
        if group:
            d = layout_dir(attr, inherited)
            lines.extend([f'{indent}subgraph {ident}["{escaped(label)}"]', f'{indent}  direction {d}'])
            for child in obj["children"]: emit(by_id[child], depth+1, d)
            lines.append(indent + "end")
        else:
            start, end = {"cylinder":('[(', ')]'), "person":('((', '))')}.get(shape, ('[', ']'))
            if shape == "queue":
                # Mermaid's documented horizontal cylinder shape.
                lines.append(f'{indent}{ident}@{{ shape: h-cyl, label: "{escaped(label)}" }}')
            else:
                lines.append(f'{indent}{ident}{start}"{escaped(label)}"{end}')
        differences=[]
        if any(attr.get(k) for k in ("gridRows", "gridColumns", "gridGap", "verticalGap", "horizontalGap")):
            differences.append("grid approximated by subgraph direction")
        if attr.get("near_key"): differences.append("near positioning omitted")
        for key in ("width", "height", "top", "left", "labelPosition", "iconPosition"):
            if attr.get(key): differences.append(f"{key} placement/sizing omitted")
        for key in attr.get("style", {}):
            if key not in retained_styles: differences.append(f"{key} style omitted")
            elif group and key in ("fontSize", "bold", "italic"): differences.append(f"group {key} omitted to avoid Mermaid label clipping")
        if attr.get("language")=="markdown": differences.append("markdown formatted as plain multiline text")
        if shape=="person": differences.append("person silhouette approximated by labeled circle")
        if shape=="square": differences.append("square aspect ratio not forced")
        if shape=="queue": differences.append("queue approximated by horizontal cylinder")
        if attr.get("tooltip") or attr.get("link"): differences.append("link/tooltip metadata retained only in manifest")
        limitations.update(differences)
        mapping_objects.append({"d2_id":obj["id"], "mermaid_id":ident, "parent_d2_id":obj["parent"], "parent_mermaid_id":ids.get(obj["parent"]), "kind":"group" if group else "node", "source_label":value(attr,"label"), "translated_label":label, "source_shape":shape, "mermaid_shape":mshape, "differences":differences, "source_attributes":attr})

    for obj in objs:
        if not obj["parent"]: emit(obj)
    mapping_edges=[]
    lines.append("  %% Edges in original compiler order; one line per compiled edge.")
    for i,edge in enumerate(graph["edges"]):
        src,dst=ids[edge["source"]],ids[edge["target"]]
        # D2 explicit arrowhead shape:none overrides the arrow token visually.
        sa=edge["source_arrow"] and value(edge.get("source_arrowhead") or {},"shape")!="none"
        da=edge["target_arrow"] and value(edge.get("target_arrowhead") or {},"shape")!="none"
        arrow={(False,False):"---",(False,True):"-->",(True,False):"-->",(True,True):"<-->"}[(sa,da)]
        start, end = (dst,src) if sa and not da else (src,dst)
        label=plaintext(value(edge["attributes"],"label"), edge["attributes"].get("language"))
        label_text=f'|"{escaped(label)}"|' if label else ""
        lines.append(f"  {start} {arrow}{label_text} {end}")
        mapping_edges.append({"index":i,"d2_id":edge["id"],"source_d2_id":edge["source"],"target_d2_id":edge["target"],"source_mermaid_id":src,"target_mermaid_id":dst,"mermaid_start_id":start,"mermaid_end_id":end,"source_arrow_token":edge["source_arrow"],"target_arrow_token":edge["target_arrow"],"source_visible_arrow":sa,"target_visible_arrow":da,"source_label":value(edge["attributes"],"label"),"translated_label":label,"mermaid_arrow":arrow,"source_attributes":edge["attributes"],"source_arrowhead":edge.get("source_arrowhead"),"target_arrowhead":edge.get("target_arrowhead")})
    for obj in objs:
        styles=css(obj["attributes"],value(obj["attributes"],"shape"),group=bool(obj["children"]))
        if styles: lines.append(f'  style {ids[obj["id"]]} {styles}')
    for i,edge in enumerate(graph["edges"]):
        styles=css(edge["attributes"],"",edge=True)
        if styles:lines.append(f'  linkStyle {i} {styles}')
    if any(graph["root_attributes"].get(k) for k in ("gridRows","gridColumns")):
        limitations["root grid approximated by flowchart direction"]+=1
    groups=sum(bool(o["children"]) for o in objs)
    counts={"objects":len(objs),"leaf_nodes":len(objs)-groups,"groups":groups,"edges":len(graph["edges"])}
    source=fixture_dir / f"{name}.d2"
    shutil.copy2(source, output_dir/source.name)
    mmd="\n".join(lines)+"\n"
    (output_dir/f"{name}.mmd").write_text(mmd)
    manifest={"fixture":name,"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"mermaid_sha256":hashlib.sha256(mmd.encode()).hexdigest(),"counts":counts,"root_attributes":graph["root_attributes"],"source_config":graph["config"],"limitations":dict(limitations),"objects":mapping_objects,"edges":mapping_edges,"synthetic_objects":0,"synthetic_edges":0}
    (output_dir/f"{name}.mapping.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    summary.append({"fixture":name,**counts,"limitations":dict(limitations)})
shutil.copy2(fixture_dir/"REAL_WORLD.md",output_dir/"REAL_WORLD.md")
license_dir = fixture_dir/"real_world_licenses"
if not license_dir.exists(): license_dir = fixture_dir.parent/"licenses"
if license_dir.exists(): shutil.copytree(license_dir,output_dir/"real_world_licenses",dirs_exist_ok=True)
(output_dir/"corpus.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary,indent=2))
