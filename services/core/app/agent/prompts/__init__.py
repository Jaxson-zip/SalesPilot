"""System prompt：通用约束（§6.3）+ 当前行业包的 prompts.md。"""

from pathlib import Path

from app.packs.registry import list_packs

SYSTEM_FILE = Path(__file__).with_name("system.md")


def system_prompt(pack_id: str | None = None) -> str:
    text = SYSTEM_FILE.read_text(encoding="utf-8")
    pack = list_packs().get(pack_id or "")
    if pack and pack.prompts_file.exists():
        text += "\n\n" + pack.prompts_file.read_text(encoding="utf-8")
    return text
