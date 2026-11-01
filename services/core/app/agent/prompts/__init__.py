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
        "需要审批或处理别人的单子时，建议找团队主管。"
    ),
    Role.MANAGER: (
        "主管可以查看和处理本团队的客户与单据，负责审批报价、报销和登记回款；"
        "账号、行业包价格、业务规则这类全公司配置由管理员维护。"
    ),
    Role.ADMIN: (
        "管理员在对话里只能查询业务数据，不能修改客户、商机、报价、报销（没有这些写工具）。"
        "用户要求修改时，说明管理员账号对业务数据是只读的，建议联系这一单的负责销售或其团队主管处理；"
        "不要建议用户自己手动修改，也不要建议「联系管理员」（当前用户就是管理员）。"
        "管理员负责的是成员与团队、行业包与价格、业务规则、模型接入等配置页面。"
    ),
}


def role_limits(role: Role) -> str:
    return ROLE_LIMITS.get(role, "")
