"""Long-running ops invoked from API (selfcheck, etc.)."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SELFCHECK_SCRIPT = ROOT / "scripts" / "run_all_selfchecks.py"

_jobs: dict[str, "JobRecord"] = {}
_lock = threading.Lock()


@dataclass
class JobRecord:
    job_id: str
    kind: str
    status: str = "running"
    exit_code: int | None = None
    output: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None


def _run_selfcheck(job: JobRecord) -> None:
    try:
        proc = subprocess.run(
            [sys.executable, str(SELFCHECK_SCRIPT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            env={**__import__("os").environ, "TAX_AGENT_LLM_ENABLED": "0"},
        )
        job.output = (proc.stdout or "") + (proc.stderr or "")
        job.exit_code = proc.returncode
        job.status = "passed" if proc.returncode == 0 else "failed"
    except Exception as exc:  # noqa: BLE001
        job.output = str(exc)
        job.exit_code = 1
        job.status = "failed"
    finally:
        job.finished_at = time.time()


def start_selfcheck() -> JobRecord:
    job = JobRecord(job_id=str(uuid.uuid4()), kind="selfcheck")
    with _lock:
        _jobs[job.job_id] = job
        # keep last 10
        if len(_jobs) > 10:
            for old in sorted(_jobs, key=lambda k: _jobs[k].started_at)[:-10]:
                _jobs.pop(old, None)
    threading.Thread(target=_run_selfcheck, args=(job,), daemon=True).start()
    return job


def get_job(job_id: str) -> JobRecord | None:
    return _jobs.get(job_id)


def job_to_dict(job: JobRecord) -> dict[str, object]:
    return {
        "jobId": job.job_id,
        "kind": job.kind,
        "status": job.status,
        "exitCode": job.exit_code,
        "startedAt": job.started_at,
        "finishedAt": job.finished_at,
        "outputTail": job.output[-8000:] if job.output else "",
    }
