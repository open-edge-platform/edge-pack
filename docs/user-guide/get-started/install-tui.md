# Install Edge Pack With TUI

TUI is the recommended installation method. It is a terminal-based wizard built with
[Textual](https://textual.textualize.io/) that
detects the host platform, Ubuntu release, and kernel before presenting compatible base
profiles and add-ons. No need for hand-crafting `apt` commands or configuring the repository.
To start, follow the steps:

1. Download the package: [Releases](https://github.com/open-edge-platform/edge-pack/releases).
   You can use the [interactive installation selector](../get-started.md) to obtain specific
   release URLs.
2. Run the installer.

   ```bash
   sudo chmod +x ./edgepack-installer
   sudo ./edgepack-installer
   ```

3. Go through a 4-step wizard.

   - Confirm the detected platform and choose a base profile.
   - Select compatible optional add-ons.
   - Review the installation summary and warnings.
   - Confirm the installation and monitor package progress.

   | Keyboard Navigation              | Action                                            |
   |----------------------------------|---------------------------------------------------|
   | `Tab` / `Shift+Tab`              | Move focus between sections                       |
   | `↑` / `↓`                        | Move between items within a list (Step 2 add-ons) |
   | `←` / `→`                        | Move between buttons                              |
   | `Space`                          | Toggle a checkbox / press the focused button      |
   | `Enter`                          | Press the focused button                          |
   | `Ctrl+Q`                         | Quit                                              |



See what the process looks like in the video:
https://github.com/user-attachments/assets/ef562165-f427-434d-a472-1244b3e430f6

A checksum is published with the binary, so you can verify the download integrity:

```bash
sha256sum -c edgepack-installer.sha256
```


## Logs

Installation activity is written to:

```text
/var/log/edgepack/edgepack-installer.log
```

Include this log when reporting an installation failure, after reviewing it for
deployment-specific information.



## How to run from source

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

## How to build a standalone executable (PyInstaller)

The installer can be packaged into a single self-contained binary that requires no Python or
dependencies on the target machine.

> [!Note]
> Build on **Ubuntu 24.04 (Noble)** to ensure glibc compatibility with target
  machines running Ubuntu 24.04 or 26.04.

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
