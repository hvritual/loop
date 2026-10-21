"""Finite worker execution. Docker is fail-closed; trusted mode is explicitly NOT a sandbox."""
from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .model import Rejected, digest, encode, file_hash, relative, require

MAX_FILE = 1024 * 1024
MAX_OUTPUT = 10 * MAX_FILE


def regular_files(directory):
    total = 0
    files = []
    for index, p in enumerate(Path(directory).rglob("*")):
        require(index < 2000 and len(p.relative_to(directory).parts) <= 16, "output tree budget exceeded")
        info = p.lstat()
        require(not stat.S_ISLNK(info.st_mode), "symlink output refused")
        if stat.S_ISDIR(info.st_mode):
            continue
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "non-regular or hard-linked output refused")
        total += info.st_size
        require(info.st_size <= MAX_FILE and total <= MAX_OUTPUT and len(files) < 1000, "worker output budget exceeded")
        relative(p.relative_to(directory).as_posix())
        files.append(p)
    return files


def docker_command(image, name, script, inputs, work, output):
    for p in (script, inputs, work, output):
        require("," not in str(p) and "\n" not in str(p), "unsafe Docker mount path")
    return ["docker", "run", "--rm", "--name", name, "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "128",
            "--memory", "256m", "--cpus", "1", "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--mount", f"type=bind,src={script},dst=/adapter/worker.py,readonly",
            "--mount", f"type=bind,src={inputs},dst=/input,readonly",
            "--mount", f"type=bind,src={work},dst=/work",
            "--mount", f"type=bind,src={output},dst=/output",
            image, "python", "-I", "/adapter/worker.py", "/input/context.json", "/work", "/output"]


