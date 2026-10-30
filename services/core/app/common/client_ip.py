"""请求来源 IP：登录失败锁定、操作日志、电话查看留痕都用它。

X-Forwarded-For / X-Real-IP 都是客户端可以随便填的请求头，直接信任的话，换一个假 IP
就能绕过「错 10 次锁定」。所以默认只认 TCP 连接的对端地址；部署在 nginx 后面时设
TRUST_PROXY_HEADERS=true，读取 nginx 用 $remote_addr 覆盖写入的 X-Real-IP。
"""

from app.common.config import get_settings


def resolve_client_ip(real_ip: str | None, peer: str | None) -> str | None:
    if get_settings().trust_proxy_headers and real_ip and real_ip.strip():
        return real_ip.strip()[:64]
    return peer
