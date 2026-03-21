"""Tests for pamlease.lease — grant, revoke, load, validate, extend, format."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pamlease.lease as lease_module
from pamlease.exceptions import LeaseExistsError, LeaseNotFoundError, UserNotFoundError
from pamlease.lease import (
    extend_lease,
    format_duration,
    grant_lease,
    is_valid,
    load_lease,
    parse_duration,
    revoke_lease,
    time_remaining,
)


@pytest.fixture(autouse=True)
def use_tmp_lease_dir(tmp_path, monkeypatch):
    """Redirect LEASE_DIR to a temporary directory for every test."""
    monkeypatch.setattr(lease_module, "LEASE_DIR", str(tmp_path))


@pytest.fixture()
def mock_getpwnam():
    """Patch pwd.getpwnam so tests do not require real system users."""
    with patch("pamlease.lease.pwd.getpwnam") as mock:
        mock.return_value = MagicMock()
        yield mock


# ---------------------------------------------------------------------------
# parse_duration
# ---------------------------------------------------------------------------


def test_parse_duration_handles_30m():
    """30m → 1800 seconds."""
    assert parse_duration("30m") == 1800


def test_parse_duration_handles_1h():
    """1h → 3600 seconds."""
    assert parse_duration("1h") == 3600


def test_parse_duration_handles_2h30m():
    """2h30m → 9000 seconds."""
    assert parse_duration("2h30m") == 9000


def test_parse_duration_handles_1h30m():
    """1h30m → 5400 seconds."""
    assert parse_duration("1h30m") == 5400


def test_parse_duration_rejects_invalid():
    """Invalid duration strings raise ValueError."""
    with pytest.raises(ValueError):
        parse_duration("45s")

    with pytest.raises(ValueError):
        parse_duration("0m")

    with pytest.raises(ValueError):
        parse_duration("")


# ---------------------------------------------------------------------------
# format_duration
# ---------------------------------------------------------------------------


def test_format_duration_seconds_only():
    """Durations under one hour show minutes and seconds."""
    assert format_duration(1694) == "28m 14s"


def test_format_duration_exact_minutes():
    """Exact multiples of 60 show zero seconds."""
    assert format_duration(1800) == "30m 0s"


def test_format_duration_hours_and_minutes():
    """Durations of one hour or more show hours and minutes."""
    assert format_duration(3720) == "1h 2m"


def test_format_duration_exactly_one_hour():
    """Exactly 3600 seconds formats as 1h 0m."""
    assert format_duration(3600) == "1h 0m"


def test_format_duration_zero():
    """Zero seconds formats as 0m 0s."""
    assert format_duration(0) == "0m 0s"


# ---------------------------------------------------------------------------
# grant_lease
# ---------------------------------------------------------------------------


def test_grant_lease_creates_correct_lease_file(tmp_path, mock_getpwnam):
    """grant_lease writes a valid JSON lease file with the correct fields."""
    lease = grant_lease("testuser", 1800, "root")

    lease_file = tmp_path / "testuser.lease"
    assert lease_file.exists(), "Lease file was not created"

    with open(lease_file) as f:
        data = json.load(f)

    assert data["user"] == "testuser"
    assert data["granted_by"] == "root"
    assert data["duration_seconds"] == 1800
    assert data["warned_5min"] is False
    assert data["warned_1min"] is False
    assert "issued_at" in data
    assert "expires_at" in data

    issued = datetime.strptime(data["issued_at"], "%Y-%m-%dT%H:%M:%S")
    expires = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%S")
    assert abs((expires - issued).total_seconds() - 1800) < 5


def test_grant_lease_raises_for_nonexistent_user():
    """grant_lease raises UserNotFoundError when the system user is missing."""
    with patch("pamlease.lease.pwd.getpwnam", side_effect=KeyError("no user")):
        with pytest.raises(UserNotFoundError):
            grant_lease("nosuchuser", 1800, "root")


def test_grant_lease_raises_if_lease_exists(mock_getpwnam):
    """grant_lease raises LeaseExistsError when a lease file already exists."""
    grant_lease("testuser", 1800, "root")
    with pytest.raises(LeaseExistsError):
        grant_lease("testuser", 600, "root")


def test_grant_lease_force_overwrites(mock_getpwnam):
    """grant_lease with force=True replaces an existing lease."""
    grant_lease("testuser", 1800, "root")
    lease = grant_lease("testuser", 600, "root", force=True)
    assert lease["duration_seconds"] == 600


def test_grant_lease_file_permissions(tmp_path, mock_getpwnam):
    """Lease file is created with mode 0o600."""
    grant_lease("testuser", 1800, "root")
    lease_file = tmp_path / "testuser.lease"
    mode = lease_file.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


# ---------------------------------------------------------------------------
# load_lease
# ---------------------------------------------------------------------------


def test_load_lease_returns_none_for_missing_file():
    """load_lease returns None when no lease file exists."""
    assert load_lease("nobody") is None


def test_load_lease_returns_dict_for_existing_file(mock_getpwnam):
    """load_lease returns the lease dict when the file exists."""
    grant_lease("testuser", 1800, "root")
    lease = load_lease("testuser")
    assert lease is not None
    assert lease["user"] == "testuser"


def test_load_lease_returns_none_for_corrupt_file(tmp_path):
    """load_lease returns None when the file is not valid JSON."""
    corrupt = tmp_path / "baduser.lease"
    corrupt.write_text("not json {{{")
    assert load_lease("baduser") is None


# ---------------------------------------------------------------------------
# is_valid / time_remaining
# ---------------------------------------------------------------------------


def test_is_valid_returns_true_for_valid_lease():
    """is_valid returns True when the expiry is in the future."""
    future = datetime.now() + timedelta(hours=1)
    lease = {
        "user": "testuser",
        "expires_at": future.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    assert is_valid(lease) is True


def test_is_valid_returns_false_for_expired_lease():
    """is_valid returns False when the expiry is in the past."""
    past = datetime.now() - timedelta(seconds=1)
    lease = {
        "user": "testuser",
        "expires_at": past.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    assert is_valid(lease) is False


def test_time_remaining_positive_for_future_lease():
    """time_remaining returns a positive number of seconds for a future expiry."""
    future = datetime.now() + timedelta(hours=1)
    lease = {
        "user": "testuser",
        "expires_at": future.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    secs = time_remaining(lease)
    assert 3590 < secs <= 3600


def test_time_remaining_negative_for_expired_lease():
    """time_remaining returns a negative number for an expired lease."""
    past = datetime.now() - timedelta(seconds=60)
    lease = {
        "user": "testuser",
        "expires_at": past.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    assert time_remaining(lease) < 0


# ---------------------------------------------------------------------------
# revoke_lease
# ---------------------------------------------------------------------------


def test_revoke_lease_deletes_file(tmp_path, mock_getpwnam):
    """revoke_lease removes the lease file from disk."""
    grant_lease("testuser", 1800, "root")
    lease_file = tmp_path / "testuser.lease"
    assert lease_file.exists()

    revoke_lease("testuser")
    assert not lease_file.exists()


def test_revoke_lease_raises_for_missing_lease():
    """revoke_lease raises LeaseNotFoundError when no lease file exists."""
    with pytest.raises(LeaseNotFoundError):
        revoke_lease("nobody")


# ---------------------------------------------------------------------------
# extend_lease
# ---------------------------------------------------------------------------


def test_extend_lease_updates_expiry_and_resets_warned_flags(mock_getpwnam):
    """extend_lease adds extra time and resets both warned flags to False."""
    lease = grant_lease("testuser", 1800, "root")
    original_expiry = datetime.strptime(lease["expires_at"], "%Y-%m-%dT%H:%M:%S")

    # Simulate that warnings have already been sent.
    lease["warned_5min"] = True
    lease["warned_1min"] = True
    from pamlease.lease import save_lease

    save_lease(lease)

    updated = extend_lease("testuser", 1800)

    new_expiry = datetime.strptime(updated["expires_at"], "%Y-%m-%dT%H:%M:%S")
    diff = (new_expiry - original_expiry).total_seconds()
    assert abs(diff - 1800) < 5, f"Expected ~1800s extension, got {diff}s"

    assert updated["warned_5min"] is False
    assert updated["warned_1min"] is False


def test_extend_lease_raises_for_missing_lease():
    """extend_lease raises LeaseNotFoundError when no lease exists."""
    with pytest.raises(LeaseNotFoundError):
        extend_lease("nobody", 600)
