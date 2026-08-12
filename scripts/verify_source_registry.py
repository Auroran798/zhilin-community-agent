"""Fail closed when source provenance, review state, or checksums are incomplete."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data_pipeline.source_governance import validate_registry


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT/"artifacts/data_quality/knowledge_source_governance.json",
        help="Machine-readable validation output path.",
    )
    args=parser.parse_args()
    result=validate_registry(ROOT/"data/knowledge/source_registry.csv",ROOT/"data/knowledge")
    result["generated_at"]=datetime.now(UTC).isoformat()
    output=args.output
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"]!="PASS": raise SystemExit(1)


if __name__=="__main__": main()
