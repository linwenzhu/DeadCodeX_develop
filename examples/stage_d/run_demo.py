"""Run stage-D control-flow examples through the Python API."""

from deadcodex import DeadCodex

CASES = [
    ("return", "def f():\n    return\n    value = 1\n", 1),
    ("raise", "raise RuntimeError()\nvalue = 1\n", 1),
    ("break", "while flag:\n    break\n    value = 1\n", 1),
    ("continue", "while flag:\n    continue\n    value = 1\n", 1),
    ("constant_false", "if False:\n    value = 1\n", 1),
    (
        "all_branches_exit",
        "def f(flag):\n    if flag:\n        return\n"
        "    else:\n        raise RuntimeError()\n    value = 1\n",
        1,
    ),
    (
        "possible_fallthrough",
        "def f(flag):\n    if flag:\n        return\n    value = 1\n",
        0,
    ),
]


def main():
    for name, source, expected in CASES:
        analyzer = DeadCodex()
        analyzer.scan(source, filename=f"{name}.py")
        findings = [
            item
            for item in analyzer.get_unused_code(min_confidence=100)
            if item.typ == "unreachable_code"
        ]
        if len(findings) != expected:
            raise AssertionError(
                f"{name}: expected {expected} regions, got {len(findings)}"
            )
        print(f"[{name}] {len(findings)} unreachable regions")
        for item in findings:
            print(item.get_report(add_size=True))
    print(f"{len(CASES)} scenarios passed")


if __name__ == "__main__":
    main()