class Runner:
    def __init__(self, runtime, adapter_root, *, allow_trusted=False):
        require(runtime.role == "runner", "runner credential required")
        self.runtime = runtime
        self.adapter_root = Path(adapter_root).resolve()
        self.allow_trusted = allow_trusted

    def run_once(self, intent):
        rt = self.runtime
        state = rt.get(intent)
        queued = [j for j in state["jobs"].values() if j["status"] == "queued" and rt._current(state, j)]
        if not queued:
            return {"ran": False, "reason": "no queued work"}
        job = sorted(queued, key=lambda j: (j["discovery"] is None, j["created_at"], j["id"]))[0]
        cfg = rt.policy()["adapters"][job["adapter"]]
        script = self.adapter_root / cfg["script"]
        require(script.is_file() and not script.is_symlink() and script.resolve().is_relative_to(self.adapter_root), "invalid adapter path")
        require(file_hash(script) == cfg["sha256"], "adapter content drift")
        if cfg["mode"] == "trusted":
            require(self.allow_trusted, "trusted execution requires explicit --allow-trusted; it is not sandboxed")
        else:
            require(shutil.which("docker"), "Docker unavailable; no trusted fallback")
            inspected = subprocess.run(["docker", "image", "inspect", cfg["image"], "--format", "{{.Id}}"], capture_output=True, timeout=10)
            require(inspected.returncode == 0 and inspected.stdout.decode().strip() == cfg["image"], "pinned local Docker image unavailable; runtime will not pull")
        context = rt.context(intent, job["id"], include_source=True)
        state = rt.command(intent, "claim", {"job": job["id"]}, key="claim-" + uuid.uuid4().hex, expected=state["revision"])
        job = state["jobs"][job["id"]]
        if job["status"] != "running":
            return {"ran": False, "reason": job["status"]}
        nonce = uuid.uuid4().hex
        base = rt.root / "work" / nonce
        inputs, work, output = (base / name for name in ("input", "work", "output"))
        for directory in (inputs, work, output):
            directory.mkdir(parents=True)
        for name, content in context.pop("source_files").items():
            dest = work / relative(name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        if context["previous"]:
            src = rt.root / context["previous"]["path"]
            receipt, _ = rt._load_receipt(context["previous"]["path"])
            previous = inputs / "previous"
            previous.mkdir()
            for name in receipt["files"]:
                dest = previous / relative(name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src.parent / name, dest)
        for stage, handoff in context["handoffs"].items():
            e = rt._valid_evidence(state, handoff["evidence"])
            source_receipt = rt.root / e["path"]
            upstream_receipt, _ = rt._load_receipt(e["path"])
            for filename in upstream_receipt["files"]:
                destination = inputs / "upstream" / stage / relative(filename)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_receipt.parent / filename, destination)
        context["source_manifest"] = {k: digest(v) for k, v in state["source_files"].items()}
        context_file = inputs / "context.json"
        context_file.write_text(encode(context), encoding="utf-8")
        name = "loop-" + nonce
        if cfg["mode"] == "docker":
            for p in [work, output, *work.rglob("*")]:
                p.chmod(0o777 if p.is_dir() else 0o666)
            cmd = docker_command(cfg["image"], name, script, inputs, work, output)
        else:
            cmd = [sys.executable, "-I", str(script), str(context_file), str(work), str(output)]
        log_out, log_err = base / "stdout.log", base / "stderr.log"
        env = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "HOME": str(base),
               "TMPDIR": str(base), "PYTHONDONTWRITEBYTECODE": "1"}
        if os.name == "nt":
            env["SystemRoot"] = os.environ.get("SystemRoot", "C:\\Windows")
        started = time.monotonic()
        error, timed_out, uncertain, code = None, False, False, -1
        proc = None
        try:
            with log_out.open("wb") as stdout, log_err.open("wb") as stderr:
                proc = subprocess.Popen(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                        start_new_session=os.name == "posix")
                while proc.poll() is None:
                    elapsed = time.monotonic() - started
                    over_output = log_out.stat().st_size > MAX_FILE or log_err.stat().st_size > MAX_FILE
                    try:
                        regular_files(output)
                        regular_files(work)
                    except Rejected:
                        over_output = True
                    if elapsed > cfg["seconds"] or over_output:
                        timed_out = elapsed > cfg["seconds"]
                        error = "timeout" if timed_out else "log_output_budget_exceeded"
                        if os.name == "posix":
                            try:
                                os.killpg(proc.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                        else:
                            proc.kill()
                        proc.wait(timeout=5)
                        break
                    time.sleep(0.02)
                code = proc.wait(timeout=5)
        except (OSError, subprocess.SubprocessError) as exc:
            error = "execution error: " + str(exc)
            uncertain = proc is not None and proc.poll() is None
        finally:
            if cfg["mode"] == "docker" and (timed_out or error):
                try:
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
                    check = subprocess.run(["docker", "inspect", name], capture_output=True, timeout=10)
                    absent = check.returncode != 0 and (b"No such object" in check.stderr or b"No such container" in check.stderr)
                    uncertain = uncertain or not absent
                except (OSError, subprocess.SubprocessError):
                    uncertain = True
        evidence = rt.root / "evidence" / nonce
        evidence.mkdir()
        result = None
        try:
            for p in regular_files(output):
                dest = evidence / p.relative_to(output)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dest)
            result_file = evidence / "result.json"
            require(result_file.is_file(), "worker did not return result.json")
            result = json.loads(result_file.read_text(encoding="utf-8"))
            encode(result)  # Reject NaN/Infinity even in fields a worker wants the controller to ignore.
        except (Rejected, OSError, ValueError) as exc:
            result = None
            error = error or "output rejected: " + str(exc)
        for p in (log_out, log_err):
            raw = p.read_bytes()[:MAX_FILE] if p.exists() else b""
            (evidence / p.name).write_bytes(raw)
        files = {p.relative_to(evidence).as_posix(): file_hash(p) for p in regular_files(evidence)}
        receipt = {"protocol": 1, "job": job["id"], "lease": job["lease"], "binding": job["binding"],
                   "adapter": job["adapter"], "adapter_hash": cfg["sha256"], "scope": cfg["scope"],
                   "input_hash": digest(context), "image": cfg.get("image"), "mode": cfg["mode"],
                   "exit_code": code, "timed_out": timed_out, "uncertain": uncertain, "error": error,
                   "elapsed_seconds": time.monotonic() - started, "result": result, "files": files,
                   "metering": {"actual_tokens": None, "actual_cost_microusd": None,
                                "reservation": job["reservation"], "basis": "conservative upper-bound reservation; not an invoice"}}
        receipt_path = evidence / "receipt.json"
        receipt_path.write_text(encode(receipt), encoding="utf-8")
        for p in regular_files(evidence):
            p.chmod(0o444)
        # Work output cannot change a control-plane file: only the controller ingests this receipt.
        latest = rt.get(intent)
        completed = rt.command(intent, "finish", {"job": job["id"], "lease": job["lease"],
                               "receipt": receipt_path.relative_to(rt.root).as_posix()},
                               key="finish-" + nonce, expected=latest["revision"])
        return {"ran": True, "job": job["id"], "status": completed["jobs"][job["id"]]["status"],
                "receipt": receipt_path.relative_to(rt.root).as_posix()}
