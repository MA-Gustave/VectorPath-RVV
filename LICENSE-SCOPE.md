# VectorPath-RVV — authoritative rights map

**Mixed-origin derivative of simdjson v5.0.3; not an official simdjson release.** This map is authoritative for the publishing package together with `LICENSE`. Earlier licences and source-specific notices take precedence for content already covered by them.

| Content / source range | Known or provisional licence status | Requirement |
| --- | --- | --- |
| Identical upstream simdjson code, including the unmodified inherited majority | Upstream Apache-2.0 **or** MIT, as applicable | Preserve original licence, attributions and third-party notices; upstream reuse remains permitted by applicable terms |
| Fork changes already published under MIT/Apache-2.0 or another broad grant | The permissions actually granted at time of publication; **not retrospectively withdrawable** | Research release history and file/commit terms; do not assert a new restriction |
| Source files modified in the inherited core (`include/`, `src/`, `tests/`, build scripts) | Mixed origin; segments require patch-level history | Preserve upstream licences and identify any separately controlled original segments |
| `src/rvv/`, `include/simdjson/rvv/`, `scripts/rvv/`, `tests/rvv/`, RVV-specific toolchains | **Potentially original additions, UNVERIFIED**; differing from an upstream tag is not proof of title or first licence | Check actual human authorship, external influences, first release, applicable GitHub-root licence and every earlier grant |
| **Future** separable independently authored and rights-controlled additions, designated before publication and recorded in `PROVENANCE-ADDITIONS.md` | Custom reserved notice `LicenseRef-MA-Gustave-Restricted-2026` only if each eligibility condition is met | No unlicensed reuse; explicit prohibition of incorporation into official simdjson, subject to legal limits |
| Third-party embedded code (`fast_float`, `nonstd/string_view.hpp`, Dragonbox, PyTorch-derived or other actual code) | Respective third-party licences | Inventory and retain exact licence notices, including Boost/BSD/Apache LLVM-exception terms where present |
| Historic upstream `AUTHORS`, `CONTRIBUTORS`, `HACKING.md`, `README` content | Attributions and historical documentation; no upstream endorsement | Preserve credit, clearly separate project-specific policies and identity |

The Apache-2.0 full text formerly at root is preserved verbatim at `THIRD_PARTY_LICENSES/simdjson-Apache-2.0.txt`; its MIT counterpart remains at `LICENSE-MIT` and in `THIRD_PARTY_LICENSES/simdjson-MIT.txt`. Do not alter either licence text. `LICENSE` is now an explanatory *mixed-origin* notice, not a purported rewriting of Apache 2.0.

## Evidence comparison (14 October 2026)

The GitHub tree at `MA-Gustave/VectorPath-RVV` compared to the **upstream simdjson v5.0.3 tree** contained **690 identical files, 13 modified files at shared paths, and 75 files at new paths** (blob-SHA comparison). These categories show source differences, **not ownership**. The uploaded snapshot omits its prior Git history. No presently published source segment is certified as a newly rights-restricted Covered Addition solely by this analysis.

If the objective is enforceable exclusivity against upstream reuse, develop **genuinely new, separable changes privately**, verify rights and previous grants, decide on the proprietary notice *before first release*, mark the exact file/patch, and preserve evidence. For already published additions, obtain a legal evaluation of the precise historical grants; do not assume a later notice cures them.
