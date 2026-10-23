# Install with the TUI

The TUI is the recommended installation method. It detects the host platform,
Ubuntu release, and kernel before presenting compatible base profiles and
add-ons.

## Install

Use the [interactive installation selector](../index.md)
to obtain the current release URLs, or download `edgepack-installer` and
`edgepack-installer.sha256` from the repository's latest release.

```bash
sha256sum -c edgepack-installer.sha256
chmod +x edgepack-installer
sudo ./edgepack-installer
```

Follow the four steps in the wizard:

1. Confirm the detected platform and choose a base profile.
2. Select compatible optional add-ons.
3. Review the installation summary and warnings.
4. Confirm the installation and monitor package progress.

## Logs

Installation activity is written to:

```text
/var/log/edgepack/edgepack-installer.log
```

Include this log when reporting an installation failure, after reviewing it for
deployment-specific information.

## Keyboard navigation

| Key | Action |
| --- | --- |
| `Tab` / `Shift+Tab` | Move between controls |
| Arrow keys | Move within a list or button group |
| `Space` | Toggle or activate the focused control |
| `Enter` | Activate the focused button |
| `Ctrl+Q` | Exit the installer |
