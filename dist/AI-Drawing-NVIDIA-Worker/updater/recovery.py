"""Argument-free login recovery for an interrupted managed activation."""
from __future__ import annotations

import sys

from .cli import EXIT_INVALID_INVOCATION, EXIT_READY, EXIT_RECOVERY_REQUIRED, ProductionUpdaterServices
from .config import UpdaterConfigError
from .git_source import UpdateError
from .request_lock import RequestLockError
from .state import StateStoreError


def main(argv: list[str] | None = None) -> int:
    if list(sys.argv[1:] if argv is None else argv):
        return EXIT_INVALID_INVOCATION
    try:
        services = ProductionUpdaterServices.from_program_data()
        try:
            with services.run_lock():
                services.recover_activation()
        except UpdateError as error:
            # A normal activation owns the updater run lock while it starts the
            # candidate Worker and proves health. Startup must not wait on or
            # roll back that in-flight switch. OS locks are released by a
            # crash/power loss, so the next login can perform real recovery.
            if error.code == "UPDATE_ALREADY_RUNNING":
                return EXIT_READY
            raise
        return EXIT_READY
    except (OSError, ValueError, UpdateError, UpdaterConfigError, StateStoreError, RequestLockError):
        return EXIT_RECOVERY_REQUIRED


if __name__ == "__main__":
    raise SystemExit(main())
