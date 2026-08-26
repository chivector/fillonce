from fillonce.models import Evidence, Fact, FieldInfo, FillPlan, PlanItem


def test_plan_json_shape_roundtrips() -> None:
    evidence = Evidence("source.yaml", "email", "email: a@example.com")
    fact = Fact("fact_1", "email", "email", "a@example.com", "a@example.com", evidence)
    item = PlanItem(
        field=FieldInfo("email", "Email", "text", page=1),
        value=fact.value,
        status="ready",
        confidence=1.0,
        reason="exact semantic alias",
        fact_id=fact.fact_id,
        evidence=evidence,
        selected=True,
    )
    original = FillPlan("form.pdf", ["source.yaml"], [item], [fact])
    restored = FillPlan.from_dict(original.to_dict())
    assert restored.to_dict() == original.to_dict()
