# CLAUDE.md — Environment Reference

## Environment

| Key | Value |
|-----|-------|
| OS | Ubuntu 25.10 (Questing Quokka) via proot-distro |
| Host | Android (Termux) |
| Architecture | aarch64 (arm64) |
| Kernel | 6.17.0-PRoot-Distro |
| Shell | bash |
| Home | `/root` |

This is a **proot-distro Ubuntu container** running inside Termux on Android. It is not a VM — it shares the Android kernel via proot. Some syscalls are unavailable or behave differently.

## Installed Tools

| Tool | Version | Location |
|------|---------|----------|
| Node.js | v25.8.2 | via Termux (`/data/data/com.termux/files/usr/bin/node`) |
| npm | 11.12.1 | via Termux |
| Claude Code | 2.1.114 | see workaround below |
| git | 2.51.0 | Ubuntu native |
| curl | 8.14.1 | Ubuntu native |
| ripgrep | 14.1.1 | Ubuntu native |
| Python | 3.13.7 | Ubuntu native |

Node and npm are **not installed inside proot Ubuntu** — they run from Termux's prefix and are accessible because Termux's bin path (`/data/data/com.termux/files/usr/bin`) is appended to `$PATH` in this session. If they disappear from PATH, add this to `~/.bashrc`:

```bash
export PATH="$PATH:/data/data/com.termux/files/usr/bin"
```

## Claude Code — How It's Installed (Workaround)

Standard `npm install -g @anthropic-ai/claude-code` **fails on Termux** because Node reports `process.platform === 'android'` instead of `'linux'`. The postinstall script can't resolve the correct platform binary and aborts.

**The working installation:**

Install the linux-arm64 package directly from Termux (outside proot):
```bash
npm install -g @anthropic-ai/claude-code-linux-arm64
```

This installs the claude binary to `/data/data/com.termux/files/usr/bin/claude`, which is already in Termux's PATH and accessible from proot via the inherited PATH environment.

**Current status (verified April 19, 2026):**
- Binary location: `/data/data/com.termux/files/usr/bin/claude` (v2.1.114)
- Accessible from proot via PATH inheritance (no symlink needed)
- `which claude` returns `/data/data/com.termux/files/usr/bin/claude`

**To upgrade Claude Code:** run `npm install -g @anthropic-ai/claude-code-linux-arm64` from Termux. No manual PATH configuration is needed.

## Android Storage

| Path | Writable from proot? | Notes |
|------|---------------------|-------|
| `/sdcard` | Read-only directly | Use SSH bridge (see below) to write |
| `/storage/emulated/0` | Read-only directly | Android shared storage |
| `/root` | Yes | proot Ubuntu home |
| `/data/data/com.termux/files/home` | Yes (via Termux) | Termux home |

**Writes to `/sdcard` from proot** use the SSH bridge — no need to switch to a Termux window.

To give Termux storage access (one-time): `termux-setup-storage`

## SSH Bridge: proot → Termux (verified 2026-04-21)

proot cannot write to `/sdcard` directly, but can SSH into Termux (which can). This lets Claude Code run Termux-side commands without the user switching windows.

**Setup (already done — do not redo):**
- SSH key at `/root/.ssh/id_ed25519` (proot)
- Public key installed in Termux `~/.ssh/authorized_keys`
- Termux sshd on port 8022

**Start sshd if not running (run in Termux):**
```bash
sshd
```

**Usage from proot:**
```bash
ssh -p 8022 localhost 'cp /path/to/file "/sdcard/ObsidianVault/destination/"'
```

**Proot rootfs path from Termux:**
```
/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/ubuntu/
```
So `/root/file.png` in proot = that path + `root/file.png` from Termux.

## Obsidian Vault

**Location:** `/root/ObsidianVault` → symlink → `/sdcard/ObsidianVault`

The vault lives on Android shared storage so the Obsidian Android app can open it directly. The symlink lets proot Ubuntu access it at the expected home path.

