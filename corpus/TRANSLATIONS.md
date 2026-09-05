# Translation and validation boundaries

The ten diagrams contain **486 semantic objects: 346 leaves and 140 groups, with 195 connections**. Every format retains those identities, nesting relationships, parallel edges and plain text labels. The semantic maps were captured after D2 compilation expanded implicit objects, scoped identifiers, classes and globs; they are not a regular-expression interpretation of D2 source. The mappings include the source-D2 hash and full source attributes.

D2 retains its source diagrams and styles. Mermaid, DOT and PlantUML translate the same content with the following deliberate limitations. They are comparable real-world CLI workloads, not pixel-equivalent renderers or isolated measurements of a single layout algorithm.

| Behavior | Mermaid | Graphviz DOT | PlantUML |
|---|---|---|---|
| Containers | Nested subgraphs | Nested clusters | Aliased nested deployment groups |
| Container endpoints | Native Mermaid syntax | 55 small invisible representatives, no added edges; 65 edges clipped with `lhead`/`ltail` | Native PlantUML group syntax; internal layout implementation remains PlantUML's responsibility |
| Person | Labeled circle | Labeled circle | Person shape |
| Queue | Horizontal cylinder | Vertical cylinder | Queue shape |
| Cylinder container | Subgraph | Rectangular cluster | Database group |
| Text-only shape | Transparent rectangle | Plain text | Transparent rectangle |
| Markdown | Same frozen plain multiline labels in all translations | Same | Same |
| Grids/manual placement | Approximate grid direction; explicit sizes/near positions omitted | Grid/manual constraints omitted | Grid/manual constraints omitted |
| Local direction | Emitted, but Mermaid can ignore it when children connect outside a subgraph | Omitted; one global rank direction | Omitted; root direction retained |

No translator removes edges to simplify routing, merges repeated nodes, drops parallel edges, or removes labels. DOT is a non-strict directed graph. Invisible DOT representatives are empty, 0.01-inch points; they remain layout work in timed commands. No synthetic DOT edges are added. Native Graphviz's compound-edge mechanism is documented under [compound](https://graphviz.org/docs/attrs/compound/) and [lhead](https://graphviz.org/docs/attrs/lhead/).

Common colors, font sizes and ordinary dashed strokes are mapped where each format supports them. Exact font metrics, D2 themes, manual wrapping, numeric corner radii, shadows, fill patterns, stacked/multiple decorations and double borders are not equivalent. DOT uses Helvetica with 14-point defaults. PlantUML uses ordinary deployment styling with shadowing disabled. Mermaid group font overrides are omitted because its label measurement can clip subsequently enlarged labels; leaf/edge styles remain. Per-object omissions are recorded in `semantic/*.mapping.json` for Mermaid and in the `semantic/graphviz` / `semantic/plantuml` mappings for those tools.

D2's source-only arrow in Mocha becomes a reversed Mermaid statement; semantic source/target metadata remains unchanged. OIDC's five `target-arrowhead.shape: none` overrides become unheaded lines. There are 210 enabled arrowhead geometries but **208 painted arrowheads**: Mocha includes a transparent bidirectional connection that remains part of layout. Native DOT serializes its two transparent arrow shapes; PlantUML omits their painted polygons.

ROSS and Lion include link/tooltip metadata that remains in the semantic maps. The translated assets omit that interactive metadata and do not append its text. D2 PNG may append that metadata, increasing its content, dimensions and work. Sources contain no runtime icon downloads, image dependencies or imports. URLs in comments, ordinary links and text are not downloaded while rendering.

## Offline validation

`benchmarks.corpus.validate_corpus` checks the complete four-format source set, all declared hashes, license/provenance records, object identity and acyclic containment, edge endpoints/multiplicity, mapping consistency, and the generated Mermaid/DOT/PlantUML statements themselves. It parses only the translators' declared subset and rejects unknown statements. Frozen D2 hashes tie those source files to the compiler-derived semantic graph; the fast check does not recompile D2.

`benchmarks.corpus.validate_svg` audits actual output XML after each SVG command, outside its timer:

- D2: all semantic object/edge wrappers appear exactly once, with finite connection paths. This check does not assert its rich-text typography or layout quality.
- Mermaid: rendered object/edge identities, multiplicity, plaintext labels, endpoints, enabled markers and finite routes. Generated numeric edge suffixes can be nonconsecutive; parallel edges are compared as labeled endpoint/arrow multisets.
- DOT: every semantic object and edge ID, exact plaintext label lines, endpoint identities, enabled arrow polygons and finite routes, with no visible endpoint representatives.
- PlantUML: every object identity/kind, immediate parent, edge source-line identity, endpoint/label/multiplicity, finite painted route, arrow count and direction. Transparent layout links are retained as semantic links without requiring a painted route.

These are output-integrity checks, not visual-quality scores. Missing content fails validation instead of becoming a faster benchmark result. The adapters recognize the pinned versions' output conventions; changing renderer versions may require revising them. PNG integrity and dimensional checks are handled by the runner; they do not replace the semantic SVG audit.

For a stronger DOT check, the separate native audit invokes `dot -Tjson` and `dot -Tsvg` to verify parsed cluster membership and actual edge endpoints on the intended cluster borders. It accepts the configured toolchain's executable argument vector and environment. It is not run inside timed repetitions.

## Regeneration

From the repository root, choose an output directory that does not exist:

```sh
python3 scripts/translations/regenerate.py --output /tmp/d2-bench-generated
```

This regenerates all 30 translated inputs from the frozen compiler-derived maps and verifies their hashes against the corpus. It uses only Python's standard library. It does not overwrite the checked-in corpus or its manifest. The maps retain sufficient original compiler attributes to reconstruct the Mermaid translation and feed the DOT/PlantUML translators.

To rebuild semantic maps after changing D2 inputs, `scripts/translations/export.go` calls D2's actual compiler. Run it from a chosen public D2 module checkout, passing an output directory and the D2 input files; then use `mermaid_from_compiler.py` with that graph directory, the fixture directory and a new output directory. Review all semantic and rendering differences before replacing the corpus and hashes. The helper records source basenames, not local checkout paths.

The native Graphviz audit can be run separately:

```sh
python3 scripts/translations/validate_graphviz_native.py \
  --source corpus/semantic --input corpus/graphviz \
  --toolchain .tools/toolchain.json --output /tmp/d2-bench-dot-validation
```

All scripts use caller-supplied paths or repository-relative defaults. No previous user's tool paths, private source code, timing results or rendered outputs are distributed with this corpus.
