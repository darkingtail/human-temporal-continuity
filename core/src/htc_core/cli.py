from __future__ import annotations

import argparse
import json
import sys

from .core import SilentCore
from .repository import SQLiteRepository


def read_json(path: str | None) -> dict:
    return json.loads(open(path, encoding="utf-8").read()) if path else json.load(sys.stdin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="htc-core")
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
    args = parser.parse_args(argv)
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
