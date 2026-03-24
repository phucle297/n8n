"""
python/lib/run_logger.py — Structured JSON run logger.

Usage:
    from lib.run_logger import RunLogger
    logger = RunLogger(run_id="550e8400-...")
    logger.log_stage("fetch_paper", "success", duration_sec=1.2)
    logger.flush()          # writes logs/<run_id>.json
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Literal


StageStatus = Literal["success", "failed", "skipped"]


class RunLogger:
    def __init__(self, run_id: str, log_dir: str = "logs") -> None:
        self.run_id = run_id
        self.log_dir = log_dir
        self.started_at: str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.stages: list[dict] = []
        self._start_times: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Stage timing helpers
    # ------------------------------------------------------------------

    def start_stage(self, stage: str) -> None:
        """Record wall-clock start time for a stage."""
        self._start_times[stage] = time.monotonic()

    def log_stage(
        self,
        stage: str,
        status: StageStatus,
        *,
        duration_sec: float | None = None,
        error: str | None = None,
    ) -> None:
        """
        Append a StageResult entry and immediately flush to disk.

        If duration_sec is None and start_stage() was called for this stage,
        the elapsed time is computed automatically.
        """
        if duration_sec is None and stage in self._start_times:
            duration_sec = round(time.monotonic() - self._start_times.pop(stage), 3)
        elif duration_sec is None:
            duration_sec = 0.0

        entry: dict = {
            "stage": stage,
            "status": status,
            "duration_sec": round(duration_sec, 3),
            "error": error,
        }
        self.stages.append(entry)
        self.flush()

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def flush(self) -> str:
        """Write the current run record to logs/<run_id>.json. Returns the path."""
        os.makedirs(self.log_dir, exist_ok=True)
        path = os.path.join(self.log_dir, f"{self.run_id}.json")
        record = {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "stages": self.stages,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
        return path
