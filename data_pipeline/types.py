from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    slug: str
    name: str
    domain: str
    country: str
    city: str
    publisher: str
    source_url: str
    api_url: str
    download_url: str
    license: str
    license_url: str
    record_kind: str
    source_id_field: str
    selected_fields: tuple[str, ...]
    order: str
    category_field: str
    source_row_count: int
    strata: tuple[str, ...] = field(default_factory=tuple)
    extra_notes: str = ""
