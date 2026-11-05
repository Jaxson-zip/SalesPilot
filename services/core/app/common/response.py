"""统一响应 {code, message, data, request_id} 与全局异常处理器。"""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import DataError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.errors import BizError, ErrorCode, http_status_of
from app.common.request_id import get_request_id

logger = logging.getLogger("core")


class ApiResponse[T](BaseModel):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    request_id: str = ""


def ok[T](data: T = None) -> ApiResponse[T]:
    return ApiResponse[T](data=data, request_id=get_request_id())


def error_body(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": jsonable_encoder(data),
        "request_id": get_request_id(),
    }


def error_response(code: int, message: str, data: Any = None) -> JSONResponse:
    return JSONResponse(status_code=http_status_of(code), content=error_body(code, message, data))


async def _biz_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, BizError)
    return error_response(exc.code, exc.message, exc.data)


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [{"loc": [str(p) for p in e.get("loc", ())], "msg": _msg(e)} for e in exc.errors()]
    # 自己写的中文校验（「客户名称不能为空」）直接当提示语，前端不用再拼字段名
    own = next((e["msg"] for e in errors if _is_chinese(e["msg"])), None)
    return error_response(ErrorCode.VALIDATION, own or "参数校验失败", {"errors": errors})


def _msg(e: Mapping[str, Any]) -> str:
    msg = str(e.get("msg", ""))
    return msg.removeprefix("Value error, ") if e.get("type") == "value_error" else msg


def _is_chinese(text: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in text)


_HTTP_TO_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.NOT_FOUND,
    422: ErrorCode.VALIDATION,
}


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL)
    return error_response(code, str(exc.detail))


async def _db_unavailable_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("database unavailable request_id=%s: %s", get_request_id(), exc)
    return error_response(ErrorCode.INTERNAL, "数据库不可用，请稍后重试")


async def _bad_data_handler(_: Request, exc: Exception) -> JSONResponse:
    """数据库拒收的输入（NUL 控制字符、数值超出范围、格式不对）：是输入的问题 → 40001，不是 500。"""
    text = str(getattr(exc, "orig", exc)).splitlines()[0][:200]
    logger.info("input rejected by database request_id=%s: %s", get_request_id(), text)
    if "NUL" in text:
        return error_response(ErrorCode.VALIDATION, "内容里有不可见的控制字符，请删除后重试")
    return error_response(ErrorCode.VALIDATION, "数据格式不对或数值超出范围，请检查后重试")


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # 500 处理器位于最外层中间件，contextvar 已复位，从 request.state 取请求 ID
    rid = getattr(request.state, "request_id", "") or get_request_id()
    logger.exception("unhandled error request_id=%s", rid, exc_info=exc)
    body = error_body(ErrorCode.INTERNAL, "内部错误")
    body["request_id"] = rid
    return JSONResponse(status_code=500, content=body, headers={"X-Request-ID": rid})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BizError, _biz_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(OperationalError, _db_unavailable_handler)
    app.add_exception_handler(DataError, _bad_data_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
