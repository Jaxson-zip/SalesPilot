"""对话循环里的「方案进行中」说明：讲清楚走到哪一步、草稿里已有哪些信息。"""

from app.agent.nodes.tool_loop import solution_note
from app.agent.requirement_brief import requirement_facts, solution_progress

REQ = {
    "project": "星河设计工作室预约小程序",
    "platforms": ["mini_program", "admin"],
    "modules": [
        {"key": "login", "name": "微信登录", "complexity": "simple"},
        {"key": "booking", "name": "服务预约", "complexity": "medium"},
    ],
    "budget": 10_000_000,
    "deadline_weeks": 6,
    "questions": ["预约是否需要支付定金？"],
}


def test_facts_list_what_user_already_gave() -> None:
    facts = "\n".join(requirement_facts("software_outsourcing", REQ))
    assert "mini_program、admin" in facts and "微信登录、服务预约" in facts
    assert "¥100,000（10 万元）" in facts and "6" in facts
    assert "定金" not in facts  # 待确认问题不算已给的信息
    assert requirement_facts("nope", REQ) == []


def test_unconfirmed_draft_says_card_is_waiting() -> None:
    """回归：需求卡片已发出，用户纠正方向后模型说「上一轮还没有真正生成方案」并重复追问。"""
    note = solution_progress("software_outsourcing", REQ, confirmed=False)
    assert "需求卡片" in note and "不要说「还没有生成方案」" in note
    assert "软件外包" in note and "不要再问" in note
    assert "已经确认" in solution_progress("software_outsourcing", REQ, confirmed=True)


def test_solution_note_uses_progress() -> None:
    state = {"pack_id": "software_outsourcing", "requirement": REQ, "requirement_confirmed": False}
    note = solution_note(state)  # type: ignore[arg-type]
    assert note and "服务预约" in note
    assert solution_note({}) is None  # type: ignore[typeddict-item]
