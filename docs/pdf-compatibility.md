# PDF compatibility

FillOnce works with native AcroForm fields. A PDF can look like a form while containing only lines and text; those flat or scanned files do not expose fields to FillOnce yet.

## Quick diagnosis

```bash
fillonce inspect blank.pdf -o fields.json
```

If fields are listed, the form is a native AcroForm. If FillOnce reports that no fields were found, try opening the PDF in a desktop editor and checking whether the apparent inputs are actually selectable form controls. XFA-only forms, scanned forms, and password-protected forms are outside v0.1 support.

## What FillOnce validates

An interactive PDF stores form state in more than one place. FillOnce checks all of the following before delivering a file:

- every requested field still exists in the canonical field tree;
- the canonical value equals the requested value;
- every matching page widget inherits or stores the same value;
- a selected radio group has a widget using the requested appearance state;
- every updated widget has a usable normal appearance;
- a flattened output contains no widgets or AcroForm tree.

The output is first written to a temporary sibling file. It replaces the requested destination only after these checks pass. The original form cannot be used as the output path.

## Checkboxes, choices, and radio groups

Checkbox export values are not standardized. A checked box might use `/Yes`, `/On`, `/1`, or a producer-specific name. FillOnce reads the actual on-state from the widget appearance dictionary and writes that value. Ambiguous human-entered checkbox values are rejected instead of being interpreted as false.

Choice and radio values must equal one of the field's declared export options. FillOnce displays readable option names, preserves the underlying PDF export state, and verifies the selected radio appearance after writing. Push buttons remain deliberately untouched.

## Editable versus static

Editable output preserves widgets and is the default. Use a static copy when a receiving portal or viewer does not display field appearances reliably:

```bash
fillonce apply fill-plan.json -o completed-static.pdf --flatten
```

Flattening removes interactive controls from the output copy. FillOnce refuses to flatten a PDF with an existing signature value. Always keep the original form and review the rendered result in the viewer required by the form issuer.

## Reporting an interoperability bug

Create a synthetic file that reproduces the same field structure without personal data. Include the PDF producer, FillOnce version, operating system, and viewers where the behavior differs. Never upload a real form that contains or once contained private information.
