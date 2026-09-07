# Custom toolchains

The setup command writes `.tools/toolchain.json`. Copy it to another local file and edit explicit argument arrays. Paths to executables, JavaScript entry points, JARs, and caches should be absolute. The runner executes these commands, so use a configuration you trust.

A D2 configuration looks like:

```json
{
  "schema_version": 1,
  "tools": {
    "d2-dagre": {
      "kind": "d2",
      "argv": ["/absolute/path/to/d2", "--layout", "dagre"],
      "version_argv": ["/absolute/path/to/d2", "--version"],
      "env": {},
      "provenance": {
        "source": "https://github.com/d2lang/d2",
        "revision": "your exact source commit",
        "build": "record your actual build flags"
      }
    }
  }
}
```

```sh
python3 -m benchmarks doctor --toolchain local.json --tools d2-dagre
./make.sh --toolchain local.json --tools d2-dagre --output results/local-d2
```

For another D2 build, add a distinct ID such as `d2-candidate`, with `kind: "d2"`. Select both IDs in the same run so they use the same corpus and sampling procedure. Choose the reference with `--baseline d2-dagre`.

Compare each configuration within the same workload and output format. The default includes SVG and PNG for basic 2-, 10-, and 100-node trees and the real-world complex corpus, with separate results for each dimension. For example, `./make.sh --toolchain local.json --tools d2-dagre d2-candidate --category basic --formats svg png` measures both configurations on all three basic sizes. `--nodes 100` limits the run to the basic 100-node case; it does not select real-world diagrams by their node counts. Reports compare elapsed CLI time and do not score output file size.

## Optional D2 / TALA

The five-tool reference adds D2 / TALA from private staging commit `3f0a4a31a0aeadfc35b31bdb04def30982e2d304`. TALA requires your own authorized source access or executable; this repository does not distribute its source or binary. Plain `./make.sh` continues to install and measure the four public tools.

With access to `alixander/d2-tala-staging`, run this from the benchmark repository root. Use Python 3.11.9 or newer as described in [setup](SETUP.md), and authenticate `gh` for the private repository. Setup installs the pinned public tools and Go compiler without starting a benchmark.

```sh
set -eu
python3 scripts/setup.py
benchmark_root="$(pwd)"
mkdir -p .tools-tala
gh repo clone alixander/d2-tala-staging .tools-tala/source
git -C .tools-tala/source checkout --detach 3f0a4a31a0aeadfc35b31bdb04def30982e2d304
(
  cd .tools-tala/source
  CGO_ENABLED=0 GOTOOLCHAIN=local GOWORK=off \
    "$benchmark_root/.tools/go/go/bin/go" build -trimpath -ldflags='-s -w' \
    -o "$benchmark_root/.tools-tala/d2" .
)
cp .tools/toolchain.json .tools-tala/toolchain.json
python3 - <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess

root = Path.cwd()
config = root / ".tools-tala/toolchain.json"
binary = root / ".tools-tala/d2"
revision = subprocess.check_output(
    ["git", "-C", str(root / ".tools-tala/source"), "rev-parse", "HEAD"], text=True
).strip()
assert revision == "3f0a4a31a0aeadfc35b31bdb04def30982e2d304"
toolchain = json.loads(config.read_text())
toolchain["tools"]["d2-tala"] = {
    "kind": "d2",
    "argv": [str(binary), "--layout", "tala", "--tala-seeds", "1,2,3"],
    "version_argv": [str(binary), "--version"],
    "env": {},
    "provenance": {
        "source": "https://github.com/alixander/d2-tala-staging",
        "revision": revision,
        "go": subprocess.check_output(
            [str(root / ".tools/go/go/bin/go"), "version"], text=True
        ).strip(),
        "build": "CGO_ENABLED=0 GOTOOLCHAIN=local GOWORK=off go build -trimpath -ldflags='-s -w'",
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "tala_seeds": [1, 2, 3],
    },
}
config.write_text(json.dumps(toolchain, indent=2) + "\n")
PY
python3 -m benchmarks doctor --toolchain .tools-tala/toolchain.json \
  --tools d2-dagre d2-tala mermaid-dagre graphviz-dot plantuml-dot
./make.sh --toolchain .tools-tala/toolchain.json \
  --tools d2-dagre d2-tala mermaid-dagre graphviz-dot plantuml-dot
```

The source, binary, and generated configuration stay in ignored `.tools-tala/`. The explicit seeds fix TALA's search inputs across invocations. This comparison uses the public D2 build for Dagre and the separate staging build for TALA, so timings include differences between those builds. To isolate layout choice, add the staging executable's Dagre mode under another tool ID and measure both modes together.

## Other configurations

Other supported kinds are `mermaid`, `graphviz`, and `plantuml`. The runner appends source/output/format/density arguments according to the kind. Start from setup's working definitions, preserve required headless/browser/Graphviz settings, and test SVG and PNG before a full run. A version command is run before timing; explicit file hashes are recorded separately from self-reported version strings.

Ambient `D2_*`, Node and JVM option variables and selected global diagram switches are cleared by the runner. Explicit `env` entries in the toolchain take precedence and are therefore part of your experiment. Do not place credentials in a toolchain or published run.
