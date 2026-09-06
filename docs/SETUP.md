# Pinned local tool setup

Run from the repository root:

```sh
./make.sh
```

This installs the pinned tools if needed, then runs the complete benchmark and generates its reports. Later invocations reuse a completed installation with matching pins. Pass runner options directly, for example `./make.sh --formats svg`. `./make.sh --help` displays options without installing diagram tools. An explicit `--toolchain PATH` uses your existing tools and skips automatic tool setup.

The default measures all four CLIs in SVG and PNG on three basic diagrams (2, 10, and 100 nodes) and ten real-world complex diagrams. Reports keep every basic size and each real-world output format separate. The default sampling plan is three warm-up rounds and twenty measured rounds; reported metrics concern rendering time, not file size.

To select part of the matrix:

```sh
./make.sh --category basic
./make.sh --nodes 2 10 100 --formats svg
./make.sh --category real-world --formats svg png
./make.sh --fixtures jupyter_aws_eks --warmups 0 --repetitions 1 --label smoke
```

`--category` accepts `basic`, `real-world`, or both. `--nodes` selects basic diagrams with those node counts and excludes real-world diagrams. Use `--fixtures` for explicit fixture IDs. A short smoke run checks execution; its report suppresses aggregate performance rankings.

The launcher uses an available Python 3.11.9+ (3.12+ recommended). If none is available, it downloads checksum-pinned CPython 3.12.14 from the [Python standalone build release](https://github.com/astral-sh/python-build-standalone/releases/tag/20260901) into `.tools-python/`. Bootstrap requires `curl`, `tar`, and `sha256sum` or `shasum`; it verifies the archive before extraction. To select your own interpreter, run `PYTHON=/path/to/python3 ./make.sh`. `PYTHON` is an executable path, not a command with flags.

For the direct Python commands in these docs, use your supported interpreter or the downloaded `.tools-python/cpython-3.12.14-20260901-<target>/python/bin/python3`, where `<target>` is `aarch64-apple-darwin` or `x86_64-unknown-linux-gnu`. For setup without a benchmark run:

```sh
python3 scripts/setup.py
python3 -m benchmarks doctor
```

Setup supports native macOS arm64 and Linux x86_64. Ubuntu 24.04 is the Linux CI target. A Linux host needs the standard desktop libraries required by Chrome Headless Shell; the GitHub-hosted Ubuntu 24.04 image supplies them. Minimal containers may lack those libraries. Ubuntu 23.10+ may also require an administrator to allow Chrome's sandbox user namespaces through AppArmor; see [Puppeteer's official troubleshooting guide](https://pptr.dev/troubleshooting#issues-with-apparmor-on-ubuntu). Setup reports Chrome launch errors in `.tools/setup.log` and does not install system packages or disable the browser sandbox.

The script installs executables and caches under `.tools/`. It does not run sudo, initialize a shell, change PATH permanently, register a user conda environment, or install global npm/pip packages. No Docker image is provided. Allow several gigabytes of free space for the downloaded archives, native libraries, Chromium, npm dependencies, Go modules, and compilation cache.

Setup renders a small graph to both SVG and PNG with all four tools before declaring success. These smoke renders check execution, not performance or equivalence across the full corpus. The benchmark command performs the corpus run separately.

## Frozen versions

| Component | Pin |
| --- | --- |
| D2 | Public commit `a825194903523c4409f4df7e7f4385efacb6deeb` |
| Go | 1.27.0 |
| Node.js | 24.19.0 |
| Mermaid CLI | 11.17.0 |
| Mermaid | 11.17.2 |
| Puppeteer | 25.10.0 |
| Chrome Headless Shell (Chrome for Testing) | 152.0.7977.75 |
| Graphviz | 14.1.2 |
| OpenJDK | 21.0.10 |
| PlantUML | 1.2026.8 |
| Micromamba | 2.9.0 |

`runtime/pins.json` contains exact download URLs and SHA-256 checksums for the public D2 source archive, Go, Node, Chrome Headless Shell, PlantUML, and micromamba. Each native package in `runtime/locks/<platform>.json` also has its URL, version, build, SHA-256, and MD5. Setup verifies SHA-256 **before** handing local archives to micromamba. The adjacent explicit lock files are human-readable references to the same packages. The installer uses no dependency solve or floating channel versions.

`runtime/package-lock.json` freezes npm dependencies and their registry integrity hashes; installation uses `npm ci --ignore-scripts`. Mermaid CLI 11.17.0 defaults to Puppeteer's `headless: "shell"` mode, so its executable is the separately pinned **Chrome Headless Shell**. The browser variant matters for fresh-process startup time. Setup checks the installed CLI's active launch default against the pinned executable variant and records both in provenance. Puppeteer does not download a browser during npm installation. `config/mermaid-dagre.json` explicitly selects Mermaid's Dagre renderer.

D2 is compiled from the checked source archive using `CGO_ENABLED=0 go build -trimpath -ldflags="-s -w"`. The pinned Go toolchain runs with `GOTOOLCHAIN=local`; downloaded Go modules are verified by the source `go.sum` and Go's public checksum database. Build and installation time are outside measured runs.

## Generated configuration and evidence

`.tools/toolchain.json` contains absolute executable paths, per-tool runtime environment, version commands, and provenance. It is local generated configuration and must not be committed. `.tools/setup-manifest.json` records the pins, lock hashes, actual version output, installed native packages, and smoke status. `.tools/setup.log` retains exact installation and smoke commands plus their diagnostics.

Graphviz's PNG output uses Cairo and its SVG output uses the native SVG renderer; verbose smoke diagnostics record the selected plugins. PlantUML is configured with the same Graphviz executable through `GRAPHVIZ_DOT`. Each invocation starts a fresh JVM and uses `-DPLANTUML_LIMIT_SIZE=32768` to permit the substantial fixtures. The limit does not rescale the graph.

Native font/rendering dependencies are in the platform locks. Platform font selection is still relevant: macOS CoreText, Linux Fontconfig, and the host's available fonts can change glyph measurements and image dimensions. The dependency pins do not promise identical pixels or timings across operating systems.

## Reuse and alternate directories

`./make.sh` reuses the completed setup without reinstalling. Running `python3 scripts/setup.py` explicitly reuses verified downloads, reinstalls locked npm packages, rebuilds D2 using its local build cache, and repeats all smoke renders. Incomplete setup is retried on the next launcher invocation. If pins change, setup asks for a fresh generated tools directory instead of silently mixing revisions.

An alternate tools directory and a reusable cache are optional:

```sh
python3 scripts/setup.py --tools-dir .tools-other --cache-dir .benchmark-cache
python3 -m benchmarks doctor --toolchain .tools-other/toolchain.json
./make.sh --toolchain .tools-other/toolchain.json
```

Do not run setup concurrently against one tools/cache directory. Deleting a generated tools directory removes its installed tools; a separately chosen cache remains available for reuse.

TALA is optional and is not downloaded or configured by setup. Add a separately obtained executable to a local toolchain file using the documented `d2-tala` schema. The public setup does not require access to a private repository.

## CI scope

The workflow runs Python tests, corpus validation, a fresh Linux tool setup, and all three basic fixtures plus one real-world fixture through all four CLIs in both output formats. A second launcher invocation checks setup reuse and basic-size selection. On its ephemeral Ubuntu runner it enables sandbox user namespaces using the same sysctl setting as [Puppeteer's upstream CI](https://github.com/puppeteer/puppeteer/blob/main/.github/workflows/ci.yml); this is separate from the local setup script. Version pins and native execution failures are correctness checks. Shared-runner durations are retained as diagnostics and are never used as a performance threshold or a published benchmark result.

Download sources: [Go releases](https://go.dev/dl/), [Node.js releases](https://nodejs.org/dist/), [Chrome for Testing](https://developer.chrome.com/docs/automation-and-testing/chrome-for-testing), [Micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html), [Graphviz downloads](https://graphviz.org/download/), and [PlantUML releases](https://github.com/plantuml/plantuml/releases/tag/v1.2026.8).
