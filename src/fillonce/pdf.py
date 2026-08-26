from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

from fillonce.integrity import sha256_file
from fillonce.models import FieldInfo, FillPlan


class FormError(ValueError):
    pass


FIELD_TYPES = {
    "/Tx": "text",
    "/Btn": "checkbox",
    "/Ch": "choice",
    "/Sig": "signature",
}


@dataclass(slots=True)
class _WidgetInfo:
    name: str
    page: int
    widget: Any
    parent: Any | None


def _pdf_value(value: Any) -> Any:
    try:
        return value.get_object()
    except AttributeError:
        return value


def _qualified_field_name(widget: Any) -> tuple[str, Any | None]:
    parts: list[str] = []
    current = widget
    immediate_parent = None
    seen: set[tuple[int | None, int | None] | int] = set()
    while current is not None:
        reference = getattr(current, "indirect_reference", None)
        identity: tuple[int | None, int | None] | int
        if reference is not None:
            identity = (getattr(reference, "idnum", None), getattr(reference, "generation", None))
        else:
            identity = id(current)
        if identity in seen:
            break
        seen.add(identity)
        partial = current.get("/T")
        if partial:
            parts.append(str(partial))
        parent_reference = current.get("/Parent")
        if not parent_reference:
            break
        parent = _pdf_value(parent_reference)
        if immediate_parent is None:
            immediate_parent = parent
        current = parent
    return ".".join(reversed(parts)), immediate_parent


def _widgets(document: Any) -> list[_WidgetInfo]:
    result: list[_WidgetInfo] = []
    for page_number, page in enumerate(document.pages, start=1):
        for annotation_ref in page.get("/Annots", []):
            annotation = _pdf_value(annotation_ref)
            if annotation.get("/Subtype") != "/Widget":
                continue
            name, parent = _qualified_field_name(annotation)
            if name:
                result.append(_WidgetInfo(name=name, page=page_number, widget=annotation, parent=parent))
    return result


def _page_field_names(document: Any) -> dict[str, int]:
    pages: dict[str, int] = {}
    for widget in _widgets(document):
        pages.setdefault(widget.name, widget.page)
    return pages


def _checkbox_states(document: Any) -> dict[str, list[str]]:
    states: dict[str, set[str]] = {}
    for info in _widgets(document):
        appearance = _pdf_value(info.widget.get("/AP") or {})
        normal = _pdf_value(appearance.get("/N") or {})
        if not isinstance(normal, dict):
            continue
        on_states = {str(key) for key in normal if str(key) != "/Off"}
        if on_states:
            states.setdefault(info.name, set()).update(on_states)
    return {name: sorted(values) for name, values in states.items()}


