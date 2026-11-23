"""Process-Tree Resource Sampling Monitor for Arova Creator Intelligence.

Samples parent and recursive child processes at a high frequency (default: 25ms)
using psutil to capture accurate aggregate Working Set (RSS) memory consumption
across subprocess boundaries (e.g. Python + FFmpeg).
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any
import psutil


class ProcessTreeMonitor:
    """Samples parent and recursive child processes to measure true peak WorkingSet (RSS)."""

    def __init__(self, target_pid: int | None = None, sample_interval_ms: int = 25):
        self.target_pid = target_pid or os.getpid()
        self.sample_interval_sec = sample_interval_ms / 1000.0
        self.sample_interval_ms = sample_interval_ms

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self.samples: list[dict[str, Any]] = []
        self.current_stage: str = "init"
        self.stage_peaks: dict[str, float] = {}

        self.parent_peak_rss_bytes: int = 0
        self.largest_single_process_rss_bytes: int = 0
        self.largest_single_process_info: dict[str, Any] = {}
        self.peak_aggregate_rss_bytes: int = 0
        self.all_observed_processes: dict[int, str] = {}

        self.start_time: float = 0.0
        self.stop_time: float = 0.0

    def set_stage(self, stage_name: str) -> None:
        """Update current pipeline stage for per-stage memory attribution."""
        self.current_stage = stage_name
        if stage_name not in self.stage_peaks:
            self.stage_peaks[stage_name] = 0.0

    def start(self) -> None:
        """Start the background sampling thread."""
        self.start_time = time.perf_counter()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        """Stop the background sampling thread and return structured metrics."""
        self.stop_time = time.perf_counter()
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        elapsed = round(self.stop_time - self.start_time, 3)
        sample_count = len(self.samples)

        # Convert bytes to MB
        to_mb = lambda b: round(b / (1024 * 1024), 2)

        return {
            "elapsed_sec": elapsed,
            "sample_count": sample_count,
            "sample_interval_ms": self.sample_interval_ms,
            "parent_peak_rss_mb": to_mb(self.parent_peak_rss_bytes),
            "largest_single_process_peak_mb": to_mb(self.largest_single_process_rss_bytes),
            "largest_process_info": self.largest_single_process_info,
            "peak_aggregate_rss_mb": to_mb(self.peak_aggregate_rss_bytes),
            "per_stage_peaks_mb": {k: round(v, 2) for k, v in self.stage_peaks.items()},
            "observed_processes": self.all_observed_processes,
            "metric_type": "working_set_rss",
            "sampling_caveat": "Short-lived child processes that start and terminate between 25ms samples represent a lower bound.",
        }

    def _monitor_loop(self) -> None:
        try:
            parent_proc = psutil.Process(self.target_pid)
        except psutil.NoSuchProcess:
            return

        while not self._stop_event.is_set():
            t_sample_start = time.perf_counter()
            try:
                if not parent_proc.is_running():
                    break

                # 1. Parent process memory
                parent_mem = parent_proc.memory_info().rss
                if parent_mem > self.parent_peak_rss_bytes:
                    self.parent_peak_rss_bytes = parent_mem

                if parent_mem > self.largest_single_process_rss_bytes:
                    self.largest_single_process_rss_bytes = parent_mem
                    self.largest_single_process_info = {
                        "pid": parent_proc.pid,
                        "name": parent_proc.name(),
                        "rss_mb": round(parent_mem / (1024 * 1024), 2),
                    }

                self.all_observed_processes[parent_proc.pid] = parent_proc.name()

                aggregate_rss = parent_mem

                # 2. Recursive child processes (e.g. FFmpeg, FFprobe)
                children = parent_proc.children(recursive=True)
                for child in children:
                    try:
                        c_rss = child.memory_info().rss
                        aggregate_rss += c_rss
                        self.all_observed_processes[child.pid] = child.name()

                        if c_rss > self.largest_single_process_rss_bytes:
                            self.largest_single_process_rss_bytes = c_rss
                            self.largest_single_process_info = {
                                "pid": child.pid,
                                "name": child.name(),
                                "rss_mb": round(c_rss / (1024 * 1024), 2),
                            }
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # 3. Track aggregate peak
                if aggregate_rss > self.peak_aggregate_rss_bytes:
                    self.peak_aggregate_rss_bytes = aggregate_rss

                # 4. Stage peak
                agg_mb = aggregate_rss / (1024 * 1024)
                if agg_mb > self.stage_peaks.get(self.current_stage, 0.0):
                    self.stage_peaks[self.current_stage] = agg_mb

                self.samples.append({
                    "timestamp": t_sample_start,
                    "stage": self.current_stage,
                    "aggregate_rss": aggregate_rss,
                })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

            # Precise interval sleep
            t_elapsed = time.perf_counter() - t_sample_start
            sleep_time = max(0.001, self.sample_interval_sec - t_elapsed)
            time.sleep(sleep_time)
