"""演示身份：固定 UUID（uuid5），种子数据与假登录共用，保证不连数据库也能签发 token。"""

import uuid

from app.common.auth import CurrentUser, Role

_NS = uuid.uuid5(uuid.NAMESPACE_URL, "salespilot.demo")


def demo_id(key: str) -> uuid.UUID:
    return uuid.uuid5(_NS, key)


TEAM_SOUTH_ID = demo_id("team:south")

DEMO_USERS: dict[Role, CurrentUser] = {
    Role.SALES: CurrentUser(
        id=demo_id("user:sales"), name="张晨", role=Role.SALES, team_id=TEAM_SOUTH_ID
    ),
    Role.MANAGER: CurrentUser(
        id=demo_id("user:manager"), name="李薇", role=Role.MANAGER, team_id=TEAM_SOUTH_ID
    ),
    Role.ADMIN: CurrentUser(id=demo_id("user:admin"), name="周敏", role=Role.ADMIN, team_id=None),
}

# 同团队的另一名销售（只在种子数据里出现，用于演示销售之间数据隔离）
EXTRA_SALES = CurrentUser(
    id=demo_id("user:sales2"), name="王磊", role=Role.SALES, team_id=TEAM_SOUTH_ID
)


# 演示账户的登录名（迁移 0019 和种子数据共用；初始密码见 DEMO_PASSWORD）
DEMO_LOGINS: dict[uuid.UUID, str] = {
    DEMO_USERS[Role.SALES].id: "zhangchen",
    DEMO_USERS[Role.MANAGER].id: "liwei",
    DEMO_USERS[Role.ADMIN].id: "zhoumin",
    EXTRA_SALES.id: "wanglei",
}
