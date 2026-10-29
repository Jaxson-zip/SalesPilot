"""客户批量导入：表头识别、逐行校验、查重、负责人分配、预览不写入、导入后可清理。"""

import io
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import delete, select

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.models import Activity, Contact, Customer, Notification
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker

SALES = DEMO_USERS[Role.SALES]
MANAGER = DEMO_USERS[Role.MANAGER]
TAG = uuid.uuid4().hex[:6]  # 每次运行用不同的客户名，避免和上次残留冲突


def _csv(text: str, encoding: str = "utf-8-sig") -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("customers.csv", text.encode(encoding), "text/csv")}


def _created(tracker: Tracker) -> dict[str, Customer]:
    """按本次运行的名称标记找出导入的客户，交给 tracker 清理。"""
    with session_scope() as db:
        rows = list(db.scalars(select(Customer).where(Customer.name.like(f"%{TAG}%"))))
        for c in rows:
            db.expunge(c)
    tracker.customers += [c.id for c in rows if c.id not in tracker.customers]
    return {c.name: c for c in rows}


@pytest.fixture
def clean_notes() -> Iterator[None]:
    yield
    with session_scope() as db:
        db.execute(delete(Notification).where(Notification.title.like("% 导入了 % 个客户给你")))


def test_preview_validates_and_dedupes_without_writing(
    client: TestClient, tracker: Tracker
) -> None:
    body = (
        "客户名称*,行业,等级,年度预算（元）,联系人,电话,联系人角色,没用的列\n"
        f"导入甲{TAG}科技有限公司,制造业,a,5万,王总,13800000000,决策人,x\n"
        f"导入甲{TAG}科技,制造业,B,,,,,\n"  # 与上一行核心名相同
        "深圳明理律师事务所,法律,A,,,,,\n"  # 已存在
        f"导入乙{TAG},,D,abc,,13900000000,老板,\n"  # 多个错误
        ",,,,,,,\n"  # 空行忽略
        f"导入丙{TAG}贸易,零售,,,,,,\n"
    )
    r = client.post("/api/customers/import/preview", files=_csv(body), headers=SALES_H)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["created"] is False
    assert (data["total"], data["ok"], data["skipped"]) == (5, 2, 3)
    assert data["ignored_columns"] == ["没用的列"]
    rows = {row["line"]: row for row in data["rows"]}
    assert rows[2]["status"] == "ok"
    assert rows[2]["owner_name"] == SALES.name
    assert rows[3] == rows[3] | {"status": "duplicate", "message": "与第 2 行重复"}
    assert rows[4]["status"] == "duplicate"
    assert "深圳明理律师事务所" in rows[4]["message"]
    assert rows[5]["status"] == "error"
    for part in ("等级只能填", "年度预算要填数字", "联系人角色只能填", "没有联系人姓名"):
        assert part in rows[5]["message"]
    assert 6 not in rows  # 空行
    assert rows[7]["status"] == "ok"
    assert _created(tracker) == {}  # 预览不写入


def test_import_creates_customers_and_contacts(client: TestClient, tracker: Tracker) -> None:
    body = (
        "客户名称,行业,等级,规模,年度预算,标签,联系人,职位,电话,联系人角色\n"
        f"导入丁{TAG}有限公司,制造业,a,100-500人,1.5万,重点、华南,李工,CTO,13800000001,技术把关\n"
        f"导入戊{TAG},,,,,,,,,\n"
    )
    r = client.post("/api/customers/import", files=_csv(body, "gb18030"), headers=SALES_H)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["created"] is True
    assert data["ok"] == 2
    made = _created(tracker)
    first = made[f"导入丁{TAG}有限公司"]
    assert first.level == "A"
    assert first.annual_budget == 1_500_000  # 1.5 万元 = 150 万分
    assert first.tags == ["重点", "华南"]
    assert first.owner_id == SALES.id
    assert first.team_id == SALES.team_id
    assert made[f"导入戊{TAG}"].level == "C"
    with session_scope() as db:
        contact = db.scalar(select(Contact).where(Contact.customer_id == first.id))
        assert contact is not None
        assert (contact.name, contact.title, contact.role) == ("李工", "CTO", "technical")
        act = db.scalar(select(Activity).where(Activity.subject_id == first.id))
        assert act is not None
        assert act.action == "import"
    # 再导入同一个文件：全部是重复，什么都不写
    again = client.post("/api/customers/import", files=_csv(body), headers=SALES_H).json()["data"]
    assert (again["ok"], again["skipped"], again["created"]) == (0, 2, False)


