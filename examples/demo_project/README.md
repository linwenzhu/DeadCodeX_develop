# FastAPI project analysis demo

This example demonstrates framework-aware reachability without importing or
running FastAPI. From the repository root, run:

```bash
python -m deadcodex examples/demo_project --framework fastapi
```

`read_user` is discovered through `@app.get`, and `serialize_user` is reachable
from that handler. The report contains only `old_format_user`.

Machine-readable reports and baselines can be demonstrated with:

```bash
python -m deadcodex examples/demo_project --framework fastapi --format json
python -m deadcodex examples/demo_project --framework fastapi \
  --baseline examples/demo_project/baseline.json --update-baseline
```
