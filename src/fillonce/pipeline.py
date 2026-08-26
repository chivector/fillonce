from __future__ import annotations

from pathlib import Path

from fillonce.agent import apply_agent_suggestions, suggest_fact_ids
from fillonce.audit import write_audits
from fillonce.extractors import extract_many
from fillonce.integrity import sha256_file
from fillonce.matcher import match_fields
from fillonce.models import Fact, FieldInfo, FillPlan
from fillonce.pdf import apply_pdf_plan, inspect_pdf


def inspect_form(path: str | Path) -> list[FieldInfo]:
    return inspect_pdf(path)


def extract_facts(paths: list[str | Path]) -> list[Fact]:
    return extract_many(paths)


def build_plan(
    form_path: str | Path,
    source_paths: list[str | Path],
    *,
    agent_model: str | None = None,
    agent_base_url: str | None = None,
    agent_api_key: str | None = None,
) -> FillPlan:
    form = Path(form_path).expanduser().resolve()
    sources = [Path(path).expanduser().resolve() for path in source_paths]
    fields = inspect_pdf(form)
    facts = extract_many(sources)
    items = match_fields(fields, facts)
    if agent_model:
        if not agent_base_url:
            raise ValueError("agent_base_url is required when agent_model is set")
        mapping = suggest_fact_ids(
            items,
            facts,
            model=agent_model,
            base_url=agent_base_url,
            api_key=agent_api_key,
        )
        apply_agent_suggestions(items, facts, mapping)
    return FillPlan(
        form_path=str(form),
        sources=[str(path) for path in sources],
        fields=items,
        facts=facts,
        version="2",
        form_sha256=sha256_file(form),
    )


def apply_plan(
    plan: FillPlan,
    output_path: str | Path,
    *,
    form_path: str | Path | None = None,
    audits: bool = True,
    flatten: bool = False,
) -> Path:
    output = apply_pdf_plan(plan, output_path, form_path=form_path, flatten=flatten)
    if audits:
        write_audits(
            plan,
            output,
            original_pdf=form_path or plan.form_path,
            output_mode="flattened" if flatten else "editable",
        )
    return output
