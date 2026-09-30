# EdgePack TUI and CLI Installer


A terminal-based installer for Intel EdgePack software packages, built with [Textual](https://textual.textualize.io/).

The installer walks you through a 4-step wizard:

1. **Profile selection** — choose your base profile (standard or realtime kernel) and detect your hardware platform
2. **Add-on packages** — select optional add-on profiles to install alongside the base
3. **Installation summary** — review compatibility warnings and confirm what will be installed
4. **Installation** — live progress as packages are downloaded and installed via `apt`

> EdgePack [installation setup guide](doc/installation_setup.md). Follow this guide to install EdgePack using TUI installer, guide below shows how to build the installer.
---

## Running from source

### Requirements

- Python **3.10** or newer
- A terminal that supports 256 colours

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/open-edge-platform/edge-pack.git
cd edge-pack/edgepack-installer

# 2. (Recommended) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the TUI wizard (Ubuntu 24.04 / 26.04 only, requires sudo)
python3 -m tui

# Or install a profile directly from the CLI, no wizard (requires sudo)
sudo python3 -m tui install base-standard npu

# List available base profiles and add-ons
python3 -m tui list
```

---

## YAML installation choices

The CLI accepts the same base profile and add-on choices as the TUI wizard.
The user configuration is separate from the bundled package catalog; do not edit
`data/edgepacks-template.yml` to make installation selections.

A minimal `choices.yml` selects just one base profile:

```yaml
base_profile: base-standard
```

To select optional add-ons:

```yaml
base_profile: base-standard
addons:
	- ffmpeg
	- manageability
```

See [the complete example](data/user-options-example.yml) for optional fields.

| Field | Required | Default / meaning |
|---|---|---|
| `base_profile` | Yes | One base-profile key from `list` |
| `addons` | No | `[]`: no optional add-ons; only listed add-ons are selected |
| `edgepack_version` | No | Current installer version, currently `"2026.2"`; quote this string |
| `schema_version` | No | Integer `1` |

The version field checks compatibility with the current installer. It does not
download another EdgePack release or pin APT package versions. Packages,
prerequisites, and repositories are resolved automatically using the detected
CPU, OS, and kernel. Unsupported or disabled profiles and incompatible add-ons
are rejected, just as in the wizard. For example, `npu` currently requires Ubuntu
24.04; it is not supported on Ubuntu 26.04.

The file must contain one UTF-8 YAML mapping, at most 64 KiB. Unknown or duplicate
fields, wrong types, anchors, aliases, and custom tags are rejected. Passwords,
reboot, arbitrary package/repository overrides, and host overrides are not
configuration options. A restart is always left to the user.

From the source directory:

```bash
python3 -m tui list
python3 -m tui install --config choices.yml --dry-run
python3 -m tui install --config choices.yml --dry-run --json
sudo python3 -m tui install --config choices.yml
```

When using a virtual environment, run installation with that environment's Python
explicitly, for example `sudo .venv/bin/python -m tui install --config choices.yml`.

With the standalone executable:

```bash
./edgepack-installer list --json
./edgepack-installer install --config /path/to/choices.yml --dry-run
sudo ./edgepack-installer install --config /path/to/choices.yml --json
```

Paths are relative to the current working directory unless absolute. Do not mix
`--config` with positional profile arguments. The existing positional command
continues to work and also accepts `--dry-run` and `--json`:

```bash
./edgepack-installer install base-standard ffmpeg --dry-run
```

**Installation is unattended:** without `--dry-run`, `install` immediately
proceeds after validation and requires root. It can add repository keys, sources
and APT preferences, install prerequisites, and install or downgrade packages.
No confirmation prompt or automatic reboot is performed.

Dry-run requires no root and does not access the network, write logs or system
configuration, or invoke APT. It checks the actual host and previews profile
packages, additional OS packages, repositories, and prerequisites. It is not an
APT simulation: dependency versions and package availability are determined only
during installation. Unsupported hosts still return a validation failure.

### JSON output and exit codes

`--json` emits one result object to stdout. During installation, package-manager
output streams to stderr; it is not included in the JSON object. Normal help
output remains plain text. Results include `schema_version`, `command`, `status`,
`dry_run`, `exit_code`, `selection`, `host`, `plan`, `errors`, and
`restart_recommended`. `list --json` additionally includes `profiles`. Unavailable
selection/host/plan data is `null`. Errors include a `code`, `message`, and an
optional `field`. Successful dry-runs never recommend a restart.

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | Privilege or operational error |
| `2` | Invalid arguments, YAML, or unknown selection |
| `3` | Incompatible selection or empty package list |
| `4` | Unsupported host |
| `130` | Interrupted |
| Other | Installation subprocess exit code, such as APT's `100` |

Subprocess codes are passed through and can overlap installer codes. Use the
JSON error code (such as `installation_failed` or `unsupported_host`) to identify
the failure stage. Interrupting the CLI does not guarantee that an already
started package operation has stopped or been rolled back.

## Building a standalone executable (PyInstaller)

The installer can be packaged into a single self-contained binary that requires no Python or dependencies on the target machine.

> **Important:** Build on **Ubuntu 24.04 (Noble)** to ensure glibc compatibility with target machines running Ubuntu 24.04 or 26.04.

```bash
# 1. Install binutils
sudo apt install binutils

# 2. Install PyInstaller
pip install pyinstaller

# 3. Build (uses edgepack-installer.spec)
./build.sh

# Output: dist/edgepack-installer
```

The `build.sh` script installs PyInstaller, runs the spec, and reports the output path.

### Distributing the binary

Copy `dist/edgepack-installer` to the target machine and run:

```bash
# Run the TUI wizard
./edgepack-installer

# Install a profile directly from the CLI, no wizard (requires sudo)
sudo ./edgepack-installer install base-standard npu

# List available base profiles and add-ons
./edgepack-installer list
```

No Python, no pip, no dependencies needed on the target.

---

## Installation log

The TUI writes timestamped installation logs under:

```
/var/log/edgepack/
```

The TUI falls back to a user-writable location if needed. The CLI streams its
installation output without creating a persistent log. Redirect output to retain
it; for example, `sudo ./edgepack-installer install --config choices.yml --json
>result.json 2>install.log`. Dry-run does not create installation logs.

## Tests

Run from `edgepack-installer` with PyYAML installed:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Tests use mocked host and installation operations; they do not install packages,
modify repositories, or require root.

---

## Project structure

```
.
├── tui/                        # Textual TUI application
│   ├── app.py                  #   Root app class and shared wizard state
│   ├── app.tcss                #   All CSS styles
│   ├── main.py                 #   CLI entry point (argparse)
│   ├── package_logic.py        #   Package tree logic (no UI dependencies)
│   └── screens/
│       ├── step1.py            #   Profile & platform selection
│       ├── step2.py            #   Add-on package selection
│       ├── step3.py            #   Installation summary & warnings
│       ├── step4.py            #   Installation progress & log
│       └── validation.py       #   Post-install validation (future)
├── edgepack_shared/            # UI-agnostic business logic
│   ├── processor.py            #   Parses edgepacks-template.yml
│   ├── host.py                 #   OS / CPU auto-detection
│   ├── install_logic.py        #   Builds and runs the apt script
│   └── package_status.py       #   Queries dpkg for installed versions
├── data/
│   └── edgepacks-template.yml  #   Package, profile, and platform definitions
├── edgepack-installer.spec     # PyInstaller build spec
├── build.sh                    # One-command build script
└── requirements.txt
```

---

## Keyboard navigation

| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | Move focus between sections |
| `↑` / `↓` | Move between items within a list (Step 2 add-ons) |
| `←` / `→` | Move between buttons |
| `Space` | Toggle a checkbox / press the focused button |
| `Enter` | Press the focused button |
| `Ctrl+Q` | Quit |

---
