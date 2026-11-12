# 第三阶段：D 成员第一次提交

## 范围与现状

本阶段负责函数内部的控制流与不可达语句检测。实现来源是
`linwenzhu/DeadcodeX` 的 `3eb1dd3`。

为修复 Collector 的前置依赖，`reachability.py` 和 63 项原版控制流
回归测试已经随第二阶段 PR #3 合入 main（`9c22514`）。
本分支基于该版本整理交付，并补充独立接口测试与演示，不重复宣称
已有代码是本阶段新实现的功能。

## D 需要理解和负责的文件

| 文件 | 职责 |
| --- | --- |
| deadcodex/reachability.py | 终止语句标记、分支汇合、循环与异常分支分析 |
| tests/test_reachability.py | 已有 63 项控制流回归测试 |
| tests/test_stage_d.py | 独立回调契约、状态重置、误报边界与集成测试 |
| examples/stage_d/run_demo.py | 七个可以直接运行的 API 演示 |

协作接口还需阅读 Collector 的 `visit()`、`collect()` 和 `_define()`，
以及 AnalysisResult 的 `get_unused_code()`。这些接口已接通，
本阶段无需修改 core.py。

## 验收清单

- return、raise、break、continue 后的语句区域和行号正确。
- if/else 全部终止与仍可继续执行的分支能够区分。
- 常量条件、while、嵌套循环、with 和 try/except/else 回归通过。
- Visitor 先访问子节点，再调用 Reachability.visit()。
- 报告通过注入的回调返回；Collector 转换为 100% 置信度的 Item。
- reset() 清理单个模块的状态；动态条件保守处理。
- 基础模块与现有 Parser、Collector 的测试全部通过。

该实现不是完整 Python 控制流图，无法证明任意动态条件、异常或
finally 组合的可达性；新增语法（例如 match、except*）不能据此
宣称全面支持。项目级 CallGraph、入口可达性和路径解释属于
D 第二次提交，等待 Resolver 完成后再接入。

## 本地验证

```bash
uv sync --locked --all-groups
uv run pytest
uv run ruff check deadcodex tests test_smoke.py examples/stage_d
uv run ruff format --check deadcodex tests test_smoke.py examples/stage_d
uv run tox
uv run tox -e py39,py311
uv run python examples/stage_d/run_demo.py
```

目前命令行入口尚待 E 阶段完成，因此演示使用 Python API。
本分支提交后先查看 CI，本次任务不合并 main。

## 本次本地测试结果

- Python 3.9.6、3.11.16、3.12.14：各 116 项测试通过。
- 新增 11 项 D 阶段测试；此前 105 项测试保持通过。
- tox cleanup、py、py39、py311 环境全部通过，测试前构建并安装 wheel。
- Ruff 检查与格式检查通过，覆盖代码、测试和本阶段示例共 45 个文件。
- 七个演示场景通过；reachability.py 的语句覆盖率保持 100%。
- Python 3.13、3.14 由提交后的远程 CI 检查。
