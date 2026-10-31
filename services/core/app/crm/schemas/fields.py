"""通用字段校验：页面、批量导入、AI 写入共用同一套规则。

- 名称类必填字段：去掉首尾空格后不能为空（只填空格的「空名称」会被拒绝）
- 电话：去掉首尾空格；空串视为没填；要像电话号码（数字、+、空格、横线、括号，可带分机）
- 发生日期：不能晚于今天（北京时间）
- 网站：只接受 http / https 地址（javascript:、data: 等一律拒绝）；只写域名的补成 https://
"""

import re
from datetime import date
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, BeforeValidator, Field

from app.crm.services.codes import local_today

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
