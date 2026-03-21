"""Click CLI for pam-lease — the pamlease command."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click

import pamlease.lease as lease_module
from pamlease.exceptions import (
    LeaseExistsError,
    LeaseNotFoundError,
    UserNotFoundError,
)
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


def _require_root() -> None:
    """Exit with an error message if the current process is not running as root."""
    if os.geteuid() != 0:
        click.echo("Error: pamlease must be run as root.", err=True)
        sys.exit(1)


@click.group()
def main() -> None:
    """pam-lease: grant and manage time-limited SSH access leases."""


@main.command()
@click.argument("username")
@click.option("--duration", required=True, help="Lease duration, e.g. 30m, 1h, 2h30m.")
@click.option("--force", is_flag=True, help="Overwrite an existing lease.")
def grant(username: str, duration: str, force: bool) -> None:
    """Grant a time-limited SSH lease for USERNAME."""
    _require_root()

    try:
        duration_seconds = parse_duration(duration)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    granted_by = os.environ.get("SUDO_USER", "root")

    try:
        lease = grant_lease(username, duration_seconds, granted_by, force=force)
    except UserNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except LeaseExistsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    expiry = datetime.strptime(lease["expires_at"], "%Y-%m-%dT%H:%M:%S")
    click.echo(
        f"Lease granted for {username} until {expiry.strftime('%H:%M:%S')}"
        f" ({format_duration(duration_seconds)})."
    )


@main.command()
@click.argument("username")
def revoke(username: str) -> None:
    """Revoke the SSH lease for USERNAME and terminate active sessions."""
    _require_root()

    try:
        revoke_lease(username)
    except LeaseNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    try:
        subprocess.run(
            ["loginctl", "terminate-user", username],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        click.echo(f"Warning: Could not terminate sessions: {exc}", err=True)

    click.echo(f"Lease revoked for {username}. Active sessions terminated.")


@main.command(name="list")
def list_leases() -> None:
    """List all active leases."""
    _require_root()

    lease_dir = Path(lease_module.LEASE_DIR)
    if not lease_dir.exists():
        click.echo("No lease directory found. No leases have been granted.")
        return

    lease_files = sorted(lease_dir.glob("*.lease"))
    if not lease_files:
        click.echo("No active leases.")
        return

    header = f"{'USER':<12} {'GRANTED BY':<14} {'EXPIRES AT':<22} {'TIME LEFT'}"
    click.echo(header)
    click.echo("-" * len(header))

    for lease_file in lease_files:
        username = lease_file.stem
        lease = load_lease(username)
        if lease is None:
            continue

        expires_str = datetime.strptime(
            lease["expires_at"], "%Y-%m-%dT%H:%M:%S"
        ).strftime("%Y-%m-%d %H:%M")

        secs = time_remaining(lease)
        time_left = format_duration(secs) if secs > 0 else "EXPIRED"

        click.echo(
            f"{lease['user']:<12} {lease['granted_by']:<14} {expires_str:<22} {time_left}"
        )


@main.command()
@click.argument("username")
def show(username: str) -> None:
    """Show full details of the lease for USERNAME."""
    _require_root()

    lease = load_lease(username)
    if lease is None:
        click.echo(f"No lease found for {username!r}.", err=True)
        sys.exit(1)

    secs = time_remaining(lease)
    time_left = format_duration(secs) if secs > 0 else "EXPIRED"

    click.echo(f"User:       {lease['user']}")
    click.echo(f"Granted by: {lease['granted_by']}")
    click.echo(f"Issued at:  {lease['issued_at']}")
    click.echo(f"Expires at: {lease['expires_at']}")
    click.echo(f"Time left:  {time_left}")
    click.echo(f"Warned 5m:  {'Yes' if lease.get('warned_5min') else 'No'}")
    click.echo(f"Warned 1m:  {'Yes' if lease.get('warned_1min') else 'No'}")


@main.command()
@click.argument("username")
@click.option(
    "--duration", required=True, help="Additional duration to add, e.g. 30m, 1h."
)
def extend(username: str, duration: str) -> None:
    """Extend the lease for USERNAME by an additional DURATION."""
    _require_root()

    try:
        extra_seconds = parse_duration(duration)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    try:
        lease = extend_lease(username, extra_seconds)
    except LeaseNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    expiry = datetime.strptime(lease["expires_at"], "%Y-%m-%dT%H:%M:%S")
    click.echo(
        f"Lease for {username} extended by {format_duration(extra_seconds)}."
        f" New expiry: {expiry.strftime('%H:%M:%S')}."
    )
