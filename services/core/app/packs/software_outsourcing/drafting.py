"""软件外包需求的文字部分：给大模型的拆解说明，以及大模型不可用时按关键词出的需求草稿。"""

import json
import re
from typing import Any

_SOLO_WORDS = ("一个人", "个人全栈", "独立开发", "我自己做", "自己一个人", "单人")
_PLATFORM_WORDS: dict[str, tuple[str, ...]] = {
    "mini_program": ("小程序",),
    "app": ("app", "安卓", "android", "ios", "苹果"),
    "web": ("网站", "官网", "h5", "网页", "web"),
    "admin": ("后台", "管理端", "管理系统"),
}
_NO_SOP_WORDS = ("没有sop", "没sop", "无sop", "没有流程文档", "没有文档", "脑子里", "没有成文")
_OCR_VOLUME_RE = re.compile(
    r"每(天|日|月)\s*(?:约|大概|大约|差不多)?\s*(\d+(?:\.\d+)?)\s*(万)?\s*(?:张|票|单|份|页)"
)
_WEEKS_RE = re.compile(r"(\d+)\s*(个月|月|周|星期)")
_BUDGET_RE = re.compile(r"预算\s*(?:在|约|为)?\s*(\d+(?:\.\d+)?)\s*(万|元)?")


def extract_hint(library: dict[str, Any], draft: dict[str, Any] | None = None) -> str:
    """给大模型的拆解说明：模块库、复杂度和首期判断（数字一律不让模型估）。

    已有需求草稿时附上，让模型在草稿基础上改（「去掉地图」「支付改简单」），输出完整模块清单。
    """
    lib = "；".join(f"{k}={m['name']}" for k, m in library.items())
    current = ""
    if draft and draft.get("modules"):
        keep = {k: draft[k] for k in ("project", "platforms", "modules") if k in draft}
        current = (
            "\n当前需求草稿（JSON）："
            + json.dumps(keep, ensure_ascii=False)
            + "\n用户这句话如果在增删或修改功能 / 端，"
            "请在草稿基础上输出修改后的完整 modules / platforms；"
            "只是补充预算、工期等其他信息时不要输出 modules 和 platforms。"
        )
    return current + (
        "这是软件外包项目。modules 需要你把客户描述的业务拆解成功能模块"
        "（这一项可以根据业务常识推断，"
        "例如「预约小程序」通常包含 用户登录、预约排期、消息通知）："
        f"优先使用模块库里的 key：{lib}。模块库没有的功能用 key=custom 并写清名称。"
        "同一个功能只出现一次；复杂度按描述判断（多规则、多角色、需对接外部系统 → complex）；"
        "客户说「以后再做 / 二期」的模块 must=false。"
        "客户明确提到的功能 source=mentioned，你根据常识补充的 source=inferred。"
        "questions 写 3–5 个销售需要回头和客户确认的关键问题。"
        "platforms 只填客户明确提到或业务上必然需要的端（提到管理、运营、后台配置时加 admin）；"
        "只说「手机也能用」「网页和手机都能用」、没提 App 或小程序时"
        "按网页自适应处理，只填 web；客户没说做什么端时，按用户是谁选一个最合适的客户端"
        "（面向消费者 / 学员 / 会员的优先 mini_program，企业内部办公优先 web），"
        "不要同时加多个。"
        "客户只说了要做 App / 小程序 / 系统、没说是什么业务时，modules 留空（交给销售追问），"
        "不要凭空拆解。"
        "图片 / 单据 / 票据的 OCR 识别用 key=ocr（不是 ai）；ai 只用于对话、问答、内容生成。"
        "客户说没有 SOP、没有流程文档、流程在老员工脑子里时 no_sop=true；"
        "ocr_monthly_pages 只填客户说的业务量，样例张数不算。不要估算人天和价格。"
    )


def rule_draft(library: dict[str, Any], text: str) -> dict[str, Any]:
    """规则兜底：按关键词识别端和标准模块（大模型不可用时也能出一版）。"""
    low = text.lower()
    draft: dict[str, Any] = {}
    platforms = [p for p, words in _PLATFORM_WORDS.items() if any(w in low for w in words)]
    if platforms:
        draft["platforms"] = platforms
    modules = [
        {"key": key, "name": m["name"], "complexity": "medium", "must": True}
        for key, m in library.items()
        if any(w.lower() in low for w in m.get("keywords", []))
    ]
    if modules:
        draft["modules"] = modules
    if any(w in text for w in _SOLO_WORDS):
        draft["team_size"] = 1
    if any(w in low.replace(" ", "") for w in _NO_SOP_WORDS):
        draft["no_sop"] = True
    if m := _OCR_VOLUME_RE.search(text):
        n = float(m.group(2)) * (10000 if m.group(3) else 1)
        draft["ocr_monthly_pages"] = round(n * (1 if m.group(1) == "月" else 30))
    if m := _WEEKS_RE.search(text):
        n = int(m.group(1))
        draft["deadline_weeks"] = n * 4 if "月" in m.group(2) else n
    if m := _BUDGET_RE.search(text):
        value = float(m.group(1)) * (10000 if m.group(2) == "万" else 1)
        draft["budget"] = round(value * 100)
    return draft
