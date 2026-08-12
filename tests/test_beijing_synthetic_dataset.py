import json
from pathlib import Path

from scripts.generate_beijing_synthetic_ops import COUNTS, validate


def test_beijing_synthetic_dataset_is_bounded_labelled_and_non_personal():
    path=Path(__file__).resolve().parents[1]/"data/demo_synthetic/beijing_property_ops_6000.jsonl"
    rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    result=validate(rows)
    assert result["status"]=="PASS"
    assert 3000<=len(rows)<=10000
    assert result["coverage_days"]>=365
    assert result["type_counts"]==COUNTS
    assert all(row["synthetic"] and row["data_class"]=="DEMO_SYNTHETIC" for row in rows)
