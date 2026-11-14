#!/usr/bin/env python3
"""Brain UJN SMTP fast runner (one-minute Cron, ~10-second checks).

Invokes existing single-item approved worker in short bursts. Serialized via
local flock to prevent concurrent Cron instances. The database claims jobs
atomically and NEVER retries CLAIMED/UNKNOWN automatically.
"""
import fcntl
import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/ujn/brain-ujn")
LOCK_FILE = ROOT / "state" / "smtp_fast_runner.lock"
WORKER = ROOT / "ujn_smtp_supervised_worker.py"
INTERVAL = 10.0
DURATION = 54.0
SINGLE_CALL_TIMEOUT = 36

def diagnose():
    """No network, no credentials, no SMTP, no queue claims."""
    info = {"fast_runner":"DIAGNOSTIC", "sent_email":False,
            "python_version":sys.version.split()[0],
            "runner_exists":Path(__file__).is_file(),
            "worker_exists":WORKER.is_file(),
            "state_dir_exists":LOCK_FILE.parent.is_dir(),
            "worker_syntax_valid":False}
    if WORKER.is_file():
        try:
            ast.parse(WORKER.read_text(encoding="utf-8"), filename=str(WORKER))
            info["worker_syntax_valid"]=True
        except (SyntaxError, UnicodeError):
            info["worker_syntax_valid"]=False
    print(json.dumps(info),flush=True)
    return 0 if all((info["runner_exists"],info["worker_exists"],
                    info["state_dir_exists"],info["worker_syntax_valid"])) else 2

def main():
    if "--diagnose" in sys.argv[1:]:
        raise SystemExit(diagnose())
    with open(str(LOCK_FILE), "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            print(json.dumps({"fast_runner": "ALREADY_RUNNING", "sent_email": False}), flush=True)
            return
        print(json.dumps({"fast_runner":"STARTED","interval_seconds":INTERVAL,"sent_email":False}),flush=True)
        start = time.monotonic()
        run_index = 0
        while True:
            target = start + run_index * INTERVAL
            remaining = target - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            if time.monotonic() - start >= DURATION:
                break
            run_index += 1
            try:
                process = subprocess.run(
                    [sys.executable, str(WORKER), "--send-one"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True, timeout=SINGLE_CALL_TIMEOUT,
                    env=os.environ.copy(),
                )
                for line in process.stdout.splitlines():
                    if line.strip():
                        print(line, flush=True)
                if process.returncode:
                    print(json.dumps({"fast_runner": "WORKER_ERROR",
                                      "returncode": process.returncode,
                                      "error_type": "See private SMTP worker log"}), flush=True)
                    # Avoid leaking exception content (credentials might be present).
                    break
                if process.stderr:
                    print(json.dumps({"fast_runner": "WORKER_WARNING",
                                      "error_type": "Private worker stderr recorded"}), flush=True)
            except subprocess.TimeoutExpired:
                # The worker could have sent the e-mail. Do not blindly retry the claimed job.
                print(json.dumps({"fast_runner": "WORKER_TIMEOUT",
                                  "manual_reconciliation_required": True}), flush=True)
                break
        print(json.dumps({"fast_runner": "COMPLETE", "checks": run_index}), flush=True)

if __name__ == "__main__":
    main()
