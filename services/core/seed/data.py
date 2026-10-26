"""演示数据（与 prototype/index.html 一致）。金额单位：分；所有价格为模拟数据。"""

from datetime import date
from typing import Any

from app.common.auth import Role
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES, TEAM_SOUTH_ID, demo_id

SALES = DEMO_USERS[Role.SALES]
MANAGER = DEMO_USERS[Role.MANAGER]
ADMIN = DEMO_USERS[Role.ADMIN]
USERS = [SALES, MANAGER, ADMIN, EXTRA_SALES]

TEAM: dict[str, Any] = {"id": TEAM_SOUTH_ID, "name": "华南销售组"}

PL_LLM = demo_id("product_line:llm")
PL_IT = demo_id("product_line:it")
PRODUCT_LINES: list[dict[str, Any]] = [
    {"id": PL_LLM, "name": "大模型私有化部署", "pack": "llm_deploy", "enabled": True},
    {"id": PL_IT, "name": "企业办公设备", "pack": "it_office", "enabled": True},
]

C_MINGLI = demo_id("customer:mingli")
C_HNZZ = demo_id("customer:hnzz")
C_XINGHE = demo_id("customer:xinghe")
C_PC3H = demo_id("customer:pc3h")
C_YUNFAN = demo_id("customer:yunfan")
C_YUEHAI = demo_id("customer:yuehai")
C_NANSHAN = demo_id("customer:nanshan")

CUSTOMERS: list[dict[str, Any]] = [
    {
        "id": C_MINGLI,
        "name": "深圳明理律师事务所",
        "industry": "法律服务",
        "level": "A",
        "size": "120 人",
        "address": "深圳市福田区",
        "website": "mingli-law.cn",
        "annual_budget": 40_000_000,
        "tags": ["重点客户"],
        "owner": SALES,
    },
    {
        "id": C_HNZZ,
        "name": "华南智能制造有限公司",
        "industry": "制造业",
        "level": "A",
        "size": "800 人",
        "address": "东莞市松山湖",
        "website": "hnzz.com",
        "annual_budget": 60_000_000,
        "tags": [],
        "owner": SALES,
    },
    {
        "id": C_XINGHE,
        "name": "星河设计工作室",
        "industry": "设计",
        "level": "B",
        "size": "40 人",
        "address": "深圳市南山区",
        "website": "xinghe.design",
        "annual_budget": 30_000_000,
        "tags": [],
        "owner": SALES,
    },
    {
        "id": C_PC3H,
        "name": "鹏城第三人民医院",
        "industry": "医疗",
        "level": "B",
        "size": "1500 人",
        "address": "深圳市龙岗区",
        "website": "pc3h.org.cn",
        "annual_budget": 80_000_000,
        "tags": [],
        "owner": EXTRA_SALES,
    },
    {
        "id": C_YUNFAN,
        "name": "前海云帆科技",
        "industry": "互联网",
        "level": "C",
        "size": "60 人",
        "address": "深圳市前海",
        "website": "yunfan.tech",
        "annual_budget": None,
        "tags": [],
        "owner": SALES,
    },
    {
        "id": C_YUEHAI,
        "name": "粤海物流集团",
        "industry": "物流",
        "level": "A",
        "size": "2000 人",
        "address": "广州市黄埔区",
        "website": "yuehai-logistics.cn",
        "annual_budget": 100_000_000,
        "tags": ["已签约"],
        "owner": SALES,
    },
    {
        "id": C_NANSHAN,
        "name": "南山教育集团",
        "industry": "教育",
        "level": "B",
        "size": "600 人",
        "address": "深圳市南山区",
        "website": "nanshan-edu.cn",
        "annual_budget": 35_000_000,
        "tags": ["已签约"],
        "owner": SALES,
    },
]

OPPORTUNITIES: list[dict[str, Any]] = [
    {
        "id": demo_id("opp:mingli"),
        "customer_id": C_MINGLI,
        "name": "合同审查私有化",
        "stage": "proposal",
        "amount": 37_200_000,
        "win_rate": 60,
        "expected_close_date": date(2026, 11, 15),
        "product_line_id": PL_LLM,
        "owner": SALES,
    },
    {
        "id": demo_id("opp:hnzz"),
        "customer_id": C_HNZZ,
        "name": "质检助手",
        "stage": "proposal",
        "amount": 46_000_000,
        "win_rate": 50,
        "expected_close_date": date(2026, 12, 1),
        "product_line_id": PL_LLM,
        "owner": SALES,
    },
    {
        "id": demo_id("opp:xinghe"),
        "customer_id": C_XINGHE,
        "name": "IT 设备换新",
        "stage": "qualified",
        "amount": 23_800_000,
        "win_rate": 40,
        "expected_close_date": date(2026, 11, 20),
        "product_line_id": PL_IT,
        "owner": SALES,
    },
    {
        "id": demo_id("opp:pc3h"),
        "customer_id": C_PC3H,
        "name": "病历质控",
        "stage": "qualified",
        "amount": 52_000_000,
        "win_rate": 30,
        "expected_close_date": date(2026, 12, 15),
        "product_line_id": PL_LLM,
        "owner": EXTRA_SALES,
    },
    {
        "id": demo_id("opp:yunfan"),
        "customer_id": C_YUNFAN,
        "name": "AI 客服",
        "stage": "lead",
        "amount": 15_000_000,
        "win_rate": 10,
        "expected_close_date": date(2026, 11, 30),
        "product_line_id": PL_LLM,
        "owner": SALES,
    },
    {
        "id": demo_id("opp:yuehai"),
        "customer_id": C_YUEHAI,
        "name": "智能调度",
        "stage": "won",
        "amount": 81_000_000,
        "win_rate": 100,
        "expected_close_date": date(2026, 10, 20),
        "product_line_id": PL_LLM,
        "owner": SALES,
    },
    {
        "id": demo_id("opp:nanshan"),
        "customer_id": C_NANSHAN,
        "name": "校本知识库",
        "stage": "won",
        "amount": 28_600_000,
        "win_rate": 100,
        "expected_close_date": date(2026, 10, 12),
        "product_line_id": PL_LLM,
        "owner": SALES,
    },
]

FOLLOWUPS: list[dict[str, Any]] = [
    {
        "id": demo_id("fu:mingli:1"),
        "customer_id": C_MINGLI,
        "type": "visit",
        "source": "manual",
        "content": "与王律师、IT 负责人陈工见面，客户关注数据不出内网、审计日志。",
    },
    {
        "id": demo_id("fu:mingli:2"),
        "customer_id": C_MINGLI,
        "type": "phone",
        "source": "manual",
        "content": "确认 50 人并发、合同审查场景，预算 40 万以内，下周看方案。",
    },
    {
        "id": demo_id("fu:hnzz:1"),
        "customer_id": C_HNZZ,
        "type": "ai",
        "source": "agent",
        "content": "根据会议纪要更新了商机阶段：需求确认 → 方案报价。",
    },
]
