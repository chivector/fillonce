# Changelog

All notable changes are documented here. FillOnce follows semantic versioning once the first public release is tagged.

## 0.1.0 - 2026-08-26

### Added

- Native AcroForm inspection and evidence-bound filling.
- JSON, YAML, CSV, text, Markdown, DOCX, and PDF fact extraction.
- Conservative multilingual aliases, conflict detection, and human-review states.
- Editable output plus explicit static flattening.
- JSON and standalone HTML audits with source and output hashes.
- Stateless local review UI and synthetic one-command demo.
- Optional OpenAI-compatible matching restricted to existing fact IDs.
- Orphaned-widget recovery, real checkbox export-state detection, and post-write verification.
- Radio-button filling with export-state and selected-appearance verification.
- Evidence-candidate selection, required-field cues, and local PDF preview in the review UI.
- SHA-256 binding between each review plan and its original PDF.
- Locked, vulnerability-audited development dependencies and a dedicated CI security job.

### Safety boundaries

- No automatic submission, signatures, telemetry, or core network calls.
- Missing, conflicting, fuzzy, button, and signature fields are not auto-filled. Radio fields are filled only from an exact declared option.
- Original forms cannot be overwritten in place.
