"""System prompt：通用约束（§6.3）+ 当前行业包的 prompts.md；学习问答模式用 learn.md。"""

from pathlib import Path

from app.common.auth import Role
from app.packs.registry import list_packs

SYSTEM_FILE = Path(__file__).with_name("system.md")
LEARN_FILE = Path(__file__).with_name("learn.md")

SAMPLE_NOTICE = """
## 示例资料
当前系统里的产品目录价格和知识库文档是演示用的示例资料，还没有换成公司真实资料。
回答开头先提醒一次：「以下内容来自系统内置的示例资料，用于熟悉业务和系统，具体以公司实际为准。」
""".strip()


def system_prompt(pack_id: str | None = None) -> str:
    text = SYSTEM_FILE.read_text(encoding="utf-8")
    pack = list_packs().get(pack_id or "")
    if pack and pack.prompts_file.exists():
        text += "\n\n" + pack.prompts_file.read_text(encoding="utf-8")
    return text


def learn_prompt() -> str:
    text = LEARN_FILE.read_text(encoding="utf-8")
    if any(p.sample_data for p in list_packs().values()):
        text += "\n\n" + SAMPLE_NOTICE
    return text


# 各角色能做什么、做不了时找谁：工具已按角色过滤，这里让模型解释限制时说对人，
# 不建议当前角色做不了的操作（例如管理员只读，却建议「手动修改或联系管理员」）
ROLE_LIMITS: dict[Role, str] = {
    Role.SALES: (
        "销售只能查看和操作自己负责的客户与单据，不能审批、不能登记回款；"
        "需要审批、转移客户负责人或处理别人的单子时，建议找团队主管"
        "，不要建议找管理员（管理员不处理这类业务操作）。"
    ),
    Role.MANAGER: (
        "主管可以查看和处理本团队的客户与单据，负责审批报价、报销和登记回款；"
        "主管不能审批自己提交的单子。转移客户负责人在「客户」页勾选客户后批量转移"
        "（对话里做不了，指引用户去页面操作，不要说要找管理员）；"
        "账号与密码、行业包价格、业务规则这类全公司配置由管理员在设置页维护。"
    ),
    Role.ADMIN: (
        "管理员在对话里只能查询业务数据，不能修改客户、商机、报价、报销。"
        "用户要求修改时，说明管理员账号对业务数据是只读的，建议联系这一单的负责销售或其团队主管处理；"
        "不要建议用户自己手动修改，也不要建议「联系管理员」（当前用户就是管理员）。"
        "管理员负责的配置在设置页操作（指引到对应页面，"
        "不要说管理员没有权限，也不要建议找 IT）：成员与团队（新建账号、停用、重置密码）、"
        "产品与定价（行业包价格、知识库）、业务规则（毛利底线、招待标准等）、模型接入。"
        "管理员不能提交报销：用户要报销时第一句就说明，不要先追问报销信息。"
        "解释原因时只说账号权限，不要提「工具」「写工具」这类系统内部的说法。"
    ),
}


def role_limits(role: Role) -> str:
    return ROLE_LIMITS.get(role, "")
