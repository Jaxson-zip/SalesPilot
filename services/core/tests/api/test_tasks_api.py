"""任务、下一步行动、阶段默认赢率、停滞提醒、任务到期通知（接口契约 v3 §12、§13、§15）。"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.common.db import session_scope
from app.crm.models import Activity, Opportunity
from app.rules.crm_calc import day_bounds
from seed.data import C_MINGLI, C_PC3H
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H, Tracker
from tests.api.test_opportunities_api import new_opp


def today_due() -> str:
    """今天（北京时间）结束前 1 分钟，任何时候跑都算「今天到期」。"""
    return (day_bounds(datetime.now(UTC))[1] - timedelta(minutes=1)).isoformat()


def new_task(
    client: TestClient,
    tracker: Tracker,
    subject_id: str,
    subject_type: str = "opportunity",
    headers: dict[str, str] = SALES_H,
    **extra: object,
) -> dict:
    body = {
        "title": f"测试任务-{uuid.uuid4().hex[:6]}",
        "due_at": today_due(),
        "subject_type": subject_type,
        "subject_id": subject_id,
        "type": "call",
        **extra,
    }
    r = client.post("/api/tasks", json=body, headers=headers).json()
    if r["code"] == 0:
        tracker.tasks.append(uuid.UUID(r["data"]["id"]))
    return r


def test_task_lifecycle_and_next_task(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    later = new_task(
        client, tracker, opp["id"], due_at=(datetime.now(UTC) + timedelta(days=5)).isoformat()
    )
    task = new_task(client, tracker, opp["id"], note="带上报价单")["data"]
    assert task["subject_name"] == opp["name"] and task["owner"]["name"] == "张晨"
    assert task["done"] is False and task["overdue"] is False and task["type"] == "call"

    detail = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    assert detail["next_task"]["id"] == task["id"]  # 最早到期的未完成任务

    listed = client.get(f"/api/tasks?subject_id={opp['id']}", headers=SALES_H).json()["data"]
    assert listed["total"] == 2 and listed["items"][0]["id"] == task["id"]

    patched = client.patch(f"/api/tasks/{task['id']}", json={"title": "改标题"}, headers=SALES_H)
    assert patched.json()["data"]["title"] == "改标题"
    done = client.patch(f"/api/tasks/{task['id']}", json={"done": True}, headers=SALES_H).json()
    assert done["data"]["done"] is True and done["data"]["done_at"]

    detail = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    assert detail["next_task"]["id"] == later["data"]["id"]
    assert any(
        a["action"] == "task_done" and "改标题" in a["content"] for a in detail["activities"]
    )

    locked = client.delete(f"/api/tasks/{task['id']}", headers=SALES_H).json()
    assert locked["code"] == 42201 and locked["data"]["rule"] == "task_done_not_deletable"
    assert client.delete(f"/api/tasks/{later['data']['id']}", headers=SALES_H).json()["code"] == 0
    detail = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    assert detail["next_task"] is None


def test_create_task_permissions(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    admin = new_task(client, tracker, opp["id"], headers=ADMIN_H)
    assert admin["code"] == 40301 and admin["data"]["rule"] == "role_forbidden"
    manager = new_task(client, tracker, opp["id"], headers=MANAGER_H)
    assert manager["code"] == 40301 and manager["data"]["rule"] == "not_owner"
    invisible = new_task(client, tracker, str(C_PC3H), "customer")  # 王磊的客户
    assert invisible["code"] == 40401
    bad = new_task(client, tracker, opp["id"], "contract")
    assert bad["code"] == 40001
    on_customer = new_task(client, tracker, str(C_MINGLI), "customer")["data"]
    assert on_customer["subject_name"] == "深圳明理律师事务所"


def test_only_owner_can_edit_task(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    task = new_task(client, tracker, opp["id"])["data"]
    url = f"/api/tasks/{task['id']}"
    manager = client.patch(url, json={"done": True}, headers=MANAGER_H).json()
    assert manager["code"] == 40301 and manager["data"]["rule"] == "not_owner"
    admin = client.delete(url, headers=ADMIN_H).json()
    assert admin["code"] == 40301 and admin["data"]["rule"] == "role_forbidden"
    team = client.get("/api/tasks?view=team&status=open&page_size=100", headers=MANAGER_H)
    assert task["id"] in {t["id"] for t in team.json()["data"]["items"]}  # 主管看得到
    missing = client.patch(f"/api/tasks/{uuid.uuid4()}", json={"done": True}, headers=SALES_H)
    assert missing.json()["code"] == 40401


def test_due_filters_and_dashboard(client: TestClient, tracker: Tracker) -> None:
    today = client.get("/api/tasks?due=today", headers=SALES_H).json()["data"]["items"]
    assert "给王律师发送修订版方案" in {t["title"] for t in today}
    overdue = client.get("/api/tasks?due=overdue", headers=SALES_H).json()["data"]["items"]
    assert "电话跟进刘经理确认报价" in {t["title"] for t in overdue}
    assert all(t["overdue"] for t in overdue)
    done = client.get("/api/tasks?status=done", headers=SALES_H).json()["data"]["items"]
    assert all(t["done"] for t in done) and len(done) >= 1
    before = client.get("/api/dashboard", headers=SALES_H).json()["data"]
    opp = new_opp(client, tracker)
    yesterday = (datetime.now(UTC) - timedelta(days=1, hours=1)).isoformat()
    new_task(client, tracker, opp["id"], due_at=yesterday)
    new_task(client, tracker, opp["id"])
    after = client.get("/api/dashboard", headers=SALES_H).json()["data"]
    assert after["tasks_overdue"] == before["tasks_overdue"] + 1
    assert after["tasks_today"] == before["tasks_today"] + 1
    assert client.get("/api/tasks?due=bad", headers=SALES_H).json()["code"] == 40001


def test_seeded_next_task_and_stale(client: TestClient) -> None:
    items = client.get("/api/opportunities?page_size=100", headers=SALES_H).json()["data"]["items"]
    by_name = {o["name"]: o for o in items}
    assert by_name["合同审查私有化"]["next_task"]["overdue"] is False
    assert by_name["质检助手"]["next_task"]["overdue"] is True
    stale = by_name["IT 设备换新"]
    assert stale["next_task"] is None and stale["stale"] is True and stale["idle_days"] >= 14
    assert by_name["AI 客服"]["next_task"] is None
    assert by_name["智能调度"]["stale"] is False  # 终态不提醒
    assert (
        by_name["合同审查私有化"]["stale"] is False
        and by_name["合同审查私有化"]["last_activity_at"]
    )


def _backdate(opp: dict, days: int) -> None:
    moment = datetime.now(UTC) - timedelta(days=days)
    ids = [uuid.UUID(opp["id"]), uuid.UUID(opp["customer"]["id"])]
    with session_scope() as db:
        db.execute(update(Activity).where(Activity.subject_id.in_(ids)).values(created_at=moment))
        db.execute(update(Opportunity).where(Opportunity.id == ids[0]).values(created_at=moment))


def test_stale_boundary(client: TestClient, tracker: Tracker) -> None:
    body = {"name": f"测试停滞客户-{uuid.uuid4().hex[:6]}"}
    customer = client.post("/api/customers", json=body, headers=SALES_H).json()["data"]
    tracker.customers.append(uuid.UUID(customer["id"]))
    opp = new_opp(client, tracker, customer_id=customer["id"])
    _backdate(opp, 13)
    got = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    assert got["idle_days"] == 13 and got["stale"] is False
    _backdate(opp, 14)
    got = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    assert got["idle_days"] == 14 and got["stale"] is True
    # 写一条跟进后不再停滞
    client.post(
        f"/api/customers/{customer['id']}/followups",
        json={"type": "phone", "content": "测试-重新联系"},
        headers=SALES_H,
    )
    got = client.get(f"/api/opportunities/{opp['id']}", headers=SALES_H).json()["data"]
    assert got["idle_days"] == 0 and got["stale"] is False


def test_stage_change_sets_default_win_rate(client: TestClient, tracker: Tracker) -> None:
    opp = new_opp(client, tracker)
    url = f"/api/opportunities/{opp['id']}"
    moved = client.patch(f"{url}/stage", json={"stage": "qualified"}, headers=SALES_H).json()
    assert moved["data"]["win_rate"] == 25
    manual = client.patch(url, json={"win_rate": 33}, headers=SALES_H).json()["data"]
    assert manual["win_rate"] == 33  # 仍可手动修改
    moved = client.patch(f"{url}/stage", json={"stage": "negotiation"}, headers=SALES_H).json()
    assert moved["data"]["win_rate"] == 75
    lost = client.patch(
        f"{url}/stage", json={"stage": "lost", "lost_reason": "预算取消"}, headers=SALES_H
    ).json()
    assert lost["data"]["win_rate"] == 0


def test_task_due_notification_generated_once(client: TestClient) -> None:
    def due_titles() -> list[str]:
        data = client.get("/api/notifications?limit=100", headers=SALES_H).json()["data"]
        return [n["title"] for n in data["items"] if n["type"] == "task_due"]

    first = due_titles()
    assert first.count("任务今天到期：给王律师发送修订版方案") == 1
    assert due_titles().count("任务今天到期：给王律师发送修订版方案") == 1  # 同一天不重复生成
