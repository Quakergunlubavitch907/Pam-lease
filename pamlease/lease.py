"""Lease file read/write/validate logic for pam-lease."""

import json
import os
import pwd
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pamlease.exceptions import (
    LeaseExistsError,
    LeaseNotFoundError,
    UserNotFoundError,
)

LEASE_DIR: str = "/run/pamlease"


def _lease_path(username: str) -> Path:
    """Return the path to the lease file for the given user."""
    return Path(LEASE_DIR) / f"{username}.lease"


def _atomic_write(path: Path, data: dict) -> None:
    """Write a dict as JSON to path atomically via a temporary file."""
    content = json.dumps(data, indent=4)
    dir_path = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(tmp_path, 0o600)
        os.rename(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def parse_duration(s: str) -> int:
    """Parse a duration string like '30m', '1h', '2h30m' into seconds."""
    s = s.strip()
    pattern = r"^(?:(\d+)h)?(?:(\d+)m)?$"
    match = re.fullmatch(pattern, s)
    if not match or not any(match.groups()):
        raise ValueError(
            f"Invalid duration format: {s!r}. Use formats like '30m', '1h', '2h30m'."
        )
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    total = hours * 3600 + minutes * 60
    if total <= 0:
        raise ValueError(f"Duration must be positive, got: {s!r}")
    return total


def format_duration(seconds: int) -> str:
    """Format an integer number of seconds into a human-readable string."""
    seconds = int(seconds)
    if seconds < 3600:
        m, s = divmod(abs(seconds), 60)
        return f"{m}m {s}s"
    h, remainder = divmod(abs(seconds), 3600)
    m = remainder // 60
    return f"{h}h {m}m"


def load_lease(username: str) -> Optional[dict]:
    """Load and return the lease dict for a user, or None if not found."""
    path = _lease_path(username)
    try:
        with open(str(path), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        return None


def save_lease(lease: dict) -> None:
    """Write a lease dict back to disk atomically."""
    username = lease["user"]
    path = _lease_path(username)
    _atomic_write(path, lease)


def is_valid(lease: dict) -> bool:
    """Return True if the lease exists and has not yet expired."""
    return time_remaining(lease) > 0


def time_remaining(lease: dict) -> int:
    """Return seconds remaining until lease expiry (negative when expired)."""
    expires_at = datetime.strptime(lease["expires_at"], "%Y-%m-%dT%H:%M:%S")
    now = datetime.now()
    delta = expires_at - now
    return int(delta.total_seconds())


def grant_lease(
    username: str,
    duration_seconds: int,
    granted_by: str,
    force: bool = False,
) -> dict:
    """Create a new lease file for the given user and return it."""
    try:
        pwd.getpwnam(username)
    except KeyError:
        raise UserNotFoundError(f"System user {username!r} does not exist.")

    lease_dir = Path(LEASE_DIR)
    lease_dir.mkdir(mode=0o700, exist_ok=True)

    path = _lease_path(username)
    if path.exists() and not force:
        raise LeaseExistsError(
            f"A lease already exists for {username!r}. Use --force to overwrite."
        )

    now = datetime.now()
    expires_at = now + timedelta(seconds=duration_seconds)

    lease = {
        "user": username,
        "granted_by": granted_by,
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": duration_seconds,
        "warned_5min": False,
        "warned_1min": False,
    }

    _atomic_write(path, lease)
    return lease


def revoke_lease(username: str) -> None:
    """Delete the lease file for the given user."""
    path = _lease_path(username)
    try:
        path.unlink()
    except FileNotFoundError:
        raise LeaseNotFoundError(f"No active lease found for {username!r}.")


def extend_lease(username: str, extra_seconds: int) -> dict:
    """Extend the expiry of an existing lease and reset warning flags."""
    lease = load_lease(username)
    if lease is None:
        raise LeaseNotFoundError(f"No active lease found for {username!r}.")

    current_expiry = datetime.strptime(lease["expires_at"], "%Y-%m-%dT%H:%M:%S")
    new_expiry = current_expiry + timedelta(seconds=extra_seconds)

    lease["expires_at"] = new_expiry.strftime("%Y-%m-%dT%H:%M:%S")
    lease["duration_seconds"] = lease.get("duration_seconds", 0) + extra_seconds
    lease["warned_5min"] = False
    lease["warned_1min"] = False

    _atomic_write(_lease_path(username), lease)
    return lease
