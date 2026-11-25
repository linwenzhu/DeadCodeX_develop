from deadcodex import ProjectAnalyzer, core


class _Pass:
    def __init__(self, events, name, result=None):
        self.events = events
        self.name = name
        self.result = result

    def resolve(self, project, defined_items):
        self.events.append((self.name, project, defined_items))

    def build(self, project, defined_items):
        self.events.append((self.name, project, defined_items))
        return self.result


def test_project_analyzer_runs_passes_in_dependency_order():
    events = []
    graph = object()
    import_resolver = _Pass(events, "imports")
    reference_resolver = _Pass(events, "references")
    call_graph_builder = _Pass(events, "calls", result=graph)
    assert call_graph_builder.build
    analyzer = ProjectAnalyzer(
        import_resolver, reference_resolver, call_graph_builder
    )
    project = object()
    items = object()

    result = analyzer.analyze(project, items)

    assert result is graph
    assert events == [
        ("imports", project, items),
        ("references", project, items),
        ("calls", project, items),
    ]


def test_deadcodex_uses_the_shared_project_analyzer():
    analyzer = core.DeadCodex()

    assert (
        analyzer.project_analyzer.import_resolver is analyzer.import_resolver
    )
    assert (
        analyzer.project_analyzer.reference_resolver
        is analyzer.reference_resolver
    )
    assert (
        analyzer.project_analyzer.call_graph_builder
        is analyzer.call_graph_builder
    )
