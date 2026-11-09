<!--hide_directive ```{eval-rst}
.. meta::
   :description: Choose and start an Edge Pack installation method using the TUI installer, installer CLI, or APT.
   :keywords: Edge Pack, get started, installation, TUI, installer CLI, APT
``` hide_directive-->

# Get Started - Edge Pack

To deploy Edge Pack, make sure your setup meets the [system requirements](./get-started/system-requirements.md).

Edge Pack supports three installation methods, all using the compatibility, repository, and
package definitions in the [installer manifest](https://github.com/open-edge-platform/edge-pack/blob/main/edgepack-installer/data/edgepacks-template.yml). Select the
installation method best suited to your setup using the form below, or compare them here:

| Method                                      | Host validation | Interactive | Intended use |
| ------------------------------------------- | --------------- | ----------- | --- |
| [TUI installer](get-started/install-tui.md) | Yes             | Yes         | Recommended for individual systems |
| [Installer CLI](get-started/install-cli.md) | Yes             | No          | Automated installation with guardrails |
| [APT](get-started/install-apt.md)           | No              | No          | Native package management and provisioning workflows |

The TUI and installer CLI resolve packages and prerequisites identically. APT installation
exposes every repository and package command, so the operator is responsible for selecting
a supported combination.

<!--hide_directive
<script type="module" crossorigin src="../../_static/edgepack-installer-files/iframe-resizer.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<iframe
	id="installerFrame"
	src="../../_static/edgepack-installer-files/selector.html"
	style="width: 100%; min-width: 0; border: 0; overflow: hidden;"
	title="Install Edge Pack"
></iframe>
hide_directive-->

















> [!WARNING]
> Start with a fresh Ubuntu 24.04.5.1 or Ubuntu 26.04.1 Desktop installation on a
> supported Panther Lake or Wildcat Lake platform. Confirm the
> [system requirements](./get-started/system-requirements.md), including the
> Ubuntu kernel requirement, before installing.

These public installation instructions use Intel's signed APT repository at
<https://apt.repos.intel.com/edgepack/> and the
[public installer releases](https://github.com/open-edge-platform/edge-pack/releases).

Updating Ubuntu to the latest Stable Release Update (SRU) kernel is optional
when the ISO's kernel already meets the system requirements. To update:

```bash
sudo apt update
sudo apt upgrade
sudo reboot
```

Skip this upgrade if you intend to retain the supported kernel supplied by the ISO.

For console-only deployments, complete the installation first, then follow
[Convert Ubuntu Desktop to Behave Like Ubuntu Server](./ubuntu-desktop-remove-display.md).

<!--hide_directive
:::{toctree}
:hidden:

System Requirements <./get-started/system-requirements.md>
Install with the TUI <./get-started/install-tui.md>
Install with the Installer CLI <./get-started/install-cli.md>
Install with APT <./get-started/install-apt.md>
:::
hide_directive-->