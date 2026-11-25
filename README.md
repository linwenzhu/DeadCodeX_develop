# DeadCodeX

DeadCodeX is a cross-file and framework-aware dead code analyzer for Python
projects.

## Run a scan

```bash
uv sync --locked
uv run deadcodex path/to/project
uv run deadcodex examples/demo_project --framework fastapi --format json
uv run deadcodex examples/demo_project --framework fastapi --format html --output report.html
```

Use `--entry-point package.module.function` or a framework adapter to analyze
which callables are reachable. Paths and options can also be configured in
`[tool.deadcodex]` in `pyproject.toml` or an explicit `--config` file.

Save the current findings to a baseline, then use it to report new findings:

```bash
uv run deadcodex path/to/project --baseline baseline.json --update-baseline
uv run deadcodex path/to/project --baseline baseline.json
```

Exit codes are `0` for no reportable findings or a successful baseline update,
`1` for invalid input, `2` for invalid arguments or configuration, and `3`
when findings are reported. See the [examples](examples/README.md) for more.

## Architecture

```text
Source Paths
    -> ProjectLoader
    -> PythonParser
    -> ScopeCollector and AstCollector
    -> ImportResolver and ReferenceResolver
    -> CallGraphBuilder and ReachabilityAnalyzer
    -> Framework Adapters
    -> Reporters and Baseline
```

## Package layout

```text
deadcodex/
    model.py
    parser.py
    collector.py
    scope.py
    project.py
    analysis.py
    resolver.py
    callgraph.py
    adapters.py
    pipeline.py
    config.py
    reporters.py
    baseline.py
    core.py
```

