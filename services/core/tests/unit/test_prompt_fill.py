"""AI 工作台示例问题按数据填写：缺数据时用 fallback，没有 fallback 就不显示。"""

from app.crm.services.prompt_fill import fill

PROMPTS = [
    {"title": "出方案报价", "prompt": "给明理律所出方案", "pack_example": True},
    {"title": "对话报销", "prompt": "请{customer}的{contact}吃饭", "fallback": "请客户吃饭"},
    {"title": "推进商机", "prompt": "把{opp_customer}的「{opp_name}」推进到{next_stage}"},
]


def test_fill_with_data() -> None:
    values = {"customer": "星河设计", "contact": "周总", "opp_customer": "华南智造"}
    values |= {"opp_name": "产线质检", "next_stage": "方案报价"}
    out = fill(PROMPTS, values)
    assert [p["prompt"] for p in out] == [
        "给明理律所出方案",
        "请星河设计的周总吃饭",
        "把华南智造的「产线质检」推进到方案报价",
    ]
    assert all("fallback" not in p for p in out) and out[0]["pack_example"] is True


def test_fill_without_data() -> None:
    """回归：示例写死「把星河设计的商机推进到商务谈判」，商机删了 / 输单了仍然推荐。"""
    out = fill(PROMPTS, {})
    assert [p["title"] for p in out] == ["出方案报价", "对话报销"]
    assert out[1]["prompt"] == "请客户吃饭"
