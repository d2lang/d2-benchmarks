# d2-benchmarks

**Results — September 7, 2026 (UTC) · Apple M4 · milliseconds**

| Workload | Format | D2 / Dagre | D2 / TALA | Mermaid / Dagre | Graphviz / dot | PlantUML / Graphviz |
|---|---|---:|---:|---:|---:|---:|
| Basic · 2 nodes | SVG | **18.9** | 22.1 | 394.9 | 69.2 | 865.8 |
| Basic · 2 nodes | PNG 2× | **22.0** | 28.2 | 411.1 | 68.4 | 904.4 |
| Basic · 10 nodes | SVG | **19.8** | 22.6 | 388.5 | 71.7 | 877.3 |
| Basic · 10 nodes | PNG 2× | 42.8 | **39.9** | 469.3 | 91.8 | 981.7 |
| Basic · 100 nodes | SVG | **32.4** | 105.0 | 523.7 | 72.0 | 946.4 |
| Basic · 100 nodes | PNG 2× | 540.8 | 380.3 | 805.5 | **323.2** | 1,361.9 |
| Real-world complex | SVG | **30.8** | 125.6 | 461.1 | 80.4 | 928.7 |
| Real-world complex | PNG 2× | **269.5** | 310.3 | 723.5 | 340.1 | 1,480.2 |
| TPMJS supplement | PNG 0.5× supplement | 305.8 | 2,894.4 | 854.8 | **197.8** | 1,405.6 |

Time to start the CLI, render a diagram, write the output, and exit—including browser or JVM startup. **Bold is the lowest observed time.** Each result uses 20 runs after 3 warm-ups. Basic rows are medians; real-world rows are geometric means of per-diagram medians.

The real-world set contains ten diagrams originally written in D2. PNG uses 2× density, except TPMJS at 0.5×, shown separately. Layouts and image dimensions differ between tools. These numbers come from one desktop session with uncontrolled background activity.

D2 / Dagre uses public D2 `c058268f661a`; D2 / TALA uses the separate private staging build `3f0a4a31a0ae`. [Reference data](reference/README.md) · [Methodology](docs/METHODOLOGY.md).

## Run it

```sh
git clone https://github.com/d2lang/d2-benchmarks.git
cd d2-benchmarks
./make.sh
```

Supports macOS on Apple silicon and Ubuntu 24.04 on x86-64. The script downloads pinned tools on first use, then runs all 13 diagrams in SVG and PNG. Allow about 25 minutes, plus first-time setup. Open the printed `index.html` path for results and diagrams.

The default runs D2 / Dagre, Mermaid, Graphviz, and PlantUML. [Adding TALA](docs/CUSTOM-TOOLS.md#optional-d2--tala) requires access to the private staging build.

Use `./make.sh --help` to choose tools, formats, or diagrams. Run on an idle machine.

[Setup](docs/SETUP.md) · [Diagram sources](corpus/README.md) · [Contributing](CONTRIBUTING.md)
