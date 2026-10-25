"""业务错误码（开发规范 §8.2）与 BizError。"""

from enum import IntEnum
from typing import Any


class ErrorCode(IntEnum):
    OK = 0
    VALIDATION = 40001
    MODEL_CAPABILITY = 40002
    UNAUTHORIZED = 40101
    FORBIDDEN = 40301
    NOT_FOUND = 40401
    DUPLICATE = 40901
    RULE_VIOLATION = 42201
    RATE_LIMITED = 42901
    INTERNAL = 50001
    NOT_IMPLEMENTED = 50101
    UPSTREAM = 50201
    TIMEOUT = 50401


DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.OK: "ok",
    ErrorCode.VALIDATION: "参数校验失败",
    ErrorCode.MODEL_CAPABILITY: "模型能力不匹配",
    ErrorCode.UNAUTHORIZED: "未登录或 token 失效",
    ErrorCode.FORBIDDEN: "无权限",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.DUPLICATE: "重复提交",
    ErrorCode.RULE_VIOLATION: "业务规则不满足",
    ErrorCode.RATE_LIMITED: "模型限流",
    ErrorCode.INTERNAL: "内部错误",
    ErrorCode.NOT_IMPLEMENTED: "未实现",
    ErrorCode.UPSTREAM: "模型网关上游错误",
    ErrorCode.TIMEOUT: "模型调用超时",
}


def http_status_of(code: int) -> int:
    """错误码前三位即 HTTP 状态码；0 → 200。"""
    if code == 0:
        return 200
    return int(str(code)[:3])


class BizError(Exception):
    """业务异常：由全局处理器转换为统一响应。"""

    def __init__(self, code: int, message: str | None = None, data: Any = None) -> None:
        self.code = int(code)
        try:
            default = DEFAULT_MESSAGES[ErrorCode(self.code)]
        except ValueError:
            default = "error"
        self.message = message or default
        self.data = data
        super().__init__(f"{self.code}: {self.message}")

    @property
    def http_status(self) -> int:
        return http_status_of(self.code)


def not_implemented(feature: str) -> BizError:
    return BizError(ErrorCode.NOT_IMPLEMENTED, "未实现", {"feature": feature})
