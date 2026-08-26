from __future__ import annotations

import json
import urllib.error
import urllib.request

from fillonce.models import Fact, PlanItem


class AgentError(RuntimeError):
    pass


def suggest_fact_ids(
    items: list[PlanItem],
    facts: list[Fact],
    *,
    model: str,
    base_url: str,
    api_key: str | None = None,
) -> dict[str, str]:
    """Ask an OpenAI-compatible endpoint to link fields to existing fact IDs only."""
    unresolved = [item for item in items if item.status in {"missing", "review"}]
    if not unresolved or not facts:
        return {}
    allowed = {fact.fact_id for fact in facts}
    prompt = {
        "instruction": (
            "Match each PDF field to an existing fact only when they mean the same thing. "
            "Never create or transform a value. Return a JSON object mapping field_name to fact_id. "
            "Omit uncertain fields."
        ),
        "fields": [
            {"field_name": item.field.name, "label": item.field.label, "type": item.field.field_type}
            for item in unresolved
        ],
        "facts": [
            {"fact_id": fact.fact_id, "label": fact.label, "value": fact.value}
            for fact in facts
        ],
    }
    request_body = json.dumps(
        {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "You are a conservative record-linking engine."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        }
    ).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    request = urllib.request.Request(endpoint, data=request_body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - explicit opt-in URL
            payload = json.load(response)
        content = payload["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```")
            content = content.removesuffix("```").strip()
        result = json.loads(content)
    except (OSError, KeyError, IndexError, TypeError, json.JSONDecodeError, urllib.error.URLError) as exc:
        raise AgentError(f"Agent endpoint returned an invalid response: {exc}") from exc
    field_names = {item.field.name for item in unresolved}
    return {
        str(field_name): str(fact_id)
        for field_name, fact_id in result.items()
        if field_name in field_names and fact_id in allowed
    }


def apply_agent_suggestions(items: list[PlanItem], facts: list[Fact], mapping: dict[str, str]) -> None:
    fact_by_id = {fact.fact_id: fact for fact in facts}
    for item in items:
        fact_id = mapping.get(item.field.name)
        if not fact_id or item.status not in {"missing", "review"}:
            continue
        fact = fact_by_id[fact_id]
        item.value = fact.value
        item.fact_id = fact.fact_id
        item.evidence = fact.evidence
        item.status = "review"
        item.confidence = min(max(item.confidence, 0.7), 0.89)
        item.reason = "Agent linked this field to an existing fact; human review required"
        item.selected = False
