"""客户外部情报：工商信息、新闻舆情、招投标。

接入层：IntelProvider 定义统一的返回结构，真实数据源（企查查 / 天眼查 / 招投标平台的开放接口）
按同样的结构实现一个 provider 即可替换，由环境变量 INTEL_PROVIDER 选择。

当前只内置 DemoProvider：按客户名稳定生成的「演示数据」，不是真实的工商或招投标信息，
接口和页面都会明确标注 demo=true，AI 引用时也会说明是演示数据。
"""

import hashlib
import random
import uuid
from datetime import date, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.common.auth import CurrentUser
from app.common.config import get_settings
from app.common.errors import BizError, ErrorCode
from app.crm.services import customer_service
from app.crm.services.codes import local_today

SIGNAL_DAYS = 180  # 多久以内的相关招标 / 采购意向算作提示
# 招标标题命中这些词，提示「可能是我们的机会」
OPPORTUNITY_KEYWORDS = (
    "大模型",
    "人工智能",
    "AI",
    "智能",
    "知识库",
    "合同审查",
    "病历",
    "算力",
    "私有化",
)


class CompanyProfile(BaseModel):
    full_name: str
    credit_code: str
    legal_rep: str
    registered_capital: str
    founded: date
    status: str
    industry: str | None = None
    staff_size: str
    address: str


class NewsItem(BaseModel):
    date: date
    title: str
    source: str
    sentiment: Literal["positive", "neutral", "negative"]


class TenderItem(BaseModel):
    date: date
    title: str
    kind: Literal["招标", "中标", "采购意向"]
    amount: int | None = None  # 分
    winner: str | None = None
    opportunity: bool = False  # 标题命中我们的业务关键词


class RiskItem(BaseModel):
    level: Literal["low", "medium", "high"]
    text: str


class CompanyIntel(BaseModel):
    customer_id: uuid.UUID
    provider: str
    demo: bool
    notice: str | None = None
    profile: CompanyProfile
    news: list[NewsItem] = Field(default_factory=list)
    tenders: list[TenderItem] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)  # 给销售的提示（新招标、负面舆情等）


class IntelProvider(Protocol):
    name: str
    demo: bool

    def lookup(
        self, name: str, industry: str | None
    ) -> tuple[CompanyProfile, list[NewsItem], list[TenderItem], list[RiskItem]]: ...


SURNAMES = "王李张刘陈杨黄赵周吴徐孙马胡朱郭何罗高林"
GIVEN = ["建国", "海涛", "志强", "晓燕", "立新", "文博", "国华", "雪梅", "振宇", "春明"]
CITIES = ["深圳市南山区", "广州市天河区", "北京市海淀区", "上海市浦东新区", "杭州市滨江区"]
NEWS_POS = [
    "{n}发布数字化转型三年规划，提出全面引入智能化工具",
    "{n}获评年度行业创新示范单位",
    "{n}与高校共建联合实验室",
    "{n}业务规模持续增长，计划扩充团队",
]
NEWS_NEU = [
    "{n}召开年度工作会议，部署信息化建设重点",
    "{n}负责人出席行业论坛，谈数据安全与合规",
    "{n}启动内部流程优化专项",
]
NEWS_NEG = [
    "{n}因合同纠纷被列为被告（一审审理中）",
    "{n}一名高管离职",
]
TENDERS = [
    ("{n}智能合同审查系统采购项目", "招标"),
    ("{n}大模型私有化部署及知识库建设项目", "采购意向"),
    ("{n}办公设备年度采购", "招标"),
    ("{n}信息化运维服务项目", "中标"),
    ("{n}人工智能辅助办公平台试点", "招标"),
    ("{n}网络安全等级保护测评服务", "中标"),
]
WINNERS = ["某信息技术有限公司", "某软件股份有限公司", "某数据科技有限公司"]


