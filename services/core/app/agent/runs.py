"""后台运行的 Agent：图的执行与浏览器连接解耦。

以前图在 SSE 响应里同步迭代，用户切到别的页面或刷新时连接断开，图跑到一半就停了，
这一轮的回复不会写进会话。现在每一轮在后台线程里跑完，事件按顺序缓存：
- 浏览器连着时实时推送；断开后后台照常跑完并写入 checkpoint；
- 回到会话时重新订阅，从第一条事件重放，接着实时推送；
- 「停止」是显式请求（不再靠断开连接）。

core 是单进程运行（uvicorn 单 worker），进程内登记即可。
"""

import contextvars
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from app.common.errors import BizError, ErrorCode

Event = dict[str, Any]
RunKind = Literal["chat", "resume"]

KEEP_FINISHED_SECONDS = 600  # 结束后保留一会儿，刚好在结束时回来的页面还能重放
WAIT_SECONDS = 1.0  # 订阅者等新事件的间隔（期间连接断开能及时退出）


@dataclass
class Run:
    thread_id: str
    user_id: str
    kind: RunKind
    # chat：用户这一轮发的消息；resume：approve / reject
    input: str
    # 这一轮开始前的会话（history.ThreadMessages）：回来时页面先显示它，再重放本轮事件
    base: Any = None
    events: list[Event] = field(default_factory=list)
    done: bool = False
    cancelled: bool = False
    finished_at: float | None = None
    cond: threading.Condition = field(default_factory=threading.Condition)

    @property
    def active(self) -> bool:
        return not self.done

    def follow(self, start: int = 0) -> Iterator[Event]:
        """从第 start 条事件开始，按顺序产出直到本轮结束（同步，供线程池迭代）。

        不能在持有锁时 yield：订阅者断开后生成器停在 yield 处不再继续，
        锁就永远不会释放，后台线程写下一条事件时会一直卡住。
        """
        i = start
        while True:
            with self.cond:
                if i >= len(self.events) and not self.done:
                    self.cond.wait(WAIT_SECONDS)
                batch = self.events[i:]
                finished = self.done
            if not batch and not finished:
                yield {"event": "__wait__", "data": {}}  # 让上层有机会发现连接已断开
                continue
            yield from batch
            i += len(batch)
            if finished and i >= len(self.events):
                return


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    def get(self, thread_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(thread_id)

    def active(self, thread_id: str) -> Run | None:
        run = self.get(thread_id)
        return run if run is not None and run.active else None

    def active_threads(self, user_id: str) -> set[str]:
        with self._lock:
            return {t for t, r in self._runs.items() if r.active and r.user_id == user_id}

    def start(self, run: Run, events: Iterator[Event]) -> Run:
        """登记并在后台线程里跑完 events；同一会话上一轮还没结束时拒绝。"""
        with self._lock:
            self._purge()
            current = self._runs.get(run.thread_id)
            if current is not None and current.active:
                raise BizError(ErrorCode.DUPLICATE, "上一条回复还在生成，请等它完成或先停止")
            self._runs[run.thread_id] = run
        ctx = contextvars.copy_context()  # 保留 request_id 等日志上下文
        worker = threading.Thread(
            target=ctx.run, args=(_pump, run, events), name=f"agent-{run.thread_id}", daemon=True
        )
        worker.start()
        return run

    def stop(self, thread_id: str) -> bool:
        run = self.active(thread_id)
        if run is None:
            return False
        run.cancelled = True
        return True

    def _purge(self) -> None:
        now = time.monotonic()
        for t, r in list(self._runs.items()):
            if r.finished_at is not None and now - r.finished_at > KEEP_FINISHED_SECONDS:
                del self._runs[t]


def _pump(run: Run, events: Iterator[Event]) -> None:
    """后台线程：迭代图的事件写入缓存；收到停止请求时关闭生成器（图在当前节点后停下）。"""
    try:
        for ev in events:
            if run.cancelled:  # 停止后产生的事件丢弃
                close = getattr(events, "close", None)
                if close is not None:
                    close()
                with run.cond:
                    run.events.append({"event": "done", "data": {"thread_id": run.thread_id}})
                break
            with run.cond:
                run.events.append(ev)
                run.cond.notify_all()
    finally:
        with run.cond:
            run.done = True
            run.finished_at = time.monotonic()
            run.cond.notify_all()


registry = RunRegistry()
