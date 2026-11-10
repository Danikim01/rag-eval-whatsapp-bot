from modamayor.run_eval import evaluate, summarize

QUESTIONS = [
    {"id": "q1", "type": "directa", "question": "a?", "key_facts": ["4800"], "handoff": False},
    {"id": "q2", "type": "directa", "question": "b?", "key_facts": ["12"], "handoff": False},
    {"id": "q3", "type": "contradiccion", "question": "c?", "key_facts": ["17800"],
     "must_not_say": ["14500"], "handoff": False},
]

ANSWERS = {"a?": "sale 4.800", "b?": "no se", "c?": "17.800 y antes 14.500"}


def test_evaluate_scores_each_question():
    results = evaluate(QUESTIONS, lambda q: ANSWERS[q])
    assert [r["id"] for r in results] == ["q1", "q2", "q3"]
    assert [r["passed"] for r in results] == [True, False, False]
    assert results[1]["missing"] == ["12"]
    assert results[2]["forbidden_hits"] == ["14500"]
    assert results[0]["answer"] == "sale 4.800"


def test_summarize_totals_and_by_type():
    summary = summarize(evaluate(QUESTIONS, lambda q: ANSWERS[q]))
    assert summary["passed"] == 1
    assert summary["total"] == 3
    assert summary["by_type"] == {"directa": [1, 2], "contradiccion": [0, 1]}


def test_retrieval_report_hits_when_all_expected_sources_retrieved():
    from modamayor.loader import Chunk
    from modamayor.run_eval import retrieval_report

    questions = [
        {"id": "q1", "sources": ["a.txt", "b.md"]},
        {"id": "q2", "sources": ["a.txt"]},
        {"id": "q3", "sources": []},
    ]
    retrieved = {
        "q1": [Chunk("a#0", "x", "a.txt")],
        "q2": [Chunk("a#0", "x", "a.txt"), Chunk("c#0", "y", "c.txt")],
        "q3": [Chunk("c#0", "y", "c.txt")],
    }
    report = retrieval_report(questions, lambda q: retrieved[q["id"]])
    assert [r["hit"] for r in report] == [False, True, True]
    assert report[0]["missing_sources"] == ["b.md"]
    assert report[1]["retrieved_ids"] == ["a#0", "c#0"]
