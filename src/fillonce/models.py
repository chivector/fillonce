from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Status = Literal["ready", "review", "missing", "conflict", "skip"]


@dataclass(slots=True)
class Evidence:
    source: str
    locator: str
    excerpt: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return cls(**data)


@dataclass(slots=True)
class Fact:
    fact_id: str
    key: str
    label: str
    value: str
    normalized_value: str
    evidence: Evidence

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Fact:
        data = dict(data)
        data["evidence"] = Evidence.from_dict(data["evidence"])
        return cls(**data)


@dataclass(slots=True)
class FieldInfo:
    name: str
    label: str
    field_type: str
    page: int | None = None
    required: bool = False
    options: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldInfo:
        return cls(**data)


@dataclass(slots=True)
class Candidate:
    fact_id: str
    value: str
    confidence: float
    reason: str
    evidence: Evidence

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Candidate:
        data = dict(data)
        data["evidence"] = Evidence.from_dict(data["evidence"])
        return cls(**data)


@dataclass(slots=True)
class PlanItem:
    field: FieldInfo
    value: str | None
    status: Status
    confidence: float
    reason: str
    fact_id: str | None = None
    evidence: Evidence | None = None
    candidates: list[Candidate] = field(default_factory=list)
    selected: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanItem:
        data = dict(data)
        data["field"] = FieldInfo.from_dict(data["field"])
        if data.get("evidence"):
            data["evidence"] = Evidence.from_dict(data["evidence"])
        data["candidates"] = [Candidate.from_dict(c) for c in data.get("candidates", [])]
        return cls(**data)


@dataclass(slots=True)
class FillPlan:
    form_path: str
    sources: list[str]
    fields: list[PlanItem]
    facts: list[Fact] = field(default_factory=list)
    version: str = "1"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    form_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FillPlan:
        data = dict(data)
        data["fields"] = [PlanItem.from_dict(item) for item in data.get("fields", [])]
        data["facts"] = [Fact.from_dict(fact) for fact in data.get("facts", [])]
        return cls(**data)

    @classmethod
    def from_json_file(cls, path: str | Path) -> FillPlan:
        import json

        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def summary(self) -> dict[str, int]:
        counts = {status: 0 for status in ("ready", "review", "missing", "conflict", "skip")}
        for item in self.fields:
            counts[item.status] += 1
        return counts