class DemoProvider:
    """按客户名稳定生成的演示数据（同一个客户每次结果一样，日期相对今天）。"""

    name = "demo"
    demo = True

    def lookup(
        self, name: str, industry: str | None
    ) -> tuple[CompanyProfile, list[NewsItem], list[TenderItem], list[RiskItem]]:
        seed = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:12], 16)
        rnd = random.Random(seed)
        today = local_today()
        profile = CompanyProfile(
            full_name=name
            if name.endswith(("公司", "所", "院", "局", "中心"))
            else f"{name}有限公司",
            credit_code="91"
            + "".join(rnd.choice("0123456789ABCDEFGHJKLMNPQRTUWXY") for _ in range(16)),
            legal_rep=rnd.choice(SURNAMES) + rnd.choice(GIVEN),
            registered_capital=f"{rnd.choice([500, 1000, 2000, 5000, 10000])} 万元人民币",
            founded=today - timedelta(days=rnd.randint(5 * 365, 25 * 365)),
            status="存续",
            industry=industry,
            staff_size=rnd.choice(["100-499 人", "500-999 人", "1000-4999 人"]),
            address=rnd.choice(CITIES) + f"科技园 {rnd.randint(1, 30)} 栋",
        )
        news: list[NewsItem] = []
        for pool, sentiment in ((NEWS_POS, "positive"), (NEWS_NEU, "neutral")):
            for t in rnd.sample(pool, 2):
                news.append(
                    NewsItem(
                        date=today - timedelta(days=rnd.randint(1, 120)),
                        title=t.format(n=name),
                        source=rnd.choice(["行业媒体", "企业官网", "地方新闻"]),
                        sentiment=sentiment,  # type: ignore[arg-type]
                    )
                )
        risks: list[RiskItem] = []
        if rnd.random() < 0.4:
            news.append(
                NewsItem(
                    date=today - timedelta(days=rnd.randint(1, 60)),
                    title=rnd.choice(NEWS_NEG).format(n=name),
                    source="裁判文书 / 公开报道",
                    sentiment="negative",
                )
            )
            risks.append(RiskItem(level="medium", text="近期有负面舆情，拜访前了解客户关注点"))
        news.sort(key=lambda x: x.date, reverse=True)

        tenders: list[TenderItem] = []
        for title, kind in rnd.sample(TENDERS, 3):
            text = title.format(n=name)
            tenders.append(
                TenderItem(
                    date=today - timedelta(days=rnd.randint(1, 180)),
                    title=text,
                    kind=kind,  # type: ignore[arg-type]
                    amount=rnd.choice([30, 80, 120, 260, 500]) * 10_000_00,
                    winner=rnd.choice(WINNERS) if kind == "中标" else None,
                    opportunity=any(k in text for k in OPPORTUNITY_KEYWORDS),
                )
            )
        tenders.sort(key=lambda x: x.date, reverse=True)
        if not risks:
            risks.append(RiskItem(level="low", text="未发现经营异常、失信或行政处罚记录"))
        return profile, news, tenders, risks


PROVIDERS: dict[str, IntelProvider] = {"demo": DemoProvider()}


def _provider() -> IntelProvider:
    key = get_settings().intel_provider
    p = PROVIDERS.get(key)
    if p is None:
        raise BizError(
            ErrorCode.UPSTREAM,
            f"外部情报数据源「{key}」未接入，请联系管理员（可设为 demo 查看演示）",
        )
    return p


def _signals(news: list[NewsItem], tenders: list[TenderItem], today: date) -> list[str]:
    out = []
    for t in tenders:
        if t.opportunity and t.kind != "中标" and (today - t.date).days <= SIGNAL_DAYS:
            out.append(
                f"{t.date:%m-%d} {t.kind}：{t.title}，与我们的业务相关，建议尽快确认需求和预算"
            )
    for n in news:
        if n.sentiment == "negative":
            out.append(f"{n.date:%m-%d} 负面舆情：{n.title}")
    return out


def company_intel(db: Session, user: CurrentUser, customer_id: uuid.UUID) -> CompanyIntel:
    """只能查看自己可见的客户。"""
    c = customer_service.get_customer(db, user, customer_id)
    p = _provider()
    profile, news, tenders, risks = p.lookup(c.name, c.industry)
    if p.demo:
        # 演示数据不要和 CRM 里已经录入的信息打架
        if c.address:
            profile.address = c.address
        if c.size:
            profile.staff_size = c.size
    return CompanyIntel(
        customer_id=c.id,
        provider=p.name,
        demo=p.demo,
        notice="按客户名生成，不是真实的工商、舆情或招投标信息" if p.demo else None,
        profile=profile,
        news=news,
        tenders=tenders,
        risks=risks,
        signals=_signals(news, tenders, local_today()),
    )
