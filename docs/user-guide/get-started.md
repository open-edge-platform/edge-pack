# Get Started - Edge Pack

To deploy Edge Pack, make sure your setup meets the [system requirements](./get-started/system-requirements.md)

Edge Pack supports three installation methods, all using the compatibility, repository, and
package definitions in `/edgepack-installer/data/edgepacks-template.yml`.
Select the installation method best suited to your setup using the form below. You can also
learn more about each method in the following installation guides:

- [Install with the TUI](get-started/install-tui.md)
- [Install with the installer CLI](get-started/install-cli.md)
- [Install with APT](get-started/install-apt.md)


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
> Before installing, make sure your setup meets (System Requirements)[./get-started/system-requirements.md].
> Ubuntu 24.04.4 default base Kernel is 6.17, upgrade it to Kernel 7.0 manually:
> ```
> $ sudo apt-get update
> $ sudo apt install -y linux-generic-7.0
> $ sudo reboot
> ```

<!--hide_directive
:::{toctree}
:hidden:

Install with Terminal User Interface <./get-started/tui-installer.md>
System Requirements <./get-started/system-requirements.md>
:::
hide_directive-->