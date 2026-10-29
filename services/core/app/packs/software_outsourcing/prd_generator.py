"""PRD 规格书：按需求清单生成 Markdown。

章节：项目背景、范围、角色权限、模块用例、数据结构、非功能、验收。

- skeleton：只用需求清单拼出的模板版，模型不可用时直接用它；
- messages：交给模型扩写的提示词（保留章节和模块清单，不写价格，推测的内容标「待确认」）。
PRD 不写任何金额：价格只来自报价引擎。
"""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.packs.software_outsourcing.requirement import (
    COMPLEXITY_NAMES,
    PLATFORM_NAMES,
    Module,
    SoftwareRequirement,
)

DRAFT_NOTE = "> AI 生成的草案，模块用例、数据结构和验收指标需与客户逐项确认后再作为开发依据。"
TEMPLATE_NOTE = "> 按需求清单生成的模板版（AI 暂不可用），标「待确认」的部分需要和客户补充。"

PROMPT = """
你是资深软件产品经理，为软件外包项目写需求规格说明书（PRD），读者是客户和开发团队。

要求：
- 以给出的「模板版 PRD」为骨架扩写：保留全部章节标题和顺序，
  模块清单、交付端、首期 / 二期划分不能增删改。
- 第 4 章逐个模块写：功能说明、主要用例（角色 → 操作 → 结果）、业务规则、异常与边界情况、验收要点。
- 第 3 章给出角色 × 模块的权限矩阵（Markdown 表格，可用 ✓ / 只读 / —）。
- 第 5 章给出主要数据实体和关键字段（表格：实体、字段、说明），只写业务字段。
- 第 6 章写可量化的指标（例如页面响应 ≤ 2 秒、可用性、数据备份、安全要求）。
- 不写任何价格、费用、人天和报价；工期只引用需求里给出的期望工期。
- 需求里没有、由你根据行业常识推测的内容，在句末标「（待确认）」。
- 只输出 Markdown 正文，不要代码块包裹，不要开场白和结束语；控制在 4000 字以内。
""".strip()


def _roles(r: SoftwareRequirement) -> list[str]:
    clients = [p for p in r.platforms if p != "admin"]
    roles = ["终端用户（客户的顾客 / 员工）"] if clients else []
    if "admin" in r.platforms or not clients:
        roles += ["运营管理员", "系统管理员"]
    return roles


def _module_row(m: Module) -> str:
    phase = "首期" if m.must else "二期"
    origin = "客户提出" if m.source == "mentioned" else "建议补充（待确认）"
    return f"| {m.name} | {COMPLEXITY_NAMES.get(m.complexity, m.complexity)} | {phase} | {origin} |"


def skeleton(r: SoftwareRequirement, *, title: str, customer: str, confirmed: bool) -> str:
    """只用需求清单拼出的模板版 PRD（不调模型）。"""
    platforms = "、".join(PLATFORM_NAMES.get(p, p) for p in r.platforms)
    status = "已与客户确认" if confirmed else "待与客户确认"
    roles = _roles(r)
    first = [m for m in r.modules if m.must]
    later = [m for m in r.modules if not m.must]
    lines = [
        f"# {title} 需求规格说明书",
        "",
        TEMPLATE_NOTE,
        "",
        f"- 客户：{customer}",
        f"- 需求清单状态：{status}",
        f"- 交付端：{platforms}",
    ]
    if r.deadline_weeks:
        lines.append(f"- 期望工期：{r.deadline_weeks} 周")
    lines += [
        "",
        "## 1 项目背景与目标",
        "",
        f"{r.project or title}。项目目标与业务痛点（待确认）。",
        "",
        "## 2 交付范围",
        "",
        "| 模块 | 复杂度 | 阶段 | 来源 |",
        "|---|---|---|---|",
        *[_module_row(m) for m in r.modules],
        "",
        f"首期上线 {len(first)} 个模块" + (f"，二期 {len(later)} 个模块。" if later else "。"),
        "不在本期范围：上表以外的功能、与第三方系统的对接（除非上表列出）。",
        "",
        "## 3 角色与权限",
        "",
        "| 模块 | " + " | ".join(roles) + " |",
        "|---|" + "---|" * len(roles),
        *[f"| {m.name} | " + " | ".join("待确认" for _ in roles) + " |" for m in r.modules],
        "",
        "## 4 模块详细用例规格",
        "",
    ]
    for i, m in enumerate(r.modules, 1):
        lines += [
            f"### 4.{i} {m.name}",
            "",
            "- 功能说明：待确认",
            "- 主要用例：待确认",
            "- 业务规则与异常：待确认",
            "- 验收要点：主流程可走通，异常有提示（待确认）",
            "",
        ]
    lines += [
        "## 5 数据结构草案",
        "",
        "主要数据实体与字段在需求确认后补充（待确认）。",
        "",
        "## 6 非功能性需求",
        "",
        "- 性能：常用页面响应 ≤ 2 秒（待确认并发量）",
        "- 安全：全站 HTTPS，账号密码加密存储，按角色控制权限",
        "- 可靠性：数据每日备份，保留 7 天（待确认）",
        f"- 兼容性：{platforms}的主流版本",
        "",
        "## 7 验收标准与里程碑",
        "",
        "- 按第 2 章首期模块逐项验收，第 4 章验收要点全部通过",
        "- 里程碑：原型确认 → 开发完成 → 测试验收 → 上线（时间待确认）",
    ]
    if r.questions:
        lines += ["", "## 8 待确认问题", "", *[f"- {q}" for q in r.questions]]
    return "\n".join(lines) + "\n"


def messages(r: SoftwareRequirement, template: str) -> list[BaseMessage]:
    facts = r.model_dump_json(exclude={"samples", "budget"}, exclude_none=True)
    human = f"需求清单（JSON）：\n{facts}\n\n模板版 PRD：\n{template}"
    return [SystemMessage(PROMPT), HumanMessage(human)]


def finalize(text: str) -> str:
    """模型输出：去掉误加的代码块围栏，把模板说明换成草案说明（没有就补在标题下）。"""
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1] if "\n" in body else ""
        body = body.removesuffix("```").rstrip()
    body = body.replace(TEMPLATE_NOTE, DRAFT_NOTE)
    if DRAFT_NOTE not in body:
        head, _, rest = body.partition("\n")
        body = (
            f"{head}\n\n{DRAFT_NOTE}\n{rest}" if head.startswith("#") else f"{DRAFT_NOTE}\n\n{body}"
        )
    return body + "\n"
