# Privacy model

FillOnce is designed so a useful default workflow does not need an account, a hosted database, telemetry, or a model provider.

## CLI and Python API

Files are read from paths you provide. Generated PDFs, plans, and audits are written only to paths you choose. The deterministic pipeline makes no network requests.

## Local review UI

The server binds to `127.0.0.1` by default. Each request is processed in a newly created temporary directory. Uploaded bytes and intermediate files are removed before the request completes; the result is returned directly to the browser. FillOnce has no session database.

Browser, operating-system, proxy, antivirus, backup, or filesystem behavior is outside FillOnce's control. Avoid binding to a public interface unless you have added appropriate authentication and transport security.

## Optional Agent matching

Agent matching is disabled by default. When explicitly configured, FillOnce sends field labels, extracted fact values, and evidence to the selected OpenAI-compatible endpoint. Consult that provider's policies before using personal documents. The endpoint can only nominate an existing fact ID; its suggestions still require human review.

## Audit files

Audits intentionally contain proposed values and evidence excerpts. Treat them as sensitive documents. They are portable so you can store or delete them according to your own retention policy.