```
ObsidianVault/
├── 00 Inbox/               # default landing for new notes
├── 01 Daily Notes/         # daily-notes plugin output (YYYY-MM-DD.md)
├── 02 Work/                # customize to your domains
├── 03 Projects/
│   ├── Active/
│   └── Archive/
├── 04 Reference/
│   ├── Literature and Papers/
│   ├── Reagents and Supplies/
│   └── Methods and Techniques/
├── 05 Personal/            # personal notes
├── 06 Templates/           # Daily Note, Meeting Note, Project Note, Lab Protocol
├── 07 Chat Archives/       # ChatGPT and Claude conversation exports
│   ├── ChatGPT/            # conversation notes
│   └── Claude/             # conversation notes
│       └── Projects/       # project notes
└── .obsidian/              # app.json, core-plugins, daily-notes, templates config
```

**Obsidian config highlights:**
- New notes → `00 Inbox` automatically
- Attachments → `04 Reference/Attachments`
- Daily notes format: `YYYY-MM-DD`, stored in `01 Daily Notes/`
- Templates plugin points to `06 Templates/`

**Installed Community Plugins (April 19, 2026):**

Since this is a mobile vault, plugins must be installed manually (the in-app installer is unavailable). All plugins are downloaded from GitHub releases and placed in `.obsidian/plugins/{plugin-id}/`, then enabled in `.obsidian/community-plugins.json`.

| Plugin | ID | Version | Status |
|--------|-----|---------|--------|
| Omnisearch | omnisearch | 1.28.2 | ✓ Enabled |
| Dataview | dataview | 0.5.70 | ✓ Enabled |
| Templater | templater-obsidian | 2.19.0 | ✓ Enabled |
| Calendar | calendar-beta | 2.0.0-beta.2 | ✓ Enabled |
| Tag Wrangler | tag-wrangler | 0.6.4 | ✓ Enabled |

**Installation method:** Each plugin folder contains `main.js`, `manifest.json`, and (where available) `styles.css`. The plugin IDs in `community-plugins.json` must match the `id` field in each plugin's `manifest.json`.

**Mobile Installation Workflow:**

To install a new plugin on this mobile vault:
1. Get the latest release version from GitHub: `curl -sL https://github.com/{owner}/{repo}/releases/download/{version}/{filename}`
2. Create the plugin folder: `mkdir -p ~/.obsidian/plugins/{plugin-id}`
3. Download `main.js`, `manifest.json`, and `styles.css` (if present) into that folder
4. Add the plugin's ID (from `manifest.json`) to `.obsidian/community-plugins.json` as a JSON array
5. Restart Obsidian to load the plugin

**To verify plugin installation:** Check that `~/.obsidian/community-plugins.json` contains all intended plugin IDs, and files exist in `~/.obsidian/plugins/{plugin-id}/`.

## Chat Archives

**Import Summary:**
- ChatGPT conversation notes from exported JSON files
- Claude conversation notes and projects from exported JSON files

**Vault Location:** `~/ObsidianVault/07 Chat Archives/`
- `ChatGPT/` — conversation notes
- `Claude/` — conversation notes
- `Claude/Projects/` — project notes

**Parser Scripts:** Idempotent and safe to re-run after new exports; automatically skips already-existing files
- `parse_chatgpt.py` — processes ChatGPT exports
- `parse_claude.py` — processes Claude conversation and memory exports

## Known Gotchas

- **No systemd.** proot does not support systemd. Don't try to run `systemctl`. Use process managers like `supervisor` or run services manually if needed.
- **Some syscalls fail silently.** Operations that require real kernel namespaces (mount, some ioctls) may fail or no-op without errors.
- **Termux PATH must be present** for Node/npm/claude to work. Verify with `which node`.
- **npm global dir is Termux's**, not Ubuntu's. Global npm packages install to `/data/data/com.termux/files/usr/lib/node_modules/`, not `/usr/local/lib/`. Don't mix with `sudo npm install -g`.
- **File permissions on `/sdcard`** use Android's FUSE layer — ownership/chmod results look odd (uid 10295, sticky bits) and don't map to Linux users. This is normal.
- **Obsidian vault symlink**: if the symlink at `~/ObsidianVault` breaks (e.g. after a proot reinstall), recreate it with:
  ```bash
  ln -sf /sdcard/ObsidianVault ~/ObsidianVault
  ```
