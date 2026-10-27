"""评测打分逻辑（不调用 Embedding）。"""

from app.rag.evaluate import Case, judge, load_cases, report, summarize
from app.rag.ingest import load_chunks
from app.rag.retriever import PolicySearchResult, Source, filter_hits


def _result(*hits: tuple[str, str | None, float]) -> PolicySearchResult:
    return filter_hits([Source(content="x", doc_name=d, section=s, score=sc) for d, s, sc in hits])


def test_hit_requires_doc_and_section_in_top4() -> None:
    case = Case(q="招待标准", doc="费用报销管理制度", section="4.2")
    good = _result(
        ("销售提成制度", "1", 0.9), ("费用报销管理制度", "4 客户招待 > 4.2 招待标准", 0.8)
    )
    assert judge(case, good).hit
    wrong_section = _result(("费用报销管理制度", "4 客户招待 > 4.3 票据要求", 0.8))
    assert not judge(case, wrong_section).hit
    fifth = _result(
        *[(f"其他{i}", None, 0.9 - i / 100) for i in range(4)], ("费用报销管理制度", "4.2", 0.7)
    )
    assert not judge(case, fifth).hit  # 第 5 条才命中不算


def test_no_answer_case_scores_rejection() -> None:
    case = Case(q="年假几天", no_answer=True)
    assert judge(case, _result()).hit
    assert not judge(case, _result(("费用报销管理制度", None, 0.55))).hit


def test_summary_and_report() -> None:
    results = [
        judge(Case(q="a", doc="D"), _result(("D", None, 0.8))),
        judge(Case(q="b", doc="D"), _result(("E", None, 0.8))),
        judge(Case(q="c", no_answer=True), _result()),
    ]
    assert summarize(results) == {
        "answer_cases": 2,
        "hit_rate": 0.5,
        "no_answer_cases": 1,
        "reject_rate": 1.0,
    }
    text = report({0.4: results, 0.5: results, 0.6: results})
    assert "| 0.5 | 50%（2 题） | 100%（1 题） |" in text and "应拒答" in text


def test_qa_set_points_to_existing_documents() -> None:
    """评测集里期望的文档都真实存在，且至少 15 题、包含无答案题。"""
    cases = load_cases()
    assert len(cases) >= 15 and sum(c.no_answer for c in cases) >= 3
    docs = {c.doc_name for scope in ("company", "pack:llm_deploy") for c in load_chunks(scope)}
    for case in cases:
        if not case.no_answer:
            assert case.doc in docs, case.q


def test_auto_ingest_decision() -> None:
    from app.rag.autoload import decide

    assert decide(lambda: False, lambda: True) == "skip_not_empty"
    assert decide(lambda: True, lambda: False) == "skip_no_embedding"
    assert decide(lambda: True, lambda: True) == "ingest"
