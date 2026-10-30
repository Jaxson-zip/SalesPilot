"""初始化 / 找回管理员：python -m seed.admin <登录名> [--name 姓名]

正式上线用空库时，先用它建第一个管理员，再由管理员在「成员与团队」里建其他账号，不需要导入演示数据。
登录名已存在时改为重置它的密码（演示账号上线前用这个换掉公开的初始密码）。
两种情况都生成临时密码打印到终端，首次登录必须修改。
"""

import argparse
import re
import sys

from sqlalchemy import func, select

from app.common.auth import Role, forget_user
from app.common.db import session_scope
from app.common.passwords import hash_password, temp_password
from app.crm.models import ProductLine, User
from app.crm.schemas.account import USERNAME_PATTERN
from seed import data


def ensure_product_lines() -> None:
    """三个行业包对应的产品线是系统配置（不是演示数据），空库里也要有。"""
    with session_scope() as db:
        for line in data.PRODUCT_LINES:
            if db.get(ProductLine, line["id"]) is None:
                db.add(ProductLine(**line))


def upsert_admin(username: str, name: str | None) -> tuple[str, bool]:
    """返回（临时密码，是否新建）。"""
    password = temp_password()
    with session_scope() as db:
        user = db.scalars(select(User).where(func.lower(User.username) == username)).first()
        created = user is None
        if user is None:
            user = User(username=username, name=name or username, role=Role.ADMIN.value)
            user.token_version = 0
            db.add(user)
        user.password_hash = hash_password(password)
        user.must_change_password = True
        user.active = True
        if not created:
            user.token_version += 1  # 旧的登录全部失效
        db.flush()
        forget_user(user.id)
    return password, created


def main() -> None:
    parser = argparse.ArgumentParser(description="新建管理员，或重置已有账号的密码")
    parser.add_argument("username", help="登录名（字母开头，3–30 位字母、数字或 ._-）")
    parser.add_argument("--name", help="新建时的姓名，默认同登录名")
    args = parser.parse_args()
    username = args.username.strip().lower()
    if not re.fullmatch(USERNAME_PATTERN, username):
        sys.exit(f"登录名格式不对：{args.username}")
    ensure_product_lines()
    password, created = upsert_admin(username, args.name)
    action = "已新建管理员" if created else "已重置密码（角色不变）"
    print(f"{action}：{username}\n临时密码：{password}\n首次登录后必须修改密码。")


if __name__ == "__main__":
    main()
