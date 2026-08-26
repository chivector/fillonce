# Security policy

## Supported versions

Until FillOnce reaches 1.0, security fixes are applied to the latest release and the `main` branch.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose document contents, cause unreviewed values to be filled, escape the request-scoped temporary directory, or execute code from an uploaded file. Use GitHub's private vulnerability reporting feature for this repository.

Include the affected version, a minimal reproduction using synthetic data, the expected security boundary, and the observed behavior. You should receive an acknowledgement within seven days.

## Scope and boundaries

- Core extraction and matching make no network calls.
- Agent matching is an explicit opt-in and sends field labels, extracted values, and evidence to the configured endpoint.
- The web UI binds to loopback by default. A non-loopback bind exposes it to the network.
- FillOnce parses complex third-party formats. Only process files you trust, keep dependencies current, and use OS-level isolation for hostile files.
- FillOnce does not sign or submit forms.