def _recover_orphaned_fields(reader: PdfReader, raw_fields: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    widget_names = {widget.name for widget in _widgets(reader)}
    if not widget_names.difference(raw_fields):
        return reader, raw_fields
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.reattach_fields()
    return writer, writer.get_fields() or {}


def inspect_pdf(path: str | Path) -> list[FieldInfo]:
    form_path = Path(path).expanduser().resolve()
    if not form_path.exists():
        raise FormError(f"Form does not exist: {form_path}")
    try:
        reader = PdfReader(form_path)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise FormError("The PDF is password protected")
        raw_fields = reader.get_fields() or {}
        document, raw_fields = _recover_orphaned_fields(reader, raw_fields)
    except FormError:
        raise
    except Exception as exc:
        raise FormError(f"Could not read PDF form: {exc}") from exc
    if not raw_fields:
        raise FormError(
            "No native AcroForm fields were found. Scanned and flat PDFs are not supported yet."
        )
    page_names = _page_field_names(document)
    checkbox_states = _checkbox_states(document)
    result: list[FieldInfo] = []
    for name, raw in raw_fields.items():
        data = _pdf_value(raw)
        flags = int(data.get("/Ff", 0) or 0)
        raw_type = str(data.get("/FT", ""))
        if raw_type == "/Btn" and flags & 65536:
            field_type = "button"
        elif raw_type == "/Btn" and flags & 32768:
            field_type = "radio"
        else:
            field_type = FIELD_TYPES.get(raw_type, "unknown")
        label = str(data.get("/TU") or data.get("/TM") or name)
        required = bool(flags & 2)
        raw_options = data.get("/Opt") or []
        options: list[str] = []
        for option in raw_options:
            value = _pdf_value(option)
            if isinstance(value, list):
                options.append(str(value[-1]))
            else:
                options.append(str(value))
        if field_type in {"checkbox", "radio"}:
            options = checkbox_states.get(name, ["/Yes"])
        result.append(
            FieldInfo(
                name=name,
                label=label,
                field_type=field_type,
                page=page_names.get(name),
                required=required,
                options=options,
            )
        )
    return result


def _checkbox_value(value: str, states: list[str]) -> str:
    normalized = value.strip().casefold()
    if normalized in {"true", "yes", "y", "1", "on", "checked"}:
        return states[0] if states else "/Yes"
    if normalized in {"false", "no", "n", "0", "off", "unchecked"}:
        return "/Off"
    raise FormError(f"Checkbox value must be yes/no, not {value!r}")


def _has_normal_appearance(widget: Any) -> bool:
    appearance = _pdf_value(widget.get("/AP") or {})
    normal = _pdf_value(appearance.get("/N"))
    if normal is None:
        return False
    if hasattr(normal, "get_data"):
        return bool(normal.get_data())
    if isinstance(normal, dict):
        return bool(normal)
    return True


def _verify_editable_pdf(
    path: Path, expected: dict[str, Any], field_types: dict[str, str]
) -> None:
    reader = PdfReader(path)
    fields = reader.get_fields() or {}
    missing = set(expected).difference(fields)
    if missing:
        raise FormError(f"Written PDF is missing fields: {', '.join(sorted(missing))}")
    for name, expected_value in expected.items():
        actual = fields[name].get("/V")
        if str(actual or "") != str(expected_value):
            raise FormError(
                f"Written value for {name!r} is {str(actual or '')!r}, expected {expected_value!r}"
            )

    widgets_by_name: dict[str, list[_WidgetInfo]] = {}
    for widget in _widgets(reader):
        widgets_by_name.setdefault(widget.name, []).append(widget)
    for name, expected_value in expected.items():
        matching = widgets_by_name.get(name, [])
        if not matching:
            raise FormError(f"Written PDF has no page widget for field {name!r}")
        if field_types.get(name) == "radio":
            selected = [
                info for info in matching if str(info.widget.get("/AS") or "") == str(expected_value)
            ]
            if not selected:
                raise FormError(f"Radio field {name!r} has no selected widget appearance")
            if any(
                str(info.widget.get("/AS") or "/Off") not in {str(expected_value), "/Off"}
                for info in matching
            ):
                raise FormError(f"Radio field {name!r} has an inconsistent widget state")
            if any(not _has_normal_appearance(info.widget) for info in matching):
                raise FormError(f"Widget for {name!r} has no usable normal appearance")
            continue
        for info in matching:
            effective_value = info.widget.get("/V")
            if effective_value is None and info.parent is not None:
                effective_value = info.parent.get("/V")
            if str(effective_value or "") != str(expected_value):
                raise FormError(f"Widget value for {name!r} does not match the field tree")
            if not _has_normal_appearance(info.widget):
                raise FormError(f"Widget for {name!r} has no usable normal appearance")


def _verify_flattened_pdf(path: Path) -> None:
    reader = PdfReader(path)
    if reader.trailer["/Root"].get("/AcroForm") is not None:
        raise FormError("Flattened PDF still contains an AcroForm field tree")
    if _widgets(reader):
        raise FormError("Flattened PDF still contains interactive widgets")


def apply_pdf_plan(
    plan: FillPlan,
    output_path: str | Path,
    form_path: str | Path | None = None,
    *,
    flatten: bool = False,
) -> Path:
    source = Path(form_path or plan.form_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()
    if not source.exists():
        raise FormError(
            f"Original form not found at {source}. Move it back or pass a plan with an updated form_path."
        )
    if source == destination:
        raise FormError("Output path must differ from the original form so the source is preserved")
    if plan.form_sha256 and sha256_file(source) != plan.form_sha256:
        raise FormError(
            "The original form changed after this plan was created. Build a new plan before applying it."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    values: dict[str, str] = {}
    for item in plan.fields:
        if not item.selected or item.value is None or item.status in {"missing", "conflict", "skip"}:
            continue
        if item.field.field_type in {"signature", "button", "unknown"}:
            continue
        if item.field.field_type == "checkbox":
            value = _checkbox_value(item.value, item.field.options)
        elif item.field.field_type in {"choice", "radio"} and item.field.options:
            option_map = {
                option.strip().removeprefix("/").casefold(): option for option in item.field.options
            }
            option_key = item.value.strip().removeprefix("/").casefold()
            if option_key not in option_map:
                raise FormError(
                    f"Choice value for {item.field.label!r} must be one of {item.field.options}"
                )
            value = option_map[option_key]
        else:
            value = item.value
        values[item.field.name] = value
    try:
        reader = PdfReader(source)
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        fields = writer.get_fields() or {}
        widget_names = {widget.name for widget in _widgets(writer)}
        if widget_names.difference(fields) or set(values).difference(fields):
            writer.reattach_fields()
            fields = writer.get_fields() or {}
        missing = set(values).difference(fields)
        if missing:
            raise FormError(f"Form fields not found: {', '.join(sorted(missing))}")

        if flatten and any(
            str(field.get("/FT")) == "/Sig" and field.get("/V") for field in fields.values()
        ):
            raise FormError("Refusing to flatten a PDF that contains a signature value")

        values_to_write: dict[str, Any] = values
        if flatten:
            values_to_write = {
                name: field.get("/V", "/Off" if str(field.get("/FT")) == "/Btn" else "")
                for name, field in fields.items()
            }
            values_to_write.update(values)
        for page in writer.pages:
            writer.update_page_form_field_values(
                page,
                values_to_write,
                auto_regenerate=False,
                flatten=flatten,
            )
        if flatten:
            writer.remove_annotations(subtypes="/Widget")
            writer.root_object.pop(NameObject("/AcroForm"), None)
        elif "/AcroForm" in writer.root_object:
            acroform = _pdf_value(writer.root_object["/AcroForm"])
            acroform[NameObject("/NeedAppearances")] = BooleanObject(False)

        temporary: Path | None = None
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.stem}-",
            suffix=".pdf",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            writer.write(handle)
        try:
            if flatten:
                _verify_flattened_pdf(temporary)
            else:
                _verify_editable_pdf(
                    temporary,
                    values,
                    {item.field.name: item.field.field_type for item in plan.fields},
                )
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except FormError:
        raise
    except Exception as exc:
        raise FormError(f"Could not write filled PDF: {exc}") from exc
    return destination
