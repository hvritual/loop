"""Small, strict contracts for a provider-neutral, mode-B controller (Python 3.11+)."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

VERSION = "1.0.0"
STAGES = ("discover", "design", "build", "deploy")
ROLES = ("human", "controller", "runner", "design", "build", "deploy", "explorer", "verifier")
KINDS = ("pre", "execute", "verify", "post", "experiment", "compare")
DIMENSIONS = ("jobs", "seconds", "tokens", "cost_microusd", "pocs")
DEFAULT_LIMITS = {"jobs": 48, "seconds": 2400, "tokens": 120000, "cost_microusd": 0, "pocs": 2}
EXPLORE_LIMITS = {"jobs": 16, "seconds": 900, "tokens": 40000, "cost_microusd": 0, "pocs": 2}


class Rejected(ValueError):
    """A policy/contract/concurrency rejection; never evidence of completion."""


def require(condition, message):
    if not condition:
        raise Rejected(message)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(value, field, maximum=8000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= maximum, f"invalid {field}")
    return value.strip()


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value), "invalid id")
    return value


def number(value, field, minimum=0):
    require(type(value) in (int, float) and math.isfinite(value) and value >= minimum, f"invalid {field}")
    return value


def integer(value, field, minimum=0):
    require(type(value) is int and value >= minimum, f"invalid {field}")
    return value


def relative(value):
    require(isinstance(value, str) and value and "\\" not in value, "invalid relative path")
    p = Path(value)
    require(not p.is_absolute() and all(x not in ("..", ".", "") for x in value.split("/")), "unsafe path")
    require(not any(x in (".git", ".credentials") or x.startswith(".env") for x in p.parts), "private path")
    return value


def binding(state):
    return {k: state[k] for k in ("epoch", "goal_version", "spec_version", "plan_version", "source_commit", "source_hash", "policy_hash")}


def goal_contract(goal):
    require(isinstance(goal, dict), "goal must be an object")
    require(set(goal) <= {"outcome", "non_goals", "constraints", "criteria", "metrics", "ui_required"}, "unknown goal fields")
    text(goal.get("outcome"), "outcome")
    for field in ("non_goals", "constraints"):
        require(isinstance(goal.get(field), list), f"{field} required")
        for entry in goal[field]:
            text(entry, field)
    require(type(goal.get("ui_required", False)) is bool, "ui_required must be boolean")
    criteria = goal.get("criteria")
    require(isinstance(criteria, dict) and set(criteria) == set(STAGES), "criteria required for all four stages")
    ids = []
    for stage, checks in criteria.items():
        require(isinstance(checks, list) and checks, f"empty criteria: {stage}")
        for check in checks:
            require(set(check) == {"id", "description"}, "invalid criterion")
            ids.append(identifier(check["id"]))
            text(check["description"], "criterion")
    require(len(ids) == len(set(ids)), "duplicate criteria")
    for metric in goal.get("metrics", []):
        require(set(metric) == {"id", "operator", "target", "unit"}, "invalid outcome metric")
        identifier(metric["id"])
        require(metric["operator"] in (">=", "<=", "=="), "invalid metric operator")
        number(metric["target"], "target", -1e30)
        text(metric["unit"], "unit")
    mids = [m["id"] for m in goal.get("metrics", [])]
    require(len(mids) == len(set(mids)), "duplicate metric id")
    return goal


def policy_contract(policy):
    require(policy.get("mode") == "B", "only authorization mode B is implemented")
    for name in ("limits", "exploration_limits"):
        require(set(policy.get(name, {})) == set(DIMENSIONS), f"invalid {name}")
        for key, value in policy[name].items():
            integer(value, key)
    for field in ("max_depth", "max_candidates", "max_attempts", "no_gain_limit", "lease_seconds"):
        integer(policy.get(field), field, 1)
    require(policy["lease_seconds"] >= 5, "lease too short")
    caps = policy.get("stage_exploration_limits", {})
    require(not caps or set(caps) == set(STAGES), "stage budgets must cover all stages")
    for limits in caps.values():
        require(set(limits) == set(DIMENSIONS), "invalid stage budget vector")
        for key, value in limits.items():
            integer(value, key)
    adapters = policy.get("adapters")
    require(isinstance(adapters, dict) and adapters, "adapters required")
    for name, adapter in adapters.items():
        identifier(name)
        require(adapter.get("mode") in ("trusted", "docker"), "unknown adapter mode")
        require(adapter.get("role") in ROLES[3:], "invalid adapter role")
        relative(adapter.get("script"))
        require(re.fullmatch(r"[a-f0-9]{64}", adapter.get("sha256", "")), "adapter digest required")
        require(adapter.get("scope") in ("fixture", "local", "sandbox"), "production execution is not enabled")
        for key in ("seconds", "tokens", "cost_microusd"):
            integer(adapter.get(key), key, 1 if key == "seconds" else 0)
        require(adapter["seconds"] < policy["lease_seconds"], "lease must outlive command timeout")
        if adapter["mode"] == "docker":
            require(re.fullmatch(r"sha256:[a-f0-9]{64}", adapter.get("image", "")), "Docker image content ID must be pinned")
            require(adapter["scope"] in ("fixture", "sandbox"), "Docker scope must be sandbox/fixture")
    require(set(policy.get("routing", {})) == set(STAGES) | {"explorer", "verifier"}, "incomplete routing")
    for route, name in policy["routing"].items():
        require(name in adapters, "unknown routed adapter")
        expected = "design" if route in ("discover", "design") else route
        require(adapters[name]["role"] == expected, "adapter role mismatch")
    verifier = adapters[policy["routing"]["verifier"]]
    for stage in STAGES:
        require(adapters[policy["routing"][stage]]["sha256"] != verifier["sha256"], "producer cannot be its own verifier")
    return policy
