"""错误统一：差异 #13。"""

from __future__ import annotations

from typing import Any

import pytest

from app.compat.errors import (
    GatewayError,
    aggregate_errors,
    classify_exception,
    error_body,
    should_failover,
)
from tests.fakes import load_fixture, upstream_error

CASES: list[dict[str, Any]] = load_fixture("upstream_errors.synthetic.json")["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["exc"] for c in CASES])
def test_diff13_upstream_errors_mapped(case: dict[str, Any]) -> None:
    err = classify_exception(upstream_error(case["exc"], case["status"], case["message"]))
    assert (err.status, err.code) == (case["expect_status"], case["expect_code"])


def test_diff13_builtin_timeout_mapped() -> None:
    err = classify_exception(TimeoutError("timed out"))
    assert (err.status, err.gateway_code) == (504, 50401)


def test_error_body_is_openai_shape() -> None:
    body = error_body(GatewayError(429, 42901, "slow down", "rate_limit_error", "rate_limit_exceeded"))
    assert body == {
        "error": {
            "message": "slow down",
            "type": "rate_limit_error",
            "param": None,
            "code": "rate_limit_exceeded",
            "gateway_code": 42901,
        }
    }


def _err(status: int, code: str) -> GatewayError:
    return GatewayError(status, 0, "x", code=code)


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([(429, "rate_limit_exceeded"), (429, "rate_limit_exceeded")], (429, 42901)),
        ([(504, "timeout"), (504, "timeout")], (504, 50401)),
        ([(429, "rate_limit_exceeded"), (502, "upstream_error")], (502, 50201)),
    ],
)
def test_group_errors_aggregated(statuses: list[tuple[int, str]], expected: tuple[int, int]) -> None:
    attempts = [(f"m{i}", _err(s, c)) for i, (s, c) in enumerate(statuses)]
    err = aggregate_errors(attempts, is_group=True)
    assert (err.status, err.gateway_code) == expected
    assert len(err.details) == len(statuses)


def test_single_model_error_passthrough_and_failover_policy() -> None:
    original = _err(401, "upstream_auth")
    assert aggregate_errors([("m", original)], is_group=False) is original
    assert should_failover(original)
    assert not should_failover(_err(400, "content_filter"))


@pytest.mark.parametrize(
    ("exc", "status", "message"),
    [
        ("BadRequestError", 402, "Insufficient Balance (request_id: x)"),
        (
            "BadRequestError",
            400,
            "Arrearage: Access denied, please make sure your account is in good standing.",
        ),
    ],
)
def test_insufficient_balance_is_not_bad_request(exc: str, status: int, message: str) -> None:
    err = classify_exception(upstream_error(exc, status, message))
    assert (err.status, err.code) == (502, "insufficient_balance")
    assert should_failover(err)
