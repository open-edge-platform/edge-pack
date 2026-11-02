<!--hide_directive ```{eval-rst}
.. meta::
   :description: Install Edge Pack non-interactively using the installer CLI.
   :keywords: Edge Pack, installer CLI, automation, installation
``` hide_directive-->

# Install with the Installer CLI

The installer CLI is the non-interactive counterpart to the TUI (terminal user interface).
It performs the same host, profile, add-on, repository, and dependency checks, making it
the preferred automation interface when a terminal wizard is unsuitable.

## List Profiles

```bash
./edgepack-installer list
```

## Install Profiles

Pass exactly one base profile followed by zero or more add-ons:

```bash
sudo ./edgepack-installer install base-standard
sudo ./edgepack-installer install base-standard ffmpeg gstreamer
```

Use the [interactive installation selector](../index.md)
to generate a command containing only add-ons supported by the selected Ubuntu
release and platform.

The command exits without changing packages when host validation or profile
compatibility fails. It does not prompt for confirmation, so review the command
before using it in automation.

## Verify the Release Download

The selector downloads the installer and its published SHA-256 checksum from
the latest GitHub release. Always verify the binary before running it:

```bash
sha256sum -c edgepack-installer.sha256
```

Do not run the installer when its checksum does not match.

## Run from Source

For development checkouts:

```bash
cd edgepack-installer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m tui list
sudo .venv/bin/python -m tui install base-standard ffmpeg
```
