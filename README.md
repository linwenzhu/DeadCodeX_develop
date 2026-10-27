# DeadCodeX

DeadCodeX is a cross-file and framework-aware dead code analyzer for Python
projects.

This initial commit establishes the project architecture and public module
boundaries. Analysis algorithms, framework rules, reports, tests, examples,
and CI configuration will be implemented in later development commits.

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

