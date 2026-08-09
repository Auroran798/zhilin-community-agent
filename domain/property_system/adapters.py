"""Read-only property-system adapter contract and controlled demo adapter."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class AdapterUnavailable(RuntimeError):
    """The selected upstream is unavailable or returned unusable data."""


class AdapterNotFound(LookupError):
    """The selected adapter or upstream record does not exist."""


class AdapterMetadata(BaseModel):
    name: str
    mode: str = "read_only"
    source_kind: str
    supports_writes: bool = False
    contains_real_data: bool = False


class ExternalWorkOrder(BaseModel):
    """The vendor-neutral record exposed to the application and agent."""

    external_id: str
    source_system: str
    property_reference: str
    status: str
    category: str
    priority: str
    summary: str = Field(max_length=500)
    location_description: str = Field(max_length=200)
    risk_level: str = "low"
    created_at: datetime
    updated_at: datetime
    mapping_warnings: list[str] = Field(default_factory=list)


class PropertySystemAdapter(ABC):
    """A deliberately small contract for the first, read-only pilot.

    There are intentionally no create/update/delete methods. A future
    controlled-write phase must introduce a separate reviewed contract rather
    than silently extending this one.
    """

    @property
    @abstractmethod
    def metadata(self) -> AdapterMetadata: ...

    @abstractmethod
    def healthcheck(self) -> dict: ...

    @abstractmethod
    def list_work_orders(self, *, status: str | None = None, limit: int = 20, offset: int = 0) -> tuple[list[ExternalWorkOrder], int]: ...

    @abstractmethod
    def get_work_order(self, external_id: str) -> ExternalWorkOrder: ...


class DemoPropertySystemAdapter(PropertySystemAdapter):
    """Controlled synthetic upstream used to validate the Stage 6 boundary."""

    def __init__(self, data_path: str | Path):
        self._data_path = Path(data_path)
        self._records: list[ExternalWorkOrder] | None = None

    @property
    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(name="demo", source_kind="controlled_synthetic_fixture", contains_real_data=False)

    def _load(self) -> list[ExternalWorkOrder]:
        if self._records is not None:
            return self._records
        try:
            payload = json.loads(self._data_path.read_text(encoding="utf-8"))
            records = payload["work_orders"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise AdapterUnavailable("Demo property-system fixture is unavailable") from exc
        try:
            self._records = [ExternalWorkOrder.model_validate(item) for item in records]
        except Exception as exc:
            raise AdapterUnavailable("Demo property-system fixture does not match the normalized contract") from exc
        return self._records

    def healthcheck(self) -> dict:
        records = self._load()
        return {**self.metadata.model_dump(), "status": "ready", "record_count": len(records)}

    def list_work_orders(self, *, status: str | None = None, limit: int = 20, offset: int = 0) -> tuple[list[ExternalWorkOrder], int]:
        records = self._load()
        filtered = [item for item in records if status is None or item.status == status]
        return filtered[offset : offset + limit], len(filtered)

    def get_work_order(self, external_id: str) -> ExternalWorkOrder:
        for item in self._load():
            if item.external_id == external_id:
                return item
        raise AdapterNotFound(f"External work order '{external_id}' was not found")
