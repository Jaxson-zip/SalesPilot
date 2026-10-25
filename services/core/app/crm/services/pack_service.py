"""行业包配置 service：列出已安装的行业包。

TODO: 产品线 → 行业包映射的增删改（仅 admin），启用 / 停用行业包。
"""

from pydantic import BaseModel

from app.packs.registry import list_packs


class PackOut(BaseModel):
    id: str
    name: str
    description: str
    version: str


def list_installed_packs() -> list[PackOut]:
    return [
        PackOut(id=p.id, name=p.name, description=p.description, version=p.version)
        for p in list_packs().values()
    ]
