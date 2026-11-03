"""通用字段校验：页面、批量导入、AI 写入共用同一套规则。

- 名称类必填字段：去掉首尾空格后不能为空（只填空格的「空名称」会被拒绝）
- 电话：去掉首尾空格；空串视为没填；要像电话号码（数字、+、空格、横线、括号，可带分机）
- 发生日期：不能晚于今天（北京时间）；发生时间不能晚于现在
- 时间不带时区时按北京时间理解（原来按 UTC，「当天 00:00」存成了北京时间 08:00）
- 网站：只接受 http / https 地址（javascript:、data: 等一律拒绝）；只写域名的补成 https://
- 金额：不超过 100 亿元（多打了几个 0、以及超出数据库 bigint 时返回 500 的问题）
- 计划日期（预计成交、任务截止）：2000 年以后、今天起 10 年以内（防 1900、2999 这类误填）
"""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, BeforeValidator, Field

from app.crm.services.codes import LOCAL_TZ, local_today

# 手机 13800138000、+86 138 0013 8000、座机 0755-12345678、(010)12345678、400-800-1234 转 123
_PHONE = re.compile(
    r"^\+?[\d\s()（）\-－]+(?:\s*(?:转|分机|ext\.?|#|,)\s*\d{1,6})?$", re.IGNORECASE
)
PHONE_DIGITS = (7, 16)


def phone_error(text: str) -> str | None:
    """电话号码不合格时返回原因，合格返回 None（批量导入逐行报错用）。"""
    main = re.split(r"转|分机|ext|#|,", text, maxsplit=1, flags=re.IGNORECASE)[0]
    digits = sum(c.isdigit() for c in main)
    if not _PHONE.match(text) or not PHONE_DIGITS[0] <= digits <= PHONE_DIGITS[1]:
        return "电话格式不对，请填手机号或座机号（如 13800138000、0755-12345678）"
    return None


def _required(label: str) -> AfterValidator:
    def check(v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError(f"{label}不能为空")
        return v

    return AfterValidator(check)


CustomerName = Annotated[str, _required("客户名称"), Field(max_length=200)]
ContactName = Annotated[str, _required("联系人姓名"), Field(max_length=50)]
ExpenseReason = Annotated[str, _required("事由"), Field(max_length=500)]
OpportunityName = Annotated[str, _required("商机名称"), Field(max_length=200)]
PersonName = Annotated[str, _required("姓名"), Field(max_length=50)]
TeamName = Annotated[str, _required("团队名称"), Field(max_length=100)]
PlanName = Annotated[str, _required("期次名称"), Field(max_length=30)]
ItemName = Annotated[str, _required("费用名称"), Field(max_length=200)]


def _blank_to_none(v: object) -> object:
    return v.strip() or None if isinstance(v, str) else v


def _phone(v: str | None) -> str | None:
    if v is not None and (err := phone_error(v)):
        raise ValueError(err)
    return v


def _phone_or_masked(v: str | None) -> str | None:
    # 编辑表单原样提交的脱敏号码（139****2222）：服务层会忽略，不改电话
    return v if v is not None and "*" in v else _phone(v)


_PhoneText = Annotated[str, Field(max_length=30)] | None
Phone = Annotated[_PhoneText, BeforeValidator(_blank_to_none), AfterValidator(_phone)]
PhoneOrMasked = Annotated[
    _PhoneText, BeforeValidator(_blank_to_none), AfterValidator(_phone_or_masked)
]


def _not_future(v: date | None) -> date | None:
    if v is not None and v > local_today():
        raise ValueError("发生日期不能晚于今天")
    return v


PastDate = Annotated[date, AfterValidator(_not_future)]


def _local(v: datetime | None) -> datetime | None:
    return v.replace(tzinfo=LOCAL_TZ) if v is not None and v.tzinfo is None else v


def _past_time(v: datetime | None) -> datetime | None:
    v = _local(v)
    # 允许几分钟误差：浏览器和服务器的时钟不完全一致
    if v is not None and v > datetime.now(UTC) + timedelta(minutes=10):
        raise ValueError("发生时间不能晚于现在")
    return v


PastTime = Annotated[datetime, AfterValidator(_past_time)]

MAX_AMOUNT_FEN = 10**12  # 100 亿元


def _amount(v: int | None) -> int | None:
    if v is not None and v > MAX_AMOUNT_FEN:
        raise ValueError("金额不能超过 100 亿元，请检查是否多填了几个 0")
    return v


Amount = Annotated[int, Field(ge=0), AfterValidator(_amount)]
PositiveAmount = Annotated[int, Field(gt=0), AfterValidator(_amount)]

PLAN_YEARS = 10


def _plan_day(v: date) -> date:
    today = local_today()
    if v < date(2000, 1, 1) or v > today.replace(year=today.year + PLAN_YEARS):
        raise ValueError(f"日期不合理：要在 2000 年以后、{PLAN_YEARS} 年以内")
    return v


def _plan_date(v: date | None) -> date | None:
    return None if v is None else _plan_day(v)


def _plan_time(v: datetime | None) -> datetime | None:
    v = _local(v)
    if v is not None:
        _plan_day(v.date())
    return v


PlanDate = Annotated[date, AfterValidator(_plan_date)]
PlanTime = Annotated[datetime, AfterValidator(_plan_time)]
TaskTitle = Annotated[str, _required("任务标题"), Field(max_length=200)]


_BARE_DOMAIN = re.compile(r"^[\w-]+(?:\.[\w-]+)+(?::\d+)?(?:[/?#]\S*)?$")
WEBSITE_ERROR = "网站地址要以 http:// 或 https:// 开头，例如 https://example.com"


def normalize_website(text: str) -> str | None:
    """合法时返回规范化的地址（只写域名的补 https://），不合法返回 None。"""
    v = text.strip()
    if "://" not in v and _BARE_DOMAIN.match(v):
        v = f"https://{v}"
    if any(c.isspace() or ord(c) < 32 for c in v):
        return None
    try:
        parts = urlsplit(v)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    return v


def _website(v: str | None) -> str | None:
    if v is None:
        return None
    if (url := normalize_website(v)) is None:
        raise ValueError(WEBSITE_ERROR)
    return url


Website = Annotated[
    Annotated[str, Field(max_length=200)] | None,
    BeforeValidator(_blank_to_none),
    AfterValidator(_website),
]
