# Edge Pack Metadata

This directory contains the Debian packaging definitions for [Edge Pack](../README.md). These metapackages group the drivers, libraries, and tools needed to enable Intel platform capabilities on Ubuntu. APT resolves their dependencies; the driver and application payloads come from the configured package repositories.

For installation on supported hardware, use the
[Edge Pack installation guide](../docs/user-guide/installation/index.md). This
directory is primarily for maintainers building or updating the metapackages.

## Release Layout

| Directory | Target Release | Architecture |
|---|---|---|
| `noble/` | Ubuntu 24.04.5 LTS | `amd64` |
| `resolute/` | Ubuntu 26.04.1 LTS | `amd64` |

Each release contains independent source-package directories, such as `intel-edge-base/` and `intel-edge-media/`. Dependencies differ between releases, so build and install packages for the matching Ubuntu release only.

Each source package uses this layout:

```text
intel-edge-<domain>/
	debian/
		changelog
		control
		rules
		source/
			format
		<binary-package>.postinst / .postrm (where needed)
```

- `debian/control` defines the source package, binary packages, architecture, dependencies, and conflicts.
- `debian/changelog` records package versions and release history.
- `debian/rules` builds the packages using debhelper compatibility level 13.
- `debian/source/format` selects the `3.0 (native)` source format.
- Maintainer scripts apply or remove host configuration when applicable.

## Package Domains

The table describes the packaging definitions currently present, not a hardware compatibility matrix. See the [project README](../README.md) for supported platforms and use the installer to validate profile compatibility.

| Source Package | Binary Packages | Purpose |
|---|---|---|
| `intel-edge-base` | `intel-edge-base-standard`, `intel-edge-base-realtime` | Base profiles for standard and real-time systems |
| `intel-edge-graphics` | `intel-edge-graphics-core`, `intel-edge-graphics-display`, `intel-edge-graphics-sriov`, `intel-edge-graphics-udeb` | Graphics runtime, display, SR-IOV virtualization, and installer dependencies |
| `intel-edge-ipu` | `intel-edge-ipu` | Image Processing Unit (IPU) camera stack |
| `intel-edge-manageability` | `intel-edge-manageability` | Intel platform manageability stack |
| `intel-edge-media` | `intel-edge-media-core`, `intel-edge-media-gst`, `intel-edge-media-ffmpeg` | Media acceleration, GStreamer, and FFmpeg |
| `intel-edge-npu` | `intel-edge-npu` | Neural Processing Unit (NPU) stack |
| `intel-edge-tsn` | `intel-edge-tsn` | Time-Sensitive Networking (TSN) tools |

Release-specific differences:

- `intel-edge-base-realtime` is defined only in `resolute/`. It depends on `ubuntu-realtime` and conflicts with `intel-edge-base-standard`.
- On Resolute, `intel-edge-base-standard` also conflicts with `ubuntu-realtime`.
- `intel-edge-graphics-udeb` is defined only in `noble/`.
- `intel-edge-npu` currently has packaging only in `noble/`.

The release-specific control files are the source of truth for exact dependency lists. For example, see the base definitions for [Noble](noble/intel-edge-base/debian/control) and [Resolute](resolute/intel-edge-base/debian/control).

## Build Locally

Use an `amd64` Ubuntu build environment matching the target release. Install the packaging tools:

```bash
sudo apt update
sudo apt install build-essential debhelper dpkg-dev
```

From the repository root, build a source package's binary packages without signing:

```bash
cd edgepack-metadata/noble/intel-edge-base
dpkg-checkbuilddeps
dpkg-buildpackage -us -uc -b
```

Replace the release and source-package directory as needed. The build writes its artifacts to the parent directory, for example `edgepack-metadata/noble/`. One source package can produce multiple binary packages.

Inspect a generated package before installation:

```bash
dpkg-deb --info ../intel-edge-base-standard_*_amd64.deb
dpkg-deb --contents ../intel-edge-base-standard_*_amd64.deb
```

Use an explicit artifact filename if the directory contains multiple versions. Building a metapackage does not install or bundle its runtime dependencies, nor does it verify that they are available from the target system's repositories.

## Installation Considerations

Use the installer for normal deployments. Manual installation requires the matching Ubuntu and Intel package repositories, all required metapackages, and supported hardware. A successful local build alone does not establish platform compatibility.

Some base and graphics packages include maintainer scripts that change GRUB defaults or kernel command-line parameters and regenerate the boot configuration. Review those scripts before testing on a host, and reboot when requested for kernel and driver changes to take effect. Build in an isolated environment and test installation on a suitable non-production system.

## Updating Metadata

1. Edit the relevant release's `debian/control` file to update dependencies, descriptions, or conflicts.
2. Review any associated maintainer scripts when changing kernel or driver behavior.
3. Add a `debian/changelog` entry with the new version and a summary of the change.
4. Build the affected source package in the matching Ubuntu environment and inspect its output.
5. Test dependency resolution, installation, upgrade, and removal on the intended platform.

Check whether a change applies to both releases, but preserve release-specific dependencies. Follow the repository's [contribution guidelines](../CONTRIBUTING.md), including commit sign-off requirements.

## License

The packaging definitions are covered by the repository's [MIT License](../LICENSE.txt). Dependencies retain their respective licenses.
