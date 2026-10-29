"""System prompt：通用约束（§6.3）+ 当前行业包的 prompts.md；学习问答模式用 learn.md。"""

from pathlib import Path

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
