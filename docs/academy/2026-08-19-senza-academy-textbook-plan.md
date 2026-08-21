# Senza Academy 教材正文计划

> 状态：v1 正文已完成
> 日期：2026-08-19
> 正文入口：[`textbook/README.md`](textbook/README.md)

## 1. 目标

在已经完成的十课课程骨架、实验与学习版 PPT 之上，编写一套可以脱离演讲独立阅读的中文教材。
教材以《动手学 AI Agent》的理论问题为坐标，以 Runtime/Senza 的真实组件、源码和实验替换泛化
Agent 示例。

教材不重复实验 README。每章需要完成从设计动机到工程证据的闭环：

```text
理论问题 → 架构选择 → Runtime/Senza 映射 → 执行故事
        → 源码导读 → 配套实验 → 能力边界 → 复习题
```

## 2. 交付范围

- 序言、学习方式与四层架构地图；
- 10 章正文，对应 Academy 01–10；
- 统一术语表；
- 每章到本地理论章节、源码、实验与 live example 的可解析链接；
- 可自动检查的教材清单与最低内容契约。

Word/PDF 属于正文定稿后的派生产物。本阶段以 Markdown 作为唯一内容源，避免多格式并行编辑造成
事实和版本漂移。

## 3. 章节完成定义

每章必须：

1. 明确本章问题、学习目标和先修知识；
2. 用自己的语言解释理论，不大段复制参考书；
3. 准确区分 Agent Core、Hook、Plugin、Tool、Store 与外部基础设施；
4. 至少给出一条端到端执行故事和一组源码入口；
5. 指向对应 Academy 实验，并说明 recorded/live 各自证明什么；
6. 包含常见误解、当前能力边界、小结与复习题；
7. 遵守 `stable`、`teaching`、`preview` 的证据等级。

## 4. 编写顺序

- [x] 建立目录、序言、术语表与编写约定；
- [x] 第 1–3 章：ReAct、Hook、Plugin；
- [x] 第 4–6 章：Context、Coding、Workflow；
- [x] 第 7–10 章：Knowledge/Memory/Recall、Spawn、Eval、Improvement；
- [x] 全书事实复核、相对链接检查和内容契约测试；
- [x] 更新 Academy 总入口与最终验证记录。

## 5. 非目标

- 不把 recorded trace 改写成虚构的 live 执行；
- 不把教学 runner 宣传为 Runtime 内建产品；
- 不为了教材叙事补造尚不存在的持久 Memory、Recall Python 链路或专业子 Agent；
- 不在 Markdown 定稿前维护第二份 Word/PDF 正文。

## 6. 实际验证记录

- 教材包含序言、10 章正文、术语表和源码地图；序言与正文合计 2,968 行；
- `course_manifest.json` 将每个 Lab 映射到唯一教材章节，自动检查章节篇幅、成熟度、实验链接、
  能力边界、复习题、代码围栏和行尾空白；
- `python -m pytest academy/tests academy/labs -q`：通过；具体用例数以当前分支 CI 为准；
- Academy 范围内的仓库内链接全部解析且不会逃出 Senza 根目录；跨仓库源码与理论引用均使用
  固定 commit 的 GitHub URL，不依赖本机兄弟目录；
- Academy 的 38 个 Python 文件按 Python 3.9 grammar 解析通过，`compileall` 通过；
- 独立事实审查发现并修正 5 项重要问题：Safety 路径能力、snapshot 外部并发边界、HITL channel
  进程边界、跨 case Pass@k/Pass^k 聚合、proposal artifact 与门禁未绑定；
- Lab 09 现按 `(variant, case_id)` 估计可靠性后做宏平均；Lab 10 的 replay 现实际消费结构化
  artifact，并用 digest、diff 一致性和精确 target allowlist 约束教学 proposal；
- `git diff --check` 通过，仅有工作区的 LF/CRLF 转换提示。
