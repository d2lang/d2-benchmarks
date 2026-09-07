"""Process orchestration and evidence capture; no installation inside timers."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import shutil
import signal
import struct
import subprocess
import sys
import time
from typing import Any
from xml.etree import ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_TOOLS = ["d2-dagre", "d2-tala", "mermaid-dagre", "graphviz-dot", "plantuml-dot"]
KINDS = {"d2": ".d2", "mermaid": ".mmd", "graphviz": ".dot", "plantuml": ".puml"}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def load_toolchain(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1 or not isinstance(data.get("tools"), dict):
        raise ValueError("toolchain must have schema_version=1 and a tools object")
    for name, tool in data["tools"].items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise ValueError(f"invalid tool ID: {name}")
        if tool.get("kind") not in KINDS:
            raise ValueError(f"unknown kind for {name}")
        for key in ("argv", "version_argv"):
            if not isinstance(tool.get(key), list) or not tool[key] or not all(isinstance(s, str) for s in tool[key]):
                raise ValueError(f"{name}.{key} must be a nonempty argument array")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in tool.get("env", {}).items()):
            raise ValueError(f"{name}.env must contain string values")
    return data


def clean_environment(overrides: dict | None = None) -> dict:
    env = os.environ.copy()
    # Ambient tool switches can otherwise silently change a requested workload.
    for key in list(env):
        if key.startswith("D2_") or key in {
            "SCALE", "DEBUG", "OMIT_VERSION", "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS",
            "JDK_JAVA_OPTIONS", "PLANTUML_LIMIT_SIZE", "GRAPHVIZ_DOT", "NODE_OPTIONS",
        }:
            del env[key]
    env.update({"LC_ALL": "C", "TZ": "UTC"})
    env.update(overrides or {})
    return env


def kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def invoke(argv: list[str], env: dict, timeout: float, cwd: Path | None = None) -> dict:
    """Include launch through child exit; image checks and hashing are outside."""
    started = time.perf_counter_ns()
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, cwd=cwd, start_new_session=True)
    except OSError as error:
        return {"wall_ms": (time.perf_counter_ns() - started) / 1e6,
                "returncode": None, "stdout": "", "stderr": str(error), "launch_error": type(error).__name__}
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_group(proc)
        stdout, stderr = proc.communicate()
    except BaseException:
        kill_group(proc)
        proc.communicate()
        raise
    result = {"wall_ms": (time.perf_counter_ns() - started) / 1e6,
              "returncode": proc.returncode, "stdout": stdout.decode(errors="replace"),
              "stderr": stderr.decode(errors="replace")}
    if timed_out:
        result["timeout"] = True
    return result


def image_info(path: Path) -> dict:
    data = path.read_bytes()
    if not data:
        raise ValueError("empty output")
    info = {"sha256": hashlib.sha256(data).hexdigest()}
    if path.suffix == ".png":
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("invalid PNG signature")
        offset, ended, idat, chunks = 8, False, False, 0
        while offset + 12 <= len(data):
            size = struct.unpack_from(">I", data, offset)[0]
            kind = data[offset + 4:offset + 8]
            end = offset + size + 12
            if end > len(data):
                raise ValueError("truncated PNG chunk")
            payload = data[offset + 8:offset + 8 + size]
            crc = struct.unpack_from(">I", data, offset + size + 8)[0]
            if zlib.crc32(kind + payload) & 0xffffffff != crc:
                raise ValueError("PNG chunk CRC mismatch")
            if chunks == 0:
                if kind != b"IHDR" or size != 13:
                    raise ValueError("missing PNG IHDR")
                info["width"], info["height"] = struct.unpack_from(">II", payload)
            idat |= kind == b"IDAT"
            chunks += 1
            offset = end
            if kind == b"IEND":
                ended = size == 0 and offset == len(data)
                break
        if not ended or not idat or not info.get("width") or not info.get("height"):
            raise ValueError("incomplete PNG")
        info["pixels"] = info["width"] * info["height"]
    else:
        svg = ET.fromstring(data)
        if svg.tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError("output is not an SVG document")
        if svg.get("data-diagram-type") == "ERROR":
            raise ValueError("PlantUML error diagram")
        info.update({key: svg.get(key) for key in ("width", "height", "viewBox")})
        for key in ("width", "height"):
            match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(px|pt|in|cm|mm)?", svg.get(key, ""))
            if match:
                scale = {None: 1, "px": 1, "pt": 96/72, "in": 96, "cm": 96/2.54, "mm": 96/25.4}[match[2]]
                info[key + "_css_px"] = float(match[1]) * scale
        if svg.get("viewBox"):
            box = [float(x) for x in svg.get("viewBox").replace(",", " ").split()]
            if len(box) != 4 or not all(math.isfinite(x) for x in box) or min(box[2:]) <= 0:
                raise ValueError("invalid SVG viewBox")
            info.setdefault("width_css_px", box[2])
            info.setdefault("height_css_px", box[3])
        for element in svg.iter():
            for key in ("d", "points", "transform"):
                if re.search(r"\b(?:NaN|Infinity|undefined)\b", element.get(key, "")):
                    raise ValueError("nonfinite SVG geometry")
    return info


def command_for(tool: dict, source: Path, output: Path, fmt: str, density: float | None, config: Path) -> list[str]:
    argv = tool["argv"].copy()
    kind = tool["kind"]
    if kind == "d2":
        if fmt == "png":
            argv += ["--scale", str(density / 2)]
        argv += [str(source), str(output)]
    elif kind == "mermaid":
        argv += ["-i", str(source), "-o", str(output), "-c", str(config), "-s", str(density or 1)]
    elif kind == "graphviz":
        argv += ["-T" + fmt, str(source), "-o", str(output)]
        if fmt == "png":
            argv += ["-Gdpi=" + str(96 * density)]
    else:
        argv += ["-t" + fmt, "-o", str(output.parent)]
        if fmt == "png":
            argv += ["-Sdpi=" + str(int(96 * density))]
        argv += [str(source)]
    return argv


def hardware() -> dict:
    data = {"os": platform.system(), "os_release": platform.release(), "os_version": platform.version(),
            "architecture": platform.machine(), "logical_cpus": os.cpu_count(), "python": platform.python_version()}
    if sys.platform == "darwin":
        for key, query in (("cpu", "machdep.cpu.brand_string"), ("memory_bytes", "hw.memsize")):
            p = subprocess.run(["sysctl", "-n", query], capture_output=True, text=True)
            if p.returncode == 0:
                data[key] = p.stdout.strip()
    elif sys.platform.startswith("linux"):
        for path, key in (("/proc/cpuinfo", "cpuinfo"), ("/proc/meminfo", "meminfo")):
            if Path(path).exists():
                text = Path(path).read_text()
                if key == "cpuinfo":
                    data["cpu"] = next((line.split(":", 1)[1].strip() for line in text.splitlines() if line.startswith("model name")), platform.processor())
                else:
                    data["memory"] = text.splitlines()[0]
        governor = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        if governor.exists():
            data["cpu0_governor"] = governor.read_text().strip()
    if hasattr(os, "sched_getaffinity"):
        data["cpu_affinity"] = sorted(os.sched_getaffinity(0))
    data["clock"] = vars(time.get_clock_info("perf_counter"))
    data["background_load_controlled"] = False
    data["environment_note"] = "Fresh processes, warm filesystem caches. Runner does not change power, CPU, scheduler, or system settings."
    return data


def inspect_tools(toolchain: dict, names: list[str]) -> dict:
    result = {}
    for name in names:
        if name not in toolchain["tools"]:
            raise ValueError(f"tool {name!r} is not configured")
        tool = toolchain["tools"][name]
        probe = invoke(tool["version_argv"], clean_environment(tool.get("env")), 30)
        if probe.get("returncode") != 0:
            raise ValueError(f"{name} version probe failed: {probe['stderr'][-1000:]}")
        fingerprints = {}
        for value in dict.fromkeys(tool["argv"] + tool["version_argv"] + list(tool.get("env", {}).values())):
            path = Path(value)
            if path.is_absolute() and path.is_file():
                fingerprints[str(path)] = sha256(path)
        executable = shutil.which(tool["argv"][0], path=clean_environment(tool.get("env")).get("PATH"))
        if executable:
            fingerprints[executable] = sha256(Path(executable))
        result[name] = {"kind": tool["kind"], "version": (probe["stdout"] + probe["stderr"]).strip(),
                        "file_sha256": fingerprints, "environment_overrides": tool.get("env", {}),
                        "provenance": tool.get("provenance", {})}
    return result


def build_jobs(fixtures: list[dict], names: list[str], formats: list[str], toolchain: dict, output: Path) -> list[dict]:
    jobs = []
    for fixture in fixtures:
        for fmt in formats:
            density = fixture["png_density"] if fmt == "png" else None
            for name in names:
                tool = toolchain["tools"][name]
                kind = tool["kind"]
                source = output / "inputs" / fixture["inputs"][kind]["path"]
                dest = output / "renders" / name / (fixture["id"] + "." + fmt)
                dest.parent.mkdir(parents=True, exist_ok=True)
                jobs.append({"id": f"{fixture['id']}/{name}/{fmt}", "fixture": fixture["id"],
                             "tool": name, "format": fmt, "raster_density": density,
                             "primary": fmt == "svg" or fixture["primary_png"],
                             "input": str(source.relative_to(output)), "input_sha256": sha256(source),
                             "command": command_for(tool, source, dest, fmt, density, output / "config/mermaid-dagre.json"),
                             "output": str(dest.relative_to(output))})
    return jobs


def select_fixtures(fixtures: list[dict], args) -> list[dict]:
    """Apply explicit workload filters without blending basic and real-world cases."""
    selected = fixtures
    if args.fixtures:
        missing = set(args.fixtures) - {f["id"] for f in fixtures}
        if missing:
            raise ValueError("unknown fixtures: " + ", ".join(sorted(missing)))
        selected = [f for f in selected if f["id"] in args.fixtures]
    categories = getattr(args, "category", None)
    if categories:
        selected = [f for f in selected if f.get("category", "real-world") in categories]
    nodes = getattr(args, "nodes", None)
    if nodes:
        available = {f["counts"]["leaf_nodes"] for f in fixtures if f.get("category") == "basic"}
        missing = set(nodes) - available
        if missing:
            raise ValueError("unsupported basic node counts: " + ", ".join(map(str, sorted(missing))))
        selected = [f for f in selected if f.get("category") == "basic" and f["counts"]["leaf_nodes"] in nodes]
    if not selected:
        raise ValueError("no fixtures match the selected category, node counts, and fixture IDs")
    return selected


def run(args) -> tuple[Path, int]:
    from .corpus import validate_corpus, validate_svg
    corpus = ROOT / "corpus"
    validation = validate_corpus(corpus)
    if validation.get("errors"):
        raise ValueError("corpus validation failed: " + str(validation["errors"]))
    manifest = json.loads((corpus / "manifest.json").read_text())
    fixtures = select_fixtures(manifest["fixtures"], args)
    toolchain = load_toolchain(args.toolchain)
    env = hardware()
    env["tools"] = inspect_tools(toolchain, args.tools)
    output = args.output.resolve()
    # An exclusive new directory prevents stale images or combined sessions.
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(corpus, output / "inputs")
    shutil.copytree(ROOT / "config", output / "config")
    snapshot_validation = validate_corpus(output / "inputs")
    if snapshot_validation.get("errors"):
        raise ValueError("copied corpus failed validation: " + str(snapshot_validation["errors"]))
    jobs = build_jobs(fixtures, args.tools, args.formats, toolchain, output)
    config_hashes = {str(p.relative_to(output)): sha256(p) for p in sorted((output / "config").rglob("*")) if p.is_file()}
    git_info = {"revision": None, "dirty": None}
    if shutil.which("git"):
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
        if revision.returncode == 0 and status.returncode == 0:
            git_info = {"revision": revision.stdout.strip(), "dirty": bool(status.stdout.strip())}
    metadata = {"schema_version": 1, "run_id": output.name, "label": args.label,
                "started_utc": utc(), "status": "running", "seed": args.seed,
                "warmups": args.warmups, "repetitions": args.repetitions, "timeout_seconds": args.timeout,
                "tools": args.tools, "formats": args.formats, "fixtures": fixtures, "jobs": jobs, "environment": env,
                "smoke": args.repetitions < 10, "corpus_validation": validation,
                "config_sha256": config_hashes, "repository": git_info,
                "method": "serial randomized complete rounds; fresh process; warm filesystem; no outlier deletion",
                "harness_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "benchmarks").glob("*.py"))}}
    write_json(output / "run.json", metadata)
    write_json(output / "environment.json", env)
    rng = random.Random(args.seed)
    failures, interrupted, fatal = 0, False, None
    try:
        with (output / "raw.jsonl").open("x") as log:
            for round_id in range(-args.warmups, args.repetitions):
                order = jobs.copy()
                rng.shuffle(order)
                for index, job in enumerate(order):
                    dest = output / job["output"]
                    dest.unlink(missing_ok=True)
                    row = dict(job, round=round_id, warmup=round_id < 0, utc=utc(),
                               loadavg=list(os.getloadavg()) if hasattr(os, "getloadavg") else None)
                    row.update(invoke(job["command"], clean_environment(toolchain["tools"][job["tool"]].get("env")), args.timeout, output))
                    if row.get("returncode") == 0 and not row.get("timeout"):
                        try:
                            row["image"] = image_info(dest)
                            if job["format"] == "svg":
                                audit = validate_svg(dest, job["fixture"], toolchain["tools"][job["tool"]]["kind"], output / "inputs")
                                if audit.get("errors"):
                                    raise ValueError(str(audit["errors"]))
                                row["semantic_validation"] = audit
                        except Exception as error:
                            row["validation_error"] = f"{type(error).__name__}: {error}"
                    row["success"] = row.get("returncode") == 0 and "image" in row and not row.get("timeout") and not row.get("validation_error")
                    failures += not row["success"]
                    log.write(json.dumps(row, ensure_ascii=False) + "\n")
                    log.flush()
                    print(f"round {round_id:3} {index+1:2}/{len(jobs)} {job['id']} {row['wall_ms']:.1f} ms {'ok' if row['success'] else 'FAILED'}", flush=True)
    except KeyboardInterrupt:
        interrupted = True
    except BaseException as error:
        fatal = f"{type(error).__name__}: {error}"
        raise
    finally:
        final_validation = validate_corpus(output / "inputs")
        if final_validation.get("errors"):
            failures += 1
            metadata["input_integrity_errors"] = final_validation["errors"]
        config_changes = [file for file, expected in config_hashes.items()
                          if not (output / file).is_file() or sha256(output / file) != expected]
        if config_changes:
            failures += 1
            metadata["config_integrity_errors"] = config_changes
        tool_changes = []
        for name, tool in env["tools"].items():
            for file, expected in tool["file_sha256"].items():
                path = Path(file)
                if not path.is_file() or sha256(path) != expected:
                    tool_changes.append({"tool": name, "file": file, "expected_sha256": expected})
        if tool_changes:
            failures += 1
            metadata["tool_integrity_errors"] = tool_changes
        if fatal:
            metadata["fatal_error"] = fatal
        metadata.update(completed_utc=utc(), status="interrupted" if interrupted else ("failed" if failures or fatal else "complete"), failures=failures)
        write_json(output / "run.json", metadata)
    return output, 130 if interrupted else int(bool(failures))
