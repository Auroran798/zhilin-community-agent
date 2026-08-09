"""Reusable, deterministic Skill contracts for the Stage 3 property agent."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class SkillSpec:
    name: str
    intents: tuple[str, ...]
    required_fields: tuple[str, ...]
    requires_rag: bool
    requires_confirmation: bool
    requires_staff_review: bool
    allowed_tools: tuple[str, ...]
    missing_question: dict[str, str]

    def missing(self, fields: dict[str, object]) -> list[str]:
        return [field for field in self.required_fields if not fields.get(field)]

    def question_for(self, field: str) -> str:
        return self.missing_question.get(field, f"请补充{field}。")
