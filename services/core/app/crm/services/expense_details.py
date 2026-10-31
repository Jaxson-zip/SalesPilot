"""报销补充信息（details）按类型校验（v4）。

- 差旅交通：实报实销，不按行程算标准，出发地 / 目的地 / 交通方式都是选填（填了就保存）；
- 差旅住宿：城市、入住日期、离店日期必填，离店晚于入住、不晚于今天，单张报销最多 60 晚；
- 客户招待 / 其他：不需要 details，传了也丢弃。
校验失败抛 40001，`data.errors[].loc` 指向字段（与参与人校验一致）。
"""

from datetime import date
from typing import Any

from app.common.errors import BizError, ErrorCode
from app.crm.schemas.finance import ExpenseDetails
from app.crm.services.codes import local_today
from app.rules.calculators import stay_nights

MAX_NIGHTS = 60
REQUIRED: dict[str, dict[str, str]] = {
    "transport": {},
    "hotel": {
        "city": "请填写住宿城市",
        "check_in": "请选择入住日期",
        "check_out": "请选择离店日期",
    },
}


def _invalid(field: str, message: str) -> BizError:
    error = {"loc": ["body", "details", field], "msg": message}
    return BizError(ErrorCode.VALIDATION, message, {"errors": [error]})


def clean_details(expense_type: str, details: ExpenseDetails | None) -> dict[str, Any] | None:
    """返回要存库的 details（JSON 可序列化）；不需要 details 的类型返回 None。"""
    required = REQUIRED.get(expense_type)
    if required is None:
        return None
    data = details.model_dump(mode="json", exclude_none=True) if details else {}
    for field, message in required.items():
        if not str(data.get(field) or "").strip():
            raise _invalid(field, message)
    if expense_type == "transport":
        data = {k: data[k] for k in ("from_city", "to_city", "transport_mode") if k in data}
        return data or None
    nights = stay_nights(data)
    if nights < 1:
        raise _invalid("check_out", "离店日期要晚于入住日期")
    if nights > MAX_NIGHTS:
        raise _invalid("check_out", f"单张报销最多 {MAX_NIGHTS} 晚，请分开报销")
    if date.fromisoformat(data["check_out"]) > local_today():
        raise _invalid("check_out", "离店日期不能晚于今天，住完再报销")
    return {k: data[k] for k in ("city", "check_in", "check_out")}
