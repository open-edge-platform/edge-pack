<!--hide_directive ```{eval-rst}
.. meta::
   :description: Hardware, software, and access requirements for installing Edge Pack.
   :keywords: Edge Pack, system requirements, Panther Lake, Wildcat Lake, Ubuntu, kernel
``` hide_directive-->

# Edge Pack System Requirements



**Platforms**:

- Intel® Core™ Ultra Series 3 (formerly codenamed as Panther Lake)
  - Supported CPU models: 338H, 358H, 356H, 368H, 388H, 325H, 345H, 355H, 375H
- Intel® Core™ Series 3 (formerly codenamed as Wildcat Lake)
  - Supported CPU models: 304, 305, 310, 320, 330, 350


**Software**:

- Linux Distribution:
  - Fresh Ubuntu 24.04.5.1 (Noble) Desktop installation
  - Fresh Ubuntu 26.04.1 (Resolute) Desktop installation
- Kernel Version:
  - Ubuntu Kernel 7.0+ generic

Download the Desktop ISO from the official Ubuntu release pages for
[24.04](https://releases.ubuntu.com/24.04/) or
[26.04](https://releases.ubuntu.com/resolute/).
For headless deployments, start with the supported Desktop installation, install
Edge Pack, then follow the [headless conversion guide](../ubuntu-desktop-remove-display.md).
An Ubuntu Server ISO is not a substitute for this installation workflow.

The release instructions describe realtime support only for Ubuntu 26.04.
However, the current installer manifest disables `base-realtime`, so the TUI,
installer CLI, and generated APT instructions do not currently offer that profile.
Do not install `intel-edge-base-realtime` based on the release instructions alone.

**Access**:

- Administrative privileges and network access to the configured package repositories

Edge Pack packages come from Intel's public APT repository at
<https://apt.repos.intel.com/edgepack/>. Installer binaries are published on the
[public GitHub releases page](https://github.com/open-edge-platform/edge-pack/releases).

Consult the [project README](https://github.com/open-edge-platform/edge-pack/blob/main/README.md)
for the current platform and SKU matrix. The manifest remains authoritative when this guide
and a released installer differ.

