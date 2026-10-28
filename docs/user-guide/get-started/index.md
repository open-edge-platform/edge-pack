# Install Edge Pack


## Choose an installation method

| Method | Host validation | Interactive | Intended use |
| --- | --- | --- | --- |
| [TUI installer](install-tui.md) | Yes | Yes | Recommended for individual systems |
| [Installer CLI](install-cli.md) | Yes | No | Automated installation with guardrails |
| [APT](install-apt.md) | No | No | Native package management and provisioning workflows |

The TUI and installer CLI resolve packages and prerequisites identically. APT
installation exposes every repository and package command, so the operator
is responsible for selecting a supported combination.

## Requirements

- A supported Intel Panther Lake or Wildcat Lake processor
- Ubuntu 24.04 or Ubuntu 26.04 Desktop
- Ubuntu kernel 7.0 or later
- Administrative privileges and network access to the configured repositories

Consult the [project README](../../../README.md#supported-platforms) for the current
platform and SKU matrix. The manifest remains authoritative when a guide and a
released installer differ.

Ubuntu 24.04 installations below the required kernel level must upgrade before
installing Edge Pack:

```bash
sudo apt-get update
sudo apt-get install -y linux-generic-7.0
sudo reboot
```

For console-only deployments, complete the installation first, then follow
[Convert Ubuntu Desktop to Behave Like Ubuntu Server](../ubuntu-desktop-remove-display.md).

## Verify release downloads

The selector downloads the installer and its published SHA-256 checksum from
the latest GitHub release. Always verify the binary before running it:

```bash
sha256sum -c edgepack-installer.sha256
```

Do not run the installer when its checksum does not match.