@pytest.mark.usefixtures("clean_notes")
def test_manager_assigns_owner_or_pool(client: TestClient, tracker: Tracker) -> None:
    body = (
        "客户名称,负责人\n"
        f"导入己{TAG},王磊\n"
        f"导入庚{TAG},zhangchen\n"
        f"导入辛{TAG},公海\n"
        f"导入壬{TAG},\n"
        f"导入癸{TAG},不存在的人\n"
    )
    r = client.post("/api/customers/import", files=_csv(body), headers=MANAGER_H)
    data = r.json()["data"]
    assert (data["ok"], data["skipped"]) == (4, 1)
    assert "不是本团队的成员" in data["rows"][-1]["message"]
    made = _created(tracker)
    assert made[f"导入己{TAG}"].owner_id == EXTRA_SALES.id
    assert made[f"导入庚{TAG}"].owner_id == SALES.id  # 账号也能认
    pool = made[f"导入辛{TAG}"]
    assert pool.owner_id is None
    assert pool.team_id == MANAGER.team_id
    assert made[f"导入壬{TAG}"].owner_id == MANAGER.id
    with session_scope() as db:
        notes = list(
            db.scalars(
                select(Notification).where(
                    Notification.user_id == EXTRA_SALES.id,
                    Notification.title == f"{MANAGER.name} 导入了 1 个客户给你",
                )
            )
        )
    assert len(notes) == 1


def test_sales_cannot_import_for_others(client: TestClient, tracker: Tracker) -> None:
    body = f"客户名称,负责人\n导入子{TAG},王磊\n导入丑{TAG},{SALES.name}\n"
    data = client.post("/api/customers/import", files=_csv(body), headers=SALES_H).json()["data"]
    assert (data["ok"], data["skipped"]) == (1, 1)
    assert "销售只能导入给自己" in data["rows"][0]["message"]
    assert list(_created(tracker)) == [f"导入丑{TAG}"]


def test_xlsx_import(client: TestClient, tracker: Tracker) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["名称", "行业", "年度预算（元）"])
    ws.append([f"导入寅{TAG}", "教育", 80000])
    buf = io.BytesIO()
    wb.save(buf)
    files = {"file": ("客户.xlsx", buf.getvalue(), "application/octet-stream")}
    data = client.post("/api/customers/import", files=files, headers=SALES_H).json()["data"]
    assert data["ok"] == 1
    assert _created(tracker)[f"导入寅{TAG}"].annual_budget == 8_000_000


def test_file_level_errors(client: TestClient) -> None:
    def post(body: bytes, name: str = "a.csv", h: dict[str, str] = SALES_H) -> tuple[int, str]:
        r = client.post("/api/customers/import/preview", files={"file": (name, body)}, headers=h)
        return r.status_code, r.json()["message"]

    assert post("客户名称\n导入\n".encode(), h=ADMIN_H)[0] == 403
    assert "客户名称" in post("公司,行业\nx,y\n".encode())[1]
    assert "空的" in post(b"  ")[1]
    assert "没有数据" in post("客户名称\n".encode())[1]
    assert "打不开" in post(b"PK\x03\x04broken", "a.xlsx")[1]
    too_many = "客户名称\n" + "".join(f"客户{i}号\n" for i in range(1001))
    assert "最多导入 1000 行" in post(too_many.encode())[1]
    assert "2MB" in post(b"x" * (2 * 1024 * 1024 + 1))[1]
