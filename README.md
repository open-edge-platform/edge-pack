# Edge Pack

Edge Pack is a curated collection of Intel-validated software packages and drivers that unlock specific Intel platform capabilities — such as graphics and media acceleration, the Neural Processing Unit (NPU), platform manageability, and real-time kernel support — on top of stock Ubuntu LTS installations. Rather than hunting down individual drivers, PPAs, and kernel packages and figuring out how they fit together, EdgePack packages them into validated, ready-to-install profiles for supported Intel platforms.

## What Edge Pack Provides

- **Base profiles** — the validated core package set for a given platform and OS, forming the required foundation before any add-on can be installed
- **Add-on profiles** — optional package groups layered on top of a base profile, each enabling a specific Intel platform capability
- **Platform and OS validation** — every profile and add-on is validated against specific hardware models, Ubuntu versions, and kernels, so only combinations Intel has tested are offered
- **Compatibility checks** — conflicting or unsupported combinations are flagged before anything is installed

## Supported Platforms

| Ecosystem | Support |
|---|---|
| Platform | Intel Panther Lake (PTL), Intel Wildcat Lake (WCL) |
| Linux Distro | Ubuntu 24.04 (Desktop), Ubuntu 26.04 (Desktop) |
| Kernel | Ubuntu Kernel 7.0+ generic, Ubuntu Kernel 7.0+ real-time (Ubuntu 26.04 only) |

## Getting Started

The recommended way to install Edge Pack is through the Edge Pack TUI Installer, a terminal-based wizard that detects your platform and OS, then guides you through profile selection, add-on packages, an installation summary, and live installation progress — without requiring you to hand-craft `apt` commands or repository configuration yourself.

## Contribute

Read the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting issues and pull requests.

## Community and Support

For support, submit your bug report and feature request to [Github Issues](https://github.com/open-edge-platform/edge-pack/issues).

## License Information

License information for Edge Pack will be published here.
