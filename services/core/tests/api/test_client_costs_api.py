"""软件外包：第三方费用默认不计入报价，单列为客户自付；报价单保存并在详情里返回。"""

import uuid

from fastapi.testclient import TestClient

from app.common.auth import Role
from app.common.db import session_scope
from app.crm.services import quote_service
from app.crm.services.demo import DEMO_USERS
from app.packs.registry import get_configurator
from app.packs.software_outsourcing.requirement import SoftwareRequirement
from seed.data import C_MINGLI
from tests.api.conftest import SALES_H, Tracker

SALES = DEMO_USERS[Role.SALES]


def test_quote_keeps_client_costs(client: TestClient, tracker: Tracker) -> None:
    req = SoftwareRequirement.model_validate(
        {
            "platforms": ["app", "admin"],
            "modules": [{"key": "ai", "name": "智能客服"}, {"key": "order", "name": "订单"}],
        }
    )
    tier = {t.tier: t for t in get_configurator("software_outsourcing").configure(req)}["standard"]
    assert not [i for i in tier.items if i.sku.startswith("TP-")]
    with session_scope() as db:
        quote = quote_service.create_from_tier(
            db,
            SALES,
            pack="software_outsourcing",
            tier=tier,
            opportunity_id=None,
            idempotency_key=f"test-cc-{uuid.uuid4().hex}",
            customer_id=C_MINGLI,
        )
    tracker.quotes.append(quote.id)
    assert quote.total_price == tier.total_price
    detail = client.get(f"/api/quotes/{quote.id}", headers=SALES_H).json()["data"]
    names = {c["name"]: c for c in detail["client_costs"]}
    assert names["苹果开发者账号"]["period"] == "year"
    assert names["大模型调用费（AI 功能）"]["period"] == "month"
    assert names["大模型调用费（AI 功能）"]["amount"] == tier.specs["ai_monthly_cost"]
