# pam-lease

**pam-lease** grants time-limited SSH access to Linux users via a custom PAM module
written in C, with automatic session termination enforced by a systemd watchdog daemon.
Once a lease is granted, users SSH in normally with zero extra prompts; the lease is
checked transparently on every login attempt.

---

## How It Works

1. An administrator runs `pamlease grant <user> --duration 30m`.  This writes a JSON
   lease file to `/run/pamlease/<user>.lease` (tmpfs — wiped on reboot).
2. When the user SSHes in, the PAM module (`pam_lease.so`) reads the lease file.
   - No lease → authentication denied, "Permission denied".
   - Expired lease → authentication denied.
   - Valid lease → authentication proceeds; the session-open hook prints the expiry time.
3. The `pamlease-watchdog` daemon runs every 30 seconds.  It warns the user at 5 minutes
   and 1 minute before expiry by writing to their TTY, then terminates the session via
   `loginctl terminate-user` at expiry and deletes the lease file.

---

## Prerequisites

Install the PAM development headers for your distribution before building the C module:

| Distribution      | Command                              |
|-------------------|--------------------------------------|
| Debian / Ubuntu   | `sudo apt install libpam-dev`        |
| RHEL / Fedora     | `sudo dnf install pam-devel`         |
| Arch Linux        | `sudo pacman -S linux-pam`           |

---

## Install

### 1. Install the Python package

```bash
sudo pip install .
```

This installs the `pamlease` and `pamlease-watchdog` CLI tools and creates
`/run/pamlease/` with mode 700.

### 2. Build and install the PAM module

```bash
cd pam_lease
make
sudo make install
```

The Makefile verifies that `pam_appl.h` is present before compiling and installs
`pam_lease.so` to `/lib/security/`.

### 3. Configure PAM

Add the following two lines to `/etc/pam.d/sshd`, **before** the existing `auth` lines:

```
auth     required pam_lease.so
session  optional pam_lease.so
```

Example resulting file fragment:

```
auth     required pam_lease.so
auth     required pam_unix.so
auth     required pam_nologin.so
...
session  optional pam_lease.so
session  required pam_unix.so
```

### 4. Enable the systemd watchdog

```bash
sudo cp systemd/pamlease-watchdog.service /etc/systemd/system/
sudo cp systemd/pamlease-watchdog.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pamlease-watchdog.timer
```

The watchdog runs every 30 seconds and is restarted automatically if it crashes.

---

## CLI Usage

All `pamlease` subcommands require root.

### Grant a lease

```bash
# Grant 30 minutes
pamlease grant odai --duration 30m

# Grant 1.5 hours, overwriting any existing lease
pamlease grant alice --duration 1h30m --force
```

Output:

```
Lease granted for odai until 10:30:00 (30m 0s).
```

### Revoke a lease

```bash
pamlease revoke odai
```

Output:

```
Lease revoked for odai. Active sessions terminated.
```

Active SSH sessions are terminated immediately via `loginctl terminate-user`.

### List all active leases

```bash
pamlease list
```

Output:

```
USER         GRANTED BY     EXPIRES AT             TIME LEFT
-----------------------------------------------------------------
odai         root           2026-03-21 10:30       28m 14s
alice        root           2026-03-21 11:00       58m 14s
```

### Show a single lease

```bash
pamlease show odai
```

Output:

```
User:       odai
Granted by: root
Issued at:  2026-03-21 10:00:00
Expires at: 2026-03-21 10:30:00
Time left:  28m 14s
Warned 5m:  No
Warned 1m:  No
```

### Extend a lease

```bash
pamlease extend odai --duration 30m
```

Output:

```
Lease for odai extended by 30m 0s. New expiry: 11:00:00.
```

Extension resets both the 5-minute and 1-minute warning flags so the user receives
fresh warnings before the new deadline.

---

## What the User Sees

### On login (session open)

```
Your session will expire in 28 minutes (at 10:30:00).
```

### 5-minute warning (written directly to the user's TTY)

```
*** pamlease: Warning: Your session expires in 5 minutes. Save your work. ***
```

### 1-minute warning

```
*** pamlease: Warning: Your session expires in 1 minute. ***
```

### At expiry

```
*** pamlease: Your session has expired. You will be disconnected now. ***
```

The session is then terminated by `loginctl terminate-user`.

### When there is no lease (or the lease has expired) and the user tries to SSH in

```
Permission denied (publickey).
```

The connection is dropped by PAM before any password prompt is shown.

---

## Fail-Closed Behaviour

The PAM module is loaded with `required`, meaning **a valid lease is mandatory for
authentication**.  There is no fallback — if the lease file is missing, unreadable, or
expired, the user cannot log in regardless of their SSH key or password.

---

## Security Notes

- **tmpfs storage** — lease files live in `/run/pamlease/`, which is a tmpfs mount on
  all modern Linux distributions.  All leases are automatically wiped on reboot with no
  manual cleanup required.
- **Root-only directory** — `/run/pamlease/` is created with mode `0700` owned by root.
  Lease files are created with mode `0600` owned by root.  Unprivileged users cannot
  read, create, or modify lease files.
- **Atomic writes** — all lease file updates are performed by writing to a `.tmp` file
  and then calling `os.rename()`, so a concurrent reader never sees a partially-written
  file.
- **No secrets** — the lease file contains only timing metadata.  There are no tokens,
  keys, or passwords stored on disk.
- **CLI requires root** — every `pamlease` subcommand checks `os.geteuid() == 0` and
  exits immediately if not running as root.

---

## Development

### Run the test suite

```bash
pip install pytest
pytest tests/
```

All tests use pytest's `tmp_path` fixture and never touch `/run/pamlease/`.

