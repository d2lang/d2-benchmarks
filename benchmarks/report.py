"""Statistics and local reports for recorded CLI benchmark runs (standard library)."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
from typing import Any

SCHEMA_VERSION = 2
TOOL_NAMES = {
    "d2-dagre": "D2 / Dagre", "d2-tala": "D2 / TALA",
    "mermaid-dagre": "Mermaid / Dagre", "graphviz-dot": "Graphviz / dot",
    "plantuml-dot": "PlantUML / Graphviz",
}
BOOTSTRAP_NOTE = (
    "Percentile 95% bootstrap intervals resample complete measured round indices, "
    "using the same indices across tools and fixtures. Every fixture remains in the "
    "fixed corpus. These intervals describe within-run sampling noise, not uncertainty "
    "across machines, sessions, background loads, or populations of graphs. No outliers "
    "are removed. Incomplete jobs show descriptive successful-attempt samples only."
)


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lo, hi = math.floor(index), math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def _geomean(values: list[float]) -> float | None:
    return math.exp(statistics.mean(math.log(x) for x in values)) if values else None


def _finite_time(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _safe_path(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return None
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def _asset(root: Path, job: dict, records: list[dict]) -> dict:
    output = job.get("output")
    path = _safe_path(root, output)
    result = {"path": output, "exists": bool(path and path.is_file()), "verified": False}
    if not result["exists"]:
        return result
    data = path.read_bytes()
    result["sha256"] = hashlib.sha256(data).hexdigest()
    last = records[-1] if records else {}
    image = last.get("image") or {}
    result["verified"] = bool(last.get("success") and image.get("sha256") == result["sha256"])
    if result["verified"]:
        for key in ("width", "height", "viewBox", "width_css_px", "height_css_px"):
            if key in image:
                result[key] = image[key]
    return result


def _read_rows(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        return [], ["raw.jsonl is missing"]
    rows, errors = [], []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("record is not an object")
            rows.append(value)
        except (ValueError, json.JSONDecodeError) as error:
            errors.append(f"raw.jsonl line {line_number}: {error}")
    return rows, errors


def _bootstrap_draws(n: int, iterations: int, seed: int) -> list[list[int]]:
    rng = random.Random(seed)
    return [[rng.randrange(n) for _ in range(n)] for _ in range(iterations)] if n else []


def _statistics(samples: list[float], draws: list[list[int]]) -> tuple[dict, list[float]]:
    boot = [statistics.median([samples[i] for i in draw]) for draw in draws] if samples else []
    result = {"count": len(samples), "samples": samples, "median": statistics.median(samples) if samples else None,
              "min": min(samples) if samples else None, "max": max(samples) if samples else None,
              "q25": _quantile(samples, .25), "q75": _quantile(samples, .75),
              "p95": _quantile(samples, .95),
              "median_ci95": [_quantile(boot, .025), _quantile(boot, .975)] if boot else None}
    return result, boot


def _key(row: dict) -> tuple:
    return row.get("fixture"), row.get("tool"), row.get("format")


def _group(fixture: dict, fmt: str, primary: bool) -> dict:
    """Keep controlled graph sizes and the real-world corpus independently comparable."""
    category = fixture.get("category", "real-world")
    if category not in ("basic", "real-world"):
        raise ValueError(f"Unknown fixture category: {category}")
    node_count = fixture.get("counts", {}).get("leaf_nodes") if category == "basic" else None
    if category == "basic" and (not isinstance(node_count, int) or isinstance(node_count, bool) or node_count < 1):
        raise ValueError(f"Basic fixture {fixture['id']} requires a positive leaf_nodes count")
    suffix = "svg" if fmt == "svg" else "png-primary" if primary else "png-supplemental"
    group_id = f"basic-{node_count}-{suffix}" if category == "basic" else suffix
    workload = f"Basic · {node_count} nodes" if category == "basic" else "Real-world complex"
    density = fixture.get("png_density")
    density_label = f"{density:g}×" if isinstance(density, (int, float)) else "density unspecified"
    format_label = "SVG" if fmt == "svg" else f"PNG {density_label}" + ("" if primary else " supplement")
    return {"id": group_id, "category": category, "node_count": node_count, "format": fmt,
            "primary": primary, "workload": workload, "format_label": format_label,
            "title": f"{workload} · {format_label}"}


def _summarize(root: Path, run: dict, rows: list[dict], parse_errors: list[str], baseline: str, bootstrap: int) -> dict:
    repetitions, warmups = int(run.get("repetitions", 0)), int(run.get("warmups", 0))
    tools, fixtures = list(run.get("tools", [])), list(run.get("fixtures", []))
    issues = list(parse_errors)
    for field in ("fatal_error", "input_integrity_errors", "tool_integrity_errors", "config_integrity_errors"):
        if run.get(field):
            issues.append(f"{field}: {run[field]}")
    if repetitions < 1 or warmups < 0:
        raise ValueError("Run metadata must specify repetitions >= 1 and warmups >= 0")
    if not tools or not fixtures:
        raise ValueError("Run metadata must specify tools and fixtures")
    fixture_ids = [f["id"] for f in fixtures]
    if len(set(tools)) != len(tools) or len(set(fixture_ids)) != len(fixture_ids):
        issues.append("Duplicate tool or fixture IDs in run metadata")
    plans = list(run.get("jobs", []))
    formats = sorted({j.get("format") for j in plans if j.get("format") in ("svg", "png")})
    if not formats:
        formats = list(run.get("formats", ["svg", "png"]))
        issues.append("Run metadata contains no planned jobs")
    by_key = {}
    for job in plans:
        if _key(job) in by_key:
            issues.append(f"Duplicate planned job: {_key(job)}")
        by_key[_key(job)] = job
    expected_keys = {(fixture, tool, fmt) for fixture in fixture_ids for tool in tools for fmt in formats}
    extra_plans = set(by_key) - expected_keys
    if extra_plans:
        issues.append(f"Unexpected planned jobs: {sorted(map(str, extra_plans))}")
    unexpected = [row for row in rows if _key(row) not in expected_keys]
    if unexpected:
        issues.append(f"{len(unexpected)} raw records do not correspond to an expected job")
    # Resampling round indices jointly preserves correlations within each complete
    # round while holding the chosen corpus fixed. There is no graph resampling.
    seed = int.from_bytes(hashlib.sha256(("d2-benchmarks-bootstrap-v1:" + str(run.get("seed", 0))).encode()).digest()[:8], "big")
    draws_by_count = {}
    bootstrap_medians, cases, group_metadata = {}, [], {}
    for fixture in fixtures:
        for tool in tools:
            for fmt in formats:
                key = fixture["id"], tool, fmt
                missing_plan = key not in by_key
                job = by_key.get(key, {"id": "/".join(key), "fixture": key[0], "tool": tool, "format": fmt,
                                       "raster_density": fixture.get("png_density") if fmt == "png" else None,
                                       "primary": fixture.get("primary_png", True) if fmt == "png" else True,
                                       "output": f"renders/{tool}/{key[0]}.{fmt}"})
                records = [row for row in rows if _key(row) == key]
                measured = [row for row in records if not row.get("warmup", False)]
                warm = [row for row in records if row.get("warmup", False)]
                valid_success = lambda r: bool(r.get("success") and r.get("returncode") == 0 and not r.get("timeout")
                                               and not r.get("validation_error") and _finite_time(r.get("wall_ms")))
                successful = [row for row in measured if valid_success(row)]
                ordered = sorted(enumerate(successful), key=lambda pair: (pair[1].get("round", -1), pair[0]))
                samples = [float(row["wall_ms"]) for _, row in ordered]
                measured_rounds = [row.get("round") for row in measured]
                warm_rounds = [row.get("round") for row in warm]
                missing_rounds = sorted(set(range(repetitions)) - set(measured_rounds))
                duplicate_rounds = sorted({r for r in measured_rounds if measured_rounds.count(r) > 1}, key=str)
                unexpected_rounds = [r for r in measured_rounds if r not in range(repetitions)]
                measured_complete = (len(measured) == repetitions and not missing_rounds and not duplicate_rounds and not unexpected_rounds)
                warm_complete = len(warm) == warmups and set(warm_rounds) == set(range(-warmups, 0))
                input_mismatches = [r.get("round") for r in records if job.get("input_sha256") and r.get("input_sha256") != job["input_sha256"]]
                plan_mismatches = [r.get("round") for r in records if any(r.get(field) != job.get(field) for field in ("id", "output", "raster_density", "primary"))]
                asset = _asset(root, job, records)
                measured_hashes = sorted({r.get("image", {}).get("sha256") for r in successful
                                          if r.get("image", {}).get("sha256")})
                hash_records = sum(bool(r.get("image", {}).get("sha256")) for r in successful)
                reasons = []
                if missing_plan: reasons.append("planned job is missing")
                if not measured_complete: reasons.append("measured rounds are missing, duplicated, or unexpected")
                if len(successful) != len(measured): reasons.append("one or more measured attempts failed or have invalid timings")
                if not warm_complete: reasons.append("warm-up rounds are incomplete")
                if any(not valid_success(r) for r in warm): reasons.append("one or more warm-up attempts failed")
                if input_mismatches: reasons.append("input hashes differ from the planned input")
                if plan_mismatches: reasons.append("raw job metadata differs from the planned job")
                if hash_records != len(successful): reasons.append("one or more successful measurements lack output hashes")
                if not asset["verified"]: reasons.append("retained output is missing or does not match the final successful record")
                if len(samples) not in draws_by_count:
                    draws_by_count[len(samples)] = _bootstrap_draws(len(samples), bootstrap, seed)
                draws = draws_by_count[len(samples)]
                stats, boot = _statistics(samples, draws)
                bootstrap_medians[key] = boot
                failure_details = [{k: r.get(k) for k in ("round", "returncode", "timeout", "validation_error", "stderr", "wall_ms")}
                                   for r in measured if not valid_success(r)]
                primary = bool(job.get("primary", fixture.get("primary_png", True)))
                group = _group(fixture, fmt, primary)
                group_metadata[group["id"]] = group
                case = {"id": job["id"], "fixture": key[0], "title": fixture.get("title", key[0]), "tool": tool,
                        "category": group["category"], "node_count": fixture.get("counts", {}).get("leaf_nodes"),
                        "format": fmt, "raster_density": job.get("raster_density"), "primary": primary,
                        "group": group["id"],
                        "expected_measured": repetitions, "measured_attempts": len(measured), "successes": len(successful),
                        "failures": len(measured)-len(successful), "missing_rounds": missing_rounds,
                        "duplicate_rounds": duplicate_rounds, "unexpected_rounds": unexpected_rounds,
                        "expected_warmups": warmups, "warmup_attempts": len(warm),
                        "warmup_failures": sum(not valid_success(r) for r in warm), "missing_plan": missing_plan,
                        "complete": measured_complete and warm_complete and not missing_plan,
                        "eligible": not reasons, "ineligibility_reasons": reasons, "timing_ms": stats,
                        "failure_details": failure_details, "input": job.get("input"), "input_sha256": job.get("input_sha256"),
                        "command": job.get("command"), "output": job.get("output"), "asset": asset}
                case.update(measured_output_hashes=measured_hashes,
                            measured_output_hash_count=len(measured_hashes),
                            output_hash_records=hash_records,
                            output_stable=(len(measured_hashes) == 1) if hash_records == len(successful) and hash_records else None)
                cases.append(case)
    status = str(run.get("status", "incomplete")).lower()
    # The runner finalizes a session as "failed" when any job fails. Other
    # independently grouped workloads remain comparable if all their own records
    # are complete and successful, and no run-wide integrity/fatal error exists.
    complete_status = status in {"complete", "completed", "success"} or (status == "failed" and bool(run.get("completed_utc")))
    smoke = bool(run.get("smoke") or run.get("mode") == "smoke")
    short = repetitions < 10 or warmups < 1
    global_reasons = list(issues)
    if not complete_status: global_reasons.append(f"Run status is {run.get('status', 'incomplete')}")
    if smoke: global_reasons.append("Smoke runs are correctness checks; aggregate rankings are suppressed")
    if short: global_reasons.append("Short run: fewer than ten measurements or no warm-up; aggregate rankings are suppressed")
    groups = []
    ordered_groups = sorted(group_metadata.values(), key=lambda g: (
        g["category"] != "basic", g["node_count"] or 0, g["format"] != "svg", not g["primary"]))
    for group_meta in ordered_groups:
        group_name = group_meta["id"]
        group_cases = [c for c in cases if c["group"] == group_name]
        if not group_cases:
            continue
        group_fixtures = [f for f in fixture_ids if any(c["fixture"] == f for c in group_cases)]
        expected = {(fixture, tool) for fixture in group_fixtures for tool in tools}
        actual = {(c["fixture"], c["tool"]) for c in group_cases}
        reasons = list(global_reasons)
        if actual != expected: reasons.append("Tools do not cover the same fixture set")
        if baseline not in tools: reasons.append(f"Baseline {baseline} is not part of this run")
        if any(not c["eligible"] for c in group_cases): reasons.append("At least one expected job is incomplete, failed, or unverified; no success-only ranking is shown")
        densities = {c["raster_density"] for c in group_cases}
        if group_meta["format"] == "png" and len(densities) != 1: reasons.append("PNG density differs within this group")
        if group_meta["format"] == "png" and group_meta["primary"] and densities != {2, 2.0}:
            reasons.append("Primary PNG is not consistently rendered at 2x density")
        aggregates = []
        if not reasons:
            lookup = {(c["fixture"], c["tool"]): c for c in group_cases}
            for tool in tools:
                selected = [lookup[f, tool] for f in group_fixtures]
                baselines = [lookup[f, baseline] for f in group_fixtures]
                ratios = [b["timing_ms"]["median"]/c["timing_ms"]["median"] for b, c in zip(baselines, selected)]
                boot_ratios, boot_medians = [], []
                for i in range(bootstrap):
                    boot_medians.append(_geomean([bootstrap_medians[(f, tool, group_meta["format"])][i]
                                                  for f in group_fixtures]))
                    boot_ratios.append(_geomean([bootstrap_medians[(f, baseline, selected[0]["format"])][i] /
                                                 bootstrap_medians[(f, tool, selected[0]["format"])][i] for f in group_fixtures]))
                aggregates.append({"tool": tool, "fixtures": group_fixtures,
                                   "geomean_median_ms": _geomean([c["timing_ms"]["median"] for c in selected]),
                                   "geomean_median_ci95_ms": [_quantile(boot_medians,.025), _quantile(boot_medians,.975)] if boot_medians else None,
                                   "baseline_over_tool_ratio": _geomean(ratios),
                                   "ratio_ci95": [_quantile(boot_ratios,.025), _quantile(boot_ratios,.975)] if boot_ratios else None})
        groups.append({**group_meta, "fixtures": group_fixtures, "fixture_count": len(group_fixtures),
                       "density": next(iter(densities)) if len(densities)==1 else None,
                       "expected_jobs": len(expected), "eligible_jobs": sum(c["eligible"] for c in group_cases),
                       "expected_measurements": len(expected)*repetitions, "attempts": sum(c["measured_attempts"] for c in group_cases),
                       "successes": sum(c["successes"] for c in group_cases), "failures": sum(c["failures"] for c in group_cases),
                       "ranking_available": not reasons, "ranking_suppression_reasons": reasons,
                       "aggregates": aggregates, "ranking": [a["tool"] for a in sorted(aggregates,key=lambda a:a["geomean_median_ms"])] if aggregates else None})
    return {"schema_version":SCHEMA_VERSION, "run_id":run.get("run_id"), "status":run.get("status","incomplete"),
            "started_utc":run.get("started_utc"), "completed_utc":run.get("completed_utc"),
            "baseline":baseline, "tools":tools, "fixtures":fixtures, "environment":run.get("environment",{}),
            "provenance":run.get("provenance",{}), "harness_sha256":run.get("harness_sha256",{}),
            "corpus_validation":run.get("corpus_validation",{}), "smoke":smoke, "short_run":short,
            "repetitions":repetitions, "warmups":warmups, "issues":issues,
            "bootstrap":{"iterations":bootstrap,"seed":seed,"seed_text":str(seed),"confidence":.95,"method":"percentile; matched round resampling; fixed corpus","interpretation":BOOTSTRAP_NOTE},
            "completeness":{"expected_jobs":len(expected_keys), "planned_jobs":len(plans), "expected_measured":len(expected_keys)*repetitions,
                            "measured_attempts":sum(c["measured_attempts"] for c in cases), "successes":sum(c["successes"] for c in cases),
                            "failures":sum(c["failures"] for c in cases), "missing_measurements":sum(len(c["missing_rounds"]) for c in cases),
                            "warmup_attempts":sum(c["warmup_attempts"] for c in cases), "warmup_failures":sum(c["warmup_failures"] for c in cases),
                            "unexpected_raw_records":len(unexpected), "all_jobs_eligible":all(c["eligible"] for c in cases),
                            "jobs_with_changing_output_hashes":sum(c["output_stable"] is False for c in cases)},
            "cases":cases,"groups":groups}


def _num(value: float | None, places: int = 2) -> str:
    return "—" if value is None else f"{value:,.{places}f}"


def _interval(values: list | None) -> str:
    return "—" if not values else f"{_num(values[0])}–{_num(values[1])}"


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _write_csv(root: Path, summary: dict) -> None:
    fields = ["fixture", "category", "node_count", "group", "tool", "format", "raster_density", "primary", "eligible",
              "expected_measured", "measured_attempts", "successes", "failures", "missing_measurements", "median_ms",
              "ci95_low_ms", "ci95_high_ms", "min_ms", "q25_ms", "q75_ms", "p95_ms", "max_ms",
              "measured_output_hash_count", "output_stable", "output"]
    with (root / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for case in summary["cases"]:
            row = {key: case.get(key) for key in fields}
            stats = case["timing_ms"]
            row.update(missing_measurements=len(case["missing_rounds"]), median_ms=stats["median"],
                       ci95_low_ms=stats["median_ci95"][0] if stats["median_ci95"] else None,
                       ci95_high_ms=stats["median_ci95"][1] if stats["median_ci95"] else None)
            for key in ("min", "q25", "q75", "p95", "max"):
                row[key + "_ms"] = stats[key]
            writer.writerow(row)


def _write_markdown(root: Path, summary: dict) -> None:
    c = summary["completeness"]
    lines = ["# Diagram CLI benchmark", "", f"Run `{summary['run_id']}` · status **{summary['status']}** · {summary['started_utc'] or 'date unavailable'}", "",
             "## Performance matrix", "",
             "Fresh-process CLI latency in milliseconds; lower is faster. Basic diagrams are separated by node count. Real-world cells use the geometric mean of their per-diagram medians. No aggregate combines workload families, graph sizes, output formats, or PNG densities. Intervals and individual samples appear below.", "",
             "| Workload | Format | " + " | ".join(_md(TOOL_NAMES.get(t, t)) for t in summary["tools"]) + " |",
             "|---|---|" + "---:|" * len(summary["tools"])]
    for group in summary["groups"]:
        aggregates = {a["tool"]: a for a in group["aggregates"]}
        values = [_num(aggregates[t]["geomean_median_ms"]) if t in aggregates else "unavailable" for t in summary["tools"]]
        lines.append(f"| {_md(group['workload'])} | {_md(group['format_label'])} | " + " | ".join(values) + " |")
    lines += ["", f"{c['successes']} successful measured attempts / {c['expected_measured']} expected; {c['failures']} failures, {c['missing_measurements']} missing measurements. {c['warmup_attempts']} excluded warm-ups ({c['warmup_failures']} failed).", "",
              "[Interactive report](index.html) · [CSV](summary.csv) · [Complete statistics](summary.json) · [Run metadata](run.json) · [Raw attempts](raw.jsonl)", ""]
    if summary["smoke"] or summary["short_run"]:
        lines += ["**Smoke or short run: use this report to check execution and outputs. Aggregate rankings are suppressed.**", ""]
    lines += [f"{c['jobs_with_changing_output_hashes']} jobs produced more than one measured output hash. Changing hashes can reflect layout, identifiers or metadata; hashes alone do not explain the cause.", ""]
    if summary["issues"]:
        lines += ["## Recording issues", ""] + ["- " + _md(i) for i in summary["issues"]] + [""]
    lines += ["## Method and uncertainty", "", BOOTSTRAP_NOTE, "",
              f"Medians use all successful measured attempts, excluding warm-ups. {summary['repetitions']} measurements and {summary['warmups']} warm-ups were planned per job. Bootstrap iterations: {summary['bootstrap']['iterations']}; deterministic seed: {summary['bootstrap']['seed']}.", "",
              "Fresh-process CLI time includes startup, parsing, layout, rendering and output writing. It is not isolated layout-engine time. Equal PNG density does not imply equal pixels or styling. Controlled basic graphs expose scale and startup costs; the D2-authored real-world diagrams represent a fixed corpus, not a random sample of graph workloads.", ""]
    for group in summary["groups"]:
        lines += [f"## {group['title']}", "", f"{group['fixture_count']} fixed fixtures; {group['successes']} successes / {group['expected_measurements']} expected measurements; {group['failures']} failures.", ""]
        if not group["ranking_available"]:
            lines += ["**Aggregate ranking unavailable.** " + "; ".join(group["ranking_suppression_reasons"]) + ".", ""]
            continue
        lines += [f"Ratios are `{summary['baseline']} median / tool median`, geometrically averaged over matched fixtures. Above 1 means the tool is faster than the baseline. The baseline interval is exactly 1 because it is compared with itself.", "",
                  "| Tool | Geomean median (ms) | 95% latency interval (ms) | Baseline / tool | 95% ratio interval |",
                  "|---|---:|---:|---:|---:|"]
        for a in sorted(group["aggregates"], key=lambda a: a["geomean_median_ms"]):
            lines.append(f"| {_md(TOOL_NAMES.get(a['tool'],a['tool']))} | {_num(a['geomean_median_ms'])} | {_interval(a['geomean_median_ci95_ms'])} | {_num(a['baseline_over_tool_ratio'])} | {_interval(a['ratio_ci95'])} |")
        lines.append("")
    lines += ["## Per-job observations", "", "Incomplete rows retain all successful observations for diagnosis; their conditional medians are not eligible for aggregate rankings. Intervals and ranges describe milliseconds.", "",
              "| Diagram | Tool | Output | Success / expected | Failed | Missing | Median | 95% interval | Min–max | Output hashes | Eligible |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for case in summary["cases"]:
        s = case["timing_ms"]
        lines.append(f"| {_md(case['title'])} | {_md(TOOL_NAMES.get(case['tool'],case['tool']))} | {case['format']} | {case['successes']}/{case['expected_measured']} | {case['failures']} | {len(case['missing_rounds'])} | {_num(s['median'])} | {_interval(s['median_ci95'])} | {_num(s['min'])}–{_num(s['max'])} | {case['measured_output_hash_count']}{' (changed)' if case['output_stable'] is False else ''} | {'yes' if case['eligible'] else 'no'} |")
    lines += ["", "## Environment and provenance", "", "The following metadata belongs to this run. No results from other machines or historical runs are substituted.", "", "```json", json.dumps({"environment": summary["environment"], "provenance": summary["provenance"], "harness_sha256": summary["harness_sha256"], "source_hashes": summary["source_hashes"], "corpus_validation": summary["corpus_validation"]}, indent=2, ensure_ascii=False), "```", ""]
    (root / "report.md").write_text("\n".join(lines))


def generate(run_dir: Path, baseline: str = "d2-dagre", bootstrap: int = 2000) -> dict:
    """Read immutable run records and write reproducible statistics and HTML reports."""
    if not isinstance(bootstrap, int) or bootstrap < 0:
        raise ValueError("bootstrap must be a nonnegative integer")
    root=Path(run_dir).resolve()
    run=json.loads((root/"run.json").read_text())
    rows,errors=_read_rows(root/"raw.jsonl")
    summary=_summarize(root,run,rows,errors,baseline,bootstrap)
    summary["source_hashes"]={"run.json":hashlib.sha256((root/"run.json").read_bytes()).hexdigest(),
                              "raw.jsonl":hashlib.sha256((root/"raw.jsonl").read_bytes()).hexdigest() if (root/"raw.jsonl").exists() else None,
                              "inputs/manifest.json":hashlib.sha256((root/"inputs/manifest.json").read_bytes()).hexdigest() if (root/"inputs/manifest.json").exists() else None}
    (root/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    _write_csv(root,summary)
    _write_markdown(root,summary)
    _write_html(root,summary)
    return summary


_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diagram CLI benchmark report</title><style>
:root{color-scheme:light dark;--bg:#f6f8fb;--panel:#fff;--text:#1c2733;--muted:#5d6977;--line:#d5dce6;--accent:#185ca5;--soft:#e9f1fb;--warn:#fff0d6;--warntext:#654100}
*{box-sizing:border-box}body{margin:0;color:var(--text);background:var(--bg);font:15px/1.5 system-ui,sans-serif}main{max-width:1600px;margin:auto;padding:30px 24px}h1{font-size:clamp(25px,3vw,38px);line-height:1.15;letter-spacing:-.025em;margin:10px 0 16px}h2{font-size:21px;margin:26px 0 10px}h3{font-size:16px;margin:12px 0}p{max-width:1050px}a{color:var(--accent);text-underline-offset:3px}nav{display:flex;gap:10px 20px;flex-wrap:wrap;margin:18px 0}.muted{color:var(--muted)}.status{padding:14px 18px;border:1px solid var(--line);border-radius:8px;background:var(--soft);margin:18px 0}.status.warn{background:var(--warn);color:var(--warntext)}.status strong{display:block}.controls{display:flex;gap:14px;flex-wrap:wrap;padding:16px;background:var(--panel);border:1px solid var(--line);border-radius:8px}label{display:flex;flex-direction:column;gap:5px;min-width:130px;flex:1;font-size:13px;color:var(--muted)}select,button{font:inherit;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:5px;padding:9px;min-height:41px;cursor:pointer}a:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:8px;background:var(--panel);margin:14px 0}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{white-space:nowrap;padding:10px 13px;text-align:right;border-bottom:1px solid var(--line)}th{font-size:12px;color:var(--muted);font-weight:600}th:first-child,td:first-child{text-align:left}tr:last-child td{border-bottom:0}td.bad{color:var(--warntext);background:var(--warn)}.pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;margin:20px 0}.panel{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}.panel-head{padding:15px}.panel-head p{font-size:13px;margin:8px 0}.asset-links{display:flex;gap:14px;flex-wrap:wrap;font-size:13px}.viewport{height:520px;overflow:auto;background:white;padding:12px;display:flex;align-items:center;justify-content:center}.viewport img{max-width:100%;max-height:100%;object-fit:contain;width:100%;height:100%}.viewport.actual{display:block}.viewport.actual img{max-width:none;max-height:none}.unavailable{color:#654100;font-size:15px;padding:20px}.spark{width:135px;height:26px;vertical-align:middle;overflow:visible}.spark line,.spark circle{stroke:var(--accent);fill:var(--accent)}details{padding:14px 18px;border:1px solid var(--line);border-radius:8px;background:var(--panel);margin:18px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;word-break:break-word;font:12px/1.5 ui-monospace,monospace;max-height:500px;overflow:auto}.note{font-size:13px;color:var(--muted)}.aggregate-note{padding:12px 16px;border-left:3px solid var(--line)}footer{border-top:1px solid var(--line);padding-top:20px;margin-top:28px;font-size:13px;color:var(--muted)}
@media(prefers-color-scheme:dark){:root{--bg:#151b23;--panel:#1e2733;--text:#e7edf6;--muted:#aab7c9;--line:#394759;--accent:#86baf0;--soft:#263a51;--warn:#493718;--warntext:#f6d89e}}
@media(max-width:800px){main{padding:22px 14px}.pair{grid-template-columns:1fr}.viewport{height:430px}.controls{gap:10px}label:first-child{flex-basis:100%}}
</style></head><body><main>
<p class="muted">Local CLI measurements · fixed diagram corpus</p><h1>Diagram rendering performance</h1>
<p>Fresh-process CLI latency across output formats, controlled graph sizes and real-world diagrams. Every recorded failure and missing measurement remains visible. Different layouts, fonts and canvases make these equivalent semantic graphs, not identical rendering workloads.</p>
<div id="status" class="status" role="status"></div>
<nav><a href="report.md">Text report</a><a href="summary.csv">CSV</a><a href="summary.json">Statistics JSON</a><a href="run.json">Run and environment</a><a href="raw.jsonl">Every raw attempt</a></nav>
<section id="matrix"></section>
<h2>Inspect a diagram</h2><div class="controls">
<label>Diagram<select id="fixture"></select></label><label>Format<select id="format"></select></label><label>Preview<select id="zoom"><option value="fit">Fit diagram</option><option value="actual">Actual size · scroll</option></select></label>
</div><p id="fixture-note" class="muted"></p>
<div class="table-wrap"><table><thead><tr><th>Tool</th><th>Success / expected</th><th>Failed / missing</th><th>Median (ms)</th><th>95% interval (ms)</th><th>All successful samples</th><th>Min–max (ms)</th><th>Output hashes</th></tr></thead><tbody id="jobs"></tbody></table></div>
<p class="note">Dots show every successful measured attempt; the vertical mark is the median. Each row uses its own min–max scale. Warm-ups are excluded. Output hash counts cover measured successes; changing hashes may reflect layout, identifiers or metadata and do not automatically invalidate timings. A row with failures or missing measurements has a conditional descriptive median and is excluded from aggregate rankings.</p>
<div class="pair">
<section class="panel"><div class="panel-head"><label>Left tool<select id="left"></select></label><p id="left-info"></p><div class="asset-links" id="left-links"></div></div><div class="viewport" id="left-view"></div></section>
<section class="panel"><div class="panel-head"><label>Right tool<select id="right"></select></label><p id="right-info"></p><div class="asset-links" id="right-links"></div></div><div class="viewport" id="right-view"></div></section>
</div><section id="aggregate"><h2>Uncertainty by workload</h2></section><details id="failures"><summary>Failures, missing measurements and recording issues</summary><pre id="failure-detail"></pre></details>
<details open><summary>Method and interpretation</summary><p id="bootstrap-note"></p><p>Rounds are resampled jointly and the corpus is held fixed; the report does not bootstrap diagrams. Confidence intervals cannot account for uncontrolled background activity, the choice of examples, different hardware or another benchmark session. No outliers are discarded. A baseline ratio above 1 means the selected tool is faster than that baseline.</p><p>Each basic node count and the real-world corpus are separate workload groups, each split into SVG, primary 2× PNG and any supplemental PNG. They are never pooled into a single score. PNG timing depends on the resulting pixel count. Native SVG fonts, embedded resources and metadata differ across renderers. Times include startup, parsing, layout, rendering and output creation, including Java or browser startup where used.</p><p>Aggregate rankings require a finished non-smoke run without fatal or integrity errors, at least ten measurements and one warm-up, every planned measurement in that workload and format to succeed, and all its retained assets to match their final records. A failed workload does not suppress other complete workload and format groups. Incomplete tools never disappear into a success-only leaderboard.</p></details>
<details><summary>Environment and provenance</summary><pre id="environment"></pre></details>
<footer id="footer"></footer></main>
<script type="application/json" id="data">__DATA__</script><script>
'use strict';
const D=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);
const names={'d2-dagre':'D2 / Dagre','d2-tala':'D2 / TALA','mermaid-dagre':'Mermaid / Dagre','graphviz-dot':'Graphviz / dot','plantuml-dot':'PlantUML / Graphviz'};
const name=t=>names[t]||t,n=v=>v==null?'—':Number(v).toLocaleString('en-US',{maximumFractionDigits:2}),ci=x=>x?`${n(x[0])}–${n(x[1])}`:'—';
const text=(tag,value,cls)=>{const e=document.createElement(tag);e.textContent=value;if(cls)e.className=cls;return e;};
const addOption=(el,value,label)=>{const o=text('option',label);o.value=value;el.append(o);};
const cell=(row,value,cls)=>{const c=text('td',value,cls);row.append(c);return c;};
const sourcePath=p=>typeof p==='string'&&!p.startsWith('/')&&!p.split('/').includes('..')&&!/^[a-z]+:/i.test(p)?p:null;
const addLink=(parent,label,path)=>{if(!sourcePath(path))return;const a=text('a',label);a.href=path;a.target='_blank';a.rel='noopener';parent.append(a);};
const count=D.completeness;
$('status').append(text('strong',`Run ${D.run_id||''} · ${D.status}${D.smoke?' · SMOKE':D.short_run?' · SHORT RUN':''}`),text('span',`${count.successes} successes / ${count.expected_measured} expected measured attempts · ${count.failures} failures · ${count.missing_measurements} missing · ${count.warmup_failures} failed warm-ups.`));
if(D.issues.length||!count.all_jobs_eligible||D.smoke||D.short_run||!['complete','completed','success'].includes(String(D.status).toLowerCase()))$('status').classList.add('warn');
$('matrix').append(text('h2',`Performance matrix · ${(D.started_utc||'date unavailable').slice(0,10)}`),text('p','Fresh-process CLI latency in milliseconds; lower is faster. Basic node counts, the real-world corpus and output formats are compared independently. Each cell is the geometric mean of its per-diagram medians; a single basic diagram uses its own median. Confidence intervals and every individual sample remain available below.','note'));
const matrixWrap=text('div','','table-wrap'),matrixTable=document.createElement('table'),matrixHead=document.createElement('thead'),matrixHeader=document.createElement('tr'),matrixBody=document.createElement('tbody');
for(const label of ['Workload','Format',...D.tools.map(name)])matrixHeader.append(text('th',label));
matrixHead.append(matrixHeader);matrixTable.append(matrixHead);
for(const group of D.groups){const tr=document.createElement('tr');cell(tr,group.workload);cell(tr,group.format_label);for(const tool of D.tools){const a=group.aggregates.find(a=>a.tool===tool);const td=cell(tr,a?n(a.geomean_median_ms):'unavailable',a?'':'bad');td.title=a?`95% interval: ${ci(a.geomean_median_ci95_ms)} ms; ${group.fixture_count} fixture(s)`:group.ranking_suppression_reasons.join('; ');}matrixBody.append(tr);}
matrixTable.append(matrixBody);matrixWrap.append(matrixTable);$('matrix').append(matrixWrap);
for(const group of D.groups){
 const section=document.createElement('details');section.append(text('summary',group.title),text('p',`${group.fixture_count} fixed fixtures · ${group.successes}/${group.expected_measurements} successful measurements · ${group.failures} failed.`, 'muted'));
 if(!group.ranking_available){section.append(text('p','Ranking unavailable: '+group.ranking_suppression_reasons.join('; '),'aggregate-note'));}
 else{
  section.append(text('p',`Geometric means of per-fixture medians. Ratio = ${name(D.baseline)} / tool; above 1 means faster.`, 'note'));
  const wrap=text('div','','table-wrap'),table=document.createElement('table'),head=document.createElement('thead'),hr=document.createElement('tr');
  for(const label of ['Tool','Geomean median (ms)','95% latency interval (ms)','Baseline / tool','95% ratio interval'])hr.append(text('th',label));head.append(hr);table.append(head);const body=document.createElement('tbody');
  for(const a of [...group.aggregates].sort((a,b)=>a.geomean_median_ms-b.geomean_median_ms)){const tr=document.createElement('tr');[name(a.tool),n(a.geomean_median_ms),ci(a.geomean_median_ci95_ms),n(a.baseline_over_tool_ratio),ci(a.ratio_ci95)].forEach(v=>cell(tr,v));body.append(tr);}table.append(body);wrap.append(table);section.append(wrap);
 }$('aggregate').append(section);
}
D.fixtures.forEach(f=>addOption($('fixture'),f.id,f.title||f.id));
[...new Set(D.cases.map(c=>c.format))].forEach(f=>addOption($('format'),f,f.toUpperCase()));
for(const side of ['left','right'])D.tools.forEach(t=>addOption($(side),t,name(t)));
const lookup=new Map(D.cases.map(c=>[`${c.fixture}/${c.tool}/${c.format}`,c]));
function current(tool){return lookup.get(`${$('fixture').value}/${tool}/${$('format').value}`);}
function dims(c){const a=c.asset;if(c.format==='png')return a.width&&a.height?`${n(a.width)} × ${n(a.height)} px`:'—';if(a.width_css_px&&a.height_css_px)return `${n(a.width_css_px)} × ${n(a.height_css_px)} CSS px`;return a.viewBox?'viewBox '+a.viewBox:'—';}
function spark(stats){const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('class','spark');svg.setAttribute('viewBox','0 0 135 26');svg.setAttribute('role','img');svg.setAttribute('aria-label',`${stats.count} samples, minimum ${stats.min}, median ${stats.median}, maximum ${stats.max} milliseconds`);const x=v=>stats.max===stats.min?67:5+125*(v-stats.min)/(stats.max-stats.min);for(const [i,v]of stats.samples.entries()){const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',x(v));dot.setAttribute('cy',10+(i%3)*3);dot.setAttribute('r','1.7');dot.setAttribute('opacity','.55');const title=document.createElementNS(ns,'title');title.textContent=`${v} ms`;dot.append(title);svg.append(dot);}if(stats.count){const line=document.createElementNS(ns,'line');line.setAttribute('x1',x(stats.median));line.setAttribute('x2',x(stats.median));line.setAttribute('y1','3');line.setAttribute('y2','23');svg.append(line);}return svg;}
function panel(side){const c=current($(side).value),view=$(side+'-view'),links=$(side+'-links');view.replaceChildren();links.replaceChildren();if(!c){$(side+'-info').textContent='Job missing';view.append(text('p','No planned job','unavailable'));return;}
 $(side+'-info').textContent=`${n(c.timing_ms.median)} ms median · ${c.successes}/${c.expected_measured} successful measurements · ${dims(c)}`;
 addLink(links,'Open output',c.output);addLink(links,'View input',c.input);
 if(!c.asset.verified||!sourcePath(c.output)){view.append(text('p','No verified final output. See failures and raw records.','unavailable'));return;}
 const img=document.createElement('img');img.alt=`${c.title}: ${name(c.tool)} ${c.format}`;img.src=c.output;img.onerror=()=>{view.replaceChildren(text('p','The local output could not be loaded.','unavailable'));};
 const actual=$('zoom').value==='actual';view.classList.toggle('actual',actual);
 if(actual){const vb=String(c.asset.viewBox||'').split(/[\s,]+/).map(Number),w=c.format==='png'?c.asset.width:c.asset.width_css_px||vb[2],h=c.format==='png'?c.asset.height:c.asset.height_css_px||vb[3];if(w)img.style.width=w+'px';if(h)img.style.height=h+'px';}
 view.append(img);
}
function update(hash=true){const f=D.fixtures.find(x=>x.id===$('fixture').value),counts=f.counts||{};const first=current(D.tools[0]);$('fixture-note').textContent=`${f.category==='basic'?'Basic':'Real-world complex'} · ${counts.leaf_nodes??'?'} nodes · ${counts.groups??'?'} groups · ${counts.edges??'?'} edges${first?.format==='png'?` · ${first.raster_density}× PNG density${first.primary?'':' · supplemental'}`:''}`;
 $('jobs').replaceChildren();for(const tool of D.tools){const c=current(tool),row=document.createElement('tr');cell(row,name(tool));if(!c){cell(row,'Missing');$('jobs').append(row);continue;}const s=c.timing_ms;cell(row,`${c.successes}/${c.expected_measured}`,c.eligible?'':'bad');cell(row,`${c.failures} / ${c.missing_rounds.length}`,c.eligible?'':'bad');cell(row,n(s.median));cell(row,ci(s.median_ci95));const plot=cell(row,'');plot.append(spark(s));cell(row,`${n(s.min)}–${n(s.max)}`);cell(row,c.measured_output_hash_count+(c.output_stable===false?' · changed':''));$('jobs').append(row);}panel('left');panel('right');if(hash)history.replaceState(null,'','#'+new URLSearchParams({fixture:f.id,format:$('format').value,left:$('left').value,right:$('right').value,zoom:$('zoom').value}));}
function state(){const p=new URLSearchParams(location.hash.slice(1));$('fixture').value=D.fixtures.some(f=>f.id===p.get('fixture'))?p.get('fixture'):D.fixtures[0].id;$('format').value=[...$('format').options].some(o=>o.value===p.get('format'))?p.get('format'):D.cases.some(c=>c.format==='svg')?'svg':$('format').options[0].value;$('left').value=D.tools.includes(p.get('left'))?p.get('left'):D.tools.includes(D.baseline)?D.baseline:D.tools[0];$('right').value=D.tools.includes(p.get('right'))?p.get('right'):D.tools.find(t=>t!==$('left').value)||D.tools[0];$('zoom').value=p.get('zoom')==='actual'?'actual':'fit';update(false);}
for(const id of ['fixture','format','left','right','zoom'])$(id).addEventListener('change',()=>update());window.addEventListener('hashchange',state);
const failed=D.cases.filter(c=>!c.eligible).map(c=>({fixture:c.fixture,tool:c.tool,format:c.format,reasons:c.ineligibility_reasons,missing_rounds:c.missing_rounds,duplicate_rounds:c.duplicate_rounds,failures:c.failure_details}));$('failure-detail').textContent=JSON.stringify({recording_issues:D.issues,jobs:failed},null,2);if(failed.length||D.issues.length)$('failures').open=true;
$('bootstrap-note').textContent=D.bootstrap.interpretation+` Bootstrap samples: ${D.bootstrap.iterations}. Seed: ${D.bootstrap.seed_text}.`;$('environment').textContent=JSON.stringify({environment:D.environment,provenance:D.provenance,source_hashes:D.source_hashes,harness_sha256:D.harness_sha256,corpus_validation:D.corpus_validation},null,2);$('footer').textContent=`${D.started_utc||''} — ${D.completed_utc||'run not completed'} · All statistics come from this run's recorded attempts.`;state();
</script></body></html>'''


def _write_html(root: Path, summary: dict) -> None:
    data=json.dumps(summary,separators=(",",":"),ensure_ascii=False,allow_nan=False).replace("</", "<\\/")
    (root/"index.html").write_text(_HTML.replace("__DATA__",data))
