from __future__ import annotations

from collections import defaultdict

from rapidfuzz.fuzz import ratio

from fillonce.models import Candidate, Fact, FieldInfo, PlanItem
from fillonce.normalization import canonical_key, normalize_label

READY_CONFIDENCE = 0.96
REVIEW_THRESHOLD = 0.72
CHECKBOX_VALUES = {
    "true",
    "yes",
    "y",
    "1",
    "on",
    "checked",
    "false",
    "no",
    "n",
    "0",
    "off",
    "unchecked",
}


def _option_key(value: str) -> str:
    return value.strip().removeprefix("/").casefold()


def _candidate(fact: Fact, confidence: float, reason: str) -> Candidate:
    return Candidate(
        fact_id=fact.fact_id,
        value=fact.value,
        confidence=round(confidence, 3),
        reason=reason,
        evidence=fact.evidence,
    )


def match_field(field: FieldInfo, facts: list[Fact]) -> PlanItem:
    field_key = canonical_key(field.label or field.name)
    exact = [fact for fact in facts if fact.key == field_key]
    if exact:
        distinct_values = {fact.normalized_value for fact in exact}
        candidates = [_candidate(fact, 1.0, "exact semantic alias") for fact in exact]
        if len(distinct_values) > 1:
            return PlanItem(
                field=field,
                value=None,
                status="conflict",
                confidence=1.0,
                reason=f"{len(distinct_values)} different values found for the same fact",
                candidates=candidates,
                selected=False,
            )
        chosen = exact[0]
        return PlanItem(
            field=field,
            value=chosen.value,
            status="ready",
            confidence=1.0,
            reason="exact semantic alias",
            fact_id=chosen.fact_id,
            evidence=chosen.evidence,
            candidates=candidates,
            selected=True,
        )

    field_label = normalize_label(field.label or field.name)
    scored: list[tuple[float, Fact]] = []
    for fact in facts:
        fact_label = normalize_label(fact.label)
        score = ratio(field_label, fact_label) / 100
        if score >= REVIEW_THRESHOLD:
            scored.append((score, fact))
    scored.sort(key=lambda item: item[0], reverse=True)
    candidates = [_candidate(fact, score, "similar label; human review required") for score, fact in scored[:5]]
    if candidates:
        best = candidates[0]
        return PlanItem(
            field=field,
            value=best.value,
            status="review",
            confidence=best.confidence,
            reason=best.reason,
            fact_id=best.fact_id,
            evidence=best.evidence,
            candidates=candidates,
            selected=False,
        )
    return PlanItem(
        field=field,
        value=None,
        status="missing",
        confidence=0.0,
        reason="no supported fact found",
        selected=False,
    )


def match_fields(fields: list[FieldInfo], facts: list[Fact]) -> list[PlanItem]:
    # Keeping this grouping local makes future per-key validators straightforward.
    by_key: dict[str, list[Fact]] = defaultdict(list)
    for fact in facts:
        by_key[fact.key].append(fact)
    ordered = [fact for group in by_key.values() for fact in group]
    items = [match_field(field, ordered) for field in fields]
    for item in items:
        if item.field.field_type in {"signature", "button", "unknown"}:
            item.status = "skip"
            item.selected = False
            item.reason = f"{item.field.field_type} fields are not supported for writing"
            continue
        if item.status != "ready" or item.value is None:
            continue
        if item.field.field_type == "checkbox" and item.value.casefold() not in CHECKBOX_VALUES:
            item.status = "review"
            item.selected = False
            item.reason = "checkbox value is not an explicit yes/no"
        elif item.field.field_type in {"choice", "radio"} and item.field.options:
            option_map = {_option_key(option): option for option in item.field.options}
            option = option_map.get(_option_key(item.value))
            if option is None:
                item.status = "review"
                item.selected = False
                item.reason = "value is not one of the PDF field's allowed choices"
            else:
                item.value = option
    return items
