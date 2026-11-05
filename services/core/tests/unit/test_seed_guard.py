"""seed --reset 必须明确确认（回归：线上照文档跑了 --reset，试用者录入的报销全部消失）。"""

from unittest.mock import MagicMock

import pytest

from seed import guard


@pytest.fixture
def db() -> MagicMock:
    session = MagicMock()
    session.execute.return_value.scalar_one.return_value = 6
    return session


def test_yes_flag_skips_prompt(db: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
    assert guard.confirm_reset(db, assume_yes=True, interactive=False)
    assert "报销单 6" in capsys.readouterr().out


def test_non_interactive_without_yes_refuses(db: MagicMock) -> None:
    assert not guard.confirm_reset(db, assume_yes=False, interactive=False)


def test_interactive_requires_typing_reset(db: MagicMock) -> None:
    assert guard.confirm_reset(db, False, ask=lambda _: "RESET", interactive=True)
    assert not guard.confirm_reset(db, False, ask=lambda _: "y", interactive=True)
