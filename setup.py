"""Setup script for pam-lease."""

import os
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.install import install

LEASE_DIR = "/run/pamlease"


class PostInstallCommand(install):
    """Custom install command that creates the lease directory after install."""

    def run(self):
        """Run the standard install then perform post-install steps."""
        install.run(self)
        self._create_lease_dir()
        self._print_next_steps()

    @staticmethod
    def _create_lease_dir():
        try:
            Path(LEASE_DIR).mkdir(mode=0o700, exist_ok=True)
            os.chmod(LEASE_DIR, 0o700)
            print(f"Created {LEASE_DIR}/ with mode 700.")
        except PermissionError:
            print(
                f"Note: Could not create {LEASE_DIR}/. "
                "Create it manually (requires root):\n"
                f"  sudo mkdir -p {LEASE_DIR} && sudo chmod 700 {LEASE_DIR}"
            )

    @staticmethod
    def _print_next_steps():
        print(
            "\n"
            "=== pam-lease installation complete ===\n"
            "\n"
            "Next steps:\n"
            "\n"
            "1. Build and install the PAM module:\n"
            "     cd pam_lease && make && sudo make install\n"
            "\n"
            "2. Add the following lines to /etc/pam.d/sshd\n"
            "   (place BEFORE the existing auth lines):\n"
            "     auth     required pam_lease.so\n"
            "     session  optional pam_lease.so\n"
            "\n"
            "3. Install and enable the systemd watchdog:\n"
            "     sudo cp systemd/pamlease-watchdog.service /etc/systemd/system/\n"
            "     sudo cp systemd/pamlease-watchdog.timer   /etc/systemd/system/\n"
            "     sudo systemctl daemon-reload\n"
            "     sudo systemctl enable --now pamlease-watchdog.timer\n"
        )


setup(
    name="pam-lease",
    version="1.0.0",
    description="Time-limited SSH access enforced via PAM and a systemd watchdog.",
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="pam-lease contributors",
    python_requires=">=3.10",
    packages=["pamlease"],
    install_requires=[
        "click>=8.0",
    ],
    entry_points={
        "console_scripts": [
            "pamlease=pamlease.cli:main",
            "pamlease-watchdog=pamlease.watchdog:main",
        ],
    },
    cmdclass={
        "install": PostInstallCommand,
    },
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Systems Administration",
    ],
)
