# 教材编写约定

本文件用于维护教材的一致性，不是 Runtime API 规范。

## 每章固定结构

1. 本章回答的问题；
2. 学习目标与先修知识；
3. 理论直觉；
4. Runtime/Senza 架构映射；
5. 一条完整执行故事；
6. 源码导读；
7. 配套实验；
8. 常见误解与能力边界；
9. 小结、复习题和延伸阅读。

章节可以按内容调整二级标题，但不能删掉“能力边界”和“复习题”。

## 事实与措辞

- 使用 **Agent Core** 指 Runtime 中稳定的 run/turn/model/tool 控制循环；
- Hook 数量固定写作 **14 个 Hook 类型**，不得与 Plugin 数量混淆；
- Plugin 写作**构建期能力包**，不得描述成 built Harness 上的热插拔模块；
- Rust Plugin 可贡献 tools、hooks、skills、templates；Python `create_plugin()` 当前只开放
  tools 与 hooks；
- local Knowledge 当前是 BM25，不写成向量或混合检索；
- Senza 内置 MemoryStore 是进程内 `Mutex<Vec>` demo，不持久化，且不会自动进入
  local Knowledge source；
- Session Recall 的 Python projector/index population 链路尚未完整公开；
- Senza spawn 当前只给主 Agent 自动挂载 5 个管理工具，child 使用 `NoopPlugin`；
- 教学 eval 与 improvement proposal 属于 Academy 层，不写成 Runtime 已内建产品。

## 证据等级

- **stable**：当前公开 API、源码与自动化测试可以共同证明；
- **teaching**：为讲清方法而提供的确定性教学实现，不等同于 Runtime 产品能力；
- **preview**：底层契约或部分装配存在，但当前 Python 端到端路径仍不完整。

recorded trace 只能证明经审阅的机制叙事；真实 Provider、Hook dispatch、持久化或系统调用必须由
live example 或集成测试证明。

## 引用

- 理论出处链接到本地 `ai-agent-book` 的对应章节；
- 工程事实优先链接到 Runtime/Senza 源码，其次链接权威文档；
- 实践步骤链接对应 `academy/labs/*`，不在教材中复制一套会漂移的完整 demo；
- 不使用大段原文引述；理论部分必须使用自己的语言解释。
