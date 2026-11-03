# Development environment

Run these commands from the repository root:

```bash
uv sync --locked --all-groups --python 3.12
uv run pytest
uv run ruff check deadcodex tests test_smoke.py
uv run ruff format --check deadcodex tests test_smoke.py
uv run tox
```

The development dependency group includes pytest, pytest-cov, coverage, Ruff,
tox, Pint and ty. When changing dependencies, update and commit both
`pyproject.toml` and `uv.lock`.

GitHub Actions reads `.github/workflows/ci.yml`. It checks Python 3.9, 3.11,
3.13 and 3.14 using the locked uv environment. tox additionally builds and
installs a wheel in a separate environment using the dependencies in `tox.ini`.

This stage contains the project skeleton and import/version smoke tests.
Analysis and CLI implementations are scheduled for subsequent stages.
