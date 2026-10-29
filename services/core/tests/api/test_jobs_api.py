"""定时任务：管理接口、调度判断（到点 / 工作日 / 一天一次）、各任务的提醒内容和去重。

任务本身的业务逻辑在一个事务里跑完后回滚，不在测试库里留下通知或改动；调度和运行记录用替换进去的
假任务验证。
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.common.auth import Role
from app.common.db import get_sessionmaker, session_scope
from app.crm.models import (
    Activity,
    Contract,
    Customer,
    DailyReport,
    JobRun,
    Notification,
    Opportunity,
    PaymentPlan,
    ScheduledJob,
    Task,
    User,
)
from app.crm.services import job_service, jobs, wecom_service
from app.crm.services.demo import DEMO_USERS, EXTRA_SALES
from app.rules.crm_calc import LOCAL_TZ
from tests.api.conftest import ADMIN_H, MANAGER_H, SALES_H

SALES = DEMO_USERS[Role.SALES]
MANAGER = DEMO_USERS[Role.MANAGER]
NOW = datetime.now(UTC)


@pytest.fixture
def db() -> Iterator[Session]:
    """跑完回滚：任务生成的通知、改动都不落库。"""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _notes(db: Session, key_prefix: str) -> list[Notification]:
    stmt = select(Notification).where(Notification.dedupe_key.like(f"{key_prefix}%"))
    return list(db.scalars(stmt))


def _local(d: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), LOCAL_TZ)


# ---------- 管理接口 ----------


def test_only_admin_can_see_or_change_jobs(client: TestClient) -> None:
    for h in (SALES_H, MANAGER_H):
        assert client.get("/api/admin/jobs", headers=h).status_code == 403
        assert client.post("/api/admin/jobs/task_due/run", headers=h).status_code == 403
    r = client.get("/api/admin/jobs", headers=ADMIN_H)
    assert r.status_code == 200
    items = {j["name"]: j for j in r.json()["data"]}
    assert set(items) == set(jobs.JOBS)
    # 公海回收会改负责人：默认关闭，带天数参数
    assert items["pool_recycle"]["enabled"] is False
    assert items["pool_recycle"]["options"] == [{"key": "days", "value": 90}]
    assert items["report_remind"]["weekdays_only"] is True
    assert items["task_due"]["run_at"] == "08:30"


@pytest.fixture
def restore_pool_job() -> Iterator[None]:
    yield
    with session_scope() as s:
        s.execute(delete(ScheduledJob).where(ScheduledJob.name == "pool_recycle"))


@pytest.mark.usefixtures("restore_pool_job")
def test_update_job_config(client: TestClient) -> None:
    url = "/api/admin/jobs/pool_recycle"
    r = client.patch(url, json={"run_at": "03:15", "options": {"days": 120}}, headers=ADMIN_H)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["run_at"] == "03:15"
    assert data["enabled"] is False  # 没传的字段不变
    assert data["options"] == [{"key": "days", "value": 120}]
    r = client.patch(url, json={"enabled": True}, headers=ADMIN_H)
    assert r.json()["data"]["enabled"] is True
    assert r.json()["data"]["run_at"] == "03:15"
    assert client.patch(url, json={"run_at": "25:00"}, headers=ADMIN_H).status_code == 400
    bad = client.patch(url, json={"options": {"hours": 3}}, headers=ADMIN_H)
    assert bad.status_code == 400
    assert client.patch(url, json={"options": {"days": 0}}, headers=ADMIN_H).status_code == 400
    assert client.patch("/api/admin/jobs/nope", json={}, headers=ADMIN_H).status_code == 404


# ---------- 调度：到点、工作日、一天一次 ----------


@pytest.fixture
def fake_job(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[datetime]]:
    """调度器只看到一个假任务：工作日 9:00，第三次运行抛错。"""
    calls: list[datetime] = []

    def run(_db: Session, now: datetime, _opts: dict[str, Any]) -> str:
        calls.append(now)
        if len(calls) == 3:
            raise RuntimeError("模拟失败")
        return f"第 {len(calls)} 次"

    fake = jobs.JobDef("e2e_fake", "假任务", "测试用", time(9, 0), True, True, run)
    monkeypatch.setattr(job_service, "JOBS", {"e2e_fake": fake})
    yield calls
    with session_scope() as s:
        s.execute(delete(JobRun).where(JobRun.job == "e2e_fake"))


def test_due_respects_time_and_weekdays(fake_job: list[datetime]) -> None:
    monday = date(2031, 1, 6)
    saturday = date(2031, 1, 11)
    assert job_service.due(_local(monday, 8, 59)) == []
    assert job_service.due(_local(monday, 9, 0)) == ["e2e_fake"]
    assert job_service.due(_local(saturday, 10, 0)) == []  # 只在工作日
    assert fake_job == []


def test_tick_runs_once_per_day_and_records_failure(fake_job: list[datetime]) -> None:
    day = date(2031, 1, 7)
    assert job_service.tick(_local(day, 9, 5)) == ["e2e_fake"]
    assert job_service.tick(_local(day, 9, 30)) == []  # 同一天不再跑
    assert job_service.tick(_local(day + timedelta(days=1), 9, 1)) == ["e2e_fake"]
    assert len(fake_job) == 2
    # 第三次运行抛错：记录为 failed，不影响之后的运行
    run_id = job_service.execute("e2e_fake", NOW, run_key=jobs.new_run_key(), trigger="manual")
    with session_scope() as s:
        run = s.get(JobRun, run_id)
        assert run is not None
        assert run.status == "failed"
        assert "模拟失败" in (run.summary or "")
        keys = set(s.scalars(select(JobRun.run_key).where(JobRun.job == "e2e_fake")))
    assert {"2031-01-07", "2031-01-08"} <= keys


def test_run_now_api_records_who_ran_it(client: TestClient, fake_job: list[datetime]) -> None:
    r = client.post("/api/admin/jobs/e2e_fake/run", headers=ADMIN_H)
    assert r.status_code == 200, r.text
    run = r.json()["data"]
    assert run["status"] == "ok"
    assert run["trigger"] == "manual"
    assert run["triggered_by"] == DEMO_USERS[Role.ADMIN].name
    assert run["summary"] == "第 1 次"
    runs = client.get("/api/admin/jobs/runs?name=e2e_fake", headers=ADMIN_H).json()["data"]
    assert runs[0]["id"] == run["id"]


# ---------- 各任务的内容（事务回滚，不落库） ----------


def _customer(db: Session, owner_id: uuid.UUID, team_id: Any, days_ago: int = 0) -> Customer:
    c = Customer(
        name=f"定时任务测试-{uuid.uuid4().hex[:6]}",
        level="C",
        owner_id=owner_id,
        team_id=team_id,
        created_at=NOW - timedelta(days=days_ago),
    )
    db.add(c)
    db.flush()
    return c


def test_task_due_job_notifies_once(db: Session) -> None:
    c = _customer(db, SALES.id, SALES.team_id)
    common = {"customer_id": c.id, "subject_type": "customer", "subject_id": c.id}
    owner = {"owner_id": SALES.id, "team_id": SALES.team_id}
    today = Task(title="今天到期测试", due_at=NOW, **common, **owner)
    late = Task(title="逾期测试", due_at=NOW - timedelta(days=2), **common, **owner)
    old = Task(title="很久以前", due_at=NOW - timedelta(days=30), **common, **owner)
    db.add_all([today, late, old])
    db.flush()
    jobs.JOBS["task_due"].run(db, NOW, {})
    jobs.JOBS["task_due"].run(db, NOW, {})  # 再跑一次不重复
    assert len(_notes(db, f"task_due:{today.id}")) == 1
    overdue = _notes(db, f"task_overdue:{late.id}")
    assert len(overdue) == 1
    assert overdue[0].user_id == SALES.id
    assert overdue[0].title == "任务已逾期：逾期测试"
    assert _notes(db, f"task_overdue:{old.id}") == []  # 超过一周的不再提醒


def test_payment_overdue_notifies_owner_and_manager(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pushed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        wecom_service, "queue", lambda _db, ev, title, _c: pushed.append((ev, title))
    )
    c = _customer(db, SALES.id, SALES.team_id)
    contract = Contract(
        code=f"HT-JOB-{uuid.uuid4().hex[:6]}",
        customer_id=c.id,
        amount=100_000,
        paid_amount=10_000,
        owner_id=SALES.id,
        team_id=SALES.team_id,
    )
    db.add(contract)
    db.flush()
    owner = {"owner_id": SALES.id, "team_id": SALES.team_id}
    first = PaymentPlan(
        contract_id=contract.id,
        seq=1,
        name="预付款",
        amount=30_000,
        due_date=(NOW - timedelta(days=5)).date(),
        **owner,
    )
    later = PaymentPlan(
        contract_id=contract.id,
        seq=2,
        name="尾款",
        amount=70_000,
        due_date=(NOW + timedelta(days=30)).date(),
        **owner,
    )
    db.add_all([first, later])
    db.flush()
    summary = jobs.JOBS["payment_overdue"].run(db, NOW, {})
    jobs.JOBS["payment_overdue"].run(db, NOW, {})
    notes = _notes(db, f"payment_overdue:{first.id}")
    assert {n.user_id for n in notes} == {SALES.id, MANAGER.id}
    assert "应收 ¥200.00" in (notes[0].body or "")  # 300 元的预付款已回 100
    assert notes[0].link == f"/contracts?plan={contract.id}"
    assert _notes(db, f"payment_overdue:{later.id}") == []
    assert "逾期" in summary
    assert len([p for p in pushed if p[0] == "payment_overdue"]) == 1  # 第二次没有新提醒就不推


def test_stale_opportunity_notifies_once_per_episode(db: Session) -> None:
    c = _customer(db, SALES.id, SALES.team_id, days_ago=60)
    opp = Opportunity(
        customer_id=c.id,
        name="停滞测试商机",
        stage="proposal",
        owner_id=SALES.id,
        team_id=SALES.team_id,
        created_at=NOW - timedelta(days=60),
    )
    db.add(opp)
    db.flush()
    jobs.JOBS["stale_opportunities"].run(db, NOW, {})
    jobs.JOBS["stale_opportunities"].run(db, NOW, {})
    notes = _notes(db, f"opp_stale:{opp.id}")
    assert len(notes) == 1
    assert notes[0].link == f"/pipeline?opp={opp.id}"
    assert "60 天没有进展" in notes[0].title


def test_report_remind_skips_submitted_and_inactive(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pushed: list[str] = []
    monkeypatch.setattr(wecom_service, "queue", lambda _db, ev, _t, content: pushed.append(content))
    day = (NOW.astimezone(LOCAL_TZ)).date().isoformat()
    jobs.JOBS["report_remind"].run(db, NOW, {})
    jobs.JOBS["report_remind"].run(db, NOW, {})
    submitted = set(
        db.scalars(
            select(Notification.user_id).where(Notification.dedupe_key.like("report_remind:%"))
        )
    )
    done = set(
        db.scalars(
            select(DailyReport.user_id).where(
                DailyReport.report_date == NOW.astimezone(LOCAL_TZ).date(),
                DailyReport.status == "submitted",
            )
        )
    )
    active_sales = set(
        db.scalars(select(User.id).where(User.role == "sales", User.active.is_(True)))
    )
    assert submitted == active_sales - done
    for uid in submitted:
        assert len(_notes(db, f"report_remind:{uid}:{day}")) == 1
    if submitted:
        assert pushed and "还没提交" in pushed[0]


def test_pool_recycle_moves_idle_customers_only(db: Session) -> None:
    idle = _customer(db, EXTRA_SALES.id, EXTRA_SALES.team_id, days_ago=200)
    busy = _customer(db, EXTRA_SALES.id, EXTRA_SALES.team_id, days_ago=200)
    fresh = _customer(db, EXTRA_SALES.id, EXTRA_SALES.team_id, days_ago=10)
    db.add(
        Opportunity(
            customer_id=busy.id,
            name="进行中",
            stage="qualified",
            owner_id=EXTRA_SALES.id,
            team_id=EXTRA_SALES.team_id,
        )
    )
    db.flush()
    summary = jobs.JOBS["pool_recycle"].run(db, NOW, {"days": 90})
    db.expire_all()
    assert db.get(Customer, idle.id).owner_id is None  # type: ignore[union-attr]
    assert db.get(Customer, idle.id).team_id == EXTRA_SALES.team_id  # type: ignore[union-attr]
    assert db.get(Customer, busy.id).owner_id == EXTRA_SALES.id  # type: ignore[union-attr]
    assert db.get(Customer, fresh.id).owner_id == EXTRA_SALES.id  # type: ignore[union-attr]
    act = db.scalar(select(Activity).where(Activity.subject_id == idle.id))
    assert act is not None
    assert act.source == "system"
    assert act.actor_id is None
    assert "90 天" in (act.content or "")
    note = _notes(db, f"customer_recycled:{idle.id}")
    assert len(note) == 1
    assert note[0].user_id == EXTRA_SALES.id
    assert "退回公海" in summary
    assert db.scalar(select(func.count()).where(Activity.subject_id == busy.id)) == 0


def test_job_wecom_events_are_opt_in() -> None:
    """定时任务自动推群的消息默认不开，已保存的推送配置也不会因为升级多推。"""
    assert {"payment_overdue", "report_remind_auto"} <= set(wecom_service.EVENTS)
    assert not {"payment_overdue", "report_remind_auto"} & set(wecom_service.DEFAULT_EVENTS)
