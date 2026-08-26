import json

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from fillonce.demo import _create_form
from fillonce.pdf import FormError, inspect_pdf
from fillonce.pipeline import apply_plan, build_plan


def _profile(path) -> None:
    path.write_text(
        "full_name: Maya Okafor\nemail: maya@example.com\nconsent: true\n",
        encoding="utf-8",
    )


def _radio_form(path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    form = pdf.acroForm
    pdf.drawString(72, 760, "Country")
    pdf.drawString(100, 720, "Canada")
    form.radio(name="country", value="Canada", x=72, y=710, selected=False)
    pdf.drawString(100, 680, "United States")
    form.radio(name="country", value="UnitedStates", x=72, y=670, selected=False)
    pdf.save()


def test_orphaned_widgets_are_recovered_safely(tmp_path) -> None:
    original = tmp_path / "original.pdf"
    orphaned = tmp_path / "orphaned.pdf"
    profile = tmp_path / "profile.yaml"
    _create_form(original)
    _profile(profile)

    reader = PdfReader(original)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.root_object["/AcroForm"].get_object()[NameObject("/Fields")] = ArrayObject()
    with orphaned.open("wb") as handle:
        writer.write(handle)

    assert not (PdfReader(orphaned).get_fields() or {})
    fields = inspect_pdf(orphaned)
    assert {field.name for field in fields} >= {"full_name", "email", "consent"}

    plan = build_plan(orphaned, [profile])
    output = tmp_path / "recovered.pdf"
    apply_plan(plan, output)
    assert PdfReader(output).get_fields()["email"].get("/V") == "maya@example.com"


def test_checkbox_uses_the_forms_real_export_state(tmp_path) -> None:
    original = tmp_path / "original.pdf"
    custom = tmp_path / "custom-checkbox.pdf"
    profile = tmp_path / "profile.yaml"
    _create_form(original)
    _profile(profile)

    reader = PdfReader(original)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    for page in writer.pages:
        for reference in page.get("/Annots", []):
            widget = reference.get_object()
            if str(widget.get("/T")) != "consent":
                continue
            normal = widget["/AP"].get_object()["/N"].get_object()
            normal[NameObject("/Agree")] = normal.pop(NameObject("/Yes"))
    with custom.open("wb") as handle:
        writer.write(handle)

    consent = next(field for field in inspect_pdf(custom) if field.name == "consent")
    assert consent.options == ["/Agree"]
    plan = build_plan(custom, [profile])
    output = tmp_path / "checked.pdf"
    apply_plan(plan, output)
    assert str(PdfReader(output).get_fields()["consent"].get("/V")) == "/Agree"


def test_flattened_output_has_no_interactive_form(tmp_path) -> None:
    form = tmp_path / "blank.pdf"
    profile = tmp_path / "profile.yaml"
    output = tmp_path / "static.pdf"
    _create_form(form)
    _profile(profile)
    plan = build_plan(form, [profile])

    apply_plan(plan, output, flatten=True)
    reader = PdfReader(output)
    assert reader.trailer["/Root"].get("/AcroForm") is None
    assert all(
        annotation.get_object().get("/Subtype") != "/Widget"
        for page in reader.pages
        for annotation in page.get("/Annots", [])
    )
    audit = json.loads((tmp_path / "static.audit.json").read_text(encoding="utf-8"))
    assert audit["output"]["mode"] == "flattened"


def test_original_form_cannot_be_overwritten_in_place(tmp_path) -> None:
    form = tmp_path / "blank.pdf"
    profile = tmp_path / "profile.yaml"
    _create_form(form)
    _profile(profile)
    plan = build_plan(form, [profile])
    original_bytes = form.read_bytes()

    with pytest.raises(FormError, match="must differ"):
        apply_plan(plan, form)
    assert form.read_bytes() == original_bytes


def test_checkbox_rejects_ambiguous_manual_value(tmp_path) -> None:
    form = tmp_path / "blank.pdf"
    profile = tmp_path / "profile.yaml"
    _create_form(form)
    _profile(profile)
    plan = build_plan(form, [profile])
    consent = next(item for item in plan.fields if item.field.name == "consent")
    consent.value = "maybe"
    consent.selected = True
    consent.status = "review"

    with pytest.raises(FormError, match="must be yes/no"):
        apply_plan(plan, tmp_path / "invalid.pdf")


def test_radio_group_uses_export_state_and_widget_appearance(tmp_path) -> None:
    form = tmp_path / "radio.pdf"
    profile = tmp_path / "profile.yaml"
    output = tmp_path / "filled-radio.pdf"
    _radio_form(form)
    profile.write_text("country: Canada\n", encoding="utf-8")

    inspected = inspect_pdf(form)
    assert len(inspected) == 1
    assert inspected[0].field_type == "radio"
    assert inspected[0].options == ["/Canada", "/UnitedStates"]

    plan = build_plan(form, [profile])
    item = plan.fields[0]
    assert item.status == "ready"
    assert item.value == "/Canada"
    assert item.selected is True

    apply_plan(plan, output)
    reader = PdfReader(output)
    assert str(reader.get_fields()["country"].get("/V")) == "/Canada"
    states = [
        str(reference.get_object().get("/AS"))
        for page in reader.pages
        for reference in page.get("/Annots", [])
    ]
    assert states == ["/Canada", "/Off"]


def test_plan_is_bound_to_the_original_form_bytes(tmp_path) -> None:
    form = tmp_path / "blank.pdf"
    changed = tmp_path / "changed.pdf"
    profile = tmp_path / "profile.yaml"
    _create_form(form)
    _profile(profile)
    plan = build_plan(form, [profile])
    changed.write_bytes(form.read_bytes() + b"\n% modified after planning\n")

    assert plan.form_sha256
    with pytest.raises(FormError, match="changed after this plan"):
        apply_plan(plan, tmp_path / "should-not-exist.pdf", form_path=changed)
    assert not (tmp_path / "should-not-exist.pdf").exists()
