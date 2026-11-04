"""产品目录改价写进操作日志的那句话。"""

from app.crm.services.catalog_service import change_text

BASE = {"name": "GPU 服务器", "unit": "台", "cost": 200_000, "price": 300_000}


def test_change_text_lists_changed_fields_in_yuan() -> None:
    after = {**BASE, "price": 100_000, "unit": "套"}
    expected = "GPU 服务器：单位 台 → 套，售价 ¥3,000.00 → ¥1,000.00"
    assert change_text("GPU 服务器", BASE, after) == expected


def test_change_text_empty_when_nothing_changed() -> None:
    assert change_text("GPU 服务器", BASE, dict(BASE)) == ""
