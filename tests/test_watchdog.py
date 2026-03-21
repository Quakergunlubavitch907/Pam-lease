"""Tests for pamlease.watchdog — warning dispatch and session termination."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import pamlease.lease as lease_module
from pamlease.watchdog import _check_leases


@pytest.fixture(autouse=True)
def use_tmp_lease_dir(tmp_path, monkeypatch):
    """Redirect LEASE_DIR to a temporary directory for every test."""
    monkeypatch.setattr(lease_module, "LEASE_DIR", str(tmp_path))


@pytest.fixture()
def logger():
    """Return a silent logger so tests produce no output."""
    log = logging.getLogger("pamlease.test")
    log.addHandler(logging.NullHandler())
    return log


def _write_lease(tmp_path: Path, username: str, expires_delta_secs: int, **kwargs) -> Path:
    """Write a lease file for *username* expiring in *expires_delta_secs* seconds."""
    now = datetime.now()
    expires_at = now + timedelta(seconds=expires_delta_secs)
    data = {
        "user": username,
        "granted_by": "root",
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_seconds": abs(expires_delta_secs),
        "warned_5min": False,
        "warned_1min": False,
    }
    data.update(kwargs)

    lease_file = tmp_path / f"{username}.lease"
    lease_file.write_text(json.dumps(data))
    return lease_file


# ---------------------------------------------------------------------------
# missing lease directory
# ---------------------------------------------------------------------------


def test_watchdog_handles_missing_lease_dir(tmp_path, monkeypatch, logger):
    """_check_leases returns silently when the lease directory does not exist."""
    monkeypatch.setattr(lease_module, "LEASE_DIR", str(tmp_path / "nonexistent"))
    # Must not raise.
    _check_leases(logger)


# ---------------------------------------------------------------------------
# 5-minute warning
# ---------------------------------------------------------------------------


def test_watchdog_sends_5min_warning_when_time_left_lte_300(tmp_path, logger):
    """_check_leases sends the 5-minute warning when 240 seconds remain."""
    _write_lease(tmp_path, "odai", expires_delta_secs=240)

    with patch("pamlease.watchdog.notify_user") as mock_notify, \
         patch("pamlease.watchdog._terminate_user") as mock_term:

        _check_leases(logger)

        mock_notify.assert_called_once_with(
            "odai",
            "Warning: Your session expires in 5 minutes. Save your work.",
        )
        mock_term.assert_not_called()

    # warned_5min flag must have been persisted.
    updated = lease_module.load_lease("odai")
    assert updated is not None
    assert updated["warned_5min"] is True
    assert updated["warned_1min"] is False


def test_watchdog_does_not_repeat_5min_warning(tmp_path, logger):
    """_check_leases skips the 5-minute warning if warned_5min is already True."""
    _write_lease(tmp_path, "odai", expires_delta_secs=240, warned_5min=True)

    with patch("pamlease.watchdog.notify_user") as mock_notify:
        _check_leases(logger)
        mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# 1-minute warning
# ---------------------------------------------------------------------------


def test_watchdog_sends_1min_warning_when_time_left_lte_60(tmp_path, logger):
    """_check_leases sends the 1-minute warning when 45 seconds remain."""
    _write_lease(tmp_path, "alice", expires_delta_secs=45, warned_5min=True)

    with patch("pamlease.watchdog.notify_user") as mock_notify, \
         patch("pamlease.watchdog._terminate_user") as mock_term:

        _check_leases(logger)

        mock_notify.assert_called_once_with(
            "alice",
            "Warning: Your session expires in 1 minute.",
        )
        mock_term.assert_not_called()

    updated = lease_module.load_lease("alice")
    assert updated is not None
    assert updated["warned_1min"] is True


def test_watchdog_does_not_repeat_1min_warning(tmp_path, logger):
    """_check_leases skips the 1-minute warning if warned_1min is already True."""
    _write_lease(
        tmp_path, "alice", expires_delta_secs=45,
        warned_5min=True, warned_1min=True,
    )

    with patch("pamlease.watchdog.notify_user") as mock_notify:
        _check_leases(logger)
        mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# session termination at expiry
# ---------------------------------------------------------------------------


def test_watchdog_terminates_session_when_expired(tmp_path, logger):
    """_check_leases notifies, waits, terminates, and deletes the lease file."""
    lease_file = _write_lease(tmp_path, "bob", expires_delta_secs=-5)

    with patch("pamlease.watchdog.notify_user") as mock_notify, \
         patch("pamlease.watchdog._terminate_user") as mock_term, \
         patch("pamlease.watchdog.time.sleep") as mock_sleep:

        _check_leases(logger)

        mock_notify.assert_called_once_with(
            "bob",
            "Your session has expired. You will be disconnected now.",
        )
        mock_sleep.assert_called_once_with(2)
        mock_term.assert_called_once_with("bob", logger)

    # Lease file must be deleted after termination.
    assert not lease_file.exists()


def test_watchdog_handles_multiple_leases(tmp_path, logger):
    """_check_leases processes all lease files in a single pass."""
    _write_lease(tmp_path, "user1", expires_delta_secs=-1)   # expired
    _write_lease(tmp_path, "user2", expires_delta_secs=45, warned_5min=True)   # 1min
    _write_lease(tmp_path, "user3", expires_delta_secs=3600)  # fine, no action

    notify_calls = []

    def fake_notify(username, message):
        notify_calls.append((username, message))

    with patch("pamlease.watchdog.notify_user", side_effect=fake_notify), \
         patch("pamlease.watchdog._terminate_user"), \
         patch("pamlease.watchdog.time.sleep"):

        _check_leases(logger)

    notified_users = {c[0] for c in notify_calls}
    assert "user1" in notified_users
    assert "user2" in notified_users
    assert "user3" not in notified_users


def test_watchdog_continues_on_corrupt_lease(tmp_path, logger):
    """_check_leases logs an error and continues when a lease file is corrupt."""
    corrupt = tmp_path / "corrupt.lease"
    corrupt.write_text("not valid json {{{")

    # Must not raise.
    _check_leases(logger)
