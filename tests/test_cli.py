import json

from pypdf import PdfReader
from typer.testing import CliRunner

from fillonce.cli import app
from fillonce.demo import _create_form

runner = CliRunner()


def test_cli_inspect_extract_plan_apply_and_fill(tmp_path) -> None:
    form = tmp_path / "blank.pdf"
    profile = tmp_path / "profile.yaml"
    fields_json = tmp_path / "fields.json"
    facts_json = tmp_path / "facts.json"
    plan_json = tmp_path / "plan.json"
    editable = tmp_path / "editable.pdf"
    static = tmp_path / "static.pdf"
    _create_form(form)
    profile.write_text(
        "full_name: Maya Okafor\nemail: maya@example.com\nconsent: true\n",
        encoding="utf-8",
    )

    version = runner.invoke(app, ["--version"])
    assert version.exit_code == 0
    assert "FillOnce 0.1.0" in version.stdout

    inspected = runner.invoke(app, ["inspect", str(form), "-o", str(fields_json)])
    assert inspected.exit_code == 0, inspected.stdout
    assert len(json.loads(fields_json.read_text(encoding="utf-8"))) == 8

    extracted = runner.invoke(app, ["extract", str(profile), "-o", str(facts_json)])
    assert extracted.exit_code == 0, extracted.stdout
    assert {fact["key"] for fact in json.loads(facts_json.read_text(encoding="utf-8"))} >= {
        "full_name",
        "email",
        "consent",
    }

    planned = runner.invoke(
        app,
        ["plan", str(form), str(profile), "-o", str(plan_json)],
    )
    assert planned.exit_code == 0, planned.stdout
    payload = json.loads(plan_json.read_text(encoding="utf-8"))
    assert payload["version"] == "2"
    assert payload["form_sha256"]

    applied = runner.invoke(app, ["apply", str(plan_json), "-o", str(editable)])
    assert applied.exit_code == 0, applied.stdout
    assert PdfReader(editable).get_fields()["email"].get("/V") == "maya@example.com"
    assert (tmp_path / "editable.audit.json").exists()
    assert (tmp_path / "editable.audit.html").exists()

    filled = runner.invoke(
        app,
        ["fill", str(form), str(profile), "-o", str(static), "--flatten"],
    )
    assert filled.exit_code == 0, filled.stdout
    assert PdfReader(static).trailer["/Root"].get("/AcroForm") is None
    assert (tmp_path / "static.plan.json").exists()
