"""Run a concurrent localhost load smoke test against an isolated API process.

This catches locking, connection and latency regressions. It is intentionally
not presented as production capacity planning.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def percentile(samples: list[float], fraction: float) -> float:
    values = sorted(samples)
    index = max(0, min(len(values) - 1, int(len(values) * fraction + 0.9999) - 1))
    return values[index]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_port(port: int, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"API exited with {process.returncode}")
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise TimeoutError("API did not become ready")


def main() -> None:
    runtime = ROOT / "tmp" / f"load-{uuid.uuid4().hex}"
    runtime.mkdir(parents=True)
    port = free_port()
    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{(runtime / 'load.db').as_posix()}",
        "RAG_STORAGE_PATH": str(runtime / "knowledge"),
        "RAG_CHROMA_PATH": str(runtime / "chroma"),
        "AGENT_CHECKPOINT_PATH": str(runtime / "agent.sqlite"),
    }
    process = None
    output = ROOT / "artifacts/performance/stage5_performance.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)
        subprocess.run([sys.executable, "-m", "data.seed"], cwd=ROOT, env=env, check=True)
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        wait_port(port, process)
        base = f"http://127.0.0.1:{port}"

        def token(username: str) -> str:
            response = requests.post(
                base + "/api/v1/auth/login",
                json={"username": username, "password": "DemoPass123!"}, timeout=10,
            )
            response.raise_for_status()
            return response.json()["data"]["access_token"]

        resident = {"Authorization": "Bearer " + token("resident_demo")}
        manager = {"Authorization": "Bearer " + token("manager_demo")}
        scenarios = {
            "health": ("GET", "/health", {}, None, 0.50),
            "work_orders": ("GET", "/api/v1/work-orders", resident, None, 1.00),
            "dashboard": ("GET", "/api/v1/dashboard/summary", manager, None, 1.50),
            "knowledge": ("POST", "/api/v1/knowledge/query", resident, {"query": "装修前需要办理什么手续？", "top_k": "3"}, 3.00),
        }
        # Warm caches and fail before measuring if a scenario is not runnable.
        for method, path, headers, data, _ in scenarios.values():
            response = requests.request(method, base + path, headers=headers, data=data, timeout=10)
            response.raise_for_status()

        work = ["health"] * 50 + ["work_orders"] * 50 + ["dashboard"] * 40 + ["knowledge"] * 20
        workers = 10

        def invoke(name: str) -> tuple[str, float, int, str | None]:
            method, path, headers, data, _ = scenarios[name]
            started = time.perf_counter()
            try:
                response = requests.request(method, base + path, headers=headers, data=data, timeout=10)
                elapsed = (time.perf_counter() - started) * 1000
                return name, elapsed, response.status_code, None if response.ok else response.text[:300]
            except Exception as exc:
                return name, (time.perf_counter() - started) * 1000, 0, f"{type(exc).__name__}: {exc}"

        wall_started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(invoke, work))
        wall_seconds = time.perf_counter() - wall_started

        samples: dict[str, list[float]] = defaultdict(list)
        failures = []
        for name, elapsed, status_code, error in results:
            samples[name].append(elapsed)
            if status_code < 200 or status_code >= 300:
                failures.append({"scenario": name, "status_code": status_code, "error": error})
        metrics = {}
        threshold_failures = []
        for name, values in samples.items():
            threshold_ms = scenarios[name][4] * 1000
            p95 = percentile(values, 0.95)
            metrics[name] = {
                "requests": len(values),
                "p50_ms": round(percentile(values, 0.50), 2),
                "p90_ms": round(percentile(values, 0.90), 2),
                "p95_ms": round(p95, 2),
                "average_ms": round(statistics.mean(values), 2),
                "p95_threshold_ms": threshold_ms,
                "threshold_status": "PASS" if p95 <= threshold_ms else "FAIL",
            }
            if p95 > threshold_ms:
                threshold_failures.append(name)
        all_samples = [value for values in samples.values() for value in values]
        status = "PASS" if not failures and not threshold_failures else "FAIL"
        report = {
            "status": status,
            "scenario": "concurrent localhost load smoke (separate API process)",
            "concurrency": workers,
            "requests": len(results),
            "failures": len(failures),
            "failure_examples": failures[:10],
            "wall_seconds": round(wall_seconds, 3),
            "throughput_rps": round(len(results) / wall_seconds, 2),
            "p50_ms": round(percentile(all_samples, 0.50), 2),
            "p95_ms": round(percentile(all_samples, 0.95), 2),
            "by_endpoint": metrics,
            "threshold_failures": threshold_failures,
            "environment": {"platform": platform.platform(), "python": platform.python_version()},
            "limitations": "Local SQLite smoke test only; use production topology and representative data for capacity planning.",
        }
    except Exception as exc:
        report = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(runtime, ignore_errors=True)

    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "docs/53_stage5_performance_report.md").write_text(
        "# 阶段 5 并发性能烟测\n\n"
        "本结果用于回归检测，不代表生产容量承诺。\n\n"
        "```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
