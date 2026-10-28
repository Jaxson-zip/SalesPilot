"""记录每次大模型调用的 token 用量，按人、按功能统计 AI 成本。

- 请求进来时（RequestIdMiddleware）把当前用户和接口路径放进 contextvar；
  Agent 后台线程用 copy_context 继承，所以对话里的模型调用也能归到发起人；
- get_chat_model 给每个模型挂上 UsageCallback，调用结束读 token 用量写 ai_usage；
- 记录失败只打日志，绝不影响业务请求。
"""

import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("core.llm.usage")


@dataclass(frozen=True)
class UsageContext:
    user_id: uuid.UUID | None
    team_id: uuid.UUID | None
    path: str


_ctx: ContextVar[UsageContext | None] = ContextVar("usage_ctx", default=None)

# 接口路径 → 功能名（按顺序匹配第一个包含的片段）
FEATURES: list[tuple[str, str]] = [
    ("/api/agent/materials", "材料识别"),
    ("/api/agent/", "AI 工作台"),
    ("/meddic/assess", "赢单评估"),
    ("/api/reports/daily/draft", "日报草稿"),
    ("/api/reports/team/summary", "团队汇总"),
]
OTHER = "其他"


def feature_for(path: str) -> str:
    return next((name for part, name in FEATURES if part in path), OTHER)


def bind(path: str, authorization: str | None) -> Any:
    """请求开始时调用；返回 token 供 reset。令牌无效时只记路径。"""
    from app.common.auth import decode_token  # 避免循环导入

    user_id = team_id = None
    if authorization and authorization.lower().startswith("bearer "):
        try:
            user = decode_token(authorization.split(" ", 1)[1].strip())
            user_id, team_id = user.id, user.team_id
        except Exception:
            pass
    return _ctx.set(UsageContext(user_id=user_id, team_id=team_id, path=path))


def reset(token: Any) -> None:
    _ctx.reset(token)


def current() -> UsageContext | None:
    return _ctx.get()


def _tokens(response: LLMResult) -> tuple[int, int, str | None]:
    out = response.llm_output or {}
    usage = out.get("token_usage") or {}
    model = out.get("model_name")
    p, c = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    if not (p or c):
        # 流式：用量在最后一片里，LangChain 合并到 message.usage_metadata
        for gens in response.generations:
            for g in gens:
                msg = getattr(g, "message", None)
                meta = getattr(msg, "usage_metadata", None) or {}
                p += int(meta.get("input_tokens") or 0)
                c += int(meta.get("output_tokens") or 0)
                model = model or (getattr(msg, "response_metadata", None) or {}).get("model_name")
    return p, c, model


def record(alias: str, response: LLMResult, request_id: str | None) -> None:
    from app.common.db import session_scope
    from app.crm.models import AiUsage

    p, c, model = _tokens(response)
    if not (p or c):
        return
    ctx = current()
    try:
        with session_scope() as db:
            db.add(
                AiUsage(
                    user_id=ctx.user_id if ctx else None,
                    team_id=ctx.team_id if ctx else None,
                    feature=feature_for(ctx.path) if ctx else "系统",
                    model=(model or alias)[:80],
                    prompt_tokens=p,
                    completion_tokens=c,
                    request_id=(request_id or None) and request_id[:40],
                )
            )
    except Exception:
        logger.warning("ai usage: failed to record", exc_info=True)


class UsageCallback(BaseCallbackHandler):
    def __init__(self, alias: str, request_id: str | None) -> None:
        self.alias = alias
        self.request_id = request_id

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        record(self.alias, response, self.request_id)
