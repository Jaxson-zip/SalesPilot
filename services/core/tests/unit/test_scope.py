"""数据范围过滤：用 SQL 编译结果断言（不连数据库）。"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.common.auth import CurrentUser, Role
from app.common.errors import BizError
from app.common.scope import View, apply_scope, can_see, ensure_visible, resolve_view
from app.crm.models import Customer
from app.crm.services.customer_service import build_list_query, rank_by_similarity
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES

SALES = DEMO_USERS[Role.SALES]
MANAGER = DEMO_USERS[Role.MANAGER]
ADMIN = DEMO_USERS[Role.ADMIN]


def compiled(stmt: object) -> tuple[str, dict[str, object]]:
    c = stmt.compile(dialect=postgresql.dialect())  # type: ignore[attr-defined]
    return str(c), dict(c.params)


def where_of(sql: str) -> str:
    return sql.split("WHERE", 1)[1] if "WHERE" in sql else ""


class TestApplyScope:
    def test_sales_filters_owner(self) -> None:
        sql, params = compiled(apply_scope(select(Customer), Customer, SALES))
        assert "customers.owner_id = " in where_of(sql)
        assert SALES.id in params.values()

    def test_manager_filters_team(self) -> None:
        sql, params = compiled(apply_scope(select(Customer), Customer, MANAGER))
        assert "customers.team_id = " in where_of(sql)
        assert MANAGER.team_id in params.values()

    def test_admin_no_filter(self) -> None:
        sql, _ = compiled(apply_scope(select(Customer), Customer, ADMIN))
        assert "WHERE" not in sql

    def test_manager_mine_view(self) -> None:
        sql, _ = compiled(apply_scope(select(Customer), Customer, MANAGER, View.MINE))
        assert "customers.owner_id = " in where_of(sql) and "team_id" not in where_of(sql)

    def test_sales_cannot_escalate_to_all(self) -> None:
        sql, _ = compiled(apply_scope(select(Customer), Customer, SALES, View.ALL))
        assert "customers.owner_id = " in where_of(sql)

    def test_manager_without_team_sees_nothing(self) -> None:
        lonely = CurrentUser(id=uuid.uuid4(), name="x", role=Role.MANAGER, team_id=None)
        sql, _ = compiled(apply_scope(select(Customer), Customer, lonely))
        assert "false" in where_of(sql).lower()


@pytest.mark.parametrize(
    ("role", "requested", "expected"),
    [
        (Role.SALES, None, View.MINE),
        (Role.SALES, View.TEAM, View.MINE),
        (Role.MANAGER, None, View.TEAM),
        (Role.MANAGER, View.MINE, View.MINE),
        (Role.ADMIN, View.TEAM, View.TEAM),
        (Role.ADMIN, None, View.ALL),
    ],
)
def test_resolve_view(role: Role, requested: View | None, expected: View) -> None:
    assert resolve_view(DEMO_USERS[role], requested) is expected


class TestVisibility:
    own = Customer(owner_id=SALES.id, team_id=SALES.team_id)
    colleague = Customer(owner_id=EXTRA_SALES.id, team_id=EXTRA_SALES.team_id)
    other_team = Customer(owner_id=uuid.uuid4(), team_id=uuid.uuid4())

    def test_sales(self) -> None:
        assert can_see(self.own, SALES)
        assert not can_see(self.colleague, SALES)  # 销售之间互相看不到

    def test_manager(self) -> None:
        assert can_see(self.colleague, MANAGER)
        assert not can_see(self.other_team, MANAGER)

    def test_admin(self) -> None:
        assert can_see(self.other_team, ADMIN)

    def test_ensure_visible_hides_existence(self) -> None:
        with pytest.raises(BizError) as exc:
            ensure_visible(self.colleague, SALES)
        assert exc.value.code == 40401
        with pytest.raises(BizError):
            ensure_visible(None, ADMIN)


def test_customer_list_query_is_scoped_and_searchable() -> None:
    sql, params = compiled(build_list_query(SALES, None, "明理"))
    where = where_of(sql)
    assert "customers.owner_id = " in where and "ILIKE" in where.upper()
    assert "%明理%" in params.values()
    assert "sum(opportunities.amount)" in sql and "max(followups.created_at)" in sql


def test_rank_by_similarity() -> None:
    names = ["深圳明理律师事务所", "华南智能制造有限公司", "星河设计工作室"]
    assert rank_by_similarity("今天和明理律所王律师通了电话", names) == ["深圳明理律师事务所"]
    assert rank_by_similarity("你好", names) == []
