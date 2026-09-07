# d2-benchmarks

**Results — September 7, 2026 (UTC) · Apple M4 · milliseconds**

| Workload | Format | D2 / Dagre | D2 / TALA | Mermaid / Dagre | Graphviz / dot | PlantUML / Graphviz |
|---|---|---:|---:|---:|---:|---:|
| Basic · 2 nodes | SVG | **17.8** | 21.2 | 355.9 | 66.1 | 891.5 |
| Basic · 2 nodes | PNG 2× | **20.2** | 24.8 | 398.1 | 66.8 | 936.2 |
| Basic · 10 nodes | SVG | **18.3** | 20.9 | 370.4 | 67.6 | 903.6 |
| Basic · 10 nodes | PNG 2× | 41.5 | **35.0** | 423.5 | 85.4 | 992.2 |
| Basic · 100 nodes | SVG | **26.5** | 98.1 | 510.8 | 68.9 | 957.8 |
| Basic · 100 nodes | PNG 2× | 523.9 | 343.0 | 747.3 | **313.4** | 1,364.9 |
| Real-world complex | SVG | **29.3** | 115.8 | 431.4 | 78.3 | 943.1 |
| Real-world complex | PNG 2× | 327.6 | 373.3 | Does not render | 396.1 | 1,651.5 |

Time to start the CLI, render a diagram, write the output, and exit—including browser or JVM startup. **Bold is the lowest observed time.** Each result uses 20 runs after 3 warm-ups. Basic rows are medians; real-world rows are geometric means of per-diagram medians.

The real-world set contains ten diagrams originally written in D2, including TPMJS. All PNGs use 2× density. Layouts and image dimensions differ between tools. These numbers come from one desktop session with uncontrolled background activity.

Mermaid's TPMJS PNG omits content at 2×, so its PNG average is unavailable and that row is unranked.

Both D2 layouts use public D2 `52a59749a4e4`; TALA uses fixed seeds `1,2,3`. [Reference data](reference/README.md) · [Methodology](docs/METHODOLOGY.md).

## Run it

```sh
git clone https://github.com/d2lang/d2-benchmarks.git
cd d2-benchmarks
./make.sh
```

Supports macOS on Apple silicon and Ubuntu 24.04 on x86-64. The script downloads pinned tools on first use, then runs all 13 diagrams in SVG and PNG with all five configurations above. D2 includes TALA. Allow about 30 minutes, plus first-time setup. Open the printed `index.html` path for results and diagrams.

Use `./make.sh --help` to choose tools, formats, or diagrams. Run on an idle machine.

[Setup](docs/SETUP.md) · [Diagram sources](corpus/README.md) · [Contributing](CONTRIBUTING.md)
