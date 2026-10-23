# Edge Pack

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

Edge Pack is a set of modular platform software packages that installs key
functionality for your operating system, including graphics, media, edge AI,
networking, and manageability. Install Edge Pack with the interactive
text-based installer (TUI), the installer CLI, or the native APT package
management process.

Edge Packs are grouped into technical domain areas so you can install the
capabilities needed for a particular system or workload.

*<mark>**[!NOTE]**</mark> Edge Pack is currently available as a **Tech Preview**.*

## What Edge Pack Provides

- **Base profiles** — the validated core package set for a given platform and OS, forming the required foundation before any add-on can be installed
- **Add-on profiles** — optional package groups layered on top of a base profile, each enabling a specific Intel platform capability
- **Platform and OS validation** — every profile and add-on is validated against specific hardware models, Ubuntu versions, and kernels, so only combinations Intel has tested are offered
- **Compatibility checks** — conflicting or unsupported combinations are flagged before anything is installed

### Base Profiles

| Profile | Name | Description |
|---|---|---|
| `base-standard` | Intel Edge Base Profile | Graphics and media software with AI compute support |

### Add-on Profiles

| Profile | Name | Description |
|---|---|---|
| `ffmpeg` | FFmpeg | FFmpeg multimedia framework with Intel GPU support |
| `gstreamer` | GStreamer | GStreamer multimedia framework with Intel GPU support |
| `npu` | NPU | Software to enable Intel's Neural Processing Unit (NPU) on Edge platforms |
| `manageability` | Manageability | Software to enable Intel vPro manageability on Edge platforms |


## Supported Platforms

| Ecosystem | Support |
|---|---|
| Platform | Intel Panther Lake (PTL), Intel Wildcat Lake (WCL) |
| Linux Distro | Ubuntu 24.04 (Desktop), Ubuntu 26.04 (Desktop) |
| Kernel | Ubuntu Kernel 7.0+ generic, Ubuntu Kernel 7.0+ real-time (Ubuntu 26.04 only) |

### Supported SKUs

| Platform | Supported SKUs (CPU model) |
|---|---|
| Intel Panther Lake (PTL) | 338H, 358H, 356H, 368H, 388H, 325H, 345H, 355H, 375H |
| Intel Wildcat Lake (WCL) | 304, 305, 310, 320, 330, 350 |

## Getting Started

Start with the [installation overview](docs/user-guide/installation/index.md)
to choose an installation method for the target system.

Three installation methods are available:

| Method | Best for | Guide |
| --- | --- | --- |
| TUI installer | Guided, interactive installations | [Install with the TUI](docs/user-guide/installation/tui.md) |
| Installer CLI | Automation with installer compatibility checks | [Install with the installer CLI](docs/user-guide/installation/installer-cli.md) |
| APT | Native package management and provisioning workflows | [Install with APT](docs/user-guide/installation/apt.md) |

The TUI installer is recommended for most users. It detects the platform and OS,
then guides you through profile selection, add-ons, a summary, and installation
progress.

```bash
# 1. Verify the downloaded binary against its published checksum
sha256sum -c edgepack-installer.sha256

# 2. Run the interactive wizard
sudo ./edgepack-installer
```

See the [installation overview](docs/user-guide/installation/index.md) for system
requirements and a comparison of the methods. To convert a supported Ubuntu
Desktop installation to a console-only system, see the
[headless Ubuntu guide](docs/user-guide/ubuntu-desktop-remove-display.md).

The following video demonstrates the TUI workflow:

https://github.com/user-attachments/assets/ef562165-f427-434d-a472-1244b3e430f6

## Contribute

Read the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting issues and pull requests.

## Community and Support

For support, submit your bug report and feature request to [Github Issues](https://github.com/open-edge-platform/edge-pack/issues).

## License Information

Edge Pack is licensed under the [MIT License](LICENSE.txt).
