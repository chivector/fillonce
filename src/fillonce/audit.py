from __future__ import annotations

import html
import json
from pathlib import Path

from fillonce.integrity import sha256_file
from fillonce.models import FillPlan, PlanItem


def audit_payload(
    plan: FillPlan,
    output_pdf: str | Path | None = None,
    original_pdf: str | Path | None = None,
    output_mode: str = "editable",
) -> dict:
    payload = plan.to_dict()
    payload["summary"] = plan.summary()
    payload["output"] = {"mode": output_mode}
    original = Path(original_pdf or plan.form_path)
    payload["integrity"] = {
        "original_pdf_sha256": sha256_file(original) if original.exists() else None,
        "output_pdf_sha256": sha256_file(output_pdf) if output_pdf and Path(output_pdf).exists() else None,
    }
    return payload


def write_json_audit(
    plan: FillPlan,
    path: str | Path,
    output_pdf: str | Path | None = None,
    original_pdf: str | Path | None = None,
    output_mode: str = "editable",
) -> Path:
    destination = Path(path)
    destination.write_text(
        json.dumps(
            audit_payload(plan, output_pdf, original_pdf, output_mode),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination


def _source_cell(item: PlanItem) -> str:
    if not item.evidence:
        return '<span class="muted">No evidence</span>'
    evidence = item.evidence
    title = html.escape(f"{evidence.source} · {evidence.locator}")
    return f'<span class="source" title="{title}">{html.escape(evidence.excerpt)}</span>'


def write_html_audit(
    plan: FillPlan,
    path: str | Path,
    output_pdf: str | Path | None = None,
    original_pdf: str | Path | None = None,
    output_mode: str = "editable",
) -> Path:
    destination = Path(path)
    summary = plan.summary()
    rows = "".join(
        f"""
        <tr>
          <td><strong>{html.escape(item.field.label)}</strong><small>{html.escape(item.field.name)}</small></td>
          <td>{html.escape(item.value or "—")}</td>
          <td>{"Yes" if item.selected and item.value and item.status not in {"missing", "conflict", "skip"} else "No"}</td>
          <td><span class="pill {item.status}">{item.status}</span></td>
          <td>{_source_cell(item)}</td>
          <td>{html.escape(item.reason)}</td>
        </tr>"""
        for item in plan.fields
    )
    integrity = audit_payload(plan, output_pdf, original_pdf, output_mode)["integrity"]
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>FillOnce audit</title>
<style>
:root{{--ink:#17231d;--muted:#627068;--paper:#fbfcf7;--line:#dfe5dc;--lime:#c9f26b;--green:#176b48;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:48px 24px}} h1{{font-size:38px;letter-spacing:-1.5px;margin:0}} .eyebrow{{color:var(--green);font-weight:800;letter-spacing:.1em;text-transform:uppercase}}
.summary{{display:flex;gap:12px;flex-wrap:wrap;margin:28px 0}} .card{{background:white;border:1px solid var(--line);border-radius:14px;padding:14px 18px;min-width:120px}} .card b{{display:block;font-size:26px}}
table{{width:100%;border-collapse:separate;border-spacing:0;background:white;border:1px solid var(--line);border-radius:16px;overflow:hidden}} th,td{{padding:14px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}} th{{font-size:12px;text-transform:uppercase;color:var(--muted)}} tr:last-child td{{border:0}} td small{{display:block;color:var(--muted)}}
.pill{{display:inline-block;border-radius:999px;padding:3px 9px;font-size:12px;font-weight:800}} .ready{{background:#dcfce7;color:#166534}} .review{{background:#fef3c7;color:#92400e}} .missing{{background:#f1f5f9;color:#475569}} .conflict{{background:#fee2e2;color:#991b1b}} .source{{font-family:ui-monospace,monospace;font-size:12px}} .muted,footer{{color:var(--muted)}}
.hashes{{margin-top:24px;font:11px/1.6 ui-monospace,monospace;color:var(--muted);overflow-wrap:anywhere}} footer{{margin-top:30px}}
@media(max-width:760px){{table,tbody,tr,td{{display:block}} thead{{display:none}} td{{border:0;padding:8px 14px}} tr{{display:block;border-bottom:1px solid var(--line);padding:8px 0}}}}
</style></head><body><main>
<p class="eyebrow">FillOnce · portable evidence</p><h1>Fill audit</h1>
<p>Created {html.escape(plan.created_at)} · {html.escape(output_mode.capitalize())} PDF · Review every value before submitting the form.</p>
<section class="summary">{''.join(f'<div class="card"><b>{count}</b>{status}</div>' for status, count in summary.items() if count)}</section>
<table><thead><tr><th>Field</th><th>Proposed value</th><th>Applied</th><th>Status</th><th>Evidence</th><th>Decision</th></tr></thead><tbody>{rows}</tbody></table>
<div class="hashes"><strong>Original SHA-256</strong> {integrity['original_pdf_sha256'] or 'unavailable'}<br><strong>Output SHA-256</strong> {integrity['output_pdf_sha256'] or 'unavailable'}</div>
<footer>Generated locally by FillOnce. This report records suggestions and sources; it is not proof that a form was submitted.</footer>
</main></body></html>"""
    destination.write_text(document, encoding="utf-8")
    return destination


def write_audits(
    plan: FillPlan,
    output_pdf: str | Path,
    original_pdf: str | Path | None = None,
    output_mode: str = "editable",
) -> tuple[Path, Path]:
    pdf_path = Path(output_pdf)
    stem = pdf_path.with_suffix("")
    json_path = stem.parent / f"{stem.name}.audit.json"
    html_path = stem.parent / f"{stem.name}.audit.html"
    return (
        write_json_audit(plan, json_path, pdf_path, original_pdf, output_mode),
        write_html_audit(plan, html_path, pdf_path, original_pdf, output_mode),
    )
