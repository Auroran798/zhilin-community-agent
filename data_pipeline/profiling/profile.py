from __future__ import annotations

import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from data_pipeline.privacy.sanitizer import PrivacySanitizer


def _date(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def profile_jsonl(path: Path, id_field: str, category_fields: tuple[str, ...], status_fields: tuple[str, ...], text_fields: tuple[str, ...], date_fields: tuple[str, ...]) -> dict:
    rows = 0; columns: Counter[str] = Counter(); missing: Counter[str] = Counter(); seen: set[str] = set(); duplicate_ids = 0
    categories: Counter[str] = Counter(); statuses: Counter[str] = Counter(); dates: list[datetime] = []; text_sizes: list[int] = []; sanitizer = PrivacySanitizer(); pii_hits = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line); rows += 1; columns.update(row.keys())
            for key, value in row.items():
                if value in (None, ""): missing[key] += 1
            record_id = str(row.get(id_field, ""))
            if record_id in seen: duplicate_ids += 1
            seen.add(record_id)
            for key in category_fields:
                if row.get(key): categories[str(row[key])] += 1
            for key in status_fields:
                if row.get(key): statuses[str(row[key])] += 1
            for key in date_fields:
                if value := _date(row.get(key)): dates.append(value)
            for key in text_fields:
                if row.get(key):
                    text = str(row[key]); text_sizes.append(len(text)); pii_hits += sanitizer.pii_hits(text)
    return {"file":str(path).replace("\\", "/"),"row_count":rows,"column_count":len(columns),"null_rate":{key:round(count/rows,6) for key,count in sorted(missing.items())} if rows else {},"duplicate_id_count":duplicate_ids,"time_range":{"min":min(dates).isoformat() if dates else None,"max":max(dates).isoformat() if dates else None},"category_distribution":dict(categories.most_common(50)),"status_distribution":dict(statuses.most_common(50)),"text_length":{"count":len(text_sizes),"mean":round(statistics.mean(text_sizes),2) if text_sizes else 0,"median":round(statistics.median(text_sizes),2) if text_sizes else 0,"max":max(text_sizes,default=0)},"pii_pattern_hits":pii_hits,"address_policy":"raw retrieval query excludes street, house number, apartment and coordinates; normalized output retains only city, borough and ZIP prefix."}


def write_profile(profile: dict, json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# Data profile: {Path(profile['file']).name}", "", f"- Records: {profile['row_count']}", f"- Columns: {profile['column_count']}", f"- Duplicate source IDs: {profile['duplicate_id_count']}", f"- Time range: {profile['time_range']['min']} to {profile['time_range']['max']}", f"- Text length mean / median / max: {profile['text_length']['mean']} / {profile['text_length']['median']} / {profile['text_length']['max']}", f"- PII-pattern hits in analysed text: {profile['pii_pattern_hits']}", f"- Address policy: {profile['address_policy']}", "", "## Categories", "", "| value | count |", "| --- | ---: |"]
    lines.extend(f"| {key} | {value} |" for key, value in profile["category_distribution"].items())
    lines.extend(["", "## Statuses", "", "| value | count |", "| --- | ---: |"])
    lines.extend(f"| {key} | {value} |" for key, value in profile["status_distribution"].items())
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
