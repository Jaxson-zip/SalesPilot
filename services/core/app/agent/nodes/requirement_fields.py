"""方案需求的大模型结构化抽取。

行业包的 requirement_model 有必填字段；抽取时把所有字段改成可选（没提到就留空，不让模型猜），
抽到的值再交给 parse_requirement 工具与规则抽取结果合并，并用完整的 schema 校验。
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, create_model

from app.agent.deps import AgentDeps

logger = logging.getLogger("core.agent")

EXTRACT_PROMPT = (
    "从用户描述里抽取方案需求字段。用户没有明确说到的字段留空，不要猜测或补默认值。"
    "金额字段以「分」为单位（40 万元 = 40000000）。"
)


def optional_model(model: type[BaseModel]) -> type[BaseModel]:
    """把需求 schema 的字段全部变为可选（保留类型和字段说明）。"""
    fields: dict[str, Any] = {
        name: (f.annotation | None, Field(default=None, description=f.description))
        for name, f in model.model_fields.items()
    }
    return create_model(f"{model.__name__}Extract", __doc__=model.__doc__, **fields)


def extract_with_llm(
    deps: AgentDeps, model: type[BaseModel], text: str, hint: str = ""
) -> dict[str, Any]:
    """返回模型抽到的非空字段；没有模型或抽取失败返回空 dict（只用规则抽取）。

    hint：行业包补充的抽取说明（例如软件外包需要把业务拆解成功能模块）。
    """
    if deps.llm is None or not text.strip():
        return {}
    try:
        schema = optional_model(model)
        extractor = deps.llm.with_structured_output(schema, method="function_calling")
        system = f"{EXTRACT_PROMPT}\n{hint}" if hint else EXTRACT_PROMPT
        out = extractor.invoke([SystemMessage(system), HumanMessage(text)])
    except Exception:
        logger.warning("parse_requirement: llm extract failed, use rules only", exc_info=True)
        return {}
    if not isinstance(out, BaseModel):
        return {}
    return {k: v for k, v in out.model_dump().items() if v is not None}
