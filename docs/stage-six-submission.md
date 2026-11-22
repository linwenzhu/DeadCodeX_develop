# 第六阶段：D 第二次提交

## 基线与来源

基于 DeadCodeX_develop/main 的 e536f0d（已包含第五阶段解析修复）。
CallGraphBuilder、ReachabilityAnalyzer、CallEdge、CallGraph、
ReachabilityResult 及基础回归用例移植自完整版 DeadcodeX 的 3eb1dd3。
保留当前已修复的 Resolver，不覆盖第五阶段改动。

## 提交内容

| 文件 | 内容 |
| --- | --- |
| deadcodex/model.py | 调用边、调用图、可达性结果与路径解释的数据模型 |
| deadcodex/callgraph.py | 从解析结果建立调用边，按显式入口执行确定性 BFS |
| deadcodex/core.py | resolve_references 返回图，增加 analyze_reachability 和 get_unused_code_project |
| tests/test_callgraph.py | 本地函数、跨文件、静态方法、外部和动态调用 |
| tests/test_project_reachability.py | 入口、递归、同名函数、不可达函数与错误输入 |
| tests/test_stage_six.py | 重建幂等性、遮蔽、保守保护闭包、路径确定性及独立模块调用 |
| examples/stage_six/run_demo.py | 可运行的调用链和项目级报告示例 |

新增 API 示例：

```python
from deadcodex import DeadCodex

analyzer = DeadCodex()
analyzer.scavenge(["myproject"])
graph = analyzer.resolve_references()
result = analyzer.analyze_reachability(["myproject.main"])
print(result.explain("myproject.helpers.work"))
unused = analyzer.get_unused_code_project(["myproject.main"])
```

入口必须是已扫描项目中的限定模块名或可调用对象名。
analyze_reachability 返回无法解析及有歧义的入口信息；
get_unused_code_project 对无效入口抛出 ValueError，避免产生误导报告。
重复构建图会重新解析，不积累重复调用边。

## 与完整版的阶段性适配

- scavenge 保持现有扫描行为；调用图通过 resolve_references 或项目 API 构建。
- 对 self/动态实例类型不作猜测，保留 unresolved，不伪造确定的调用边。
- 返回的可达性集合表示“已解析图上的可达性”，不是运行时执行证明。
- 项目报告保守保护未解析/有歧义调用的同名候选函数，并保护其已知下游。
  这是对完整版同名保护策略的加强，避免只保护入口却误报其 helper。
- 非可调用项仍使用已有名称级分析；限定名分析和 Pipeline 留给第七阶段。
- 不接入框架入口提供器、报告格式或 CLI；使用 Python API 演示。
- 不建模所有动态反射、回调传递、隐式导入副作用、实例分派和类构造调用。
  不可达结果只供人工核查，不代表代码可安全自动删除。

## 验证

```bash
uv sync --locked --all-groups
uv run pytest
uv run ruff check deadcodex tests test_smoke.py examples/stage_six
uv run ruff format --check deadcodex tests test_smoke.py examples/stage_six
uv run tox -e cleanup,py,py39,py311
uv run python examples/stage_six/run_demo.py
```

Python 3.9.6、3.11.16、3.12.14 各 155 项测试通过；
tox cleanup、py、py39、py311 全部通过，隔离 wheel 项目分析验证通过。
Ruff lint/format 与示例通过；callgraph.py 语句覆盖率 100%，
全仓库语句覆盖率 80%。远程 CI 另检查 Python 3.13 和 3.14。
