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

Use the [interactive installation selector](../index.md)
to generate the current commands. Repository distributions, signing keys,
prerequisite repositories, pinning, and package names vary by selection.

## What the Generated Commands Do

1. Install HTTPS, download, and OpenPGP tooling.
2. Download each repository key and store it under `/etc/apt/keyrings`.
3. Configure APT sources with an explicit `signed-by` keyring.
4. Configure the Edge Pack repository pin priority.
5. Add any profile-specific prerequisite repositories.
6. Refresh package metadata and install the resolved metapackages.

The generated commands deliberately do not use the deprecated `apt-key`
command and do not configure repositories as trusted or unsigned.

## Review Before Running

- Confirm every repository and key URL belongs to the expected publisher.
- Confirm the repository distribution matches the installed Ubuntu release.
- Review all package names and APT's proposed dependency changes.
- Test provisioning changes on a non-production system first.

For selector source and regeneration instructions, see
[Maintaining the Installation Selector](https://github.com/open-edge-platform/edge-pack/blob/main/docs/edgepack-installer-files/README.md).
