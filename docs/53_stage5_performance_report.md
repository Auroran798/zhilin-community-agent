# 阶段 5 并发性能烟测

本结果用于回归检测，不代表生产容量承诺。

```json
{
  "status": "PASS",
  "scenario": "concurrent localhost load smoke (separate API process)",
  "concurrency": 10,
  "requests": 160,
  "failures": 0,
  "failure_examples": [],
  "wall_seconds": 2.645,
  "throughput_rps": 60.5,
  "p50_ms": 81.48,
  "p95_ms": 396.11,
  "by_endpoint": {
    "health": {
      "requests": 50,
      "p50_ms": 35.18,
      "p90_ms": 49.7,
      "p95_ms": 53.5,
      "average_ms": 35.53,
      "p95_threshold_ms": 500.0,
      "threshold_status": "PASS"
    },
    "work_orders": {
      "requests": 50,
      "p50_ms": 79.59,
      "p90_ms": 95.25,
      "p95_ms": 97.56,
      "average_ms": 79.66,
      "p95_threshold_ms": 1000.0,
      "threshold_status": "PASS"
    },
    "dashboard": {
      "requests": 40,
      "p50_ms": 296.73,
      "p90_ms": 571.61,
      "p95_ms": 670.23,
      "average_ms": 338.04,
      "p95_threshold_ms": 1500.0,
      "threshold_status": "PASS"
    },
    "knowledge": {
      "requests": 20,
      "p50_ms": 278.58,
      "p90_ms": 367.26,
      "p95_ms": 429.66,
      "average_ms": 295.32,
      "p95_threshold_ms": 3000.0,
      "threshold_status": "PASS"
    }
  },
  "threshold_failures": [],
  "environment": {
    "platform": "Windows-11-10.0.26200-SP0",
    "python": "3.14.0"
  },
  "limitations": "Local SQLite smoke test only; use production topology and representative data for capacity planning."
}
```
