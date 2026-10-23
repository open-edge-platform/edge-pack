# Install with the Installer CLI

The installer CLI is the non-interactive counterpart to the TUI. It performs
the same host, profile, add-on, repository, and dependency checks, making it the
preferred automation interface when a terminal wizard is unsuitable.

## List profiles

```bash
./edgepack-installer list
```

## Install profiles

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

## Run from source

For development checkouts:

```bash
cd edgepack-installer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m tui list
sudo .venv/bin/python -m tui install base-standard ffmpeg
```
