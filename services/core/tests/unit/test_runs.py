"""后台运行的 Agent：浏览器断开不中断、回来重放、同一会话不能并发、显式停止。"""

import threading
from collections.abc import Iterator

import pytest

from app.agent.runs import Event, Run, RunRegistry
from app.common.errors import BizError, ErrorCode


def gated(gate: threading.Event, closed: list[bool]) -> Iterator[Event]:
    try:
        yield {"event": "message.delta", "data": {"text": "第一段"}}
        gate.wait(5)
        yield {"event": "message.delta", "data": {"text": "第二段"}}
        yield {"event": "done", "data": {"thread_id": "t1"}}
    finally:
        closed.append(True)


def wait_done(run: Run) -> None:
    with run.cond:
        assert run.cond.wait_for(lambda: run.done, 5)


def real(events: Iterator[Event]) -> list[Event]:
    return [e for e in events if e["event"] != "__wait__"]


def test_run_finishes_after_subscriber_leaves_and_replays() -> None:
    reg, gate, closed = RunRegistry(), threading.Event(), []
    run = reg.start(Run("t1", "u1", "chat", "你好"), gated(gate, closed))
    first = next(e for e in run.follow() if e["event"] != "__wait__")
    assert first["data"]["text"] == "第一段"  # 订阅者看完第一条就离开（页面切走）
    gate.set()
    wait_done(run)
    replay = real(run.follow())  # 回到会话：从头重放
    assert [e["data"].get("text") for e in replay] == ["第一段", "第二段", None]
    assert reg.active("t1") is None and reg.get("t1") is run


def test_same_thread_cannot_run_twice() -> None:
    reg, gate = RunRegistry(), threading.Event()
    reg.start(Run("t1", "u1", "chat", "a"), gated(gate, []))
    with pytest.raises(BizError) as exc:
        reg.start(Run("t1", "u1", "chat", "b"), gated(gate, []))
    assert exc.value.code == ErrorCode.DUPLICATE
    assert reg.active_threads("u1") == {"t1"} and reg.active_threads("u2") == set()
    gate.set()


def test_stop_closes_graph_and_ends_with_done() -> None:
    reg, gate, closed = RunRegistry(), threading.Event(), []
    run = reg.start(Run("t1", "u1", "chat", "a"), gated(gate, closed))
    assert reg.stop("t1")
    gate.set()
    wait_done(run)
    events = real(run.follow())
    assert events[-1]["event"] == "done" and closed == [True]
    assert all(e["data"].get("text") != "第二段" for e in events)
    assert not reg.stop("t1")  # 已结束的不再处理


def test_abandoned_subscriber_does_not_block_run() -> None:
    """回归：订阅者在等待中断开（生成器停在 yield 处）时，后台照样能写完事件。"""
    reg, gate = RunRegistry(), threading.Event()
    run = reg.start(Run("t1", "u1", "chat", "a"), gated(gate, []))
    sub = run.follow()
    assert next(sub)["event"] == "message.delta"
    assert next(sub)["event"] == "__wait__"  # 停在等待里，之后不再继续迭代
    gate.set()
    wait_done(run)
    assert [e["event"] for e in real(run.follow())][-1] == "done"
    sub.close()
