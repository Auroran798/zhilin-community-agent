# 阶段 5 综合评测报告

```json
{
  "status": "PASS",
  "mode": "offline deterministic regression with independent fixtures",
  "sample_counts": {
    "intent": 20,
    "extraction": 6,
    "high_risk": 10,
    "prompt_injection": 10,
    "parameter_validation": 8,
    "permission": 4
  },
  "thresholds": {
    "intent_accuracy": 0.9,
    "extraction_f1": 0.8,
    "tool_selection_success_rate": 0.9,
    "parameter_validation_success_rate": 1.0,
    "high_risk_recall": 1.0,
    "prompt_injection_block_rate": 1.0,
    "permission_intercept_rate": 1.0
  },
  "metrics": {
    "intent_accuracy": 1.0,
    "extraction_precision": 0.9286,
    "extraction_recall": 0.9286,
    "extraction_f1": 0.9286,
    "tool_selection_success_rate": 1.0,
    "parameter_validation_success_rate": 1.0,
    "high_risk_recall": 1.0,
    "prompt_injection_block_rate": 1.0,
    "permission_intercept_rate": 1.0,
    "ordinary_answer_average_latency_ms": 0.015,
    "ordinary_answer_p95_latency_ms": 0.019,
    "failed_cases": 0
  },
  "failures": []
}
```
