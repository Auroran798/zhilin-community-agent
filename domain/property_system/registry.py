"""Adapter selection. Keep all real-vendor construction centralized here."""
from __future__ import annotations

from api.config import settings

from .adapters import AdapterNotFound, DemoPropertySystemAdapter, PropertySystemAdapter


def get_property_system_adapter() -> PropertySystemAdapter:
    if settings.property_system_adapter == "demo":
        return DemoPropertySystemAdapter(settings.property_system_demo_data_path)
    raise AdapterNotFound(f"Unsupported property-system adapter: {settings.property_system_adapter}")
