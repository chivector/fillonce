from fillonce.matcher import match_field, match_fields
from fillonce.models import Evidence, Fact, FieldInfo
from fillonce.normalization import normalize_value


def fact(number: int, key: str, label: str, value: str) -> Fact:
    return Fact(
        fact_id=f"fact_{number}",
        key=key,
        label=label,
        value=value,
        normalized_value=normalize_value(value),
        evidence=Evidence("profile.yaml", f"line {number}", f"{label}: {value}"),
    )


def test_exact_alias_is_ready() -> None:
    field = FieldInfo("surname", "Surname", "text")
    item = match_field(field, [fact(1, "last_name", "family name", "Okafor")])
    assert item.status == "ready"
    assert item.selected is True
    assert item.value == "Okafor"


def test_conflicting_sources_are_never_selected() -> None:
    field = FieldInfo("email", "Email", "text")
    item = match_field(
        field,
        [
            fact(1, "email", "email", "old@example.com"),
            fact(2, "email", "email address", "new@example.com"),
        ],
    )
    assert item.status == "conflict"
    assert item.selected is False
    assert item.value is None
    assert len(item.candidates) == 2


def test_fuzzy_label_needs_review() -> None:
    field = FieldInfo("org_name", "Organizational affiliation", "text")
    item = match_field(field, [fact(1, "organization", "organization affiliation", "Lab")])
    assert item.status == "review"
    assert item.selected is False


def test_ambiguous_checkbox_value_requires_review() -> None:
    field = FieldInfo("consent", "Consent", "checkbox")
    [item] = match_fields([field], [fact(1, "consent", "consent", "I understand")])
    assert item.status == "review"
    assert item.selected is False


def test_choice_must_be_a_pdf_option() -> None:
    field = FieldInfo("country", "Country", "choice", options=["Canada", "Japan"])
    [item] = match_fields([field], [fact(1, "country", "country", "France")])
    assert item.status == "review"
    assert item.selected is False


def test_signature_is_always_skipped() -> None:
    field = FieldInfo("signature", "Full name", "signature")
    [item] = match_fields([field], [fact(1, "full_name", "full name", "Maya Okafor")])
    assert item.status == "skip"
    assert item.selected is False
