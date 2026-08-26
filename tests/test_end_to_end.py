import json

from pypdf import PdfReader

from fillonce.demo import create_demo
from fillonce.models import FillPlan


def test_demo_creates_editable_pdf_and_audits(tmp_path) -> None:
    paths = create_demo(tmp_path / "demo")
    assert all(path.exists() for path in paths.values())
    fields = PdfReader(paths["filled PDF"]).get_fields()
    assert fields["email"].get("/V") == "maya.okafor@example.com"
    assert fields["organization"].get("/V") == "Open Civic Lab"
    reader = PdfReader(paths["filled PDF"])
    assert "/AcroForm" in reader.trailer["/Root"]
    widget_names = set()
    for page in reader.pages:
        for reference in page.get("/Annots", []):
            widget = reference.get_object()
            if widget.get("/Subtype") != "/Widget":
                continue
            parent = widget.get("/Parent")
            parent = parent.get_object() if parent else {}
            name = str(widget.get("/T") or parent.get("/T"))
            widget_names.add(name)
            assert widget.get("/AP", {}).get("/N"), f"{name} has no normal appearance"
            assert (widget.get("/V") or parent.get("/V")) == fields[name].get("/V")
    assert widget_names == set(fields)

    payload = json.loads(paths["JSON audit"].read_text(encoding="utf-8"))
    assert payload["summary"]["conflict"] == 0
    assert payload["integrity"]["output_pdf_sha256"]
    assert payload["output"]["mode"] == "editable"
    assert "<th>Applied</th>" in paths["HTML audit"].read_text(encoding="utf-8")
    plan = FillPlan.from_json_file(paths["review plan"])
    assert plan.version == "2"
    assert plan.form_sha256
    assert plan.summary()["ready"] >= 7
