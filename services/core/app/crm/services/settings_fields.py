"""网页上可修改的配置项清单：通用业务规则（GLOBAL_FIELDS）和行业包参数（pack.yaml 的 settings 段）。

只声明「有哪些项、怎么显示、取值范围」；读写和校验在 settings_service。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.packs.registry import PackInfo
from app.rules.loader import read_yaml

Kind = Literal[
    "percent", "money", "int", "float", "cities", "percent_list", "stages", "megabytes", "bool"
]


class SettingField(BaseModel):
    """一个可在网页上修改的配置项。值按存储单位：比例是小数、金额是分、大小是字节。"""

    key: str  # 点分路径
    label: str
    group: str
    kind: Kind
    unit: str = ""
    min: float | None = None
    max: float | None = None
    help: str = ""


class SettingValue(SettingField):
    value: Any
    default: Any
    overridden: bool
    updated_at: datetime | None = None
    updated_by: str | None = None


class SettingsOut(BaseModel):
    groups: list[str]
    fields: list[SettingValue]


class SettingsUpdate(BaseModel):
    """key → 新值；null 表示恢复默认。"""

    values: dict[str, Any]


def _f(key: str, label: str, group: str, kind: Kind, **kw: Any) -> SettingField:
    return SettingField(key=key, label=label, group=group, kind=kind, **kw)


_STAGE_LABELS = {
    "lead": "线索",
    "qualified": "需求确认",
    "proposal": "方案报价",
    "negotiation": "商务谈判",
}

GLOBAL_FIELDS: list[SettingField] = [
    _f(
        "org.solo_mode",
        "个人模式",
        "工作方式",
        "bool",
        help="一个人接单时打开：报价、报销触发审批规则时自动通过（原因照常记在动态里）；"
        "主管账号可以进入模型接入、行业包、业务规则等系统配置，团队相关的页面隐藏",
    ),
    _f(
        "margin.floor_rate",
        "毛利底线",
        "报价与审批",
        "percent",
        min=0,
        max=0.9,
        help="报价毛利低于该值，需要主管审批",
    ),
    _f(
        "discount.max_rate",
        "销售折扣权限",
        "报价与审批",
        "percent",
        min=0,
        max=0.9,
        help="销售可以直接给的最大折扣，超过需要主管审批",
    ),
    _f("quote.valid_days", "报价有效期", "报价与审批", "int", unit="天", min=1, max=365),
    _f(
        "quote.followup_days",
        "发送报价后跟进",
        "报价与审批",
        "int",
        unit="天",
        min=0,
        max=60,
        help="报价单标记已发送时自动建一条跟进任务，这么多天后到期；0 表示不建",
    ),
    _f("commission.rates.hardware", "提成比例 · 硬件", "提成", "percent", min=0, max=0.5),
    _f("commission.rates.software", "提成比例 · 软件", "提成", "percent", min=0, max=0.5),
    _f("commission.rates.service", "提成比例 · 服务", "提成", "percent", min=0, max=0.5),
    _f(
        "commission.low_margin_floor",
        "低毛利线",
        "提成",
        "percent",
        min=0,
        max=0.9,
        help="合同毛利低于该值时，提成按下方系数打折",
    ),
    _f("commission.low_margin_factor", "低毛利提成系数", "提成", "float", unit="倍", min=0, max=1),
    _f("expense.entertainment_per_person", "客户招待标准", "报销", "money", unit="元/人", min=0),
    _f("expense.hotel.per_night", "住宿标准 · 其他城市", "报销", "money", unit="元/晚", min=0),
    _f(
        "expense.hotel.per_night_tier1", "住宿标准 · 一线城市", "报销", "money", unit="元/晚", min=0
    ),
    _f(
        "expense.hotel.tier1_cities",
        "一线城市",
        "报销",
        "cities",
        help="城市名包含其中任意一个即按一线标准",
    ),
    *[
        _f(
            f"pipeline.stage_win_rate.{k}",
            f"默认赢率 · {v}",
            "商机",
            "int",
            unit="%",
            min=0,
            max=100,
        )
        for k, v in _STAGE_LABELS.items()
    ],
    _f(
        "pipeline.stale_days",
        "停滞提醒",
        "商机",
        "int",
        unit="天",
        min=1,
        max=365,
        help="进行中的商机超过这么多天没有动态，提醒负责人",
    ),
    _f(
        "payment.schedule",
        "标准回款计划",
        "回款",
        "stages",
        help="合同生成时按此拆分回款期次，比例合计必须是 100%",
    ),
    _f(
        "payment.remind_days",
        "到期前提醒",
        "回款",
        "int",
        unit="天",
        min=0,
        max=30,
        help="每期回款到期前这么多天提醒合同负责人，可以提前开票、提醒客户付款；0 表示不提醒",
    ),
    _f(
        "payment.followup_days",
        "逾期跟进",
        "回款",
        "int",
        unit="天",
        min=1,
        max=365,
        help="逾期超过这么多天，每周跟进",
    ),
    _f(
        "payment.block_days",
        "逾期暂停新报价",
        "回款",
        "int",
        unit="天",
        min=1,
        max=730,
        help="逾期超过这么多天，暂停该客户新报价的审批",
    ),
    _f("attachment.max_bytes", "单个票据大小上限", "票据", "megabytes", unit="MB", min=1, max=50),
    _f(
        "privacy.phone_reveal_daily_limit",
        "每天查看完整电话次数",
        "数据安全",
        "int",
        unit="次",
        min=0,
        max=1000,
        help="联系人电话默认脱敏显示，点「查看」才显示完整号码并记入操作日志",
    ),
    _f(
        "privacy.export_max_rows",
        "单次导出上限",
        "数据安全",
        "int",
        unit="条",
        min=1,
        max=10000,
        help="列表导出 CSV 的最大条数；销售不能导出客户和商机名单",
    ),
    _f(
        "agent.margin_max_retries",
        "毛利不达标时重新配置次数",
        "AI 助手",
        "int",
        unit="次",
        min=0,
        max=5,
    ),
    _f("agent.max_tool_calls", "单轮最多调用工具次数", "AI 助手", "int", unit="次", min=1, max=20),
    _f(
        "ai_usage.input_price_per_million",
        "输入单价",
        "AI 用量",
        "float",
        unit="元/百万 tokens",
        min=0,
        max=1000,
        help="按所用模型的官方价格填写，用于估算 AI 费用",
    ),
    _f(
        "ai_usage.output_price_per_million",
        "输出单价",
        "AI 用量",
        "float",
        unit="元/百万 tokens",
        min=0,
        max=1000,
    ),
    _f(
        "ai_usage.monthly_budget",
        "全公司月度预算",
        "AI 用量",
        "money",
        min=0,
        help="超过 80% 时 AI 用量页提醒；0 表示不设，不会拦截调用",
    ),
    _f("ai_usage.team_monthly_budget", "每个团队月度预算", "AI 用量", "money", min=0),
    _f(
        "ai_usage.user_daily_tokens",
        "每人每日 tokens 上限",
        "AI 用量",
        "int",
        unit="tokens",
        min=0,
        help="超过后当天不能再发起 AI 对话、识别和日报草稿（已在确认中的操作不受影响）；0 表示不限",
    ),
]


def pack_fields(pack: PackInfo) -> list[SettingField]:
    """行业包可改的参数在 pack.yaml 的 settings 段声明；毛利底线每个行业包都可以单独设置。"""
    manifest = read_yaml(pack.path / "pack.yaml")
    fields = [
        _f(
            "margin.floor_rate",
            "本行业毛利底线",
            "报价",
            "percent",
            min=0,
            max=0.9,
            help="不单独设置时沿用通用规则",
        ),
    ]
    return fields + [SettingField.model_validate(x) for x in manifest.get("settings", [])]
