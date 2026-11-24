在 README.md 的 Usage 章节（"$ deadcodex myscript.py  # or" 那段命令行示例之后）
补充以下两段（如果已经存在相同内容，说明前序成员已加过，核对即可，不要重复添加）：

--------------------------------------------------------------------
Reports can be printed as JSON or written as a standalone HTML file:

    $ deadcodex mypackage/ --format json
    $ deadcodex mypackage/ --format html --output deadcodex-report.html

To accept all current findings and report only new ones in later runs:

    $ deadcodex mypackage/ --baseline deadcodex-baseline.json --update-baseline
    $ deadcodex mypackage/ --baseline deadcodex-baseline.json
--------------------------------------------------------------------

CHANGELOG（可选）：如果课程要求记录本组变更，在 CHANGELOG.md 最顶部加一条：

# 1.0 (2026-XX-XX)

* 交付 Console/JSON/HTML 报告、版本化 Baseline、wheel 安装测试与 CI 验收。
