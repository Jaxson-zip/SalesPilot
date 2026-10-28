"""competitors：竞品战卡；opportunities.competitor_ids：商机遇到的竞品

内置三类常见竞争形态作为示例（不针对具体公司），管理员可在网页上修改或删除。

Revision ID: 0012_competitors
Revises: 0011_meddic
Create Date: 2026-10-28
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_competitors"
down_revision: str | None = "0011_meddic"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SAMPLES = [
    {
        "id": uuid.UUID("00000000-0000-4000-8000-0000000c0001"),
        "name": "公有云大模型 API",
        "aliases": ["公有云", "云 API", "调用 API", "按量付费"],
        "summary": "按调用量计费的云上大模型服务，起步快、免运维。",
        "strengths": ["起步成本低，按量付费", "免运维，模型版本更新快", "生态和工具链成熟"],
        "weaknesses": [
            "数据要出内网，合规评估难过（法务、医疗、政企尤其敏感）",
            "长期调用成本随用量线性增长",
            "难以深度定制，和内网系统对接受限",
        ],
        "win_tactics": [
            "按客户实际调用量算 3 年总成本（TCO），给出盈亏平衡点",
            "强调数据不出内网、满足等保和行业合规",
            "可提混合方案：敏感数据私有化，通用任务调云",
        ],
        "objections": [
            {
                "say": "云上 API 便宜多了，按量付费更灵活",
                "respond": "按贵司预计的调用量测算，一年半左右私有化总成本就会更低；"
                "而且合同、病历等敏感数据不出内网，省去合规评估。我先给您做一版 3 年成本对比。",
            },
            {
                "say": "云厂商的模型更新更快",
                "respond": "私有化方案支持定期升级开源模型，升级包含在维保里；"
                "核心业务更需要版本可控、结果可复现，升级节奏由贵司决定。",
            },
        ],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-8000-0000000c0002"),
        "name": "大模型一体机厂商",
        "aliases": ["一体机", "硬件厂商", "整机"],
        "summary": "软硬件打包的一体机，开箱即用，偏重硬件交付。",
        "strengths": ["开箱即用，交付快", "硬件议价能力强"],
        "weaknesses": [
            "行业应用和知识库落地薄弱，后续定制要另找人",
            "绑定单一硬件，扩容和升级不灵活",
        ],
        "win_tactics": [
            "突出行业包：合同审查 / 病历质控等场景的知识库和流程落地",
            "硬件可选多品牌，按并发和预算配置",
            "把培训、上线后的使用率保障写进方案",
        ],
        "objections": [
            {
                "say": "一体机插电就能用，你们还要部署",
                "respond": "一体机解决的是「能跑模型」，我们交付的是「能用起来」："
                "知识库、权限对接、培训都在方案里，上线后真正有人用才有价值。",
            }
        ],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-8000-0000000c0003"),
        "name": "客户自建（开源 + 自有团队）",
        "aliases": ["自建", "自研", "开源", "自己搭"],
        "summary": "客户 IT 团队用开源模型自己搭建。",
        "strengths": ["看起来成本最低", "完全自主可控"],
        "weaknesses": [
            "招人难、周期长，通常半年以上才能稳定",
            "选型、显存规划、推理优化、升级运维都要自己扛",
        ],
        "win_tactics": [
            "帮客户估算自建人力成本（算法 + 运维工程师的年成本）",
            "提供「交付 + 培训 + 转交」模式，保留客户自主权",
        ],
        "objections": [
            {
                "say": "我们 IT 自己用开源搭一套就行",
                "respond": "开源模型能跑起来不难，难的是选型、显存规划、推理优化和持续升级。"
                "我们可以按「交付 + 培训」来做，3 个月内上线，同时把能力转交给贵司团队。",
            }
        ],
    },
]


def upgrade() -> None:
    table = op.create_table(
        "competitors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("aliases", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strengths", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("weaknesses", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("win_tactics", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("objections", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.String(50), nullable=True),
    )
    op.add_column(
        "opportunities",
        sa.Column("competitor_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.bulk_insert(table, SAMPLES)


def downgrade() -> None:
    op.drop_column("opportunities", "competitor_ids")
    op.drop_table("competitors")
