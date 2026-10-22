# Get Started - Edge Pack

The recommended installation method is using Edge Pack TUI Installer, a terminal-based wizard
that detects your platform and OS and guides you through the process. No need for hand-crafting
`apt` commands or configuring the repository. To start, follow the steps:

1. Download the package: [Releases](https://github.com/open-edge-platform/edge-pack/releases).
2. Run the installer.

   ```bash
   sudo chmod +x ./edgepack-installer
   sudo ./edgepack-installer
   ```
3. Go through a 4-step wizard.

   - **Profile selection**: choose your base profile (standard or realtime kernel) and detect
     your hardware platform.
   - **Add-on packages**: select optional add-on profiles to install alongside the base.
   - **Installation summary**: review compatibility warnings and confirm what will be installed.
   - **Installation**: live progress as packages are downloaded and installed via `apt`.

   | Keyboard Navigation              | Action                                            |
   |----------------------------------|---------------------------------------------------|
   | `Tab` / `Shift+Tab`              | Move focus between sections                       |
   | `↑` / `↓`                        | Move between items within a list (Step 2 add-ons) |
   | `←` / `→`                        | Move between buttons                              |
   | `Space`                          | Toggle a checkbox / press the focused button      |
   | `Enter`                          | Press the focused button                          |
   | `Ctrl+Q`                         | Quit                                              |



Learn more [about the installer](.get-started/tui-installer.md) or see what the process looks
like in the video:

https://github.com/user-attachments/assets/ef562165-f427-434d-a472-1244b3e430f6

A checksum is published with the binary, so you can verify the download integrity:

```bash
sha256sum -c edgepack-installer.sha256
```


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