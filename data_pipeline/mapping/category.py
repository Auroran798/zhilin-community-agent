from __future__ import annotations

import csv
from pathlib import Path


COMPLAINT_MAP = {
    "ELEVATOR": ("电梯", "elevator", "high"),
    "PLUMBING": ("给排水", "plumbing", "medium"),
    "WATER LEAK": ("给排水", "water_leak", "high"),
    "HEATING": ("给排水", "heating", "medium"),
    "HEAT/HOT WATER": ("给排水", "hot_water", "high"),
    "ELECTRIC": ("配电设施", "electrical", "high"),
    "DOOR/WINDOW": ("门禁", "door_window", "medium"),
    "UNSANITARY CONDITION": ("公共区域卫生", "sanitation", "medium"),
    "FLOORING/STAIRS": ("道路和地面", "floor_stairs", "medium"),
    "SAFETY": ("消防设施", "safety", "high"),
    "OUTSIDE BUILDING": ("公共区域卫生", "outside", "medium"),
    "GENERAL": ("其他", "general", "low"),
    "PAINT/PLASTER": ("其他", "finish", "low"),
    "NONCONST": ("其他", "non_construction", "low"),
    "APPLIANCE": ("其他", "appliance", "low"),
    "CONSTRUCTION": ("其他", "construction", "medium"),
}
KEYWORDS = (
    (("ELEVATOR",), ("电梯", "elevator", "high")),
    (("FIRE", "SMOKE", "SPRINKLER", "EXIT"), ("消防设施", "fire_safety", "high")),
    (("ELECTRIC", "WIRING", "OUTLET"), ("配电设施", "electrical", "high")),
    (("PLUMB", "WATER", "TOILET", "SINK", "HEAT"), ("给排水", "plumbing", "medium")),
    (("DOOR", "LOCK", "WINDOW"), ("门禁", "access", "medium")),
    (("STAIR", "FLOOR", "HALL"), ("道路和地面", "floor_stairs", "medium")),
    (("ROACH", "MICE", "RAT", "GARBAGE", "UNSANITARY"), ("公共区域卫生", "sanitation", "medium")),
)


def map_category(record_kind: str, external_category: object, text: object = "") -> dict[str, object]:
    category = str(external_category or "").upper().strip()
    if record_kind == "work_order" and category in COMPLAINT_MAP:
        mapped, subcategory, risk = COMPLAINT_MAP[category]
        return {"normalized_category": mapped, "normalized_subcategory": subcategory, "default_risk": risk, "mapping_method": "exact_major_category", "mapping_confidence": 1.0}
    haystack = f"{category} {text or ''}".upper()
    for words, outcome in KEYWORDS:
        if any(word in haystack for word in words):
            mapped, subcategory, risk = outcome
            return {"normalized_category": mapped, "normalized_subcategory": subcategory, "default_risk": risk, "mapping_method": "keyword_rule", "mapping_confidence": 0.85}
    risk = "high" if category == "C" else "medium" if category == "B" else "low"
    # "其他" is an existing domain category, not a missing value.  It retains
    # the source category/text for later human mapping review without inventing
    # a new property-domain enum.
    return {"normalized_category": "其他", "normalized_subcategory": "other", "default_risk": risk, "mapping_method": "default_other", "mapping_confidence": 0.60}


def write_mapping_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for external, (normalized, subcategory, risk) in COMPLAINT_MAP.items():
        rows.append({"source_dataset":"ygpa-z7cr","external_category":external,"external_subcategory":"","normalized_category":normalized,"normalized_subcategory":subcategory,"default_risk":risk,"mapping_method":"exact_major_category","mapping_confidence":"1.00","mapping_version":"stage6-v1","reviewed":"yes","notes":"NYC HPD major category"})
    for external in ("A", "B", "C", "I"):
        result = map_category("inspection_rectification", external)
        rows.append({"source_dataset":"wvxf-dwi5","external_category":external,"external_subcategory":"description keyword applies when available","normalized_category":result["normalized_category"],"normalized_subcategory":result["normalized_subcategory"],"default_risk":result["default_risk"],"mapping_method":result["mapping_method"],"mapping_confidence":str(result["mapping_confidence"]),"mapping_version":"stage6-v1","reviewed":"yes","notes":"Class is a risk signal; description keyword rules override category when a rule matches."})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
