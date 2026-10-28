"""客户查重的名称比较（纯函数）。"""

from app.crm.services.customer_service import core_name, similar_names


def test_core_name_strips_suffix_brackets_and_spaces() -> None:
    assert core_name("明理科技（深圳）有限公司") == "明理科技"
    assert core_name(" 云帆 集团 ") == "云帆"
    assert core_name("有限公司") == "有限公司"  # 只剩后缀时不剥


def test_similar_names_exact_first_and_threshold() -> None:
    cands = ["深圳明理律师事务所", "明理科技有限公司", "星河数据", "明月律所"]
    got = similar_names("明理科技", cands)
    assert got[0] == ("明理科技有限公司", True)
    assert ("深圳明理律师事务所", False) not in got  # 只有「明理」一个字组重合
    assert similar_names("深圳明理律所", cands)[0] == ("深圳明理律师事务所", False)
    assert similar_names("星", cands) == []
    assert similar_names("星河", cands) == [("星河数据", False)]  # 包含关系，两个字也提示
