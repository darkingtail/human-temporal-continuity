from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .core import SilentCore
from .doctor import run_doctor
from .installer import (
    InstallError,
    InstallPlan,
    InstallRequest,
    apply_install_plan,
    build_install_plan,
    rollback_install,
)
from .launcher import ensure_runtime, runtime_status
from .repository import SQLiteRepository


def read_json(path: str | None) -> dict:
    return json.loads(open(path, encoding="utf-8").read()) if path else json.load(sys.stdin)


def _default_source_root() -> Path:
    candidate = Path(__file__).resolve().parents[2]
    return candidate


def _default_program_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "HTC"


def _default_data_root() -> Path:
    return Path(os.environ.get("HTC_DATA_HOME", Path.home() / ".htc")).expanduser()


def _default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def _install_request(args: argparse.Namespace) -> InstallRequest:
    return InstallRequest(
        source_root=args.source_root,
        program_root=args.program_root,
        data_root=args.data_root,
        codex_home=args.codex_home,
        python_executable=args.python_executable,
        version=args.version,
        timezone=args.timezone,
    )


def _add_install_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-root", type=Path, default=_default_source_root())
    parser.add_argument("--program-root", type=Path, default=_default_program_root())
    parser.add_argument("--data-root", type=Path, default=_default_data_root())
    parser.add_argument("--codex-home", type=Path, default=_default_codex_home())
    parser.add_argument("--python", dest="python_executable", type=Path, default=Path(sys.executable))
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--timezone", default="Asia/Shanghai")


def _manifest_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_default_data_root() / "install-manifest.json",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="htc")
    parser.add_argument("--db", default=":memory:")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("observe", "decide", "revise", "entity", "recall", "policy", "import-source", "import-start", "import-batch", "bootstrap"):
        p = sub.add_parser(name)
        p.add_argument("--input")
    p = sub.add_parser("explain")
    p.add_argument("--id", required=True)
    p.add_argument("--user-id", required=True)
    p = sub.add_parser("validate")
    p.add_argument("--id", required=True)
    p.add_argument("--now", required=True)
    p = sub.add_parser("install", help="Preview or apply a user-level HTC installation")
    _add_install_paths(p)
    p.add_argument("--out", type=Path)
    p.add_argument("--plan-file", type=Path)
    p.add_argument("--dry-run", action="store_true", help="Only print the plan (default)")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("doctor", help="Read-only installation diagnostics")
    _manifest_arg(p)
    p = sub.add_parser("rollback", help="Preview or restore the last exact preimage")
    _manifest_arg(p)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("uninstall", help="Remove HTC-managed files and keep user data")
    _manifest_arg(p)
    p.add_argument("--keep-data", action="store_true", default=True)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("runtime", help="Inspect or bootstrap the HTC daemon")
    runtime_sub = p.add_subparsers(dest="runtime_command", required=True)
    runtime_sub.add_parser("status")
    ensure_parser = runtime_sub.add_parser("ensure")
    ensure_parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)
    if args.command == "install":
        try:
            plan = InstallPlan.load(args.plan_file) if args.plan_file else build_install_plan(_install_request(args))
            if args.out:
                plan.write(args.out)
            result: dict[str, object] = {
                "mode": "apply" if args.apply else "dry-run",
                "changed": plan.changed,
                "operation_id": plan.operation_id,
                "files": [str(item.path) for item in plan.files if item.preimage_sha256 != item.postimage_sha256],
                "plan_file": str(args.out) if args.out else None,
            }
            if args.apply:
                result["manifest"] = apply_install_plan(plan)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except InstallError as error:
            print(json.dumps({"error": str(error)}, ensure_ascii=False))
            return 2
    if args.command == "doctor":
        result = run_doctor(args.manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    if args.command in {"rollback", "uninstall"}:
        try:
            result = rollback_install(args.manifest, apply=args.apply)
            result["action"] = args.command
            result["keep_data"] = True
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except InstallError as error:
            print(json.dumps({"error": str(error)}, ensure_ascii=False))
            return 2
    if args.command == "runtime":
        if args.runtime_command == "status":
            print(json.dumps(runtime_status(), ensure_ascii=False, indent=2))
            return 0
        ok = ensure_runtime(timeout=args.timeout)
        print(json.dumps({"started_or_running": ok, **runtime_status()}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    core = SilentCore(SQLiteRepository(args.db))
    if args.command == "observe":
        body = read_json(args.input)
        result = core.observe(body["request"], body["proposal"])
    elif args.command == "decide":
        body = read_json(args.input)
        result = core.decide(
            body["candidate_id"],
            body.get("decision", "accept"),
            body["now"],
            summary=body.get("summary"),
            permissions=body.get("permissions"),
            memory_id=body.get("memory_id"),
            merge_into_memory_id=body.get("merge_into_memory_id"),
        )
    elif args.command == "recall":
        result = core.recall(read_json(args.input))
    elif args.command == "revise":
        body = read_json(args.input)
        result = core.revise(
            body["memory_id"],
            body["now"],
            expected_revision=body["expected_revision"],
            action=body["action"],
            source_id=body["source_id"],
            summary=body.get("summary"),
            time=body.get("time"),
        )
    elif args.command == "entity":
        body = read_json(args.input)
        result = core.canonicalize_entity(**body)
    elif args.command == "validate":
        result = {"valid": core.validate_package(args.id, args.now)}
    elif args.command == "policy":
        body = read_json(args.input)
        result = core.set_user_policy(**body)
    elif args.command == "import-source":
        result = core.register_import_source(read_json(args.input))
    elif args.command == "import-start":
        result = core.start_import(read_json(args.input))
    elif args.command == "import-batch":
        body = read_json(args.input)
        result = core.import_batch(body["job_id"], body["records"], body["now"])
    elif args.command == "bootstrap":
        result = core.finalize_bootstrap(read_json(args.input))
    else:
        result = core.explain(args.id, user_id=args.user_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
