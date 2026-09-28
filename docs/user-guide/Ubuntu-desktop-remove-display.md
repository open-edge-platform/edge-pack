# Convert Ubuntu Desktop to Behave Like Ubuntu Server (No Display)

This guide turns an **Ubuntu Desktop** installation into a headless, console-only
system that behaves like **Ubuntu Server** — no graphical login, no desktop
environment loaded at boot. It applies to both **Ubuntu 24.04 LTS** and
**Ubuntu 26.04**, which both use `systemd` and the `gdm3` display manager.

## Background: what each command does

| Command | Purpose |
| --- | --- |
| `systemctl set-default multi-user.target` | Sets the default boot target to `multi-user` (text/console, networking, no GUI) instead of `graphical`. |
| `systemctl disable gdm3` | Removes `gdm3` from the boot sequence so the graphical login is not started automatically. |
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

```
Created symlink '/etc/systemd/system/default.target' → '/usr/lib/systemd/system/multi-user.target'.
```

### 2. Disable the display manager

Ubuntu Desktop uses **GDM3** by default:

```bash
sudo systemctl disable gdm3
```

Expected output:

```
Synchronizing state of gdm3.service with SysV service script...
Removed '/etc/systemd/system/display-manager.service'.
```

### 3. Reboot

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

# Should print: inactive (dead)  and  disabled
systemctl is-active gdm3
systemctl status gdm3

# Confirm no graphical target is active
systemctl status graphical.target
```

You can also confirm no X/Wayland session is running:

```bash
# Should return nothing (no display server processes)
pgrep -a "Xorg|Xwayland|gnome-shell"
```

---