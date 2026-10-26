"""业务模块演示数据（与 prototype/index.html 对齐）：报价、合同、报销、审批、动态、联系人。

金额单位：分；所有价格为模拟数据。毛利、提成不写死，由 seed.business 调用规则代码计算。
"""

from datetime import date
from typing import Any

from app.crm.services.demo import demo_id
from seed.data import C_HNZZ, C_MINGLI, C_NANSHAN, C_XINGHE, C_YUEHAI, MANAGER, SALES

Q_HNZZ = demo_id("quote:hnzz")
Q_YUEHAI = demo_id("quote:yuehai")
Q_NANSHAN = demo_id("quote:nanshan")
E_MINGLI = demo_id("expense:mingli")
E_HNZZ_TRIP = demo_id("expense:hnzz-trip")


def _line(sku: str, name: str, cat: str, unit: str, qty: int, cost: int, price: int) -> dict:
    return {
        "sku": sku,
        "name": name,
        "category": cat,
        "unit": unit,
        "qty": qty,
        "unit_cost": cost,
        "unit_price": price,
    }


# 报价：status 为目标状态；paid_ratio 不为空时同时生成合同和提成
QUOTES: list[dict[str, Any]] = [
    {
        # 低毛利（22.8%）待主管审批
        "id": Q_HNZZ,
        "opportunity_id": demo_id("opp:hnzz"),
        "customer_id": C_HNZZ,
        "pack": "llm_deploy",
        "tier": "economy",
        "status": "pending_approval",
        "source": "manual",
        "items": [
            _line(
                "SRV-L20-4", "GPU 服务器 4× L20 48G", "hardware", "台", 1, 21_800_000, 26_300_000
            ),
            _line(
                "SW-MONITOR", "监控 Prometheus + Grafana", "software", "项", 1, 300_000, 1_200_000
            ),
            _line("SVC-MAINT-1Y", "一年维保", "service", "台·年", 1, 900_000, 2_300_000),
        ],
        "suggestion": "硬件占比高、服务项少。建议补充调优人天或把部署实施改为远程交付，"
        "毛利可回到 25% 以上；客户为 A 级重点客户，也可酌情通过。",
    },
    {
        # 回款中合同（40%）
        "id": Q_YUEHAI,
        "opportunity_id": demo_id("opp:yuehai"),
        "customer_id": C_YUEHAI,
        "pack": "llm_deploy",
        "tier": "standard",
        "status": "accepted",
        "source": "agent",
        "paid_ratio": 0.4,
        "items": [
            _line(
                "SRV-H20-8", "GPU 服务器 8× H20 96G", "hardware", "台", 1, 45_000_000, 54_000_000
            ),
            _line("SVC-DEPLOY", "vLLM 部署实施", "service", "项", 1, 2_000_000, 4_500_000),
            _line("SW-HA", "双机高可用与负载均衡", "software", "项", 1, 1_500_000, 3_600_000),
            _line(
                "SW-MONITOR", "监控 Prometheus + Grafana", "software", "项", 1, 300_000, 1_200_000
            ),
            _line("SVC-TUNING", "模型调优与知识库对接", "service", "人天", 18, 250_000, 600_000),
            _line("SVC-MAINT-1Y", "一年维保", "service", "台·年", 3, 900_000, 2_300_000),
        ],
    },
    {
        # 已回款合同
        "id": Q_NANSHAN,
        "opportunity_id": demo_id("opp:nanshan"),
        "customer_id": C_NANSHAN,
        "pack": "llm_deploy",
        "tier": "standard",
        "status": "accepted",
        "source": "manual",
        "paid_ratio": 1.0,
        "items": [
            _line(
                "SRV-L20-2", "GPU 服务器 2× L20 48G", "hardware", "台", 1, 11_200_000, 12_800_000
            ),
            _line("SVC-DEPLOY", "vLLM 部署实施", "service", "项", 1, 2_000_000, 4_500_000),
            _line(
                "SW-MONITOR", "监控 Prometheus + Grafana", "software", "项", 1, 300_000, 1_200_000
            ),
            _line("SVC-TUNING", "模型调优与知识库对接", "service", "人天", 13, 250_000, 600_000),
            _line("SVC-MAINT-1Y", "一年维保", "service", "台·年", 1, 900_000, 2_300_000),
        ],
    },
]

