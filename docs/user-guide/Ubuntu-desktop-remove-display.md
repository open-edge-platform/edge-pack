# Convert Ubuntu Desktop to Behave Like Ubuntu Server (No Display)

This guide turns an **Ubuntu Desktop** installation into a headless, console-only
system that behaves like **Ubuntu Server** — no graphical login, no desktop
environment loaded at boot. It applies to both **Ubuntu 24.04 LTS** and
**Ubuntu 26.04**, which both use `systemd` and the `gdm3` display manager.

## Background: what each command does

| Command | Purpose |
| --- | --- |
| `systemctl set-default multi-user.target` | Sets the default boot target to `multi-user` (text/console, networking, no GUI) instead of `graphical`. |
| `systemctl disable --now gdm3` | Stops `gdm3` immediately and removes it from the boot sequence. |
| `apt install ubuntu-server` | Installs the Ubuntu Server package set before the desktop package set is removed. |
| `apt purge ubuntu-desktop ubuntu-desktop-minimal gdm3` | Removes the Ubuntu Desktop metapackages and graphical login manager. |
| `apt autoremove --purge` | Removes dependencies that APT no longer considers necessary. Review its proposed changes before accepting them. |
| `reboot` | Restarts so the machine comes up in console-only mode. |

### About the two systemd "targets"

- `graphical.target` → boots into the full desktop with a graphical login (GDM).
- `multi-user.target` → boots into a multi-user text console (like Ubuntu Server).

`multi-user.target` is the standard target used by Ubuntu Server, which is why
switching to it makes a Desktop install behave like a Server install.

---

## Step-by-step

### 1. Set the default boot target to console

```bash
sudo systemctl set-default multi-user.target
```

Expected output:

```text
Created symlink '/etc/systemd/system/default.target' → '/usr/lib/systemd/system/multi-user.target'.
```

### 2. Stop and disable the display manager

Ubuntu Desktop uses **GDM3** by default:

```bash
sudo systemctl disable --now gdm3
```

Run this command from a text console or an SSH session. It immediately ends any
active graphical login sessions.

Expected output:

```text
Synchronizing state of gdm3.service with SysV service script...
Removed '/etc/systemd/system/display-manager.service'.
```

### 3. Make sure the GPU PF has no clients

Before removing the desktop packages, verify that no process is using a Direct
Rendering Manager (DRM) device belonging to the GPU physical function (PF).
First identify the GPU PF's PCI address:

```bash
lspci -D | grep -Ei 'VGA|Display'
```

For example, if the address is `0000:00:02.0`, list its DRM device nodes:

```bash
GPU_PF=0000:00:02.0
find -L /dev/dri/by-path -maxdepth 1 -type c \
  -name "pci-${GPU_PF}-*" -print
```

Check those nodes for clients:

```bash
sudo fuser -v /dev/dri/by-path/pci-${GPU_PF}-*
```

No output means that the PF has no clients. If processes are listed, stop the
associated service or application and run the check again. Do not continue
until the command produces no output. If `gdm`, `gnome-shell`, `Xorg`, or
`Xwayland` appears, confirm that `gdm3` was stopped in the previous step.

### 4. Remove the desktop packages

Install the Ubuntu Server package set first. This keeps packages shared with a
server installation from being selected for automatic removal:

```bash
sudo apt update
sudo apt install ubuntu-server
```

Preview the desktop purge and review the packages listed for removal:

```bash
sudo apt-get --simulate purge ubuntu-desktop ubuntu-desktop-minimal gdm3
```

If the proposed changes are safe for the deployment, remove the desktop
metapackages and display manager:

```bash
sudo apt purge ubuntu-desktop ubuntu-desktop-minimal gdm3
```

Finally, preview the unused dependencies. This list can be much larger than
the first purge:

```bash
sudo apt-get --simulate autoremove --purge
```

Review every package in the removal summary, especially when working remotely.
Do not continue if it includes a package required by the deployment. When the
proposed changes are safe:

```bash
sudo apt autoremove --purge
```

### 5. Reboot

```bash
sudo reboot
```

The system now boots to a text console login, like Ubuntu Server.

---

## Verify the change

After rebooting, log in at the console and run:

```bash
# Should print: multi-user.target
systemctl get-default

# Should print inactive and disabled, or report that gdm3 is not installed
systemctl is-active gdm3
systemctl is-enabled gdm3

# Confirm no graphical target is active
systemctl status graphical.target
```

You can also confirm no X/Wayland session is running:

```bash
# Should return nothing (no display server processes)
pgrep -a "Xorg|Xwayland|gnome-shell"
```

Confirm that the desktop package sets are no longer installed:

```bash
# Should return no lines beginning with "ii"
dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' \
  ubuntu-desktop ubuntu-desktop-minimal gdm3 2>/dev/null | grep '^ii'
```

---
