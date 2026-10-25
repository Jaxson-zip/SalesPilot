"""统一响应、错误处理、请求 ID、JWT。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from app.common.auth import Role, decode_token, issue_token
from app.common.errors import BizError, ErrorCode, http_status_of
from app.common.request_id import RequestIdMiddleware
from app.common.response import ApiResponse, ok, register_exception_handlers
from app.crm.services.demo import DEMO_USERS


class Body(BaseModel):
    n: int


def make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    @app.get("/ok")
    def _ok() -> ApiResponse[dict[str, int]]:
        return ok({"a": 1})

    @app.get("/biz")
    def _biz() -> None:
        raise BizError(ErrorCode.RULE_VIOLATION, "毛利不足", {"rule": "margin"})

    @app.post("/body")
    def _body(body: Body) -> ApiResponse[int]:
        return ok(body.n)

    @app.get("/boom")
    def _boom() -> None:
        raise RuntimeError("boom")

    @app.get("/db")
    def _db() -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    return app


@pytest.fixture
def api() -> TestClient:
    return TestClient(make_app(), raise_server_exceptions=False)


def test_ok_envelope_and_request_id(api: TestClient) -> None:
    r = api.get("/ok", headers={"X-Request-ID": "req_abc"})
    assert r.status_code == 200
    assert r.json() == {"code": 0, "message": "ok", "data": {"a": 1}, "request_id": "req_abc"}
    assert r.headers["X-Request-ID"] == "req_abc"


def test_request_id_generated(api: TestClient) -> None:
    r = api.get("/ok")
    assert r.json()["request_id"].startswith("req_")
    assert r.headers["X-Request-ID"] == r.json()["request_id"]


def test_biz_error(api: TestClient) -> None:
    r = api.get("/biz")
    assert r.status_code == 422
    assert r.json()["code"] == 42201 and r.json()["data"] == {"rule": "margin"}


def test_validation_error(api: TestClient) -> None:
    r = api.post("/body", json={"n": "x"})
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == 40001 and body["data"]["errors"][0]["loc"][-1] == "n"


def test_not_found_route(api: TestClient) -> None:
    r = api.get("/nope")
    assert r.status_code == 404 and r.json()["code"] == 40401


def test_unhandled_error(api: TestClient) -> None:
    r = api.get("/boom", headers={"X-Request-ID": "req_boom"})
    assert r.status_code == 500
    assert r.json()["code"] == 50001 and r.json()["request_id"] == "req_boom"


def test_db_unavailable(api: TestClient) -> None:
    r = api.get("/db")
    assert r.status_code == 500
    assert r.json()["code"] == 50001 and "数据库不可用" in r.json()["message"]


def test_malformed_json(api: TestClient) -> None:
    r = api.post("/body", content=b"{bad", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["code"] == 40001


@pytest.mark.parametrize(
    ("code", "status"), [(0, 200), (40001, 400), (40101, 401), (40901, 409), (50101, 501)]
)
def test_http_status_of(code: int, status: int) -> None:
    assert http_status_of(code) == status


def test_biz_error_default_message() -> None:
    assert BizError(ErrorCode.NOT_IMPLEMENTED).message == "未实现"


class TestJwt:
    def test_roundtrip(self) -> None:
        user = DEMO_USERS[Role.MANAGER]
        assert decode_token(issue_token(user)) == user

    def test_invalid(self) -> None:
        with pytest.raises(BizError) as exc:
            decode_token("not-a-token")
        assert exc.value.code == 40101

    def test_expired(self) -> None:
        token = issue_token(DEMO_USERS[Role.SALES], expire_minutes=-1)
        with pytest.raises(BizError):
            decode_token(token)
