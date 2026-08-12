import json
from pathlib import Path


def test_controlled_beijing_regression_dataset_has_required_coverage():
    root=Path(__file__).resolve().parents[1]/"evals/beijing"
    rows=[json.loads(line) for line in (root/"controlled_regression_360.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert 300<=len(rows)<=500
    assert len({row["case_id"] for row in rows})==len(rows)
    assert all(row["dataset_status"]=="auto_generated_regression_not_gold" for row in rows)
    assert len({row["category"] for row in rows})>=15
    assert {row["language"] for row in rows}=={"zh-CN","en"}
