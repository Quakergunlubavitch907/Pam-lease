"""Watchdog daemon — checks lease expiry, sends warnings, terminates sessions."""

import logging
import logging.handlers
import subprocess
import time
from pathlib import Path

import pamlease.lease as lease_module
from pamlease.notify import notify_user


def _setup_logger() -> logging.Logger:
    """Create and return a syslog-backed logger for the watchdog."""
    logger = logging.getLogger("pamlease.watchdog")
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


def _terminate_user(username: str, logger: logging.Logger) -> None:
    """Terminate all active sessions for the given user via loginctl."""
    try:
        subprocess.run(
            ["loginctl", "terminate-user", username],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.error("Failed to terminate sessions for %s: %s", username, exc)
    logger.info("session expired for %s, terminated", username)


def _check_leases(logger: logging.Logger) -> None:
    """Iterate all lease files and send warnings or terminate expired sessions."""
    lease_dir = Path(lease_module.LEASE_DIR)
    if not lease_dir.exists():
        return

    for lease_file in lease_dir.glob("*.lease"):
        username = lease_file.stem
        try:
            lease = lease_module.load_lease(username)
            if lease is None:
                continue

            secs = lease_module.time_remaining(lease)

            if secs <= 0:
                notify_user(
                    username,
                    "Your session has expired. You will be disconnected now.",
                )
                time.sleep(2)
                _terminate_user(username, logger)
                try:
                    lease_file.unlink()
                except FileNotFoundError:
                    pass

            elif secs <= 60 and not lease.get("warned_1min", False):
                notify_user(username, "Warning: Your session expires in 1 minute.")
                lease["warned_1min"] = True
                lease_module.save_lease(lease)
                logger.info("1 minute warning sent to %s", username)

            elif secs <= 300 and not lease.get("warned_5min", False):
                notify_user(
                    username,
                    "Warning: Your session expires in 5 minutes. Save your work.",
                )
                lease["warned_5min"] = True
                lease_module.save_lease(lease)
                logger.info("5 minute warning sent to %s", username)

        except Exception as exc:
            logger.error("Error processing lease for %s: %s", username, exc)


def main() -> None:
    """Entry point for the pamlease-watchdog daemon — runs forever."""
    logger = _setup_logger()
    logger.info("pamlease watchdog started")

    while True:
        try:
            _check_leases(logger)
        except Exception as exc:
            logger.error("Unexpected error in watchdog loop: %s", exc)
        time.sleep(30)
