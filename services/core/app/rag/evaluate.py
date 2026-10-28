"""知识库评测（架构设计 §5.5）：Top-4 命中率 + 无答案问题的拒答率，并对比不同相似度阈值。

运行：uv run python -m app.rag.evaluate [--out ../../docs/知识库评测结果.md]
需要已配置 Embedding 模型并完成入库（python -m app.rag.ingest --scope all）。

每个问题只检索一次（阈值为 0，取 top_k 条原始结果），不同阈值在本地过滤后分别打分，
这样调阈值不用反复调用 Embedding。另外对比「向量顺序」和「重排后」的 Top-1 命中率。
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.common.db import session_scope
from app.common.errors import BizError
from app.rag.retriever import (
    THRESHOLD,
    TOP_K,
    PolicySearchResult,
    filter_hits,
    rerank_hits,
    scopes_for,
    search,
)

CORE_ROOT = Path(__file__).resolve().parents[2]
QA_FILE = CORE_ROOT / "tests" / "rag" / "qa.yaml"
TOP_N = 4  # 命中率按前 4 条计算（与回复里引用的出处数量一致）
THRESHOLDS = (0.4, 0.5, 0.6)


class Case(BaseModel):
    q: str
    doc: str | None = None
    section: str | None = None
    pack: str | None = None
    no_answer: bool = False


@dataclass
class CaseResult:
    case: Case
    found: bool
    hit: bool  # 有答案的题：前 TOP_N 条里有期望出处；无答案的题：正确拒答
    top: list[tuple[str, str | None, float]]


def load_cases(path: Path = QA_FILE) -> list[Case]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [Case.model_validate(c) for c in raw.get("cases", [])]


def judge(case: Case, result: PolicySearchResult, top_n: int = TOP_N) -> CaseResult:
    top = [(s.doc_name, s.section, s.score) for s in result.sources[:top_n]]
    if case.no_answer:
        hit = not result.found
    else:
        hit = any(
            doc == case.doc and (case.section is None or case.section in (section or ""))
            for doc, section, _ in top
        )
    return CaseResult(case=case, found=result.found, hit=hit, top=top)


def summarize(results: list[CaseResult]) -> dict[str, float | int]:
    answer = [r for r in results if not r.case.no_answer]
    no_answer = [r for r in results if r.case.no_answer]

    def rate(items: list[CaseResult]) -> float:
        return round(sum(r.hit for r in items) / len(items), 3) if items else 0.0

    return {
        "answer_cases": len(answer),
        "hit_rate": rate(answer),
        "no_answer_cases": len(no_answer),
        "reject_rate": rate(no_answer),
    }


@dataclass
class RerankComparison:
    cases: int
    top1_vector: float
    top1_rerank: float


def retrieve(cases: list[Case]) -> list[PolicySearchResult]:
    """每题检索一次（不过滤、不重排）。"""
    with session_scope() as db:
        return [
            search(db, c.q, scopes_for(c.pack), top_k=TOP_K, threshold=0.0, rerank=False)
            for c in cases
        ]


def score(cases: list[Case], raw: list[PolicySearchResult]) -> dict[float, list[CaseResult]]:
    return {
        t: [judge(c, filter_hits(r.sources, t)) for c, r in zip(cases, raw, strict=True)]
        for t in THRESHOLDS
    }


def run(cases: list[Case]) -> dict[float, list[CaseResult]]:
    """每题检索一次，再按各阈值过滤打分。"""
    return score(cases, retrieve(cases))


def compare_rerank(cases: list[Case], raw: list[PolicySearchResult]) -> RerankComparison:
    """阈值 0.5 下，有答案的题第一条就是期望出处的比例：向量顺序 vs 重排后。"""
    vector_hits = rerank_hits_count = 0
    answer = [
        (c, filter_hits(r.sources)) for c, r in zip(cases, raw, strict=True) if not c.no_answer
    ]
    for case, kept in answer:
        vector_hits += judge(case, kept, top_n=1).hit
        ranked = PolicySearchResult(found=kept.found, sources=rerank_hits(case.q, kept.sources))
        rerank_hits_count += judge(case, ranked, top_n=1).hit
    n = len(answer) or 1
    return RerankComparison(len(answer), round(vector_hits / n, 3), round(rerank_hits_count / n, 3))


def report(
    by_threshold: dict[float, list[CaseResult]], rerank: RerankComparison | None = None
) -> str:
    lines = ["# 知识库评测结果", "", "由 `python -m app.rag.evaluate` 生成。", ""]
    lines += ["| 阈值 | Top-4 命中率 | 拒答率 |", "|---|---|---|"]
    for t, results in by_threshold.items():
        s = summarize(results)
        lines.append(
            f"| {t} | {s['hit_rate']:.0%}（{s['answer_cases']} 题） | "
            f"{s['reject_rate']:.0%}（{s['no_answer_cases']} 题） |"
        )
    if rerank is not None:
        lines += [
            "",
            f"## 重排对比（阈值 {THRESHOLD}，{rerank.cases} 道有答案的题）",
            "",
            "| 排序 | Top-1 命中率 |",
            "|---|---|",
            f"| 向量相似度 | {rerank.top1_vector:.0%} |",
            f"| 重排后 | {rerank.top1_rerank:.0%} |",
        ]
    lines += [
        "",
        f"## 逐题结果（阈值 {THRESHOLD}）",
        "",
        "| 问题 | 期望 | 结果 | 前几条出处（相似度） |",
    ]
    lines.append("|---|---|---|---|")
    for r in by_threshold[THRESHOLD]:
        expect = "应拒答" if r.case.no_answer else f"{r.case.doc} {r.case.section or ''}".strip()
        top = "；".join(f"{d} {s or ''}（{score:.2f}）" for d, s, score in r.top) or "（无）"
        lines.append(f"| {r.case.q} | {expect} | {'✅' if r.hit else '❌'} | {top} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="知识库评测")
    parser.add_argument("--out", type=Path, help="把评测报告写入 Markdown 文件")
    args = parser.parse_args()
    cases = load_cases()
    try:
        raw = retrieve(cases)
    except BizError as exc:
        sys.exit(f"评测需要 Embedding 模型：{exc.message}。请先配置 Key 并执行入库。")
    text = report(score(cases, raw), compare_rerank(cases, raw))
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
