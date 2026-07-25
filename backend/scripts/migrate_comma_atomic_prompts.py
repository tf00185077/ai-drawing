"""Privileged offline CLI for the comma-atomic Prompt Library migration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.comma_atomic_migration import (  # noqa: E402
    CommaAtomicPromptLibraryMigration,
    canonical_json_bytes,
)


def _write_report(path: Path | None, payload: object) -> None:
    raw = canonical_json_bytes(payload)
    if path is None:
        sys.stdout.buffer.write(raw)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "audit",
            "dry-run",
            "apply",
            "resume",
            "rollback",
            "validate",
            "activate-enforcement",
            "finalize",
            "status",
        ],
    )
    parser.add_argument("--library-root", type=Path, default=REPO_ROOT / "prompt_library")
    parser.add_argument("--plan-hash")
    parser.add_argument("--run-id")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    migration = CommaAtomicPromptLibraryMigration(args.library_root)
    if args.action == "status":
        _write_report(
            args.report,
            migration.control.bootstrap().model_dump(mode="json"),
        )
        return 0

    privilege = migration.issue_privilege()
    if args.action in {"audit", "dry-run", "validate"}:
        report = migration.audit(privilege, mode=args.action)
        _write_report(args.report, report.model_dump(mode="json"))
        return 0 if report.eligible else 2
    if args.action == "apply":
        if not args.plan_hash:
            parser.error("apply requires --plan-hash from the reviewed dry-run")
        result = migration.apply(
            privilege,
            plan_hash=args.plan_hash,
            run_id=args.run_id,
        )
    elif args.action == "resume":
        if not args.plan_hash or not args.run_id:
            parser.error("resume requires --plan-hash and --run-id")
        result = migration.resume(
            privilege,
            plan_hash=args.plan_hash,
            run_id=args.run_id,
        )
    elif args.action == "rollback":
        if not args.run_id:
            parser.error("rollback requires --run-id")
        result = migration.rollback(privilege, run_id=args.run_id)
    elif args.action == "activate-enforcement":
        if not args.plan_hash:
            parser.error("activate-enforcement requires --plan-hash")
        migration.activate_atomic_enforcement(
            privilege,
            plan_hash=args.plan_hash,
        )
        _write_report(
            args.report,
            migration.control.status().model_dump(mode="json"),
        )
        return 0
    else:
        if not args.plan_hash:
            parser.error("finalize requires --plan-hash")
        result = migration.finalize(privilege, plan_hash=args.plan_hash)
    _write_report(args.report, result.model_dump(mode="json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
