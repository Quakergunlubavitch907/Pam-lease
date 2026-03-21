"""Terminal notification for pam-lease — writes messages to user TTYs."""

import logging
import logging.handlers
import subprocess
from typing import Optional


def _get_logger() -> logging.Logger:
    """Return a syslog-backed logger for the notify module."""
    logger = logging.getLogger("pamlease.notify")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        try:
            handler: logging.Handler = logging.handlers.SysLogHandler(
                address="/dev/log"
            )
        except (OSError, ConnectionRefusedError):
            handler = logging.handlers.SysLogHandler()
        handler.setFormatter(logging.Formatter("pamlease: %(message)s"))
        logger.addHandler(handler)
    return logger


def _find_user_tty(username: str) -> Optional[str]:
    """Return the first active TTY for the given user, or None."""
    try:
        result = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    session_ids = []
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == username:
            session_ids.append(parts[0])

    for session_id in session_ids:
        try:
            tty_result = subprocess.run(
                ["loginctl", "show-session", session_id, "-p", "TTY"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

        for line in tty_result.stdout.strip().splitlines():
            if line.startswith("TTY="):
                tty = line[4:].strip()
                if tty:
                    return tty

    return None


def notify_user(username: str, message: str) -> None:
    """Write a notification message to the user's active terminal session."""
    logger = _get_logger()

    tty = _find_user_tty(username)
    if tty is None:
        logger.info(
            "No active TTY found for %s, notification skipped: %s", username, message
        )
        return

    try:
        with open(f"/dev/{tty}", "w") as tty_file:
            tty_file.write(f"\n\n*** pamlease: {message} ***\n\n")
    except OSError as exc:
        logger.warning(
            "Could not write to /dev/%s for user %s: %s", tty, username, exc
        )
