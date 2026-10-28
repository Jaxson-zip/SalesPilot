"""AI 出方案时识别用户提到的客户（mention_keys）：「明理律所」能对上「深圳明理律师事务所」。"""

from app.crm.services.customer_service import mention_keys


def test_mention_keys_strip_city_and_suffix() -> None:
    assert mention_keys("深圳明理律师事务所") == ["明理律师事务所", "明理律师", "明理律", "明理"]
    assert mention_keys("华南智能制造有限公司")[:2] == ["华南智能制造", "华南智能"]
    assert "粤海" in mention_keys("粤海物流集团")


def test_short_names_and_city_only() -> None:
    assert mention_keys("星河") == ["星河"]
    assert mention_keys("深圳") == ["深圳"]  # 只有城市名时不去掉
    assert mention_keys("A") == []
