"""Small deterministic Stage 7 API baseline; not a production load claim."""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient

from api.main import app


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    return values[max(0, min(len(values) - 1, int(len(values) * fraction) - 1))]


def main() -> None:
    samples: dict[str, list[float]] = {name: [] for name in ("work_orders", "dashboard", "notifications", "bill_details", "equipment_history", "inspection_tasks")}
    with TestClient(app) as client:
        def login(username: str) -> dict[str, str]:
            payload = client.post("/api/v1/auth/login", json={"username": username, "password": "DemoPass123!"}).json()["data"]
            return {"Authorization": "Bearer " + payload["access_token"]}

        resident, manager, worker = login("resident_demo"), login("manager_demo"), login("maintenance_demo")
        bill_id = client.get("/api/v1/bills", headers=resident).json()["data"][0]["id"]
        equipment = client.get("/api/v1/equipment", headers=manager).json()["data"]
        equipment_id = equipment[0]["id"] if equipment else None
        calls = {
            "work_orders": lambda: client.get("/api/v1/work-orders", headers=resident),
            "dashboard": lambda: client.get("/api/v1/dashboard/summary", headers=manager),
            "notifications": lambda: client.get("/api/v1/notifications", headers=resident),
            "bill_details": lambda: client.get(f"/api/v1/bills/{bill_id}/details", headers=resident),
            "equipment_history": lambda: client.get(f"/api/v1/equipment/{equipment_id}/history", headers=manager) if equipment_id else client.get("/health"),
            "inspection_tasks": lambda: client.get("/api/v1/inspection-tasks", headers=worker),
        }
        for name, call in calls.items():
            for _ in range(25):
                started = time.perf_counter()
                response = call()
                response.raise_for_status()
                samples[name].append((time.perf_counter() - started) * 1000)
    all_values = [value for values in samples.values() for value in values]
    report = {
        "scenario": "in-process, authenticated single-process Stage 7 baseline",
        "requests": len(all_values),
        "failures": 0,
        "p50_ms": round(percentile(all_values, .5), 2),
        "p95_ms": round(percentile(all_values, .95), 2),
        "by_endpoint": {name: {"requests": len(values), "p50_ms": round(percentile(values, .5), 2), "p95_ms": round(percentile(values, .95), 2), "average_ms": round(statistics.mean(values), 2)} for name, values in samples.items()},
        "limitations": "No concurrent users, network hop or external LLM; this is not a production SLA measurement.",
    }
    path = ROOT / "artifacts/performance/stage7_performance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
