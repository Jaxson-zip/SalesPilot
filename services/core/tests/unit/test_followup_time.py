"""跟进发生时间（2026-11-03 实测「刚保存的跟进显示 15 小时前」的回归用例）。"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.crm.schemas.dashboard import FollowupIn
from app.crm.services.codes import LOCAL_TZ


def test_naive_time_is_beijing_time() -> None:
    f = FollowupIn(type="phone", content="电话沟通", occurred_at=datetime(2026, 11, 1, 9, 0))
    assert f.occurred_at == datetime(2026, 11, 1, 9, 0, tzinfo=LOCAL_TZ)


def test_future_time_rejected() -> None:
    later = datetime.now(UTC) + timedelta(hours=2)
    with pytest.raises(ValidationError, match="不能晚于现在"):
        FollowupIn(type="phone", content="电话沟通", occurred_at=later)
