# EdgePack TUI Installer


A terminal-based installer for Intel EdgePack software packages, built with [Textual](https://textual.textualize.io/).

The installer walks you through a 4-step wizard:

1. **Profile selection** — choose your base profile (standard or realtime kernel) and detect your hardware platform
2. **Add-on packages** — select optional add-on profiles to install alongside the base
3. **Installation summary** — review compatibility warnings and confirm what will be installed
4. **Installation** — live progress as packages are downloaded and installed via `apt`

---

## Getting started
Download the installer binary from the
[releases page](https://github.com/open-edge-platform/edge-pack/releases),
follow the **[Install with the TUI]([doc/tui_installation_setup.md](https://github.com/open-edge-platform/edge-pack/docs/user-guide/installation/tui.md))**.

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
