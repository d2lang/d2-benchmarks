# Diagram workloads

Three basic sizes and ten real-world diagrams provide separate performance workloads, each rendered to SVG and PNG. Basic sizes are reported individually; they are not pooled into a scaling score or mixed with real-world diagrams.

## Basic diagrams

| Fixture | Nodes | Groups | Edges | Structure |
|---|---:|---:|---:|---|
| `basic_002` | 2 | 0 | 1 | Balanced binary tree |
| `basic_010` | 10 | 0 | 9 | Balanced binary tree |
| `basic_100` | 100 | 0 | 99 | Balanced binary tree |

These graphs are generated from a tool-neutral model: breadth-first node IDs, parent `(i - 1) // 2` for node `i > 0`, labels `Node 000` through `Node 099`, rectangular nodes, downward direction, and unlabeled directed edges. There are no groups, layout constraints, icons, or manually assigned dimensions. All four formats retain that topology and those labels. Renderer defaults still differ. A balanced tree is one controlled topology, not a representative sample of every graph of that size; the 100-node case is a larger basic graph, not a substitute for the real-world diagrams.

## Real-world complex diagrams

Ten documented projects contain **346 leaf nodes, 140 groups, and 195 edges** in total. These sources are D2-authored, so this part of the corpus is not a random or tool-neutral sample.

| Fixture | Context | Leaves | Groups | Edges |
|---|---|---:|---:|---:|
| `fulcro_rad` | Application architecture | 19 | 6 | 16 |
| `jupyter_aws_eks` | AWS EKS infrastructure | 12 | 12 | 4 |
| `jupyter_k8s_oidc` | Kubernetes authentication | 23 | 10 | 17 |
| `leios_simulator` | Simulation components | 20 | 5 | 18 |
| `lion_reader_frontend` | Feed-reader frontend | 19 | 7 | 16 |
| `mocha_soc` | Secure-enclave SoC | 34 | 4 | 18 |
| `queue_workers` | Multi-service worker architecture | 23 | 10 | 23 |
| `ross_overview` | Rotor-dynamics package | 24 | 3 | 14 |
| `spyre_encoder` | Inference target architecture | 32 | 35 | 6 |
| `tpmjs_architecture` | Package execution platform | 140 | 48 | 63 |

- [Provenance](PROVENANCE.md): deterministic basic generation and exact upstream revisions, source hashes, context, and adaptations.
- [Licenses](LICENSES.md): generated fixture MIT terms and original MIT/Apache-2.0 terms and attribution.
- [Translations and validation](TRANSLATIONS.md): retained semantics, rendering differences, and regeneration instructions.
- [Machine-readable manifest](manifest.json): all frozen source/map/license hashes and primary/supplemental PNG classification.

The four source directories are `d2/`, `mermaid/`, `graphviz/`, and `plantuml/`. Semantic mappings are in `semantic/`. They retain full plain-text labels, hierarchy, edge endpoints and multiplicity, and visible arrow direction. The diagrams use local or built-in shapes in place of fragile external image dependencies. SVGs still differ in fonts, typesetting, layout, styling, and metadata; inspect the generated gallery before drawing conclusions about visual quality.

From the repository root, run `python3 -m benchmarks validate` to check integrity and translated source semantics without installing a renderer. Each SVG render is separately validated after its measured process exits.
