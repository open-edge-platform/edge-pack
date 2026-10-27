# Release Notes - Edge Pack



## Version 2026.2.0

**Release Date**: September 10, 2026

Terminal-based wizard for installing Intel EdgePack software packages on supported Linux platforms.

### Features

- Guided installation wizard — walks you through choosing and installing EdgePack packages step
  by step, no manual apt commands needed.
- Auto-detects your hardware and OS — picks the right packages for your platform and warns
  you if your system isn't supported.
- Optional add-on packages — choose extra packages to install alongside the base package.
- Handles dependencies for you — automatically works out and installs everything a package
  needs.
- Install without the wizard — new CLI mode lets you install a base profile and add-ons
  directly (edgepack-installer install <profile> ...) or list what's available
  (edgepack-installer - list), useful for scripted and automated setups.
- Hardened against malicious input — internal parsers and the install-script builder are now
  fuzz-tested, closing a shell-injection risk found during that testing.
- Safer handling of your sudo password — held in memory as a mutable buffer and explicitly
  wiped immediately after use, instead of lingering as an ordinary string.
- Safer downloads — downloaded files are validated (size and content) before being trusted,
  and are only moved into place once they pass those checks.
- Less information leakage — error messages no longer reveal internal details like supported
  profiles, platforms, or your detected CPU/OS; log files are now locked down to your user
  only.
- Signed repository support — installs use signed-by keyrings instead of blanket-trusting
  repositories once a signing key is available.
- New installation setup guide — step-by-step guide for preparing supported platforms before
  running the installer.

