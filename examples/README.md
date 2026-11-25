# DeadCodex examples

这些示例从单文件扫描逐步扩展到项目级分析，所有命令都从仓库根目录运行。推荐使用 `uv run`，发现死代码时退出码为 3 是正常结果。

## 功能覆盖表

| 目录 | 主要演示内容 |
|---|---|
| `01_basic_scan` | 函数、异步函数、类、方法、属性、变量、导入、不可达代码和 `noqa` |
| `02_cross_file` | 包、相对导入、别名、重导出、同名函数、跨文件调用图和显式入口 |
| `03_flask_project` | Flask 路由隐式入口和框架误报降低 |
| `demo_project` | FastAPI 路由隐式入口、JSON/HTML 报告和 Baseline |
| `04_custom_decorator` | 自定义装饰器入口和多个入口组合 |
| `05_configured_project` | `pyproject.toml`、排除目录、忽略名称、忽略装饰器、置信度和按大小排序 |
| `06_api_usage` | Python API、调用边、可达路径解释和限定名结果 |

## 1 基础单文件扫描

```bash
uv run deadcodex examples/01_basic_scan
```

报告会包含未使用导入、异步函数、函数、类、方法、属性以及 `return` 后的不可达语句。带有 `# noqa: V107` 的变量不会出现。

还可以生成 whitelist 格式：

```bash
uv run deadcodex examples/01_basic_scan --make-whitelist
```

## 2 跨文件项目分析

```bash
uv run deadcodex examples/02_cross_file --entry-point app.main
```

`app.main` 通过 `from import as` 别名到达 `shop.service.checkout`，再通过相对模块导入和相对符号别名到达格式化与税费函数。`shop.legacy.checkout` 虽然与活动函数同名，仍会被正确识别为不可达。`shop.__init__` 也保留了包级重导出的建模样例。

## 3 Flask 和 FastAPI

静态分析不需要安装 Flask 或 FastAPI：

```bash
uv run deadcodex examples/03_flask_project --framework flask
uv run deadcodex examples/demo_project --framework fastapi
```

框架 Adapter 会把路由处理函数作为入口，并继续沿调用图保留其依赖，只报告真正不可达的旧函数。

## 4 自定义装饰器入口

```bash
uv run deadcodex examples/04_custom_decorator \
  --entry-point jobs.job \
  --entry-point-decorator job
```

这里同时使用显式入口和装饰器入口。`daily_cleanup` 及其调用的 `archive_records` 可达，只有 `old_cleanup` 被报告。

## 5 配置文件驱动

```bash
uv run deadcodex --config examples/05_configured_project/pyproject.toml
```

配置文件指定扫描路径与入口，并演示 `exclude`、`ignore_names`、`ignore_decorators`、`min_confidence` 和 `sort_by_size`。命令行仍可覆盖配置，例如：

```bash
uv run deadcodex --config examples/05_configured_project/pyproject.toml \
  --format json
```

## 6 报告与 Baseline

```bash
uv run deadcodex examples/demo_project --framework fastapi \
  --format json --output /tmp/deadcodex-report.json

uv run deadcodex examples/demo_project --framework fastapi \
  --format html --output /tmp/deadcodex-report.html

uv run deadcodex examples/demo_project --framework fastapi \
  --baseline /tmp/deadcodex-baseline.json --update-baseline

uv run deadcodex examples/demo_project --framework fastapi \
  --baseline /tmp/deadcodex-baseline.json
```

最后一条命令会隐藏 Baseline 中已经接受的问题并以状态码 0 结束。

## 7 Python API 与可解释路径

```bash
uv run python examples/06_api_usage/analyze_project.py
```

程序会打印解析后的跨文件调用边、从入口到目标的一条确定路径，以及项目级未使用限定名。
