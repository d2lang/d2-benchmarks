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

To measure TALA, provide a D2-compatible executable with that layout available and use `argv: ["/absolute/path/to/d2", "--layout", "tala"]`, `kind: "d2"`, and a separate ID such as `d2-tala`. Record its version, source/build provenance where available, seed configuration, and any plugin path in `env`. The repository neither distributes nor fetches private implementations. Compare against the same D2 binary's Dagre mode when isolating layout choice, and make that distinction explicit in your report.

Other supported kinds are `mermaid`, `graphviz`, and `plantuml`. The runner appends source/output/format/density arguments according to the kind. Start from setup's working definitions, preserve required headless/browser/Graphviz settings, and test SVG and PNG before a full run. A version command is run before timing; explicit file hashes are recorded separately from self-reported version strings.

Ambient `D2_*`, Node and JVM option variables and selected global diagram switches are cleared by the runner. Explicit `env` entries in the toolchain take precedence and are therefore part of your experiment. Do not place credentials in a toolchain or published run.
