"""列表服务端分页 / 筛选 / 排序 / 筛选项：只读演示数据。

做法：先不带筛选取全量（演示数据不超过 100 条），再逐个筛选断言服务端结果与「对全量按同样规则过滤」
一致——这正是原来前端做的事，改到服务端后行为不能变。
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H

Row = dict[str, Any]


def _get(client: TestClient, path: str, headers: dict[str, str], **params: Any) -> Any:
    r = client.get(path, params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _all(client: TestClient, path: str, headers: dict[str, str], **params: Any) -> list[Row]:
    data = _get(client, path, headers, page_size=100, **params)
    assert data["total"] <= 100, "演示数据超过一页，测试前提不成立"
    return data["items"]


def _ids(rows: list[Row]) -> list[str]:
    return [r["id"] for r in rows]


def _owner(r: Row) -> str | None:
    return r["owner"]["id"] if r.get("owner") else None


def _customer(r: Row) -> str | None:
    return r["customer"]["id"] if r.get("customer") else None


def test_customer_filters_match_full_list(client: TestClient) -> None:
    full = _all(client, "/api/customers", ADMIN_H, view="all")
    assert full
    level = {(c["level"] or "").strip()[:1].upper() for c in full} - {""}
    for grade in level:
        got = _all(client, "/api/customers", ADMIN_H, view="all", level=[grade])
        want = [c for c in full if (c["level"] or "").strip()[:1].upper() == grade]
        assert sorted(_ids(got)) == sorted(_ids(want))
    industries = {c["industry"] for c in full if c["industry"]}
    one = sorted(industries)[:2]
    got = _all(client, "/api/customers", ADMIN_H, view="all", industry=one)
    assert sorted(_ids(got)) == sorted(c["id"] for c in full if c["industry"] in one)
    owners = {_owner(c) for c in full} - {None}
    owner = sorted(owners)[0]
    got = _all(client, "/api/customers", ADMIN_H, view="all", owner_id=[owner])
    assert sorted(_ids(got)) == sorted(c["id"] for c in full if _owner(c) == owner)
    # 不同字段之间为「且」
    both = _all(client, "/api/customers", ADMIN_H, view="all", owner_id=[owner], industry=one)
    assert sorted(_ids(both)) == sorted(
        c["id"] for c in full if _owner(c) == owner and c["industry"] in one
    )


def test_customer_facets_cover_scope(client: TestClient) -> None:
    full = _all(client, "/api/customers", SALES_H, view="mine")
    facets = _get(client, "/api/customers/facets", SALES_H, view="mine")
    assert {o["value"] for o in facets["industry"]} == {
        c["industry"] for c in full if c["industry"]
    }
    assert {o["value"] for o in facets["owner"]} == {_owner(c) for c in full} - {None}
    # 销售只能看到自己的客户：负责人筛选项只有本人
    assert len(facets["owner"]) <= 1


def test_pagination_is_stable_and_complete(client: TestClient) -> None:
    for sort in ("default", "updated", "amount_desc", "amount_asc"):
        full = _all(client, "/api/customers", ADMIN_H, view="all", sort=sort)
        pages: list[Row] = []
        page = 1
        while True:
            data = _get(
                client, "/api/customers", ADMIN_H, view="all", sort=sort, page=page, page_size=3
            )
            assert data["total"] == len(full)
            if not data["items"]:
                break
            pages += data["items"]
            page += 1
        assert _ids(pages) == _ids(full), sort  # 翻页不重复、不遗漏，顺序与一次取全一致


def test_sort_by_amount_and_updated(client: TestClient) -> None:
    desc = _all(client, "/api/customers", ADMIN_H, view="all", sort="amount_desc")
    amounts = [c["opportunity_amount"] for c in desc]
    assert amounts == sorted(amounts, reverse=True)
    asc = _all(client, "/api/quotes", ADMIN_H, view="all", sort="amount_asc")
    prices = [q["total_price"] for q in asc]
    assert prices == sorted(prices)
    upd = _all(client, "/api/customers", ADMIN_H, view="all", sort="updated")
    times = [c["last_followup_at"] for c in upd]
    present = [t for t in times if t]
    assert present == sorted(present, reverse=True)
    assert times[: len(present)] == present  # 没有跟进的排在最后


def test_quote_filters_match_full_list(client: TestClient) -> None:
    full = _all(client, "/api/quotes", MANAGER_H, view="team")
    assert full
    statuses = sorted({q["status"] for q in full})
    got = _all(client, "/api/quotes", MANAGER_H, view="team", status_in=statuses[:2])
    assert sorted(_ids(got)) == sorted(q["id"] for q in full if q["status"] in statuses[:2])
    for source in ("agent", "manual"):
        got = _all(client, "/api/quotes", MANAGER_H, view="team", source=[source])
        assert sorted(_ids(got)) == sorted(q["id"] for q in full if q["source"] == source)
    facets = _get(client, "/api/quotes/facets", MANAGER_H, view="team")
    assert {o["value"] for o in facets["pack"]} == {q["pack"] for q in full}
    assert {o["value"] for o in facets["customer"]} == {_customer(q) for q in full} - {None}
    pack = facets["pack"][0]["value"]
    got = _all(client, "/api/quotes", MANAGER_H, view="team", pack=[pack])
    assert sorted(_ids(got)) == sorted(q["id"] for q in full if q["pack"] == pack)
    customer = facets["customer"][0]["value"]
    got = _all(client, "/api/quotes", MANAGER_H, view="team", customer_in=[customer])
    assert sorted(_ids(got)) == sorted(q["id"] for q in full if _customer(q) == customer)


def test_tab_status_and_filter_status_both_apply(client: TestClient) -> None:
    full = _all(client, "/api/quotes", MANAGER_H, view="team")
    status = full[0]["status"]
    other = next((q["status"] for q in full if q["status"] != status), None)
    if other is None:
        pytest.skip("演示报价只有一种状态")
    data = _get(client, "/api/quotes", MANAGER_H, view="team", status=status, status_in=[other])
    assert data["total"] == 0


def test_contract_filters_match_full_list(client: TestClient) -> None:
    data = _get(client, "/api/contracts", MANAGER_H, view="team", page_size=100)
    full = data["items"]
    assert full
    for flag in ("overdue", "ok"):
        got = _all(client, "/api/contracts", MANAGER_H, view="team", overdue=[flag])
        want = [c for c in full if (c["overdue_amount"] > 0) == (flag == "overdue")]
        assert sorted(_ids(got)) == sorted(_ids(want)), flag
    both = _all(client, "/api/contracts", MANAGER_H, view="team", overdue=["overdue", "ok"])
    assert len(both) == len(full)
    facets = _get(client, "/api/contracts/facets", MANAGER_H, view="team")
    assert {o["value"] for o in facets["owner"]} == {_owner(c) for c in full} - {None}
    owner = facets["owner"][0]["value"]
    got = _all(client, "/api/contracts", MANAGER_H, view="team", owner_in=[owner])
    assert sorted(_ids(got)) == sorted(c["id"] for c in full if _owner(c) == owner)
    # 筛选不影响顶部汇总
    filtered = _get(client, "/api/contracts", MANAGER_H, view="team", owner_in=[owner])
    assert filtered["summary"] == data["summary"]


def test_expense_filters_match_full_list(client: TestClient) -> None:
    full = _all(client, "/api/expenses", MANAGER_H, view="team")
    assert full
    for flag in ("yes", "no"):
        got = _all(client, "/api/expenses", MANAGER_H, view="team", over=[flag])
        want = [e for e in full if e["over_limit"] == (flag == "yes")]
        assert sorted(_ids(got)) == sorted(_ids(want)), flag
    types = sorted({e["type"] for e in full})
    got = _all(client, "/api/expenses", MANAGER_H, view="team", type=types[:1])
    assert sorted(_ids(got)) == sorted(e["id"] for e in full if e["type"] == types[0])


def test_pool_accepts_filters(client: TestClient) -> None:
    full = _all(client, "/api/customers/pool", SALES_H)
    facets = _get(client, "/api/customers/facets", SALES_H, pool=True)
    assert set(facets) == {"industry"}
    assert {o["value"] for o in facets["industry"]} == {
        c["industry"] for c in full if c["industry"]
    }
    got = _all(client, "/api/customers/pool", SALES_H, level=["Z"])
    assert got == []


def test_bad_filter_values_are_rejected(client: TestClient) -> None:
    r = client.get("/api/customers?owner_id=not-a-uuid", headers=ADMIN_H)
    assert r.status_code == 400
    r = client.get("/api/quotes?sort=random", headers=ADMIN_H)
    assert r.status_code == 400
