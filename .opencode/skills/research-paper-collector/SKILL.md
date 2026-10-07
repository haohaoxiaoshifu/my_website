---
name: research-paper-collector
description: 收集指定领域最近发布的 arXiv 论文，去重、验证并更新网站数据。
---

# Research Paper Collector

## 何时使用

当用户要求查找、更新或整理某个领域的最新论文时使用。

## 输入

- 研究主题；
- 最多返回数量，默认 10；
- 时间范围，默认最近 7 天。

## 工作流

1. 读取 `references/topics.md`，把用户主题映射为查询词；
2. 运行 `python scripts/collect_papers.py --query "查询词" --limit 10`；
3. 读取 `public/data/papers.json`；
4. 以 arXiv id 去重，不以翻译后的标题去重；
5. 检查每项是否具有 id、title、authors、published、summary、url；
6. 摘要只能依据论文原始摘要，不猜测实验结论；
7. 运行 `python scripts/check_papers.py`；
8. 运行 `python scripts/build.py` 重建页面；
9. 报告新增数、总数、查询词和失败项。

## 安全与质量规则

- 论文链接必须来自配置的数据源；
- 不能把预印本描述成已经同行评审；
- 没有新论文时不改写文件；
- 网络失败时保留原数据；
- 不因一篇论文的摘要而给出医疗、法律或投资结论。
