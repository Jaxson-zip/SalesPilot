"""企业办公 IT 需求 schema：按岗位人数配置电脑。"""

from typing import ClassVar

from pydantic import BaseModel, Field, model_validator


class ItOfficeRequirement(BaseModel):
    # 整体校验（至少 1 个岗位人数）没过时追问的内容
    missing_hint: ClassVar[str] = "各岗位要配电脑的人数（普通办公几人、设计几人）"

    office_staff: int = Field(default=0, ge=0, le=10000, description="行政 / 普通办公人数")
    designers: int = Field(default=0, ge=0, le=10000, description="设计岗位人数")
    budget: int | None = Field(default=None, ge=0, description="预算（分）")

    @model_validator(mode="after")
    def _at_least_one(self) -> "ItOfficeRequirement":
        if self.office_staff + self.designers <= 0:
            raise ValueError("至少需要 1 个岗位人数")
        return self


FIELD_LABELS: dict[str, str] = {
    "office_staff": "普通办公人数",
    "designers": "设计岗位人数",
}
