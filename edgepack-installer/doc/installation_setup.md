# EdgePack Installation Setup Guide
### Requirements:
| Ecosystem | Type |
|---| ---|
| Platform | <ul><li> PTL-H </li><li> WCL-U </li></ul> |
| Linux Distro | <ul><li> Ubuntu 24.04.4++ (Desktop version)</li><li> Ubuntu 26.04.0++ (Desktop version)</li></ul> |
| Kernel | <ul><li> Ubuntu Kernel 7.0++ generic </li><li> Ubuntu Kernel 7.0++ realtime (Ubuntu 26.04 only) </li></ul> |

---
## Pre-Requisite
### > Install EdgePack on Ubuntu 24.04
1. Freshly install Ubuntu 24.04 (Desktop) from the [Ubuntu release site](https://releases.ubuntu.com/noble/) onto the supported platform as requirement above.
> [!WARNING]
> Ubuntu 24.04.4 default base Kernel is 6.17, and user need upgrade to Kernel 7.0 manually.
> ```
> $ sudo apt-get update
> $ sudo apt install -y linux-generic-7.0
> $ sudo reboot
> ```
### > Install EdgePack on Ubuntu 26.04
1. Freshly install Ubuntu 26.04 (Desktop) from the [Ubuntu release site](https://releases.ubuntu.com/resolute/) onto the supported platform as requirement above.
---
## Deploying EdgePack
1. Download EdgePack installer binary from the [GitHub release here](https://github.com/intel-innersource/os.linux.edgepack.tui-installer/releases)
2. Execute the installer to deploy the EdgePack installation:
```
$ sudo chmod +x ./edgepack-installer
$ ./edgepack-installer
```

## Installing from user YAML

For unattended CLI installation, supply the choices you would make in the TUI.
Only one base profile is required. For example, `choices.yml` can contain:

```yaml
base_profile: base-standard
```

To select add-ons, add only the desired profile keys:

```yaml
base_profile: base-standard
addons:
	- ffmpeg
	- manageability
```

Omitted add-ons mean none. The installer detects the host, checks compatibility,
and includes required packages and prerequisites automatically. The current
EdgePack version is used unless explicitly specified. Do not put passwords in
this file.

```bash
./edgepack-installer list
./edgepack-installer install --config choices.yml --dry-run
sudo ./edgepack-installer install --config choices.yml
```

Dry-run validates and previews without root or system changes; it does not verify
APT dependency versions or package availability. Without `--dry-run`, installation
starts after validation with no confirmation prompt. Restart manually after a
successful installation.

Add `--json` for a machine-readable result on stdout. Installation output then
streams to stderr. See the [YAML and CLI reference](../README.md#yaml-installation-choices)
for optional fields, error codes, and output details, and the
[example configuration](../data/user-options-example.yml).