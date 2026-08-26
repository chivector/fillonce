# Contributing to FillOnce

Thanks for helping make paperwork less repetitive and more trustworthy.

## Good first contributions

- Add a high-precision alias in `src/fillonce/normalization.py` with tests.
- Improve extraction for a supported document type.
- Create a synthetic PDF form that covers a field behavior we do not test.
- Improve keyboard navigation, small-screen layout, or screen-reader labels.
- Document a reproducible PDF interoperability issue.

Do not contribute real forms that once contained personal information. PDF editors often leave removed text, images, metadata, and revisions in the file. Recreate the relevant structure with fictional values instead.

## Development

```bash
git clone https://github.com/chivector/fillonce.git
cd fillonce
uv sync --all-extras --locked
uv run pytest
uv run ruff check .
```

Plain Python also works:

```bash
python -m venv .venv
# activate the environment for your shell
python -m pip install -e ".[dev]"
pytest
ruff check .
```

Run `uv run fillonce demo` after any change to PDF inspection, matching, writing, or auditing. A core change should include a focused unit test and, when it affects the deliverable, an end-to-end assertion.

## Pull requests

Keep each change small enough to review. Explain the user problem, the trust or privacy impact, and how you verified the behavior. New automatic matches must be semantic equivalents—not merely labels that are often associated.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
