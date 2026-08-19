"""Deterministic teaching model for the basic spawn/message lifecycle.

This module deliberately uses only the Python standard library. It models
registry state and message isolation; it does not pretend to execute an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Literal, Optional, Union


MAIN_SIDE_TOOLS = (
    "spawn_agent",
    "message_subagent",
    "await_subagent_reply",
    "query_subagent",
    "abort_subagent",
)
RUNTIME_CHILD_SIDE_TOOLS = ("message_main", "await_main_message")
SENZA_CHILD_PLUGIN = "NoopPlugin"
SENZA_DEFAULT_CHILD_TOOLS: tuple[str, ...] = ()

ChildStatus = Literal["running", "done", "aborted"]


@dataclass
class ChildTask:
    """One isolated child context and its observable registry state."""

    agent_id: str
    prompt: str
    injected_context: tuple[str, ...]
    role: Optional[str] = None
    description: Optional[str] = None
    status: ChildStatus = "running"
    inbox: list[str] = field(default_factory=list)
    result: Optional[str] = None

    @property
    def context_view(self) -> tuple[str, ...]:
        """The explicit child-visible context; no main history is inherited."""

        return (self.prompt, *self.injected_context, *self.inbox)


class CoordinatorModel:
    """Small state machine mirroring the main-side spawn control surface."""

    def __init__(self, main_context: tuple[str, ...]) -> None:
        self.main_context = list(main_context)
        self.children: dict[str, ChildTask] = {}

    def spawn_agent(
        self,
        prompt: str,
        *,
        context: tuple[str, ...] = (),
        role: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        agent_id = f"sub-{len(self.children) + 1}"
        self.children[agent_id] = ChildTask(
            agent_id=agent_id,
            prompt=prompt,
            injected_context=tuple(context),
            role=role,
            description=description,
        )
        return agent_id

    def message_subagent(self, agent_id: str, message: str) -> None:
        child = self._running_child(agent_id)
        if not message.strip():
            raise ValueError("message must not be empty")
        child.inbox.append(message)

    def query_subagent(
        self, agent_id: Optional[str] = None
    ) -> Union[dict[str, Any], List[dict[str, Any]]]:
        if agent_id is not None:
            return self._snapshot(self._child(agent_id))
        return [self._snapshot(child) for child in self.children.values()]

    def complete(self, agent_id: str, result: str) -> None:
        child = self._running_child(agent_id)
        if not result.strip():
            raise ValueError("result must not be empty")
        child.result = result
        child.status = "done"

    def abort_subagent(self, agent_id: str) -> None:
        child = self._running_child(agent_id)
        child.status = "aborted"

    def await_subagent_reply(self, agent_id: str) -> dict[str, Optional[str]]:
        child = self._child(agent_id)
        if child.status == "running":
            return {"agent_id": agent_id, "status": "waiting", "result": None}
        return {
            "agent_id": agent_id,
            "status": child.status,
            "result": child.result,
        }

    def _child(self, agent_id: str) -> ChildTask:
        try:
            return self.children[agent_id]
        except KeyError as error:
            raise KeyError(f"unknown child: {agent_id}") from error

    def _running_child(self, agent_id: str) -> ChildTask:
        child = self._child(agent_id)
        if child.status != "running":
            raise ValueError(f"{agent_id} is already {child.status}")
        return child

    @staticmethod
    def _snapshot(child: ChildTask) -> dict[str, Any]:
        # role/description are copied into the snapshot only; they do not drive
        # transitions, prompts, tools, or permissions in this model.
        return {
            "agent_id": child.agent_id,
            "status": child.status,
            "role": child.role,
            "description": child.description,
        }


@dataclass
class ScenarioResult:
    coordinator: CoordinatorModel
    completed_agent: str
    aborted_agent: str
    events: list[dict[str, Any]]


def run_recorded_scenario() -> ScenarioResult:
    """Execute the stable classroom scenario and return its state plus events."""

    coordinator = CoordinatorModel(
        main_context=(
            "private-main-note: leadership prefers option B",
            "task: compare two release strategies",
        )
    )
    events: list[dict[str, Any]] = []

    def record(
        kind: str,
        actor: str,
        summary: str,
        status: str,
        lifecycle: str,
    ) -> None:
        events.append(
            {
                "seq": len(events) + 1,
                "kind": kind,
                "actor": actor,
                "summary": summary,
                "status": status,
                "lifecycle": lifecycle,
            }
        )

    first = coordinator.spawn_agent(
        "Reason about the reliability trade-off of canary release.",
        context=("criterion: minimize user-visible failure",),
        role="reasoner-a",
        description="Evaluate one independent option",
    )
    record(
        "tool",
        "main",
        "创建 sub-1：只注入 canary 任务包；role=reasoner-a 仅作展示元数据",
        "accepted",
        "spawn_agent",
    )

    second = coordinator.spawn_agent(
        "Reason about the operational trade-off of blue-green release.",
        context=("criterion: minimize rollback time",),
        role="reasoner-b",
        description="Evaluate a second independent option",
    )
    record(
        "tool",
        "main",
        "创建 sub-2：只注入 blue-green 任务包，与 sub-1 及 Main 私有上下文隔离",
        "accepted",
        "spawn_agent",
    )

    snapshots = coordinator.query_subagent()
    record(
        "tool",
        "main",
        f"非阻塞查询两个子任务：{snapshots[0]['status']} / {snapshots[1]['status']}",
        "info",
        "query_subagent",
    )

    coordinator.message_subagent(first, "Also state one measurable rollback signal.")
    record(
        "tool",
        "main",
        "只向 sub-1 追加 rollback signal 要求；sub-2 的 inbox 保持为空",
        "accepted",
        "message_subagent",
    )

    coordinator.complete(
        first,
        "Canary limits blast radius; watch error-rate delta and roll back on threshold breach.",
    )
    record(
        "agent",
        first,
        "纯推理任务完成并产生一个显式结果；私有轨迹不复制给 Main",
        "passed",
        "child running → done",
    )

    first_reply = coordinator.await_subagent_reply(first)
    record(
        "tool",
        "main",
        f"等待并收取 sub-1 完成事件：status={first_reply['status']}",
        "ok",
        "await_subagent_reply",
    )

    second_snapshot = coordinator.query_subagent(second)
    record(
        "tool",
        "main",
        f"再次查询 sub-2：status={second_snapshot['status']}，决定停止不再需要的分支",
        "info",
        "query_subagent",
    )

    coordinator.abort_subagent(second)
    record(
        "tool",
        "main",
        "取消 sub-2，使状态从 running 转为 aborted",
        "accepted",
        "abort_subagent",
    )

    second_reply = coordinator.await_subagent_reply(second)
    record(
        "tool",
        "main",
        f"收取 sub-2 终止事件：status={second_reply['status']}，没有伪造结果",
        "ok",
        "await_subagent_reply",
    )

    coordinator.main_context.append(first_reply["result"] or "")
    record(
        "context",
        "main",
        "Main 只合入 sub-1 的显式结果；两个子 Agent 的私有 context 仍未暴露",
        "passed",
        "manager synthesis",
    )

    return ScenarioResult(
        coordinator=coordinator,
        completed_agent=first,
        aborted_agent=second,
        events=events,
    )
