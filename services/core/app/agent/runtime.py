"""每轮对话的运行信息：当前北京时间、这一轮实际用的模型，写进系统提示。

模型自己不知道现在几点，也不知道自己是被哪个网关、哪个别名调用的；不告诉它，
问「现在几点」「你是什么模型」时它只能编。网关对分组按顺序用第一个可用的成员，
所以在调用前就能知道这一轮用的是谁（那个模型出错时网关会切到下一个，回答里一并说明）。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.rules.crm_calc import LOCAL_TZ

WEEKDAYS = "一二三四五六日"

# 网关别名前缀 → 厂商和模型系列（别名以 services/gateway/models.yaml 为准；对不上就只报别名）
PROVIDERS: tuple[tuple[str, str], ...] = (
    ("deepseek", "深度求索 DeepSeek"),
    ("qwen", "阿里云通义千问 Qwen"),
    ("hunyuan", "腾讯混元"),
    ("glm", "智谱 GLM"),
    ("moonshot", "月之暗面 Kimi"),
    ("kimi", "月之暗面 Kimi"),
    ("doubao", "字节豆包"),
    ("ernie", "百度文心"),
    ("gpt", "OpenAI GPT"),
    ("claude", "Anthropic Claude"),
    ("gemini", "Google Gemini"),
)


@dataclass(frozen=True)
class ModelInfo:
    """selected：用户选的别名或分组；served：这一轮会用的模型别名；fallbacks：出错时依次切到的。"""

    selected: str
    served: str | None
    fallbacks: list[str] = field(default_factory=list)


def now_text(now: datetime | None = None) -> str:
    t = (now or datetime.now(LOCAL_TZ)).astimezone(LOCAL_TZ)
    return f"{t:%Y-%m-%d} 星期{WEEKDAYS[t.weekday()]} {t:%H:%M}（北京时间）"


def provider_of(alias: str) -> str | None:
    low = alias.lower()
    return next((name for prefix, name in PROVIDERS if low.startswith(prefix)), None)


def resolve_model(selected: str, cards: list[dict[str, Any]]) -> ModelInfo:
    """按网关 /models 的能力表算出这一轮会用的模型（分组取第一个可用成员）。"""
    card = next((c for c in cards if c.get("id") == selected), None)
    if card is None or not card.get("available"):
        return ModelInfo(selected=selected, served=None)
    if card.get("type") != "group":
        return ModelInfo(selected=selected, served=selected)
    members = [str(m) for m in card.get("available_members") or []]
    return ModelInfo(
        selected=selected, served=members[0] if members else None, fallbacks=members[1:]
    )


def model_text(info: ModelInfo | None) -> str:
    if info is None or info.served is None:
        return "这一轮没有接入大模型，回复由系统规则生成。"
    provider = provider_of(info.served)
    name = (
        f"{provider} 的模型（网关别名 {info.served}）"
        if provider
        else f"网关别名为 {info.served} 的模型"
    )
    via = f"，用户选的是模型分组「{info.selected}」" if info.selected != info.served else ""
    tail = f"；这个模型出错时网关会自动切到 {'、'.join(info.fallbacks)}" if info.fallbacks else ""
    return f"这一轮由 {name} 生成，经公司的模型网关调用{via}{tail}。"


def runtime_note(info: ModelInfo | None, now: datetime | None = None) -> str:
    return f"""## 运行信息（真实，回答时以此为准）
- 现在是 {now_text(now)}。问时间、日期、星期、还剩几天时按这个回答或推算。
- 你是 SalesPilot 里的 AI 助手。{model_text(info)}
- 被问到「你是什么模型 / 谁做的」时如实回答上面这句，可以说明具体用哪个模型由管理员在网关里配置；
  不要声称自己是其他公司的模型，也不要编版本号、参数量这类上面没写的信息。"""
