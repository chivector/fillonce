from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import HTMLResponse, JSONResponse, Response
except ImportError as exc:  # pragma: no cover - only reached without the optional web extra
    raise RuntimeError("Install the web extra first: uv sync --extra web") from exc

from fillonce.models import FillPlan
from fillonce.pipeline import apply_plan, build_plan

app = FastAPI(title="FillOnce", docs_url=None, redoc_url=None)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_SOURCE_SUFFIXES = {".json", ".yaml", ".yml", ".csv", ".txt", ".md", ".docx", ".pdf"}


def _safe_name(name: str | None, fallback: str) -> str:
    candidate = Path(name or fallback).name
    return candidate if candidate not in {"", ".", ".."} else fallback


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"{upload.filename or 'Upload'} is larger than 25 MB")
    destination.write_bytes(content)
    await upload.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "storage": "request-scoped"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


@app.post("/api/plan")
async def plan_endpoint(
    form: UploadFile = File(...), sources: list[UploadFile] = File(...)
) -> JSONResponse:
    if Path(form.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(400, "The blank form must be a PDF")
    if not sources:
        raise HTTPException(400, "Add at least one source document")
    with tempfile.TemporaryDirectory(prefix="fillonce-") as temp:
        root = Path(temp)
        form_path = root / _safe_name(form.filename, "form.pdf")
        await _save_upload(form, form_path)
        source_paths: list[Path] = []
        for index, upload in enumerate(sources):
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in ALLOWED_SOURCE_SUFFIXES:
                raise HTTPException(400, f"Unsupported source type: {suffix or 'unknown'}")
            path = root / f"source-{index}-{_safe_name(upload.filename, f'source{suffix}') }"
            await _save_upload(upload, path)
            source_paths.append(path)
        try:
            plan = build_plan(form_path, source_paths)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        payload = plan.to_dict()
        payload["form_path"] = _safe_name(form.filename, "form.pdf")
        for fact in payload["facts"]:
            fact["evidence"]["source"] = Path(fact["evidence"]["source"]).name.split("-", 2)[-1]
        for item in payload["fields"]:
            if item.get("evidence"):
                item["evidence"]["source"] = Path(item["evidence"]["source"]).name.split("-", 2)[-1]
            for candidate in item.get("candidates", []):
                candidate["evidence"]["source"] = Path(candidate["evidence"]["source"]).name.split("-", 2)[-1]
        payload["sources"] = [_safe_name(upload.filename, "source") for upload in sources]
        return JSONResponse(payload)


@app.post("/api/apply")
async def apply_endpoint(
    form: UploadFile = File(...),
    plan_json: str = Form(...),
    flatten: bool = Form(False),
) -> Response:
    try:
        plan = FillPlan.from_dict(json.loads(plan_json))
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(400, f"Invalid review plan: {exc}") from exc
    with tempfile.TemporaryDirectory(prefix="fillonce-") as temp:
        root = Path(temp)
        form_path = root / "blank-form.pdf"
        await _save_upload(form, form_path)
        output = root / "filled-form.pdf"
        try:
            apply_plan(plan, output, form_path=form_path, flatten=flatten)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(output, "filled-form.pdf")
            bundle.write(root / "filled-form.audit.html", "filled-form.audit.html")
            bundle.write(root / "filled-form.audit.json", "filled-form.audit.json")
            bundle.writestr("fill-plan.json", json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
        return Response(
            archive.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="fillonce-results.zip"'},
        )


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FillOnce · Private PDF form filling</title>
<style>
:root{--ink:#15231c;--muted:#67736c;--paper:#f7f9f2;--card:#fff;--line:#dce4d9;--green:#176b48;--lime:#c9f26b;--red:#b42318;--yellow:#9a6700}
*{box-sizing:border-box} body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}
button,input{font:inherit} .shell{max-width:1180px;margin:auto;padding:24px}.nav{display:flex;align-items:center;justify-content:space-between;padding:8px 0 44px}.brand{font-weight:900;font-size:21px;letter-spacing:-.6px}.brand i{display:inline-block;width:13px;height:13px;background:var(--lime);border-radius:4px;margin-right:8px;box-shadow:5px -5px 0 var(--green)}.private{font-size:12px;color:var(--green);font-weight:700}.hero{display:grid;grid-template-columns:1.25fr .75fr;gap:48px;align-items:end;margin-bottom:35px}.eyebrow{font-size:12px;font-weight:800;color:var(--green);text-transform:uppercase;letter-spacing:.12em}.hero h1{font-size:clamp(42px,7vw,76px);line-height:.95;letter-spacing:-4px;margin:12px 0 18px;max-width:850px}.hero p{font-size:18px;color:var(--muted);max-width:650px}.promise{border-left:4px solid var(--lime);padding-left:18px;font-weight:750;font-size:17px}
.workspace{background:var(--card);border:1px solid var(--line);border-radius:24px;box-shadow:0 18px 50px rgba(21,35,28,.08);overflow:hidden}.steps{display:flex;border-bottom:1px solid var(--line);padding:0 26px}.step{padding:18px 12px;margin-right:20px;color:var(--muted);font-weight:700;font-size:13px;border-bottom:3px solid transparent}.step.active{color:var(--green);border-color:var(--lime)}.panel{padding:32px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.drop{display:block;border:1.5px dashed #b8c5b6;background:#fbfcf8;border-radius:16px;padding:28px;cursor:pointer;min-height:170px;transition:.2s}.drop:hover,.drop.drag{border-color:var(--green);background:#f5faec}.drop input{position:absolute;opacity:0;width:1px;height:1px}.drop:focus-within{outline:3px solid var(--lime);outline-offset:2px}.drop .icon{font-size:24px}.drop strong{display:block;margin:9px 0 4px;font-size:17px}.drop span{display:block;color:var(--muted);font-size:13px}.filelist{margin-top:12px;color:var(--green);font-weight:700;overflow-wrap:anywhere}.actions{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:22px}.note{color:var(--muted);font-size:12px;max-width:560px}.primary{border:0;border-radius:12px;background:var(--ink);color:white;font-weight:800;padding:13px 20px;cursor:pointer;box-shadow:4px 4px 0 var(--lime)}.primary:hover{background:var(--green)}.primary:disabled{opacity:.5;cursor:wait}.hidden{display:none!important}
.summary{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}.counter{border:1px solid var(--line);border-radius:12px;padding:8px 13px}.counter b{font-size:20px;margin-right:5px}.counter.selected{background:var(--ink);color:white}.tablewrap{overflow:auto;border:1px solid var(--line);border-radius:14px}table{width:100%;border-collapse:collapse;min-width:1020px}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:11px;text-transform:uppercase;color:var(--muted);letter-spacing:.06em}tbody tr:last-child td{border:0}.field small,.evidence small{display:block;color:var(--muted)}.required{display:inline-block;margin-left:6px;color:var(--red);font-size:10px;text-transform:uppercase;letter-spacing:.04em}.value,.candidate{width:100%;min-width:170px;border:1px solid var(--line);border-radius:8px;padding:8px;background:#fbfcf8;color:var(--ink)}.candidate-wrap{display:grid;gap:4px;margin-top:9px}.candidate-wrap span{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:var(--green)}.check{width:18px;height:18px;accent-color:var(--green)}.pill{font-size:11px;font-weight:850;border-radius:100px;padding:4px 8px;white-space:nowrap}.pill.ready{background:#dcfce7;color:#166534}.pill.review{background:#fef3c7;color:#92400e}.pill.missing,.pill.skip{background:#eef2f0;color:#53615a}.pill.conflict{background:#fee2e2;color:#991b1b}.reason{font-size:12px;color:var(--muted);max-width:180px}.preview{margin-top:22px;border:1px solid var(--line);border-radius:14px;background:#fbfcf8;overflow:hidden}.preview summary{cursor:pointer;padding:13px 16px;color:var(--green);font-weight:800}.preview object{display:block;width:100%;height:520px;border:0;border-top:1px solid var(--line)}.review-options{display:grid;gap:7px;max-width:540px}.mode{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:750;color:var(--green);cursor:pointer}.mode input{width:16px;height:16px;accent-color:var(--green)}.error{margin-top:18px;padding:12px 15px;border-radius:10px;background:#fee2e2;color:var(--red);font-weight:700}.loading{display:inline-block;width:14px;height:14px;border:2px solid #ffffff66;border-top-color:white;border-radius:50%;animation:spin .8s linear infinite;margin-right:7px}@keyframes spin{to{transform:rotate(360deg)}}footer{display:flex;justify-content:space-between;gap:20px;padding:30px 0;color:var(--muted);font-size:12px}
@media(max-width:750px){.hero,.grid{grid-template-columns:1fr}.hero{gap:12px}.hero h1{letter-spacing:-2.5px}.steps{padding:0 12px}.step{margin-right:5px}.panel{padding:20px}.actions,footer{align-items:stretch;flex-direction:column}.primary{width:100%}}
</style></head><body><div class="shell">
<nav class="nav"><div class="brand"><i></i>FillOnce</div><div class="private">● LOCAL · REQUEST-SCOPED</div></nav>
<section class="hero"><div><div class="eyebrow">Documents in. Paperwork out.</div><h1>Your files already know the answers.</h1><p>Fill an editable PDF from facts you already have. See the exact source behind every proposed value.</p></div><div class="promise">Never invent a fact.<br>Never submit without you.</div></section>
<main class="workspace"><div class="steps"><div class="step active" id="s1">1 · Add files</div><div class="step" id="s2">2 · Review evidence</div><div class="step" id="s3">3 · Download</div></div>
<section class="panel" id="uploadPanel"><div class="grid">
  <label class="drop" id="formDrop"><input id="form" type="file" aria-label="Blank PDF form" accept="application/pdf,.pdf"><span class="icon">▱</span><strong>Blank PDF form</strong><span>Native AcroForm fields · up to 25 MB</span><div class="filelist" id="formName">Choose a PDF</div></label>
  <label class="drop" id="sourceDrop"><input id="sources" type="file" aria-label="Files containing answers" multiple accept=".json,.yaml,.yml,.csv,.txt,.md,.docx,.pdf"><span class="icon">≡</span><strong>Files containing answers</strong><span>JSON, YAML, CSV, text, Markdown, DOCX, or PDF</span><div class="filelist" id="sourceNames">Choose one or more files</div></label>
</div><div class="actions"><div class="note">Files are processed in a temporary directory and removed before the request completes. The server makes no outbound network calls.</div><button class="primary" id="planBtn">Build review plan →</button></div><details class="preview hidden" id="previewPanel"><summary>Preview blank PDF locally</summary><object id="pdfPreview" type="application/pdf" title="Blank PDF preview"><p>Your browser cannot preview this PDF. You can still build a review plan.</p></object></details><div class="error hidden" id="uploadError"></div></section>
<section class="panel hidden" id="reviewPanel"><div class="summary" id="summary"></div><div class="tablewrap"><table><thead><tr><th>Use</th><th>PDF field</th><th>Proposed value</th><th>Status</th><th>Evidence</th><th>Why</th></tr></thead><tbody id="rows"></tbody></table></div><div class="actions"><button class="primary" id="backBtn" style="background:#fff;color:var(--ink);box-shadow:none;border:1px solid var(--line)">← Change files</button><div class="review-options"><div class="note">Only checked values are written. Edits you type here are recorded as human-confirmed.</div><label class="mode"><input id="flatten" type="checkbox"> Make a static copy (remove editable fields)</label></div><button class="primary" id="applyBtn">Create editable PDF + audit →</button></div><div class="error hidden" id="reviewError"></div></section>
</main><footer><span>Open source · local first · no telemetry</span><span>Review the result before signing or submitting.</span></footer></div>
<script>
const $=s=>document.querySelector(s), form=$('#form'), sources=$('#sources'); let plan=null,previewUrl=null;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
form.onchange=()=>{const file=form.files[0];$('#formName').textContent=file?.name||'Choose a PDF';if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=file?URL.createObjectURL(file):null;$('#pdfPreview').data=previewUrl||'';$('#previewPanel').classList.toggle('hidden',!file)};
sources.onchange=()=>{$('#sourceNames').textContent=[...sources.files].map(f=>f.name).join(', ')||'Choose one or more files'};
function busy(btn,on,label){btn.disabled=on;btn.innerHTML=on?'<i class="loading"></i>'+label:btn.dataset.normal}
function error(id,msg){const el=$(id);el.textContent=msg;el.classList.toggle('hidden',!msg)}
function stage(n){[1,2,3].forEach(i=>$('#s'+i).classList.toggle('active',i===n))}
$('#planBtn').dataset.normal=$('#planBtn').innerHTML; $('#applyBtn').dataset.normal=$('#applyBtn').innerHTML;
function updateOutputLabel(){const label=$('#flatten').checked?'Create static PDF + audit →':'Create editable PDF + audit →';$('#applyBtn').dataset.normal=label;$('#applyBtn').innerHTML=label} $('#flatten').onchange=updateOutputLabel;
$('#planBtn').onclick=async()=>{error('#uploadError','');if(!form.files[0]||!sources.files.length){error('#uploadError','Choose a blank PDF and at least one source file.');return}const data=new FormData();data.append('form',form.files[0]);[...sources.files].forEach(f=>data.append('sources',f));busy($('#planBtn'),true,'Reading evidence…');try{const res=await fetch('/api/plan',{method:'POST',body:data});const body=await res.json();if(!res.ok)throw Error(body.detail||'Could not build a plan');plan=body;render();$('#uploadPanel').classList.add('hidden');$('#reviewPanel').classList.remove('hidden');stage(2)}catch(e){error('#uploadError',e.message)}finally{busy($('#planBtn'),false)}};
function valueControl(i,n){const label=esc(i.field.label),current=String(i.value||'');if(i.field.field_type==='checkbox'){const yes=['true','yes','y','1','on','checked'].includes(current.toLowerCase()),no=['false','no','n','0','off','unchecked'].includes(current.toLowerCase());return `<select class="value" aria-label="Value for ${label}" data-n="${n}"><option value="">Choose…</option><option value="Yes" ${yes?'selected':''}>Yes</option><option value="No" ${no?'selected':''}>No</option></select>`}if(['choice','radio'].includes(i.field.field_type)&&i.field.options?.length){const options=i.field.options.map(o=>`<option value="${esc(o)}" ${o===current?'selected':''}>${esc(String(o).replace(/^\//,''))}</option>`).join('');return `<select class="value" aria-label="Value for ${label}" data-n="${n}"><option value="">Choose…</option>${options}</select>`}return `<input class="value" aria-label="Value for ${label}" data-n="${n}" value="${esc(current)}" placeholder="Leave blank">`}
function candidateControl(i,n){if(!i.candidates?.length||(i.status==='ready'&&i.candidates.length===1))return '';const options=i.candidates.map((c,x)=>`<option value="${x}" ${c.fact_id===i.fact_id?'selected':''}>${esc(c.value)} — ${esc(c.evidence.source)} (${esc(c.evidence.locator)})</option>`).join('');return `<label class="candidate-wrap"><span>Evidence candidates</span><select class="candidate" aria-label="Evidence candidate for ${esc(i.field.label)}" data-n="${n}"><option value="">Choose evidence…</option>${options}</select></label>`}
function syncReview(){document.querySelectorAll('.value').forEach(el=>{const i=plan.fields[+el.dataset.n],old=i.value||'';i.value=el.value.trim()||null;if(i.value!==old){i.evidence=null;i.fact_id=null;i.reason='Value explicitly confirmed in the local review UI';i.status=i.value?'review':'missing'}});document.querySelectorAll('.check').forEach(el=>plan.fields[+el.dataset.n].selected=el.checked)}
function renderSummary(){const counts={},selected=plan.fields.filter(i=>i.selected&&i.value).length;plan.fields.forEach(i=>counts[i.status]=(counts[i.status]||0)+1);$('#summary').innerHTML=`<div class="counter selected"><b>${selected}</b>selected</div>`+Object.entries(counts).map(([k,v])=>`<div class="counter"><b>${v}</b>${esc(k)}</div>`).join('')}
function render(){renderSummary();$('#rows').innerHTML=plan.fields.map((i,n)=>`<tr><td><input class="check" type="checkbox" aria-label="Use ${esc(i.field.label)}" data-n="${n}" ${i.selected?'checked':''} ${i.status==='skip'?'disabled':''}></td><td class="field"><strong>${esc(i.field.label)}</strong>${i.field.required?'<span class="required">required</span>':''}<small>${esc(i.field.name)} · ${esc(i.field.field_type)}${i.field.page?' · page '+esc(i.field.page):''}</small></td><td>${valueControl(i,n)}</td><td><span class="pill ${esc(i.status)}">${esc(i.status)}</span></td><td class="evidence">${i.evidence?`<strong>${esc(i.evidence.excerpt)}</strong><small>${esc(i.evidence.source)} · ${esc(i.evidence.locator)}</small>`:'<small>No source selected</small>'}${candidateControl(i,n)}</td><td class="reason">${esc(i.reason)}</td></tr>`).join('');document.querySelectorAll('.candidate').forEach(el=>el.onchange=()=>{if(el.value==='')return;syncReview();const i=plan.fields[+el.dataset.n],candidate=i.candidates[+el.value];i.value=candidate.value;i.fact_id=candidate.fact_id;i.evidence=candidate.evidence;i.confidence=candidate.confidence;i.reason='Evidence candidate explicitly selected in the local review UI';i.status='review';i.selected=true;render()});document.querySelectorAll('.check').forEach(el=>el.onchange=()=>{plan.fields[+el.dataset.n].selected=el.checked;renderSummary()});document.querySelectorAll('.value').forEach(el=>el.onchange=()=>{syncReview();renderSummary()})}
$('#backBtn').onclick=()=>{$('#reviewPanel').classList.add('hidden');$('#uploadPanel').classList.remove('hidden');stage(1)};
$('#applyBtn').onclick=async()=>{error('#reviewError','');syncReview();const selected=plan.fields.filter(i=>i.selected&&i.value);if(!selected.length){error('#reviewError','Select at least one non-empty value.');return}const data=new FormData();data.append('form',form.files[0]);data.append('plan_json',JSON.stringify(plan));data.append('flatten',$('#flatten').checked?'true':'false');busy($('#applyBtn'),true,'Creating files…');try{const res=await fetch('/api/apply',{method:'POST',body:data});if(!res.ok){let msg='Could not create the PDF';try{msg=(await res.json()).detail||msg}catch{}throw Error(msg)}const blob=await res.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='fillonce-results.zip';a.style.display='none';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);stage(3);$('#applyBtn').innerHTML='Downloaded ✓';$('#applyBtn').disabled=false}catch(e){error('#reviewError',e.message);busy($('#applyBtn'),false)}};
</script></body></html>"""
