import io
import json

import pytest

from fillonce.agent import AgentError, apply_agent_suggestions, suggest_fact_ids
from fillonce.models import Evidence, Fact, FieldInfo, PlanItem


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def unresolved_item() -> PlanItem:
    return PlanItem(FieldInfo("affiliation", "Affiliation", "text"), None, "missing", 0, "")


def source_fact() -> Fact:
    evidence = Evidence("resume.md", "line 3", "Organization: Open Civic Lab")
    return Fact(
        "fact_1",
        "organization",
        "organization",
        "Open Civic Lab",
        "open civic lab",
        evidence,
    )


def test_agent_can_only_return_supplied_fact_ids(monkeypatch) -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "```json\n{\"affiliation\": \"fact_1\", \"other\": \"invented\"}\n```"
                }
            }
        ]
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: Response(json.dumps(payload).encode()),
    )
    item, fact = unresolved_item(), source_fact()
    mapping = suggest_fact_ids(
        [item], [fact], model="local-model", base_url="http://127.0.0.1:11434/v1"
    )
    assert mapping == {"affiliation": "fact_1"}
    apply_agent_suggestions([item], [fact], mapping)
    assert item.status == "review"
    assert item.selected is False
    assert item.value == "Open Civic Lab"


def test_invalid_agent_response_is_explicit(monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: Response(b'{"choices": []}'),
    )
    with pytest.raises(AgentError, match="invalid response"):
        suggest_fact_ids(
            [unresolved_item()],
            [source_fact()],
            model="local-model",
            base_url="http://127.0.0.1:11434/v1",
        )
