"""企业办公 IT 需求 schema：按岗位人数配置电脑。"""

from pydantic import BaseModel, Field, model_validator


class ItOfficeRequirement(BaseModel):
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
