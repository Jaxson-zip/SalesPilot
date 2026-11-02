from app.agent.stage_text import annotate_stages


def test_stage_codes_get_system_labels() -> None:
    out = annotate_stages(
        {"stages": [{"stage": "proposal", "count": 2}], "stage": "negotiation", "x": "won"}
    )
    assert out["stages"][0]["stage_label"] == "方案报价"
    assert out["stage_label"] == "商务谈判"
    assert "x_label" not in out  # 只认阶段字段


def test_unknown_stage_value_untouched() -> None:
    assert annotate_stages({"stage": "weird"}) == {"stage": "weird"}
