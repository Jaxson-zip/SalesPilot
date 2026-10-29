"""软件外包需求 schema：项目形态 + 功能模块拆解（由大模型拆，配置器按人天定价）。"""

from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["web", "mini_program", "app", "admin"]
Complexity = Literal["simple", "medium", "complex"]

PLATFORM_NAMES: dict[str, str] = {
    "web": "网站 / H5",
    "mini_program": "微信小程序",
    "app": "App（iOS + Android）",
    "admin": "管理后台",
}
COMPLEXITY_NAMES: dict[str, str] = {"simple": "简单", "medium": "中等", "complex": "复杂"}


class Module(BaseModel):
    """一个功能模块。"""

    key: str = Field(description="标准模块 key（见说明里的模块库）；模块库没有的填 custom")
    name: str = Field(description="模块名称，例如「在线预约」「对接用友 ERP」")
    complexity: Complexity = Field(
        default="medium",
        description="复杂度：simple 简单（标准做法）/ medium 中等 / "
        "complex 复杂（规则多、定制多、对接多）",
    )
    must: bool = Field(
        default=True, description="首期必须上线为 true；客户说可以二期 / 以后再做的为 false"
    )
    source: Literal["mentioned", "inferred"] = Field(
        default="mentioned",
        description="mentioned 客户明确提到的功能；inferred 你根据业务常识推断、客户没说的功能",
    )


class SoftwareRequirement(BaseModel):
    """软件外包项目需求：交付端 + 功能模块清单。"""

    project: str | None = Field(
        default=None, description="项目一句话描述，例如「连锁门店预约小程序」"
    )
    platforms: list[Platform] = Field(
        min_length=1,
        description="要交付的端：web 网站或 H5 / mini_program 微信小程序 / "
        "app 原生 App / admin 管理后台",
    )
    modules: list[Module] = Field(min_length=1, description="功能模块拆解清单")
    deadline_weeks: int | None = Field(default=None, gt=0, le=104, description="期望工期（周）")
    budget: int | None = Field(default=None, ge=0, description="预算（分）")
    questions: list[str] = Field(
        default_factory=list,
        description="销售下次需要和客户确认的 3–5 个关键问题"
        "（针对描述里不清楚、会明显影响工作量的点，"
        "例如有几种角色、要不要对接已有系统、数据量和并发、是否分期）；每个问题一句话",
    )
    team_size: int | None = Field(
        default=None,
        ge=1,
        le=30,
        description="交付人数：销售说自己一个人做 / 个人全栈 / 独立开发时为 1；"
        "没说留空（用默认团队）",
    )


# 追问时展示给用户的字段名
FIELD_LABELS: dict[str, str] = {
    "platforms": "要做哪些端（网站 / 小程序 / App / 管理后台）",
    "modules": "主要功能（例如预约、支付、会员、数据报表）",
}
