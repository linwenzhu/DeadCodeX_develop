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

## Stage one source

The development environment is ported from `linwenzhu/DeadcodeX` at commit
`92eb8edac284a3e10e9dfd9329ef4b41a6857780`.
`pyproject.toml`, `tox.ini` and `uv.lock` are copied verbatim.
The workflow uses the same jobs and commands, with `test_smoke.py` also
included in Ruff checks because this repository currently keeps its smoke tests
at the root. Later-stage analyzer implementations and their feature tests
remain outside this stage.
