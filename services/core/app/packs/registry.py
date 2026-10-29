"""行业包注册表：扫描 packs/<id>/pack.yaml，按 pack_id 加载配置器。

新增行业只需要在 packs/ 下新建目录，不改 agent 和 crm 的代码。
"""

import importlib
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.common.errors import BizError, ErrorCode
from app.packs.base import Configurator

PACKS_DIR = Path(__file__).parent


class PackInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    # 产品目录价格和知识库是演示用的示例资料：页面标「示例」，AI 回答时说明；
    # 换成真实资料后在 pack.yaml 里改为 false
    sample_data: bool = False
    path: Path

    @property
    def knowledge_dir(self) -> Path:
        return self.path / "knowledge"

    @property
    def rules_file(self) -> Path:
        return self.path / "rules.yaml"

    @property
    def prompts_file(self) -> Path:
        return self.path / "prompts.md"


@lru_cache
def list_packs() -> dict[str, PackInfo]:
    packs: dict[str, PackInfo] = {}
    for manifest in sorted(PACKS_DIR.glob("*/pack.yaml")):
        raw = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        info = PackInfo(path=manifest.parent, **raw)
        packs[info.id] = info
    return packs


def get_pack(pack_id: str) -> PackInfo:
    pack = list_packs().get(pack_id)
    if pack is None:
        raise BizError(ErrorCode.NOT_FOUND, f"行业包不存在：{pack_id}")
    return pack


@lru_cache
def get_configurator(pack_id: str) -> Configurator:
    """约定：packs/<id>/configurator.py 暴露 create_configurator() -> Configurator。"""
    get_pack(pack_id)
    module = importlib.import_module(f"app.packs.{pack_id}.configurator")
    configurator = module.create_configurator()
    if not isinstance(configurator, Configurator):
        raise BizError(ErrorCode.INTERNAL, f"行业包 {pack_id} 的配置器未实现 Configurator 接口")
    return configurator