EXPENSES: list[dict[str, Any]] = [
    {
        # 超标待审批：人均 ¥215 > ¥150
        "id": E_MINGLI,
        "type": "entertainment",
        "amount": 86_000,
        "headcount": 4,
        "participants": "客户：王律师、陈工；我方：张晨、李薇",
        "occurred_on": date(2026, 10, 23),
        "customer_id": C_MINGLI,
        "opportunity_id": demo_id("opp:mingli"),
        "reason": "方案沟通晚餐",
        "status": "pending_approval",
        "suggestion": "关联商机 ¥372,000 处于方案报价阶段，客户为 A 级重点客户，超标幅度可接受。",
        "attachments": [
            ("invoice", "电子发票_海底捞福田店_860.00.pdf"),
            ("receipt", "消费小票_IMG_2041.png"),
        ],
    },
    {
        "id": E_HNZZ_TRIP,
        "type": "transport",
        "amount": 32_600,
        "headcount": 1,
        "participants": "张晨",
        "occurred_on": date(2026, 10, 17),
        "customer_id": C_HNZZ,
        "opportunity_id": demo_id("opp:hnzz"),
        "reason": "东莞现场调研",
        "status": "approved",
        "attachments": [("invoice", "高铁电子发票_深圳北-东莞.pdf")],
    },
]

CONTACTS: list[dict[str, Any]] = [
    {"key": "mingli:wang", "customer_id": C_MINGLI, "name": "王律师", "title": "管理合伙人",
     "phone": "138****1024", "is_decision_maker": True},
    {"key": "mingli:chen", "customer_id": C_MINGLI, "name": "陈工", "title": "IT 负责人",
     "phone": "139****2048", "is_decision_maker": False},
    {"key": "hnzz:liu", "customer_id": C_HNZZ, "name": "刘经理", "title": "质量部经理",
     "phone": "137****3072", "is_decision_maker": True},
    {"key": "xinghe:zhou", "customer_id": C_XINGHE, "name": "周总", "title": "创始人",
     "phone": "136****4096", "is_decision_maker": True},
]  # fmt: skip

# 动态：hours_ago 用于排序展示；actor=None 表示 AI 写入
ACTIVITIES: list[dict[str, Any]] = [
    {"key": "hnzz:stage", "subject_type": "opportunity", "subject_id": demo_id("opp:hnzz"),
     "actor": None, "action": "stage_changed", "content": "需求确认 → 方案报价", "hours_ago": 30},
    {"key": "hnzz:quote", "subject_type": "quote", "subject_id": Q_HNZZ, "actor": SALES,
     "action": "submit", "content": "提交报价单，进入主管审批：毛利 22.8% < 25%", "hours_ago": 26},
    {"key": "mingli:stage", "subject_type": "opportunity", "subject_id": demo_id("opp:mingli"),
     "actor": SALES, "action": "stage_changed", "content": "需求确认 → 方案报价", "hours_ago": 96},
    {"key": "mingli:expense", "subject_type": "expense", "subject_id": E_MINGLI, "actor": SALES,
     "action": "submit", "content": "提交报销单，超标进入主管审批：人均 ¥215 超出标准 ¥150/人",
     "hours_ago": 8},
    {"key": "yuehai:won", "subject_type": "opportunity", "subject_id": demo_id("opp:yuehai"),
     "actor": SALES, "action": "stage_changed", "content": "商务谈判 → 赢单", "hours_ago": 72},
    {"key": "yuehai:payment", "subject_type": "contract", "subject_id": demo_id("contract:yuehai"),
     "actor": MANAGER, "action": "payment", "content": "登记回款 ¥324,000，累计回款 40%",
     "hours_ago": 20},
    {"key": "nanshan:payment", "subject_type": "contract",
     "subject_id": demo_id("contract:nanshan"), "actor": MANAGER, "action": "payment",
     "content": "登记回款 ¥286,000，累计回款 100%", "hours_ago": 120},
]  # fmt: skip
