<!--hide_directive ```{eval-rst}
.. meta::
   :description: Install Edge Pack using native APT package management.
   :keywords: Edge Pack, APT, package management, installation
``` hide_directive-->

# Install with APT

APT installation uses the standard native package management process. It is
suited to provisioning systems that need explicit repository and package
operations. APT does not run Edge Pack's host validation, so the operator must
ensure that the Ubuntu release, platform, kernel, base profile, and add-ons form
a supported combination.

Use the [interactive installation selector](../get-started.md)
to generate the current commands. Repository distributions, signing keys,
prerequisite repositories, pinning, and package names vary by selection.

For both Ubuntu 24.04 (Noble) and Ubuntu 26.04 (Resolute), the public Edge Pack
source is `https://apt.repos.intel.com/edgepack/`, with the matching suite
(`noble` or `resolute`) and the `stable` component. The signing key is published at
<https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB>.

The generated APT preferences use `Pin: origin apt.repos.intel.com` and
`Pin-Priority: 1001` so Intel-validated versions take precedence over the Ubuntu
archive.

The standard base metapackage is `intel-edge-base-standard`. Additional packages
and prerequisite repositories are selected from the current manifest; the Kobuk
snapshot is currently needed only for the Ubuntu 24.04 NPU add-on, not for every
base installation. Do not add a blanket Kobuk source for both Ubuntu releases.

## What the Generated Commands Do

1. Install HTTPS, download, and OpenPGP tooling.
2. Download each repository key and store it under `/etc/apt/keyrings`.
3. Configure APT sources with an explicit `signed-by` keyring.
4. Configure the Edge Pack repository pin priority.
5. Add any profile-specific prerequisite repositories.
6. Refresh package metadata and install the resolved metapackages.

After installation, reboot to load the installed kernel and drivers:

```bash
sudo reboot
```

For console-only deployments, then follow the
[headless conversion guide](../ubuntu-desktop-remove-display.md).

The generated commands deliberately do not use the deprecated `apt-key`
command and do not configure repositories as trusted or unsigned.

## Review Before Running

- Confirm every repository and key URL belongs to the expected publisher.
- Confirm the repository distribution matches the installed Ubuntu release.
- Review all package names and APT's proposed dependency changes.
- Test provisioning changes on a non-production system first.

For selector source and regeneration instructions, see
[Maintaining the Installation Selector](https://github.com/open-edge-platform/edge-pack/blob/main/docs/edgepack-installer-files/README.md).
