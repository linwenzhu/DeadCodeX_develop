"""Inspect call edges, reachability, and findings through the Python API."""

from pathlib import Path

from deadcodex import DeadCodex

PROJECT = Path(__file__).resolve().parents[1] / "02_cross_file"
ENTRY_POINT = "app.main"

analyzer = DeadCodex()
analyzer.scavenge([PROJECT])
result = analyzer.analyze_reachability([ENTRY_POINT])

print("Resolved call edges:")
for edge in analyzer.call_graph.edges:
    print(f"  {edge.caller} -> {edge.callee}")

print("\nReachability explanations:")
print(" ", result.explain("shop.formatting.format_total"))
print(" ", result.explain("shop.legacy.checkout"))

print("\nProject-aware unused callables:")
for item in analyzer.get_unused_code_project([ENTRY_POINT]):
    if item.qualified_name is not None:
        print(f"  {item.qualified_name}")
