# Real-world diagram corpus

Ten documented projects, **346 leaf nodes, 140 groups, and 195 edges** in total. The sources are D2-authored, so this is a deliberately transparent workload collection, not a random or tool-neutral sample.

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

- [Provenance](PROVENANCE.md): exact upstream revisions, source hashes, context, and adaptations.
- [Licenses](LICENSES.md): original MIT/Apache-2.0 terms and attribution.
- [Translations and validation](TRANSLATIONS.md): retained semantics, rendering differences, and regeneration instructions.
- [Machine-readable manifest](manifest.json): all frozen source/map/license hashes and primary/supplemental PNG classification.

The four source directories are `d2/`, `mermaid/`, `graphviz/`, and `plantuml/`. Semantic mappings are in `semantic/`. They retain full plain-text labels, hierarchy, edge endpoints and multiplicity, and visible arrow direction. The diagrams use local or built-in shapes in place of fragile external image dependencies. SVGs still differ in fonts, typesetting, layout, styling, and metadata; inspect the generated gallery before drawing conclusions about visual quality.

From the repository root, run `python3 -m benchmarks validate` to check integrity and translated source semantics without installing a renderer. Each SVG render is separately validated after its measured process exits.
