# Third-party component attribution audit — preliminary

This is a **non-exhaustive file-level review**, not a software bill of materials or licence-certification report. All licence notices found in the actual source override any oversimplified summary.

| Identified file or component | Evidence in uploaded snapshot | Status / action |
| --- | --- | --- |
| simdjson inherited implementation and documentation | README, historical authors, original root Apache and MIT texts; 690 upstream-matching blobs relative to v5.0.3 | Apache-2.0 and/or MIT rights retained; inspect all inherited file-specific notices |
| `include/simdjson/nonstd/string_view.hpp` | Source header identifies Martin Moene and **Boost Software License 1.0** | Preserve full relevant third-party licence notice and verify whether a separate full Boost licence text should be bundled |
| `include/simdjson/internal/fast_float.h` | Header says vendored `fast_float` 8.2.10 and **Apache-2.0 OR MIT OR BSL-1.0** | Preserve attribution and review vendoring script and full text requirements |
| `windows/dirent_portable.h` and Windows dirent implementation, if distributed | Upstream README documents MIT licensing for the directory compatibility code | Verify actual vendored implementation header(s), not just wrapper |
| Dragonbox-derived serialization logic, if present | Upstream README reports Apache-2.0 with LLVM exceptions or Boost | Pin exact version/path and retain the corresponding exception/notice |
| PyTorch-origin runtime dispatch code, if present | Upstream README reports BSD 3-Clause | Locate exact source portion and include conditions/attribution |
| RVV additions and lab tools | Additional paths, provenance presently unverified | Not automatically proprietary merely because they are absent from upstream |

Before claiming full compliance: produce SBOM/REUSE report, enumerate all vendored sources, capture source commit and licence hash, inspect license headers and original source links, and obtain legal review of mixed-origin patch ownership. Existing `LICENSE-MIT`, `engine/LICENSE`, `engine/LICENSE-MIT`, and `THIRD_PARTY_LICENSES/` must not be silently removed or altered.
