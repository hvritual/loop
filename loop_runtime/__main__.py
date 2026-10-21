"""Machine-readable CLI. Human credentials must not be made available to worker processes."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from .model import Rejected, VERSION, encode
from .runner import Runner
from .runtime import Runtime
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--root", type=Path, default=Path(".loop-runtime"))
    parser.add_argument("--token-file", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("--policy", type=Path, required=True)
    p = sub.add_parser("command"); p.add_argument("intent"); p.add_argument("action")
    p.add_argument("--data", type=Path, required=True); p.add_argument("--key", required=True); p.add_argument("--expected", type=int, required=True)
    for name in ("status", "resume", "tick", "review"):
        p = sub.add_parser(name); p.add_argument("intent")
    p = sub.add_parser("context"); p.add_argument("intent"); p.add_argument("job")
    p = sub.add_parser("export"); p.add_argument("intent"); p.add_argument("directory", type=Path)
    p = sub.add_parser("work"); p.add_argument("intent"); p.add_argument("--adapter-root", type=Path, required=True)
    p.add_argument("--allow-trusted", action="store_true")
    p = sub.add_parser("run"); p.add_argument("intent"); p.add_argument("--adapter-root", type=Path, required=True)
    p.add_argument("--runner-token-file", type=Path, required=True); p.add_argument("--max-steps", type=int, default=64)
    p.add_argument("--allow-trusted", action="store_true")
    args = parser.parse_args(argv)
    runtime = None
    try:
        if args.command == "init":
            result = Store.initialize(args.root, json.loads(args.policy.read_text(encoding="utf-8")))
        else:
            if not args.token_file:
                raise Rejected("--token-file is required; role names are not credentials")
            runtime = Runtime(args.root, args.token_file.read_text().strip())
            if args.command == "command":
                result = runtime.command(args.intent, args.action, json.loads(args.data.read_text(encoding="utf-8")), key=args.key, expected=args.expected)
            elif args.command == "tick":
                state = runtime.get(args.intent)
                result = runtime.command(args.intent, "tick", {}, key="tick-" + uuid.uuid4().hex, expected=state["revision"])
            elif args.command == "status":
                result = runtime.get(args.intent)
            elif args.command == "resume":
                result = runtime.resume(args.intent)
            elif args.command == "context":
                result = runtime.context(args.intent, args.job)
            elif args.command == "review":
                result = [p for p in runtime.get(args.intent)["proposals"].values() if p["status"] == "pending"]
            elif args.command == "export":
                result = runtime.export(args.intent, args.directory)
            elif args.command == "run":
                if runtime.role != "controller" or not 1 <= args.max_steps <= 1000:
                    raise Rejected("run requires controller identity and 1-1000 finite steps")
                worker_runtime = Runtime(args.root, args.runner_token_file.read_text().strip())
                try:
                    worker = Runner(worker_runtime, args.adapter_root, allow_trusted=args.allow_trusted)
                    for step in range(args.max_steps):
                        state = runtime.get(args.intent)
                        state = runtime.command(args.intent, "tick", {}, key="tick-" + uuid.uuid4().hex, expected=state["revision"])
                        if state["stage"] == "closed" or state["status"] in ("waiting_human", "outcome_pending"):
                            break
                        ran = worker.run_once(args.intent)
                        if not ran["ran"] and state["status"] == "blocked":
                            break
                    result = {"steps": step + 1, "state": runtime.get(args.intent), "finite_step_limit": args.max_steps}
                finally:
                    worker_runtime.close()
            else:
                result = Runner(runtime, args.adapter_root, allow_trusted=args.allow_trusted).run_once(args.intent)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (Rejected, OSError, ValueError, KeyError, TypeError) as exc:
        print(encode({"result": "rejected", "reason": str(exc)}), file=sys.stderr)
        return 2
    finally:
        if runtime:
            runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
