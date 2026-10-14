# Embedded JSON engine — RVV-VLA Lab

This directory contains an experimental, **modified derivative of simdjson** for research on RISC-V vectors and adaptive parser configurations. It is maintained as part of `RVV-VLA-Lab`, **not** as an official release or upstream development branch.

For Lab-specific use, tests and benchmarks, read the [Lab README](../README.md), the [licence scope](../LICENSE-SCOPE.md), the [contribution policy](../CONTRIBUTING.md), and the [original-additions register](../PROVENANCE-ADDITIONS.md).

## Licence and attribution — mandatory notices retained

Inherited simdjson source remains available under its applicable [Apache License 2.0](LICENSE) and/or [MIT licence](LICENSE-MIT). The historic [authors](AUTHORS), [contributors](CONTRIBUTORS), source-level notices and any other applicable third-party notices remain intact. This short technical description does not replace any of those notices.

Embedded third-party material may be governed by separate conditions, including Boost-licensed string-view compatibility components, the Dragonbox binary-to-decimal implementation (Apache 2.0 with LLVM exceptions and/or Boost as applicable), and PyTorch-origin code under BSD-3-Clause where included. Preserve the terms and notices carried with the actual source files.

## Development boundary

The Lab's own experimental code and legal status must be evaluated per source portion, not by assigning ownership of the entire `engine/` directory. Only *separately verified and registered* original additions may be covered by a distinct rights reservation; see the root legal documents. Already granted Apache/MIT or other rights cannot be revoked by a new README.
