import json

from fillonce.extractors import extract_file


def test_nested_json_extraction_keeps_evidence(tmp_path) -> None:
    source = tmp_path / "profile.json"
    source.write_text(
        json.dumps({"person": {"email": "maya@example.com", "country": "Canada"}}),
        encoding="utf-8",
    )
    facts = extract_file(source)
    assert {(fact.key, fact.value) for fact in facts} == {
        ("email", "maya@example.com"),
        ("country", "Canada"),
    }
    assert all(fact.evidence.source == str(source.resolve()) for fact in facts)
    assert {fact.evidence.locator for fact in facts} == {"person.email", "person.country"}


def test_markdown_extracts_pairs_and_high_precision_facts(tmp_path) -> None:
    source = tmp_path / "resume.md"
    source.write_text(
        "# Profile\n\nOrganization: Open Civic Lab\nReach Maya at maya@example.com.\n",
        encoding="utf-8",
    )
    facts = extract_file(source)
    assert ("organization", "Open Civic Lab") in {(fact.key, fact.value) for fact in facts}
    assert ("email", "maya@example.com") in {(fact.key, fact.value) for fact in facts}
