from __future__ import annotations

import re


class PrivacySanitizer:
    """Conservative redaction for text sent to the application, Agent, or UI."""
    patterns = (
        (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[EMAIL_REDACTED]"),
        (re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"), "[PHONE_REDACTED]"),
        (re.compile(r"(?i)\b(?:apt\.?|apartment|unit|suite|room)\s*[A-Z0-9-]+"), "[UNIT_REDACTED]"),
        (re.compile(r"(?i)\b\d{1,5}\s+[A-Z][A-Z .'-]{2,}\s(?:ST|STREET|AVE|AVENUE|ROAD|RD|BLVD|DRIVE|LANE)\b"), "[ADDRESS_REDACTED]"),
    )

    def sanitize_text(self, value: object) -> str:
        text = "" if value is None else str(value)
        for pattern, replacement in self.patterns:
            text = pattern.sub(replacement, text)
        return " ".join(text.split())[:4_000]

    def pii_hits(self, value: object) -> int:
        text = "" if value is None else str(value)
        return sum(len(pattern.findall(text)) for pattern, _ in self.patterns)
