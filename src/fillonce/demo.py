from __future__ import annotations

import json
from pathlib import Path

from fillonce.pipeline import apply_plan, build_plan


def _create_form(path: Path) -> None:
    try:
        from reportlab.lib.colors import HexColor
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("The demo needs ReportLab. Run: uv sync --extra demo") from exc

    page_width, page_height = A4
    pdf = canvas.Canvas(str(path), pagesize=A4)
    form = pdf.acroForm
    ink, green, lime, line = map(HexColor, ("#17231d", "#176b48", "#c9f26b", "#dfe5dc"))
    pdf.setFillColor(ink)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(52, page_height - 58, "Northstar Fellowship")
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(green)
    pdf.drawString(52, page_height - 78, "2026 · SYNTHETIC DEMO APPLICATION")
    pdf.setStrokeColor(lime)
    pdf.setLineWidth(5)
    pdf.line(52, page_height - 92, page_width - 52, page_height - 92)

    fields = [
        ("full_name", "Full name", "Full name"),
        ("email", "Email address", "Primary email address"),
        ("phone", "Phone number", "Phone number"),
        ("organization", "Current organization", "Organization"),
        ("job_title", "Current role", "Job title"),
        ("github", "GitHub profile", "GitHub profile"),
        ("country", "Country of residence", "Country"),
    ]
    y = page_height - 135
    for name, label, tooltip in fields:
        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColor(ink)
        pdf.drawString(52, y, label)
        form.textfield(
            name=name,
            tooltip=tooltip,
            x=52,
            y=y - 31,
            width=page_width - 104,
            height=24,
            borderColor=line,
            fillColor=HexColor("#fbfcf7"),
            textColor=ink,
            borderWidth=1,
            fontName="Helvetica",
            fontSize=10,
        )
        y -= 57

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(75, y - 2, "I confirm that I will review this application before submission.")
    form.checkbox(
        name="consent",
        tooltip="Consent",
        x=52,
        y=y - 8,
        size=14,
        checked=False,
        buttonStyle="check",
        borderColor=line,
        fillColor=HexColor("#fbfcf7"),
        textColor=green,
    )
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.setFillColor(HexColor("#627068"))
    pdf.drawString(52, 34, "This form and every identity in the demo are fictional.")
    pdf.save()


def create_demo(output_dir: str | Path) -> dict[str, Path]:
    root = Path(output_dir).expanduser().resolve()
    sources = root / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    form_path = root / "blank-application.pdf"
    profile_path = sources / "profile.yaml"
    resume_path = sources / "resume.md"
    _create_form(form_path)
    profile_path.write_text(
        """# Entirely fictional data for the FillOnce demo
full_name: Maya Okafor
email: maya.okafor@example.com
phone: +1 202 555 0147
country: Canada
consent: true
""",
        encoding="utf-8",
    )
    resume_path.write_text(
        """# Maya Okafor

Organization: Open Civic Lab
Job title: Research engineer
GitHub: https://github.com/maya-example
Email: maya.okafor@example.com
""",
        encoding="utf-8",
    )
    plan = build_plan(form_path, [profile_path, resume_path])
    plan_path = root / "fill-plan.json"
    plan_path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    filled_path = root / "filled-application.pdf"
    apply_plan(plan, filled_path)
    return {
        "filled PDF": filled_path,
        "HTML audit": root / "filled-application.audit.html",
        "JSON audit": root / "filled-application.audit.json",
        "review plan": plan_path,
        "blank form": form_path,
    }
