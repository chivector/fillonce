import io
import json
import zipfile

from fastapi.testclient import TestClient
from pypdf import PdfReader

from fillonce.demo import _create_form
from fillonce.web import app


def test_web_plan_and_apply_are_stateless(tmp_path) -> None:
    form_path = tmp_path / "blank.pdf"
    _create_form(form_path)
    form_bytes = form_path.read_bytes()
    client = TestClient(app)
    landing = client.get("/")
    assert landing.status_code == 200
    assert "Preview blank PDF locally" in landing.text
    assert "Evidence candidates" in landing.text

    planned = client.post(
        "/api/plan",
        files=[
            ("form", ("blank.pdf", form_bytes, "application/pdf")),
            (
                "sources",
                ("profile.yaml", b"full_name: Maya Okafor\nemail: maya@example.com\n", "text/yaml"),
            ),
        ],
    )
    assert planned.status_code == 200, planned.text
    plan = planned.json()
    assert plan["form_path"] == "blank.pdf"
    assert plan["form_sha256"]
    assert all("fillonce-" not in fact["evidence"]["source"] for fact in plan["facts"])
    assert next(item for item in plan["fields"] if item["field"]["name"] == "email")[
        "status"
    ] == "ready"

    applied = client.post(
        "/api/apply",
        files={"form": ("blank.pdf", form_bytes, "application/pdf")},
        data={"plan_json": json.dumps(plan)},
    )
    assert applied.status_code == 200, applied.text
    with zipfile.ZipFile(io.BytesIO(applied.content)) as bundle:
        assert set(bundle.namelist()) == {
            "filled-form.pdf",
            "filled-form.audit.html",
            "filled-form.audit.json",
            "fill-plan.json",
        }
        audit = json.loads(bundle.read("filled-form.audit.json"))
        assert audit["integrity"]["original_pdf_sha256"]

    flattened = client.post(
        "/api/apply",
        files={"form": ("blank.pdf", form_bytes, "application/pdf")},
        data={"plan_json": json.dumps(plan), "flatten": "true"},
    )
    assert flattened.status_code == 200, flattened.text
    with zipfile.ZipFile(io.BytesIO(flattened.content)) as bundle:
        static_pdf = PdfReader(io.BytesIO(bundle.read("filled-form.pdf")))
        assert static_pdf.trailer["/Root"].get("/AcroForm") is None
        audit = json.loads(bundle.read("filled-form.audit.json"))
        assert audit["output"]["mode"] == "flattened"

    changed = form_bytes + b"\n% changed after planning\n"
    rejected = client.post(
        "/api/apply",
        files={"form": ("blank.pdf", changed, "application/pdf")},
        data={"plan_json": json.dumps(plan)},
    )
    assert rejected.status_code == 422
    assert "changed after this plan" in rejected.json()["detail"]
