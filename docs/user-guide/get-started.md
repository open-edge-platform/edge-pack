<!--hide_directive ```{eval-rst}
.. meta::
   :description: Choose and start an Edge Pack installation method using the TUI installer, installer CLI, or APT.
   :keywords: Edge Pack, get started, installation, TUI, installer CLI, APT
``` hide_directive-->

# Get Started - Edge Pack

To deploy Edge Pack, make sure your setup meets the [system requirements](./get-started/system-requirements.md).

Edge Pack supports three installation methods, all using the compatibility, repository, and
package definitions in `edgepack-installer/data/edgepacks-template.yml`. Select the
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
	style="width: 100%; min-width: 350px; border: 0; overflow: hidden;"
	title="Install Edge Pack"
></iframe>
hide_directive-->

















> [!WARNING]
> It is advisable to install Edge Pack on a freshly installed [Ubuntu Linux](https://releases.ubuntu.com/).
> Before installing, make sure your setup meets the [system requirements](./get-started/system-requirements.md).
> Ubuntu 24.04.4's default base Kernel is 6.17. Upgrade it to Kernel 7.0 manually:
>
> ```
> $ sudo apt-get update
> $ sudo apt install -y linux-generic-7.0
> $ sudo reboot
> ```

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