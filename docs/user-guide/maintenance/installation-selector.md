# Maintaining the Installation Selector

The installation selector is generated from the same metadata used by the Edge
Pack installer. Keep generated configuration committed so pull requests and the
published documentation use the same installation choices.

## Source of truth

Edit `edgepack-installer/data/edgepacks-template.yml` when changing supported
operating systems, profiles, add-ons, repositories, signing keys,
prerequisites, or package names. Edit
`docs/edgepack-installer-files/config.base.json` only for selector-specific
labels, installation methods, and release download URLs.

The TUI and installer CLI detect the platform on the target system, while
current APT commands are identical across supported platforms. The generator
evaluates all platforms and fails if their packages or commands diverge for the
same visible selection. If platform-specific output is introduced, update the
selector design before accepting that metadata change.

## Regenerate and validate

After changing either source file, run:

```bash
python3 scripts/build-install-selector-config.py
python3 scripts/build-install-selector-config.py --check
python3 scripts/validate-install-selector.py
```

Commit the updated `docs/edgepack-installer-files/config.json` with the source
change. The selector configuration workflow runs the deterministic check and
validation for pull requests.

## Preview the Web UI locally

### Standalone selector

From the repository root, verify the generated configuration and start a local
HTTP server:

```bash
python3 scripts/build-install-selector-config.py --check
python3 scripts/validate-install-selector.py
python3 -m http.server 8765 --directory docs/edgepack-installer-files
```

Open <http://localhost:8765/selector.html> in a browser. Use an HTTP server
rather than opening `selector.html` directly because the browser loads
`config.json` with `fetch`. Press `Ctrl+C` in the terminal to stop the server.

### Complete OEP documentation page

Use a disposable directory to preview the selector inside the same OEP Sphinx
template used by documentation CI:

```bash
rm -rf /tmp/edge-pack-oep-preview
mkdir -p /tmp/edge-pack-oep-preview
rsync -a --exclude '.git' --exclude 'out' \
  --exclude 'venv_open-edge-platform' ./ /tmp/edge-pack-oep-preview/
cd /tmp/edge-pack-oep-preview
wget https://docs.openedgeplatform.intel.com/template/template.tar.gz
tar xf template.tar.gz
make build
mkdir -p out/html/_static/edgepack-installer-files
cp -a docs/edgepack-installer-files/. \
  out/html/_static/edgepack-installer-files/
python3 -m http.server 8766 --directory out/html
```

Open <http://localhost:8766/> in a browser. The explicit copy into `_static`
reproduces the asset-staging step performed by the OEP publication pipeline.
Press `Ctrl+C` to stop the server, then remove the disposable directory when it
is no longer needed.

## Documentation publication

The browser assets are committed under `docs/edgepack-installer-files/`. The
OEP documentation page embeds them from
`_static/edgepack-installer-files/` using the `hide_directive` block in
`docs/user-guide/index.md`. This follows the OEP component documentation
convention: GitHub displays the Markdown content, while the OEP publication
pipeline exposes the same-origin iframe assets.
