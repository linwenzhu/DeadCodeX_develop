# 第五阶段解析修复

基于 PR #5 的提交 e63205f，本次修复四个已复现的错误：

1. 导入绑定增加可选 scope_name，由 Collector 记录导入所在作用域。
   Resolver 按词法作用域由内向外查找，参数、局部变量和闭包绑定
   遮蔽外层导入；方法不会捕获类命名空间中的裸名称。
2. 删除无导入时的项目全局同名匹配。其他模块存在同名符号不代表
   当前模块能使用它。真正重复的项目模块仍保留 ambiguous 状态。
3. 局部属性引用保留完整后缀，例如 Service.run 指向
   consumer.Service.run；无法确认局部对象属性时保持 unresolved。
4. 相对导入不允许移除全部包层级；合法的父包相对导入仍可解析。

新增 12 项回归用例，保留既有绝对导入、别名、外部依赖与核心
集成测试。原先“未导入的跨模块同名符号为 ambiguous”的测试
改为 unresolved，因为两者都不在当前可见作用域中。

这是保守静态解析，不包含动态类型推断、动态导入或完整控制流
敏感的绑定分析。scope_name 默认为 None，兼容已有手工构造
ImportBinding 的调用；缺省时按模块级导入处理。

验证命令：

```bash
uv run pytest
uv run ruff check deadcodex tests test_smoke.py
uv run ruff format --check deadcodex tests test_smoke.py
uv run tox -e cleanup,py,py39,py311
```
