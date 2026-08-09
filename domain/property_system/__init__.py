"""Stage 6 property-system integration boundary.

Only normalized, read-only records may cross this boundary. Vendor-specific
schemas and credentials must stay inside an adapter implementation.
"""

from .adapters import AdapterNotFound, AdapterUnavailable, DemoPropertySystemAdapter, PropertySystemAdapter
from .registry import get_property_system_adapter

__all__ = [
    "AdapterNotFound",
    "AdapterUnavailable",
    "DemoPropertySystemAdapter",
    "PropertySystemAdapter",
    "get_property_system_adapter",
]
