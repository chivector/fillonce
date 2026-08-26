# Architecture

FillOnce separates observation, decision, and action. That separation is the main safety feature, not an implementation detail.

```text
PDF form ──> field inspection ──────────────┐
                                             ├─> match ─> FillPlan ─> PDF writer
source files ─> facts + evidence ───────────┘                  └────> audits
```

## Core objects

- `FieldInfo` describes an existing native PDF field. Inspection does not read source documents.
- `Fact` is a value extracted from a supplied source plus its file, locator, and excerpt.
- `PlanItem` records a proposed field-to-fact link, confidence, status, evidence, and whether it is selected.
- `FillPlan` is the review boundary. It is ordinary JSON, so a person or another tool can inspect and edit it before anything touches the PDF. Version 2 plans carry the original form's SHA-256 digest; applying a plan to different bytes is rejected.

## Matching policy

The deterministic matcher canonicalizes only known semantic equivalents. An exact, conflict-free canonical match is `ready`. Similar labels are `review`; no match is `missing`; multiple normalized values for the same canonical fact are `conflict`. Only selected values are applied, and by default only `ready` items are selected.

Optional Agent matching is deliberately weaker than deterministic matching. It can return only a supplied `fact_id`, never free-form text. Agent-linked items remain `review` and unselected.

## PDF behavior

FillOnce reads and updates AcroForm widgets with pypdf. It clones the original document and never writes in place. Before writing, the source bytes must match the plan fingerprint. Genuinely orphaned page widgets are reattached only when their names are absent from the canonical field tree. Selected fields are updated in a temporary PDF, then the file is reopened and checked against both the canonical `/AcroForm/Fields` tree and every matching page `/Widget`. Values and normal appearance streams must agree before the temporary file replaces the requested output. Radio groups additionally require a widget whose selected appearance matches the field's declared export state.

Editable output is the default. An explicit `flatten=True` or `--flatten` paints appearances and removes widgets plus the AcroForm tree from the output copy. FillOnce refuses to flatten a PDF with an existing signature value. It never signs or submits a form.

PDF implementations vary. End-to-end tests cover editable values, appearance streams, nonstandard checkbox export states, orphaned widgets, and flattened output. New viewer- or producer-specific behavior should be captured with a synthetic regression fixture before expanding claims.

## Web privacy boundary

The FastAPI UI has no database or server-side session. The browser previews the blank form from a local object URL. Planning and applying are separate requests; the browser re-uploads the original blank form for the apply request, and the server verifies it against the plan fingerprint. Each handler uses a request-scoped temporary directory, loads the result into the response, and removes the directory before returning.
