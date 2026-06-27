# claude-code-android

Run Claude Code on Android via Termux and proot-distro, with a full Ubuntu environment and Obsidian vault integration.

This repo documents a working setup for Claude Code v2.1.114 on Android (aarch64), including a workaround for Node.js platform detection and an sdcard-synced Obsidian vault accessible from both CLI and mobile app.

## Overview

This setup uses:
- **Termux** — Linux environment on Android
- **proot-distro** — Full Ubuntu 25.10 container inside Termux (no root required)
- **Claude Code** — Anthropic's official CLI, installed via the linux-arm64 package
- **Obsidian** — Note-taking app with mobile vault on Android shared storage

The key insight: Node.js on Termux reports `process.platform === 'android'`, which breaks the standard `npm install -g @anthropic-ai/claude-code`. The workaround installs the linux-arm64 package directly.

## Prerequisites

- **Android device** (aarch64 / arm64 architecture)
- **Termux** installed from [F-Droid](https://f-droid.org/en/packages/com.termux/) (not Google Play)
- **proot-distro** plugin for Termux (`pkg install proot-distro`)
- Basic familiarity with Linux terminals

## Installation

### 1. Set Up proot-distro Ubuntu

From Termux (outside proot):

```bash
pkg install proot-distro
proot-distro install ubuntu
proot-distro login ubuntu
```

You are now in the proot Ubuntu container. Verify:
```bash
uname -a  # Should show "6.17.0-PRoot-Distro" kernel
```

### 2. Install Claude Code

Still in proot Ubuntu, install Node and npm first:

```bash
apt update && apt install -y nodejs npm git curl ripgrep python3
```

Verify Node is accessible (it runs from Termux):
```bash
which node
# Output: /data/data/com.termux/files/usr/bin/node
```

Add Termux PATH to `~/.bashrc` (if not already present):

```bash
echo 'export PATH="$PATH:/data/data/com.termux/files/usr/bin"' >> ~/.bashrc
source ~/.bashrc
```

Install Claude Code from Termux (outside proot):

```bash
# Exit proot Ubuntu first
exit

# In Termux, install the linux-arm64 binary directly
npm install -g @anthropic-ai/claude-code-linux-arm64

# Verify
which claude
# Output: /data/data/com.termux/files/usr/bin/claude
```

**Why this works:** The `npm install -g` command installs to Termux's global prefix (`/data/data/com.termux/files/usr/lib/node_modules/`), and the Termux binary goes directly to `/data/data/com.termux/files/usr/bin/claude`. This path is already in Termux's PATH and inherited by proot Ubuntu.

Re-enter proot Ubuntu and confirm Claude Code is accessible:

```bash
proot-distro login ubuntu
which claude
# Output: /data/data/com.termux/files/usr/bin/claude
claude --version
# Output: claude 2.1.114
```

### 3. (Optional) Set Up Obsidian Vault on Android Storage

If you want to use Obsidian on both Android and Linux, store the vault on shared storage.

#### Give Termux Storage Access

From Termux:
```bash
termux-setup-storage
# This creates ~/storage/shared/ → /storage/emulated/0
```

#### Create Vault on Shared Storage

From proot Ubuntu:
```bash
# Create vault directory on shared storage (accessible from Termux)
mkdir -p /sdcard/ObsidianVault

# Create symlink in proot home (so Linux tools can access it at expected path)
ln -sf /sdcard/ObsidianVault ~/ObsidianVault
```

**Note:** `/sdcard/` is a symlink to `/storage/emulated/0` (Android shared storage). Writes from proot are read-only — use the SSH bridge (see below) to write files to `/sdcard` without leaving proot.

#### Initialize Vault Structure

```bash
cd ~/ObsidianVault
mkdir -p "00 Inbox" "01 Daily Notes" "02 Work" "03 Projects" "04 Bioinformatics" \
         "05 Reference" "06 Personal" "07 Templates" "08 Chat Archives"
mkdir -p ".obsidian"
```

#### Install Obsidian Plugins (Mobile Vault)

Since Obsidian on mobile doesn't support the in-app plugin installer, install plugins manually.

Create `.obsidian/community-plugins.json`:

```json
[
  "omnisearch",
  "dataview",
  "templater-obsidian",
  "calendar-beta",
  "tag-wrangler"
]
```

For each plugin, create a folder and download `main.js`, `manifest.json`, and `styles.css`:

```bash
PLUGIN_ID="omnisearch"
mkdir -p ~/.obsidian/plugins/$PLUGIN_ID
cd ~/.obsidian/plugins/$PLUGIN_ID

# Example: Omnisearch v1.28.2
curl -sL https://github.com/scambier/obsidian-omnisearch/releases/download/1.28.2/main.js -o main.js
curl -sL https://github.com/scambier/obsidian-omnisearch/releases/download/1.28.2/manifest.json -o manifest.json
curl -sL https://github.com/scambier/obsidian-omnisearch/releases/download/1.28.2/styles.css -o styles.css
```

Repeat for other plugins (adjust repo, release tag, and plugin ID).

**Recommended plugins:**
- [omnisearch](https://github.com/scambier/obsidian-omnisearch) — advanced search (v1.28.2)
- [dataview](https://github.com/blacksmithgu/obsidian-dataview) — query data (v0.5.70)
- [templater](https://github.com/SilentVoid13/Templater) — template automation (v2.19.0)
- [calendar](https://github.com/liamcain/obsidian-calendar-plugin) — visual calendar (v2.0.0-beta.2)
- [tag-wrangler](https://github.com/pjeby/tag-wrangler) — tag management (v0.6.4)

Open Obsidian on Android, open the vault at `/sdcard/ObsidianVault`, and plugins will load.

## SSH Bridge: proot → Termux (Write to /sdcard Without Switching Windows)

proot cannot write to `/sdcard` directly, but Termux can. By setting up an SSH connection from proot to Termux, Claude Code (and any script) can trigger Termux-side file operations without the user manually switching windows.

### One-Time Setup

**In Termux:**
```bash
pkg install openssh
sshd   # starts on port 8022
passwd   # set a Termux password (used once during key install)
```

**In proot Ubuntu:**
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
```

**In Termux — install the proot public key:**
```bash
cat /data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/ubuntu/root/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
pkill sshd && sshd
```

**Test from proot:**
```bash
ssh -p 8022 localhost echo "works"
# Should print: works  (no password prompt)
```

### Usage

From proot (or any script running inside proot), run Termux-side commands like:

```bash
# Copy rendered image to Obsidian vault
ssh -p 8022 localhost 'cp /path/to/file.png "/sdcard/ObsidianVault/05 Reference/Attachments/file.png"'

# Sync a directory
ssh -p 8022 localhost 'cp -rf /sdcard/source/. "/sdcard/ObsidianVault/destination/"'
```

**If SSH stops working:** run `sshd` in Termux to restart the daemon, then retry.

### What This Unlocks

- Claude Code can write render outputs, exports, and generated files directly to the Obsidian vault
- No manual copy-paste between Termux and proot windows
- Verified working: PyMOL ray-traced renders (1920×1440 PNG) copied to vault on aarch64 Android

## Known Issues & Gotchas

### systemd is unavailable
proot does not emulate systemd. Don't run `systemctl`. Use process managers like `supervisor` or run services manually.

### Some syscalls fail silently
Operations requiring real kernel namespaces (mount, some ioctls) may fail without errors.

### Termux PATH inheritance
Node/npm/claude are accessible from proot only because Termux's `/data/data/com.termux/files/usr/bin` is in `$PATH`. If PATH is cleared or reset, add it back to `~/.bashrc`:

```bash
export PATH="$PATH:/data/data/com.termux/files/usr/bin"
```

### npm global installs go to Termux
`npm install -g` installs to `/data/data/com.termux/files/usr/lib/node_modules/`, not `/usr/local/lib/`. Don't mix with `sudo npm install -g`.

### File permissions on /sdcard are odd
Android's FUSE layer shows odd ownership (uid 10295) and sticky bits. This is normal; don't try to `chown` or `chmod`.

### Symlink breaks after proot reinstall
If `~/ObsidianVault` becomes invalid:

```bash
ln -sf /sdcard/ObsidianVault ~/ObsidianVault
```

## Upgrading Claude Code

From Termux (outside proot):

```bash
npm install -g @anthropic-ai/claude-code-linux-arm64
```

The binary at `/data/data/com.termux/files/usr/bin/claude` will be updated automatically.

## File Structure

```
Termux (Android)
├── /data/data/com.termux/files/usr/bin/claude      ← Claude Code binary
├── /data/data/com.termux/files/usr/bin/node        ← Node.js binary
└── /storage/emulated/0/ObsidianVault               ← Obsidian vault (Android storage)

proot Ubuntu (inside Termux)
├── /root/                                          ← Home directory
│   ├── .bashrc                                     ← PATH setup
│   └── ObsidianVault -> /sdcard/ObsidianVault      ← Symlink to vault
├── /sdcard/ -> /storage/emulated/0                 ← Read-only symlink
└── /data/data/com.termux/files/usr/bin/*           ← Inherited from Termux
```

## Testing Your Setup

```bash
# In proot Ubuntu
which claude && claude --version
which node && node --version
which npm && npm --version

# If Obsidian vault is set up
ls -la ~/ObsidianVault
cat ~/.obsidian/community-plugins.json
```

## References

- [Termux](https://termux.dev/) — Linux on Android
- [proot-distro](https://github.com/termux/proot-distro) — Full Linux distros in Termux
- [Claude Code](https://claude.com/claude-code) — Anthropic's official CLI
- [Obsidian](https://obsidian.md/) — Note-taking app
- [Node.js on Android](https://nodejs.org/en/download/package-manager#termux) — Termux Node.js guide

## Troubleshooting

**Claude Code not found after install:**
- Verify `which claude` returns `/data/data/com.termux/files/usr/bin/claude`
- Check `~/.bashrc` includes the Termux PATH: `grep "com.termux" ~/.bashrc`
- Restart proot: `exit` and `proot-distro login ubuntu`

**Obsidian vault not syncing between devices:**
- Ensure vault is at `/sdcard/ObsidianVault` (or `/storage/emulated/0/ObsidianVault`)
- Verify symlink: `ls -la ~/ObsidianVault` should show `-> /sdcard/ObsidianVault`
- Check Obsidian app on Android has vault opened at the correct path

**Plugins not loading:**
- Verify plugin IDs in `.obsidian/community-plugins.json` match `id` fields in `manifest.json`
- Check files exist: `ls -la ~/.obsidian/plugins/{plugin-id}/`
- Restart Obsidian after adding plugins

**Permission denied on /sdcard:**
- Writes to `/sdcard` from proot are blocked (read-only from proot perspective)
- Use the SSH bridge to run copy commands via Termux: `ssh -p 8022 localhost 'cp ...'`
- Run `termux-setup-storage` in Termux if it doesn't have storage access yet

## License

This documentation is provided as-is for educational and reference purposes.

## Contributing

Improvements, clarifications, and bug fixes are welcome. Please test on a real Android device before submitting.

---

**Last tested:** April 21, 2026  
**Environment:** Ubuntu 25.10 (proot-distro), Termux on Android (aarch64)  
**Claude Code version:** 2.1.114  
**Node.js:** v25.8.2 (via Termux)  
**Verified capabilities:** Obsidian vault sync, PyMOL 3.1.0 ray-traced renders, SSH bridge for /sdcard writes, Remote Control access
